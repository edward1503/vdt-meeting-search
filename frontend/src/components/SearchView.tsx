import { useEffect, useRef, useState, type ReactNode } from 'react';
import { Search, UnfoldMore, Verified, Bolt, KeyboardDoubleArrowDown } from '@/src/components/Icons';
import { cn } from '@/src/lib/utils';
import { searchDataset, type SearchResult, type SearchResponse, type SearchSupportSummary } from '@/src/lib/api';
import type { DatasetProfile, SearchPreset } from '@/src/types';

const HOTPOTQA_SUGGESTIONS = [
  'What occupations do both Ian Hunter and Rob Thomas have?',
  'The Death of Cook depicts the death of James Cook at a bay on what coast?',
];

const VIMQA_SUGGESTIONS = [
  'Hà Nội là thủ đô của nước nào?',
  'Việt Nam có thủ đô nào?',
];

const METHOD_LABELS: Record<string, string> = {
  tv_hybrid: 'TurboVec Hybrid RRF (Full Dense + BM25)',
  tv_dense: 'TurboVec Dense (Vector Only)',
  tv_filtered_hybrid: 'Filtered TurboVec Hybrid',
  es_bm25: 'Standard BM25 (Keyword Only)',
  es_dense: 'Elasticsearch Dense Vector',
  es_hybrid: 'Elasticsearch Hybrid RRF',
};

const FALLBACK_METHODS = ['tv_hybrid', 'tv_dense', 'tv_filtered_hybrid', 'es_bm25'];

function methodOptions(methods?: string[]) {
  return (methods && methods.length ? methods : FALLBACK_METHODS).map((value) => ({
    value,
    label: METHOD_LABELS[value] ?? value,
  }));
}

