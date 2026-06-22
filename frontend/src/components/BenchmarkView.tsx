import { useEffect, useMemo, useState } from 'react';
import type { BenchmarkResult, DatasetProfile } from '@/src/types';
import { getDatasetBenchmark, type BenchmarkDashboard, type BenchmarkSection } from '@/src/lib/api';
import { Verified, TrendingUp, FactCheck, Bolt } from '@/src/components/Icons';
import { ScatterChart, Scatter, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import { cn } from '@/src/lib/utils';

export function BenchmarkView({ dataset }: { dataset: DatasetProfile | null }) {
  const [dashboard, setDashboard] = useState<BenchmarkDashboard | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!dataset) return;
    setDashboard(null);
    setError(null);
    getDatasetBenchmark(dataset.id)
      .then(setDashboard)
      .catch((err) => setError(err instanceof Error ? err.message : 'Could not load benchmark data'));
  }, [dataset?.id]);

  const current = dashboard?.current ?? emptySection('Current Full-Corpus Benchmark');
  const legacy = dashboard?.legacy ?? emptySection('Legacy Nano / Elasticsearch Benchmarks');
  const isVimQA = dataset?.id === 'vimqa';
  const bestRecall = Math.max(0, ...current.results.map((d) => d.recall10));
  const bestNdcg = Math.max(0, ...current.results.map((d) => d.ndcg10));
  const bestFullSupport = Math.max(0, ...current.results.map((d) => d.fullSup10));
  const fastest = current.results.reduce<BenchmarkResult | null>((best, row) => !best || row.p50 < best.p50 ? row : best, null);

  const scatterData = useMemo(() => current.results.map((d) => ({
    x: d.p50,
    y: isVimQA ? d.recall10 : d.fullSup10,
    name: d.method,
    peak: d.isPeak,
  })), [current.results, isVimQA]);
  const protocolRows = isVimQA ? [
    ['Current table', 'Full VimQA query set with 9,044 labeled queries across BM25, BKAI dense, and BM25+BKAI hybrid.'],
    ['Dataset protocol', 'Use vimqa/all queries and qrels with Recall@10, MRR@10, and nDCG@10 as the comparison metrics.'],
    ['Project metric', 'Prefer Recall@10 for the single-context retrieval proxy; no HotpotQA full-support claim is made.'],
  ] : [
    ['Current table', 'Full corpus, 200 dev queries, project-progress pilot.'],
    ['Paper-style run', 'Run full beir/hotpotqa/test, 7,405 queries, nDCG@10 as primary metric.'],
    ['Project metric', 'Keep Full-support Recall@10 because HotpotQA requires retrieving both evidence documents.'],
  ];

  return (
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-700">
      <div className="flex flex-col gap-1.5">
        <h3 className="font-headline text-3xl font-extrabold text-on-surface">Retrieval Quality Benchmarks</h3>
        <p className="text-on-surface-variant max-w-5xl text-sm font-normal">
          {isVimQA
            ? 'VimQA is a single-context retrieval proxy, so recall, MRR, and nDCG are emphasized over HotpotQA full-support metrics.'
            : 'HotpotQA is multi-hop, so full-support recall remains the project metric for retrieving all evidence documents.'}
        </p>
      </div>

      {error && <div className="bg-white border border-primary text-primary rounded-xl p-4 font-bold">{error}</div>}

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
        <SummaryCard label="Best Recall@10" value={bestRecall.toFixed(3)} Icon={Verified} badge="Current Run" />
        <SummaryCard label="Best nDCG@10" value={bestNdcg.toFixed(3)} Icon={TrendingUp} badge="Current Run" isAlt />
        <SummaryCard label={isVimQA ? 'Best Recall@10' : 'Best Full-Support@10'} value={(isVimQA ? bestRecall : bestFullSupport).toFixed(3)} Icon={FactCheck} badge={dataset?.primary_metric ?? 'Primary Metric'} />
        <SummaryCard label="Fastest p50 Latency" value={fastest ? `${Math.round(fastest.p50)}ms` : '0ms'} Icon={Bolt} badge={fastest?.method ?? 'N/A'} isMuted />
      </div>

      <section className="grid grid-cols-1 xl:grid-cols-7 gap-5 items-stretch">
        <div className="xl:col-span-5 bg-white border border-outline-variant rounded-xl shadow-sm overflow-hidden h-full flex flex-col">
          <SectionHeader section={current} badge="Current" metricLabel={isVimQA ? 'Best recall' : 'Best full support'} />
          <BenchmarkTable rows={current.results} showQueries />
        </div>

        <div className="xl:col-span-2 bg-white border border-outline-variant rounded-xl shadow-sm overflow-hidden h-full flex flex-col">
          <div className="px-4 py-3 border-b border-outline-variant bg-surface-container">
            <h4 className="font-headline text-lg font-bold text-on-surface">Benchmark Config</h4>
            <p className="text-[11px] text-on-surface-variant mt-1">Snapshot metadata for the current project-progress run.</p>
          </div>
          <ConfigTable config={current.config} />
        </div>
      </section>

      <section className="grid grid-cols-1 xl:grid-cols-5 gap-5 items-stretch">
        <div className="xl:col-span-3 bg-white border border-outline-variant p-4 rounded-xl shadow-sm flex flex-col min-h-[320px]">
          <h5 className="font-label text-[10px] text-on-surface-variant mb-3 uppercase tracking-widest text-center font-bold">Efficiency Frontier ({isVimQA ? 'Recall' : 'Full-Support'} vs p50)</h5>
          <div className="flex-1 min-h-[250px]">
            <ResponsiveContainer width="100%" height="100%">
              <ScatterChart margin={{ top: 20, right: 20, bottom: 20, left: 20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f8" />
                <XAxis type="number" dataKey="x" name="Latency" unit="ms" label={{ value: 'Latency (p50)', position: 'insideBottom', offset: -10, className: 'font-label text-[10px] uppercase font-bold' }} />
                <YAxis type="number" dataKey="y" name={isVimQA ? 'Recall' : 'Full-support'} domain={[0, 1]} label={{ value: isVimQA ? 'Recall@10' : 'Full Support@10', angle: -90, position: 'insideLeft', className: 'font-label text-[10px] uppercase font-bold' }} />
                <Tooltip cursor={{ strokeDasharray: '3 3' }} />
                <Scatter name="Methods" data={scatterData}>
                  {scatterData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.peak ? '#bf0027' : '#936e6c'} r={entry.peak ? 8 : 6} />
                  ))}
                </Scatter>
              </ScatterChart>
            </ResponsiveContainer>
          </div>
        </div>
        <div className="xl:col-span-2 bg-white border border-outline-variant rounded-xl shadow-sm overflow-hidden">
          <div className="px-4 py-3 border-b border-outline-variant bg-surface-container">
            <h4 className="font-headline text-lg font-bold text-on-surface">Benchmark Protocol</h4>
            <p className="text-[11px] text-on-surface-variant mt-1">Use this before interpreting project benchmark evidence.</p>
          </div>
          <div className="p-4 space-y-3 text-sm text-on-surface-variant leading-relaxed">
            {protocolRows.map(([label, value]) => (
              <p key={label}><span className="font-bold text-on-surface">{label}:</span> {value}</p>
            ))}
          </div>
        </div>
      </section>

      <section className="bg-white border border-outline-variant rounded-xl shadow-sm overflow-hidden">
        <SectionHeader section={legacy} badge="Legacy" muted />
        <BenchmarkTable rows={legacy.results} compact />
      </section>
    </div>
  );
}

