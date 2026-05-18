import type { UploadResponse, ExportFormat, PageResult } from './types';

const BASE = '/api';

function token(): string | null {
  return localStorage.getItem('token');
}

function authHeaders(): HeadersInit {
  const t = token();
  return t ? { Authorization: `Bearer ${t}` } : {};
}

async function checkResponse(res: Response) {
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body?.detail ?? `HTTP ${res.status}`);
  }
  return res;
}

// ── Auth ──────────────────────────────────────────────────────────────────────

export async function fetchLoginUrl(): Promise<string> {
  const res = await checkResponse(await fetch(`${BASE}/auth/login`));
  const data = await res.json();
  return data.url as string;
}

export async function fetchMe(): Promise<{ email: string; name: string; picture?: string }> {
  const res = await checkResponse(
    await fetch(`${BASE}/auth/me`, { headers: authHeaders() })
  );
  return res.json();
}

// ── Upload ────────────────────────────────────────────────────────────────────

export async function uploadPdf(file: File): Promise<UploadResponse> {
  const form = new FormData();
  form.append('file', file);
  const res = await checkResponse(
    await fetch(`${BASE}/upload`, {
      method: 'POST',
      headers: authHeaders(),
      body: form,
    })
  );
  return res.json();
}

export async function deleteUpload(uploadId: string): Promise<void> {
  await fetch(`${BASE}/upload/${uploadId}`, {
    method: 'DELETE',
    headers: authHeaders(),
  });
}

// ── Extract (SSE) ─────────────────────────────────────────────────────────────

export function extractPages(
  uploadId: string,
  pageNums: number[],
  onEvent: (e: import('./types').SSEEvent) => void,
  onError: (msg: string) => void
): () => void {
  const t = token();
  const controller = new AbortController();

  (async () => {
    try {
      const res = await checkResponse(
        await fetch(`${BASE}/extract`, {
          method: 'POST',
          signal: controller.signal,
          headers: {
            'Content-Type': 'application/json',
            ...(t ? { Authorization: `Bearer ${t}` } : {}),
          },
          body: JSON.stringify({ upload_id: uploadId, page_nums: pageNums }),
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
              const evt = JSON.parse(line.slice(6));
              onEvent(evt);
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
    await fetch(`${BASE}/export/${format}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...authHeaders(),
      },
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
