import { authHeaders } from '../hooks/useAuth';

export async function publishDocuments(files, { onLog, onDone } = {}) {
  const form = new FormData();
  files.forEach((f) => form.append('files', f));

  let res;
  try {
    res = await fetch('/api/admin/documents/publish', {
      method: 'POST',
      headers: authHeaders(),
      body: form,
    });
  } catch {
    return { ok: false, error: 'Network error. Is the backend running?' };
  }

  if (!res.ok) {
    const text = await res.text().catch(() => '');
    let detail = `Publish failed (${res.status})`;
    try { detail = JSON.parse(text).detail || detail; } catch { /* ignore */ }
    return { ok: false, error: detail };
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = '';
  let finalResult = null;

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    const lines = buf.split('\n');
    buf = lines.pop();
    for (const line of lines) {
      if (!line.startsWith('data: ')) continue;
      let evt;
      try { evt = JSON.parse(line.slice(6)); } catch { continue; }
      if (evt.type === 'log' && onLog) onLog(evt.text);
      if (evt.type === 'done') {
        finalResult = evt;
        if (onDone) onDone(evt);
      }
    }
  }

  if (!finalResult) return { ok: false, error: 'No response from server' };
  if (!finalResult.ok) return { ok: false, error: finalResult.error || 'Publish failed' };
  return { ok: true, results: finalResult.results || [] };
}
