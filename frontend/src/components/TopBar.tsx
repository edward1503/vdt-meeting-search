import { Analytics, AccountCircle } from '@/src/components/Icons';
import type { DatasetProfile, ViewType } from '@/src/types';

interface TopBarProps {
  activeView: ViewType;
  dataset: DatasetProfile | null;
}

const VIEW_TITLES: Record<ViewType, string> = {
  search: 'Knowledge Explorer',
  queries: 'Elasticsearch Workbench',
  benchmark: 'Retrieval Dashboard',
  indexes: 'Dataset Indexes',
  metadata: 'Dataset Metadata',
  history: 'Query History',
  status: 'Dataset Retrieval Status',
};

export function TopBar({ activeView, dataset }: TopBarProps) {
  return (
    <header className="bg-white border-b-4 border-primary w-full sticky top-0 z-40">
      <div className="flex items-center justify-between px-6 py-3 max-w-[1500px] mx-auto w-full">
        <div className="flex items-center gap-3">
          <Analytics className="text-primary text-3xl font-bold" />
          <h2 className="font-headline text-xl font-bold text-on-background">
            {VIEW_TITLES[activeView]}
          </h2>
        </div>
        <div className="flex items-center gap-4">
          {dataset && (
            <div className="hidden md:flex items-center space-x-2 px-3 py-1 bg-primary/10 rounded-full border border-primary/20">
              <span className="font-label text-[10px] text-primary uppercase font-bold tracking-widest">
                {dataset.id} / {dataset.language} / {dataset.readiness}
              </span>
            </div>
          )}
          <div className="hidden md:flex items-center space-x-2 px-3 py-1 bg-primary/10 rounded-full border border-primary/20">
            <span className="w-2 h-2 rounded-full bg-primary animate-pulse"></span>
            <span className="font-label text-[10px] text-primary uppercase font-bold tracking-widest">
              API Online
            </span>
          </div>
          <button className="w-9 h-9 rounded-full hover:bg-surface-container-low transition-colors flex items-center justify-center text-on-surface-variant">
            <AccountCircle size={24} />
          </button>
        </div>
      </div>
    </header>
  );
}
