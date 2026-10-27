import http from 'node:http';
import {randomUUID} from 'node:crypto';
import {TASKS, metadata, assess, validateInput} from './models.mjs';
import {buildOpenAPI} from './openapi.mjs';
import {HttpError} from './errors.mjs';
import {createSupabase, UUID} from './supabase.mjs';
import {createExplanationService} from './gemini.mjs';
const fail = (status, code, message) => { throw new HttpError(status, code, message); };
const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);

function readBody(request, config) {
  if (request.headers['content-encoding'] && request.headers['content-encoding'] !== 'identity') {
    fail(415, 'unsupported_encoding', 'Compressed request bodies are not supported.');
  }
  if (!/^application\/json(?:\s*;.*)?$/i.test(request.headers['content-type'] || '')) {
    fail(415, 'unsupported_media_type', 'Use Content-Type: application/json.');
  }
  if (Number(request.headers['content-length']) > config.maxBodyBytes) {
    fail(413, 'body_too_large', 'Request body exceeds the configured limit.');
  }
  return new Promise((resolve, reject) => {
    let size = 0;
    const chunks = [];
    const cleanup = () => {
      clearTimeout(timer);
      request.off('data', onData);
      request.off('end', onEnd);
      request.off('aborted', onAbort);
      request.off('error', onError);
    };
    const rejectBody = error => { cleanup(); reject(error); };
    const onError = () => rejectBody(new HttpError(400, 'incomplete_body', 'Could not read request body.'));
    const onAbort = () => rejectBody(new HttpError(400, 'incomplete_body', 'Request body was interrupted.'));
    const onData = chunk => {
      size += chunk.length;
      if (size > config.maxBodyBytes) {
        rejectBody(new HttpError(413, 'body_too_large', 'Request body exceeds the configured limit.'));
      } else chunks.push(chunk);
    };
    const onEnd = () => {
      cleanup();
      try {
        resolve(JSON.parse(new TextDecoder('utf-8', {fatal: true}).decode(Buffer.concat(chunks))));
      } catch {
        reject(new HttpError(400, 'invalid_json', 'Request body must be valid UTF-8 JSON.'));
      }
    };
    const timer = setTimeout(() => rejectBody(new HttpError(408, 'body_timeout', 'Request body timed out.')), config.bodyTimeoutMs);
    timer.unref();
    request.on('data', onData);
    request.on('end', onEnd);
    request.on('aborted', onAbort);
    request.on('error', onError);
  });
}

function validateEnvelope(body, scenario = false) {
  if (!object(body)) fail(400, 'invalid_request', 'Request body must be a JSON object.');
  const allowed = scenario ? ['task', 'input', 'changes'] : ['task', 'input'];
  if (Object.keys(body).some(key => !allowed.includes(key))) {
    fail(400, 'invalid_request', `Only ${allowed.join(', ')} are accepted.`);
  }
  if (!TASKS.includes(body.task)) fail(400, 'invalid_task', 'task must be screening or biomarker.');
  for (const key of scenario ? ['input', 'changes'] : ['input']) {
    if (!object(body[key])) fail(400, 'invalid_request', `${key} must be a JSON object.`);
    if (Object.values(body[key]).some(value => value !== null && (typeof value !== 'number' || !Number.isFinite(value)))) {
      fail(400, 'invalid_request', `${key} values must be finite JSON numbers or null; numeric strings are not accepted.`);
    }
  }
  if (scenario && Object.keys(body.changes).length !== 1) {
    fail(400, 'invalid_request', 'Supply exactly one feature in changes.');
  }
}

