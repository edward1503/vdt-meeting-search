import { DescriptionIcon, Hub, Bolt, Route, ExportNotes, Search, MoreVert } from '@/src/components/Icons';
import { useEffect, useMemo, useState } from 'react';
import { Query } from '@/src/types';
import { cn } from '@/src/lib/utils';
import { getQueries, searchHotpotQA } from '@/src/lib/api';

export function QueriesView() {
  const [queries, setQueries] = useState<Query[]>([]);
  const [selectedQuery, setSelectedQuery] = useState<Query | null>(null);
  const [filter, setFilter] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [runState, setRunState] = useState<string | null>(null);

  useEffect(() => {
    getQueries()
      .then((rows) => {
        setQueries(rows);
        setSelectedQuery(rows[0] ?? null);
      })
      .catch((err) => setError(err instanceof Error ? err.message : 'Could not load queries'))
      .finally(() => setIsLoading(false));
  }, []);

  const filteredQueries = useMemo(() => {
    const value = filter.trim().toLowerCase();
    if (!value) return queries;
    return queries.filter((query) =>
      query.id.toLowerCase().includes(value) ||
      query.text.toLowerCase().includes(value) ||
      query.docs.some((doc) => doc.toLowerCase().includes(value))
    );
  }, [filter, queries]);

  async function runSelectedSearch(method = 'es_hybrid') {
    if (!selectedQuery) return;
    setRunState('Running search...');
    try {
      const result = await searchHotpotQA(selectedQuery.text, method, 10);
      setRunState(`Retrieved ${result.results.length} docs in ${Math.round(result.latency_ms)}ms`);
    } catch (err) {
      setRunState(err instanceof Error ? err.message : 'Search failed');
    }
  }

  return (
    <div className="h-full flex overflow-hidden animate-in fade-in duration-500">
      <section className="flex-1 flex flex-col border-r border-outline-variant bg-white min-w-0">
        <div className="p-8 border-b border-outline-variant bg-white">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-outline" size={18} />
            <input
              value={filter}
              onChange={(event) => setFilter(event.target.value)}
              className="w-full pl-10 pr-4 py-2 bg-surface-container-low border border-outline-variant rounded-lg focus:ring-2 focus:ring-primary focus:border-primary transition-all font-sans text-on-surface outline-none placeholder:text-outline"
              placeholder="Filter query text or doc id..."
              type="text"
            />
          </div>
          <div className="flex items-center justify-between mt-4">
            <div className="flex space-x-2">
              <FilterChip label="ALL QUERIES" active />
              <FilterChip label="PROCESSED" />
            </div>
            <span className="font-mono text-[10px] text-outline uppercase tracking-widest font-bold">Showing {filteredQueries.length} of {queries.length}</span>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto custom-scrollbar">
          {error && <div className="p-8 text-primary font-bold">{error}</div>}
          {isLoading && <div className="p-8 text-on-surface-variant font-bold">Loading queries...</div>}
          {!isLoading && !error && (
            <table className="w-full border-collapse text-left">
              <thead className="sticky top-0 bg-white border-b border-outline-variant z-10">
                <tr>
                  <th className="px-8 py-4 font-label text-[10px] text-on-surface-variant font-bold uppercase tracking-widest w-32">Query ID</th>
                  <th className="px-8 py-4 font-label text-[10px] text-on-surface-variant font-bold uppercase tracking-widest">Query Text</th>
                  <th className="px-8 py-4 font-label text-[10px] text-on-surface-variant font-bold uppercase tracking-widest w-48">Supported Docs</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-outline-variant/10">
                {filteredQueries.map((q) => (
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
      </section>

      <aside className="w-[500px] bg-white flex flex-col shadow-[-4px_0_24px_rgba(0,0,0,0.04)] z-10">
        <div className="p-8 border-b border-outline-variant flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <Bolt className="text-primary" size={20} />
            <h2 className="font-headline text-xl font-bold text-on-surface">Query Preview</h2>
          </div>
          <button className="p-2 hover:bg-surface-container-low rounded-full transition-colors">
            <MoreVert size={20} />
          </button>
        </div>

        {selectedQuery ? (
          <div className="flex-1 overflow-y-auto p-8 custom-scrollbar space-y-10">
            <div className="space-y-4">
              <span className="font-label text-[10px] text-outline uppercase tracking-[0.2em] font-bold">Metadata</span>
              <div className="flex items-center space-x-2">
                <div className="font-mono text-2xl text-primary font-bold">{selectedQuery.id}</div>
                <span className="px-2 py-0.5 bg-surface-container text-on-surface-variant font-mono text-[9px] rounded font-bold uppercase">HOTPOTQA</span>
              </div>
            </div>

            <div className="space-y-4">
              <span className="font-label text-[10px] text-outline uppercase tracking-[0.2em] font-bold">Natural Language Query</span>
              <div className="bg-surface-container-low p-6 rounded-xl border-l-[6px] border-primary">
                <p className="text-lg text-on-surface leading-relaxed italic font-medium">{selectedQuery.text}</p>
              </div>
            </div>

            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <span className="font-label text-[10px] text-outline uppercase tracking-[0.2em] font-bold">Gold Documents</span>
                <span className="font-mono text-[10px] bg-primary/10 px-2 py-0.5 rounded text-primary font-bold uppercase">{selectedQuery.docs.length} DOCS</span>
              </div>
              <div className="space-y-3">
                {selectedQuery.docs.map((doc) => (
                  <div key={doc} className="flex items-start space-x-4 p-4 bg-white border border-outline-variant rounded-xl hover:border-primary/40 transition-all cursor-pointer">
                    <div className="w-8 h-8 rounded bg-primary/10 flex items-center justify-center shrink-0">
                      <DescriptionIcon className="text-primary" size={16} />
                    </div>
                    <div>
                      <p className="font-mono text-sm font-bold text-on-surface">{doc}</p>
                      <p className="text-xs text-on-surface-variant mt-1 leading-relaxed line-clamp-2">Gold support document from HotpotQA qrels.</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="space-y-4">
              <span className="font-label text-[10px] text-outline uppercase tracking-[0.2em] font-bold">Retrieved Context Map</span>
              <div className="bg-surface-container-high rounded-xl h-48 relative overflow-hidden flex items-center justify-center border border-outline-variant/30">
                <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,_var(--tw-gradient-stops))] from-primary/5 via-transparent to-transparent opacity-50" />
                <div className="relative z-10 flex flex-col items-center">
                  <Hub className="text-primary/40 mb-2" size={40} />
                  <span className="font-mono text-[9px] font-bold text-primary tracking-[0.25em] uppercase">2-Hop Knowledge Graph View</span>
                </div>
              </div>
            </div>
          </div>
        ) : (
          <div className="flex-1 p-8 text-on-surface-variant font-bold">No query selected.</div>
        )}

        <div className="p-8 border-t border-outline-variant bg-white space-y-3 shadow-[0_-4px_12px_rgba(0,0,0,0.02)]">
          {runState && <div className="text-xs font-mono text-primary font-bold uppercase tracking-widest">{runState}</div>}
          <button onClick={() => runSelectedSearch('es_hybrid')} className="w-full py-4 bg-primary text-on-primary rounded-xl font-bold flex items-center justify-center space-x-3 hover:bg-primary/95 transition-all shadow-md active:scale-[0.98]">
            <Bolt size={20} />
            <span className="font-label text-xs tracking-[0.2em] uppercase">Run Hybrid Search</span>
          </button>
          <div className="grid grid-cols-2 gap-3">
            <ActionButton Icon={Route} label="Iterative" onClick={() => runSelectedSearch('es_iterative_hybrid')} />
            <ActionButton Icon={ExportNotes} label="Export" onClick={() => setRunState('Export uses the loaded API query set.')} />
          </div>
        </div>
      </aside>
    </div>
  );
}

function FilterChip({ label, active }: { label: string; active?: boolean }) {
  return (
    <button className={cn('px-4 py-1.5 font-label text-[10px] rounded-full transition-colors font-bold tracking-widest uppercase', active ? 'bg-primary text-on-primary' : 'bg-white text-on-surface-variant border border-outline-variant hover:bg-surface-container-low')}>
      {label}
    </button>
  );
}

function ActionButton({ Icon, label, onClick }: { Icon: any; label: string; onClick: () => void }) {
  return (
    <button onClick={onClick} className="py-3 bg-white border border-outline text-on-surface font-bold rounded-lg flex items-center justify-center space-x-2 hover:bg-surface-container-low transition-all text-xs uppercase tracking-widest">
      <Icon size={14} />
      <span>{label}</span>
    </button>
  );
}
