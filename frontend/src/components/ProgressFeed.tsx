import type { SSEEvent } from '../api/types';

interface PageStatus {
  stage: 'waiting' | 'parsing' | 'validating' | 'done' | 'error';
  error?: string;
}

interface Props {
  pageNums: number[];
  statuses: Record<number, PageStatus>;
}

const STAGE_LABEL: Record<PageStatus['stage'], string> = {
  waiting:    'Waiting…',
  parsing:    'Parsing handwriting…',
  validating: 'Validating…',
  done:       'Done',
  error:      'Error',
};

const STAGE_COLOR: Record<PageStatus['stage'], string> = {
  waiting:    'bg-slate-200',
  parsing:    'bg-amber-400 animate-pulse',
  validating: 'bg-blue-400 animate-pulse',
  done:       'bg-green-500',
  error:      'bg-red-500',
};

export function eventToStatus(e: SSEEvent, prev: Record<number, PageStatus>): Record<number, PageStatus> {
  const next = { ...prev };
  if (e.type === 'progress') {
    next[e.page] = { stage: e.stage };
  } else if (e.type === 'result') {
    next[e.page] = { stage: 'done' };
  } else if (e.type === 'error') {
    next[e.page] = { stage: 'error', error: e.error };
  }
  return next;
}

export default function ProgressFeed({ pageNums, statuses }: Props) {
  return (
    <div className="space-y-2">
      {pageNums.map((p) => {
        const s = statuses[p] ?? { stage: 'waiting' };
        return (
          <div key={p} className="flex items-center gap-3 py-2 px-3 bg-slate-50 rounded-lg border border-slate-100">
            <div className={`w-2.5 h-2.5 rounded-full flex-shrink-0 ${STAGE_COLOR[s.stage]}`} />
            <span className="text-sm font-medium text-slate-700 w-16">Page {p}</span>
            <span className="text-sm text-slate-500 flex-1">
              {s.stage === 'error' ? s.error : STAGE_LABEL[s.stage]}
            </span>
          </div>
        );
      })}
    </div>
  );
}
