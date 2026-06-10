export type ViewType = 'search' | 'queries' | 'benchmark' | 'history' | 'status';

export interface BenchmarkResult {
  method: string;
  subtext: string;
  prec10: number;
  recall10: number;
  ndcg10: number;
  fullSup10: number;
  p50: number;
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
  query: string;
  method: string;
  topK: number;
}

export interface SystemStatus {
  service: string;
  status: 'operational' | 'degraded' | 'down';
  details?: string;
}
