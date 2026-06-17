import type { BenchmarkResult, Query } from '@/src/types';

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? '/api').replace(/\/$/, '');

export interface SearchResult {
  doc_id: string;
  title: string;
  text: string;
  url: string;
  score: number;
  rank: number;
  source: string;
  hop: number;
  is_support?: boolean;
}

export interface SearchSupportSummary {
  available: boolean;
  support_doc_ids: string[];
  matched_doc_ids: string[];
  missing_doc_ids: string[];
  matched_count: number;
  total_count: number;
  recall_at_k: number | null;
}

export interface SearchResponse {
  query_id?: string | null;
  query: string;
  method: string;
  top_k: number;
  latency_ms: number;
  support?: SearchSupportSummary;
  results: SearchResult[];
}


export interface HistoryDoc {
  doc_id: string;
  title: string;
  score: number;
  rank: number;
}

export interface HistoryEntry {
  id: number;
  created_at: string;
  query: string;
  method: string;
  top_k: number;
  latency_ms: number;
  cache_hit: boolean;
  result_count: number;
  top_docs: HistoryDoc[];
  support_doc_ids: string[];
}
export interface StatsResponse {
  backend: string;
  index: string;
  methods: string[];
  dataset_id?: string;
  embedding_model?: string;
  embedding_service_url?: string;
  num_candidates?: number;
  search_cache_ttl_seconds?: number;
  history_db_path?: string;
  default_search_method?: string;
  turbovec_index_path?: string;
  turbovec_dim?: number;
  turbovec_bit_width?: number;
  runtime_profile?: string;
  corpus_doc_count?: number | null;
}

interface ApiQuery {
  query_id: string;
  query: string;
  support_doc_ids: string[];
  support_doc_count: number;
}

interface ApiBenchmarkResult {
  method: string;
  metrics: Record<string, number>;
}

interface ApiBenchmarkSection {
  title?: string;
  subtitle?: string;
  config?: Record<string, string | number | boolean | string[] | null>;
  results: ApiBenchmarkResult[];
}

interface ApiBenchmarkPayload {
  current?: ApiBenchmarkSection;
  legacy?: ApiBenchmarkSection;
  results?: ApiBenchmarkResult[];
}

export interface BenchmarkSection {
  title: string;
  subtitle: string;
  config: Record<string, string | number | boolean | string[] | null>;
  results: BenchmarkResult[];
}

export interface BenchmarkDashboard {
  current: BenchmarkSection;
  legacy: BenchmarkSection;
}

export interface QueryPage {
  count: number;
  total: number;
  limit: number;
  offset: number;
  queries: Query[];
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json', ...init?.headers },
    ...init,
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `API request failed: ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export async function getHealth(): Promise<{ status: string }> {
  return apiFetch('/health');
}

export async function getStats(): Promise<StatsResponse> {
  return apiFetch('/stats');
}

export async function getQueries({ limit = 10, offset = 0, search = '' }: { limit?: number; offset?: number; search?: string } = {}): Promise<QueryPage> {
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  });
  const trimmedSearch = search.trim();
  if (trimmedSearch) params.set('search', trimmedSearch);

  const payload = await apiFetch<{ count: number; total: number; limit: number; offset: number; queries: ApiQuery[] }>(`/queries?${params.toString()}`);
  return {
    count: payload.count,
    total: payload.total,
    limit: payload.limit,
    offset: payload.offset,
    queries: payload.queries.map((row) => ({
      id: row.query_id,
      text: row.query,
      docs: row.support_doc_ids,
      status: 'processed',
    })),
  };
}

export async function getBenchmark(): Promise<BenchmarkDashboard> {
  const payload = await apiFetch<ApiBenchmarkPayload>('/benchmark');
  const current = payload.current ?? { title: 'Current Benchmark', subtitle: '', config: {}, results: payload.results ?? [] };
  const legacy = payload.legacy ?? { title: 'Legacy Benchmark', subtitle: '', config: {}, results: [] };
  return {
    current: mapBenchmarkSection(current, 'Current Full-Corpus Benchmark'),
    legacy: mapBenchmarkSection(legacy, 'Legacy Nano / Elasticsearch Benchmarks'),
  };
}

function mapBenchmarkSection(section: ApiBenchmarkSection, fallbackTitle: string): BenchmarkSection {
  const rows = section.results.map((row) => ({
    method: row.method,
    subtext: methodLabel(row.method),
    prec10: row.metrics['precision@10'] ?? 0,
    recall10: row.metrics['recall@10'] ?? 0,
    mrr10: row.metrics['mrr@10'] ?? 0,
    ndcg10: row.metrics['ndcg@10'] ?? 0,
    fullSup10: row.metrics['full_support_recall@10'] ?? 0,
    p50: row.metrics['latency_p50_ms'] ?? 0,
    p95: row.metrics['latency_p95_ms'] ?? 0,
    qps: row.metrics.qps ?? 0,
    queries: row.metrics.queries ?? Number(section.config?.queries ?? 0),
  }));
  const bestFullSupport = Math.max(0, ...rows.map((row) => row.fullSup10));
  return {
    title: section.title ?? fallbackTitle,
    subtitle: section.subtitle ?? '',
    config: section.config ?? {},
    results: rows.map((row) => ({ ...row, isPeak: row.fullSup10 === bestFullSupport })),
  };
}

export async function searchHotpotQA(query: string, method: string, topK: number, queryId?: string): Promise<SearchResponse> {
  return apiFetch('/search', {
    method: 'POST',
    body: JSON.stringify({ query_id: queryId, query, method, top_k: topK }),
  });
}

function methodLabel(method: string): string {
  switch (method) {
    case 'es_bm25':
      return 'Keyword baseline';
    case 'tv_dense':
      return 'TurboVec dense retrieval';
    case 'tv_hybrid':
      return 'TurboVec + BM25 RRF';
    case 'tv_filtered_hybrid':
      return 'BM25-filtered TurboVec RRF';
    default:
      return 'Retrieval method';
  }
}

export async function getHistory(limit = 100): Promise<HistoryEntry[]> {
  const payload = await apiFetch<{ count: number; history: HistoryEntry[] }>(`/history?limit=${limit}`);
  return payload.history;
}

export async function getHistoryDetail(id: number): Promise<HistoryEntry> {
  return apiFetch(`/history/${id}`);
}

export async function clearHistory(): Promise<number> {
  const payload = await apiFetch<{ deleted: number }>('/history', { method: 'DELETE' });
  return payload.deleted;
}
