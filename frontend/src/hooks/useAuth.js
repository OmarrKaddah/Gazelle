import { useState, useEffect, useCallback } from 'react';

const TOKEN_KEY = 'gazelle.auth.token';
const USER_KEY = 'gazelle.auth.user';

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

  const login = useCallback(async (username, password) => {
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
  }, []);

  const logout = useCallback(async () => {
    try {
      await fetch('/api/logout', { method: 'POST', headers: authHeaders() });
    } catch {}
    clearAuth();
    setAuth({ token: null, user: null });
  }, []);

  // On mount, verify token is still valid
  useEffect(() => {
    if (!auth.token) return;
    fetch('/api/me', { headers: authHeaders() })
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (!d) {
          clearAuth();
          setAuth({ token: null, user: null });
        }
      })
      .catch(() => {});
  }, [auth.token]);

  return { ...auth, login, logout };
}
