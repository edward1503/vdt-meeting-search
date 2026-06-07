import { useEffect, useMemo, useState } from 'react';
import { Activity, Brain, Calendar, CheckSquare, Database, Filter, Search, Sparkles, User, Zap } from 'lucide-react';
import { motion } from 'motion/react';

const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://127.0.0.1:8000';
const SEARCH_METHODS = [
  { value: 'embedding', label: 'Semantic' },
  { value: 'rule_expansion', label: 'Rules' },
  { value: 'hyde_template', label: 'HyDE' },
  { value: 'multi_query_rrf', label: 'Multi-query' },
  { value: 'hybrid_rrf', label: 'Hybrid' },
  { value: 'llm_query_expansion', label: 'LLM expand' },
  { value: 'llm_hyde', label: 'LLM HyDE' },
  { value: 'llm_multi_query_rrf', label: 'LLM RRF' },
];

interface Snippet {
  chunk_id: string;
  score: number;
  speakers: string[];
  time_start?: number | null;
  time_end?: number | null;
  text: string;
}

interface SearchResult {
  meeting_id: string;
  title: string;
  date?: string | null;
  participants: string[];
  score: number;
  snippets: Snippet[];
}

interface SearchResponse {
  query: string;
  top_k: number;
  method: string;
  results: SearchResult[];
  latency_ms: number;
}

