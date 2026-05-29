import { type ReactNode, useState } from 'react';
import { Loader2, ChevronDown, ChevronUp } from 'lucide-react';

interface AgentReportCardProps {
  title: string;
  icon: ReactNode;
  content?: string;
  loadingMessage?: string;
  accentColor?: string;     // e.g. 'text-blue-400'
  accentBg?: string;        // e.g. 'bg-blue-500/10'
  accentBorder?: string;    // e.g. 'border-blue-500/20'
  confidence?: number;
}

function SkeletonRows() {
  return (
    <div className="space-y-2.5 py-1" aria-label="Loading…">
      {[95, 80, 88, 65, 75, 58].map((w, i) => (
        <div key={i} className="skeleton h-3 rounded" style={{ width: `${w}%`, animationDelay: `${i * 0.08}s` }} />
      ))}
    </div>
  );
}

function ConfidenceBar({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const { color, label, bg } =
    pct >= 70 ? { color: '#10b981', label: 'High',   bg: 'rgba(16,185,129,0.1)'  } :
    pct >= 40 ? { color: '#f59e0b', label: 'Medium', bg: 'rgba(245,158,11,0.1)'  } :
                { color: '#ef4444', label: 'Low',    bg: 'rgba(239,68,68,0.1)'   };

  return (
    <div className="mt-4 pt-4 border-t border-white/[0.05]">
      <div className="flex justify-between items-center mb-2">
        <span className="section-label">AI Confidence</span>
        <span
          className="text-[11px] font-semibold font-[var(--font-mono)] tabular-nums px-2 py-0.5 rounded-full"
          style={{ color, backgroundColor: bg }}
        >
          {label} · {pct}%
        </span>
      </div>
      <div className="h-1.5 rounded-full bg-slate-800 overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-700"
          style={{ width: `${pct}%`, backgroundColor: color, animation: 'progress-in 0.8s ease both' }}
        />
      </div>
    </div>
  );
}

const COLLAPSE_CHARS = 450;

export function AgentReportCard({
  title,
  icon,
  content,
  loadingMessage = 'Consulting agent…',
  accentColor  = 'text-slate-300',
  accentBg     = 'bg-slate-500/10',
  accentBorder = 'border-slate-500/20',
  confidence,
}: AgentReportCardProps) {
  const [collapsed, setCollapsed] = useState(false);
  const isLong = (content?.length ?? 0) > COLLAPSE_CHARS;

  // Extract the CSS color variable for the top stripe by parsing accent class
  const stripeColor =
    accentBorder.includes('blue')    ? 'from-blue-500'    :
    accentBorder.includes('emerald') ? 'from-emerald-500' :
    accentBorder.includes('amber')   ? 'from-amber-500'   :
    accentBorder.includes('red')     ? 'from-red-500'     :
    accentBorder.includes('purple')  ? 'from-purple-500'  :
    'from-slate-500';

  return (
    <div className={`glass-panel overflow-hidden border ${accentBorder} animate-slide-up`}>
      {/* Top accent stripe */}
      <div className={`h-0.5 w-full bg-gradient-to-r ${stripeColor} to-transparent`} aria-hidden />

      {/* Header */}
      <div className="flex items-center gap-3 px-5 py-4 border-b border-white/[0.05]">
        <div className={`w-8 h-8 rounded-xl ${accentBg} flex items-center justify-center flex-shrink-0 ${accentColor}`}>
          {icon}
        </div>
        <h2 className={`font-semibold text-sm flex-1 text-white`}>{title}</h2>
        {isLong && content && (
          <button
            onClick={() => setCollapsed(c => !c)}
            className="flex items-center gap-1.5 text-[11px] text-slate-500 hover:text-slate-300 transition-colors px-2 py-1 rounded-lg hover:bg-white/[0.04]"
          >
            {collapsed ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronUp className="w-3.5 h-3.5" />}
            {collapsed ? 'Expand' : 'Collapse'}
          </button>
        )}
      </div>

      {/* Body */}
      <div className="px-5 py-4">
        {content ? (
          <div className="relative">
            <p className={`text-sm text-slate-300 leading-relaxed whitespace-pre-wrap transition-all duration-300 ${
              collapsed && isLong ? 'max-h-28 overflow-hidden' : ''
            }`}>
              {content}
            </p>
            {collapsed && isLong && (
              <div className="absolute bottom-0 left-0 right-0 h-14 bg-gradient-to-t from-[#0f172a] to-transparent pointer-events-none" />
            )}
          </div>
        ) : (
          <div>
            <div className="flex items-center gap-2.5 text-slate-500 mb-4">
              <Loader2 className="w-3.5 h-3.5 animate-spin-icon flex-shrink-0" />
              <span className="text-xs">{loadingMessage}</span>
            </div>
            <SkeletonRows />
          </div>
        )}

        {/* Confidence bar — only shown when we have content */}
        {confidence !== undefined && content && <ConfidenceBar value={confidence} />}
      </div>
    </div>
  );
}
