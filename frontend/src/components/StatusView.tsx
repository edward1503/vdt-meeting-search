import { useEffect, useState } from 'react';
import { CloudDone, Database, Storage, Memory, Hub, DescriptionIcon, Dataset, Lan, Info } from '@/src/components/Icons';
import { getHealth, getStats, type StatsResponse } from '@/src/lib/api';

function formatDocCount(count?: number | null) {
  if (!count) return 'unknown';
  return count.toLocaleString('en-US');
}

function runtimeProfileLabel(profile?: string) {
  return profile ? profile.toUpperCase() : 'UNKNOWN';
}

export function StatusView() {
  const [health, setHealth] = useState('checking');
  const [stats, setStats] = useState<StatsResponse | null>(null);

  useEffect(() => {
    getHealth()
      .then((payload) => setHealth(payload.status))
      .catch(() => setHealth('down'));
    getStats()
      .then(setStats)
      .catch(() => setStats(null));
  }, []);

  return (
    <div className="space-y-6 animate-in fade-in duration-700">
      <div className="flex flex-col gap-1.5">
        <h1 className="font-headline text-3xl font-extrabold text-on-surface">System Status</h1>
        <p className="text-sm text-on-surface-variant max-w-5xl font-medium">
          Live infrastructure and runtime configuration for the HotpotQA Elasticsearch retrieval pipeline.
        </p>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-12 gap-5 items-start">
        <section className="xl:col-span-5 bg-white border border-outline-variant rounded-xl p-5 shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
            <h3 className="font-headline text-xl font-bold">Status Overview</h3>
            <span className="font-mono text-[10px] text-on-surface-variant bg-surface-container-low px-3 py-1 rounded font-bold uppercase tracking-widest">
              Last check: live API
            </span>
          </div>
          <div className="grid grid-cols-1 gap-3">
            <StatusRow Icon={CloudDone} label="API SERVICE" badge={health.toUpperCase()} isPrimary={health === 'ok'} />
            <StatusRow Icon={Database} label="BACKEND" value={stats?.backend ?? 'checking'} status={stats ? 'CONFIGURED' : 'WAITING'} />
            <StatusRow Icon={Storage} label="ACTIVE INDEX" chip={stats?.index ?? 'unknown'} />
          </div>
        </section>

        <section className="xl:col-span-7 bg-white border border-outline-variant rounded-xl overflow-hidden shadow-sm">
          <div className="bg-surface-container-low px-5 py-3 border-b border-outline-variant flex items-center justify-between">
            <h3 className="font-headline text-xl font-bold">Runtime Parameters</h3>
            <Memory className="text-primary" size={24} />
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 divide-y md:divide-y-0 md:divide-x divide-outline-variant">
            <SpecItem label="Dataset" value={stats?.dataset_id ?? 'beir/hotpotqa/dev'} />
            <SpecItem label="Embedding Model" value={stats?.embedding_model ?? 'BAAI/bge-small-en-v1.5'} />
            <SpecItem label="Runtime Profile" value={runtimeProfileLabel(stats?.runtime_profile)} />
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 border-t border-outline-variant divide-x divide-outline-variant">
            <SpecItem label="Candidate Pool" value={String(stats?.num_candidates ?? 'unknown')} />
            <SpecItem label="Cache TTL" value={`${stats?.search_cache_ttl_seconds ?? 300}s`} />
            <StatItem label="Corpus" value={formatDocCount(stats?.corpus_doc_count)} unit="docs" />
            <StatItem label="Benchmarks" value="50" unit="cases" />
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 border-t border-outline-variant divide-y md:divide-y-0 md:divide-x divide-outline-variant">
            <SpecItem label="Available Methods" value={stats?.methods?.join(', ') ?? 'loading'} />
            <SpecItem label="TurboVec Index" value={stats?.turbovec_index_path ?? 'not configured'} />
            <SpecItem label="History DB" value={stats?.history_db_path ?? '/app/data/query_history.sqlite3'} />
          </div>
        </section>
      </div>

      <section className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <h3 className="font-headline text-2xl font-extrabold">Retrieval Pipeline Dataflow</h3>
          <div className="flex items-center space-x-3">
            <Info className="text-primary" size={20} fill="currentColor" />
            <span className="font-label text-xs text-on-surface-variant uppercase tracking-[0.25em] font-bold">End-to-End Architecture</span>
          </div>
        </div>
        <div className="bg-white border border-outline-variant rounded-xl p-5 overflow-x-auto custom-scrollbar">
          <div className="flex items-center min-w-max justify-center gap-5">
            <FlowNode Icon={Dataset} label="HotpotQA" sub={runtimeProfileLabel(stats?.runtime_profile)} />
            <FlowConnector />
            <FlowNode Icon={DescriptionIcon} label="ES BM25" sub="5.23M DOCS" isPrimary />
            <FlowConnector />
            <FlowNode Icon={Hub} label="BGE Embed" sub="HOST:8010" isAlt />
            <FlowConnector />
            <FlowNode Icon={Memory} label="TurboVec" sub="LOCAL .TVIM" isPrimary />
            <FlowConnector />
            <FlowNode Icon={Lan} label="RRF Evidence" sub="RANKED" />
          </div>
        </div>
      </section>
    </div>
  );
}

