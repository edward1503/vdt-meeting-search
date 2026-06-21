/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { useEffect, useMemo, useState } from 'react';
import { Sidebar } from './components/Sidebar';
import { TopBar } from './components/TopBar';
import { SearchView } from './components/SearchView';
import { QueriesView } from './components/QueriesView';
import { BenchmarkView } from './components/BenchmarkView';
import { StatusView } from './components/StatusView';
import { HistoryView } from './components/HistoryView';
import { IndexesView } from './components/IndexesView';
import { MetadataView } from './components/MetadataView';
import type { DatasetProfile, SearchPreset, ViewType } from './types';
import { getDatasets } from './lib/api';
import { AnimatePresence, motion } from 'motion/react';

export default function App() {
  const [activeView, setActiveView] = useState<ViewType>('status');
  const [searchPreset, setSearchPreset] = useState<SearchPreset | null>(null);
  const [datasets, setDatasets] = useState<DatasetProfile[]>([]);
  const [activeDatasetId, setActiveDatasetId] = useState('hotpotqa');
  const [datasetError, setDatasetError] = useState<string | null>(null);

  useEffect(() => {
    getDatasets()
      .then((payload) => {
        setDatasets(payload.datasets);
        setActiveDatasetId(payload.default_dataset_id);
      })
      .catch((err) => setDatasetError(err instanceof Error ? err.message : 'Could not load datasets'));
  }, []);

  const activeDataset = useMemo(
    () => datasets.find((dataset) => dataset.id === activeDatasetId) ?? datasets[0] ?? null,
    [datasets, activeDatasetId],
  );

  const renderView = () => {
    switch (activeView) {
      case 'search': return <SearchView dataset={activeDataset} preset={searchPreset} />;
      case 'queries': return <QueriesView dataset={activeDataset} onSearchQuery={(preset) => { setSearchPreset({ ...preset, datasetId: activeDataset?.id }); setActiveView('search'); }} />;
      case 'benchmark': return <BenchmarkView dataset={activeDataset} />;
      case 'indexes': return <IndexesView dataset={activeDataset} />;
      case 'metadata': return <MetadataView dataset={activeDataset} />;
      case 'history': return <HistoryView onRunAgain={(preset) => { setSearchPreset(preset); setActiveDatasetId(preset.datasetId ?? activeDatasetId); setActiveView('search'); }} />;
      case 'status': return <StatusView dataset={activeDataset} datasetError={datasetError} />;
      default: return <StatusView dataset={activeDataset} datasetError={datasetError} />;
    }
  };

  return (
    <div className="flex min-h-screen bg-surface">
      <Sidebar
        activeView={activeView}
        onViewChange={setActiveView}
        datasets={datasets}
        activeDatasetId={activeDatasetId}
        onDatasetChange={(datasetId) => {
          setActiveDatasetId(datasetId);
          setSearchPreset(null);
        }}
      />

      <main className="flex-1 flex flex-col min-w-0">
        <TopBar activeView={activeView} dataset={activeDataset} />

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
              <div className={activeView !== 'queries' && activeView !== 'history' ? "max-w-[1500px] mx-auto h-full" : "h-full"}>
                {renderView()}
              </div>
            </motion.div>
          </AnimatePresence>
        </div>
      </main>
    </div>
  );
}
