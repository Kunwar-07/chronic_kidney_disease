import test, {before, after, beforeEach} from 'node:test';
import assert from 'node:assert/strict';
import {randomUUID} from 'node:crypto';
import {readFile} from 'node:fs/promises';
import {loadConfig} from '../src/config.mjs';
import {loadRegistry} from '../src/models.mjs';
import {createApp} from '../src/app.mjs';
import {createSupabase} from '../src/supabase.mjs';

const userA = '10000000-0000-4000-8000-000000000001';
const userB = '10000000-0000-4000-8000-000000000002';
const config = loadConfig({SUPABASE_URL: 'https://example.supabase.co', SUPABASE_PUBLISHABLE_KEY: 'sb_publishable_test', RATE_LIMIT_MAX: '10000'});
const registry = await loadRegistry(config.dataDir);
const sample = JSON.parse(await readFile(new URL('../examples/screening.json', import.meta.url), 'utf8'));
const records = new Map(), requests = [];
let mode = 'ok';
const json = (data, status = 200) => new Response(JSON.stringify(data), {status, headers: {'Content-Type': 'application/json'}});

// Mock only the remote Supabase HTTP boundary. The actual app and adapter run.
async function mockSupabase(url, options) {
  requests.push({url, options});
  assert.equal(options.headers.apikey, config.supabase.key);
  assert.equal(options.redirect, 'error');
  assert.ok(options.signal instanceof AbortSignal);
  const target = new URL(url);
  const token = options.headers.Authorization.slice(7);
  const userId = token === 'user-a' ? userA : token === 'user-b' ? userB : null;
  if (mode === 'network-error') throw new Error('sensitive upstream diagnostic');
  if (target.pathname === '/auth/v1/user') {
    if (mode === 'bad-auth-shape') return json({id: userA, role: 'service_role'});
    return userId ? json({id: userId, role: 'authenticated'}) : json({message: 'expired'}, 401);
  }
  assert.equal(target.pathname, '/rest/v1/assessments');
  if (mode === 'db-error') return json({message: 'private database diagnostic'}, 500);
  if (mode === 'forbidden') return json({}, 403);
  if (mode === 'bad-json') return new Response('invalid', {status: 200});
  if (mode === 'bad-shape') return json({unexpected: true});
  if (options.method === 'POST') {
    const body = JSON.parse(options.body);
    assert.equal(body.user_id, userId);
    const row = {id: randomUUID(), created_at: new Date().toISOString(), ...body};
    records.set(row.id, row);
    return json([row], 201);
  }
  assert.equal(target.searchParams.get('user_id'), `eq.${userId}`);
  let selected = [...records.values()].filter(row => row.user_id === userId);
  const id = target.searchParams.get('id')?.slice(3);
  if (id) selected = selected.filter(row => row.id === id);
  if (options.method === 'DELETE') {
    selected.forEach(row => records.delete(row.id));
    return json(selected.map(row => ({id: row.id})));
  }
  const offset = Number(target.searchParams.get('offset') || 0);
  const limit = Number(target.searchParams.get('limit') || 100);
  selected = selected.slice(offset, offset + limit);
  if (target.searchParams.get('select') !== '*') selected = selected.map(row => ({id: row.id, created_at: row.created_at,
    task: row.task, model_version: row.result.model_version, probability: row.result.probability}));
  return json(selected);
}

let server, base;
before(async () => {
  server = createApp({config, registry, database: createSupabase(config.supabase, mockSupabase)});
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  base = `http://127.0.0.1:${server.address().port}`;
});
after(async () => {
  server?.closeAllConnections();
  if (server) await new Promise(resolve => server.close(resolve));
});
beforeEach(() => { records.clear(); requests.length = 0; mode = 'ok'; });
const call = (route = '', {token = 'user-a', method = 'GET', body} = {}) => fetch(`${base}/api/v1/assessments${route}`, {
  method, headers: {...(token ? {Authorization: `Bearer ${token}`} : {}), ...(body ? {'Content-Type': 'application/json'} : {})},
  ...(body ? {body: JSON.stringify(body)} : {}),
});

