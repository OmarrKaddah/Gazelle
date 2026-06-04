import React, { useState, useEffect, useRef, useCallback } from 'react';
import { authHeaders } from '../hooks/useAuth';

const SHARED = [
  { id: 'ocr', label: 'OCR', out: 'ocr' },
  { id: 'parser', label: 'Parse', out: 'parser' },
  { id: 'chunker', label: 'Chunk', out: 'chunker' },
  { id: 'embed', label: 'Embed' },
];
const ROUTE_STAGES = {
  '1': [
    { id: 'gliner', label: 'GLiNER entities', out: 'gliner' },
    { id: 'kgBuild', label: 'Build co-mention graph' },
  ],
  '2': [
    { id: 'graphExtract', label: 'Graph extract', out: 'graphExtract' },
    { id: 'graphBuild', label: 'Build RELATED graph' },
  ],
};
const ENRICH = [{ id: 'entityEmbed', label: 'Embed entities' }];

const STATUS_STRIP = [
  { key: 'ocr', label: 'Doc_Out' },
  { key: 'parser', label: 'parsed' },
  { key: 'chunker', label: 'chunks' },
  { key: 'gliner', label: 'entities' },
  { key: 'graphExtract', label: 'graph' },
];

export default function PipelineView() {
  const [config, setConfig] = useState({ route: '2', ner: 'gliner', chunker: 'semantic', backend: 'openrouter', workers: 12 });
  const [counts, setCounts] = useState({});
  const [log, setLog] = useState([]);
  const [running, setRunning] = useState(null);
  const logRef = useRef(null);
  const abortRef = useRef(null);

  const refreshStatus = useCallback(() => {
    fetch('/api/pipeline/status', { headers: { ...authHeaders() } })
      .then((r) => r.json())
      .then((d) => { setCounts(d.counts || {}); setConfig((c) => ({ ...c, ...d.config })); })
      .catch(() => {});
  }, []);

  useEffect(() => { refreshStatus(); }, [refreshStatus]);
  useEffect(() => { if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight; }, [log]);

  const runStage = async (stage) => {
    if (running) return;
    const controller = new AbortController();
    abortRef.current = controller;
    setRunning(stage);
    setLog((l) => [...l, { kind: 'head', text: `▶ ${stage}` }]);
    try {
      const res = await fetch('/api/pipeline/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify({ stage, ...config, workers: Number(config.workers) }),
        signal: controller.signal,
      });
      if (!res.body) throw new Error('No response stream');
      const reader = res.body.getReader();
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
          if (evt.line !== undefined) {
            setLog((l) => [...l, { kind: 'line', text: evt.line }]);
          } else if (evt.done) {
            setLog((l) => [...l, { kind: evt.code === 0 ? 'ok' : 'err', text: evt.code === 0 ? '✓ done' : `✗ exited with code ${evt.code}` }]);
          }
        }
      }
    } catch (e) {
      setLog((l) => [...l, { kind: 'err', text: e.name === 'AbortError' ? '✗ stopped' : `Error: ${e.message}` }]);
    } finally {
      abortRef.current = null;
      setRunning(null);
      refreshStatus();
    }
  };

  const stopStage = () => abortRef.current?.abort();

  const setCfg = (k, v) => setConfig((c) => ({ ...c, [k]: v }));
  const routeStages = ROUTE_STAGES[config.route] || ROUTE_STAGES['2'];

  return (
    <div className="flex flex-col h-full">
      <div className="px-6 py-4 border-b border-cream-border flex items-center justify-between">
        <div>
          <h1 className="font-serif text-[18px] text-brand leading-none">Pipeline</h1>
          <div className="text-[11px] text-ink-faint mt-1">Build the knowledge graph end-to-end</div>
        </div>
        <div className="flex items-center gap-1.5">
          {STATUS_STRIP.map((s) => (
            <div key={s.key} className="px-2.5 py-1 rounded-md bg-cream-soft border border-cream-border text-[11px] text-ink-muted">
              {s.label} <span className="font-mono text-ink font-semibold">{counts[s.key] ?? 0}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="flex-1 flex min-h-0">
        {/* Left: config + stages */}
        <div className="w-[380px] border-r border-cream-border overflow-y-auto p-5 space-y-5 flex-shrink-0">
          <Section title="Configuration">
            <Field label="Graph route">
              <Segmented value={config.route} onChange={(v) => setCfg('route', v)} options={[
                { value: '1', label: '1 · Classical' },
                { value: '2', label: '2 · LLM' },
              ]} />
            </Field>
            <Field label="NER strategy">
              <Segmented value={config.ner} onChange={(v) => setCfg('ner', v)} options={[
                { value: 'gliner', label: 'GLiNER' },
                { value: 'llm', label: 'LLM' },
              ]} />
            </Field>
            <Field label="Chunker">
              <Segmented value={config.chunker} onChange={(v) => setCfg('chunker', v)} options={[
                { value: 'semantic', label: 'Semantic' },
                { value: 'default', label: 'Default' },
              ]} />
            </Field>
            <Field label="Extract backend">
              <select value={config.backend} onChange={(e) => setCfg('backend', e.target.value)}
                className="w-full px-2.5 py-1.5 text-[12px] bg-cream-soft border border-cream-border rounded-md text-ink focus:outline-none focus:border-adib">
                {['openrouter', 'ollama', 'groq', 'gemini'].map((b) => <option key={b} value={b}>{b}</option>)}
              </select>
            </Field>
            <Field label="Extract workers">
              <input type="number" min="1" max="64" value={config.workers} onChange={(e) => setCfg('workers', e.target.value)}
                className="w-full px-2.5 py-1.5 text-[12px] bg-cream-soft border border-cream-border rounded-md text-ink font-mono focus:outline-none focus:border-adib" />
            </Field>
          </Section>

          <Section title="Shared prep">
            <div className="grid grid-cols-2 gap-2">
              {SHARED.map((s) => <StageBtn key={s.id} stage={s} running={running} counts={counts} onRun={runStage} />)}
            </div>
          </Section>

          <Section title={`Graph build · Route ${config.route}`}>
            <div className="grid grid-cols-1 gap-2">
              {routeStages.map((s) => <StageBtn key={s.id} stage={s} running={running} counts={counts} onRun={runStage} />)}
            </div>
          </Section>

          <Section title="Enrichment">
            <div className="grid grid-cols-1 gap-2">
              {ENRICH.map((s) => <StageBtn key={s.id} stage={s} running={running} counts={counts} onRun={runStage} />)}
            </div>
          </Section>

          <button
            onClick={() => runStage('all')}
            disabled={!!running}
            className={`w-full py-2.5 rounded-lg text-[13px] font-medium transition ${running ? 'bg-cream-deeper text-ink-faint cursor-not-allowed' : 'bg-brand text-white hover:opacity-90 shadow-sm'}`}
          >
            {running === 'all' ? 'Running end-to-end…' : '▶ Run end-to-end'}
          </button>
        </div>

        {/* Right: live log */}
        <div className="flex-1 flex flex-col min-w-0 bg-ink/95">
          <div className="px-4 py-2 border-b border-black/30 flex items-center justify-between">
            <span className="text-[11px] uppercase tracking-[0.16em] text-white/50 font-semibold">Output</span>
            <div className="flex items-center gap-3">
              {running && <span className="text-[11px] text-adib-glow flex items-center gap-1.5"><span className="w-1.5 h-1.5 rounded-full bg-adib-glow animate-pulse" /> {running}</span>}
              {running && <button onClick={stopStage} className="text-[11px] text-red-400 hover:text-red-300 transition">Stop</button>}
              <button onClick={() => setLog([])} className="text-[11px] text-white/40 hover:text-white/80 transition">Clear</button>
            </div>
          </div>
          <div ref={logRef} className="flex-1 overflow-y-auto p-4 font-mono text-[12px] leading-relaxed">
            {log.length === 0 && <div className="text-white/30">Run a stage to see output…</div>}
            {log.map((l, i) => (
              <div key={i} className={
                l.kind === 'head' ? 'text-adib-glow mt-2' :
                l.kind === 'ok' ? 'text-green-400' :
                l.kind === 'err' ? 'text-red-400' :
                'text-white/80'
              } dir="auto">{l.text}</div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function Section({ title, children }) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-[0.18em] text-ink-faint font-semibold mb-2">{title}</div>
      <div className="space-y-2.5">{children}</div>
    </div>
  );
}

function Field({ label, children }) {
  return (
    <div>
      <div className="text-[11px] text-ink-muted mb-1">{label}</div>
      {children}
    </div>
  );
}

function Segmented({ value, onChange, options }) {
  return (
    <div className="flex gap-1 p-0.5 bg-cream-deeper rounded-md">
      {options.map((o) => (
        <button key={o.value} onClick={() => onChange(o.value)}
          className={`flex-1 px-2 py-1 text-[12px] rounded transition ${value === o.value ? 'bg-brand text-white font-medium shadow-sm' : 'text-ink-muted hover:text-ink'}`}>
          {o.label}
        </button>
      ))}
    </div>
  );
}

function StageBtn({ stage, running, counts, onRun }) {
  const isThis = running === stage.id;
  const disabled = !!running;
  const count = stage.out ? counts[stage.out] : undefined;
  return (
    <button onClick={() => onRun(stage.id)} disabled={disabled}
      className={`flex items-center justify-between px-3 py-2 rounded-md text-[12px] border transition ${
        isThis ? 'bg-adib-soft/30 border-adib text-ink' :
        disabled ? 'bg-cream-soft border-cream-border text-ink-faint cursor-not-allowed' :
        'bg-cream-soft border-cream-border text-ink hover:border-adib hover:bg-cream-deeper'
      }`}>
      <span className="flex items-center gap-1.5">
        {isThis && <span className="w-1.5 h-1.5 rounded-full bg-adib animate-pulse" />}
        {stage.label}
      </span>
      {count !== undefined && <span className="font-mono text-[11px] text-ink-faint">{count}</span>}
    </button>
  );
}
