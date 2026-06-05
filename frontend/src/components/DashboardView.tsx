import { MOCK_MEETINGS } from '../constants';
import { Database, TrendingUp, History, Activity, Bolt, Calendar, Building2, BookOpen } from 'lucide-react';
import { motion } from 'motion/react';

export default function DashboardView() {
  const stats = [
    { label: 'Total Meetings Indexed', value: '1,240', trend: '+12%', icon: Database, color: 'text-primary' },
    { label: 'System Status', value: 'Active', status: 'optimal', icon: Activity, detail: '54 streams / min' }
  ];

  const recentQueries = [
    'Reviewing Decree 105 implementation...',
    'VTS technical debt assessment Q3...',
    'AI policy updates in Viettel networks...'
  ];

  return (
    <div className="space-y-12">
      {/* Hero Section */}
      <section className="flex flex-col items-center justify-center text-center space-y-8 py-12">
        <motion.div 
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="max-w-4xl w-full"
        >
          <h1 className="text-5xl md:text-6xl font-black mb-4 tracking-tight text-on-surface">
            Precision Meeting Intelligence
          </h1>
          <p className="text-on-surface-variant text-lg md:text-xl max-w-2xl mx-auto mb-10 leading-relaxed">
            Access corporate collective memory through AI-powered semantic search across all your organization's recorded sessions.
          </p>
          
          <div className="relative group max-w-3xl mx-auto">
            <div className="absolute -inset-1 bg-gradient-to-r from-primary-container to-tertiary-container rounded-2xl blur opacity-25 group-focus-within:opacity-50 transition duration-1000"></div>
            <div className="relative flex items-center glass-panel rounded-2xl p-2 shadow-xl overflow-hidden border-primary/10">
              <span className="pl-4 text-on-surface-variant font-mono text-[11px] opacity-60 shrink-0 uppercase tracking-widest">Ask VDT:</span>
              <input 
                className="w-full bg-transparent border-none focus:ring-0 text-on-surface text-lg px-3 py-4 placeholder:text-on-surface-variant placeholder:opacity-30" 
                placeholder="Ví dụ: Tìm các cuộc họp về Nghị định 105 có sự tham gia của anh Sinh..." 
                type="text" 
              />
              <button className="bg-primary-container hover:bg-[#d0002d] text-white px-8 py-4 rounded-xl font-bold transition-all flex items-center gap-2 active:scale-95 shadow-lg">
                <Bolt className="w-5 h-5 fill-current" />
                Search
              </button>
            </div>
          </div>

          {/* Quick Filters */}
          <div className="mt-8 flex flex-wrap justify-center gap-3">
            {[
              { icon: History, label: 'Hôm nay' },
              { icon: Calendar, label: 'Tuần này' },
              { icon: Building2, label: 'Đơn vị: VTS', active: true },
              { icon: BookOpen, label: 'Chủ đề: Kỹ thuật' }
            ].map((filter, i) => (
              <motion.span 
                key={filter.label}
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: 0.1 * i }}
                className={`px-4 py-1.5 rounded-full border border-border-subtle cursor-pointer transition-all text-[11px] font-bold uppercase tracking-wider flex items-center gap-2
                  ${filter.active ? 'bg-primary-container/10 border-primary-container text-primary-container' : 'bg-surface-container hover:bg-surface-container-high text-on-surface-variant'}
                `}
              >
                <filter.icon className="w-3.5 h-3.5" />
                {filter.label}
              </motion.span>
            ))}
          </div>
        </motion.div>
      </section>

      {/* Grid Overview */}
      <section className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {stats.map((stat, i) => (
          <motion.div 
            key={stat.label}
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.2 + (i * 0.1) }}
            className="glass-panel rounded-2xl p-6 flex flex-col justify-between group overflow-hidden relative"
          >
            <div className="absolute -right-4 -top-4 text-[120px] text-on-surface-variant opacity-[0.03] group-hover:opacity-10 transition-opacity">
              <stat.icon className="w-full h-full" />
            </div>
            <div>
              <span className="text-[10px] font-bold text-on-surface-variant uppercase tracking-[0.2em]">{stat.label}</span>
              <div className="flex items-center gap-3 mt-2">
                {stat.status === 'optimal' && (
                  <div className="relative flex h-3 w-3">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-match-high opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-3 w-3 bg-match-high"></span>
                  </div>
                )}
                <h2 className={`text-4xl font-black ${stat.color || 'text-on-surface'}`}>{stat.value}</h2>
              </div>
            </div>
            {stat.trend && (
              <div className="mt-4 flex items-center text-match-high text-[11px] font-bold gap-1">
                <TrendingUp className="w-4 h-4" />
                <span>{stat.trend} vs last month</span>
              </div>
            )}
            {stat.detail && (
              <div className="mt-4 pt-4 border-t border-border-subtle">
                <p className="font-mono text-[11px] text-on-surface-variant">Real-time indexing: <span className="text-on-surface">{stat.detail}</span></p>
              </div>
            )}
          </motion.div>
        ))}

        {/* Recent Queries Card */}
        <motion.div 
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.4 }}
          className="glass-panel rounded-2xl p-6 flex flex-col gap-4"
        >
          <span className="text-[10px] font-bold text-on-surface-variant uppercase tracking-[0.2em]">Recent Semantic Queries</span>
          <ul className="space-y-3">
            {recentQueries.map((query) => (
              <li key={query} className="flex items-start gap-3 group cursor-pointer">
                <History className="text-primary-container w-4 h-4 mt-0.5 shrink-0" />
                <span className="text-[13px] text-on-surface border-b border-border-subtle group-hover:border-primary-container transition-all pb-1 leading-snug">
                  {query}
                </span>
              </li>
            ))}
          </ul>
        </motion.div>
      </section>

      {/* Recent Meetings Table */}
      <section className="space-y-6">
        <div className="flex items-center justify-between">
          <h3 className="text-xl font-bold flex items-center gap-2">
            <Activity className="text-primary w-5 h-5" />
            Intelligence Feed: Recent Meetings
          </h3>
          <button className="text-[11px] font-bold text-primary hover:underline uppercase tracking-wider">View all sessions</button>
        </div>
        <div className="overflow-hidden rounded-2xl border border-border-subtle glass-panel">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-surface-container-high/50 text-on-surface-variant text-[10px] font-bold uppercase tracking-[0.15em]">
                <th className="px-6 py-4">Meeting Title</th>
                <th className="px-6 py-4">Date & Time</th>
                <th className="px-6 py-4 text-center">Relevance</th>
              </tr>
            </thead>
            <tbody className="text-[13px] text-on-surface divide-y divide-border-subtle/30">
              {MOCK_MEETINGS.map((meeting, i) => (
                <motion.tr 
                  key={meeting.id}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.5 + (i * 0.05) }}
                  className="hover:bg-primary-container/[0.03] transition-colors group cursor-pointer"
                >
                  <td className="px-6 py-5 font-bold group-hover:text-primary transition-colors">{meeting.title}</td>
                  <td className="px-6 py-5 text-on-surface-variant font-mono text-[11px]">{meeting.date} • {meeting.time}</td>
                  <td className="px-6 py-5">
                    <div className="flex flex-col gap-1.5 items-end">
                      <div className="w-32 bg-surface-container-highest rounded-full h-1.5 overflow-hidden">
                        <div 
                          className={`h-full rounded-full ${meeting.relevance > 80 ? 'bg-match-high' : meeting.relevance > 60 ? 'bg-match-medium' : 'bg-match-low'}`} 
                          style={{ width: `${meeting.relevance}%` }}
                        ></div>
                      </div>
                      <span className="text-[10px] font-bold font-mono opacity-50">{meeting.relevance}% Match</span>
                    </div>
                  </td>
                </motion.tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