function StatusRow({ Icon, label, value, status, chip, badge, isPrimary }: any) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 p-3.5 bg-surface-container-low rounded-lg border border-outline-variant/30">
      <div className="flex items-center space-x-4 min-w-0">
        <Icon className={isPrimary ? 'text-primary' : 'text-on-surface-variant'} size={20} />
        <span className="font-headline text-sm font-bold uppercase tracking-tight truncate">{label}</span>
      </div>
      <div className="flex flex-wrap items-center justify-end gap-3 min-w-0">
        {value && <span className="font-mono text-xs text-on-surface bg-white px-3 py-1 rounded shadow-sm font-bold uppercase tracking-widest truncate max-w-56">{value}</span>}
        {status && <span className="font-mono text-xs text-primary font-bold border-l border-outline-variant pl-3 tracking-widest">{status}</span>}
        {chip && <span className="font-mono text-xs bg-primary/10 text-primary px-4 py-1.5 rounded-lg font-bold uppercase tracking-widest border border-primary/20 truncate max-w-64">{chip}</span>}
        {badge && <span className="bg-primary text-on-primary px-4 py-1.5 rounded font-mono text-[10px] font-bold uppercase tracking-[0.2em] shadow-lg shadow-primary/20">{badge}</span>}
      </div>
    </div>
  );
}

function StatItem({ label, value, unit }: any) {
  return (
    <div className="p-4 min-w-0">
      <p className="font-label text-[10px] text-on-surface-variant uppercase mb-2 font-bold tracking-widest">{label}</p>
      <div className="flex items-baseline space-x-2">
        <p className="font-headline text-2xl font-extrabold text-on-surface">{value}</p>
        <p className="font-label text-[10px] text-on-surface-variant opacity-60 font-bold uppercase tracking-widest">{unit}</p>
      </div>
    </div>
  );
}

function SpecItem({ label, value }: any) {
  return (
    <div className="p-4 min-w-0">
      <p className="font-label text-[10px] text-on-surface-variant uppercase mb-2 font-bold tracking-[0.2em]">{label}</p>
      <p className="font-mono text-sm text-primary font-bold break-words leading-relaxed">{value}</p>
    </div>
  );
}

function FlowNode({ Icon, label, sub, isPrimary, isAlt }: any) {
  return (
    <div className="flex flex-col items-center space-y-2 group">
      <div className={`w-16 h-16 rounded-xl border-2 flex items-center justify-center transition-all duration-300 ${
        isPrimary ? 'bg-primary border-primary text-on-primary shadow-xl shadow-primary/20 scale-105' :
        isAlt ? 'bg-primary/5 border-primary text-primary' :
        'bg-surface-container border-outline-variant text-on-surface-variant group-hover:border-primary group-hover:text-primary'
      }`}>
        <Icon size={28} />
      </div>
      <div className="text-center">
        <p className={`font-label text-xs uppercase font-extrabold tracking-widest ${isPrimary || isAlt ? 'text-primary' : 'text-on-surface-variant'}`}>{label}</p>
        <p className="font-mono text-[9px] text-outline font-bold mt-1 tracking-[0.1em]">{sub}</p>
      </div>
    </div>
  );
}

function FlowConnector() {
  return <div className="w-7 h-0.5 bg-outline-variant" />;
}
