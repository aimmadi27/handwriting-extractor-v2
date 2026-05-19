import { Link } from 'react-router-dom';
import type { BatchItem } from '../pages/AppPage';

interface Props {
  items: BatchItem[];
  extracting: boolean;
  allUploaded: boolean;
  onExtractAll: () => void;
  onReset: () => void;
}

function ItemStatusIcon({ item }: { item: BatchItem }) {
  if (item.uploadPhase === 'uploading') {
    return <span className="w-4 h-4 border-2 border-indigo-400 border-t-transparent rounded-full animate-spin inline-block shrink-0" />;
  }
  if (item.uploadPhase === 'error' || item.extractPhase === 'error') {
    return (
      <svg className="w-4 h-4 text-red-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
      </svg>
    );
  }
  if (item.extractPhase === 'done') {
    return (
      <svg className="w-4 h-4 text-emerald-500 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
      </svg>
    );
  }
  if (item.extractPhase === 'running') {
    return <span className="w-4 h-4 border-2 border-indigo-400 border-t-transparent rounded-full animate-spin inline-block shrink-0" />;
  }
  if (item.uploadPhase === 'done') {
    return (
      <svg className="w-4 h-4 text-slate-300 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
      </svg>
    );
  }
  return <span className="w-4 h-4 rounded-full border-2 border-slate-200 shrink-0 inline-block" />;
}

function ExtractionBar({ item }: { item: BatchItem }) {
  if (item.extractPhase === 'idle' || item.uploadPhase !== 'done') return null;
  const total = item.uploadResult?.total_pages ?? 0;
  if (total === 0) return null;
  const pct = Math.round((item.donePages / total) * 100);
  return (
    <div className="mt-1.5">
      <div className="h-1 bg-slate-100 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all ${item.extractPhase === 'done' ? 'bg-emerald-400' : 'bg-indigo-400'}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <p className="text-xs text-slate-400 mt-0.5">
        {item.extractPhase === 'done'
          ? `${total} page${total !== 1 ? 's' : ''} extracted`
          : `${item.donePages} / ${total} pages`}
      </p>
    </div>
  );
}

export default function BatchQueue({ items, extracting, allUploaded, onExtractAll, onReset }: Props) {
  const totalDone   = items.filter((i) => i.extractPhase === 'done').length;
  const totalErrors = items.filter((i) => i.extractPhase === 'error' || i.uploadPhase === 'error').length;
  const allDone     = items.length > 0 && totalDone + totalErrors === items.length;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h2 className="text-xl font-semibold text-slate-800">
            {allDone ? 'Batch complete' : extracting ? 'Extracting…' : 'Ready to extract'}
          </h2>
          <p className="text-sm text-slate-500 mt-0.5">
            {items.length} file{items.length !== 1 ? 's' : ''}
            {allDone && ` · ${totalDone} succeeded${totalErrors > 0 ? `, ${totalErrors} failed` : ''}`}
          </p>
        </div>
        <div className="flex gap-2">
          {allDone ? (
            <Link
              to="/history"
              className="px-5 py-2.5 bg-indigo-600 text-white rounded-xl font-semibold hover:bg-indigo-700 transition shadow text-sm"
            >
              View in History →
            </Link>
          ) : (
            allUploaded && !extracting && (
              <button
                onClick={onExtractAll}
                className="px-5 py-2.5 bg-indigo-600 text-white rounded-xl font-semibold hover:bg-indigo-700 transition shadow text-sm"
              >
                Extract all {items.filter((i) => i.uploadPhase === 'done').length} files
              </button>
            )
          )}
          <button
            onClick={onReset}
            className="px-4 py-2.5 text-sm text-slate-500 hover:text-slate-800 transition rounded-xl border border-slate-200 hover:border-slate-300"
          >
            {allDone ? 'New batch' : 'Cancel'}
          </button>
        </div>
      </div>

      <div className="space-y-2">
        {items.map((item) => (
          <div
            key={item.localId}
            className="bg-white rounded-2xl border border-slate-200 px-5 py-4 shadow-sm"
          >
            <div className="flex items-center gap-3">
              <ItemStatusIcon item={item} />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-slate-800 truncate">{item.file.name}</p>
                {item.error && <p className="text-xs text-red-500 mt-0.5">{item.error}</p>}
                {item.uploadPhase === 'uploading' && (
                  <p className="text-xs text-slate-400 mt-0.5">Uploading…</p>
                )}
                {item.uploadPhase === 'done' && item.extractPhase === 'idle' && (
                  <p className="text-xs text-slate-400 mt-0.5">
                    {item.uploadResult?.total_pages} page{item.uploadResult?.total_pages !== 1 ? 's' : ''} · ready
                  </p>
                )}
                <ExtractionBar item={item} />
              </div>
              {item.extractPhase === 'done' && item.uploadResult?.document_id && (
                <Link
                  to={`/documents/${item.uploadResult.document_id}`}
                  className="shrink-0 text-xs px-3 py-1.5 bg-indigo-50 text-indigo-600 rounded-lg font-medium hover:bg-indigo-100 transition"
                >
                  Open
                </Link>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
