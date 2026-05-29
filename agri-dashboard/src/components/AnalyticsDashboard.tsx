import { useState, useEffect, useCallback } from 'react';
import { toast } from 'react-toastify';
import {
  LineChart, Line, AreaChart, Area,
  PieChart, Pie, Cell, Legend,
  XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
} from 'recharts';
import {
  Database, Droplets, DollarSign, ThumbsUp, ThumbsDown,
  TrendingUp, RefreshCw, BookOpen, ChevronDown, ChevronUp,
  CloudRain, Leaf, BadgeDollarSign, Thermometer,
} from 'lucide-react';
import type { HistoryLog, AggregateStats } from '../types';
import { fetchHistory, fetchStats } from '../hooks/useAnalysis';

interface AnalyticsDashboardProps {
  onFeedback: (logId: number, rating: number) => void;
}

const PIE_COLORS = ['#10b981', '#64748b'];

function formatDate(ts: string) {
  return new Date(ts).toLocaleDateString([], { month: 'short', day: 'numeric' });
}
function formatTime(ts: string) {
  return new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

const CHART_STYLE = {
  tooltipStyle: {
    backgroundColor: '#1e293b',
    border: '1px solid rgba(255,255,255,0.08)',
    borderRadius: '10px',
    fontFamily: 'JetBrains Mono, monospace',
    fontSize: '12px',
    color: '#f1f5f9',
    boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
  },
  gridStroke: 'rgba(255,255,255,0.04)',
  axisStyle: { fill: '#475569', fontFamily: 'JetBrains Mono, monospace', fontSize: 11 },
};

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-16 gap-4 animate-fade-in">
      <div className="w-14 h-14 rounded-2xl bg-slate-800/60 border border-slate-700/50 flex items-center justify-center">
        <BookOpen className="w-6 h-6 text-slate-600" />
      </div>
      <div className="text-center">
        <p className="font-semibold text-sm text-slate-400 mb-1">No history yet</p>
        <p className="text-xs text-slate-600">Run your first analysis to start recording decisions.</p>
      </div>
    </div>
  );
}

function KpiCard({ label, value, color, bg, border }: {
  label: string; value: string; color: string; bg: string; border: string;
}) {
  return (
    <div className={`${bg} border ${border} rounded-xl p-4 text-center hover:-translate-y-0.5 hover:shadow-lg hover:shadow-black/20 transition-all duration-200 animate-slide-up`}>
      <p className="section-label mb-2">{label}</p>
      <p className={`font-[var(--font-mono)] font-bold text-lg ${color} tabular-nums`}>{value}</p>
    </div>
  );
}

function DecisionBadge({ decision }: { decision: string }) {
  const isIrrigate = decision === 'irrigate';
  return (
    <span className={`chip text-[10px] font-bold border ${
      isIrrigate
        ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/25'
        : 'bg-slate-700/40 text-slate-500 border-slate-700'
    }`}>
      {decision?.toUpperCase()}
    </span>
  );
}

