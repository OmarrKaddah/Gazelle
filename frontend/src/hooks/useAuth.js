import { useState, useEffect, useCallback } from 'react';

const TOKEN_KEY = 'gazelle.auth.token';
const USER_KEY = 'gazelle.auth.user';
const MOCK_RUNTIME_TOKEN = 'mock-runtime-token';
const MOCK_RUNTIME_USER = {
  id: '11111111-1111-1111-1111-111111111111',
  username: 'local-admin',
  name: 'Local Admin',
  role: 'admin',
  clearance: 'restricted',
};

export function loadAuth() {
  return {
    token: localStorage.getItem(TOKEN_KEY),
    user: JSON.parse(localStorage.getItem(USER_KEY) || 'null'),
  };
}

export function saveAuth(token, user) {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function clearAuth() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

export function authHeaders() {
  const token = localStorage.getItem(TOKEN_KEY);
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export function useAuth() {
  const [auth, setAuth] = useState(loadAuth);
  const [ready, setReady] = useState(false);
  const [mockRuntime, setMockRuntime] = useState(false);

  const login = useCallback(async (username, password) => {
    if (mockRuntime) {
      saveAuth(MOCK_RUNTIME_TOKEN, MOCK_RUNTIME_USER);
      setAuth({ token: MOCK_RUNTIME_TOKEN, user: MOCK_RUNTIME_USER });
      return { ok: true };
    }
    const res = await fetch('/api/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    });
    const raw = await res.text();
    let data = {};
    try {
      data = raw ? JSON.parse(raw) : {};
    } catch {
      return { ok: false, error: 'Server error (invalid response)' };
    }
    if (!data.ok) {
      return { ok: false, error: data.error || 'Login failed' };
    }
    saveAuth(data.token, data.user);
    setAuth({ token: data.token, user: data.user });
    return { ok: true };
  }, [mockRuntime]);

  const logout = useCallback(async () => {
    if (mockRuntime) {
      saveAuth(MOCK_RUNTIME_TOKEN, MOCK_RUNTIME_USER);
      setAuth({ token: MOCK_RUNTIME_TOKEN, user: MOCK_RUNTIME_USER });
      return;
    }
    try {
      await fetch('/api/logout', { method: 'POST', headers: authHeaders() });
    } catch {}
    clearAuth();
    setAuth({ token: null, user: null });
  }, [mockRuntime]);

  // On mount, verify token is still valid
  useEffect(() => {
    fetch('/api/info')
      .then((r) => r.json())
      .then((d) => {
        const nextMockRuntime = !!d.mockRuntime;
        setMockRuntime(nextMockRuntime);
        if (nextMockRuntime) {
          const user = d.auth?.user || MOCK_RUNTIME_USER;
          saveAuth(MOCK_RUNTIME_TOKEN, user);
          setAuth({ token: MOCK_RUNTIME_TOKEN, user });
          setReady(true);
          return;
        }
        if (!auth.token) {
          setReady(true);
          return;
        }
        fetch('/api/me', { headers: authHeaders() })
          .then((r) => (r.ok ? r.json() : null))
          .then((d2) => {
            if (!d2) {
              clearAuth();
              setAuth({ token: null, user: null });
            }
            setReady(true);
          })
          .catch(() => setReady(true));
      })
      .catch(() => setReady(true));
  }, [auth.token]);

  return { ...auth, login, logout, ready };
}
