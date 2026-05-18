import { useState, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { uploadPdf, deleteUpload, extractPages } from '../api/client';
import type { UploadResponse, PageResult, SSEEvent } from '../api/types';
import { useAuth } from '../hooks/useAuth';
import PagePicker from '../components/PagePicker';
import ProgressFeed, { eventToStatus } from '../components/ProgressFeed';
import SectionEditor from '../components/SectionEditor';
import ExportBar from '../components/ExportBar';

type Step = 'upload' | 'extract' | 'review';

interface PageStatus {
  stage: 'waiting' | 'parsing' | 'validating' | 'done' | 'error';
  error?: string;
}

export default function AppPage() {
  const { user, loading: authLoading, logout } = useAuth();
  const navigate = useNavigate();

  // Upload state
  const [upload, setUpload] = useState<UploadResponse | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState('');
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const fileInputRef = useRef<HTMLInputElement>(null);
  const dropRef = useRef<HTMLDivElement>(null);

  // Extract state
  const [step, setStep] = useState<Step>('upload');
  const [pageStatuses, setPageStatuses] = useState<Record<number, PageStatus>>({});
  const [extracting, setExtracting] = useState(false);
  const [extractDone, setExtractDone] = useState(false);
  const [quotaMsg, setQuotaMsg] = useState('');
  const cancelRef = useRef<(() => void) | null>(null);

  // Review state
  const [results, setResults] = useState<Record<string, PageResult>>({});
  const [activePage, setActivePage] = useState<number>(1);

  // ── Auth guard ──────────────────────────────────────────────────────────────
  if (!authLoading && !user) {
    navigate('/', { replace: true });
    return null;
  }
  if (authLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="w-8 h-8 border-4 border-indigo-400 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  // ── Upload handlers ─────────────────────────────────────────────────────────
  async function handleFile(file: File) {
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      setUploadError('Only PDF files are supported.');
      return;
    }
    setUploading(true);
    setUploadError('');
    try {
      const res = await uploadPdf(file);
      setUpload(res);
      setSelected(new Set(Array.from({ length: res.total_pages }, (_, i) => i + 1)));
      setStep('upload');
    } catch (e: unknown) {
      setUploadError((e as Error).message);
    } finally {
      setUploading(false);
    }
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  }

  // ── Extract ─────────────────────────────────────────────────────────────────
  function startExtract() {
    if (!upload || selected.size === 0) return;
    const pageNums = [...selected].sort((a, b) => a - b);
    const initStatuses: Record<number, PageStatus> = {};
    pageNums.forEach((p) => { initStatuses[p] = { stage: 'waiting' }; });
    setPageStatuses(initStatuses);
    setResults({});
    setExtractDone(false);
    setExtracting(true);
    setStep('extract');

    cancelRef.current = extractPages(
      upload.upload_id,
      pageNums,
      (evt: SSEEvent) => {
        setPageStatuses((prev) => eventToStatus(evt, prev));
        if (evt.type === 'result') {
          setResults((prev) => ({ ...prev, [String(evt.page)]: evt.data }));
          setActivePage(evt.page);
        }
        if (evt.type === 'quota_exceeded') {
          setQuotaMsg(
            `Daily limit of ${evt.daily_limit} pages reached. Resets at ${new Date(evt.reset_at).toLocaleTimeString()}.`
          );
          setExtracting(false);
          setExtractDone(true);
        }
        if (evt.type === 'done') {
          setExtracting(false);
          setExtractDone(true);
        }
      },
      (msg) => {
        setExtracting(false);
        setUploadError(msg);
      }
    );
  }

  function goToReview() {
    setStep('review');
    const firstPage = Math.min(...Object.keys(results).map(Number));
    setActivePage(firstPage);
  }

  // ── Reset ───────────────────────────────────────────────────────────────────
  function reset() {
    if (upload) deleteUpload(upload.upload_id);
    cancelRef.current?.();
    setUpload(null);
    setSelected(new Set());
    setStep('upload');
    setPageStatuses({});
    setResults({});
    setExtracting(false);
    setExtractDone(false);
    setUploadError('');
    setQuotaMsg('');
  }

  const resultPages = Object.keys(results).map(Number).sort((a, b) => a - b);

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col">
      {/* Navbar */}
      <header className="bg-white border-b border-slate-200 px-6 py-3 flex items-center justify-between shadow-sm">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 bg-indigo-500 rounded-lg flex items-center justify-center">
            <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m0 12.75h7.5M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z" />
            </svg>
          </div>
          <span className="font-semibold text-slate-800">Handwriting Extractor</span>
        </div>
        <div className="flex items-center gap-3">
          {user?.picture && <img src={user.picture} alt="" className="w-7 h-7 rounded-full" />}
          <span className="text-sm text-slate-600 hidden sm:inline">{user?.name}</span>
          <button
            onClick={logout}
            className="text-sm text-slate-500 hover:text-slate-800 transition"
          >
            Sign out
          </button>
        </div>
      </header>

      <main className="flex-1 max-w-5xl mx-auto w-full px-4 py-8 space-y-6">
        {/* ── UPLOAD STEP ─────────────────────────────────────────────────── */}
        {step === 'upload' && (
          <div className="space-y-6">
            <div>
              <h2 className="text-xl font-semibold text-slate-800">Upload a document</h2>
              <p className="text-sm text-slate-500 mt-1">Drag & drop a PDF or click to browse</p>
            </div>

            {!upload ? (
              <div
                ref={dropRef}
                onDrop={handleDrop}
                onDragOver={(e) => e.preventDefault()}
                onClick={() => fileInputRef.current?.click()}
                className="border-2 border-dashed border-slate-300 rounded-2xl p-16 flex flex-col items-center gap-4 cursor-pointer hover:border-indigo-400 hover:bg-indigo-50/30 transition bg-white"
              >
                {uploading ? (
                  <div className="w-10 h-10 border-4 border-indigo-400 border-t-transparent rounded-full animate-spin" />
                ) : (
                  <>
                    <svg className="w-14 h-14 text-slate-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1}
                        d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5m-13.5-9L12 3m0 0 4.5 4.5M12 3v13.5" />
                    </svg>
                    <div className="text-center">
                      <p className="font-medium text-slate-600">Drop your PDF here</p>
                      <p className="text-sm text-slate-400 mt-1">or click to browse files</p>
                    </div>
                  </>
                )}
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".pdf"
                  className="hidden"
                  onChange={(e) => { const f = e.target.files?.[0]; if (f) handleFile(f); }}
                />
              </div>
            ) : (
              <div className="bg-white rounded-2xl border border-slate-200 p-6 space-y-5 shadow-sm">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-semibold text-slate-800">{upload.filename}</p>
                    <p className="text-sm text-slate-500">{upload.total_pages} page{upload.total_pages !== 1 ? 's' : ''}</p>
                  </div>
                  <button onClick={reset} className="text-sm text-slate-400 hover:text-red-500 transition">
                    Remove
                  </button>
                </div>

                <PagePicker
                  thumbnails={upload.thumbnails}
                  selected={selected}
                  onToggle={(p) => setSelected((s) => {
                    const n = new Set(s);
                    n.has(p) ? n.delete(p) : n.add(p);
                    return n;
                  })}
                  onSelectAll={() => setSelected(new Set(Array.from({ length: upload.total_pages }, (_, i) => i + 1)))}
                  onClearAll={() => setSelected(new Set())}
                />

                <button
                  onClick={startExtract}
                  disabled={selected.size === 0}
                  className="w-full py-3 bg-indigo-600 text-white rounded-xl font-semibold hover:bg-indigo-700 transition disabled:opacity-50 disabled:cursor-not-allowed shadow"
                >
                  Extract {selected.size} page{selected.size !== 1 ? 's' : ''}
                </button>
              </div>
            )}

            {uploadError && <p className="text-sm text-red-500">{uploadError}</p>}
          </div>
        )}

        {/* ── EXTRACT STEP ────────────────────────────────────────────────── */}
        {step === 'extract' && (
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-xl font-semibold text-slate-800">
                  {extracting ? 'Extracting…' : 'Extraction complete'}
                </h2>
                <p className="text-sm text-slate-500 mt-1">{upload?.filename}</p>
              </div>
              {extractDone && (
                <button
                  onClick={goToReview}
                  className="px-5 py-2.5 bg-indigo-600 text-white rounded-xl font-semibold hover:bg-indigo-700 transition shadow"
                >
                  Review & Export →
                </button>
              )}
            </div>

            {quotaMsg && (
              <div className="bg-amber-50 border border-amber-200 rounded-xl px-4 py-3 text-sm text-amber-800">
                {quotaMsg}
              </div>
            )}

            <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
              <ProgressFeed
                pageNums={[...selected].sort((a, b) => a - b)}
                statuses={pageStatuses}
              />
            </div>

            {!extracting && (
              <button onClick={reset} className="text-sm text-slate-500 hover:text-slate-800 transition">
                ← Start over
              </button>
            )}
          </div>
        )}

        {/* ── REVIEW STEP ─────────────────────────────────────────────────── */}
        {step === 'review' && (
          <div className="space-y-6">
            <div className="flex items-center justify-between flex-wrap gap-3">
              <div>
                <h2 className="text-xl font-semibold text-slate-800">Review & Edit</h2>
                <p className="text-sm text-slate-500 mt-1">{upload?.filename}</p>
              </div>
              <button onClick={reset} className="text-sm text-slate-500 hover:text-slate-800 transition">
                ← New document
              </button>
            </div>

            {/* Page tabs */}
            {resultPages.length > 1 && (
              <div className="flex gap-1 flex-wrap">
                {resultPages.map((p) => (
                  <button
                    key={p}
                    onClick={() => setActivePage(p)}
                    className={`px-3 py-1.5 rounded-lg text-sm font-medium transition ${
                      activePage === p
                        ? 'bg-indigo-600 text-white shadow'
                        : 'bg-white text-slate-600 border border-slate-200 hover:border-indigo-300'
                    }`}
                  >
                    Page {p}
                  </button>
                ))}
              </div>
            )}

            {/* Side-by-side */}
            <div className="grid grid-cols-1 lg:grid-cols-[2fr_3fr] gap-5">
              {/* Original image */}
              <div className="bg-white rounded-2xl border border-slate-200 p-3 shadow-sm">
                <p className="text-xs font-medium text-slate-400 uppercase tracking-wide mb-2 px-1">Original</p>
                {upload && (
                  <img
                    src={`data:image/png;base64,${upload.thumbnails[activePage - 1]}`}
                    alt={`Page ${activePage}`}
                    className="w-full rounded-lg"
                  />
                )}
              </div>

              {/* Editable result */}
              <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm overflow-y-auto max-h-[75vh]">
                <p className="text-xs font-medium text-slate-400 uppercase tracking-wide mb-4">Extracted (editable)</p>
                {results[String(activePage)] ? (
                  <SectionEditor
                    page={results[String(activePage)]}
                    onChange={(updated) =>
                      setResults((prev) => ({ ...prev, [String(activePage)]: updated }))
                    }
                  />
                ) : (
                  <p className="text-sm text-slate-400">No data for this page.</p>
                )}
              </div>
            </div>

            {/* Export */}
            <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm">
              <ExportBar reviewData={results} />
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
