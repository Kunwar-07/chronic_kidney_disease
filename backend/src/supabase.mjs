import {HttpError} from './errors.mjs';

export const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const unavailable = () => new HttpError(503, 'database_unavailable', 'Supabase is unavailable or its database setup is incomplete.');

// The caller's JWT is forwarded to PostgREST so database RLS remains effective.
// No service-role key, JWT decoding as authentication, or shared user session.
export function createSupabase(config, fetchImpl = fetch) {
  if (!config) return null;
  const request = async (resource, token, {method = 'GET', body, auth = false} = {}) => {
    try {
      const response = await fetchImpl(`${config.url}${resource}`, {
        method, redirect: 'error', signal: AbortSignal.timeout(config.timeoutMs),
        headers: {apikey: config.key, Authorization: `Bearer ${token}`,
          Accept: 'application/json', ...(body ? {'Content-Type': 'application/json'} : {}),
          ...(!auth && method !== 'GET' ? {Prefer: 'return=representation'} : {})},
        ...(body ? {body: JSON.stringify(body)} : {}),
      });
      if (response.status === 401 || (auth && response.status === 403)) {
        throw new HttpError(401, 'invalid_token', 'A valid Supabase user access token is required.');
      }
      if (response.status === 403) throw new HttpError(403, 'database_forbidden', 'Database access was denied.');
      if (!response.ok) throw unavailable();
      return await response.json();
    } catch (error) {
      if (error instanceof HttpError) throw error;
      // Never relay upstream bodies/errors, URLs, tokens, keys or health inputs.
      throw unavailable();
    }
  };
  const rows = async (...args) => {
    const result = await request(...args);
    if (!Array.isArray(result)) throw unavailable();
    return result;
  };
  const resource = (user, extra = {}) => '/rest/v1/assessments?' + new URLSearchParams({
    select: '*', user_id: `eq.${user.id}`, ...extra,
  });
  return {
    async authenticate(authorization) {
      const match = /^Bearer ([^\s]+)$/i.exec(authorization || '');
      if (!match) throw new HttpError(401, 'authentication_required', 'Use Authorization: Bearer <Supabase user access token>.');
      const token = match[1];
      const user = await request('/auth/v1/user', token, {auth: true});
      if (!user || !UUID.test(user.id) || user.role !== 'authenticated') {
        throw new HttpError(401, 'invalid_token', 'A valid Supabase user access token is required.');
      }
      return {id: user.id, token};
    },
    async create(user, task, input, result) {
      const saved = await rows('/rest/v1/assessments?select=*', user.token, {
        method: 'POST', body: {user_id: user.id, task, input, result},
      });
      if (saved.length !== 1) throw unavailable();
      return saved[0];
    },
    async list(user, limit, offset) {
      return rows(resource(user, {order: 'created_at.desc,id.desc', limit, offset,
        select: 'id,created_at,task,model_version:result->>model_version,probability:result->probability'}), user.token);
    },
    async get(user, id) {
      return (await rows(resource(user, {id: `eq.${id}`, limit: 1}), user.token))[0] || null;
    },
    async delete(user, id) {
      return (await rows(resource(user, {id: `eq.${id}`, select: 'id'}), user.token, {method: 'DELETE'})).length === 1;
    },
  };
}
