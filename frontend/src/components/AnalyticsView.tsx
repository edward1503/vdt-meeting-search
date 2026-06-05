import { 
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  BarChart, Bar, Cell
} from 'recharts';
import { RefreshCw, TrendingUp, TrendingDown, CheckCircle, Database, RefreshCcw, Hourglass, Download, Activity } from 'lucide-react';
import { motion } from 'motion/react';

const PERFORMANCE_DATA = [
  { name: '08:00', precision: 88, recall: 82 },
  { name: '10:00', precision: 92, recall: 85 },
  { name: '12:00', precision: 90, recall: 88 },
  { name: '14:00', precision: 94, recall: 90 },
  { name: '16:00', precision: 92, recall: 88 },
];

const RELEVANCE_DATA = [
  { category: 'Transcript Search', content: 94.2, metadata: 72.1 },
  { category: 'Action Item Extraction', content: 88.5, metadata: 91.0 },
  { category: 'Speaker Identification', content: 62.0, metadata: 98.4 },
];

export default function AnalyticsView() {
  return (
    <div className="space-y-10 data-grid-pattern pb-12">
      {/* Analytics Header */}
      <header className="flex justify-between items-end mb-8">
        <div>
          <h2 className="text-3xl font-bold text-on-surface">Analytics Engine</h2>
          <p className="text-on-surface-variant text-lg">Precision monitoring and system health dashboard.</p>
        </div>
        <div className="flex gap-3">
          <div className="flex items-center gap-2 bg-surface-container-high px-4 py-2 rounded-xl border border-border-subtle shadow-lg overflow-hidden relative">
            <span className="w-2 h-2 rounded-full bg-match-high animate-pulse"></span>
            <span className="text-[10px] font-bold uppercase tracking-widest text-on-surface">Live Sync Active</span>
          </div>
          <button className="bg-surface-elevated border border-border-subtle p-2.5 rounded-xl hover:bg-surface-container-highest transition-all active:scale-95">
            <RefreshCw className="w-5 h-5 text-on-surface-variant hover:text-primary transition-colors" />
          </button>
        </div>
      </header>

      {/* Metrics Row */}
      <section className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {[
          { label: 'Precision', value: '92%', trend: '+2.4%', icon: TrendingUp, color: 'text-match-high' },
          { label: 'Recall', value: '88%', trend: '-0.5%', icon: TrendingDown, color: 'text-match-medium' },
          { label: 'MRR', value: '0.85', target: '0.90', detail: 'Rank performance index' },
          { label: 'Latency', value: '120ms', icon: CheckCircle, detail: 'Optimal', color: 'text-match-high' }
        ].map((metric, i) => (
          <motion.div 
            key={metric.label}
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: i * 0.1 }}
            className="bg-surface-elevated p-6 rounded-2xl border border-border-subtle hover:border-primary/30 transition-all group relative overflow-hidden"
          >
            <div className="flex justify-between items-start mb-4">
              <span className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest">{metric.label}</span>
              {metric.trend ? (
                <span className={`${metric.color} font-mono text-[11px] flex items-center font-bold`}>
                  <metric.icon className="w-3.5 h-3.5 mr-1" />
                  {metric.trend}
                </span>
              ) : metric.target ? (
                 <span className="text-on-surface-variant font-mono text-[11px]">Target: {metric.target}</span>
              ) : metric.detail && metric.icon ? (
                <span className={`${metric.color} font-mono text-[11px] flex items-center font-bold`}>
                  <metric.icon className="w-3.5 h-3.5 mr-1" />
                  {metric.detail}
                </span>
              ) : null}
            </div>
            <div className="flex items-baseline gap-2 mb-4">
              <span className="text-5xl font-black text-on-surface tracking-tighter">
                {metric.value.toString().replace('%', '')}
                <span className="text-primary text-2xl ml-0.5">{metric.value.toString().includes('%') ? '%' : metric.label === 'Latency' ? 'ms' : ''}</span>
              </span>
            </div>
            
            {/* Sparkline simulation or bar */}
            <div className="h-12 w-full flex items-end gap-1">
              {[60, 40, 70, 55, 85, 65, 90].map((h, j) => (
                <div 
                  key={j} 
                  className={`w-full transition-all duration-500 rounded-t-sm
                    ${j === 6 ? 'bg-primary-container h-[90%]' : 'bg-primary/10 h-['+h+'%] group-hover:bg-primary/20'}
                  `}
                ></div>
              ))}
            </div>
            {metric.detail && !metric.icon && <p className="text-[11px] text-on-surface-variant mt-2 italic">{metric.detail}</p>}
          </motion.div>
        ))}
      </section>

      {/* Charts Section */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <motion.div 
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4 }}
          className="lg:col-span-2 bg-surface-elevated rounded-2xl border border-border-subtle p-8"
        >
          <div className="flex justify-between items-center mb-8">
            <div>
              <h3 className="text-xl font-bold text-on-surface">Relevance by Category</h3>
              <p className="text-on-surface-variant text-sm">Content vs Metadata search quality benchmarks</p>
            </div>
            <div className="flex gap-4">
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 bg-primary-container rounded-sm"></div>
                <span className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest">Content</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 bg-secondary rounded-sm"></div>
                <span className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest">Metadata</span>
              </div>
            </div>
          </div>
          
          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={RELEVANCE_DATA} layout="vertical" barGap={8}>
                <XAxis type="number" hide domain={[0, 100]} />
                <YAxis 
                  dataKey="category" 
                  type="category" 
                  axisLine={false} 
                  tickLine={false} 
                  width={150} 
                  tick={{ fill: 'var(--color-on-surface-variant)', fontSize: 11, fontWeight: 700 }}
                />
                <Tooltip 
                  cursor={{ fill: 'rgba(255,255,255,0.05)' }}
                  contentStyle={{ backgroundColor: 'var(--color-surface-elevated)', border: '1px solid var(--color-border-subtle)', borderRadius: '8px' }}
                />
                <Bar dataKey="content" fill="#ee0033" radius={[0, 4, 4, 0]} barSize={12} />
                <Bar dataKey="metadata" fill="#c6c6c9" radius={[0, 4, 4, 0]} barSize={12} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </motion.div>

        {/* Pipeline Status */}
        <motion.div 
           initial={{ opacity: 0, y: 20 }}
           animate={{ opacity: 1, y: 0 }}
           transition={{ delay: 0.5 }}
          className="bg-surface-elevated rounded-2xl border border-border-subtle p-8"
        >
          <h3 className="text-xl font-bold text-on-surface mb-8">Pipeline Status</h3>
          <div className="space-y-8 relative">
            <div className="absolute left-4 top-4 bottom-4 w-[1px] bg-border-subtle/50"></div>
            {[
              { id: 1, label: 'Preprocessing', detail: '84.2 ms / chunk', status: 'done' },
              { id: 2, label: 'Embedding Generation', detail: 'TensorFlow Core (GPU-0)', status: 'done' },
              { id: 3, label: 'Indexing (Milvus)', detail: 'Writing partition: H1_2024', status: 'active' },
              { id: 4, label: 'Retrieval', detail: 'Queue: Idle', status: 'idle' }
            ].map((step) => (
              <div key={step.id} className="flex items-start gap-5 relative z-10">
                <div className={`flex-shrink-0 w-8 h-8 rounded-full border-2 flex items-center justify-center transition-all bg-surface-elevated
                  ${step.status === 'done' ? 'border-match-high text-match-high' : 
                    step.status === 'active' ? 'border-primary-container text-primary-container animate-pulse h-9 w-9 -ml-0.5' : 
                    'border-border-subtle text-on-surface-variant opacity-50'}
                `}>
                  {step.status === 'done' && <CheckCircle className="w-5 h-5" />}
                  {step.status === 'active' && <RefreshCcw className="w-5 h-5" />}
                  {step.status === 'idle' && <Hourglass className="w-5 h-5" />}
                </div>
                <div>
                  <h4 className={`text-[11px] font-bold uppercase tracking-[0.15em] ${step.status === 'idle' ? 'text-on-surface-variant opacity-50' : 'text-on-surface'}`}>
                    {step.label}
                  </h4>
                  <p className={`font-mono text-[11px] mt-1 ${step.status === 'idle' ? 'text-on-surface-variant opacity-30' : 'text-on-surface-variant'}`}>{step.detail}</p>
                </div>
              </div>
            ))}
          </div>
        </motion.div>
      </div>

      {/* Benchmarks Table */}
      <motion.section 
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.6 }}
        className="bg-surface-elevated rounded-2xl border border-border-subtle overflow-hidden shadow-2xl"
      >
        <div className="p-8 border-b border-border-subtle flex justify-between items-center bg-surface-container-low/50">
          <div>
            <h3 className="text-xl font-bold text-on-surface">Evaluation Benchmarks</h3>
            <p className="text-on-surface-variant text-sm">Embedding model comparative analysis (Q3-2024)</p>
          </div>
          <button className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-widest bg-surface-container-highest px-5 py-2.5 rounded-xl border border-border-subtle hover:bg-surface-bright transition-all shadow-lg active:scale-95">
            <Download className="w-4 h-4 text-primary" />
            Export CSV
          </button>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead className="bg-surface-container-low/80 text-on-surface-variant font-bold text-[10px] uppercase tracking-[0.2em] sticky top-0">
              <tr>
                <th className="px-8 py-5">Model Identity</th>
                <th className="px-8 py-5">NDC@10</th>
                <th className="px-8 py-5">Recall@5</th>
                <th className="px-8 py-5">Dim Size</th>
                <th className="px-8 py-5">Throughput</th>
                <th className="px-8 py-5">Status</th>
              </tr>
            </thead>
            <tbody className="font-mono text-[12px] divide-y divide-border-subtle/20">
              {[
                { name: 'SentenceTransformers/All-MiniLM-L6-v2', ndc: '0.782', recall: '0.841', dim: 384, tp: '1200 req/s', status: 'LEGACY' },
                { name: 'HuggingFace/BAAI-BGE-Base-En-v1.5', ndc: '0.892', recall: '0.915', dim: 768, tp: '450 req/s', status: 'ACTIVE', current: true },
                { name: 'SentenceTransformers/GTE-Large', ndc: '0.875', recall: '0.898', dim: 1024, tp: '180 req/s', status: 'TESTING' },
                { name: 'Cohere/Embed-English-v3', ndc: '0.912', recall: '0.934', dim: 1024, tp: '95 req/s', status: 'API_TIER' },
              ].map((row, i) => (
                <tr key={row.name} className={`group transition-colors ${row.current ? 'bg-primary-container/[0.05] border-l-2 border-primary-container' : 'hover:bg-surface-container-highest/50'}`}>
                  <td className="px-8 py-5 font-bold text-primary group-hover:text-on-surface transition-colors">{row.name}</td>
                  <td className={`px-8 py-5 ${row.current ? 'text-match-high font-bold' : ''}`}>{row.ndc}</td>
                  <td className={`px-8 py-5 ${row.current ? 'text-match-high font-bold' : ''}`}>{row.recall}</td>
                  <td className="px-8 py-5">{row.dim}</td>
                  <td className="px-8 py-5 opacity-60 uppercase">{row.tp}</td>
                  <td className="px-8 py-5">
                    <span className={`px-2 py-0.5 rounded text-[9px] font-black tracking-widest
                      ${row.current ? 'bg-primary-container text-white' : 'bg-surface-variant text-on-surface-variant'}
                    `}>
                      {row.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </motion.section>
    </div>
  );
}
