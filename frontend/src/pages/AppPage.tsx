import { useState, useCallback, useRef } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { uploadPdf, combineImages, deleteUpload, extractPages, savePageResult, getDocumentStatus } from '../api/client';
import type { UploadResponse, PageResult, SSEEvent } from '../api/types';
import { useAuth } from '../hooks/useAuth';
import { useDebounce } from '../hooks/useDebounce';
import PagePicker from '../components/PagePicker';
import ProgressFeed, { eventToStatus } from '../components/ProgressFeed';
import SectionEditor from '../components/SectionEditor';
import ExportBar from '../components/ExportBar';
import BatchQueue from '../components/BatchQueue';

type Step = 'upload' | 'extract' | 'review' | 'batch';

interface PageStatus {
  stage: 'waiting' | 'parsing' | 'validating' | 'done' | 'error';
  error?: string;
}

export interface BatchItem {
  localId: string;
  file: File;
  uploadPhase: 'pending' | 'uploading' | 'done' | 'error';
  uploadResult?: UploadResponse;
  extractPhase: 'idle' | 'running' | 'done' | 'error';
  donePages: number;
  error?: string;
}

const IMAGE_EXTS = ['.jpg', '.jpeg', '.png', '.webp', '.tiff', '.tif'];
const ACCEPTED_EXTS = ['.pdf', ...IMAGE_EXTS];


