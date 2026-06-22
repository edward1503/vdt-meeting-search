import { Braces, CheckCircle2, XCircle } from 'lucide-react';
import type { DatasetProfile } from '@/src/types';

const HOTPOTQA_METADATA_FIELDS = ['author', 'created_at', 'modified_at', 'source_split'];

export function MetadataView({ dataset }: { dataset: DatasetProfile | null }) {
  if (!dataset) {
    return <div className="p-6 font-label text-sm text-on-surface-variant">Dataset profile is loading.</div>;
  }

  const supported = dataset.supports_metadata_filters;
  const fields = dataset.id === 'hotpotqa' ? HOTPOTQA_METADATA_FIELDS : [];

  return (
    <section className="p-6 space-y-5">
      <header className="flex items-center justify-between gap-4">
        <div>
          <h2 className="font-headline text-2xl text-on-surface">Metadata</h2>
          <p className="mt-1 text-sm text-on-surface-variant">Metadata filter capability for {dataset.label}.</p>
        </div>
        <span className={`px-3 py-1 rounded-full font-mono text-xs font-bold uppercase ${supported ? 'bg-primary/10 text-primary' : 'bg-surface-container-high text-on-surface-variant'}`}>
          {supported ? 'filters enabled' : 'filters unavailable'}
        </span>
      </header>

      <div className="border border-outline-variant rounded-lg bg-white p-4 flex items-start gap-3">
        {supported ? <CheckCircle2 className="text-primary mt-0.5" size={20} /> : <XCircle className="text-on-surface-variant mt-0.5" size={20} />}
        <div>
          <div className="font-bold text-on-surface">{supported ? 'Search requests can include metadata filters.' : 'This dataset does not expose metadata filters in Sprint 4.'}</div>
          <p className="mt-1 text-sm text-on-surface-variant">
            {supported ? 'Filters are applied as hard prefilters before ranked evidence is returned.' : 'Search, queries, benchmarks, and index status remain available for this dataset.'}
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        {(fields.length ? fields : ['No metadata fields configured']).map((field) => (
          <div key={field} className="border border-outline-variant rounded-lg p-3 bg-white flex items-center gap-2">
            <Braces size={16} className="text-on-surface-variant" />
            <span className="font-mono text-sm text-on-surface">{field}</span>
          </div>
        ))}
      </div>
    </section>
  );
}