export function AnalyticsDashboard({ onFeedback }: AnalyticsDashboardProps) {
  const [history, setHistory] = useState<HistoryLog[]>([]);
  const [stats, setStats] = useState<AggregateStats | null>(null);
  const [expanded, setExpanded] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true); else setLoading(true);
    try {
      const [h, s] = await Promise.all([fetchHistory(), fetchStats()]);
      setHistory(h); setStats(s);
      if (isRefresh) toast.success('Data refreshed');
    } catch { toast.error('Could not load analytics.'); }
    setLoading(false); setRefreshing(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  const chartData = [...history].reverse();
  const pieData = stats ? [
    { name: 'Irrigate', value: stats.irrigate_count },
    { name: 'Wait',     value: stats.wait_count },
  ] : [];

  return (
    <div className="glass-panel p-6 mb-5 animate-slide-up">
      {/* Header */}
      <div className="flex items-center justify-between pb-4 mb-5 border-b border-white/[0.06]">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-xl bg-emerald-500/15 flex items-center justify-center border border-emerald-500/20">
            <Database className="w-3.5 h-3.5 text-emerald-400" />
          </div>
          <div>
            <h2 className="font-semibold text-sm text-white">Analytics</h2>
            <p className="text-[11px] text-slate-500">Decision history and aggregate statistics</p>
          </div>
        </div>
        <button onClick={() => load(true)} disabled={refreshing} className="btn-secondary px-3 py-1.5 text-xs">
          <RefreshCw className={`w-3 h-3 ${refreshing ? 'animate-spin-icon' : ''}`} />
          Refresh
        </button>
      </div>

      {/* Skeleton */}
      {loading && (
        <div className="space-y-3 py-4">
          {[100, 70, 85, 60, 90].map((w, i) => (
            <div key={i} className="skeleton h-5 rounded" style={{ width: `${w}%` }} />
          ))}
        </div>
      )}

      {!loading && stats && (
        <>
          {/* KPI row */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
            <KpiCard label="Total Runs"    value={`${stats.total_decisions}`}                          color="text-slate-200"   bg="bg-slate-700/30"      border="border-slate-700/50" />
            <KpiCard label="Total Water"   value={`${(stats.total_water_liters / 1000).toFixed(1)}k L`} color="text-blue-300"    bg="bg-blue-500/[0.06]"   border="border-blue-500/15" />
            <KpiCard label="Total Cost"    value={`${stats.total_cost_dzd.toFixed(0)} DZD`}           color="text-amber-300"   bg="bg-amber-500/[0.06]"  border="border-amber-500/15" />
            <KpiCard label="Avg Moisture"  value={`${stats.avg_soil_moisture.toFixed(1)}%`}            color="text-emerald-300" bg="bg-emerald-500/[0.06]" border="border-emerald-500/15" />
          </div>

          {/* Charts */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6">
            <div className="lg:col-span-2 bg-slate-900/60 border border-white/[0.05] rounded-xl p-4">
              <p className="section-label flex items-center gap-1.5 mb-4">
                <TrendingUp className="w-3 h-3" /> Moisture & Volume Trend
              </p>
              <ResponsiveContainer width="100%" height={200}>
                <AreaChart data={chartData} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
                  <defs>
                    <linearGradient id="moistGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%"  stopColor="#3b82f6" stopOpacity={0.25} />
                      <stop offset="95%" stopColor="#3b82f6" stopOpacity={0}    />
                    </linearGradient>
                    <linearGradient id="volGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%"  stopColor="#10b981" stopOpacity={0.25} />
                      <stop offset="95%" stopColor="#10b981" stopOpacity={0}    />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke={CHART_STYLE.gridStroke} vertical={false} />
                  <XAxis dataKey="timestamp" tickFormatter={formatDate} tick={CHART_STYLE.axisStyle} stroke="transparent" tickMargin={8} />
                  <YAxis yAxisId="l" tick={CHART_STYLE.axisStyle} stroke="transparent" />
                  <YAxis yAxisId="r" orientation="right" tick={CHART_STYLE.axisStyle} stroke="transparent" />
                  <Tooltip contentStyle={CHART_STYLE.tooltipStyle} labelFormatter={t => `${formatDate(t)} ${formatTime(t)}`} />
                  <Area yAxisId="l" type="monotone" dataKey="soil_moisture"       stroke="#3b82f6" fill="url(#moistGrad)" strokeWidth={2} name="Moisture (%)" dot={false} />
                  <Area yAxisId="r" type="monotone" dataKey="water_volume_liters" stroke="#10b981" fill="url(#volGrad)"   strokeWidth={2} name="Volume (L)"   dot={false} />
                </AreaChart>
              </ResponsiveContainer>
            </div>

            <div className="bg-slate-900/60 border border-white/[0.05] rounded-xl p-4 flex flex-col">
              <p className="section-label mb-4">Decision Split</p>
              {pieData.some(d => d.value > 0) ? (
                <ResponsiveContainer width="100%" height={200}>
                  <PieChart>
                    <Pie data={pieData} cx="50%" cy="50%" outerRadius={72} innerRadius={32}
                      dataKey="value" labelLine={false} strokeWidth={0}>
                      {pieData.map((_, i) => <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />)}
                    </Pie>
                    <Legend iconType="circle" wrapperStyle={{ fontSize: '11px', color: '#64748b' }} />
                    <Tooltip contentStyle={CHART_STYLE.tooltipStyle} />
                  </PieChart>
                </ResponsiveContainer>
              ) : (
                <p className="text-xs text-slate-600 text-center mt-8">No decisions recorded yet.</p>
              )}
            </div>
          </div>

          {chartData.length > 0 && (
            <div className="bg-slate-900/60 border border-white/[0.05] rounded-xl p-4 mb-6">
              <p className="section-label flex items-center gap-1.5 mb-4">
                <DollarSign className="w-3 h-3" /> Cost Over Time (DZD)
              </p>
              <ResponsiveContainer width="100%" height={110}>
                <LineChart data={chartData} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke={CHART_STYLE.gridStroke} vertical={false} />
                  <XAxis dataKey="timestamp" tickFormatter={formatDate} tick={CHART_STYLE.axisStyle} stroke="transparent" />
                  <YAxis tick={CHART_STYLE.axisStyle} stroke="transparent" />
                  <Tooltip contentStyle={CHART_STYLE.tooltipStyle} labelFormatter={t => formatDate(t)} />
                  <Line type="monotone" dataKey="financial_cost_dzd" stroke="#f59e0b" strokeWidth={2} name="Cost (DZD)"
                    dot={{ r: 3, fill: '#f59e0b', strokeWidth: 0 }}
                    activeDot={{ r: 5, fill: '#f59e0b', strokeWidth: 0 }} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}
        </>
      )}

      {/* Audit trail */}
      {!loading && history.length > 0 && (
        <div>
          <p className="section-label flex items-center gap-1.5 mb-3">
            <Droplets className="w-3 h-3" /> Audit Trail
          </p>
          <div className="space-y-1.5">
            {history.map(log => (
              <div key={log.id}
                className="bg-slate-900/50 border border-white/[0.05] rounded-xl overflow-hidden hover:border-white/[0.09] transition-colors duration-150"
              >
                <button
                  className="w-full text-left px-4 py-3 flex flex-wrap items-center gap-3 hover:bg-white/[0.02] transition-colors"
                  onClick={() => setExpanded(expanded === log.id ? null : log.id)}
                >
                  <DecisionBadge decision={log.decision} />

                  {log.outcome_rating === 5 && (
                    <span className="chip text-[10px] bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                      <ThumbsUp className="w-3 h-3" /> Good
                    </span>
                  )}
                  {log.outcome_rating === 1 && (
                    <span className="chip text-[10px] bg-red-500/10 text-red-400 border border-red-500/20">
                      <ThumbsDown className="w-3 h-3" /> Poor
                    </span>
                  )}

                  <span className="text-sm text-slate-300 font-medium">{log.crop_type}</span>

                  {/* Inline stats — icon only, no emoji */}
                  <span className="flex items-center gap-1 text-xs text-blue-400 font-[var(--font-mono)]">
                    <Droplets className="w-3 h-3" />{log.soil_moisture?.toFixed(1)}%
                  </span>
                  <span className="flex items-center gap-1 text-xs text-red-400 font-[var(--font-mono)]">
                    <Thermometer className="w-3 h-3" />{log.temperature}°C
                  </span>
                  <span className="flex items-center gap-1 text-xs text-amber-400 font-[var(--font-mono)]">
                    <DollarSign className="w-3 h-3" />{log.financial_cost_dzd?.toFixed(0)} DZD
                  </span>

                  <span className="text-[11px] text-slate-600 ml-auto font-[var(--font-mono)]">
                    {formatDate(log.timestamp)} {formatTime(log.timestamp)}
                  </span>
                  <span className="text-slate-600">
                    {expanded === log.id
                      ? <ChevronUp className="w-3.5 h-3.5" />
                      : <ChevronDown className="w-3.5 h-3.5" />}
                  </span>
                </button>

                {expanded === log.id && (
                  <div className="border-t border-white/[0.05] p-4 space-y-3 animate-fade-in">
                    {log.meteorologist_analysis && (
                      <div className="bg-blue-500/[0.04] border border-blue-500/12 rounded-lg p-3">
                        <p className="flex items-center gap-1.5 section-label text-blue-400/60 mb-1.5">
                          <CloudRain className="w-3 h-3" /> Meteorologist
                        </p>
                        <p className="text-xs text-slate-400 leading-relaxed">{log.meteorologist_analysis}</p>
                      </div>
                    )}
                    {log.botanist_analysis && (
                      <div className="bg-emerald-500/[0.04] border border-emerald-500/12 rounded-lg p-3">
                        <p className="flex items-center gap-1.5 section-label text-emerald-400/60 mb-1.5">
                          <Leaf className="w-3 h-3" /> Botanist
                          {log.reasoning_confidence > 0 && (
                            <span className="opacity-60 normal-case font-normal tracking-normal ml-1">
                              · {Math.round(log.reasoning_confidence * 100)}% confidence
                            </span>
                          )}
                        </p>
                        <p className="text-xs text-slate-400 leading-relaxed">{log.botanist_analysis}</p>
                      </div>
                    )}
                    {log.financial_analysis && (
                      <div className="bg-amber-500/[0.04] border border-amber-500/12 rounded-lg p-3">
                        <p className="flex items-center gap-1.5 section-label text-amber-400/60 mb-1.5">
                          <BadgeDollarSign className="w-3 h-3" /> Financial Director
                        </p>
                        <p className="text-xs text-slate-400 leading-relaxed">{log.financial_analysis}</p>
                      </div>
                    )}

                    {/* Feedback */}
                    <div className="flex items-center gap-3 pt-2 border-t border-white/[0.04]">
                      <span className="text-[11px] text-slate-600">Was this a good decision?</span>
                      <button
                        onClick={() => onFeedback(log.id, 5)}
                        className={`chip text-[10px] border transition-all cursor-pointer ${
                          log.outcome_rating === 5
                            ? 'bg-emerald-500 text-white border-emerald-500'
                            : 'bg-emerald-500/10 text-emerald-400 border-emerald-500/25 hover:bg-emerald-500/20'
                        }`}
                      >
                        <ThumbsUp className="w-3 h-3" /> Yes
                      </button>
                      <button
                        onClick={() => onFeedback(log.id, 1)}
                        className={`chip text-[10px] border transition-all cursor-pointer ${
                          log.outcome_rating === 1
                            ? 'bg-red-500 text-white border-red-500'
                            : 'bg-red-500/10 text-red-400 border-red-500/25 hover:bg-red-500/20'
                        }`}
                      >
                        <ThumbsDown className="w-3 h-3" /> No
                      </button>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {!loading && history.length === 0 && <EmptyState />}
    </div>
  );
}
