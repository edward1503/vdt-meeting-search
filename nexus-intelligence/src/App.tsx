import { useState } from 'react';
import Header from './components/Header';
import Sidebar from './components/Sidebar';
import DashboardView from './components/DashboardView';
import SearchView from './components/SearchView';
import MeetingDetailView from './components/MeetingDetailView';
import AnalyticsView from './components/AnalyticsView';
import { View } from './types';
import { AnimatePresence, motion } from 'motion/react';
import { Brain } from 'lucide-react';

export default function App() {
  const [currentView, setCurrentView] = useState<View>('dashboard');

  const renderView = () => {
    switch (currentView) {
      case 'dashboard': return <DashboardView />;
      case 'search': return <SearchView />;
      case 'detail': return <MeetingDetailView />;
      case 'analytics': return <AnalyticsView />;
      default: return <DashboardView />;
    }
  };

  return (
    <div className="flex min-h-screen bg-background selection:bg-primary/20 selection:text-white">
      <Sidebar 
        currentView={currentView} 
        onViewChange={(view) => setCurrentView(view)} 
      />
      
      <main className="flex-1 lg:ml-[280px] min-h-screen relative flex flex-col">
        <Header />
        
        <div className="flex-1 mt-16 overflow-y-auto custom-scrollbar">
          <div className={`${currentView === 'detail' || currentView === 'search' ? '' : 'max-w-[1440px] mx-auto p-gutter lg:p-12'}`}>
            <AnimatePresence mode="wait">
              <motion.div
                key={currentView}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
                className="h-full"
              >
                {renderView()}
              </motion.div>
            </AnimatePresence>
          </div>
        </div>

        {/* Decorative background elements */}
        <div className="fixed top-0 right-0 w-[500px] h-[500px] bg-primary-container/5 blur-[150px] -z-10 rounded-full"></div>
        <div className="fixed bottom-0 left-[280px] w-[300px] h-[300px] bg-tertiary-container/5 blur-[120px] -z-10 rounded-full"></div>
      </main>

      {/* Floating Action Button (Only on Mobile or specific views) */}
      <button 
        className="fixed bottom-8 right-8 h-14 w-14 bg-primary-container text-white rounded-full flex items-center justify-center shadow-2xl hover:scale-110 active:scale-90 transition-all z-50 md:hidden lg:hidden"
        onClick={() => setCurrentView('search')}
      >
        <span className="material-symbols-outlined">add</span>
      </button>
    </div>
  );
}