function emptySection(title: string): BenchmarkSection {
  return { title, subtitle: '', config: {}, results: [] };
}

function SectionHeader({ section, badge, muted, metricLabel = 'Best full support' }: { section: BenchmarkSection; badge: string; muted?: boolean; metricLabel?: string }) {
  return (
    <div className="px-4 py-3 border-b border-outline-variant bg-surface-container flex justify-between items-start gap-3">
      <div>
        <div className="flex items-center gap-2">
          <h4 className="font-headline text-lg font-bold text-on-surface">{section.title}</h4>
          <span className={cn('px-2 py-0.5 rounded font-mono text-[10px] font-black uppercase tracking-widest', muted ? 'bg-surface-container-high text-on-surface-variant' : 'bg-primary text-on-primary')}>{badge}</span>
        </div>
        {section.subtitle && <p className="text-[11px] text-on-surface-variant mt-1 max-w-4xl">{section.subtitle}</p>}
      </div>
      <div className="flex gap-4 pt-1">
        <LegendItem color="bg-primary" label={metricLabel} />
        <LegendItem color="bg-outline" label="Baseline" />
      </div>
    </div>
  );
}

function BenchmarkTable({ rows, compact, showQueries }: { rows: BenchmarkResult[]; compact?: boolean; showQueries?: boolean }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left border-collapse">
        <thead>
          <tr className="bg-surface-container-low/50">
            <Header label="Method" />
            {showQueries && <Header label="Queries" />}
            <Header label="Prec@10" />
            <Header label="Recall@10" />
            <Header label="MRR@10" />
            <Header label="nDCG@10" />
            <Header label="FullSup@10" />
            <Header label="p50" right />
            {!compact && <Header label="p95" right />}
            {!compact && <Header label="QPS" right />}
          </tr>
        </thead>
        <tbody className="divide-y divide-outline-variant/30">
          {rows.map((row) => (
            <tr key={row.method} className={cn('hover:bg-surface-container-low transition-colors group', row.isPeak && 'bg-primary/[0.03] border-l-4 border-primary')}>
              <td className="px-4 py-3">
                <div className="flex flex-col">
                  <span className={cn('font-mono text-sm font-bold', row.isPeak ? 'text-primary' : 'text-on-surface')}>{row.method}</span>
                  <span className="text-[10px] text-on-surface-variant uppercase font-semibold tracking-tight">{row.subtext}</span>
                </div>
              </td>
              {showQueries && <MetricCell value={row.queries} integer />}
              <MetricCell value={row.prec10} />
              <BarCell value={row.recall10} peak={row.isPeak} />
              <MetricCell value={row.mrr10} />
              <MetricCell value={row.ndcg10} />
              <BarCell value={row.fullSup10} peak={row.isPeak} />
              <MetricCell value={row.p50} suffix="ms" right integer />
              {!compact && <MetricCell value={row.p95} suffix="ms" right integer />}
              {!compact && <MetricCell value={row.qps} right />}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Header({ label, right }: { label: string; right?: boolean }) {
  return <th className={cn('px-3 py-3 font-label text-[10px] text-on-surface-variant border-b border-outline-variant uppercase font-bold tracking-widest', right && 'text-right')}>{label}</th>;
}

function MetricCell({ value, suffix = '', right, integer }: { value: number; suffix?: string; right?: boolean; integer?: boolean }) {
  const text = integer ? Math.round(value).toString() : value.toFixed(3);
  return <td className={cn('px-3 py-3 font-mono text-xs text-on-surface', right && 'text-right font-bold')}>{text}{suffix}</td>;
}

function BarCell({ value, peak }: { value: number; peak?: boolean }) {
  return (
    <td className="px-3 py-3">
      <div className="flex items-center gap-3">
        <span className="font-mono text-xs w-10">{value.toFixed(3)}</span>
        <div className="flex-1 min-w-[60px] h-2 bg-surface-container-high rounded-full overflow-hidden">
          <div className={cn('h-full', peak ? 'bg-primary' : 'bg-outline')} style={{ width: `${Math.min(100, value * 100)}%` }} />
        </div>
      </div>
    </td>
  );
}

function ConfigTable({ config }: { config: BenchmarkSection['config'] }) {
  const rows = [
    ['Project stage', config.project_stage],
    ['Dataset', config.dataset_id],
    ['Corpus docs', config.corpus_doc_count],
    ['Index', config.index],
    ['Benchmark queries', config.queries ?? config.max_queries],
    ['Top-k', config.top_k],
    ['Model', config.model_name],
    ['Candidates', config.candidate_k],
    ['RRF k', config.rrf_k],
    ['Paper comparable', config.paper_comparable ? 'Yes' : 'No'],
  ];

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left border-collapse">
        <tbody className="divide-y divide-outline-variant/30">
          {rows.map(([label, value]) => (
            <tr key={String(label)}>
              <td className="px-4 py-3 font-label text-[10px] text-on-surface-variant uppercase tracking-widest font-bold w-40">{label}</td>
              <td className="px-4 py-3 font-mono text-xs text-on-surface break-all">{formatConfigValue(value)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function formatConfigValue(value: unknown) {
  if (Array.isArray(value)) return value.join(', ');
  if (typeof value === 'number') return value.toLocaleString();
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  return value === null || value === undefined || value === '' ? 'N/A' : String(value);
}

function SummaryCard({ label, value, Icon, badge, isAlt, isMuted }: any) {
  return (
    <div className="bg-white border border-outline-variant p-4 rounded-xl shadow-sm hover:border-primary transition-colors min-h-28">
      <div className="flex items-center justify-between mb-2 gap-2">
        <span className="text-on-surface-variant font-label text-[10px] uppercase font-bold tracking-widest leading-tight">{label}</span>
        <Icon className="text-primary" size={20} />
      </div>
      <div className="font-headline text-3xl font-extrabold text-on-surface mb-1">{value}</div>
      <div className="flex items-center gap-2">
        <span className={cn('px-2 py-0.5 text-[10px] font-bold rounded uppercase tracking-widest',
          isMuted ? 'bg-surface-container-high text-on-surface-variant' :
          isAlt ? 'bg-primary/10 text-primary' : 'bg-primary text-on-primary'
        )}>{badge}</span>
      </div>
    </div>
  );
}

function LegendItem({ color, label }: any) {
  return (
    <span className="hidden sm:flex items-center gap-2 text-[10px] font-bold text-on-surface-variant uppercase tracking-widest whitespace-nowrap">
      <span className={`w-2.5 h-2.5 ${color} rounded-full`} /> {label}
    </span>
  );
}
