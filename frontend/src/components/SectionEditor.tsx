import type { Section, KeyValueSection, TableSection, QAPairSection, ParagraphSection, PageResult } from '../api/types';

interface Props {
  page: PageResult;
  onChange: (updated: PageResult) => void;
}

// ── Confidence helpers ────────────────────────────────────────────────────────

function ConfidenceBar({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const color =
    value < 0.5 ? 'bg-red-400' :
    value < 0.8 ? 'bg-amber-400' :
    'bg-emerald-400';
  const label =
    value < 0.5 ? 'Low confidence' :
    value < 0.8 ? 'Needs review' :
    'High confidence';
  const textColor =
    value < 0.5 ? 'text-red-600' :
    value < 0.8 ? 'text-amber-600' :
    'text-emerald-600';
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-slate-100 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className={`text-xs font-medium ${textColor} whitespace-nowrap`}>
        {pct}% — {label}
      </span>
    </div>
  );
}

function sectionConfidenceBadge(page: PageResult, idx: number) {
  const issue = page.validation?.section_issues?.find((i) => i.section_index === idx);
  if (!issue) return null;
  const pct = Math.round(issue.confidence * 100);
  if (issue.confidence >= 0.8) return null;
  const cls = issue.confidence < 0.5
    ? 'text-red-500 bg-red-50'
    : 'text-amber-500 bg-amber-50';
  return (
    <span className={`ml-2 text-xs font-medium px-1.5 py-0.5 rounded ${cls}`}>
      {pct}%
    </span>
  );
}

// ── Key-Value ─────────────────────────────────────────────────────────────────
function KeyValueEditor({ section, onChange }: { section: KeyValueSection; onChange: (s: KeyValueSection) => void }) {
  function addPair() {
    onChange({ ...section, pairs: [...section.pairs, { key: '', value: '' }] });
  }
  function deletePair(i: number) {
    onChange({ ...section, pairs: section.pairs.filter((_, idx) => idx !== i) });
  }
  return (
    <div className="space-y-0.5">
      <div className="divide-y divide-slate-100">
        {section.pairs.map((pair, i) => (
          <div key={i} className="grid grid-cols-[180px_1fr_auto] gap-2 py-2 group">
            <input
              className="text-xs font-semibold text-slate-500 bg-slate-50 rounded px-2 py-1 border border-slate-200 focus:outline-none focus:border-indigo-400"
              value={pair.key}
              onChange={(e) => {
                const pairs = [...section.pairs];
                pairs[i] = { ...pairs[i], key: e.target.value };
                onChange({ ...section, pairs });
              }}
            />
            <input
              className="text-sm text-slate-800 bg-white rounded px-2 py-1 border border-slate-200 focus:outline-none focus:border-indigo-400"
              value={pair.value ?? ''}
              onChange={(e) => {
                const pairs = [...section.pairs];
                pairs[i] = { ...pairs[i], value: e.target.value };
                onChange({ ...section, pairs });
              }}
            />
            <button
              onClick={() => deletePair(i)}
              className="opacity-0 group-hover:opacity-100 text-slate-300 hover:text-red-400 transition px-1 text-lg leading-none"
              title="Delete row"
            >
              ×
            </button>
          </div>
        ))}
      </div>
      <button
        onClick={addPair}
        className="mt-1 text-xs text-indigo-500 hover:text-indigo-700 transition font-medium"
      >
        + Add row
      </button>
    </div>
  );
}

