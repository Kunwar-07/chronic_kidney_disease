import test from 'node:test';
import assert from 'node:assert/strict';
import {createClient} from '../api.mjs';

const response = (data, status = 200) => new Response(status === 204 ? null : JSON.stringify(data), {status});
function harness({expires = 3600} = {}) {
  const requests = [], values = new Map();
  const storage = {getItem: key => values.get(key), setItem: (key,value) => values.set(key,value), removeItem: key => values.delete(key)};
  let mode = '', time = 1000000;
  const fetcher = async (url, options = {}) => {
    requests.push({url, options});
    if (url.endsWith('/api/v1/config')) return response({supabase: {url: 'https://project.supabase.co', publishableKey: 'sb_publishable_test'}});
    if (url.includes('/auth/v1/token')) {
      if (mode === 'auth-fail') return response({msg: 'Invalid login credentials'}, 400);
      return response({access_token: url.includes('refresh_token') ? 'refreshed-token' : 'user-token', refresh_token: 'refresh-secret', expires_in: expires, user: {id: 'user-one', email: 'test@example.com'}});
    }
    if (url.endsWith('/auth/v1/user')) return mode === 'unauthorized' ? response({msg:'Session expired'},401) : response({id:'user-one',email:'test@example.com'});
    if (url.includes('/auth/v1/signup') && mode === 'instant-signup') return response({access_token:'user-token',refresh_token:'refresh-secret',expires_in:3600,user:{id:'user-one',email:'test@example.com'}});
    if (url.includes('/auth/v1/signup')) return response({user: {id: 'user-one'}});
    if (url.includes('/auth/v1/logout')) return response(null, 204);
    if (mode === 'network-fail') throw new Error('offline');
    if (mode === 'unauthorized') return response({error: {message: 'Session expired'}}, 401);
    if (mode === 'db-fail') return response({error: {message: 'Database unavailable'}}, 503);
    if (url.includes('assessments?')) return response({assessments: [], limit: 10, offset: 0});
    if (mode === 'bad-save') return response({status: 'ok'});
    return response({id: 'saved-id', created_at: '2026-10-25T12:00:00Z', result: {status: 'ok', probability: .25}});
  };
  const options = {base: 'http://localhost:8000', fetcher, storage, now: () => time};
  return {client: createClient(options), options, requests, values, setMode: value => mode = value, advance: ms => time += ms};
}

test('login goes to Supabase; save goes to backend with user token and inputs only', async () => {
  const h = harness();
  await h.client.signIn('test@example.com', 'test-password');
  const input = {age: 56, sex: 0, bmi: 28.2, diabetes: 0};
  const saved = await h.client.saveAssessment('screening', input);
  assert.equal(saved.id, 'saved-id');
  const login = h.requests.find(row => row.url.includes('grant_type=password'));
  assert.equal(login.url, 'https://project.supabase.co/auth/v1/token?grant_type=password');
  assert.equal(JSON.parse(login.options.body).password, 'test-password');
  const request = h.requests.at(-1);
  assert.equal(request.url, 'http://localhost:8000/api/v1/assessments');
  assert.equal(request.options.headers.Authorization, 'Bearer user-token');
  assert.deepEqual(JSON.parse(request.options.body), {task: 'screening', input});
  const stored = [...h.values.values()].join('');
  assert.doesNotMatch(stored, /test-password|"age"|"probability"/);
  assert.equal(createClient(h.options).getUser().id, 'user-one');
});

test('signed-out submission is blocked before making a save request', async () => {
  const h = harness();
  await assert.rejects(h.client.saveAssessment('screening', {}), /Sign in/);
  assert.equal(h.requests.length, 0);
});

test('signup needing confirmation does not create an authenticated session', async () => {
  const h = harness();
  assert.equal(await h.client.signUp('test@example.com','test-password'), false);
  assert.equal(h.client.getUser(), null);
});

test('failed sign-in surfaces provider error without storing credentials', async () => {
  const h = harness(); h.setMode('auth-fail');
  await assert.rejects(h.client.signIn('test@example.com','wrong'), /Invalid login credentials/);
  assert.equal(h.values.size, 0);
});

test('session refresh uses a single request for concurrent operations', async () => {
  const h = harness();
  await h.client.signIn('test@example.com', 'test-password');
  h.advance(3600000);
  await Promise.all([h.client.listAssessments(), h.client.listAssessments()]);
  assert.equal(h.requests.filter(row => row.url.includes('grant_type=refresh_token')).length, 1);
  assert.equal(h.requests.at(-1).options.headers.Authorization, 'Bearer refreshed-token');
});

test('save failures are never returned as a successful record and never auto-retried', async () => {
  for (const mode of ['db-fail', 'network-fail', 'bad-save']) {
    const h = harness(); await h.client.signIn('test@example.com','test-password'); h.setMode(mode);
    await assert.rejects(h.client.saveAssessment('screening', {age: 56}));
    assert.equal(h.requests.filter(row => row.url.endsWith('/assessments')).length, 1);
  }
});

test('expired/revoked session is cleared when backend rejects it', async () => {
  const h = harness(); await h.client.signIn('test@example.com','test-password'); h.setMode('unauthorized');
  await assert.rejects(h.client.listAssessments(), /Session expired/);
  assert.equal(h.client.getUser(), null);
  assert.equal(h.values.size, 0);
});

test('sign-out clears tab session and revokes only the current session', async () => {
  const h = harness(); await h.client.signIn('test@example.com','test-password');
  await h.client.signOut();
  assert.equal(h.client.getUser(), null);
  assert.equal(h.values.size, 0);
  assert.match(h.requests.at(-1).url, /logout\?scope=local$/);
});

test('invalid saved session is ignored and missing backend configuration is explicit', async () => {
  const client = createClient({storage: {getItem: () => '{broken'}, fetcher: async () => response({supabase: null})});
  assert.equal(client.getUser(), null);
  await assert.rejects(client.configure(), /not configured/);
});


test('one login survives reload and saves multiple tests without another password request', async () => {
  const h = harness();
  await h.client.signIn('test@example.com','test-password');
  const reopened = createClient(h.options);
  assert.equal((await reopened.restore()).id, 'user-one');
  await reopened.saveAssessment('screening', {age:56});
  await reopened.saveAssessment('biomarker', {age:56});
  assert.equal(h.requests.filter(row => row.url.includes('grant_type=password')).length, 1);
  assert.equal(h.requests.filter(row => row.url.endsWith('/assessments')).length, 2);
});

test('signup immediately authenticates when confirmation is disabled', async () => {
  const h = harness(); h.setMode('instant-signup');
  let changes = 0;
  h.client.onAuthChange(() => changes++);
  assert.equal(await h.client.signUp('test@example.com','test-password'), true);
  await h.client.saveAssessment('screening',{age:56});
  assert.equal(changes, 1);
});

test('revoked persisted sessions are cleared on reload and signout synchronizes between tabs', async () => {
  const h = harness(); await h.client.signIn('test@example.com','test-password');
  const second = createClient(h.options);
  let changes = 0; second.onAuthChange(() => changes++);
  await h.client.signOut(); second.syncStorage();
  assert.equal(second.getUser(), null); assert.equal(changes, 1);
  await h.client.signIn('test@example.com','test-password'); h.setMode('unauthorized');
  assert.equal(await createClient(h.options).restore(), null);
  assert.equal(h.values.size, 0);
});
