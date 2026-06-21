import { FolderTree } from 'lucide-react';
import type { DatasetProfile } from '@/src/types';

function Field({ label, value }: { label: string; value: string | number | null | undefined }) {
  return (
    <div className="border border-outline-variant rounded-lg p-3 bg-white">
      <div className="font-label text-[10px] uppercase tracking-widest text-on-surface-variant font-bold">{label}</div>
      <div className="mt-1 font-mono text-sm text-on-surface break-words">{value ?? 'Not configured'}</div>
    </div>
  );
}

export function IndexesView({ dataset }: { dataset: DatasetProfile | null }) {
  if (!dataset) {
    return <div className="p-6 font-label text-sm text-on-surface-variant">Dataset profile is loading.</div>;
  }

  return (
    <section className="p-6 space-y-5">
      <header className="flex items-center justify-between gap-4">
        <div>
          <h2 className="font-headline text-2xl text-on-surface">Indexes</h2>
          <p className="mt-1 text-sm text-on-surface-variant">Runtime index configuration for {dataset.label}.</p>
        </div>
        <span className="px-3 py-1 rounded-full bg-primary/10 text-primary font-mono text-xs font-bold uppercase">{dataset.readiness}</span>
      </header>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3">
        <Field label="Search index" value={dataset.index} />
        <Field label="Dense backend" value={dataset.dense_backend} />
        <Field label="Embedding model" value={dataset.embedding_model} />
        <Field label="Vector dims" value={dataset.vector_dims} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
        <Field label="Dataset source" value={dataset.dataset_id} />
        <Field label="Query file" value={dataset.query_file} />
        <Field label="Qrels file" value={dataset.qrels_file} />
      </div>

      <div className="border border-outline-variant rounded-lg bg-white p-4">
        <div className="flex items-center gap-2 text-on-surface font-bold"><FolderTree size={18} /> Benchmark artifacts</div>
        <ul className="mt-3 space-y-2">
          {dataset.benchmark_files.map((path) => <li key={path} className="font-mono text-xs text-on-surface-variant break-all">{path}</li>)}
        </ul>
      </div>
    </section>
  );
}
