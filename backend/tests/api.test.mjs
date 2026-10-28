import test, {before, after} from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import {spawn} from 'node:child_process';
import {once} from 'node:events';
import {readFile, mkdtemp, writeFile, rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {loadConfig} from '../src/config.mjs';
import {loadRegistry, assess, TASKS} from '../src/models.mjs';
import {createApp} from '../src/app.mjs';

const config = loadConfig({RATE_LIMIT_MAX: '10000'});
const registry = await loadRegistry(config.dataDir);
const fixtures = Object.fromEntries(await Promise.all(TASKS.map(async task => [task,
  JSON.parse(await readFile(path.join(config.dataDir, `${task}-parity.json`), 'utf8'))])));
let server, base;
async function start(overrides = {}, modelRegistry = registry) {
  const instance = createApp({config: {...config, ...overrides}, registry: modelRegistry});
  await new Promise((resolve, reject) => {
    instance.once('error', reject);
    instance.listen(0, '127.0.0.1', resolve);
  });
  return {instance, url: `http://127.0.0.1:${instance.address().port}`};
}
async function stop(instance) {
  if (!instance) return;
  instance.closeAllConnections();
  await new Promise(resolve => instance.close(resolve));
}
before(async () => { const started = await start(); server = started.instance; base = started.url; });
after(async () => stop(server));
const post = (route, body, options = {}) => fetch(`${base}/api/v1/${route}`, {
  method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body), ...options,
});

for (const task of TASKS) {
  test(`${task}: HTTP results match ML runtime and all Python parity fixtures`, async () => {
    for (const fixture of fixtures[task]) {
      const response = await post('predict', {task, input: fixture.input});
      assert.equal(response.status, 200);
      assert.equal(response.headers.get('cache-control'), 'no-store');
      assert.ok(response.headers.get('x-request-id'));
      const result = await response.json();
      assert.deepEqual(result, assess(registry.models[task], fixture.input));
      assert.ok(Math.abs(result.probability - fixture.expected) < 1e-10);
    }
  });
  test(`${task}: completeness and plausibility gates return 422`, async () => {
    for (const input of [{}, {...fixtures[task][0].input, age: 17},
      {...fixtures[task][0].input, sex: 2}, {...fixtures[task][0].input, egfr: 90},
      {...fixtures[task][0].input, bp_systolic: 80, bp_diastolic: 90}]) {
      const response = await post('predict', {task, input});
      assert.equal(response.status, 422);
      const result = await response.json();
      assert.equal(result.status, 'invalid');
      assert.ok(result.errors.length);
    }
  });
  test(`${task}: validation exposes imputation and range warnings`, async () => {
    const response = await post('validate', {task, input: {...fixtures[task][0].input, diabetes: null, bmi: 99}});
    assert.equal(response.status, 200);
    const result = await response.json();
    assert.equal(result.quality.find(item => item.feature === 'diabetes').state, 'imputed');
    assert.equal(result.quality.find(item => item.feature === 'bmi').state, 'outside');
    assert.equal(result.values.diabetes, null);
    assert.equal(Object.hasOwn(result, 'probability'), false);
  });
}

test('biomarker requires at least two secondary labs', async () => {
  const input = {...fixtures.biomarker[0].input};
  for (const feature of registry.models.biomarker.features.slice(8)) input[feature] = null;
  const response = await post('predict', {task: 'biomarker', input});
  assert.equal(response.status, 422);
  assert.match((await response.json()).errors.join(' '), /two secondary biomarkers/);
});

test('scenario matches independent model evaluations and validates both stages', async () => {
  const input = fixtures.screening[0].input;
  const response = await post('scenarios', {task: 'screening', input, changes: {bmi: 35}});
  assert.equal(response.status, 200);
  const result = await response.json();
  assert.deepEqual(result.baseline, assess(registry.models.screening, input));
  assert.deepEqual(result.scenario, assess(registry.models.screening, {...input, bmi: 35}));
  assert.equal(result.probability_difference, result.scenario.probability - result.baseline.probability);
  for (const [baseline, changes, stage] of [[{}, {bmi: 35}, 'baseline'], [input, {age: 150}, 'scenario'], [input, {unknown: 1}, 'scenario']]) {
    const invalid = await post('scenarios', {task: 'screening', input: baseline, changes});
    assert.equal(invalid.status, 422);
    assert.equal((await invalid.json()).stage, stage);
  }
  for (const changes of [{}, {bmi: 35, age: 56}, null]) {
    assert.equal((await post('scenarios', {task: 'screening', input, changes})).status, 400);
  }
});

