import { useEffect, useMemo, useState } from 'react';
import { Clock, RotateCcw, Trash2, Search, FileText, Database } from 'lucide-react';
import { clearHistory, getHistory, type HistoryEntry } from '@/src/lib/api';
import type { SearchPreset } from '@/src/types';
import { cn } from '@/src/lib/utils';

interface HistoryViewProps {
  onRunAgain: (preset: SearchPreset) => void;
}

export function HistoryView({ onRunAgain }: HistoryViewProps) {
  const [rows, setRows] = useState<HistoryEntry[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [filter, setFilter] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function loadHistory() {
    setIsLoading(true);
    setError(null);
    try {
      const history = await getHistory(200);
      setRows(history);
      setSelectedId((current) => current ?? history[0]?.id ?? null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load query history');
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    loadHistory();
  }, []);

  const filteredRows = useMemo(() => {
    const value = filter.trim().toLowerCase();
    if (!value) return rows;
    return rows.filter((row) =>
      row.query.toLowerCase().includes(value) ||
      (row.dataset_id ?? 'hotpotqa').toLowerCase().includes(value) ||
      row.method.toLowerCase().includes(value) ||
      row.top_docs.some((doc) => doc.doc_id.toLowerCase().includes(value) || doc.title.toLowerCase().includes(value)) ||
      row.support_doc_ids.some((doc) => doc.toLowerCase().includes(value))
    );
  }, [filter, rows]);

  const selected = filteredRows.find((row) => row.id === selectedId) ?? filteredRows[0] ?? null;

  async function handleClear() {
    await clearHistory();
    setRows([]);
    setSelectedId(null);
  }

  return (
    <div className="h-full flex overflow-hidden animate-in fade-in duration-500">
      <section className="flex-1 flex flex-col border-r border-outline-variant bg-white min-w-0">
        <div className="p-8 border-b border-outline-variant bg-white space-y-4">
          <div className="flex items-center justify-between gap-4">
            <div>
              <h3 className="font-headline text-4xl font-extrabold text-on-surface">Query History</h3>
              <p className="text-on-surface-variant mt-1 font-medium">Review search runs, modes, top-k, retrieved docs, and gold support labels.</p>
            </div>
            <div className="flex items-center gap-3">
              <button onClick={loadHistory} className="h-11 px-4 border border-outline-variant rounded-lg font-bold text-xs uppercase tracking-widest hover:bg-surface-container-low flex items-center gap-2">
                <RotateCcw size={16} /> Refresh
              </button>
              <button onClick={handleClear} className="h-11 px-4 bg-primary text-on-primary rounded-lg font-bold text-xs uppercase tracking-widest hover:opacity-90 flex items-center gap-2">
                <Trash2 size={16} /> Clear
              </button>
            </div>
          </div>
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-outline" size={18} />
            <input
              value={filter}
              onChange={(event) => setFilter(event.target.value)}
              className="w-full pl-10 pr-4 py-2 bg-surface-container-low border border-outline-variant rounded-lg focus:ring-2 focus:ring-primary focus:border-primary transition-all font-sans text-on-surface outline-none placeholder:text-outline"
              placeholder="Filter query, method, doc id, or support doc..."
              type="text"
            />
          </div>
        </div>

        <div className="flex-1 overflow-y-auto custom-scrollbar">
          {isLoading && <div className="p-8 text-on-surface-variant font-bold">Loading history...</div>}
          {error && <div className="p-8 text-primary font-bold">{error}</div>}
          {!isLoading && !error && filteredRows.length === 0 && <div className="p-8 text-on-surface-variant font-bold">No saved searches yet.</div>}
          {!isLoading && !error && filteredRows.length > 0 && (
            <table className="w-full border-collapse text-left">
              <thead className="sticky top-0 bg-white border-b border-outline-variant z-10">
                <tr>
                  <Header label="Time" />
                  <Header label="Query" />
                  <Header label="Mode" />
                  <Header label="Top-k" />
                  <Header label="Docs" />
                  <Header label="Support" />
                </tr>
              </thead>
              <tbody className="divide-y divide-outline-variant/10">
                {filteredRows.map((row) => (
                  <tr
                    key={row.id}
                    onClick={() => setSelectedId(row.id)}
                    className={cn('cursor-pointer hover:bg-surface-container-low transition-colors', selected?.id === row.id && 'bg-primary/[0.04] border-l-4 border-primary')}
                  >
                    <td className="px-6 py-4 font-mono text-[10px] text-on-surface-variant whitespace-nowrap">{formatDate(row.created_at)}</td>
                    <td className="px-6 py-4 text-sm text-on-surface font-medium max-w-xl truncate">
                      <span className="mr-2 px-2 py-0.5 bg-surface-container-high text-on-surface-variant font-mono text-[9px] rounded font-bold uppercase">
                        {(row.dataset_id ?? 'hotpotqa').toUpperCase()}
                      </span>
                      {row.query}
                    </td>
                    <td className="px-6 py-4"><MethodBadge method={row.method} /></td>
                    <td className="px-6 py-4 font-mono text-xs font-bold">{row.top_k}</td>
                    <td className="px-6 py-4 font-mono text-xs font-bold">{row.result_count}</td>
                    <td className="px-6 py-4 font-mono text-xs font-bold text-primary">{row.support_doc_ids.length}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </section>

      <aside className="w-[520px] bg-white flex flex-col shadow-[-4px_0_24px_rgba(0,0,0,0.04)] z-10">
        {selected ? (
          <>
            <div className="p-8 border-b border-outline-variant space-y-4">
              <div className="flex items-center justify-between gap-4">
                <div className="flex items-center gap-3">
                  <Clock className="text-primary" size={22} />
                  <h2 className="font-headline text-2xl font-bold text-on-surface">Run #{selected.id}</h2>
                </div>
                <button
                  onClick={() => onRunAgain({ id: selected.id, datasetId: selected.dataset_id ?? 'hotpotqa', query: selected.query, method: selected.method, topK: selected.top_k })}
                  className="h-11 px-4 bg-primary text-on-primary rounded-lg font-bold text-xs uppercase tracking-widest hover:opacity-90 flex items-center gap-2"
                >
                  <RotateCcw size={16} /> Run again
                </button>
              </div>
              <div className="grid grid-cols-5 gap-2">
                <Metric label="Mode" value={selected.method} />
                <Metric label="Dataset" value={(selected.dataset_id ?? 'hotpotqa').toUpperCase()} />
                <Metric label="Top-k" value={String(selected.top_k)} />
                <Metric label="Latency" value={`${Math.round(selected.latency_ms)}ms`} />
                <Metric label="Cache" value={selected.cache_hit ? 'Hit' : 'Miss'} />
              </div>
            </div>

            <div className="flex-1 overflow-y-auto p-8 custom-scrollbar space-y-8">
              <section className="space-y-3">
                <Label label="Query" />
                <div className="bg-surface-container-low p-5 rounded-xl border-l-[6px] border-primary text-on-surface font-medium leading-relaxed">{selected.query}</div>
              </section>

              <section className="space-y-3">
                <Label label="Supported Docs" />
                {selected.support_doc_ids.length > 0 ? (
                  <div className="flex flex-wrap gap-2">
                    {selected.support_doc_ids.map((doc) => (
                      <span key={doc} className="px-3 py-2 bg-primary/10 text-primary border border-primary/20 rounded-lg font-mono text-xs font-bold">{doc}</span>
                    ))}
                  </div>
                ) : (
                  <div className="text-sm text-on-surface-variant bg-surface-container-low rounded-xl p-4">No gold support docs matched for this free-form query.</div>
                )}
              </section>

              <section className="space-y-3">
                <Label label="Top Retrieved Documents" />
                <div className="space-y-3">
                  {selected.top_docs.map((doc) => (
                    <div key={`${selected.id}-${doc.rank}-${doc.doc_id}`} className="border border-outline-variant rounded-xl p-4 bg-white">
                      <div className="flex items-center gap-2 mb-2">
                        <span className="px-2 py-0.5 bg-primary text-on-primary rounded font-mono text-[10px] font-black">#{doc.rank}</span>
                        <span className="font-mono text-[10px] text-on-surface-variant">{doc.doc_id}</span>
                        <span className="ml-auto font-mono text-[10px] text-primary font-bold">{doc.score.toFixed(4)}</span>
                      </div>
                      <p className="font-bold text-on-surface">{doc.title || doc.doc_id}</p>
                    </div>
                  ))}
                </div>
              </section>
            </div>
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center text-on-surface-variant font-bold p-8 text-center">
            <div>
              <Database className="mx-auto mb-4 text-primary/40" size={48} />
              Search history will appear after you run queries.
            </div>
          </div>
        )}
      </aside>
    </div>
  );
}

function Header({ label }: { label: string }) {
  return <th className="px-6 py-4 font-label text-[10px] text-on-surface-variant font-bold uppercase tracking-widest">{label}</th>;
}

function Label({ label }: { label: string }) {
  return <div className="font-label text-[10px] text-outline uppercase tracking-[0.2em] font-bold flex items-center gap-2"><FileText size={14} /> {label}</div>;
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-surface-container-low rounded-lg p-3 border border-outline-variant/40">
      <div className="font-label text-[9px] text-on-surface-variant uppercase tracking-widest font-bold mb-1">{label}</div>
      <div className="font-mono text-xs font-black text-on-surface truncate">{value}</div>
    </div>
  );
}

function MethodBadge({ method }: { method: string }) {
  const isHybrid = method.includes('hybrid');
  return (
    <span className={cn('px-3 py-1 rounded font-mono text-[10px] font-black uppercase tracking-widest', isHybrid ? 'bg-primary/10 text-primary' : 'bg-surface-container-high text-on-surface-variant')}>
      {method}
    </span>
  );
}

function formatDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}