export function SearchView({ dataset, preset }: { dataset: DatasetProfile | null; preset?: SearchPreset | null }) {
  const suggestions = dataset?.id === 'vimqa' ? VIMQA_SUGGESTIONS : HOTPOTQA_SUGGESTIONS;
  const [query, setQuery] = useState(HOTPOTQA_SUGGESTIONS[0]);
  const [queryId, setQueryId] = useState<string | undefined>(undefined);
  const [availableMethods, setAvailableMethods] = useState<string[]>(FALLBACK_METHODS);
  const [method, setMethod] = useState('tv_hybrid');
  const [topK, setTopK] = useState(10);
  const [response, setResponse] = useState<SearchResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const lastAutoRunKey = useRef<string | null>(null);

  useEffect(() => {
    const methods = dataset?.methods?.length ? dataset.methods : FALLBACK_METHODS;
    setAvailableMethods(methods);
    setMethod(methods.includes(dataset?.default_method ?? '') ? dataset!.default_method : methods[0] ?? 'es_bm25');
    setQuery(suggestions[0]);
    setQueryId(undefined);
    setResponse(null);
    setError(null);
  }, [dataset?.id]);

  useEffect(() => {
    if (!preset) return;
    const nextMethod = availableMethods.includes(preset.method) ? preset.method : availableMethods[0] ?? 'tv_hybrid';
    setQuery(preset.query);
    setQueryId(preset.queryId);
    setMethod(nextMethod);
    setTopK(preset.topK);
    setResponse(null);
    setError(null);

    if (preset.autoRun) {
      const runKey = `${preset.datasetId ?? dataset?.id ?? ''}:${preset.id ?? ''}:${preset.queryId ?? preset.query}:${nextMethod}:${preset.topK}`;
      if (lastAutoRunKey.current !== runKey) {
        lastAutoRunKey.current = runKey;
        runSearch(preset.query, preset.queryId, nextMethod, preset.topK);
      }
    }
  }, [availableMethods, preset]);

  async function runSearch(nextQuery = query, nextQueryId = queryId, nextMethod = method, nextTopK = topK) {
    const trimmed = nextQuery.trim();
    if (!trimmed) return;
    if (!dataset) {
      setError('Dataset profile is not loaded yet');
      return;
    }

    setIsLoading(true);
    setError(null);
    try {
      const payload = await searchDataset(dataset.id, trimmed, nextMethod, nextTopK, nextQueryId);
      setResponse(payload);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Search failed');
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div className="w-full space-y-6 animate-in fade-in duration-700">
      <section className="space-y-4">
        <div className="relative group">
          <input
            className="w-full h-16 pl-14 pr-44 bg-white border-2 border-outline-variant rounded-2xl font-headline text-lg text-on-surface focus:ring-4 focus:ring-primary/10 focus:border-primary shadow-sm transition-all outline-none"
            placeholder="Enter a complex retrieval query..."
            type="text"
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              setQueryId(undefined);
            }}
            onKeyDown={(event) => {
              if (event.key === 'Enter') runSearch();
            }}
          />
          <div className="absolute left-5 top-1/2 -translate-y-1/2 text-on-surface-variant/40 group-focus-within:text-primary transition-colors">
            <Search size={28} />
          </div>
          <div className="absolute right-3 top-1/2 -translate-y-1/2">
            <button
              onClick={() => runSearch()}
              disabled={isLoading}
              className="h-10 px-6 bg-primary text-on-primary rounded-lg font-headline text-xs uppercase tracking-widest font-black hover:shadow-lg transition-all active:scale-[0.98] disabled:opacity-60"
            >
              {isLoading ? 'Searching' : 'Search Results'}
            </button>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-3 px-2">
          <span className="text-on-surface-variant font-label text-xs uppercase tracking-widest font-bold opacity-60">Suggested:</span>
          {suggestions.map((suggestion) => (
            <SuggestionChip
              key={suggestion}
              label={suggestion}
              onClick={() => {
                setQuery(suggestion);
                setQueryId(undefined);
                runSearch(suggestion, undefined);
              }}
            />
          ))}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 p-4 bg-surface-container-low/50 rounded-2xl border border-outline-variant shadow-inner">
          <ControlItem label="Retrieval Methodology">
            <select
              value={method}
              onChange={(event) => setMethod(event.target.value)}
              className="w-full bg-white border border-outline-variant rounded-lg px-3 py-2.5 text-xs font-bold focus:ring-2 focus:ring-primary outline-none appearance-none cursor-pointer font-mono tracking-tight"
            >
              {methodOptions(availableMethods).map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
            </select>
            <UnfoldMore className="absolute right-3 top-[2.65rem] pointer-events-none text-on-surface-variant" size={16} />
          </ControlItem>

          <ControlItem label="Top-k Results">
            <select
              value={topK}
              onChange={(event) => setTopK(Number(event.target.value))}
              className="w-full bg-white border border-outline-variant rounded-lg px-3 py-2.5 text-xs font-bold focus:ring-2 focus:ring-primary outline-none appearance-none cursor-pointer font-mono tracking-tight"
            >
              <option value={10}>10 Documents</option>
              <option value={5}>5 Documents</option>
              <option value={25}>25 Documents</option>
            </select>
            <UnfoldMore className="absolute right-3 top-[2.65rem] pointer-events-none text-on-surface-variant" size={16} />
          </ControlItem>

          <ControlItem label="Cache Policy">
            <div className="flex items-center gap-4 h-10">
              <div className="h-2 flex-1 bg-primary/20 rounded-full overflow-hidden">
                <div className="h-full w-3/4 bg-primary rounded-full" />
              </div>
              <span className="font-mono text-xs bg-on-background text-surface px-3 py-1.5 rounded-lg font-black shadow-lg">Redis TTL</span>
            </div>
          </ControlItem>
        </div>
      </section>

      <section className="space-y-4">
        {response?.support && <SupportCoverage support={response.support} topK={response.top_k} />}

        <div className="flex items-center justify-between pb-3 border-b-4 border-outline-variant/20">
          <div className="flex items-center gap-4">
            <Verified className="text-primary" size={24} />
            <h3 className="font-headline text-2xl font-extrabold text-on-surface">Top Retrieval Matches</h3>
            <p className="text-sm text-on-surface-variant ml-2 border-l-2 pl-4 border-outline-variant/30">
              Found <span className="font-black text-on-surface">{response?.results.length ?? 0} hits</span>
              {response && <> in <span className="font-black text-on-surface">{Math.round(response.latency_ms)}ms</span></>}
            </p>
          </div>
        </div>

        {error && <div className="bg-white border border-primary text-primary rounded-xl p-6 font-bold">{error}</div>}

        <div className="space-y-4">
          {response?.results.map((result) => (
            <ResultCard key={`${result.doc_id}-${result.rank}`} result={result} />
          ))}
          {!response && !error && (
            <div className="bg-white border border-outline-variant rounded-xl p-6 text-on-surface-variant font-medium">
              Run a search to retrieve ranked evidence from the active dataset workspace.
            </div>
          )}
        </div>

        {response && response.results.length >= topK && (
          <div className="flex justify-center py-8">
            <button
              onClick={() => {
                const nextTopK = Math.min(topK + 10, 50);
                setTopK(nextTopK);
                runSearch(query, queryId, method, nextTopK);
              }}
              className="flex items-center gap-3 px-10 py-3 border-2 border-primary text-primary rounded-full font-black uppercase tracking-widest text-xs hover:bg-primary hover:text-on-primary transition-all group shadow-lg active:scale-[0.98]"
            >
              <KeyboardDoubleArrowDown className="transition-transform group-hover:translate-y-1" size={24} />
              Expand Result Depth
            </button>
          </div>
        )}
      </section>
    </div>
  );
}