export function createApp({config, registry, database = createSupabase(config.supabase), explanation = createExplanationService(config), onError = () => console.error('Backend request failed; input was not logged.')}) {
  const specification = buildOpenAPI(registry);
  const clients = new Map();
  // Bounded, expiring counters contain socket addresses only, never request data.
  const rateLimit = request => {
    const now = Date.now();
    for (const [key, entry] of clients) if (entry.reset <= now) clients.delete(key);
    const key = request.socket.remoteAddress || 'unknown';
    let entry = clients.get(key);
    if (!entry) {
      if (clients.size >= 2048) return Math.ceil(config.rateLimitWindowMs / 1000);
      entry = {count: 0, reset: now + config.rateLimitWindowMs};
      clients.set(key, entry);
    }
    entry.count += 1;
    return entry.count > config.rateLimitMax ? Math.max(1, Math.ceil((entry.reset - now) / 1000)) : 0;
  };
  const server = http.createServer({maxHeaderSize: 16384}, async (request, response) => {
    const requestId = randomUUID();
    response.setHeader('X-Request-Id', requestId);
    response.setHeader('Cache-Control', 'no-store');
    response.setHeader('X-Content-Type-Options', 'nosniff');
    response.setHeader('Referrer-Policy', 'no-referrer');
    response.setHeader('Content-Security-Policy', "default-src 'none'; frame-ancestors 'none'");
    response.setHeader('Vary', 'Origin');
    const json = (status, body) => {
      if (response.destroyed) return;
      response.writeHead(status, {'Content-Type': 'application/json; charset=utf-8'});
      response.end(request.method === 'HEAD' ? undefined : JSON.stringify(body));
    };
    try {
      const origin = request.headers.origin;
      if (origin) {
        if (!config.corsOrigins.includes(origin)) fail(403, 'origin_not_allowed', 'Origin is not allowed.');
        response.setHeader('Access-Control-Allow-Origin', origin);
        response.setHeader('Access-Control-Expose-Headers', 'X-Request-Id, Retry-After');
      }
      const url = new URL(request.url, 'http://localhost');
      const route = url.pathname;
      const collection = route === '/api/v1/assessments';
      const record = /^\/api\/v1\/assessments\/([^/]+)$/.exec(route);
      const savedRoute = collection || Boolean(record);
      const queryMethod = request.method === 'OPTIONS' ? request.headers['access-control-request-method'] : request.method;
      if (url.search && !(collection && ['GET', 'HEAD'].includes(queryMethod))) {
        fail(400, 'unexpected_query', 'Query parameters are only accepted for assessment history pagination.');
      }
      const modelTask = TASKS.find(task => route === `/api/v1/models/${task}`);
      const reads = {
        '/health': () => ({status: 'ok', service: 'nephra-backend'}),
        '/ready': () => ({status: 'ready', models: TASKS, run_id: registry.report.run_id,
          database: database ? 'configured_unverified' : 'disabled'}),
        '/openapi.json': () => specification,
        '/api/v1/config': () => ({supabase: config.supabase ? {
          url: config.supabase.url, publishableKey: config.supabase.key,
        } : null}),
        '/api/v1/models': () => ({models: TASKS.map(task => metadata(registry.models[task]))}),
        '/api/v1/research': () => registry.report,
        '/api/v1/sources': () => registry.sources,
      };
      const read = modelTask ? () => metadata(registry.models[modelTask]) : Object.hasOwn(reads, route) ? reads[route] : null;
      const write = ['/api/v1/predict', '/api/v1/validate', '/api/v1/scenarios', '/api/v1/explanation'].includes(route);
      if (!read && !write && !savedRoute) fail(404, 'not_found', 'Endpoint not found.');
      const methods = collection ? 'GET, HEAD, POST, OPTIONS' : record ? 'GET, HEAD, DELETE, OPTIONS' : read ? 'GET, HEAD, OPTIONS' : 'POST, OPTIONS';
      if (request.method === 'OPTIONS') {
        response.setHeader('Allow', methods);
        response.setHeader('Vary', 'Origin, Access-Control-Request-Method, Access-Control-Request-Headers');
        const requested = request.headers['access-control-request-method'];
        const headers = (request.headers['access-control-request-headers'] || '').split(',').map(value => value.trim().toLowerCase()).filter(Boolean);
        const allowedHeaders = savedRoute ? ['content-type', 'authorization'] : ['content-type'];
        if ((requested && !methods.split(', ').includes(requested)) || headers.some(header => !allowedHeaders.includes(header))) {
          fail(403, 'preflight_not_allowed', 'Requested CORS method or headers are not allowed.');
        }
        response.setHeader('Access-Control-Allow-Methods', methods);
        response.setHeader('Access-Control-Allow-Headers', savedRoute ? 'Content-Type, Authorization' : 'Content-Type');
        response.writeHead(204).end();
        return;
      }
      if (!methods.split(', ').includes(request.method)) {
        response.setHeader('Allow', methods);
        fail(405, 'method_not_allowed', 'Method not allowed for this endpoint.');
      }
      if (!['/health', '/ready'].includes(route)) {
        const retry = rateLimit(request);
        if (retry) {
          response.setHeader('Retry-After', retry);
          fail(429, 'rate_limited', 'Too many requests; retry later.');
        }
      }
      if (savedRoute) {
        if (!database) fail(503, 'database_not_configured', 'Configure Supabase and apply the database migration to enable saved assessments.');
        if (record && !UUID.test(record[1])) fail(400, 'invalid_id', 'Assessment ID must be a UUID.');
        const user = await database.authenticate(request.headers.authorization);
        if (collection && request.method === 'POST') {
          const body = await readBody(request, config);
          validateEnvelope(body);
          const artifact = registry.models[body.task];
          const result = assess(artifact, body.input);
          if (result.status === 'invalid') { json(422, result); return; }
          const input = validateInput(artifact, body.input).values;
          const saved = await database.create(user, body.task, input, result);
          response.setHeader('Location', `/api/v1/assessments/${saved.id}`);
          json(201, saved);
        } else if (collection) {
          for (const key of url.searchParams.keys()) {
            if (!['limit', 'offset'].includes(key) || url.searchParams.getAll(key).length !== 1) {
              fail(400, 'invalid_pagination', 'Only one limit and one offset parameter are accepted.');
            }
          }
          const page = (name, fallback, min, max) => {
            const raw = url.searchParams.get(name) ?? String(fallback);
            if (!/^\d+$/.test(raw) || Number(raw) < min || Number(raw) > max) {
              fail(400, 'invalid_pagination', `${name} must be an integer between ${min} and ${max}.`);
            }
            return Number(raw);
          };
          const limit = page('limit', 20, 1, 100), offset = page('offset', 0, 0, 1000000);
          json(200, {assessments: await database.list(user, limit, offset), limit, offset});
        } else if (request.method === 'DELETE') {
          if (!await database.delete(user, record[1])) fail(404, 'not_found', 'Assessment not found.');
          response.writeHead(204).end();
        } else {
          const saved = await database.get(user, record[1]);
          if (!saved) fail(404, 'not_found', 'Assessment not found.');
          json(200, saved);
        }
        return;
      }
      if (read) { json(200, read()); return; }
      const body = await readBody(request, config);
      const scenario = route === '/api/v1/scenarios';
      validateEnvelope(body, scenario);
      const artifact = registry.models[body.task];
      if (route === '/api/v1/validate') {
        const validation = validateInput(artifact, body.input);
        const status = validation.errors.length ? 'invalid' : 'ok';
        json(status === 'ok' ? 200 : 422, {status, ...validation});
      } else if (scenario) {
        const baseline = assess(artifact, body.input);
        if (baseline.status === 'invalid') { json(422, {stage: 'baseline', ...baseline}); return; }
        const alternative = assess(artifact, {...body.input, ...body.changes});
        if (alternative.status === 'invalid') { json(422, {stage: 'scenario', ...alternative}); return; }
        json(200, {status: 'ok', baseline, scenario: alternative,
          probability_difference: alternative.probability - baseline.probability,
          interpretation: 'Hypothetical model behavior, not a causal effect or a treatment recommendation.'});
      } else {
        const result = assess(artifact, body.input);
        if (route === '/api/v1/explanation') {
          if (result.status === 'invalid') { json(422, result); return; }
          json(200, await explanation.explain(body.task, body.input, result));
        } else {
          json(result.status === 'ok' ? 200 : 422, result);
        }
      }
    } catch (error) {
      if (!(error instanceof HttpError)) onError();
      // Close on errors so unread or oversized bodies cannot occupy a keep-alive connection.
      response.setHeader('Connection', 'close');
      if (error instanceof HttpError && error.status === 401) response.setHeader('WWW-Authenticate', 'Bearer');
      request.resume();
      json(error instanceof HttpError ? error.status : 500, {
        status: 'error', error: {
          code: error instanceof HttpError ? error.code : 'internal_error',
          message: error instanceof HttpError ? error.message : 'An internal error occurred.',
        }, request_id: requestId,
      });
    }
  });
  server.requestTimeout = config.bodyTimeoutMs + 5000;
  server.headersTimeout = Math.min(10000, server.requestTimeout);
  server.keepAliveTimeout = 5000;
  server.maxRequestsPerSocket = 100;
  return server;
}
