import { authHeaders } from '../hooks/useAuth';

// Upload documents and run the ingestion pipeline. Synchronous: the request
// resolves once the backend has finished OCR/extraction and updated the graph,
// so this can take a while for large documents.
export async function publishDocuments(files) {
  const form = new FormData();
  files.forEach((f) => form.append('files', f));

  let res;
  try {
    res = await fetch('/api/admin/documents/publish', {
      method: 'POST',
      headers: authHeaders(), // do NOT set Content-Type; the browser sets the multipart boundary
      body: form,
    });
  } catch {
    return { ok: false, error: 'Network error — is the backend running?' };
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
