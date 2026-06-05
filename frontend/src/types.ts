export type View = 'dashboard' | 'search' | 'detail' | 'analytics';

export interface Participant {
  id: string;
  name: string;
  avatar: string;
  role?: string;
  unit: string;
}

export interface Meeting {
  id: string;
  title: string;
  date: string;
  time: string;
  duration: string;
  location: string;
  participants: Participant[];
  relevance: number;
  snippet?: string;
  source: string;
  keywords: string[];
}

export interface Metric {
  label: string;
  value: string | number;
  trend?: number;
  target?: number;
  status?: 'optimal' | 'warning' | 'critical';
}

export interface AnalyticsData {
  precision: Metric;
  recall: Metric;
  mrr: Metric;
  latency: Metric;
}
