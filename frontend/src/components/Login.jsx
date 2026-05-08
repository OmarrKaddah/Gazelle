import React, { useState } from 'react';

const MOCK_USERS = [
  { username: 'omar', label: 'Omar · Admin · restricted', hint: 'admin123' },
  { username: 'sara', label: 'Sara · Senior Compliance · confidential', hint: 'compliance123' },
  { username: 'ahmed', label: 'Ahmed · Compliance Analyst · internal', hint: 'staff123' },
  { username: 'guest', label: 'Guest · External · public', hint: 'guest' },
];

export default function Login({ onLogin }) {
  const [username, setUsername] = useState('omar');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    const result = await onLogin(username, password);
    if (!result.ok) setError(result.error);
    setBusy(false);
  };

  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-20 h-20 rounded-full bg-white mb-5 shadow-md ring-1 ring-adib-soft/40 overflow-hidden">
            <img src="/logo.jpeg" alt="Gazelle" className="w-full h-full object-cover scale-[1.4]" draggable={false} />
          </div>
          <h1 className="font-serif text-[36px] leading-tight text-brand tracking-tight">Gazelle</h1>
          <div className="text-[11px] uppercase tracking-[0.18em] text-adib-deep mt-1">
            ADIB · Compliance Assistant
          </div>
        </div>

        <form
          onSubmit={submit}
          className="bg-cream-soft border border-cream-border rounded-2xl shadow-lg p-6 space-y-4"
        >
          <div>
            <label className="text-[11px] uppercase tracking-[0.16em] text-ink-faint font-semibold block mb-1.5">
              Username
            </label>
            <input
              autoFocus
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full px-3 py-2 bg-cream-frame border border-cream-border rounded-lg text-[14px] text-ink focus:outline-none focus:border-adib focus:ring-1 focus:ring-adib transition"
            />
          </div>
          <div>
            <label className="text-[11px] uppercase tracking-[0.16em] text-ink-faint font-semibold block mb-1.5">
              Password
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-3 py-2 bg-cream-frame border border-cream-border rounded-lg text-[14px] text-ink focus:outline-none focus:border-adib focus:ring-1 focus:ring-adib transition"
            />
          </div>
          {error && (
            <div className="text-[12px] text-red-700 bg-red-50 border border-red-100 rounded-md px-3 py-2">
              {error}
            </div>
          )}
          <button
            type="submit"
            disabled={busy || !username || !password}
            className="w-full bg-gradient-to-br from-adib to-adib-deep hover:from-adib-deep hover:to-brand disabled:from-cream-edge disabled:to-cream-edge disabled:cursor-not-allowed text-white font-medium py-2.5 rounded-lg shadow-sm transition"
          >
            {busy ? 'Signing in…' : 'Sign in'}
          </button>
        </form>

        <div className="mt-6 bg-cream-frame border border-cream-border rounded-xl p-4">
          <div className="text-[10px] uppercase tracking-[0.16em] text-ink-faint font-semibold mb-2">
            Mock users
          </div>
          <div className="space-y-1">
            {MOCK_USERS.map((u) => (
              <button
                key={u.username}
                type="button"
                onClick={() => {
                  setUsername(u.username);
                  setPassword(u.hint);
                }}
                className="w-full text-left px-2 py-1.5 rounded-md hover:bg-cream-deeper transition flex items-center justify-between gap-2"
              >
                <span className="text-[12px] text-ink truncate">{u.label}</span>
                <span className="text-[10px] text-ink-faint font-mono">{u.hint}</span>
              </button>
            ))}
          </div>
          <div className="text-[10px] text-ink-faint mt-3">
            Click a row to autofill credentials. Restricted users see all docs; public users only see public docs.
          </div>
        </div>
      </div>
    </div>
  );
}