// ── Table ─────────────────────────────────────────────────────────────────────
function TableEditor({ section, onChange }: { section: TableSection; onChange: (s: TableSection) => void }) {
  function addRow() {
    onChange({ ...section, rows: [...section.rows, section.columns.map(() => '')] });
  }
  function deleteRow(ri: number) {
    onChange({ ...section, rows: section.rows.filter((_, idx) => idx !== ri) });
  }
  return (
    <div>
      <div className="overflow-x-auto">
        <table className="text-sm w-full border-collapse">
          <thead>
            <tr>
              {section.columns.map((col, ci) => (
                <th key={ci} className="px-1 py-1">
                  <input
                    className="text-xs font-semibold text-slate-600 bg-slate-100 rounded px-2 py-1 w-full border border-slate-200 focus:outline-none focus:border-indigo-400"
                    value={col}
                    onChange={(e) => {
                      const columns = [...section.columns];
                      columns[ci] = e.target.value;
                      onChange({ ...section, columns });
                    }}
                  />
                </th>
              ))}
              <th className="w-6" />
            </tr>
          </thead>
          <tbody>
            {section.rows.map((row, ri) => (
              <tr key={ri} className={`group ${ri % 2 === 0 ? 'bg-white' : 'bg-slate-50'}`}>
                {section.columns.map((_, ci) => (
                  <td key={ci} className="px-1 py-1">
                    <input
                      className="text-sm text-slate-800 bg-transparent rounded px-2 py-1 w-full border border-transparent focus:border-slate-200 focus:outline-none focus:border-indigo-400"
                      value={row[ci] ?? ''}
                      onChange={(e) => {
                        const rows = section.rows.map((r, rr) =>
                          rr === ri ? r.map((v, cc) => (cc === ci ? e.target.value : v)) : r
                        );
                        onChange({ ...section, rows });
                      }}
                    />
                  </td>
                ))}
                <td className="px-1 py-1 w-6">
                  <button
                    onClick={() => deleteRow(ri)}
                    className="opacity-0 group-hover:opacity-100 text-slate-300 hover:text-red-400 transition text-lg leading-none"
                    title="Delete row"
                  >
                    ×
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <button
        onClick={addRow}
        className="mt-2 text-xs text-indigo-500 hover:text-indigo-700 transition font-medium"
      >
        + Add row
      </button>
    </div>
  );
}

// ── QA Pair ───────────────────────────────────────────────────────────────────
function QAEditor({ section, onChange }: { section: QAPairSection; onChange: (s: QAPairSection) => void }) {
  return (
    <div className="space-y-4">
      {section.items.map((item, i) => (
        <div key={i} className="space-y-1">
          <input
            className="w-full text-sm font-semibold text-slate-700 bg-slate-50 rounded px-3 py-1.5 border border-slate-200 focus:outline-none focus:border-indigo-400"
            value={item.question}
            onChange={(e) => {
              const items = [...section.items];
              items[i] = { ...items[i], question: e.target.value };
              onChange({ ...section, items });
            }}
          />
          <textarea
            className="w-full text-sm text-slate-800 bg-white rounded px-3 py-2 border border-slate-200 focus:outline-none focus:border-indigo-400 resize-none"
            rows={Math.max(2, Math.ceil((item.answer?.length ?? 0) / 80))}
            value={item.answer ?? ''}
            onChange={(e) => {
              const items = [...section.items];
              items[i] = { ...items[i], answer: e.target.value };
              onChange({ ...section, items });
            }}
          />
        </div>
      ))}
    </div>
  );
}

// ── Paragraph ─────────────────────────────────────────────────────────────────
function ParagraphEditor({ section, onChange }: { section: ParagraphSection; onChange: (s: ParagraphSection) => void }) {
  return (
    <textarea
      className="w-full text-sm text-slate-800 bg-white rounded px-3 py-2 border border-slate-200 focus:outline-none focus:border-indigo-400 resize-none"
      rows={Math.max(3, Math.ceil((section.text?.length ?? 0) / 80))}
      value={section.text ?? ''}
      onChange={(e) => onChange({ ...section, text: e.target.value })}
    />
  );
}

// ── Main ──────────────────────────────────────────────────────────────────────
export default function SectionEditor({ page, onChange }: Props) {
  function updateSection(idx: number, updated: Section) {
    const sections = page.sections.map((s, i) => (i === idx ? updated : s));
    onChange({ ...page, sections });
  }

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="border-b border-slate-200 pb-3 space-y-2">
        <div className="flex items-center gap-2">
          <input
            className="text-lg font-bold text-slate-800 bg-transparent border-b-2 border-transparent focus:border-indigo-400 focus:outline-none flex-1"
            value={page.title}
            onChange={(e) => onChange({ ...page, title: e.target.value })}
          />
          <span className="text-xs uppercase tracking-wide text-slate-400 bg-slate-100 px-2 py-1 rounded shrink-0">
            {page.doc_type}
          </span>
        </div>
        {page.validation?.overall_confidence !== undefined && (
          <ConfidenceBar value={page.validation.overall_confidence} />
        )}
      </div>

      {/* Sections */}
      {page.sections.map((section, idx) => (
        <div key={idx} className="space-y-2">
          <div className="flex items-center gap-1">
            {section.title && (
              <input
                className="text-sm font-semibold text-slate-600 bg-transparent border-b border-transparent focus:border-indigo-400 focus:outline-none flex-1"
                value={section.title}
                onChange={(e) => updateSection(idx, { ...section, title: e.target.value } as Section)}
              />
            )}
            <span className="text-xs text-slate-400 uppercase tracking-wide ml-auto">{section.type}</span>
            {sectionConfidenceBadge(page, idx)}
          </div>

          {section.type === 'key_value' && (
            <KeyValueEditor section={section} onChange={(s) => updateSection(idx, s)} />
          )}
          {section.type === 'table' && (
            <TableEditor section={section} onChange={(s) => updateSection(idx, s)} />
          )}
          {section.type === 'qa_pair' && (
            <QAEditor section={section} onChange={(s) => updateSection(idx, s)} />
          )}
          {section.type === 'paragraph' && (
            <ParagraphEditor section={section} onChange={(s) => updateSection(idx, s)} />
          )}
        </div>
      ))}
    </div>
  );
}
