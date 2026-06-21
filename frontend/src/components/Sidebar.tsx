import { cn } from '@/src/lib/utils';
import type { DatasetProfile, ViewType } from '@/src/types';
import { Search, Terminal, BarChart3 as Leaderboard, SlidersHorizontal as SettingsInputComponent, Clock, Database, FolderTree, Braces } from 'lucide-react';

interface SidebarProps {
  activeView: ViewType;
  onViewChange: (view: ViewType) => void;
  datasets: DatasetProfile[];
  activeDatasetId: string;
  onDatasetChange: (datasetId: string) => void;
}

export function Sidebar({ activeView, onViewChange, datasets, activeDatasetId, onDatasetChange }: SidebarProps) {
  const navItems = [
    { id: 'search' as ViewType, label: 'Search', Icon: Search },
    { id: 'queries' as ViewType, label: 'Queries', Icon: Terminal },
    { id: 'benchmark' as ViewType, label: 'Benchmark', Icon: Leaderboard },
    { id: 'indexes' as ViewType, label: 'Indexes', Icon: FolderTree },
    { id: 'metadata' as ViewType, label: 'Metadata', Icon: Braces },
    { id: 'history' as ViewType, label: 'History', Icon: Clock },
    { id: 'status' as ViewType, label: 'System Status', Icon: SettingsInputComponent },
  ];

  return (
    <aside className="h-full w-60 flex-shrink-0 sticky top-0 bg-white border-r border-outline-variant flex flex-col p-4 space-y-4 z-50">
      <div className="mb-3 px-2">
        <h1 className="font-headline text-xl leading-tight text-on-surface">
          Dataset <span className="text-primary font-extrabold">RETRIEVAL</span>
        </h1>
        <p className="font-label text-[10px] text-on-surface-variant opacity-70 mt-1 uppercase tracking-widest">
          RESEARCH v2.4.0
        </p>
      </div>
      <div className="px-2 space-y-2">
        <label className="font-label text-[10px] text-on-surface-variant uppercase tracking-widest font-bold">Dataset</label>
        <div className="relative">
          <Database className="absolute left-3 top-1/2 -translate-y-1/2 text-on-surface-variant" size={14} />
          <select
            value={activeDatasetId}
            onChange={(event) => onDatasetChange(event.target.value)}
            className="w-full pl-9 pr-3 py-2 bg-white border border-outline-variant rounded-lg font-mono text-xs font-bold focus:ring-2 focus:ring-primary outline-none"
          >
            {datasets.length === 0 && <option value="hotpotqa">HotpotQA Full Corpus</option>}
            {datasets.map((dataset) => <option key={dataset.id} value={dataset.id}>{dataset.label}</option>)}
          </select>
        </div>
      </div>
      <nav className="flex flex-col space-y-1.5">
        {navItems.map(({ id, label, Icon }) => (
          <button
            key={id}
            onClick={() => onViewChange(id)}
            className={cn(
              "flex items-center gap-3 px-3 py-2.5 rounded-lg font-label uppercase tracking-wider transition-all",
              activeView === id
                ? "bg-primary text-on-primary font-bold shadow-sm"
                : "text-on-surface-variant hover:bg-surface-container-low"
            )}
          >
            <Icon size={18} />
            <span className="text-xs">{label}</span>
          </button>
        ))}
      </nav>
      <div className="mt-auto pt-4 border-t border-outline-variant">
        <div className="flex items-center gap-2 px-2">
          <div className="w-2.5 h-2.5 rounded-full bg-primary animate-pulse" />
          <span className="font-mono text-[10px] text-primary font-bold tracking-widest">API ONLINE</span>
        </div>
        <p className="mt-2 px-2 font-mono text-[10px] text-on-surface-variant opacity-60">
          v2.4.1-stable
        </p>
      </div>
    </aside>
  );
}
