import type {
  UploadResponse, ExportFormat, PageResult,
  DocumentListResponse, DocumentDetail, DocumentStatus,
} from './types';

const BASE = '/api';

// ── Fetch wrapper with automatic token refresh ────────────────────────────────

let _refreshing: Promise<boolean> | null = null;

async function _tryRefresh(): Promise<boolean> {
  if (_refreshing) return _refreshing;
  _refreshing = fetch(`${BASE}/auth/refresh`, { method: 'POST', credentials: 'include' })
    .then((r) => r.ok)
    .catch(() => false)
    .finally(() => { _refreshing = null; });
  return _refreshing;
}

async function apiFetch(url: string, init?: RequestInit): Promise<Response> {
  const res = await fetch(url, { ...init, credentials: 'include' });

  // On 401: try a silent token refresh, then retry once.
  // Skip the retry loop for auth endpoints themselves.
  if (res.status === 401 && !url.includes('/auth/')) {
    const refreshed = await _tryRefresh();
    if (refreshed) {
      return fetch(url, { ...init, credentials: 'include' });
    }
    // Refresh failed — boot to login
    window.location.href = '/';
  }

  return res;
}

async function checkResponse(res: Response): Promise<Response> {
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body?.detail ?? `HTTP ${res.status}`);
  }
  return res;
}

// ── Auth ──────────────────────────────────────────────────────────────────────

export async function fetchLoginUrl(): Promise<string> {
  const res = await checkResponse(await apiFetch(`${BASE}/auth/login`));
  const data = await res.json();
  return data.url as string;
}

export async function fetchMe(): Promise<{ email: string; name: string; picture?: string }> {
  const res = await checkResponse(await apiFetch(`${BASE}/auth/me`));
  return res.json();
}

export async function logoutUser(): Promise<void> {
  await apiFetch(`${BASE}/auth/logout`, { method: 'POST' }).catch(() => {});
}

// ── Upload ────────────────────────────────────────────────────────────────────

export async function uploadPdf(file: File): Promise<UploadResponse> {
  const form = new FormData();
  form.append('file', file);
  const res = await checkResponse(
    await apiFetch(`${BASE}/upload`, { method: 'POST', body: form })
  );
  return res.json();
}

export async function combineImages(files: File[]): Promise<UploadResponse> {
  const form = new FormData();
  for (const f of files) form.append('files', f);
  const res = await checkResponse(
    await apiFetch(`${BASE}/upload/combine`, { method: 'POST', body: form })
  );
  return res.json();
}

export async function deleteUpload(uploadId: string): Promise<void> {
  await apiFetch(`${BASE}/upload/${uploadId}`, { method: 'DELETE' });
}

// ── Extract (SSE) ─────────────────────────────────────────────────────────────

export function extractPages(
  uploadId: string,
  pageNums: number[],
  onEvent: (e: import('./types').SSEEvent) => void,
  onError: (msg: string) => void,
  documentId?: string
): () => void {
  const controller = new AbortController();

  (async () => {
    try {
      const res = await checkResponse(
        await apiFetch(`${BASE}/extract`, {
          method: 'POST',
          signal: controller.signal,
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            upload_id: uploadId,
            page_nums: pageNums,
            ...(documentId ? { document_id: documentId } : {}),
          }),
        })
      );

      const reader = res.body!.getReader();
      const decoder = new TextDecoder();
      let buf = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const lines = buf.split('\n');
        buf = lines.pop()!;
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              onEvent(JSON.parse(line.slice(6)));
            } catch {
              // skip malformed lines
            }
          }
        }
      }
    } catch (err: unknown) {
      if ((err as Error).name !== 'AbortError') {
        onError((err as Error).message);
      }
    }
  })();

  return () => controller.abort();
}

// ── Documents ─────────────────────────────────────────────────────────────────

export async function listDocuments(page = 1, perPage = 20): Promise<DocumentListResponse> {
  const res = await checkResponse(
    await apiFetch(`${BASE}/documents?page=${page}&per_page=${perPage}`)
  );
  return res.json();
}

export async function getDocument(documentId: string): Promise<DocumentDetail> {
  const res = await checkResponse(await apiFetch(`${BASE}/documents/${documentId}`));
  return res.json();
}

export async function getDocumentStatus(documentId: string): Promise<DocumentStatus> {
  const res = await checkResponse(await apiFetch(`${BASE}/documents/${documentId}/status`));
  return res.json();
}

export async function deleteDocument(documentId: string): Promise<void> {
  await checkResponse(await apiFetch(`${BASE}/documents/${documentId}`, { method: 'DELETE' }));
}

export async function renameDocument(documentId: string, filename: string): Promise<void> {
  await checkResponse(
    await apiFetch(`${BASE}/documents/${documentId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ filename }),
    })
  );
}

export async function savePageResult(
  documentId: string,
  pageNum: number,
  data: Pick<PageResult, 'title' | 'sections' | 'validation'>
): Promise<void> {
  await checkResponse(
    await apiFetch(`${BASE}/documents/${documentId}/pages/${pageNum}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    })
  );
}

// ── Export ────────────────────────────────────────────────────────────────────

const MIME: Record<ExportFormat, string> = {
  pdf:   'application/pdf',
  word:  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  excel: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  json:  'application/json',
};

const EXT: Record<ExportFormat, string> = {
  pdf: 'pdf', word: 'docx', excel: 'xlsx', json: 'json',
};

export async function exportDocument(
  format: ExportFormat,
  reviewData: Record<string, PageResult>
): Promise<void> {
  const res = await checkResponse(
    await apiFetch(`${BASE}/export/${format}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ review_data: reviewData }),
    })
  );

  const blob = new Blob([await res.arrayBuffer()], { type: MIME[format] });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `extracted.${EXT[format]}`;
  a.click();
  URL.revokeObjectURL(url);
}
