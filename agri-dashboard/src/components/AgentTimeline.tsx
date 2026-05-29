import { CheckCircle, Loader2, CloudRain, Leaf, BadgeDollarSign, Database, AlertTriangle, Zap } from 'lucide-react';
import { useEffect, useRef, useState, type ReactNode } from 'react';
import type { AgentStep } from '../types';

interface AgentTimelineProps {
  currentStep: AgentStep;
  loading: boolean;
}

type StepDef = {
  id: AgentStep | string;
  label: string;
  sub: string;
  icon: ReactNode;
  color: string;
  activeBg: string;
  dotColor: string;
  stripeFrom: string;
};

const STEPS: StepDef[] = [
  {
    id: 'sensors',
    label: 'Sensors',
    sub: 'Weather & soil',
    icon: <Database className="w-4 h-4" />,
    color: 'text-amber-400',
    activeBg: 'bg-amber-400/15 border-amber-400/50',
    dotColor: 'bg-amber-400',
    stripeFrom: 'from-amber-400',
  },
  {
    id: 'meteorologist',
    label: 'AI Agents',
    sub: 'Running parallel',
    icon: <CloudRain className="w-4 h-4" />,
    color: 'text-blue-400',
    activeBg: 'bg-blue-400/15 border-blue-400/50',
    dotColor: 'bg-blue-400',
    stripeFrom: 'from-blue-400',
  },
  {
    id: 'financial',
    label: 'Financials',
    sub: 'Synthesizing',
    icon: <BadgeDollarSign className="w-4 h-4" />,
    color: 'text-purple-400',
    activeBg: 'bg-purple-400/15 border-purple-400/50',
    dotColor: 'bg-purple-400',
    stripeFrom: 'from-purple-400',
  },
  {
    id: 'awaiting',
    label: 'Your Call',
    sub: 'Awaiting input',
    icon: <Leaf className="w-4 h-4" />,
    color: 'text-emerald-400',
    activeBg: 'bg-emerald-400/15 border-emerald-400/50',
    dotColor: 'bg-emerald-400',
    stripeFrom: 'from-emerald-400',
  },
  {
    id: 'done',
    label: 'Actuated',
    sub: 'Command sent',
    icon: <Zap className="w-4 h-4" />,
    color: 'text-emerald-400',
    activeBg: 'bg-emerald-400/15 border-emerald-400/50',
    dotColor: 'bg-emerald-400',
    stripeFrom: 'from-emerald-400',
  },
];

const STEP_ORDER: AgentStep[] = ['idle', 'sensors', 'meteorologist', 'financial', 'awaiting', 'done'];

function getStatus(id: string, cur: AgentStep): 'done' | 'active' | 'pending' {
  if (cur === 'error') return 'pending';
  const ci = STEP_ORDER.indexOf(cur), si = STEP_ORDER.indexOf(id as AgentStep);
  return si < ci ? 'done' : si === ci ? 'active' : 'pending';
}

function useElapsed(active: boolean) {
  const [s, setS] = useState(0);
  const ref = useRef<ReturnType<typeof setInterval> | null>(null);
  useEffect(() => {
    if (active) { setS(0); ref.current = setInterval(() => setS(n => n + 1), 1000); }
    else if (ref.current) clearInterval(ref.current);
    return () => { if (ref.current) clearInterval(ref.current); };
  }, [active]);
  return s;
}

export function AgentTimeline({ currentStep, loading }: AgentTimelineProps) {
  const elapsed = useElapsed(loading);
  if (currentStep === 'idle' && !loading) return null;

  const isError = currentStep === 'error';

  // Calculate overall progress percentage
  const curIdx = STEP_ORDER.indexOf(currentStep);
  const progressPct = isError ? 0 : Math.round((Math.max(0, curIdx - 1) / (STEPS.length)) * 100);

  return (
    <div className="glass-panel px-5 pt-4 pb-5 mb-5 animate-slide-up">
      {/* Header row */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          {isError
            ? <AlertTriangle className="w-3.5 h-3.5 text-red-400" />
            : <Loader2 className={`w-3.5 h-3.5 text-emerald-400 ${loading ? 'animate-spin-icon' : ''}`} />}
          <span className="section-label">Agent Pipeline</span>
          {isError && (
            <span className="chip bg-red-500/10 text-red-400 border border-red-500/25 text-[10px]">Error</span>
          )}
        </div>
        {loading && (
          <div className="flex items-center gap-3">
            <div className="h-1 w-24 rounded-full bg-slate-800 overflow-hidden hidden sm:block">
              <div
                className="h-full rounded-full bg-gradient-to-r from-emerald-500 to-blue-500 transition-all duration-700"
                style={{ width: `${progressPct}%` }}
              />
            </div>
            <span className="text-xs text-slate-500 font-[var(--font-mono)] tabular-nums">{elapsed}s</span>
          </div>
        )}
      </div>

      {/* Steps */}
      <div className="flex items-center">
        {STEPS.map((step, idx) => {
          const status = getStatus(step.id, currentStep);
          const isDone   = status === 'done';
          const isActive = status === 'active';

          return (
            <div key={step.id} className="flex items-center flex-1 min-w-0">
              {/* Step */}
              <div className="flex flex-col items-center gap-1.5 min-w-0 flex-1">
                {/* Circle */}
                <div
                  className={`w-9 h-9 rounded-full flex items-center justify-center transition-all duration-400 flex-shrink-0 border ${
                    isDone
                      ? 'bg-emerald-500/15 border-emerald-500/40'
                      : isActive
                      ? `${step.activeBg} shadow-lg ${loading ? 'animate-glow-green' : ''}`
                      : 'border-slate-700/60 bg-transparent'
                  }`}
                >
                  {isDone ? (
                    <CheckCircle className="w-4 h-4 text-emerald-400" />
                  ) : isActive && loading ? (
                    <Loader2 className={`w-4 h-4 animate-spin-icon ${step.color}`} />
                  ) : (
                    <span className={isActive ? step.color : 'text-slate-600'}>{step.icon}</span>
                  )}
                </div>

                {/* Label */}
                <div className="text-center hidden sm:block">
                  <p className={`text-[10px] font-semibold leading-none ${
                    isActive ? step.color : isDone ? 'text-slate-400' : 'text-slate-600'
                  }`}>
                    {step.label}
                  </p>
                  <p className="text-[9px] text-slate-600 mt-0.5 leading-none">{step.sub}</p>
                </div>
              </div>

              {/* Connector */}
              {idx < STEPS.length - 1 && (
                <div className="flex-1 h-px mx-1 relative overflow-hidden max-w-[52px]">
                  <div className="absolute inset-0 bg-slate-800" />
                  {isDone && (
                    <div
                      className="absolute inset-0 bg-gradient-to-r from-emerald-500 to-emerald-400"
                      style={{ animation: 'progress-in 0.4s ease both' }}
                    />
                  )}
                  {isActive && loading && (
                    <div
                      className="absolute inset-0 bg-gradient-to-r from-emerald-500/60 to-transparent"
                      style={{ animation: 'shimmer 1.5s ease-in-out infinite' }}
                    />
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
