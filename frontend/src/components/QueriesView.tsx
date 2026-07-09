import { DescriptionIcon, Hub, Bolt, Route, ExportNotes, Search, MoreVert } from '@/src/components/Icons';
import { useEffect, useState } from 'react';
import type { DatasetProfile, Query, SearchPreset } from '@/src/types';
import { cn } from '@/src/lib/utils';
import { getDatasetQueries } from '@/src/lib/api';

const PAGE_SIZE = 10;

interface QueriesViewProps {
  dataset: DatasetProfile | null;
  onSearchQuery: (preset: SearchPreset) => void;
}

export function QueriesView({ dataset, onSearchQuery }: QueriesViewProps) {
  const [queries, setQueries] = useState<Query[]>([]);
  const [selectedQuery, setSelectedQuery] = useState<Query | null>(null);
  const [filter, setFilter] = useState('');
  const [offset, setOffset] = useState(0);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [runState, setRunState] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    if (!dataset) {
      setQueries([]);
      setSelectedQuery(null);
      setIsLoading(false);
      return;
    }
    setIsLoading(true);
    setError(null);

    getDatasetQueries(dataset.id, { limit: PAGE_SIZE, offset, search: filter })
      .then((page) => {
        if (cancelled) return;
        setQueries(page.queries);
        setTotal(page.total);
        setSelectedQuery((current) => page.queries.find((query) => query.id === current?.id) ?? page.queries[0] ?? null);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : 'Could not load queries');
        setQueries([]);
        setSelectedQuery(null);
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [dataset?.id, filter, offset]);

  const pageNumber = Math.floor(offset / PAGE_SIZE) + 1;
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const firstVisible = total === 0 ? 0 : offset + 1;
  const lastVisible = Math.min(offset + queries.length, total);
  const canGoPrevious = offset > 0;
  const canGoNext = offset + queries.length < total;

  function updateFilter(value: string) {
    setFilter(value);
    setOffset(0);
  }

  function handoffSelectedSearch(method = dataset?.default_method ?? 'es_bm25') {
    if (!selectedQuery) return;
    const preset: SearchPreset = {
      id: Date.now(),
      datasetId: dataset?.id,
      queryId: selectedQuery.id,
      query: selectedQuery.text,
      method,
      topK: 10,
      autoRun: true,
    };
    onSearchQuery(preset);
  }

  return (
    <div className="h-full flex overflow-hidden animate-in fade-in duration-500">
      <section className="flex-1 flex flex-col border-r border-outline-variant bg-white min-w-0">
        <div className="p-8 border-b border-outline-variant bg-white">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-outline" size={18} />
            <input
              value={filter}
              onChange={(event) => updateFilter(event.target.value)}
              className="w-full pl-10 pr-4 py-2 bg-surface-container-low border border-outline-variant rounded-lg focus:ring-2 focus:ring-primary focus:border-primary transition-all font-sans text-on-surface outline-none placeholder:text-outline"
              placeholder="Filter query text or doc id..."
              type="text"
            />
          </div>
          <div className="flex items-center justify-between mt-4 gap-4">
            <div className="flex space-x-2">
              <FilterChip label={dataset?.id === 'vimqa' ? 'VIMQA ALL' : 'FULL DEV'} active />
              <FilterChip label="10 / PAGE" />
            </div>
            <span className="font-mono text-[10px] text-outline uppercase tracking-widest font-bold">
              Showing {firstVisible}-{lastVisible} of {total}
            </span>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto custom-scrollbar">
          {error && <div className="p-8 text-primary font-bold">{error}</div>}
          {isLoading && <div className="p-8 text-on-surface-variant font-bold">Loading queries...</div>}
          {!isLoading && !error && queries.length === 0 && <div className="p-8 text-on-surface-variant font-bold">No matching queries.</div>}
          {!isLoading && !error && queries.length > 0 && (
            <table className="w-full border-collapse text-left">
              <thead className="sticky top-0 bg-white border-b border-outline-variant z-10">
                <tr>
                  <th className="px-8 py-4 font-label text-[10px] text-on-surface-variant font-bold uppercase tracking-widest w-32">Query ID</th>
                  <th className="px-8 py-4 font-label text-[10px] text-on-surface-variant font-bold uppercase tracking-widest">Query Text</th>
                  <th className="px-8 py-4 font-label text-[10px] text-on-surface-variant font-bold uppercase tracking-widest w-48">Supported Docs</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-outline-variant/10">
                {queries.map((q) => (
                  <tr
                    key={q.id}
                    onClick={() => setSelectedQuery(q)}
                    className={cn('hover:bg-surface-container-low transition-colors cursor-pointer group align-top', selectedQuery?.id === q.id && 'bg-primary/[0.04] border-l-4 border-primary')}
                  >
                    <td className="px-8 py-4 font-mono text-xs text-primary font-bold align-top whitespace-nowrap">{q.id}</td>
                    <td className="px-8 py-4 align-top"><p className="text-sm text-on-surface font-medium leading-relaxed line-clamp-2 max-w-3xl">{q.text}</p></td>
                    <td className="px-8 py-4 align-top">
                      <div className="flex max-w-48 flex-wrap gap-1">
                        {q.docs.map((doc) => (
                          <span key={doc} className="px-2 py-0.5 bg-primary/5 text-primary font-mono text-[9px] rounded border border-primary/10 uppercase font-bold">
                            {doc.slice(0, 8)}
                          </span>
                        ))}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        <div className="border-t border-outline-variant bg-white px-8 py-4 flex items-center justify-between gap-4">
          <div className="font-mono text-[10px] text-on-surface-variant uppercase tracking-widest font-bold">
            Page {pageNumber} / {pageCount}
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
              disabled={!canGoPrevious || isLoading}
              className="h-9 px-4 border border-outline-variant rounded-lg font-bold text-xs uppercase tracking-widest hover:bg-surface-container-low disabled:opacity-40 disabled:cursor-not-allowed"
            >
              Prev
            </button>
            <button
              onClick={() => setOffset(offset + PAGE_SIZE)}
              disabled={!canGoNext || isLoading}
              className="h-9 px-4 bg-primary text-on-primary rounded-lg font-bold text-xs uppercase tracking-widest hover:opacity-90 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              Next
            </button>
          </div>
        </div>
      </section>

      <aside className="w-[clamp(360px,34vw,500px)] bg-white flex flex-col shadow-[-4px_0_24px_rgba(0,0,0,0.04)] z-10">
        <div className="px-6 py-5 border-b border-outline-variant flex items-center justify-between">
          <div className="flex items-center space-x-2 min-w-0">
            <Bolt className="text-primary shrink-0" size={20} />
            <h2 className="font-headline text-xl font-bold text-on-surface truncate">Query Preview</h2>
          </div>
          <button className="p-2 hover:bg-surface-container-low rounded-full transition-colors shrink-0">
            <MoreVert size={20} />
          </button>
        </div>

        {selectedQuery ? (
          <div className="flex-1 overflow-y-auto p-6 custom-scrollbar space-y-8">
            <div className="space-y-3">
              <span className="font-label text-[10px] text-outline uppercase tracking-[0.2em] font-bold">Metadata</span>
              <div className="flex items-center gap-2 min-w-0">
                <div className="font-mono text-xl text-primary font-bold truncate">{selectedQuery.id}</div>
                <span className="px-2 py-0.5 bg-surface-container text-on-surface-variant font-mono text-[9px] rounded font-bold uppercase shrink-0">{dataset?.id ?? 'dataset'}</span>
              </div>
            </div>

            <div className="space-y-3">
              <span className="font-label text-[10px] text-outline uppercase tracking-[0.2em] font-bold">Natural Language Query</span>
              <div className="bg-surface-container-low p-5 rounded-lg border-l-[5px] border-primary">
                <p className="text-base text-on-surface leading-relaxed italic font-medium">{selectedQuery.text}</p>
              </div>
            </div>

            <div className="space-y-3">
              <div className="flex items-center justify-between gap-3">
                <span className="font-label text-[10px] text-outline uppercase tracking-[0.2em] font-bold">Gold Documents</span>
                <span className="font-mono text-[10px] bg-primary/10 px-2 py-0.5 rounded text-primary font-bold uppercase shrink-0">{selectedQuery.docs.length} Docs</span>
              </div>
              <div className="space-y-2">
                {selectedQuery.docs.map((doc) => (
                  <div key={doc} className="flex items-start space-x-3 p-3 bg-white border border-outline-variant rounded-lg hover:border-primary/40 transition-all cursor-pointer">
                    <div className="w-8 h-8 rounded bg-primary/10 flex items-center justify-center shrink-0">
                      <DescriptionIcon className="text-primary" size={16} />
                    </div>
                    <div className="min-w-0">
                      <p className="font-mono text-xs font-bold text-on-surface break-all">{doc}</p>
                      <p className="text-xs text-on-surface-variant mt-1 leading-relaxed line-clamp-2">{dataset?.id === 'vimqa' ? 'Gold context from VimQA qrels.' : 'Gold support document from HotpotQA qrels.'}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="space-y-3">
              <span className="font-label text-[10px] text-outline uppercase tracking-[0.2em] font-bold">Retrieved Context Map</span>
              <div className="bg-surface-container-high rounded-lg h-36 relative overflow-hidden flex items-center justify-center border border-outline-variant/30">
                <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,_var(--tw-gradient-stops))] from-primary/5 via-transparent to-transparent opacity-50" />
                <div className="relative z-10 flex flex-col items-center text-center px-4">
                  <Hub className="text-primary/40 mb-2" size={32} />
                  <span className="font-mono text-[9px] font-bold text-primary tracking-[0.2em] uppercase">2-Hop Knowledge Graph View</span>
                </div>
              </div>
            </div>
          </div>
        ) : (
          <div className="flex-1 p-8 text-on-surface-variant font-bold">No query selected.</div>
        )}

        <div className="p-4 border-t border-outline-variant bg-white space-y-2 shadow-[0_-4px_12px_rgba(0,0,0,0.02)]">
          {runState && <div className="text-[10px] font-mono text-primary font-bold uppercase tracking-widest truncate">{runState}</div>}
          <div className="grid grid-cols-3 gap-2">
            <CompactActionButton Icon={Bolt} label="Run Default" primary onClick={() => handoffSelectedSearch(dataset?.default_method ?? 'tv_hybrid')} />
            <CompactActionButton Icon={Route} label="Best Beam" onClick={() => handoffSelectedSearch(dataset?.methods.includes('tv_bridge_title_entities_rrf') ? 'tv_bridge_title_entities_rrf' : dataset?.default_method ?? 'tv_hybrid')} />
            <CompactActionButton Icon={ExportNotes} label="Export" onClick={() => setRunState('Export uses current query page.')} />
          </div>
        </div>
      </aside>
    </div>
  );
}

function FilterChip({ label, active }: { label: string; active?: boolean }) {
  return (
    <button className={cn('px-3 py-1.5 font-label text-[10px] rounded-full transition-colors font-bold tracking-widest uppercase', active ? 'bg-primary text-on-primary' : 'bg-white text-on-surface-variant border border-outline-variant hover:bg-surface-container-low')}>
      {label}
    </button>
  );
}

function CompactActionButton({ Icon, label, onClick, primary }: { Icon: any; label: string; onClick: () => void; primary?: boolean }) {
  return (
    <button
      onClick={onClick}
      className={cn(
        'h-10 min-w-0 rounded-lg font-bold flex items-center justify-center gap-1.5 transition-all text-[10px] uppercase tracking-widest active:scale-[0.98] px-2',
        primary ? 'bg-primary text-on-primary hover:bg-primary/95 shadow-sm' : 'bg-white border border-outline text-on-surface hover:bg-surface-container-low'
      )}
    >
      <Icon size={14} className="shrink-0" />
      <span className="truncate">{label}</span>
    </button>
  );
}
