import { Leaf, Database, Activity, RotateCcw, Wifi, WifiOff, Loader2 } from 'lucide-react';
import { useEffect, useState } from 'react';
import { API_BASE } from '../constants';

interface HeaderProps {
  loading: boolean;
  showAnalytics: boolean;
  hasData: boolean;
  onToggleAnalytics: () => void;
  onRunAnalysis: () => void;
  onReset: () => void;
}

function useBackendPing() {
  const [online, setOnline] = useState<boolean | null>(null);
  useEffect(() => {
    const check = async () => {
      const ctrl = new AbortController();
      const t = setTimeout(() => ctrl.abort(), 3000);
      try {
        const res = await fetch(`${API_BASE}/health`, { signal: ctrl.signal, cache: 'no-store' });
        setOnline(res.ok);
      } catch {
        setOnline(false);
      } finally {
        clearTimeout(t);
      }
    };
    check();
    const id = setInterval(check, 15000);
    return () => clearInterval(id);
  }, []);
  return online;
}

export function Header({ loading, showAnalytics, hasData, onToggleAnalytics, onRunAnalysis, onReset }: HeaderProps) {
  const online = useBackendPing();

  return (
    <header className="glass-panel px-5 py-3.5 mb-5 animate-slide-up flex items-center justify-between gap-4">

      {/* ── Logo ── */}
      <div className="flex items-center gap-3 min-w-0">
        {/* Animated icon */}
        <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-emerald-400 to-emerald-600 flex items-center justify-center flex-shrink-0 shadow-lg shadow-emerald-500/30 hover:shadow-emerald-500/50 transition-shadow duration-300">
          <Leaf className="w-4 h-4 text-white" strokeWidth={2.5} />
        </div>

        <div className="min-w-0">
          <h1 className="font-[var(--font-display)] text-base font-bold leading-tight truncate">
            <span className="bg-gradient-to-r from-emerald-400 to-blue-400 bg-clip-text text-transparent">
              Agri
            </span>
            <span className="text-white"> Agent</span>
          </h1>
          <p className="text-[11px] text-slate-500 leading-tight hidden sm:block">AI Irrigation Advisor</p>
        </div>

        {/* Backend status pill */}
        <div className="hidden md:flex items-center ml-2">
          {online === null ? (
            <span className="chip bg-slate-800 text-slate-400 border border-slate-700 text-[11px]">
              <Loader2 className="w-3 h-3 animate-spin-icon" /> Connecting
            </span>
          ) : online ? (
            <span className="chip bg-emerald-500/10 text-emerald-400 border border-emerald-500/25 text-[11px]">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-dot-blink flex-shrink-0" />
              <Wifi className="w-3 h-3" /> Online
            </span>
          ) : (
            <span className="chip bg-red-500/10 text-red-400 border border-red-500/25 text-[11px]">
              <WifiOff className="w-3 h-3" /> Offline
            </span>
          )}
        </div>
      </div>

      {/* ── Actions ── */}
      <div className="flex items-center gap-2 flex-shrink-0">
        {hasData && !loading && (
          <button onClick={onReset} className="btn-secondary px-3 py-2" title="Start a new analysis">
            <RotateCcw className="w-3.5 h-3.5" />
            <span className="hidden sm:inline text-xs">New Run</span>
          </button>
        )}
        <button
          onClick={onToggleAnalytics}
          className={`btn-secondary px-3 py-2 ${showAnalytics ? 'bg-white/[0.07] border-white/[0.15] text-slate-200' : ''}`}
          title="View decision history"
        >
          <Database className="w-3.5 h-3.5" />
          <span className="hidden sm:inline text-xs">{showAnalytics ? 'Close' : 'Analytics'}</span>
        </button>
        <button
          onClick={onRunAnalysis}
          disabled={loading}
          className={`px-4 py-2 rounded-[10px] font-semibold text-xs flex items-center gap-2 transition-all duration-200 ${
            loading
              ? 'bg-slate-700/60 border border-slate-600 text-slate-400 cursor-not-allowed'
              : 'btn-primary animate-glow-green'
          }`}
        >
          {loading
            ? <Loader2 className="w-4 h-4 animate-spin-icon" />
            : <Activity className="w-4 h-4" />}
          <span>{loading ? 'Analyzing…' : 'Check Farm'}</span>
        </button>
      </div>
    </header>
  );
}