test('request envelope rejects unexpected fields, invalid types and non-finite numbers', async () => {
  for (const body of [null, [], {}, {task: '__proto__', input: {}}, {task: 'screening', input: []},
    {task: 'screening', input: {}, patient_name: 'must not be accepted'},
    ...['56', true, '', {}, []].map(age => ({task: 'screening', input: {age}}))]) {
    assert.equal((await post('predict', body)).status, 400);
  }
  const response = await post('predict', {}, {body: '{"task":"screening","input":{"age":1e400}}'});
  assert.equal(response.status, 400);
});

test('malformed JSON and unsupported encodings have structured errors', async () => {
  for (const [body, headers, status] of [
    ['{', {'Content-Type': 'application/json'}, 400],
    ['', {'Content-Type': 'application/json'}, 400],
    ['{}', {'Content-Type': 'text/plain'}, 415],
    ['{}', {'Content-Type': 'application/json', 'Content-Encoding': 'gzip'}, 415],
    [Buffer.from([0xff]), {'Content-Type': 'application/json'}, 400],
  ]) {
    const response = await post('predict', {}, {body, headers});
    assert.equal(response.status, status);
    const result = await response.json();
    assert.equal(result.status, 'error');
    assert.equal(result.request_id, response.headers.get('x-request-id'));
    assert.equal(JSON.stringify(result).includes('stack'), false);
  }
});

test('discovery, research, probes, methods and HEAD', async () => {
  for (const route of ['/health', '/ready', '/openapi.json', '/api/v1/models', '/api/v1/models/screening', '/api/v1/sources']) {
    const response = await fetch(base + route);
    assert.equal(response.status, 200);
    assert.ok(await response.json());
  }
  assert.deepEqual(await (await fetch(base + '/api/v1/research')).json(), registry.report);
  const model = await (await fetch(base + '/api/v1/models/biomarker')).json();
  assert.deepEqual(model.fields, registry.models.biomarker.fields);
  assert.equal(Object.hasOwn(model, 'estimator'), false);
  for (const route of ['/ml/research/inference.py', '/frontend/index.html', '/api/v1/models/toString', '/missing']) {
    assert.equal((await fetch(base + route)).status, 404);
  }
  const wrongMethod = await fetch(base + '/api/v1/predict');
  assert.equal(wrongMethod.status, 405);
  assert.equal(wrongMethod.headers.get('allow'), 'POST, OPTIONS');
  assert.equal((await fetch(base + '/api/v1/models?age=56')).status, 400);
  const head = await fetch(base + '/api/v1/models', {method: 'HEAD'});
  assert.equal(head.status, 200);
  assert.equal(await head.text(), '');
});

test('explanation endpoint returns safe built-in guidance when Gemini is not configured', async () => {
  const fixture = fixtures.screening[0];
  const response = await post('explanation', {task: 'screening', input: fixture.input});
  assert.equal(response.status, 200);
  const result = await response.json();
  assert.equal(result.source, 'fallback');
  assert.equal(result.model, null);
  assert.match(result.body, /not a diagnosis/i);
  assert.match(result.body, /eGFR/i);
  assert.doesNotMatch(JSON.stringify(result), /API key|secret/i);
});

test('CORS permits exact configured origins and checks preflight', async () => {
  const allowed = await fetch(base + '/health', {headers: {Origin: 'http://127.0.0.1:4173'}});
  assert.equal(allowed.headers.get('access-control-allow-origin'), 'http://127.0.0.1:4173');
  assert.equal(allowed.headers.get('access-control-allow-credentials'), null);
  for (const origin of ['https://untrusted.example', 'null', 'http://127.0.0.1:4173.evil.example']) {
    const denied = await fetch(base + '/health', {headers: {Origin: origin}});
    assert.equal(denied.status, 403);
    assert.equal(denied.headers.get('access-control-allow-origin'), null);
  }
  const preflight = headers => fetch(base + '/api/v1/predict', {method: 'OPTIONS', headers: {
    Origin: 'http://localhost:4173', 'Access-Control-Request-Method': 'POST',
    'Access-Control-Request-Headers': 'content-type', ...headers,
  }});
  assert.equal((await preflight()).status, 204);
  assert.equal((await preflight({'Access-Control-Request-Method': 'DELETE'})).status, 403);
  assert.equal((await preflight({'Access-Control-Request-Headers': 'authorization'})).status, 403);
});

