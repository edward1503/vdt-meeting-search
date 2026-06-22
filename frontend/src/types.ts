export type ViewType = 'search' | 'queries' | 'benchmark' | 'indexes' | 'metadata' | 'history' | 'status';

export type DatasetReadiness = 'ready' | 'partial' | 'missing';

export interface DatasetProfile {
  id: string;
  label: string;
  language: string;
  task_type: string;
  dataset_id: string;
  index: string;
  methods: string[];
  default_method: string;
  dense_backend: string;
  embedding_model: string;
  vector_dims: number | null;
  query_file: string | null;
  qrels_file: string | null;
  benchmark_files: string[];
  readiness: DatasetReadiness;
  supports_metadata_filters: boolean;
  primary_metric: string;
}

export interface DatasetListResponse {
  default_dataset_id: string;
  datasets: DatasetProfile[];
}

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
  datasetId?: string;
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