export default function SearchView() {
  const [query, setQuery] = useState('meetings about battery life and power consumption');
  const [speaker, setSpeaker] = useState('');
  const [method, setMethod] = useState('embedding');
  const [data, setData] = useState<SearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showAiChat, setShowAiChat] = useState(false);

  const visibleResults = data?.results ?? [];
  const topScore = useMemo(() => visibleResults[0]?.score ?? 0, [visibleResults]);

  async function runSearch(nextQuery = query) {
    if (!nextQuery.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE}/search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: nextQuery, top_k: 10, speaker: speaker.trim() || null, method }),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail ?? 'Search failed');
      setData(payload);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Search failed');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    runSearch('meetings about battery life and power consumption');
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="h-full flex flex-col bg-background/50">
      <form
        onSubmit={(event) => {
          event.preventDefault();
          runSearch();
        }}
        className="px-8 py-4 bg-surface-container-low/50 border-b border-border-subtle flex items-center gap-4 sticky top-0 z-20 backdrop-blur-md"
      >
        <div className="flex-1 relative group">
          <Zap className="absolute left-4 top-1/2 -translate-y-1/2 text-primary w-5 h-5 group-focus-within:animate-pulse transition-all" />
          <input
            className="w-full bg-surface-container border border-border-subtle rounded-2xl pl-12 pr-4 py-3 text-on-surface focus:ring-1 focus:ring-primary focus:border-primary/50 transition-all text-lg outline-none"
            placeholder="Ask AMI meetings in natural language..."
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
        </div>
        <div className="hidden xl:flex items-center gap-2 bg-surface-container border border-border-subtle rounded-xl px-3 py-2">
          <User className="w-4 h-4 text-primary" />
          <input
            className="w-36 bg-transparent outline-none text-xs font-bold text-on-surface placeholder:text-on-surface-variant/50"
            placeholder="speaker filter"
            value={speaker}
            onChange={(event) => setSpeaker(event.target.value)}
          />
        </div>
        <select
          className="bg-surface-container border border-border-subtle rounded-xl px-4 py-3 text-xs font-black uppercase tracking-wider text-on-surface outline-none"
          value={method}
          onChange={(event) => setMethod(event.target.value)}
        >
          {SEARCH_METHODS.map((item) => (
            <option key={item.value} value={item.value}>{item.label}</option>
          ))}
        </select>
        <button className="px-5 py-3 bg-primary-container text-white rounded-xl flex items-center gap-2 hover:opacity-90 transition-all active:scale-95 text-xs font-bold uppercase tracking-wider shadow-lg">
          <Search className="w-4 h-4" />
          Search
        </button>
      </form>

      <header className="px-8 py-6 flex flex-col gap-4 bg-surface-container-low border-b border-border-subtle">
        <div className="flex items-end justify-between gap-6">
          <div>
            <h1 className="text-3xl font-bold text-on-surface flex items-center gap-3 flex-wrap">
              <span className="text-on-surface-variant font-normal">Results for:</span>
              <span className="italic tracking-tight">"{data?.query ?? query}"</span>
            </h1>
            <p className="text-on-surface-variant text-sm mt-1 opacity-70">
              {loading ? 'Searching FAISS index...' : `${visibleResults.length} AMI meetings returned${data ? ` in ${data.latency_ms} ms with ${data.method}` : ''}.`}
            </p>
          </div>
          <div className="flex gap-2">
            <div className="px-5 py-2.5 bg-surface-elevated border border-border-subtle rounded-xl text-on-surface flex items-center gap-2 text-xs font-bold uppercase tracking-wider">
              <Database className="w-4 h-4 text-primary" />
              171 meetings
            </div>
            <div className="px-5 py-2.5 bg-primary-container text-white rounded-xl flex items-center gap-2 text-xs font-bold uppercase tracking-wider shadow-lg">
              <Activity className="w-4 h-4" />
              Top {topScore.toFixed(3)}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-4 flex-wrap">
          <span className="text-[10px] font-bold text-on-surface-variant uppercase tracking-[0.2em] border-r border-border-subtle pr-4">Understood as</span>
          {[
            { icon: Database, label: 'Source: AMI Corpus' },
            { icon: Brain, label: 'Embedding: all-MiniLM-L6-v2' },
            { icon: Sparkles, label: `Method: ${data?.method ?? method}` },
          ].map((tag) => (
            <span key={tag.label} className="px-3 py-1 bg-surface-container-high rounded-full text-[11px] font-bold flex items-center gap-2 border border-border-subtle text-on-surface shadow-sm">
              <tag.icon className="w-3.5 h-3.5 text-primary" />
              {tag.label}
            </span>
          ))}
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">
        <aside className="w-72 border-r border-border-subtle p-8 flex flex-col gap-10 bg-surface/50 overflow-y-auto custom-scrollbar hidden lg:flex">
          <div className="flex justify-between items-center group">
            <h3 className="text-[10px] font-black text-primary uppercase tracking-[0.2em]">Filters</h3>
            <button onClick={() => setSpeaker('')} className="text-[9px] text-on-surface-variant hover:text-primary uppercase font-black underline underline-offset-4 transition-colors">Reset</button>
          </div>
          <section className="space-y-4">
            <h4 className="text-[11px] font-black text-on-surface uppercase tracking-widest flex items-center gap-2">
              <Database className="w-3.5 h-3.5 text-primary" /> Data source
            </h4>
            <label className="flex items-center gap-3 cursor-pointer group">
              <input defaultChecked className="h-4 w-4 accent-primary-container" type="checkbox" />
              <span className="text-sm text-on-surface-variant group-hover:text-on-surface transition-colors font-medium">AMI manual annotations</span>
            </label>
          </section>
          <section className="space-y-4">
            <h4 className="text-[11px] font-black text-on-surface uppercase tracking-widest flex items-center gap-2">
              <Filter className="w-3.5 h-3.5 text-primary" /> Quick prompts
            </h4>
            {[
              'prototype design evaluation and testing',
              'discussion about LCD display and screen design',
              'meetings about market research and customer needs',
              'industrial designer talking about shape and casing',
            ].map((prompt) => (
              <button
                key={prompt}
                onClick={() => {
                  setQuery(prompt);
                  runSearch(prompt);
                }}
                className="w-full text-left px-3 py-2 rounded-xl bg-surface-container-highest text-on-surface border border-border-subtle hover:border-primary/50 text-[11px] font-bold transition-all"
              >
                {prompt}
              </button>
            ))}
          </section>
          <div className="flex items-center gap-2 mt-auto p-3 bg-match-high/5 rounded-xl border border-match-high/20">
            <CheckSquare className="text-match-high w-4 h-4 shrink-0" />
            <span className="text-on-surface-variant text-[11px] font-bold leading-tight">Semantic chunks grouped by meeting</span>
          </div>
        </aside>

        <section className="flex-1 overflow-y-auto p-8 custom-scrollbar">
          <div className="max-w-4xl mx-auto flex flex-col gap-6">
            {error && <div className="glass-panel p-5 rounded-2xl text-error font-bold">{error}</div>}
            {!error && !loading && visibleResults.length === 0 && (
              <div className="glass-panel p-7 rounded-2xl text-on-surface-variant font-bold">No meetings found.</div>
            )}
            {visibleResults.map((result, index) => (
              <motion.article
                key={result.meeting_id}
                initial={{ opacity: 0, y: 30 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: index * 0.04, duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
                className="glass-panel p-7 rounded-2xl hover:bg-white transition-all duration-300 group relative overflow-hidden active:scale-[0.99] hover:shadow-[0_20px_50px_-12px_rgba(0,0,0,0.08)]"
              >
                <div className="absolute top-0 left-0 w-1 h-full bg-primary-container opacity-0 group-hover:opacity-100 transition-opacity"></div>
                <div className="flex justify-between items-start mb-4 gap-6">
                  <div className="flex flex-col gap-2 min-w-0">
                    <div className="flex items-center gap-3">
                      <span className="px-2 py-0.5 bg-surface-container-highest text-[9px] font-black tracking-widest text-primary rounded ring-1 ring-primary/20">{result.meeting_id}</span>
                      <span className="px-2 py-0.5 bg-blue-900/10 text-blue-500 text-[9px] font-black tracking-widest rounded border border-blue-900/20">AMI</span>
                    </div>
                    <h2 className="text-xl font-bold text-on-surface group-hover:text-primary transition-colors leading-tight">{result.title}</h2>
                    <div className="flex items-center gap-4 text-on-surface-variant text-[11px] font-bold">
                      <span className="flex items-center gap-1.5"><Calendar className="w-3.5 h-3.5" /> {result.date ?? 'No date'}</span>
                      <span className="flex items-center gap-1.5 opacity-60"><User className="w-3.5 h-3.5" /> {result.participants.slice(0, 4).join(', ') || 'AMI speakers'}</span>
                    </div>
                  </div>
                  <div className="px-4 py-1.5 bg-match-high/10 border border-match-high/30 rounded-full flex items-center gap-2 shrink-0">
                    <span className="text-match-high font-black italic font-mono text-sm tracking-tighter">{result.score.toFixed(3)}</span>
                    <span className="text-match-high text-[10px] font-black uppercase tracking-widest">Score</span>
                  </div>
                </div>

                <div className="space-y-3">
                  {result.snippets.slice(0, 2).map((snippet) => (
                    <div key={snippet.chunk_id} className="bg-surface-container-lowest border-l-4 border-primary-container p-5 rounded-r-2xl relative overflow-hidden">
                      <div className="flex items-center gap-3 mb-3 text-[10px] font-black text-on-surface-variant uppercase tracking-[0.18em]">
                        <span>{snippet.chunk_id}</span>
                        <span>score {snippet.score.toFixed(3)}</span>
                        {snippet.speakers.length > 0 && <span>{snippet.speakers.slice(0, 3).join(', ')}</span>}
                      </div>
                      <p className="text-on-surface-variant font-mono text-[13px] leading-relaxed" dangerouslySetInnerHTML={{ __html: highlightText(snippet.text, data?.query ?? query) }} />
                    </div>
                  ))}
                </div>
              </motion.article>
            ))}
          </div>
        </section>
      </div>

      <div className="fixed bottom-10 right-10 flex flex-col items-end gap-5 z-50">
        {showAiChat && (
          <motion.div initial={{ opacity: 0, scale: 0.9, y: 20 }} animate={{ opacity: 1, scale: 1, y: 0 }} className="glass-panel p-5 rounded-2xl max-w-xs shadow-2xl mb-2 border-primary/30">
            <p className="text-sm font-semibold text-on-surface leading-relaxed">
              Current MVP retrieves semantic AMI meeting chunks with FAISS. Hybrid BM25 and richer metadata filters can be added next.
            </p>
          </motion.div>
        )}
        <button onClick={() => setShowAiChat(!showAiChat)} className="w-16 h-16 bg-primary-container text-white rounded-full shadow-[0_10px_30px_rgba(238,0,51,0.4)] flex items-center justify-center hover:scale-110 active:scale-95 transition-all">
          <Brain className="w-8 h-8" />
        </button>
      </div>
    </div>
  );
}

function highlightText(text: string, rawQuery: string) {
  const escaped = escapeHtml(text);
  const stopwords = new Set(['about', 'with', 'and', 'the', 'for', 'from', 'that', 'this', 'meetings', 'discussion']);
  const terms = [...new Set(rawQuery.toLowerCase().match(/[a-z0-9]{3,}/g) ?? [])]
    .filter((term) => !stopwords.has(term))
    .sort((a, b) => b.length - a.length);
  if (!terms.length) return escaped;
  const pattern = new RegExp(`\\b(${terms.map(escapeRegex).join('|')})\\b`, 'gi');
  return escaped.replace(pattern, '<mark>$1</mark>');
}

function escapeHtml(value: string) {
  return value.replace(/[&<>'"]/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[char] ?? char));
}

function escapeRegex(value: string) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

