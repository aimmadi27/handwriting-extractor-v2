import type { Section, KeyValueSection, TableSection, QAPairSection, ParagraphSection, PageResult } from '../api/types';

interface Props {
  page: PageResult;
  onChange: (updated: PageResult) => void;
}

function confidence(val: number) {
  if (val < 0.5) return <span className="ml-2 text-xs font-medium text-red-500 bg-red-50 px-1.5 py-0.5 rounded">Low confidence</span>;
  if (val < 0.8) return <span className="ml-2 text-xs font-medium text-amber-500 bg-amber-50 px-1.5 py-0.5 rounded">Review</span>;
  return null;
}

function sectionConfidence(page: PageResult, idx: number) {
  const issue = page.validation?.section_issues?.find((i) => i.section_index === idx);
  return issue ? confidence(issue.confidence) : null;
}

// ── Key-Value ─────────────────────────────────────────────────────────────────
function KeyValueEditor({ section, onChange }: { section: KeyValueSection; onChange: (s: KeyValueSection) => void }) {
  return (
    <div className="divide-y divide-slate-100">
      {section.pairs.map((pair, i) => (
        <div key={i} className="grid grid-cols-[180px_1fr] gap-2 py-2">
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
        </div>
      ))}
    </div>
  );
}

// ── Table ─────────────────────────────────────────────────────────────────────
function TableEditor({ section, onChange }: { section: TableSection; onChange: (s: TableSection) => void }) {
  return (
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
          </tr>
        </thead>
        <tbody>
          {section.rows.map((row, ri) => (
            <tr key={ri} className={ri % 2 === 0 ? 'bg-white' : 'bg-slate-50'}>
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
            </tr>
          ))}
        </tbody>
      </table>
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
      <div className="border-b border-slate-200 pb-3">
        <div className="flex items-center gap-2">
          <input
            className="text-lg font-bold text-slate-800 bg-transparent border-b-2 border-transparent focus:border-indigo-400 focus:outline-none flex-1"
            value={page.title}
            onChange={(e) => onChange({ ...page, title: e.target.value })}
          />
          <span className="text-xs uppercase tracking-wide text-slate-400 bg-slate-100 px-2 py-1 rounded">
            {page.doc_type}
          </span>
        </div>
        {page.validation?.overall_confidence !== undefined && (
          <p className="text-xs text-slate-400 mt-1">
            Overall confidence: {Math.round(page.validation.overall_confidence * 100)}%
          </p>
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
            {sectionConfidence(page, idx)}
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
