interface Props {
  thumbnails: string[];
  selected: Set<number>;
  onToggle: (page: number) => void;
  onSelectAll: () => void;
  onClearAll: () => void;
}

export default function PagePicker({ thumbnails, selected, onToggle, onSelectAll, onClearAll }: Props) {
  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-sm font-medium text-slate-600">
          {selected.size} of {thumbnails.length} page{thumbnails.length !== 1 ? 's' : ''} selected
        </p>
        <div className="flex gap-2">
          <button
            onClick={onSelectAll}
            className="text-xs text-indigo-600 hover:text-indigo-800 font-medium"
          >
            Select all
          </button>
          <span className="text-slate-300">|</span>
          <button
            onClick={onClearAll}
            className="text-xs text-slate-500 hover:text-slate-700 font-medium"
          >
            Clear
          </button>
        </div>
      </div>

      <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 gap-3 max-h-72 overflow-y-auto pr-1">
        {thumbnails.map((thumb, i) => {
          const page = i + 1;
          const isSelected = selected.has(page);
          return (
            <button
              key={page}
              onClick={() => onToggle(page)}
              className={`relative rounded-lg overflow-hidden border-2 transition-all ${
                isSelected
                  ? 'border-indigo-500 shadow-md shadow-indigo-100'
                  : 'border-slate-200 hover:border-slate-400'
              }`}
            >
              <img
                src={`data:image/png;base64,${thumb}`}
                alt={`Page ${page}`}
                className="w-full object-cover aspect-[3/4]"
              />
              <div className={`absolute inset-0 transition-opacity ${isSelected ? 'bg-indigo-500/10' : ''}`} />
              {isSelected && (
                <div className="absolute top-1 right-1 w-5 h-5 bg-indigo-500 rounded-full flex items-center justify-center">
                  <svg className="w-3 h-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                  </svg>
                </div>
              )}
              <div className="absolute bottom-0 left-0 right-0 bg-black/40 text-white text-xs text-center py-0.5">
                {page}
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
