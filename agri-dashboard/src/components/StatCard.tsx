import { useEffect, useRef, useState, type ReactNode } from 'react';

interface StatCardProps {
  icon: ReactNode;
  label: string;
  value: string | number;
  unit?: string;
  accentColor?: string;     // Tailwind class e.g. 'text-emerald-400'
  accentBg?: string;        // Tailwind class e.g. 'bg-emerald-500/10'
  accentBorder?: string;    // Tailwind class e.g. 'border-emerald-500/20'
  subtext?: string;
}

function useCountUp(target: number, duration = 750) {
  const [val, setVal] = useState(0);
  const frame = useRef<number | null>(null);
  useEffect(() => {
    const start = performance.now();
    const tick = (now: number) => {
      const p = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - p, 3);
      setVal(parseFloat((target * eased).toFixed(3)));
      if (p < 1) frame.current = requestAnimationFrame(tick);
    };
    frame.current = requestAnimationFrame(tick);
    return () => { if (frame.current) cancelAnimationFrame(frame.current); };
  }, [target, duration]);
  return val;
}

export function StatCard({
  icon,
  label,
  value,
  unit,
  accentColor  = 'text-emerald-400',
  accentBg     = 'bg-emerald-500/10',
  accentBorder = 'border-emerald-500/20',
  subtext,
}: StatCardProps) {
  const numeric = typeof value === 'number' ? value : parseFloat(String(value));
  const isNum   = !isNaN(numeric);
  const counted = useCountUp(isNum ? numeric : 0);

  const display = isNum
    ? (numeric % 1 !== 0 ? counted.toFixed(1) : Math.round(counted).toString())
    : value;

  return (
    <div
      className={`
        relative glass-panel px-4 py-3.5 flex items-center gap-3.5
        border ${accentBorder}
        hover:-translate-y-0.5 hover:shadow-lg hover:shadow-black/20
        transition-all duration-200
        animate-slide-up
        overflow-hidden
        group
      `}
    >
      {/* Subtle hover shimmer */}
      <div className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-300 bg-gradient-to-r from-transparent via-white/[0.02] to-transparent pointer-events-none" />

      {/* Icon badge */}
      <div className={`w-10 h-10 rounded-xl ${accentBg} flex items-center justify-center flex-shrink-0 ${accentColor} transition-transform duration-200 group-hover:scale-105`}>
        {icon}
      </div>

      {/* Value */}
      <div className="min-w-0 flex-1">
        <p className="text-[11px] font-medium text-slate-500 leading-none mb-1">{label}</p>
        <p className={`font-[var(--font-mono)] font-semibold text-xl leading-none ${accentColor} tabular-nums`}>
          {display}
          {unit && <span className="text-xs ml-1 text-slate-500 font-[var(--font-sans)] font-normal">{unit}</span>}
        </p>
        {subtext && <p className="text-[10px] text-slate-600 mt-1">{subtext}</p>}
      </div>
    </div>
  );
}
