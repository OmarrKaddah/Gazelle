import React, { useState, useEffect, useRef } from 'react';
import {
  SendIcon,
  ChevronDownIcon,
  SlidersIcon,
  XIcon,
} from './Icons';
import { authHeaders } from '../hooks/useAuth';

const MODES = [
  { id: 'vector', label: 'Vector', desc: 'Pure semantic similarity' },
  { id: 'hybrid', label: 'Hybrid', desc: 'Vector + lexical fusion' },
  { id: 'graph', label: 'Graph', desc: 'Vector seeds + graph hops' },
];

const SUGGESTIONS = [
  { text: 'ما هي شروط إلغاء ترخيص البنك؟', tag: 'Licensing' },
  { text: 'متى يجب إخطار البنك المركزي بتغيير ملكية البنك؟', tag: 'Ownership' },
  { text: 'ما هي إجراءات وقف العمليات المصرفية جزئياً؟', tag: 'Operations' },
];

const SETTINGS_KEY = 'gazelle.settings.v1';
const DEFAULTS = { mode: 'vector', k: 5, hops: 1, provider: 'ollama' };

function loadSettings() {
  try {
    return { ...DEFAULTS, ...JSON.parse(localStorage.getItem(SETTINGS_KEY) || '{}') };
  } catch {
    return { ...DEFAULTS };
  }
}
function saveSettings(s) {
  localStorage.setItem(SETTINGS_KEY, JSON.stringify(s));
}

const CITATION_OPEN_EVENT = 'gazelle:open-citation';

function jumpToCitation(chunkId) {
  const el = document.getElementById(`citation-${cssEscape(chunkId)}`);
  if (!el) return;
  document.dispatchEvent(new CustomEvent(CITATION_OPEN_EVENT, { detail: { chunkId } }));
  setTimeout(() => {
    el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    el.classList.remove('citation-flash');
    void el.offsetWidth;
    el.classList.add('citation-flash');
  }, 60);
}

function cssEscape(s) {
  return String(s).replace(/[^a-zA-Z0-9_-]/g, (c) => `_${c.charCodeAt(0).toString(16)}_`);
}

export default function ChatView({ chatState }) {
  const { currentChat, updateChat, createChat } = chatState;
  const [query, setQuery] = useState('');
  const [streaming, setStreaming] = useState(false);
  const [settings, setSettings] = useState(loadSettings);
  const [providers, setProviders] = useState(null);
  const scrollRef = useRef(null);

  useEffect(() => saveSettings(settings), [settings]);

  useEffect(() => {
    fetch('/api/info', { headers: { ...authHeaders() } })
      .then((r) => r.json())
      .then((d) => setProviders(d.providers))
      .catch(() => setProviders(null));
  }, []);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [currentChat?.messages, streaming]);

  async function send() {
    const text = query.trim();
    if (!text || streaming) return;

    let chat = currentChat;
    if (!chat) chat = createChat();

    const userMsg = { role: 'user', text };
    const placeholder = {
      role: 'assistant',
      text: '',
      citations: [],
      mode: settings.mode,
      provider: settings.provider,
      streaming: true,
    };

    let messages = [...(chat.messages || []), userMsg, placeholder];
    let title = chat.title;
    if (!chat.messages || chat.messages.length === 0) {
      title = text.slice(0, 60);
    }
    updateChat(chat.id, { messages, title });

    setQuery('');
    setStreaming(true);

    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify({
          query: text,
          mode: settings.mode,
          k: settings.k,
          hops: settings.hops,
          provider: settings.provider,
        }),
      });
      if (!response.body) throw new Error('No response stream');
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split('\n\n');
        buffer = parts.pop() || '';
        for (const part of parts) {
          const line = part.trim();
          if (!line.startsWith('data: ')) continue;
          const evt = JSON.parse(line.slice(6));
          if (evt.type === 'citations') {
            messages = patchLast(messages, { citations: evt.citations });
          } else if (evt.type === 'token') {
            messages = patchLast(messages, { text: messages[messages.length - 1].text + evt.text });
          }
          updateChat(chat.id, { messages });
        }
      }
    } catch (err) {
      messages = patchLast(messages, { text: `Error: ${err.message}` });
    }
    messages = patchLast(messages, { streaming: false });
    updateChat(chat.id, { messages });
    setStreaming(false);
  }

  const showWelcome = !currentChat || !currentChat.messages || currentChat.messages.length === 0;

  return (
    <div className="flex flex-col h-full">
      <TopBar
        title={currentChat?.title || 'New conversation'}
        provider={settings.provider}
        providers={providers}
      />
      <div ref={scrollRef} className="flex-1 overflow-y-auto">
        <div className="max-w-3xl mx-auto px-8 pt-6 pb-10">
          {showWelcome ? (
            <Welcome onSuggestion={(t) => setQuery(t)} />
          ) : (
            <div className="space-y-7 animate-fadeIn">
              {currentChat.messages.map((m, i) => (
                <Message key={i} message={m} />
              ))}
            </div>
          )}
        </div>
      </div>
      <Composer
        query={query}
        setQuery={setQuery}
        send={send}
        streaming={streaming}
        settings={settings}
        setSettings={setSettings}
        providers={providers}
      />
    </div>
  );
}

