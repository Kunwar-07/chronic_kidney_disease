// Local development uses the API on port 8000; hosted deployments use a same-origin /api proxy.
export const API_BASE = typeof location !== 'undefined' && ['localhost', '127.0.0.1'].includes(location.hostname)
  ? `${location.protocol}//${location.hostname}:8000` : '';

export function createClient({base = API_BASE, fetcher = fetch, storage = null, now = Date.now} = {}) {
  const storageKey = 'nephra.session.v1';
  let config, session = null, refreshing = null;
  let generation = 0;
  const listeners = new Set();
  try { session = JSON.parse(storage?.getItem(storageKey) || 'null'); } catch { /* Storage may be unavailable. */ }
  if (!session?.access_token || !session?.refresh_token || !session?.user?.id || !Number.isFinite(session?.expires_at)) session = null;
  const setSession = value => {
    const previous = session?.user?.id;
    session = value;
    try { value ? storage?.setItem(storageKey, JSON.stringify(value)) : storage?.removeItem(storageKey); } catch { /* In-memory auth still works. */ }
    if (previous !== session?.user?.id) listeners.forEach(listener => listener());
  };
  const request = async (url, options = {}) => {
    let response;
    try { response = await fetcher(url, {...options, signal: AbortSignal.timeout(20000)}); }
    catch { throw new Error('Could not reach the service. Check your connection and that the backend is running.'); }
    let data;
    try { data = response.status === 204 ? null : await response.json(); }
    catch { throw new Error('The service returned an unreadable response.'); }
    if (!response.ok) {
      const error = new Error(data?.error?.message || data?.msg || data?.error_description ||
        (typeof data?.error === 'string' ? data.error : null) || data?.message || data?.errors?.join(' ') || `Request failed (${response.status}).`);
      error.status = response.status;
      throw error;
    }
    return data;
  };
  const configure = async () => {
    if (!config) {
      const result = await request(`${base}/api/v1/config`);
      if (!result?.supabase?.url || !result.supabase.publishableKey) throw new Error('Saved assessments are not configured on the backend.');
      config = result.supabase;
    }
    return config;
  };
  const auth = async (path, body, token) => {
    const cfg = await configure();
    return request(`${cfg.url}/auth/v1/${path}`, {method: 'POST',
      headers: {apikey: cfg.publishableKey, 'Content-Type': 'application/json', ...(token ? {Authorization: `Bearer ${token}`} : {})},
      ...(body ? {body: JSON.stringify(body)} : {}),
    });
  };
  const acceptSession = data => {
    if (!data?.access_token || !data.refresh_token || !data.user?.id || !Number.isFinite(data.expires_in)) {
      throw new Error('Sign-in did not return a valid session. Please sign in again.');
    }
    setSession({access_token: data.access_token, refresh_token: data.refresh_token,
      expires_at: now() + data.expires_in * 1000, user: {id: data.user.id, email: data.user.email}});
  };
  const accessToken = async () => {
    if (!session) throw new Error('Sign in before saving an assessment.');
    if (session.expires_at > now() + 60000) return session.access_token;
    if (!refreshing) {
      const version = generation, refreshToken = session.refresh_token;
      refreshing = (async () => {
        try {
          const data = await auth('token?grant_type=refresh_token', {refresh_token: refreshToken});
          if (version !== generation) throw new Error('Your session changed. Sign in again.');
          acceptSession(data);
        } catch (error) {
          if (version === generation && [400, 401, 403].includes(error.status)) setSession(null);
          throw error;
        } finally { refreshing = null; }
      })();
    }
    await refreshing;
    if (!session) throw new Error('Your session expired. Sign in again.');
    return session.access_token;
  };
  const authenticated = async (path, body) => {
    const token = await accessToken();
    try {
      return await request(`${base}/api/v1/${path}`, {method: body ? 'POST' : 'GET',
        headers: {Authorization: `Bearer ${token}`, ...(body ? {'Content-Type': 'application/json'} : {})},
        ...(body ? {body: JSON.stringify(body)} : {}),
      });
    } catch (error) {
      if (error.status === 401) { generation++; setSession(null); }
      throw error;
    }
  };
  return {
    configure,
    onAuthChange(listener) { listeners.add(listener); return () => listeners.delete(listener); },
    syncStorage() {
      let value = null;
      try { value = JSON.parse(storage?.getItem(storageKey) || 'null'); } catch {}
      if (!value?.access_token || !value?.refresh_token || !value?.user?.id || !Number.isFinite(value?.expires_at)) value = null;
      generation++;
      setSession(value);
    },
    async restore() {
      if (!session) return null;
      try {
        const token = await accessToken(), cfg = await configure();
        const user = await request(`${cfg.url}/auth/v1/user`, {headers: {apikey: cfg.publishableKey, Authorization: `Bearer ${token}`}});
        if (user.id !== session?.user?.id) setSession(null);
      } catch (error) {
        if ([400,401,403].includes(error.status)) setSession(null);
        else throw error;
      }
      return session?.user || null;
    },
    getUser: () => session?.user || null,
    async signIn(email, password) {
      const version = ++generation;
      const data = await auth('token?grant_type=password', {email, password});
      if (version === generation) acceptSession(data);
    },
    async signUp(email, password) {
      const version = ++generation;
      const data = await auth('signup', {email, password});
      if (data.access_token && version === generation) { acceptSession(data); return true; }
      return false;
    },
    async signOut() {
      const token = session?.access_token;
      generation++;
      setSession(null);
      if (token) await auth('logout?scope=local', null, token);
    },
    async saveAssessment(task, input) {
      const saved = await authenticated('assessments', {task, input});
      if (!saved?.id || !saved.created_at || saved.result?.status !== 'ok') throw new Error('The server did not confirm the saved assessment.');
      return saved;
    },
    explainAssessment: (task, input) => request(`${base}/api/v1/explanation`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({task, input}),
    }),
    getAssessment: id => authenticated(`assessments/${encodeURIComponent(id)}`),
    listAssessments: () => authenticated('assessments?limit=10&offset=0'),
  };
}

let persistentStorage = null;
try {
  if (typeof window !== 'undefined') {
    persistentStorage = window.localStorage;
    const oldSession = window.sessionStorage.getItem('nephra.session.v1');
    if (!persistentStorage.getItem('nephra.session.v1') && oldSession) persistentStorage.setItem('nephra.session.v1', oldSession);
    window.sessionStorage.removeItem('nephra.session.v1');
  }
} catch { /* In-memory auth remains available when storage is restricted. */ }
export const client = createClient({storage: persistentStorage});

if (typeof window !== "undefined") window.addEventListener("storage", event => {
  if (event.key === "nephra.session.v1" || event.key === null) client.syncStorage();
});
