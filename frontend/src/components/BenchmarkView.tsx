import { useEffect, useMemo, useState } from 'react';
import { BenchmarkResult } from '@/src/types';
import { getBenchmark } from '@/src/lib/api';
import { Verified, TrendingUp, FactCheck, Bolt } from '@/src/components/Icons';
import { ScatterChart, Scatter, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts';

const FALLBACK_BENCHMARK_DATA: BenchmarkResult[] = [];

export function BenchmarkView() {
  const [benchmarkData, setBenchmarkData] = useState<BenchmarkResult[]>(FALLBACK_BENCHMARK_DATA);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getBenchmark()
      .then(setBenchmarkData)
      .catch((err) => setError(err instanceof Error ? err.message : 'Could not load benchmark data'));
  }, []);

  const scatterData = useMemo(() => benchmarkData.map(d => ({
    x: d.p50,
    y: d.recall10,
    name: d.method,
    peak: d.isPeak
  })), [benchmarkData]);

  const bestRecall = Math.max(0, ...benchmarkData.map((d) => d.recall10));
  const bestNdcg = Math.max(0, ...benchmarkData.map((d) => d.ndcg10));
  const bestFullSupport = Math.max(0, ...benchmarkData.map((d) => d.fullSup10));
  const fastest = benchmarkData.reduce<BenchmarkResult | null>((best, row) => !best || row.p50 < best.p50 ? row : best, null);

  return (
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-700">
      <div className="flex flex-col gap-1.5">
        <h3 className="font-headline text-3xl font-extrabold text-on-surface">Retrieval Quality Benchmarks</h3>
        <p className="text-on-surface-variant max-w-5xl text-sm font-normal">
          A comprehensive comparison of retrieval strategies across the HotpotQA dataset. Metrics are evaluated on the dev-distractor split using Elasticsearch 8.12.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
        <SummaryCard label="Best Recall@10" value={bestRecall.toFixed(3)} Icon={Verified} badge="Best Method" />
        <SummaryCard label="Best nDCG@10" value={bestNdcg.toFixed(3)} Icon={TrendingUp} badge="Best Method" isAlt />
        <SummaryCard label="Best Full-Support@10" value={bestFullSupport.toFixed(3)} Icon={FactCheck} badge="Best Method" />
        <SummaryCard label="Fastest p50 Latency" value={fastest ? `${Math.round(fastest.p50)}ms` : "0ms"} Icon={Bolt} badge={fastest?.method ?? "N/A"} isMuted />
      </div>

      {error && <div className="bg-white border border-primary text-primary rounded-xl p-4 font-bold">{error}</div>}

      <div className="grid grid-cols-1 xl:grid-cols-5 gap-5 items-stretch">
        <div className="xl:col-span-3 bg-white border border-outline-variant rounded-xl shadow-sm overflow-hidden h-full flex flex-col">
          <div className="px-4 py-3 border-b border-outline-variant bg-surface-container flex justify-between items-center gap-3">
            <h4 className="font-headline text-lg font-bold text-on-surface">Method Comparison Matrix</h4>
            <div className="flex gap-4">
              <LegendItem color="bg-primary" label="Peak Performance" />
              <LegendItem color="bg-outline" label="Industry Baseline" />
            </div>
          </div>
          <div className="overflow-x-auto flex-1">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-surface-container-low/50">
                  <th className="px-4 py-3 font-label text-[10px] text-on-surface-variant border-b border-outline-variant uppercase font-bold tracking-widest">Method</th>
                  <th className="px-3 py-3 font-label text-[10px] text-on-surface-variant border-b border-outline-variant uppercase font-bold tracking-widest">Prec@10</th>
                  <th className="px-3 py-3 font-label text-[10px] text-on-surface-variant border-b border-outline-variant uppercase font-bold tracking-widest">Recall@10</th>
                  <th className="px-3 py-3 font-label text-[10px] text-on-surface-variant border-b border-outline-variant uppercase font-bold tracking-widest">nDCG@10</th>
                  <th className="px-3 py-3 font-label text-[10px] text-on-surface-variant border-b border-outline-variant uppercase font-bold tracking-widest text-right">p50</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-outline-variant/30">
                {benchmarkData.map((d) => (
                  <tr key={d.method} className={`hover:bg-surface-container-low transition-colors group ${d.isPeak ? 'bg-primary/[0.03] border-l-4 border-primary' : ''}`}>
                    <td className="px-4 py-3">
                      <div className="flex flex-col">
                        <span className={`font-mono text-sm font-bold ${d.isPeak ? 'text-primary' : 'text-on-surface'}`}>{d.method}</span>
                        <span className="text-[10px] text-on-surface-variant uppercase font-semibold tracking-tight">{d.subtext}</span>
                      </div>
                    </td>
                    <td className="px-3 py-3 font-mono text-xs">{d.prec10.toFixed(3)}</td>
                    <td className="px-3 py-3">
                      <div className="flex items-center gap-3">
                        <span className="font-mono text-xs w-10">{d.recall10.toFixed(3)}</span>
                        <div className="flex-1 min-w-[60px] h-2 bg-surface-container-high rounded-full overflow-hidden">
                          <div className={`h-full ${d.isPeak ? 'bg-primary' : 'bg-outline'}`} style={{ width: `${d.recall10 * 100}%` }} />
                        </div>
                      </div>
                    </td>
                    <td className="px-3 py-3 font-mono text-xs">{d.ndcg10.toFixed(3)}</td>
                    <td className="px-3 py-3 text-right text-on-surface font-bold font-mono text-xs">{d.p50}ms</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="xl:col-span-2 bg-white border border-outline-variant p-4 rounded-xl shadow-sm flex flex-col h-full">
           <h5 className="font-label text-[10px] text-on-surface-variant mb-3 uppercase tracking-widest text-center font-bold">Efficiency Frontier (Recall vs. p50)</h5>
           <div className="flex-1 min-h-[230px]">
             <ResponsiveContainer width="100%" height="100%">
               <ScatterChart margin={{ top: 20, right: 20, bottom: 20, left: 20 }}>
                 <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f8" />
                 <XAxis type="number" dataKey="x" name="Latency" unit="ms" label={{ value: 'Latency (p50)', position: 'insideBottom', offset: -10, className: 'font-label text-[10px] uppercase font-bold' }} />
                 <YAxis type="number" dataKey="y" name="Recall" domain={[0, 1]} label={{ value: 'Recall@10', angle: -90, position: 'insideLeft', className: 'font-label text-[10px] uppercase font-bold' }} />
                 <Tooltip cursor={{ strokeDasharray: '3 3' }} />
                 <Scatter name="Methods" data={scatterData}>
                   {scatterData.map((entry, index) => (
                     <Cell key={`cell-${index}`} fill={entry.peak ? '#bf0027' : '#936e6c'} r={entry.peak ? 8 : 6} />
                   ))}
                 </Scatter>
               </ScatterChart>
             </ResponsiveContainer>
           </div>
           <div className="mt-3 pt-3 border-t border-outline-variant/30 text-[10px] text-on-surface-variant text-center italic">
             Nodes represent distinct retrieval pipelines plotted by response speed and coverage accuracy.
           </div>
        </div>
      </div>
    </div>
  );
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
        <span className={`px-2 py-0.5 text-[10px] font-bold rounded uppercase tracking-widest ${
          isMuted ? 'bg-surface-container-high text-on-surface-variant' :
          isAlt ? 'bg-primary/10 text-primary' : 'bg-primary text-on-primary'
        }`}>{badge}</span>
      </div>
    </div>
  );
}

function LegendItem({ color, label }: any) {
  return (
    <span className="flex items-center gap-2 text-[10px] font-bold text-on-surface-variant uppercase tracking-widest">
      <span className={`w-2.5 h-2.5 ${color} rounded-full`} /> {label}
    </span>
  );
}
