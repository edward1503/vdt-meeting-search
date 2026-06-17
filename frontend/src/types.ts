export type ViewType = 'search' | 'queries' | 'benchmark' | 'history' | 'status';

export interface BenchmarkResult {
  method: string;
  subtext: string;
  prec10: number;
  recall10: number;
  mrr10: number;
  ndcg10: number;
  fullSup10: number;
  p50: number;
  p95: number;
  qps: number;
  queries: number;
  isPeak?: boolean;
}

export interface Query {
  id: string;
  text: string;
  docs: string[];
  status: 'unprocessed' | 'processed' | 'failed';
}

export interface SearchPreset {
  id: number;
  queryId?: string;
  query: string;
  method: string;
  topK: number;
  autoRun?: boolean;
}

export interface SystemStatus {
  service: string;
  status: 'operational' | 'degraded' | 'down';
  details?: string;
}