test('creates computed assessments, lists summaries, reads and deletes own records', async () => {
  const response = await call('', {method: 'POST', body: sample});
  assert.equal(response.status, 201);
  const row = await response.json();
  assert.equal(response.headers.get('location'), `/api/v1/assessments/${row.id}`);
  assert.equal(row.user_id, userA);
  assert.equal(row.result.status, 'ok');
  assert.equal(row.result.task, sample.task);
  const page = await (await call('?limit=1&offset=0')).json();
  assert.equal(page.assessments.length, 1);
  assert.equal(page.assessments[0].id, row.id);
  assert.equal(Object.hasOwn(page.assessments[0], 'input'), false);
  assert.deepEqual(await (await call(`/${row.id}`)).json(), row);
  assert.equal((await call(`/${row.id}`, {method: 'DELETE'})).status, 204);
  assert.equal((await call(`/${row.id}`)).status, 404);
});

test('browser configuration exposes only the publishable project configuration', async () => {
  const result = await (await fetch(base + '/api/v1/config')).json();
  assert.deepEqual(result, {supabase: {url: config.supabase.url, publishableKey: config.supabase.key}});
  assert.equal(requests.length, 0);
});

test('verifies user with Supabase and forwards their token and owner filters on every database operation', async () => {
  const saved = await (await call('', {method: 'POST', body: sample})).json();
  assert.equal((await call(`/${saved.id}`, {token: 'user-b'})).status, 404);
  assert.equal((await call(`/${saved.id}`, {token: 'user-b', method: 'DELETE'})).status, 404);
  assert.deepEqual((await (await call('', {token: 'user-b'})).json()).assessments, []);
  assert.equal(records.size, 1);
  assert.equal(requests.filter(request => request.url.endsWith('/auth/v1/user')).length, 4);
  assert.ok(requests.filter(request => request.url.includes('/rest/v1/')).slice(1)
    .every(request => request.options.headers.Authorization === 'Bearer user-b'));
});

test('missing, expired and non-user tokens cannot read or save', async () => {
  for (const token of [null, 'expired']) {
    for (const method of ['GET', 'POST']) {
      const response = await call('', {token, method, ...(method === 'POST' ? {body: sample} : {})});
      assert.equal(response.status, 401);
      assert.equal(response.headers.get('www-authenticate'), 'Bearer');
    }
  }
  mode = 'bad-auth-shape';
  assert.equal((await call()).status, 401);
  assert.equal(records.size, 0);
  assert.equal(requests.some(request => request.url.includes('/rest/v1/')), false);
});

test('rejects forged ownership/results and incomplete model input before database writes', async () => {
  for (const extra of [{user_id: userB}, {result: {probability: 1}}, {id: randomUUID()}]) {
    assert.equal((await call('', {method: 'POST', body: {...sample, ...extra}})).status, 400);
  }
  assert.equal((await call('', {method: 'POST', body: {task: 'screening', input: {}}})).status, 422);
  assert.equal(records.size, 0);
  assert.equal(requests.some(request => request.url.includes('/rest/v1/')), false);
});

test('normal prediction remains stateless even when Supabase is configured', async () => {
  const response = await fetch(`${base}/api/v1/predict`, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(sample)});
  assert.equal(response.status, 200);
  assert.equal(records.size, 0);
  assert.equal(requests.length, 0);
});

test('validates IDs, pagination and methods without accepting arbitrary database filters', async () => {
  for (const suffix of ['/not-a-uuid', '?limit=101', '?limit=0', '?offset=-1', '?offset=1000001', '?user_id=someone', '?limit=2&limit=3']) {
    assert.equal((await call(suffix)).status, 400);
  }
  assert.equal((await call(`/${randomUUID()}`, {method: 'PATCH'})).status, 405);
  assert.equal((await call('', {method: 'DELETE'})).status, 405);
  assert.equal(requests.some(request => request.url.includes('/rest/v1/')), false);
});

