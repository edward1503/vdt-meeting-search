import { MOCK_MEETINGS } from '../constants';
import { 
  FileText, Share2, Link as LinkIcon, Calendar, MapPin, Clock, 
  Terminal, Shield, Users, Tag, BarChart2, CheckCircle2 
} from 'lucide-react';
import { motion } from 'motion/react';

export default function MeetingDetailView() {
  const meeting = MOCK_MEETINGS[0];

  const transcript = [
    { time: '00:02:15', speaker: 'Anh Sinh', text: 'Chào mọi người. Hôm nay chúng ta tập trung thảo luận về kế hoạch hành động cụ thể để đáp ứng các yêu cầu mới trong ', highlight: 'Nghị định 105 về quản lý dữ liệu số', suffix: '. Đây là nhiệm vụ trọng tâm của quý này.' },
    { time: '00:05:40', speaker: 'Chị Lan (VTS)', text: 'Về phía kỹ thuật, chúng tôi đã rà soát lại hạ tầng. Tuy nhiên, việc đồng bộ hóa dữ liệu giữa các đơn vị thành viên vẫn còn gặp khó khăn do định dạng không thống nhất. Chúng ta cần một bộ tiêu chuẩn chung.' },
    { time: '00:12:20', speaker: 'Anh Sinh', text: 'Đúng vậy. ', highlight: 'Tôi đề nghị Chị Lan chủ trì nhóm công tác để hoàn thành bộ tiêu chuẩn dữ liệu theo hướng dẫn tại Điều 12 của Nghị định 105 trước ngày 30/11', suffix: '. Đây là mốc thời gian không thể trì hoãn.' },
    { time: '00:18:45', speaker: 'Anh Bình (VTS)', text: 'Tôi xin bổ sung thêm về phần kinh phí. Chúng ta cần dự toán ngân sách cho việc thuê chuyên gia tư vấn về an toàn bảo mật. Theo ', highlight: 'Nghị định 105', suffix: ', các hệ thống cấp 4 trở lên bắt buộc phải có đánh giá độc lập hàng năm.' },
    { time: '00:25:30', speaker: 'Anh Sinh', text: 'Bình chuẩn bị hồ sơ thầu nhé. Chúng ta sẽ áp dụng hình thức đấu thầu rộng rãi để đảm bảo tính minh bạch. Mọi quy trình phải bám sát tinh thần chuyển đổi số của tập đoàn.' },
  ];

  return (
    <div className="flex-1 flex overflow-hidden bg-background">
      {/* Document Content */}
      <section className="flex-1 overflow-y-auto custom-scrollbar p-12 relative">
        <div className="max-w-4xl mx-auto">
          {/* Document Header */}
          <header className="mb-12">
            <motion.div 
               initial={{ opacity: 0, y: 10 }}
               animate={{ opacity: 1, y: 0 }}
               className="flex items-start justify-between mb-6"
            >
              <h2 className="text-4xl font-black text-on-surface leading-tight tracking-tight max-w-2xl">{meeting.title}</h2>
              <div className="flex gap-2 shrink-0">
                <span className="px-3 py-1 bg-surface-container-highest text-primary font-mono text-[11px] font-bold rounded border border-border-subtle tracking-widest shadow-lg">CONFIDENTIAL</span>
              </div>
            </motion.div>
            
            <div className="flex flex-wrap gap-8 text-on-surface-variant text-[13px] font-bold uppercase tracking-wider">
              <div className="flex items-center gap-2.5">
                <Calendar className="w-4 h-4 text-primary" />
                <span>{meeting.date}</span>
              </div>
              <div className="flex items-center gap-2.5">
                <MapPin className="w-4 h-4 text-primary" />
                <span>{meeting.location}</span>
              </div>
              <div className="flex items-center gap-2.5">
                <Clock className="w-4 h-4 text-primary" />
                <span>{meeting.time} (150 mins)</span>
              </div>
            </div>
          </header>

          {/* Action Bar */}
          <div className="flex items-center justify-between mb-12 pb-6 border-b border-border-subtle/30 sticky top-0 bg-background/80 backdrop-blur-md z-10">
            <div className="flex gap-3">
              {[
                { label: 'Export PDF', icon: FileText },
                { label: 'Share', icon: Share2 },
                { label: 'Copy Link', icon: LinkIcon }
              ].map((btn) => (
                <button key={btn.label} className="px-5 py-2.5 border border-border-subtle hover:bg-surface-container-highest rounded-xl text-[11px] font-black uppercase tracking-widest flex items-center gap-2.5 transition-all active:scale-95 shadow-sm">
                  <btn.icon className="w-4 h-4 text-primary" />
                  {btn.label}
                </button>
              ))}
            </div>
            <div className="text-on-surface-variant text-[10px] font-black uppercase tracking-[0.2em] flex items-center gap-3 bg-match-high/5 px-4 py-2 rounded-full border border-match-high/20">
              <span className="w-2 h-2 bg-match-high rounded-full animate-pulse shadow-[0_0_8px_rgba(40,167,69,0.5)]"></span>
              98.2% Transcription Accuracy
            </div>
          </div>

          {/* Transcript Area */}
          <article className="space-y-12 text-on-surface leading-loose text-lg font-medium selection:bg-primary/20">
            {transcript.map((line, i) => (
              <motion.div 
                key={i}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.1 * i }}
                className="group relative"
              >
                <div className="flex items-center gap-6 mb-3">
                  <span className="font-mono text-on-surface-variant/40 text-[11px] font-bold w-16 shrink-0 tracking-widest">{line.time}</span>
                  <span className={`font-black text-[13px] uppercase tracking-[0.15em] ${line.speaker.includes('Sinh') ? 'text-primary' : 'text-secondary'}`}>
                    {line.speaker}
                  </span>
                </div>
                <p className="pl-22 transition-colors">
                  {line.text}
                  {line.highlight && (
                    <span className="bg-primary-container/10 border-l-4 border-primary-container pl-3 py-1 -ml-4 inline-block font-bold text-on-surface shadow-[inset_0_0_20px_rgba(238,0,51,0.05)] cursor-help group/tip relative">
                      {line.highlight}
                      <span className="absolute -top-10 left-0 bg-surface-elevated border border-primary/40 px-3 py-1.5 rounded-lg text-[10px] font-black text-primary opacity-0 group-hover/tip:opacity-100 transition-all shadow-2xl pointer-events-none whitespace-nowrap z-20">
                        SEMANTIC MATCH: {Math.floor(Math.random() * 10 + 90)}%
                      </span>
                    </span>
                  )}
                  {line.suffix}
                </p>
              </motion.div>
            ))}
            
            <div className="py-20 flex justify-center">
              <div className="flex items-center gap-6 text-on-surface-variant text-[10px] font-black tracking-[0.4em] uppercase opacity-30">
                <span className="w-24 h-[1px] bg-border-subtle"></span>
                End of Transcript
                <span className="w-24 h-[1px] bg-border-subtle"></span>
              </div>
            </div>
          </article>
        </div>
      </section>

      {/* Metadata Sidebar (Right) */}
      <aside className="w-[340px] bg-surface-container-low border-l border-border-subtle overflow-y-auto custom-scrollbar hidden xl:block p-8 space-y-12">
        <section className="space-y-5">
          <h3 className="text-[10px] font-black text-on-surface-variant uppercase tracking-[0.3em]">Unit / Department</h3>
          <div className="flex items-center gap-4 p-4 bg-surface-container rounded-2xl border border-border-subtle shadow-inner">
            <div className="w-10 h-10 bg-primary/10 rounded-xl flex items-center justify-center text-primary font-black text-lg border border-primary/20">V</div>
            <div>
              <p className="text-[13px] font-black text-on-surface">VTS</p>
              <p className="text-[11px] font-bold text-on-surface-variant opacity-60">Viettel Solutions</p>
            </div>
          </div>
        </section>

        <section className="space-y-5">
          <h3 className="text-[10px] font-black text-on-surface-variant uppercase tracking-[0.3em]">Participants (12)</h3>
          <div className="space-y-4">
            {meeting.participants.map((p) => (
              <div key={p.id} className="flex items-center gap-4 group cursor-pointer">
                <div className="relative">
                  <img alt={p.name} className="w-9 h-9 rounded-full ring-2 ring-transparent group-hover:ring-primary/40 transition-all" src={p.avatar} />
                  {p.role === 'Chair' && (
                     <div className="absolute -right-1 -bottom-1 bg-primary text-white p-0.5 rounded-full ring-2 border-surface">
                       <Shield className="w-2.5 h-2.5" />
                     </div>
                  )}
                </div>
                <span className={`text-[13px] font-bold transition-colors ${p.role === 'Chair' ? 'text-primary' : 'text-on-surface group-hover:text-primary'}`}>
                  {p.name}
                </span>
                {p.role === 'Chair' && (
                  <span className="ml-auto text-[8px] font-black px-2 py-0.5 bg-primary/10 text-primary rounded ring-1 ring-primary/20 tracking-widest">CHAIR</span>
                )}
              </div>
            ))}
            <button className="text-primary text-[11px] font-black uppercase tracking-widest mt-4 hover:underline flex items-center gap-2 group">
              View all
              <Users className="w-3.5 h-3.5 group-hover:translate-x-1 transition-transform" />
            </button>
          </div>
        </section>

        <section className="space-y-5">
          <h3 className="text-[10px] font-black text-on-surface-variant uppercase tracking-[0.3em]">Keywords</h3>
          <div className="flex flex-wrap gap-2.5">
            {meeting.keywords.map((word, i) => (
              <span key={word} className="px-3 py-1.5 bg-surface-container border border-border-subtle rounded-lg text-[10px] font-bold text-on-surface flex items-center gap-2 hover:bg-surface-bright transition-all cursor-default">
                <Tag className={`w-3 h-3 ${i < 2 ? 'text-primary' : 'text-tertiary'}`} />
                {word}
              </span>
            ))}
          </div>
        </section>

        <section className="space-y-5 pt-10 border-t border-border-subtle/30">
          <h3 className="text-[10px] font-black text-on-surface-variant uppercase tracking-[0.3em] flex items-center gap-2">
            <BarChart2 className="w-4 h-4 text-primary" />
            Meeting Insights
          </h3>
          <div className="bg-surface-elevated/50 p-5 rounded-2xl space-y-6 border border-border-subtle shadow-xl">
            <div className="space-y-2">
              <p className="text-[10px] font-black text-on-surface-variant uppercase tracking-widest mb-3">Sentiment Analysis</p>
              <div className="h-2 w-full bg-surface-container-highest rounded-full overflow-hidden flex shadow-inner">
                <div className="h-full bg-match-high w-[70%] shadow-[0_0_10px_rgba(40,167,69,0.4)]"></div>
                <div className="h-full bg-match-medium w-[20%]"></div>
                <div className="h-full bg-match-low w-[10%]"></div>
              </div>
              <div className="flex justify-between mt-2 text-[10px] font-black">
                <span className="text-match-high">POSITIVE</span>
                <span className="text-on-surface opacity-60">70%</span>
              </div>
            </div>
            
            <div className="space-y-4 pt-4 border-t border-border-subtle/20">
              <p className="text-[10px] font-black text-on-surface-variant uppercase tracking-widest">Key Entities</p>
              <ul className="text-[11px] font-bold space-y-3">
                {[
                  { label: 'Nghị định 105', count: 8 },
                  { label: 'Anh Sinh', count: 12 }
                ].map((entity) => (
                  <li key={entity.label} className="flex justify-between items-center group">
                    <span className="text-on-surface group-hover:text-primary transition-colors">{entity.label}</span>
                    <span className="text-[10px] font-mono bg-surface-container-highest px-2 py-0.5 rounded text-on-surface-variant">{entity.count} mentions</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </section>
      </aside>
    </div>
  );
}
