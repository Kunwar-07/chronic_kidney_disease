import path from 'node:path';
import {fileURLToPath} from 'node:url';

const defaultDataDir = fileURLToPath(new URL('../../frontend/data/', import.meta.url));

export function loadConfig(env = process.env) {
  const integer = (key, fallback, min, max) => {
    const raw = env[key] ?? String(fallback);
    const value = Number(raw);
    if (!/^\d+$/.test(raw) || !Number.isSafeInteger(value) || value < min || value > max) {
      throw new Error(`${key} must be an integer between ${min} and ${max}`);
    }
    return value;
  };
  const origins = (env.CORS_ORIGINS ?? 'http://127.0.0.1:4173,http://localhost:4173')
    .split(',').map(value => value.trim()).filter(Boolean);
  for (const origin of origins) {
    const url = new URL(origin);
    if (!['http:', 'https:'].includes(url.protocol) || url.origin !== origin) {
      throw new Error('CORS_ORIGINS must contain exact HTTP(S) origins without paths or wildcards');
    }
  }
  const supabaseUrl = env.SUPABASE_URL?.trim() || '';
  const supabaseKey = env.SUPABASE_PUBLISHABLE_KEY?.trim() || '';
  if (Boolean(supabaseUrl) !== Boolean(supabaseKey)) {
    throw new Error('Set both SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY, or leave both empty.');
  }
  if (supabaseUrl) {
    let url;
    try { url = new URL(supabaseUrl); } catch { throw new Error('SUPABASE_URL must be a valid project URL.'); }
    const local = ['localhost', '127.0.0.1', '[::1]'].includes(url.hostname);
    if ((url.protocol !== 'https:' && !(local && url.protocol === 'http:')) ||
        url.username || url.password || url.search || url.hash || url.pathname !== '/') {
      throw new Error('SUPABASE_URL must be an HTTPS origin (HTTP is allowed for local Supabase only).');
    }
    let legacyAnon = false;
    try {
      legacyAnon = supabaseKey.split('.').length === 3 &&
        JSON.parse(Buffer.from(supabaseKey.split('.')[1], 'base64url').toString()).role === 'anon';
    } catch { /* Only the legacy anon key format is accepted. */ }
    if ((!supabaseKey.startsWith('sb_publishable_') && !legacyAnon) || /\s/.test(supabaseKey)) {
      throw new Error('SUPABASE_PUBLISHABLE_KEY must be a publishable key or legacy anon key; admin keys are not supported.');
    }
  }
  const geminiApiKey = env.GEMINI_API_KEY?.trim() || '';
  if (geminiApiKey && /\s/.test(geminiApiKey)) {
    throw new Error('GEMINI_API_KEY must not contain whitespace.');
  }
  return {
    host: env.HOST || '127.0.0.1',
    port: integer('PORT', 8000, 1, 65535),
    dataDir: path.resolve(env.MODEL_DATA_DIR || defaultDataDir),
    corsOrigins: origins,
    maxBodyBytes: integer('MAX_BODY_BYTES', 16384, 256, 1048576),
    bodyTimeoutMs: integer('BODY_TIMEOUT_MS', 10000, 100, 60000),
    rateLimitMax: integer('RATE_LIMIT_MAX', 60, 1, 10000),
    rateLimitWindowMs: integer('RATE_LIMIT_WINDOW_MS', 60000, 100, 3600000),
    gemini: geminiApiKey ? {
      apiKey: geminiApiKey,
      model: env.GEMINI_MODEL?.trim() || 'gemini-3.5-flash-lite',
      timeoutMs: integer('GEMINI_TIMEOUT_MS', 8000, 1000, 30000),
    } : null,
    supabase: supabaseUrl ? {
      url: new URL(supabaseUrl).origin,
      key: supabaseKey,
      timeoutMs: integer('SUPABASE_TIMEOUT_MS', 10000, 100, 30000),
    } : null,
  };
}