function SuggestionChip({ label, onClick }: { key?: string; label: string; onClick: () => void }) {
  return (
    <button onClick={onClick} className="px-3 py-1.5 bg-white hover:bg-primary hover:text-on-primary text-on-surface text-xs font-bold rounded-full transition-all border border-outline-variant/30 hover:border-primary shadow-sm">
      {label}
    </button>
  );
}

function ControlItem({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-2 relative">
      <label className="font-label text-[10px] text-on-surface-variant uppercase tracking-widest font-black opacity-70 px-1">{label}</label>
      {children}
    </div>
  );
}

function SupportCoverage({ support, topK }: { support: SearchSupportSummary; topK: number }) {
  const recall = support.recall_at_k === null ? 'N/A' : support.recall_at_k.toFixed(3);
  const missingPreview = support.missing_doc_ids.slice(0, 6);

  return (
    <div className="bg-white border border-outline-variant rounded-xl p-4 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-3">
          <span className="font-label text-[10px] text-on-surface-variant uppercase tracking-widest font-black">Gold Support</span>
          {support.available ? (
            <span className="px-3 py-1 bg-primary/10 text-primary border border-primary/20 rounded font-mono text-[10px] font-black uppercase tracking-widest">
              Found {support.matched_count}/{support.total_count}
            </span>
          ) : (
            <span className="px-3 py-1 bg-surface-container-high text-on-surface-variant rounded font-mono text-[10px] font-black uppercase tracking-widest">
              Unavailable
            </span>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-mono text-[10px] text-on-surface-variant font-bold uppercase tracking-widest">Recall@{topK}</span>
          <span className="font-headline text-xl font-extrabold text-on-surface">{recall}</span>
        </div>
      </div>
      {support.available && support.missing_doc_ids.length > 0 && (
        <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-outline-variant/30 pt-3">
          <span className="font-label text-[10px] text-on-surface-variant uppercase tracking-widest font-bold">Missing</span>
          {missingPreview.map((docId) => (
            <span key={docId} className="px-2 py-1 bg-surface-container-low text-on-surface font-mono text-[10px] rounded border border-outline-variant/40 font-bold">
              {docId}
            </span>
          ))}
          {support.missing_doc_ids.length > missingPreview.length && (
            <span className="font-mono text-[10px] text-on-surface-variant font-bold">+{support.missing_doc_ids.length - missingPreview.length}</span>
          )}
        </div>
      )}
    </div>
  );
}

function ResultCard({ result }: { key?: string; result: SearchResult }) {
  const isTop = result.rank === 1;
  return (
    <article className={cn(
      'bg-white border border-outline-variant rounded-xl p-5 hover:shadow-lg transition-all relative group',
      isTop && 'border-l-8 border-primary'
    )}>
      <div className="flex flex-col gap-3">
        <div className="flex flex-wrap items-center gap-3">
          <span className={cn('px-4 py-1.5 rounded font-mono text-[10px] font-black tracking-widest uppercase', isTop ? 'bg-primary text-on-primary' : 'bg-surface-container-highest text-on-surface-variant')}>RANK {result.rank}</span>
          {result.is_support && <span className="px-4 py-1.5 rounded font-mono text-[10px] font-black tracking-widest uppercase bg-primary/10 text-primary border border-primary/20">Support Hit</span>}
          <span className="px-4 py-1.5 bg-surface-container-high text-on-surface-variant rounded font-mono text-[10px] font-black tracking-widest uppercase">HOP {result.hop}</span>
          <span className="ml-auto font-mono text-[10px] text-on-surface-variant font-bold opacity-40">UID: {result.doc_id}</span>
          <div className={cn('flex items-center gap-2 font-mono text-[10px] px-4 py-1.5 rounded-full font-black uppercase tracking-widest', isTop ? 'bg-primary/10 text-primary' : 'bg-surface-container-high text-on-surface')}>
            <Bolt size={14} /> Score: {result.score.toFixed(4)}
          </div>
        </div>
        <h4 className={cn('font-headline text-2xl font-black transition-colors', isTop ? 'text-primary' : 'text-on-surface group-hover:text-primary')}>{result.title || result.doc_id}</h4>
        <p className="text-sm text-on-surface-variant leading-relaxed max-w-6xl font-normal line-clamp-3">{result.text}</p>
        <div className="flex items-center gap-4 pt-3 border-t border-outline-variant/10">
          <span className="text-[10px] font-mono text-on-surface-variant opacity-40 uppercase tracking-[0.25em] font-black">Source: Wikipedia (en)</span>
          <span className="text-[10px] font-mono text-on-surface-variant opacity-40 uppercase tracking-[0.25em] font-black border-l-2 pl-6 border-outline-variant/10">Method: {result.source}</span>
        </div>
      </div>
    </article>
  );
}
