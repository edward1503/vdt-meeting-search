import { View } from '../types';
import { LayoutDashboard, Search, History, BarChart3, Settings, Plus, Activity } from 'lucide-react';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

interface SidebarProps {
  currentView: View;
  onViewChange: (view: View) => void;
}

export default function Sidebar({ currentView, onViewChange }: SidebarProps) {
  const navItems = [
    { id: 'dashboard' as View, label: 'Dashboard', icon: LayoutDashboard },
    { id: 'search' as View, label: 'Search', icon: Search },
    { id: 'history' as View, label: 'History', icon: History },
    { id: 'analytics' as View, label: 'Analytics', icon: BarChart3 },
    { id: 'settings' as View, label: 'Settings', icon: Settings },
  ];

  return (
    <aside className="fixed left-0 top-0 h-full w-[280px] z-50 bg-surface-container-low border-r border-border-subtle flex flex-col py-6 px-4 gap-4 hidden lg:flex">
      <div className="flex items-center gap-3 mb-8 px-2">
        <div className="w-10 h-10 bg-primary-container flex items-center justify-center rounded-lg shadow-lg">
          <Activity className="text-white w-6 h-6" />
        </div>
        <div className="flex flex-col">
          <span className="text-[22px] font-black text-primary leading-tight">VDT Search</span>
          <span className="text-[10px] font-bold tracking-[0.1em] text-on-surface-variant uppercase">Enterprise Intelligence</span>
        </div>
      </div>

      <button className="mb-6 py-3 px-4 bg-primary-container text-white rounded-xl font-bold flex items-center justify-center gap-2 hover:brightness-110 active:scale-95 transition-all shadow-[0_0_20px_rgba(238,0,51,0.2)]">
        <Plus className="w-5 h-5" />
        New Search
      </button>

      <nav className="flex flex-col gap-1">
        {navItems.map((item) => (
          <button
            key={item.id}
            onClick={() => onViewChange(item.id)}
            className={cn(
              "flex items-center gap-4 px-4 py-3 rounded-lg transition-all duration-200 group text-[13px] font-semibold uppercase tracking-wider",
              currentView === item.id
                ? "bg-primary/10 text-primary"
                : "text-on-surface-variant hover:text-on-surface hover:bg-surface-container-high"
            )}
          >
            <item.icon className={cn("w-5 h-5", currentView === item.id ? "text-primary" : "text-on-surface-variant group-hover:text-primary")} />
            {item.label}
          </button>
        ))}
      </nav>

      <div className="mt-auto p-4 glass-panel rounded-xl">
        <p className="text-[10px] font-bold text-on-surface-variant mb-2 uppercase tracking-widest">Storage Usage</p>
        <div className="w-full bg-surface-variant h-1 rounded-full mb-2 overflow-hidden">
          <div className="bg-primary-container h-full w-3/4 rounded-full shadow-[0_0_10px_rgba(238,0,51,0.4)]"></div>
        </div>
        <p className="font-mono text-[10px] text-on-surface">1.2 TB / 1.5 TB INDICES</p>
      </div>
    </aside>
  );
}
