import React, { useState, useRef } from 'react';
import { LogoMark, UploadIcon, FileIcon, ChatIcon, XIcon } from './Icons';
import { publishDocuments } from '../api/admin';

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function AdminPage({ user, onLogout, onEnterChat }) {
  const [files, setFiles] = useState([]);
  const [dragging, setDragging] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [done, setDone] = useState(null);
  const [failures, setFailures] = useState([]);
  const [error, setError] = useState(null);
  const inputRef = useRef(null);

  const resetStatus = () => {
    setDone(null);
    setFailures([]);
    setError(null);
  };

  const addFiles = (incoming) => {
    const next = Array.from(incoming);
    if (!next.length) return;
    resetStatus();
    setFiles((prev) => {
      const seen = new Set(prev.map((f) => f.name + f.size));
      return [...prev, ...next.filter((f) => !seen.has(f.name + f.size))];
    });
  };

  const removeFile = (idx) => setFiles((prev) => prev.filter((_, i) => i !== idx));

  const onDrop = (e) => {
    e.preventDefault();
    setDragging(false);
    addFiles(e.dataTransfer.files);
  };

  const publish = async () => {
    setPublishing(true);
    resetStatus();
    const res = await publishDocuments(files);
    setPublishing(false);
    if (!res.ok) {
      setError(res.error);
      return;
    }
    const published = res.results.filter((r) => r.status === 'published');
    const failed = res.results.filter((r) => r.status !== 'published');
    setDone(published.length);
    setFailures(failed);
    if (failed.length === 0) setFiles([]);
  };

  const initial = (user?.name || user?.username || '?').charAt(0).toUpperCase();

  return (
    <div className="flex flex-col h-full bg-cream overflow-hidden">
      {/* Top bar */}
      <header className="flex items-center justify-between px-6 py-3.5 bg-cream-frame border-b border-cream-border flex-shrink-0">
        <div className="flex items-center gap-2.5">
          <LogoMark className="w-9 h-9" />
          <div>
            <div className="font-serif text-[18px] leading-none text-brand tracking-tight">
              Gazelle
            </div>
            <div className="text-[10px] uppercase tracking-[0.16em] text-adib-deep mt-0.5">
              ADIB · Admin Console
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={onEnterChat}
            className="flex items-center gap-2 px-3.5 py-2 bg-gradient-to-br from-adib to-adib-deep hover:from-adib-deep hover:to-brand text-white text-[13px] font-medium rounded-lg shadow-sm transition"
          >
            <ChatIcon className="w-4 h-4" />
            <span>Chat with Gazelle</span>
          </button>

          <div className="flex items-center gap-2 pl-1">
            <div className="w-8 h-8 rounded-full bg-gradient-to-br from-brand to-adib-deep text-adib-glow flex items-center justify-center text-[13px] font-semibold ring-1 ring-adib/40">
              {initial}
            </div>
            <div className="hidden sm:block leading-tight">
              <div className="text-[13px] font-medium text-ink">{user?.name || user?.username}</div>
              <div className="text-[10px] text-ink-faint uppercase tracking-wider">{user?.role}</div>
            </div>
            <button
              onClick={onLogout}
              className="ml-1 px-2.5 py-1.5 text-[12px] text-ink-muted hover:text-brand hover:bg-cream-deeper rounded-md transition"
            >
              Sign out
            </button>
          </div>
        </div>
      </header>

      {/* Body */}
      <main className="flex-1 overflow-y-auto">
        <div className="max-w-2xl mx-auto px-6 py-10 animate-fadeIn">
          <h1 className="font-serif text-[28px] text-brand tracking-tight">Publish documents</h1>
          <p className="text-[13px] text-ink-muted mt-1.5">
            Upload regulatory and compliance documents to make them available to Gazelle.
            Supports PDF, Word, images, and any other file type.
          </p>

          {/* Upload zone */}
          <div
            onDragOver={(e) => {
              e.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={onDrop}
            onClick={() => inputRef.current?.click()}
            className={`mt-6 rounded-2xl border-2 border-dashed cursor-pointer transition flex flex-col items-center justify-center text-center px-6 py-12 ${
              dragging
                ? 'border-adib bg-cream-deeper'
                : 'border-cream-edge bg-cream-soft hover:border-adib-soft hover:bg-cream-frame'
            }`}
          >
            <div className="w-14 h-14 rounded-full bg-cream-deeper flex items-center justify-center ring-1 ring-adib-soft/40">
              <UploadIcon className="w-6 h-6 text-adib" />
            </div>
            <div className="mt-4 text-[15px] font-medium text-ink">
              Drag &amp; drop files here, or <span className="text-adib-deep">browse</span>
            </div>
            <div className="text-[12px] text-ink-faint mt-1">
              PDF · DOCX · images · any file type
            </div>
            <input
              ref={inputRef}
              type="file"
              multiple
              className="hidden"
              onChange={(e) => {
                addFiles(e.target.files);
                e.target.value = '';
              }}
            />
          </div>

          {/* Selected files */}
          {files.length > 0 && (
            <div className="mt-6">
              <div className="text-[11px] uppercase tracking-[0.16em] text-ink-faint font-semibold mb-2">
                {files.length} file{files.length > 1 ? 's' : ''} selected
              </div>
              <div className="space-y-1.5">
                {files.map((f, idx) => (
                  <div
                    key={f.name + f.size}
                    className="flex items-center gap-3 bg-cream-soft border border-cream-border rounded-lg px-3 py-2.5"
                  >
                    <div className="w-9 h-9 rounded-md bg-cream-deeper flex items-center justify-center flex-shrink-0">
                      <FileIcon className="w-4 h-4 text-adib-deep" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="text-[13px] text-ink truncate" dir="auto">{f.name}</div>
                      <div className="text-[11px] text-ink-faint">{formatSize(f.size)}</div>
                    </div>
                    <button
                      onClick={() => removeFile(idx)}
                      className="p-1.5 rounded-md text-ink-faint hover:text-brand hover:bg-cream-deeper transition flex-shrink-0"
                      title="Remove"
                    >
                      <XIcon className="w-4 h-4" />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Status messages */}
          {done != null && done > 0 && (
            <div className="mt-6 text-[13px] text-adib-deep bg-cream-deeper border border-adib-soft/50 rounded-lg px-4 py-3">
              {done} document{done > 1 ? 's' : ''} published and added to the graph.
            </div>
          )}
          {failures.length > 0 && (
            <div className="mt-3 text-[13px] text-red-700 bg-red-50 border border-red-100 rounded-lg px-4 py-3">
              <div className="font-medium mb-1">{failures.length} file{failures.length > 1 ? 's' : ''} could not be processed:</div>
              <ul className="list-disc pl-5 space-y-0.5">
                {failures.map((f) => (
                  <li key={f.file}><span className="font-medium">{f.file}</span> — {f.error || f.status}</li>
                ))}
              </ul>
            </div>
          )}
          {error && (
            <div className="mt-6 text-[13px] text-red-700 bg-red-50 border border-red-100 rounded-lg px-4 py-3">
              {error}
            </div>
          )}

          {/* Actions */}
          <div className="mt-7 flex items-center justify-end gap-3">
            {publishing && (
              <span className="text-[12px] text-ink-faint">
                Processing &amp; updating the graph — this can take a few minutes…
              </span>
            )}
            <button
              onClick={publish}
              disabled={publishing || files.length === 0}
              className="px-6 py-2.5 bg-gradient-to-br from-adib to-adib-deep hover:from-adib-deep hover:to-brand disabled:from-cream-edge disabled:to-cream-edge disabled:cursor-not-allowed text-white text-[14px] font-medium rounded-lg shadow-sm transition"
            >
              {publishing ? 'Publishing…' : 'Publish'}
            </button>
          </div>
        </div>
      </main>
    </div>
  );
}
