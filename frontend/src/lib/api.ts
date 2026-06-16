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

export async function getQueries(): Promise<Query[]> {
  const payload = await apiFetch<{ count: number; queries: ApiQuery[] }>('/queries');
  return payload.queries.map((row) => ({
    id: row.query_id,
    text: row.query,
    docs: row.support_doc_ids,
    status: 'processed',
  }));
}

export async function getBenchmark(): Promise<BenchmarkResult[]> {
  const payload = await apiFetch<{ results: ApiBenchmarkResult[] }>('/benchmark');
  const rows = payload.results.map((row) => ({
    method: row.method,
    subtext: methodLabel(row.method),
    prec10: row.metrics['precision@10'] ?? 0,
    recall10: row.metrics['recall@10'] ?? 0,
    ndcg10: row.metrics['ndcg@10'] ?? 0,
    fullSup10: row.metrics['full_support_recall@10'] ?? 0,
    p50: row.metrics['latency_p50_ms'] ?? 0,
  }));
  const bestRecall = Math.max(...rows.map((row) => row.recall10));
  return rows.map((row) => ({ ...row, isPeak: row.recall10 === bestRecall }));
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
