import { useEffect, useRef, useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { listDocuments, deleteDocument, renameDocument } from '../api/client';
import type { DocumentSummary } from '../api/types';
import { useAuth } from '../hooks/useAuth';

export default function HistoryPage() {
  const { user, loading: authLoading, logout } = useAuth();
  const navigate = useNavigate();

  const [docs, setDocs] = useState<DocumentSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [deleting, setDeleting] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingName, setEditingName] = useState('');
  const renameInputRef = useRef<HTMLInputElement>(null);

  const PER_PAGE = 20;

  useEffect(() => {
    if (!authLoading && !user) navigate('/', { replace: true });
  }, [authLoading, user, navigate]);

  useEffect(() => {
    if (!user) return;
    setLoading(true);
    setError('');
    listDocuments(page, PER_PAGE)
      .then((data) => { setDocs(data.items); setTotal(data.total); })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [user, page]);

  function startRename(doc: DocumentSummary) {
    setEditingId(doc.id);
    setEditingName(doc.filename);
    setTimeout(() => renameInputRef.current?.select(), 0);
  }

  async function commitRename(id: string) {
    const name = editingName.trim();
    setEditingId(null);
    if (!name) return;
    const prev = docs.find((d) => d.id === id)?.filename;
    if (name === prev) return;
    setDocs((ds) => ds.map((d) => (d.id === id ? { ...d, filename: name } : d)));
    try {
      await renameDocument(id, name);
    } catch {
      setDocs((ds) => ds.map((d) => (d.id === id ? { ...d, filename: prev ?? d.filename } : d)));
    }
  }

  async function handleDelete(id: string) {
    if (!confirm('Delete this document and all its extracted pages?')) return;
    setDeleting(id);
    try {
      await deleteDocument(id);
      setDocs((prev) => prev.filter((d) => d.id !== id));
      setTotal((t) => t - 1);
    } catch (e: unknown) {
      alert((e as Error).message);
    } finally {
      setDeleting(null);
    }
  }

  const totalPages = Math.ceil(total / PER_PAGE);

  if (authLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="w-8 h-8 border-4 border-indigo-400 border-t-transparent rounded-full animate-spin" />
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
            <span className="font-semibold text-slate-800 group-hover:text-indigo-600 transition">InkScan</span>
          </Link>
          <span className="text-slate-300">|</span>
          <span className="text-sm font-medium text-slate-500">History</span>
        </div>
        <div className="flex items-center gap-3">
          {user?.picture && <img src={user.picture} alt="" className="w-7 h-7 rounded-full" />}
          <span className="text-sm text-slate-600 hidden sm:inline">{user?.name}</span>
          <button onClick={logout} className="text-sm text-slate-500 hover:text-slate-800 transition">
            Sign out
          </button>
        </div>
      </header>

      <main className="flex-1 max-w-4xl mx-auto w-full px-4 py-8">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-xl font-semibold text-slate-800">Your documents</h2>
          <Link
            to="/app"
            className="px-4 py-2 bg-indigo-600 text-white rounded-xl text-sm font-semibold hover:bg-indigo-700 transition shadow"
          >
            + New document
          </Link>
        </div>

        {error && <p className="text-sm text-red-500 mb-4">{error}</p>}

        {loading ? (
          <div className="flex justify-center py-16">
            <div className="w-8 h-8 border-4 border-indigo-400 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : docs.length === 0 ? (
          <div className="bg-white rounded-2xl border border-slate-200 p-12 flex flex-col items-center gap-3 text-center shadow-sm">
            <svg className="w-12 h-12 text-slate-200" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m6.75 12H9m1.5-12H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z" />
            </svg>
            <p className="text-slate-500 font-medium">No documents yet</p>
            <p className="text-sm text-slate-400">Upload a PDF or image to get started.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {docs.map((doc) => (
              <div
                key={doc.id}
                className="bg-white rounded-2xl border border-slate-200 px-5 py-4 flex items-center justify-between gap-4 shadow-sm hover:border-indigo-200 transition"
              >
                <div className="flex-1 min-w-0">
                  {editingId === doc.id ? (
                    <input
                      ref={renameInputRef}
                      className="font-medium text-slate-800 w-full bg-white border border-indigo-400 rounded px-2 py-0.5 focus:outline-none text-sm"
                      value={editingName}
                      onChange={(e) => setEditingName(e.target.value)}
                      onBlur={() => commitRename(doc.id)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') commitRename(doc.id);
                        if (e.key === 'Escape') setEditingId(null);
                      }}
                    />
                  ) : (
                    <p
                      className="font-medium text-slate-800 truncate cursor-text hover:text-indigo-600 transition"
                      title="Click to rename"
                      onClick={() => startRename(doc)}
                    >
                      {doc.filename}
                    </p>
                  )}
                  <div className="flex items-center gap-3 mt-1 flex-wrap">
                    <span className="text-xs text-slate-400">
                      {doc.extracted_pages}/{doc.total_pages} pages extracted
                    </span>
                    <StatusBadge status={doc.status} />
                    <span className="text-xs text-slate-400">
                      {new Date(doc.created_at).toLocaleDateString()}
                    </span>
                  </div>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  {doc.extracted_pages > 0 && (
                    <Link
                      to={`/documents/${doc.id}`}
                      className="px-3 py-1.5 bg-indigo-50 text-indigo-600 rounded-lg text-sm font-medium hover:bg-indigo-100 transition"
                    >
                      Open
                    </Link>
                  )}
                  <button
                    onClick={() => handleDelete(doc.id)}
                    disabled={deleting === doc.id}
                    className="px-3 py-1.5 text-slate-400 hover:text-red-500 rounded-lg text-sm transition disabled:opacity-50"
                  >
                    {deleting === doc.id ? '…' : 'Delete'}
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-center gap-2 mt-6">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
              className="px-3 py-1.5 rounded-lg border border-slate-200 text-sm text-slate-600 hover:border-indigo-300 disabled:opacity-40 transition"
            >
              Previous
            </button>
            <span className="text-sm text-slate-500">
              Page {page} of {totalPages}
            </span>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page === totalPages}
              className="px-3 py-1.5 rounded-lg border border-slate-200 text-sm text-slate-600 hover:border-indigo-300 disabled:opacity-40 transition"
            >
              Next
            </button>
          </div>
        )}
      </main>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    uploaded:   'bg-slate-100 text-slate-500',
    extracting: 'bg-amber-100 text-amber-700',
    done:       'bg-emerald-100 text-emerald-700',
  };
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${map[status] ?? 'bg-slate-100 text-slate-500'}`}>
      {status}
    </span>
  );
}
