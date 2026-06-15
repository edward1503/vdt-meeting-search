/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { useState } from 'react';
import { Sidebar } from './components/Sidebar';
import { TopBar } from './components/TopBar';
import { SearchView } from './components/SearchView';
import { QueriesView } from './components/QueriesView';
import { BenchmarkView } from './components/BenchmarkView';
import { StatusView } from './components/StatusView';
import { HistoryView } from './components/HistoryView';
import { SearchPreset, ViewType } from './types';
import { AnimatePresence, motion } from 'motion/react';

export default function App() {
  const [activeView, setActiveView] = useState<ViewType>('status');
  const [searchPreset, setSearchPreset] = useState<SearchPreset | null>(null);

  const renderView = () => {
    switch (activeView) {
      case 'search': return <SearchView preset={searchPreset} />;
      case 'queries': return <QueriesView />;
      case 'benchmark': return <BenchmarkView />;
      case 'history': return <HistoryView onRunAgain={(preset) => { setSearchPreset(preset); setActiveView('search'); }} />;
      case 'status': return <StatusView />;
      default: return <StatusView />;
    }
  };

  return (
    <div className="flex min-h-screen bg-surface">
      <Sidebar activeView={activeView} onViewChange={setActiveView} />

      <main className="flex-1 flex flex-col min-w-0">
        <TopBar activeView={activeView} />

        <div className={activeView === 'queries' || activeView === 'history' ? "flex-1 overflow-hidden" : "flex-1 overflow-y-auto custom-scrollbar px-5 py-5 lg:px-6 lg:py-6"}>
          <AnimatePresence mode="wait">
            <motion.div
              key={activeView}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
              className="h-full"
            >
              <div className={activeView !== 'queries' ? "max-w-[1500px] mx-auto h-full" : "h-full"}>
                {renderView()}
              </div>
            </motion.div>
          </AnimatePresence>
        </div>
      </main>
    </div>
  );
}