test('upstream failures are sanitized and never reported as successful saves', async () => {
  for (const failure of ['db-error', 'network-error', 'bad-json', 'bad-shape', 'forbidden']) {
    mode = failure;
    const response = await call('', {method: 'POST', body: sample});
    assert.equal(response.status, failure === 'forbidden' ? 403 : 503);
    const text = await response.text();
    assert.doesNotMatch(text, /diagnostic|sb_publishable_test|user-a|example\.supabase/);
    assert.equal(records.size, 0);
  }
});

test('saved endpoints accept Authorization in CORS preflight', async () => {
  const response = await fetch(`${base}/api/v1/assessments/${randomUUID()}`, {method: 'OPTIONS', headers: {
    Origin: 'http://localhost:4173', 'Access-Control-Request-Method': 'DELETE',
    'Access-Control-Request-Headers': 'authorization, content-type',
  }});
  assert.equal(response.status, 204);
  assert.match(response.headers.get('access-control-allow-headers'), /Authorization/);
  assert.equal(requests.length, 0);
});

test('Supabase configuration rejects partial configuration, insecure URLs and admin keys', () => {
  for (const env of [
    {SUPABASE_URL: 'https://example.supabase.co'}, {SUPABASE_PUBLISHABLE_KEY: 'sb_publishable_test'},
    {SUPABASE_URL: 'http://example.supabase.co', SUPABASE_PUBLISHABLE_KEY: 'sb_publishable_test'},
    {SUPABASE_URL: 'https://user:secret@example.supabase.co', SUPABASE_PUBLISHABLE_KEY: 'sb_publishable_test'},
    {SUPABASE_URL: 'https://example.supabase.co/path', SUPABASE_PUBLISHABLE_KEY: 'sb_publishable_test'},
    {SUPABASE_URL: 'https://example.supabase.co', SUPABASE_PUBLISHABLE_KEY: 'sb_secret_admin'},
    {SUPABASE_URL: 'https://example.supabase.co', SUPABASE_PUBLISHABLE_KEY: `header.${Buffer.from('{"role":"service_role"}').toString('base64url')}.signature`},
  ]) assert.throws(() => loadConfig(env));
  assert.equal(loadConfig({}).supabase, null);
  assert.equal(createSupabase(null), null);
});

test('disabled database returns 503 and inference/readiness remain usable', async () => {
  const instance = createApp({config: loadConfig({}), registry});
  await new Promise(resolve => instance.listen(0, '127.0.0.1', resolve));
  const url = `http://127.0.0.1:${instance.address().port}`;
  try {
    const response = await fetch(url + '/api/v1/assessments');
    assert.equal(response.status, 503);
    assert.equal((await response.json()).error.code, 'database_not_configured');
    assert.equal((await (await fetch(url + '/ready')).json()).database, 'disabled');
  } finally {
    instance.closeAllConnections();
    await new Promise(resolve => instance.close(resolve));
  }
});

test('outbound Supabase timeout is enforced and sanitized', async () => {
  const store = createSupabase({...config.supabase, timeoutMs: 20}, (url, options) => new Promise((resolve, reject) => {
    options.signal.addEventListener('abort', () => reject(options.signal.reason), {once: true});
  }));
  // AbortSignal.timeout does not keep the event loop alive on its own.
  const keepAlive = setTimeout(() => {}, 1000);
  try { await assert.rejects(store.authenticate('Bearer user-a'), error => error.status === 503 && error.code === 'database_unavailable'); }
  finally { clearTimeout(keepAlive); }
});


test('paginated history accepts browser preflight before authenticated GET', async () => {
  const response = await fetch(`${base}/api/v1/assessments?limit=10&offset=0`, {method:'OPTIONS', headers:{
    Origin:'http://localhost:4173', 'Access-Control-Request-Method':'GET', 'Access-Control-Request-Headers':'authorization'
  }});
  assert.equal(response.status,204);
  assert.equal(response.headers.get('access-control-allow-origin'),'http://localhost:4173');
  assert.equal(requests.length,0);
});
