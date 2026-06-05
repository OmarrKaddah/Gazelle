import { authHeaders } from '../hooks/useAuth';

// Upload documents and run ingestion. The request only resolves once the
// backend finishes OCR/extraction and updates the graph, so it can be slow.
export async function publishDocuments(files) {
  const form = new FormData();
  files.forEach((f) => form.append('files', f));

  let res;
  try {
    res = await fetch('/api/admin/documents/publish', {
      method: 'POST',
      headers: authHeaders(), // let the browser set the multipart Content-Type boundary
      body: form,
    });
  } catch {
    return { ok: false, error: 'Network error. Is the backend running?' };
  }

  const raw = await res.text();
  let data = {};
  try {
    data = raw ? JSON.parse(raw) : {};
  } catch {
    return { ok: false, error: 'Server error (invalid response)' };
  }

  if (!res.ok || !data.ok) {
    return { ok: false, error: data.detail || data.error || `Publish failed (${res.status})` };
  }
  return { ok: true, results: data.results || [] };
}
