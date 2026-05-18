import { useState } from 'react';
import { exportDocument } from '../api/client';
import type { ExportFormat, PageResult } from '../api/types';

interface Props {
  reviewData: Record<string, PageResult>;
}

const FORMATS: { format: ExportFormat; label: string; icon: string }[] = [
  { format: 'pdf',   label: 'PDF',   icon: '📄' },
  { format: 'word',  label: 'Word',  icon: '📝' },
  { format: 'excel', label: 'Excel', icon: '📊' },
  { format: 'json',  label: 'JSON',  icon: '{ }' },
];

export default function ExportBar({ reviewData }: Props) {
  const [loading, setLoading] = useState<ExportFormat | null>(null);
  const [error, setError] = useState('');

  async function handleExport(format: ExportFormat) {
    setLoading(format);
    setError('');
    try {
      await exportDocument(format, reviewData);
    } catch (e: unknown) {
      setError((e as Error).message);
    } finally {
      setLoading(null);
    }
  }

  return (
    <div className="space-y-2">
      <p className="text-sm font-medium text-slate-600">Export as</p>
      <div className="flex flex-wrap gap-2">
        {FORMATS.map(({ format, label, icon }) => (
          <button
            key={format}
            onClick={() => handleExport(format)}
            disabled={loading !== null}
            className="flex items-center gap-2 px-4 py-2 rounded-lg border border-slate-200 bg-white text-slate-700 text-sm font-medium shadow-sm hover:bg-slate-50 hover:border-indigo-300 transition disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading === format ? (
              <span className="w-4 h-4 border-2 border-slate-400 border-t-indigo-500 rounded-full animate-spin" />
            ) : (
              <span>{icon}</span>
            )}
            {label}
          </button>
        ))}
      </div>
      {error && <p className="text-xs text-red-500">{error}</p>}
    </div>
  );
}