test('declared and chunked oversized bodies are rejected; slow bodies time out', async () => {
  const {instance, url} = await start({maxBodyBytes: 256, bodyTimeoutMs: 100});
  try {
    const tooBig = await fetch(url + '/api/v1/predict', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: ' '.repeat(257)});
    assert.equal(tooBig.status, 413);
    const raw = (chunk, finish) => new Promise((resolve, reject) => {
      const request = http.request(url + '/api/v1/predict', {method: 'POST', headers: {'Content-Type': 'application/json'}}, response => {
        response.resume();
        response.on('end', () => { request.destroy(); resolve(response.statusCode); });
      });
      request.on('error', reject);
      request.write(chunk);
      if (finish) request.end();
    });
    assert.equal(await raw(' '.repeat(257), true), 413);
    assert.equal(await raw('{', false), 408);
    assert.equal((await fetch(url + '/health')).status, 200);
  } finally { await stop(instance); }
});

test('rate limiting uses socket address, preserves probes and recovers after its window', async () => {
  const {instance, url} = await start({rateLimitMax: 1, rateLimitWindowMs: 100});
  try {
    assert.equal((await fetch(url + '/api/v1/models')).status, 200);
    const limited = await fetch(url + '/api/v1/models', {headers: {'X-Forwarded-For': '192.0.2.1'}});
    assert.equal(limited.status, 429);
    assert.equal(limited.headers.get('retry-after'), '1');
    assert.equal((await fetch(url + '/health')).status, 200);
    await new Promise(resolve => setTimeout(resolve, 120));
    assert.equal((await fetch(url + '/api/v1/models')).status, 200);
  } finally { await stop(instance); }
});

test('OpenAPI feature names and categories derive from existing artifacts', async () => {
  const specification = await (await fetch(base + '/openapi.json')).json();
  assert.equal(specification.openapi, '3.1.0');
  for (const task of TASKS) {
    const schema = specification.components.schemas[`${task}Input`];
    assert.deepEqual(Object.keys(schema.properties), registry.models[task].features);
    assert.deepEqual(schema.required, ['age', 'sex']);
    assert.deepEqual(schema.properties.sex.enum, [0, 1]);
    assert.equal(schema.additionalProperties, false);
  }
  function inspect(value) {
    if (!value || typeof value !== 'object') return;
    if (value.$ref) assert.ok(specification.components.schemas[value.$ref.split('/').at(-1)]);
    Object.values(value).forEach(inspect);
  }
  inspect(specification);
});

test('invalid configuration and mismatched exports fail before startup', async () => {
  for (const env of [{PORT: 'abc'}, {PORT: '0'}, {MAX_BODY_BYTES: '-1'}, {RATE_LIMIT_MAX: '0'},
    {CORS_ORIGINS: '*'}, {CORS_ORIGINS: 'http://localhost:4173/path'}]) {
    assert.throws(() => loadConfig(env));
  }
  const directory = await mkdtemp(path.join(tmpdir(), 'nephra-model-test-'));
  try {
    for (const [name, data] of Object.entries({screening: registry.models.screening, biomarker: registry.models.biomarker,
      report: {...registry.report, run_id: 'wrong-run'}, sources: registry.sources})) {
      await writeFile(path.join(directory, `${name}.json`), JSON.stringify(data));
    }
    await assert.rejects(loadRegistry(directory), /report run mismatch/);
  } finally { await rm(directory, {recursive: true, force: true}); }
});

test('server entry point starts, serves readiness and shuts down on SIGTERM', {timeout: 10000}, async () => {
  const reservation = http.createServer();
  await new Promise(resolve => reservation.listen(0, '127.0.0.1', resolve));
  const port = reservation.address().port;
  await new Promise(resolve => reservation.close(resolve));
  const child = spawn(process.execPath, [new URL('../src/server.mjs', import.meta.url).pathname], {
    env: {...process.env, HOST: '127.0.0.1', PORT: String(port), MODEL_DATA_DIR: config.dataDir},
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  try {
    await new Promise((resolve, reject) => {
      let output = '';
      child.stdout.on('data', chunk => {
        output += chunk;
        if (output.includes('Nephra API listening')) resolve();
      });
      child.once('error', reject);
      child.once('exit', code => reject(new Error(`Server exited before startup: ${code}`)));
    });
    const ready = await fetch(`http://127.0.0.1:${port}/ready`);
    assert.equal(ready.status, 200);
    assert.equal((await ready.json()).status, 'ready');
    const exit = once(child, 'exit');
    child.kill('SIGTERM');
    assert.equal((await exit)[0], 0);
  } finally { if (child.exitCode === null) child.kill('SIGKILL'); }
});
