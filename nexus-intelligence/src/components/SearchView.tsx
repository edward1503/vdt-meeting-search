import { MOCK_MEETINGS } from '../constants';
import { Search, History, Filter, SortAsc, Database, User, Calendar, CheckSquare, Verified, Zap, Brain, Activity } from 'lucide-react';
import { motion } from 'motion/react';
import { useState } from 'react';

export default function SearchView() {
  const [showAiChat, setShowAiChat] = useState(false);

  return (
    <div className="h-full flex flex-col bg-background/50">
      {/* Search Bar Area */}
      <div className="px-8 py-4 bg-surface-container-low/50 border-b border-border-subtle flex items-center gap-4 sticky top-0 z-20 backdrop-blur-md">
        <div className="flex-1 relative group">
          <Zap className="absolute left-4 top-1/2 -translate-y-1/2 text-primary w-5 h-5 group-focus-within:animate-pulse transition-all" />
          <input 
            className="w-full bg-surface-container border border-border-subtle rounded-2xl pl-12 pr-4 py-3 text-on-surface focus:ring-1 focus:ring-primary focus:border-primary/50 transition-all font-body-lg text-lg" 
            placeholder="Enter natural language query... (e.g., 'AMI meetings about interface design')" 
            defaultValue="Nghị định 105 và anh Sinh"
            type="text" 
          />
        </div>
        <div className="flex bg-surface-container p-1 rounded-xl border border-border-subtle shadow-inner">
          {['Hybrid', 'Semantic', 'BM25'].map((mode) => (
            <button 
              key={mode}
              className={`px-5 py-1.5 rounded-lg text-[11px] font-black uppercase tracking-widest transition-all
                ${mode === 'Hybrid' ? 'bg-primary-container text-white shadow-lg' : 'text-on-surface-variant hover:text-on-surface'}
              `}
            >
              {mode}
            </button>
          ))}
        </div>
      </div>

      {/* Results Header */}
      <header className="px-8 py-6 flex flex-col gap-4 bg-surface-container-low border-b border-border-subtle">
        <div className="flex items-end justify-between">
          <div>
            <h1 className="text-3xl font-bold text-on-surface flex items-center gap-3">
              <span className="text-on-surface-variant font-normal">Kết quả cho:</span>
              <span className="italic tracking-tight">"Nghị định 105 và anh Sinh"</span>
            </h1>
            <p className="text-on-surface-variant text-sm mt-1 opacity-70">Tìm thấy 12 biên bản phù hợp trong kho dữ liệu doanh nghiệp.</p>
          </div>
          <div className="flex gap-2">
            <button className="px-5 py-2.5 bg-surface-elevated border border-border-subtle rounded-xl text-on-surface flex items-center gap-2 hover:bg-surface-container-highest transition-all active:scale-95 text-xs font-bold uppercase tracking-wider">
              <SortAsc className="w-4 h-4" />
              Mới nhất
            </button>
            <button className="px-5 py-2.5 bg-primary-container text-white rounded-xl flex items-center gap-2 hover:opacity-90 transition-all active:scale-95 text-xs font-bold uppercase tracking-wider shadow-lg">
              <Activity className="w-4 h-4" />
              Độ liên quan
            </button>
          </div>
        </div>

        <div className="flex items-center gap-4">
          <span className="text-[10px] font-bold text-on-surface-variant uppercase tracking-[0.2em] border-r border-border-subtle pr-4">Hiểu được:</span>
          <div className="flex gap-2">
            {[
              { icon: Database, label: 'Source: AMI' },
              { icon: User, label: 'Speaker: Anh Sinh' },
              { icon: Calendar, label: '2023' }
            ].map((tag) => (
              <span key={tag.label} className="px-3 py-1 bg-surface-container-high rounded-full text-[11px] font-bold flex items-center gap-2 border border-border-subtle text-on-surface shadow-sm hover:border-primary/50 transition-all cursor-default">
                <tag.icon className="w-3.5 h-3.5 text-primary" />
                {tag.label}
              </span>
            ))}
          </div>
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">
        {/* Left Filter Sidebar */}
        <aside className="w-72 border-r border-border-subtle p-8 flex flex-col gap-10 bg-surface/50 overflow-y-auto custom-scrollbar">
          <div className="flex justify-between items-center group">
            <h3 className="text-[10px] font-black text-primary uppercase tracking-[0.2em]">Bộ lọc</h3>
            <button className="text-[9px] text-on-surface-variant hover:text-primary uppercase font-black underline underline-offset-4 transition-colors">Reset Filters</button>
          </div>

          <div className="space-y-4">
            <h4 className="text-[11px] font-black text-on-surface uppercase tracking-widest flex items-center gap-2">
              <Database className="w-3.5 h-3.5 text-primary" /> Nguồn dữ liệu
            </h4>
            <div className="flex flex-col gap-3">
              {['AMI Corpus', 'QMSum', 'Business Logs'].map((s, i) => (
                <label key={s} className="flex items-center gap-3 cursor-pointer group">
                  <div className="relative flex items-center justify-center">
                    <input 
                      defaultChecked={i === 0}
                      className="peer h-4 w-4 bg-surface-container border-border-subtle rounded text-primary-container focus:ring-0 transition-all" 
                      type="checkbox" 
                    />
                    <CheckSquare className="absolute w-3 h-3 text-white opacity-0 peer-checked:opacity-100 transition-opacity pointer-events-none" />
                  </div>
                  <span className="text-sm text-on-surface-variant group-hover:text-on-surface transition-colors font-medium">{s}</span>
                </label>
              ))}
            </div>
          </div>

          <div className="space-y-4">
            <h4 className="text-[11px] font-black text-on-surface uppercase tracking-widest flex items-center gap-2">
              <User className="w-3.5 h-3.5 text-primary" /> Người phát biểu
            </h4>
            <div className="flex flex-wrap gap-2">
              {['Nguyễn Quốc Sinh', 'Phạm Minh Chính', 'Lê Anh Tú'].map((n, i) => (
                <button 
                  key={n} 
                  className={`px-3 py-1.5 rounded-lg text-[11px] font-bold transition-all border
                    ${i === 0 ? 'bg-primary-container text-white border-transparent shadow-lg' : 'bg-surface-container-highest text-on-surface border-border-subtle hover:border-primary/50'}
                  `}
                >
                  {n}
                </button>
              ))}
            </div>
          </div>

          <div className="space-y-4">
            <h4 className="text-[11px] font-black text-on-surface uppercase tracking-widest flex items-center gap-2">
              <History className="w-3.5 h-3.5 text-primary" /> Khoảng thời gian
            </h4>
            <div className="flex flex-col gap-3">
              {['2023-01-01', '2023-12-31'].map((d, i) => (
                <div key={i} className="relative group/input">
                  <input 
                    className="w-full bg-surface-container border border-border-subtle rounded-xl px-3 py-2 text-[11px] text-on-surface outline-none focus:border-primary/50 transition-all font-mono" 
                    defaultValue={d}
                    type="date" 
                  />
                </div>
              ))}
            </div>
          </div>

          <div className="space-y-4 pt-4 border-t border-border-subtle/30">
            <h4 className="text-[11px] font-black text-on-surface uppercase tracking-widest flex items-center justify-between">
              Độ liên quan
              <span className="text-primary font-mono text-xs">80%+</span>
            </h4>
            <div className="px-1">
              <input 
                className="w-full h-1 bg-surface-container-highest rounded-lg appearance-none cursor-pointer accent-primary-container" 
                max="100" min="0" defaultValue="80"
                type="range" 
              />
            </div>
            <div className="flex items-center gap-2 mt-4 p-3 bg-match-high/5 rounded-xl border border-match-high/20">
              <Verified className="text-match-high w-4 h-4 shrink-0" />
              <span className="text-on-surface-variant text-[11px] font-bold leading-tight">Chỉ hiển thị Semantic Match</span>
            </div>
          </div>
        </aside>

        {/* Results List Center */}
        <section className="flex-1 overflow-y-auto p-8 custom-scrollbar">
          <div className="max-w-4xl mx-auto flex flex-col gap-6">
            {MOCK_MEETINGS.map((result, index) => (
              <motion.article 
                key={result.id}
                initial={{ opacity: 0, y: 30 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: index * 0.1, duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
                className="glass-panel p-7 rounded-2xl hover:bg-white transition-all duration-500 group cursor-pointer relative overflow-hidden active:scale-[0.99] hover:shadow-[0_20px_50px_-12px_rgba(0,0,0,0.08)]"
              >
                <div className="absolute top-0 left-0 w-1 h-full bg-primary-container opacity-0 group-hover:opacity-100 transition-opacity"></div>
                
                <div className="flex justify-between items-start mb-4">
                  <div className="flex flex-col gap-2">
                    <div className="flex items-center gap-3">
                      <span className="px-2 py-0.5 bg-surface-container-highest text-[9px] font-black tracking-widest text-primary rounded ring-1 ring-primary/20">{result.id}</span>
                      <span className="px-2 py-0.5 bg-blue-900/10 text-blue-400 text-[9px] font-black tracking-widest rounded border border-blue-900/20">{result.source}</span>
                    </div>
                    <h2 className="text-xl font-bold text-on-surface group-hover:text-primary transition-colors leading-tight">{result.title}</h2>
                    <div className="flex items-center gap-4 text-on-surface-variant text-[11px] font-bold">
                      <span className="flex items-center gap-1.5"><Calendar className="w-3.5 h-3.5" /> {result.date}</span>
                      <span className="flex items-center gap-1.5 opacity-60"><Search className="w-3.5 h-3.5" /> {result.location}</span>
                    </div>
                  </div>
                  <div className="flex flex-col items-end">
                    <div className="px-4 py-1.5 bg-match-high/10 border border-match-high/30 rounded-full flex items-center gap-2 group-hover:bg-match-high/20 transition-all">
                      <span className="text-match-high font-black italic font-mono text-sm tracking-tighter">0.{(result.relevance*10).toFixed(0)}</span>
                      <span className="text-match-high text-[10px] font-black uppercase tracking-widest">Score</span>
                    </div>
                    <span className="text-[9px] font-black text-on-surface-variant mt-2 uppercase tracking-[0.2em] opacity-40">Semantic Relevance</span>
                  </div>
                </div>

                <div className="flex items-center gap-4 mb-5 p-3 bg-surface-container-lowest/50 rounded-xl border border-border-subtle/30 group-hover:border-primary/20 transition-all">
                  <span className="text-[9px] font-black text-primary uppercase tracking-[0.2em] w-20 shrink-0">Tham gia:</span>
                  <div className="flex -space-x-2 shrink-0">
                    {result.participants.slice(0, 2).map((p) => (
                      <img key={p.id} className="w-7 h-7 rounded-full border-2 border-surface shadow-lg" src={p.avatar} alt={p.name} />
                    ))}
                    {result.participants.length > 2 && (
                      <div className="w-7 h-7 rounded-full border-2 border-surface bg-surface-container-highest flex items-center justify-center text-[10px] font-black text-white shadow-lg">+{result.participants.length - 2}</div>
                    )}
                  </div>
                  <span className="text-xs text-on-surface font-semibold truncate group-hover:text-primary transition-colors">{result.participants.map(p => p.name).join(', ')}</span>
                </div>

                <div className="bg-surface-container-lowest border-l-4 border-primary-container p-5 rounded-r-2xl relative overflow-hidden">
                  <div className="absolute top-0 right-0 w-32 h-32 bg-primary-container/5 blur-3xl rounded-full -translate-y-1/2 translate-x-1/2"></div>
                  <p className="text-on-surface-variant font-mono text-[13px] leading-relaxed relative z-10">
                    {result.snippet?.split(/(anh Sinh|Nghị định 105)/gi).map((part, i) => (
                      <span key={i} className={/(anh Sinh|Nghị định 105)/i.test(part) ? 'text-primary font-black bg-primary/10 px-0.5 rounded shadow-[0_0_10px_rgba(238,0,51,0.1)]' : ''}>
                        {part}
                      </span>
                    ))}
                  </p>
                </div>
              </motion.article>
            ))}
          </div>
        </section>
      </div>

      {/* Floating AI Action */}
      <div className="fixed bottom-10 right-10 flex flex-col items-end gap-5 z-50">
        {showAiChat && (
          <motion.div 
            initial={{ opacity: 0, scale: 0.9, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            className="glass-panel p-5 rounded-2xl max-w-xs shadow-2xl mb-2 border-primary/30"
          >
            <p className="text-sm font-semibold text-on-surface leading-relaxed">
              Bạn có muốn tôi tóm tắt các nội dung liên quan đến <span className="text-primary font-black uppercase tracking-wider">anh Sinh</span> trong bộ dữ liệu này không?
            </p>
            <div className="mt-4 flex gap-2">
              <button className="flex-1 py-2 bg-primary-container text-white rounded-lg text-[10px] font-black uppercase tracking-widest shadow-lg">Có, tóm tắt ngay</button>
              <button onClick={() => setShowAiChat(false)} className="px-4 py-2 bg-surface-container-highest text-on-surface-variant rounded-lg text-[10px] font-black uppercase tracking-widest">Bỏ qua</button>
            </div>
          </motion.div>
        )}
        <button 
          onClick={() => setShowAiChat(!showAiChat)}
          className={`w-16 h-16 bg-primary-container text-white rounded-full shadow-[0_10px_30px_rgba(238,0,51,0.4)] flex items-center justify-center hover:scale-110 active:scale-95 transition-all
            ${showAiChat ? 'rotate-12 scale-110 ring-4 ring-primary/20' : ''}
          `}
        >
          <Brain className="w-8 h-8" />
        </button>
      </div>
    </div>
  );
}