export default function AppPage() {
  const { user, loading: authLoading, logout } = useAuth();
  const navigate = useNavigate();

  // Upload state
  const [upload, setUpload] = useState<UploadResponse | null>(null);
  const [documentId, setDocumentId] = useState<string | null>(null);
  const [saveStatus, setSaveStatus] = useState<'saved' | 'saving' | ''>('');
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
  const [bgRunning, setBgRunning] = useState(false);
  const [reextracting, setReextracting] = useState<Set<number>>(new Set());
  const cancelRef = useRef<(() => void) | null>(null);

  // Review state
  const [results, setResults] = useState<Record<string, PageResult>>({});
  const [activePage, setActivePage] = useState<number>(1);

  // Batch state
  const [batchItems, setBatchItems] = useState<BatchItem[]>([]);
  const [batchExtracting, setBatchExtracting] = useState(false);
  const [combineMode, setCombineMode] = useState(false);

  // ── Auto-save current page after 1 s of inactivity ─────────────────────────
  useDebounce(results[String(activePage)], 1000, async (pageData) => {
    if (!documentId || !pageData || saveStatus !== 'saving') return;
    try {
      await savePageResult(documentId, activePage, {
        title:      pageData.title,
        sections:   pageData.sections,
        validation: pageData.validation,
      });
      setSaveStatus('saved');
    } catch {
      setSaveStatus('');
    }
  });

  const handlePageChange = useCallback((updated: PageResult) => {
    setResults((prev) => ({ ...prev, [String(activePage)]: updated }));
    setSaveStatus('saving');
  }, [activePage]);

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

  // ── Re-extract a single page in-place ──────────────────────────────────────
  function reextractPage(pageNum: number) {
    if (!upload || reextracting.has(pageNum)) return;
    setReextracting((s) => new Set(s).add(pageNum));
    extractPages(
      upload.upload_id,
      [pageNum],
      (evt: SSEEvent) => {
        if (evt.type === 'result') {
          setResults((prev) => ({ ...prev, [String(evt.page)]: evt.data }));
          setSaveStatus('saving');
        }
        if (evt.type === 'done' || evt.type === 'error') {
          setReextracting((s) => { const n = new Set(s); n.delete(pageNum); return n; });
        }
      },
      () => setReextracting((s) => { const n = new Set(s); n.delete(pageNum); return n; }),
      documentId ?? undefined,
    );
  }

  // ── Single-file upload handler ──────────────────────────────────────────────
  async function handleFile(file: File) {
    if (!ACCEPTED_EXTS.some((ext) => file.name.toLowerCase().endsWith(ext))) {
      setUploadError('Only PDF and image files (JPG, PNG, WEBP, TIFF) are supported.');
      return;
    }
    setUploading(true);
    setUploadError('');
    try {
      const res = await uploadPdf(file);
      setUpload(res);
      setDocumentId(res.document_id ?? null);
      setSelected(new Set(Array.from({ length: res.total_pages }, (_, i) => i + 1)));
      setStep('upload');
    } catch (e: unknown) {
      setUploadError((e as Error).message);
    } finally {
      setUploading(false);
    }
  }

  // ── Multi-file handler ──────────────────────────────────────────────────────
  async function handleFiles(files: File[]) {
    if (files.length === 0) return;
    if (files.length === 1) { handleFile(files[0]); return; }

    // Validate all files
    const invalid = files.find(
      (f) => !ACCEPTED_EXTS.some((ext) => f.name.toLowerCase().endsWith(ext))
    );
    if (invalid) {
      setUploadError(`Unsupported file: ${invalid.name}`);
      return;
    }

    setUploadError('');

    // If combine mode is on, all files must be images
    if (combineMode) {
      const hasPdf = files.some((f) => f.name.toLowerCase().endsWith('.pdf'));
      if (hasPdf) {
        setUploadError('Combine mode only works with images, not PDFs.');
        return;
      }
      setUploading(true);
      try {
        const res = await combineImages(files);
        setUpload(res);
        setDocumentId(res.document_id ?? null);
        setSelected(new Set(Array.from({ length: res.total_pages }, (_, i) => i + 1)));
        setStep('upload');
      } catch (e: unknown) {
        setUploadError((e as Error).message);
      } finally {
        setUploading(false);
      }
      return;
    }

    // Batch mode — upload each file independently
    const items: BatchItem[] = files.map((f) => ({
      localId:      crypto.randomUUID(),
      file:         f,
      uploadPhase:  'pending',
      extractPhase: 'idle',
      donePages:    0,
    }));
    setBatchItems(items);
    setStep('batch');

    // Upload each file, updating status per item
    for (let i = 0; i < items.length; i++) {
      setBatchItems((prev) =>
        prev.map((it, idx) => idx === i ? { ...it, uploadPhase: 'uploading' } : it)
      );
      try {
        const res = await uploadPdf(items[i].file);
        setBatchItems((prev) =>
          prev.map((it, idx) =>
            idx === i ? { ...it, uploadPhase: 'done', uploadResult: res } : it
          )
        );
      } catch (e: unknown) {
        setBatchItems((prev) =>
          prev.map((it, idx) =>
            idx === i ? { ...it, uploadPhase: 'error', error: (e as Error).message } : it
          )
        );
      }
    }
  }

  // ── Batch extract ───────────────────────────────────────────────────────────
  function startBatchExtract() {
    setBatchExtracting(true);
    const readyItems = batchItems.filter((it) => it.uploadPhase === 'done' && it.uploadResult);

    readyItems.forEach((item) => {
      const res = item.uploadResult!;
      const pageNums = Array.from({ length: res.total_pages }, (_, i) => i + 1);

      setBatchItems((prev) =>
        prev.map((it) => it.localId === item.localId ? { ...it, extractPhase: 'running' } : it)
      );

      extractPages(
        res.upload_id,
        pageNums,
        (evt: SSEEvent) => {
          if (evt.type === 'result' || evt.type === 'error') {
            setBatchItems((prev) =>
              prev.map((it) =>
                it.localId === item.localId
                  ? { ...it, donePages: it.donePages + 1 }
                  : it
              )
            );
          }
          if (evt.type === 'done') {
            setBatchItems((prev) =>
              prev.map((it) =>
                it.localId === item.localId ? { ...it, extractPhase: 'done' } : it
              )
            );
            checkAllBatchDone();
          }
        },
        () => {
          setBatchItems((prev) =>
            prev.map((it) =>
              it.localId === item.localId
                ? { ...it, extractPhase: 'error', error: 'Extraction failed' }
                : it
            )
          );
          checkAllBatchDone();
        },
        res.document_id,
      );
    });

    function checkAllBatchDone() {
      setBatchItems((prev) => {
        const allSettled = prev.every(
          (it) => it.uploadPhase === 'error' ||
                  it.extractPhase === 'done' ||
                  it.extractPhase === 'error'
        );
        if (allSettled) setBatchExtracting(false);
        return prev;
      });
    }
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    const files = Array.from(e.dataTransfer.files);
    if (files.length > 1) handleFiles(files);
    else if (files.length === 1) handleFile(files[0]);
  }

  // ── Extract (single) ────────────────────────────────────────────────────────
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
        setSaveStatus('');
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
        if (documentId) {
          setBgRunning(true);
        } else {
          setUploadError(msg);
        }
      },
      documentId ?? undefined
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
    setDocumentId(null);
    setSelected(new Set());
    setStep('upload');
    setPageStatuses({});
    setResults({});
    setExtracting(false);
    setExtractDone(false);
    setUploadError('');
    setQuotaMsg('');
    setSaveStatus('');
    setBgRunning(false);
    setReextracting(new Set());
    setBatchItems([]);
    setBatchExtracting(false);
  }

  const resultPages = Object.keys(results).map(Number).sort((a, b) => a - b);
  const allBatchUploaded = batchItems.length > 0 &&
    batchItems.every((it) => it.uploadPhase === 'done' || it.uploadPhase === 'error');

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col">
      {/* Navbar */}
      <header className="bg-white border-b border-slate-200 px-6 py-3 flex items-center justify-between shadow-sm">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 bg-indigo-500 rounded-lg flex items-center justify-center">
              <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m0 12.75h7.5M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z" />
              </svg>
            </div>
            <span className="font-semibold text-slate-800">InkScan</span>
          </div>
          <Link to="/history" className="text-sm text-slate-500 hover:text-slate-800 transition hidden sm:inline">
            History
          </Link>
        </div>
        <div className="flex items-center gap-3">
          {saveStatus === 'saving' && <span className="text-xs text-slate-400">Saving…</span>}
          {saveStatus === 'saved'  && <span className="text-xs text-emerald-500">Saved</span>}
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
            <div className="flex items-start justify-between flex-wrap gap-3">
              <div>
                <h2 className="text-xl font-semibold text-slate-800">Upload a document</h2>
                <p className="text-sm text-slate-500 mt-1">Drag & drop files or click to browse</p>
              </div>
              {/* Combine toggle — visible when drop zone is empty */}
              {!upload && (
                <label className="flex items-center gap-2 cursor-pointer select-none">
                  <div
                    onClick={() => setCombineMode((v) => !v)}
                    className={`relative w-9 h-5 rounded-full transition-colors ${combineMode ? 'bg-indigo-500' : 'bg-slate-200'}`}
                  >
                    <span className={`absolute top-0.5 left-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform ${combineMode ? 'translate-x-4' : ''}`} />
                  </div>
                  <span className="text-sm text-slate-600">Combine images into one doc</span>
                </label>
              )}
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
                      <p className="font-medium text-slate-600">
                        {combineMode ? 'Drop multiple images to combine' : 'Drop files here — one or many'}
                      </p>
                      <p className="text-sm text-slate-400 mt-1">PDF, JPG, PNG, WEBP, TIFF · up to 50 MB</p>
                    </div>
                  </>
                )}
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".pdf,.jpg,.jpeg,.png,.webp,.tiff,.tif,image/*"
                  multiple
                  className="hidden"
                  onChange={(e) => {
                    const files = Array.from(e.target.files ?? []);
                    if (files.length > 1) handleFiles(files);
                    else if (files.length === 1) handleFile(files[0]);
                    e.target.value = '';
                  }}
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

        {/* ── BATCH STEP ──────────────────────────────────────────────────── */}
        {step === 'batch' && (
          <BatchQueue
            items={batchItems}
            extracting={batchExtracting}
            allUploaded={allBatchUploaded}
            onExtractAll={startBatchExtract}
            onReset={reset}
          />
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

            {bgRunning && documentId && (
              <div className="bg-blue-50 border border-blue-200 rounded-xl px-4 py-3 text-sm text-blue-800 flex items-center justify-between gap-4">
                <span>Connection lost — extraction is still running in the background.</span>
                <button
                  onClick={async () => {
                    try {
                      const s = await getDocumentStatus(documentId);
                      if (s.status === 'done') {
                        navigate(`/documents/${documentId}`);
                      } else {
                        alert(`Still processing: ${s.extracted_pages}/${s.total_pages} pages done.`);
                      }
                    } catch {
                      alert('Could not reach server. Try again shortly.');
                    }
                  }}
                  className="shrink-0 px-3 py-1.5 bg-blue-600 text-white rounded-lg text-xs font-semibold hover:bg-blue-700 transition"
                >
                  Check status
                </button>
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
            {resultPages.length > 0 && (
              <div className="flex items-center gap-2 flex-wrap">
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
                {upload && (
                  <button
                    onClick={() => reextractPage(activePage)}
                    disabled={reextracting.has(activePage)}
                    className="ml-auto px-3 py-1.5 text-sm font-medium rounded-lg border border-slate-200 text-slate-500 hover:border-indigo-300 hover:text-indigo-600 transition disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1.5"
                  >
                    {reextracting.has(activePage) ? (
                      <>
                        <span className="w-3 h-3 border-2 border-indigo-400 border-t-transparent rounded-full animate-spin inline-block" />
                        Re-extracting…
                      </>
                    ) : (
                      <>
                        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                            d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0 3.181 3.183a8.25 8.25 0 0 0 13.803-3.7M4.031 9.865a8.25 8.25 0 0 1 13.803-3.7l3.181 3.182m0-4.991v4.99" />
                        </svg>
                        Re-extract page
                      </>
                    )}
                  </button>
                )}
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
                    onChange={handlePageChange}
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

      {/* Combine-mode info banner (shown when no file loaded yet) */}
      {step === 'upload' && !upload && combineMode && (
        <div className="fixed bottom-0 inset-x-0 bg-indigo-600 text-white text-sm text-center py-2 px-4">
          Combine mode on — drop 2–50 images to merge them into one multi-page document
        </div>
      )}
    </div>
  );
}
