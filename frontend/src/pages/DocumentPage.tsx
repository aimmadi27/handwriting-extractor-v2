import { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { getDocument, savePageResult } from '../api/client';
import type { DocumentDetail, PageResult } from '../api/types';
import { useAuth } from '../hooks/useAuth';
import { useDebounce } from '../hooks/useDebounce';
import SectionEditor from '../components/SectionEditor';
import ExportBar from '../components/ExportBar';

export default function DocumentPage() {
  const { documentId } = useParams<{ documentId: string }>();
  const { user, loading: authLoading, logout } = useAuth();
  const navigate = useNavigate();

  const [doc, setDoc] = useState<DocumentDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [activePage, setActivePage] = useState<number>(1);
  const [results, setResults] = useState<Record<string, PageResult>>({});
  const [saveStatus, setSaveStatus] = useState<'saved' | 'saving' | ''>('');

  useEffect(() => {
    if (!authLoading && !user) navigate('/', { replace: true });
  }, [authLoading, user, navigate]);

  useEffect(() => {
    if (!user || !documentId) return;
    setLoading(true);
    setError('');
    getDocument(documentId)
      .then((data) => {
        setDoc(data);
        const pageResults: Record<string, PageResult> = {};
        for (const [num, p] of Object.entries(data.pages)) {
          pageResults[num] = {
            doc_type:   p.doc_type,
            title:      p.title,
            sections:   p.sections,
            validation: p.validation,
          };
        }
        setResults(pageResults);
        const firstPage = Math.min(...Object.keys(data.pages).map(Number));
        setActivePage(firstPage);
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [user, documentId]);

  const handleChange = useCallback((updated: PageResult) => {
    setResults((prev) => ({ ...prev, [String(activePage)]: updated }));
    setSaveStatus('saving');
  }, [activePage]);

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

  const pageNums = Object.keys(results).map(Number).sort((a, b) => a - b);
  const exportData = results;

  if (authLoading || loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="w-8 h-8 border-4 border-indigo-400 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center gap-4">
        <p className="text-red-500">{error}</p>
        <Link to="/history" className="text-sm text-indigo-600 hover:underline">← Back to history</Link>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col">
      {/* Navbar */}
      <header className="bg-white border-b border-slate-200 px-6 py-3 flex items-center justify-between shadow-sm">
        <div className="flex items-center gap-4">
          <Link to="/app" className="flex items-center gap-2 group">
            <div className="w-8 h-8 bg-indigo-500 rounded-lg flex items-center justify-center">
              <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m0 12.75h7.5M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z" />
              </svg>
            </div>
            <span className="font-semibold text-slate-800 group-hover:text-indigo-600 transition">Handwriting Extractor</span>
          </Link>
          <span className="text-slate-300">|</span>
          <Link to="/history" className="text-sm text-slate-500 hover:text-slate-800 transition">History</Link>
        </div>
        <div className="flex items-center gap-3">
          {saveStatus === 'saving' && <span className="text-xs text-slate-400">Saving…</span>}
          {saveStatus === 'saved'  && <span className="text-xs text-emerald-500">Saved</span>}
          {user?.picture && <img src={user.picture} alt="" className="w-7 h-7 rounded-full" />}
          <span className="text-sm text-slate-600 hidden sm:inline">{user?.name}</span>
          <button onClick={logout} className="text-sm text-slate-500 hover:text-slate-800 transition">
            Sign out
          </button>
        </div>
      </header>

      <main className="flex-1 max-w-5xl mx-auto w-full px-4 py-8 space-y-6">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div>
            <h2 className="text-xl font-semibold text-slate-800">{doc?.filename}</h2>
            <p className="text-sm text-slate-500 mt-1">
              {pageNums.length} page{pageNums.length !== 1 ? 's' : ''} extracted
              · {new Date(doc?.created_at ?? '').toLocaleDateString()}
            </p>
          </div>
          <Link to="/history" className="text-sm text-slate-500 hover:text-slate-800 transition">
            ← Back to history
          </Link>
        </div>

        {/* Page tabs */}
        {pageNums.length > 1 && (
          <div className="flex gap-1 flex-wrap">
            {pageNums.map((p) => (
              <button
                key={p}
                onClick={() => { setSaveStatus(''); setActivePage(p); }}
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

        {/* Side-by-side editor */}
        <div className="grid grid-cols-1 lg:grid-cols-[2fr_3fr] gap-5">
          <div className="bg-white rounded-2xl border border-slate-200 p-4 shadow-sm flex flex-col gap-2">
            <p className="text-xs font-medium text-slate-400 uppercase tracking-wide">Page {activePage}</p>
            <div className="bg-slate-50 rounded-xl p-3 text-center text-slate-400 text-sm">
              Image preview not available for saved documents
            </div>
          </div>

          <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm overflow-y-auto max-h-[75vh]">
            <p className="text-xs font-medium text-slate-400 uppercase tracking-wide mb-4">Extracted (editable)</p>
            {results[String(activePage)] ? (
              <SectionEditor
                page={results[String(activePage)]}
                onChange={handleChange}
              />
            ) : (
              <p className="text-sm text-slate-400">No data for this page.</p>
            )}
          </div>
        </div>

        {/* Export */}
        <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm">
          <ExportBar reviewData={exportData} />
        </div>
      </main>
    </div>
  );
}