function patchLast(messages, patch) {
  if (!messages.length) return messages;
  const last = messages[messages.length - 1];
  return [...messages.slice(0, -1), { ...last, ...patch }];
}

function TopBar({ title, provider, providers }) {
  const model = providers?.[provider]?.model;
  return (
    <header className="border-b border-cream-border px-8 py-3 flex items-center justify-between bg-cream/80 backdrop-blur-sm flex-shrink-0">
      <div className="flex items-center gap-2 min-w-0">
        <span className="text-[13px] text-ink-muted truncate" dir="auto">
          {title}
        </span>
      </div>
      <div className="flex items-center gap-2 flex-shrink-0">
        <span className="inline-flex items-center gap-1.5 text-[10px] uppercase tracking-[0.14em] text-ink-faint">
          <span className="w-1.5 h-1.5 rounded-full bg-adib animate-pulse" />
          <span>Gazelle</span>
          <span className="text-cream-edge">·</span>
          <span className="font-mono normal-case tracking-normal text-ink-muted">
            {provider}
          </span>
          {model && (
            <>
              <span className="text-cream-edge">/</span>
              <span className="font-mono normal-case tracking-normal text-ink-muted">{model}</span>
            </>
          )}
        </span>
      </div>
    </header>
  );
}

function Welcome({ onSuggestion }) {
  return (
    <div className="pt-16 pb-8 animate-fadeIn">
      <div className="text-center mb-10">
        <div className="inline-flex items-center justify-center w-20 h-20 rounded-full bg-white mb-7 shadow-md ring-1 ring-adib-soft/40 overflow-hidden">
          <img src="/logo.jpeg" alt="Gazelle" className="w-full h-full object-cover scale-[1.4]" draggable={false} />
        </div>
        <h1 className="font-serif text-[44px] leading-[1.05] text-brand tracking-tight mb-2">
          Welcome back, <span className="italic text-adib-deep">Omar</span>.
        </h1>
        <p className="text-[15px] text-ink-muted max-w-lg mx-auto leading-relaxed">
          Gazelle is ready. Ask about ADIB. Answers are grounded in cited regulatory documents.
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 max-w-2xl mx-auto">
        {SUGGESTIONS.map((s, i) => (
          <button
            key={i}
            onClick={() => onSuggestion(s.text)}
            className="text-left p-4 rounded-xl bg-cream-soft hover:bg-cream-deeper border border-cream-border hover:border-adib-soft transition group"
            style={{ animationDelay: `${100 + i * 80}ms`, animation: 'fadeIn 0.5s ease-out backwards' }}
          >
            <div className="text-[10px] uppercase tracking-[0.16em] text-adib-deep font-semibold mb-2">
              {s.tag}
            </div>
            <div className="text-[13px] text-ink leading-relaxed group-hover:text-brand transition" dir="auto">
              {s.text}
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}

function Message({ message }) {
  if (message.role === 'user') {
    return (
      <div className="flex justify-end">
        <div
          className="bg-cream-deeper text-brand rounded-2xl px-4 py-2.5 max-w-[78%] leading-relaxed text-[15px] border border-adib-soft/40"
          dir="auto"
        >
          {message.text}
        </div>
      </div>
    );
  }
  const citationMap = new Map((message.citations || []).map((c, i) => [c.chunkId, i + 1]));
  return (
    <div className="space-y-4">
      <div className="text-ink leading-[1.7] text-[15.5px] prose-message" dir="auto">
        <RenderedText text={message.text} citationMap={citationMap} />
        {message.streaming && <span className="caret" />}
      </div>
      {message.citations && message.citations.length > 0 && (
        <Citations citations={message.citations} mode={message.mode} />
      )}
    </div>
  );
}

const CITATION_PATTERN = /\[([\w؀-ۿ.\-:]+)\]/g;

function RenderedText({ text, citationMap }) {
  const segments = [];
  let lastIndex = 0;
  let match;
  CITATION_PATTERN.lastIndex = 0;
  while ((match = CITATION_PATTERN.exec(text)) !== null) {
    const id = match[1];
    const num = citationMap.get(id);
    if (num !== undefined) {
      if (match.index > lastIndex) segments.push({ kind: 'text', value: text.slice(lastIndex, match.index) });
      segments.push({ kind: 'cite', id, num });
      lastIndex = match.index + match[0].length;
    }
  }
  if (lastIndex < text.length) segments.push({ kind: 'text', value: text.slice(lastIndex) });

  return (
    <>
      {segments.length === 0 ? (
        <span className="whitespace-pre-wrap">{text}</span>
      ) : (
        segments.map((s, i) =>
          s.kind === 'text' ? (
            <span key={i} className="whitespace-pre-wrap">
              {s.value}
            </span>
          ) : (
            <CitationRef key={i} number={s.num} chunkId={s.id} />
          )
        )
      )}
    </>
  );
}

function CitationRef({ number, chunkId }) {
  return (
    <button
      onClick={() => jumpToCitation(chunkId)}
      title={chunkId}
      className="inline-flex items-center justify-center min-w-[20px] h-[18px] px-1 mx-[1px] align-super text-[10.5px] font-mono font-semibold leading-none rounded-md bg-adib/10 text-adib-deep hover:bg-adib hover:text-white border border-adib/30 hover:border-adib transition"
    >
      {number}
    </button>
  );
}

function Citations({ citations, mode }) {
  return (
    <div className="pt-3 mt-3 border-t border-cream-border">
      <div className="flex items-center gap-2 mb-2">
        <span className="text-[10px] uppercase tracking-[0.18em] text-ink-faint font-semibold">
          Citations
        </span>
        <span className="text-[10px] text-adib-deep font-medium">{citations.length}</span>
        <span className="text-cream-edge">·</span>
        <span className="text-[10px] text-ink-faint">{mode}</span>
      </div>
      <div className="space-y-1.5">
        {citations.map((c, i) => (
          <Citation key={`${c.chunkId}-${i}`} citation={c} index={i} />
        ))}
      </div>
    </div>
  );
}

function Citation({ citation, index }) {
  const [open, setOpen] = useState(false);
  useEffect(() => {
    const handler = (e) => {
      if (e.detail?.chunkId === citation.chunkId) setOpen(true);
    };
    document.addEventListener(CITATION_OPEN_EVENT, handler);
    return () => document.removeEventListener(CITATION_OPEN_EVENT, handler);
  }, [citation.chunkId]);

  const sourceColor =
    {
      vector: 'bg-brand text-adib-glow',
      hybrid: 'bg-adib text-white',
      seed: 'bg-brand text-adib-glow',
      neighbor: 'bg-gold text-brand',
    }[citation.source] || 'bg-cream-deeper text-ink-muted';

  return (
    <div
      id={`citation-${cssEscape(citation.chunkId)}`}
      className="bg-cream-soft border border-cream-border rounded-lg overflow-hidden hover:border-adib-soft transition-colors"
    >
      <button
        onClick={() => setOpen(!open)}
        className="w-full px-3 py-2 flex items-center justify-between text-left gap-2"
      >
        <div className="flex items-center gap-2 min-w-0 flex-1">
          <span className="text-[11px] text-ink-faint font-mono flex-shrink-0">[{index + 1}]</span>
          <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium uppercase tracking-wide flex-shrink-0 ${sourceColor}`}>
            {citation.source}
          </span>
          <span className="text-[12px] text-ink font-mono truncate flex-shrink-0">
            {citation.chunkId}
          </span>
          <span className="text-[12px] text-ink-faint truncate" dir="auto">
            {citation.sectionPath?.join(' › ')}
          </span>
        </div>
        <ChevronDownIcon
          className={`w-4 h-4 text-ink-faint transition flex-shrink-0 ${open ? 'rotate-180' : ''}`}
        />
      </button>
      {open && (
        <div className="px-3 pb-3 pt-2 border-t border-cream-border animate-fadeIn">
          <div className="text-[11px] text-ink-faint mb-2 flex gap-3">
            <span>pages: {citation.pages?.join(', ') || '—'}</span>
            <span>
              score: {typeof citation.score === 'number' ? citation.score.toFixed(4) : '—'}
            </span>
          </div>
          <div
            className="text-[13px] text-ink whitespace-pre-wrap leading-relaxed max-h-72 overflow-y-auto pr-2"
            dir="auto"
          >
            {citation.text}
          </div>
        </div>
      )}
    </div>
  );
}

function Composer({ query, setQuery, send, streaming, settings, setSettings, providers }) {
  const [settingsOpen, setSettingsOpen] = useState(false);
  return (
    <div className="border-t border-cream-border bg-cream/80 backdrop-blur-sm flex-shrink-0">
      <div className="max-w-3xl mx-auto px-8 py-4">
        {/* Settings row */}
        <div className="flex items-center justify-between mb-2 px-1 relative">
          <ModePills
            mode={settings.mode}
            setMode={(mode) => setSettings({ ...settings, mode })}
          />
          <button
            onClick={() => setSettingsOpen(!settingsOpen)}
            className="flex items-center gap-1.5 text-[11px] text-ink-muted hover:text-ink transition px-2 py-1 rounded-md hover:bg-cream-deeper"
          >
            <SlidersIcon className="w-3.5 h-3.5" />
            <span className="font-mono">{settings.provider}</span>
            <span className="text-cream-edge">·</span>
            <span className="font-mono">k={settings.k}</span>
            {settings.mode === 'graph' && <span className="font-mono">·{settings.hops}-hop</span>}
          </button>
          {settingsOpen && (
            <SettingsPopover
              settings={settings}
              setSettings={setSettings}
              providers={providers}
              onClose={() => setSettingsOpen(false)}
            />
          )}
        </div>

        {/* Composer card */}
        <div className="flex items-end gap-2 bg-cream-soft border border-cream-border rounded-2xl pl-4 pr-2 py-2 shadow-sm focus-within:border-adib focus-within:shadow-md transition">
          <textarea
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                send();
              }
            }}
            placeholder="Ask Gazelle about ADIB compliance…"
            rows={1}
            dir="auto"
            disabled={streaming}
            className="flex-1 resize-none bg-transparent py-2 text-[15px] text-ink placeholder-ink-faint focus:outline-none disabled:opacity-60 leading-relaxed"
            style={{ minHeight: '40px', maxHeight: '180px' }}
          />
          <button
            onClick={send}
            disabled={streaming || !query.trim()}
            className="flex items-center justify-center w-9 h-9 rounded-xl bg-gradient-to-br from-adib to-adib-deep hover:from-adib-deep hover:to-brand disabled:from-cream-edge disabled:to-cream-edge disabled:cursor-not-allowed text-white shadow-sm transition flex-shrink-0"
            aria-label="Send"
          >
            <SendIcon className="w-4 h-4" />
          </button>
        </div>
        <div className="text-center text-[10.5px] text-ink-faint mt-2.5 tracking-wide">
          Gazelle answers from cited regulatory context. Verify with source documents.
        </div>
      </div>
    </div>
  );
}

function ModePills({ mode, setMode }) {
  return (
    <div className="flex gap-1 bg-cream-frame border border-cream-border rounded-full p-0.5">
      {MODES.map((m) => (
        <button
          key={m.id}
          onClick={() => setMode(m.id)}
          title={m.desc}
          className={`px-3 py-1 text-[11px] font-medium rounded-full transition ${
            mode === m.id
              ? 'bg-adib text-white shadow-sm'
              : 'text-ink-muted hover:text-ink'
          }`}
        >
          {m.label}
        </button>
      ))}
    </div>
  );
}

function SettingsPopover({ settings, setSettings, providers, onClose }) {
  const providerList = [
    { id: 'ollama', label: 'Local · Ollama' },
    { id: 'groq', label: 'Cloud · Groq' },
  ];
  return (
    <>
      <div className="fixed inset-0 z-10" onClick={onClose} />
      <div className="absolute bottom-full right-0 mb-2 z-20 bg-cream-soft border border-cream-border rounded-xl shadow-xl w-72 p-3 animate-fadeIn">
        <div className="flex items-center justify-between mb-3">
          <span className="text-[11px] uppercase tracking-[0.16em] text-ink-faint font-semibold">
            Retrieval & Model
          </span>
          <button onClick={onClose} className="text-ink-faint hover:text-ink">
            <XIcon className="w-3.5 h-3.5" />
          </button>
        </div>

        <SettingRow label="Provider" value={providers?.[settings.provider]?.model || '—'}>
          <div className="flex gap-1">
            {providerList.map((p) => {
              const info = providers?.[p.id];
              const available = info?.available;
              const active = settings.provider === p.id;
              return (
                <button
                  key={p.id}
                  disabled={!available}
                  onClick={() => setSettings({ ...settings, provider: p.id })}
                  title={!available ? 'API key not configured' : info?.model}
                  className={`flex-1 py-1.5 text-[10.5px] font-medium rounded transition ${
                    active
                      ? 'bg-adib text-white shadow-sm'
                      : available
                      ? 'bg-cream-frame text-ink-muted hover:bg-cream-deeper'
                      : 'bg-cream-frame text-ink-faint opacity-50 cursor-not-allowed'
                  }`}
                >
                  {p.label}
                </button>
              );
            })}
          </div>
        </SettingRow>

        <SettingRow label="Top K" value={settings.k}>
          <input
            type="range"
            min="1"
            max="15"
            value={settings.k}
            onChange={(e) => setSettings({ ...settings, k: Number(e.target.value) })}
            className="w-full accent-gold"
          />
        </SettingRow>

        {settings.mode === 'graph' && (
          <SettingRow label="Hops" value={settings.hops}>
            <div className="flex gap-1">
              {[1, 2].map((h) => (
                <button
                  key={h}
                  onClick={() => setSettings({ ...settings, hops: h })}
                  className={`flex-1 py-1 text-[11px] font-medium rounded ${
                    settings.hops === h
                      ? 'bg-adib text-white shadow-sm'
                      : 'bg-cream-frame text-ink-muted hover:bg-cream-deeper'
                  }`}
                >
                  {h}-hop
                </button>
              ))}
            </div>
          </SettingRow>
        )}

        <div className="text-[10.5px] text-ink-faint pt-2 mt-2 border-t border-cream-border">
          Settings persist locally. Disabled providers need an API key in <code className="font-mono text-[10px]">.env</code>.
        </div>
      </div>
    </>
  );
}

function SettingRow({ label, value, children }) {
  return (
    <div className="mb-3 last:mb-0">
      <div className="flex items-center justify-between mb-1.5">
        <span className="text-[12px] text-ink font-medium">{label}</span>
        <span className="text-[10.5px] text-adib-deep font-mono truncate max-w-[180px]" title={value}>
          {value}
        </span>
      </div>
      {children}
    </div>
  );
}
