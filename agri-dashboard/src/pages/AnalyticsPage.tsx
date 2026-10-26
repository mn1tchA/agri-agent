import { useEffect, useState } from 'react';
import { AlertOctagon, RefreshCw, Cpu, CheckCircle2, ShieldAlert } from 'lucide-react';
import { toast } from 'react-toastify';
import { AnalyticsDashboard } from '../components/AnalyticsDashboard';
import { useFarmStore } from '../store/useFarmStore';
import { useAuthStore } from '../store/useAuthStore';

export function AnalyticsPage() {
  const { selectedFarm, valves, fetchValves, emergencyStopValves } = useFarmStore();
  const { user } = useAuthStore();
  const [isStopping, setIsStopping] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);

  useEffect(() => {
    fetchValves();
  }, [fetchValves, selectedFarm]);

  const handleRefresh = async () => {
    setIsRefreshing(true);
    await fetchValves();
    setIsRefreshing(false);
    toast.info('Hardware valve records refreshed.');
  };

  const handleEmergencyStop = async () => {
    if (!window.confirm('⚠️ EMERGENCY OVERRIDE: Are you sure you want to immediately halt all active irrigation field valves?')) {
      return;
    }
    setIsStopping(true);
    try {
      await emergencyStopValves();
      toast.warning('EMERGENCY STOP EXECUTED: All field valves closed.');
    } catch {
      toast.error('Failed to trigger emergency stop.');
    } finally {
      setIsStopping(false);
    }
  };

  const isOperator = user?.role === 'operator' || user?.role === 'admin';

  return (
    <div className="space-y-8 animate-fade-in">
      {/* ── Main Analytics Dashboard (Charts, KPIs, Decision Audit Trail) ── */}
      <AnalyticsDashboard />

      {/* ── Persistent MCP Valve Registry Section ── */}
      <div className="glass-panel p-6 border border-slate-800 shadow-xl space-y-5">
        <div className="flex flex-wrap items-center justify-between gap-4 pb-4 border-b border-slate-800">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center shadow-lg shadow-blue-500/20">
              <Cpu className="w-5 h-5 text-white" />
            </div>
            <div>
              <h3 className="text-base font-semibold text-white font-[var(--font-display)] flex items-center gap-2">
                <span>MCP Valve Actuation Registry</span>
                <span className="badge badge-blue text-[10px] py-0.5 px-2">SQLite Persisted</span>
              </h3>
              <p className="text-xs text-slate-400">
                Audited hardware actuation commands surviving restarts
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2.5">
            <button
              onClick={handleRefresh}
              disabled={isRefreshing}
              className="btn-secondary text-xs px-3 py-2 flex items-center gap-1.5"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin' : ''}`} />
              Refresh
            </button>

            {isOperator && (
              <button
                onClick={handleEmergencyStop}
                disabled={isStopping}
                className="px-3.5 py-2 rounded-lg bg-rose-500/15 hover:bg-rose-500/25 text-rose-300 border border-rose-500/40 text-xs font-semibold flex items-center gap-2 transition-all shadow-md shadow-rose-500/10"
              >
                <AlertOctagon className="w-4 h-4 text-rose-400" />
                {isStopping ? 'Halting Valves...' : 'Emergency Stop All'}
              </button>
            )}
          </div>
        </div>

        {/* Valve Commands Table */}
        {valves.length === 0 ? (
          <div className="py-12 text-center text-slate-500 text-xs">
            No hardware actuation commands recorded yet. Run an analysis and approve irrigation to dispatch valve commands.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-slate-800 text-slate-400 uppercase text-[10px] tracking-wider">
                  <th className="py-2.5 px-3">Command ID</th>
                  <th className="py-2.5 px-3">Crop</th>
                  <th className="py-2.5 px-3">Volume</th>
                  <th className="py-2.5 px-3">Coordinates</th>
                  <th className="py-2.5 px-3">Salinity</th>
                  <th className="py-2.5 px-3">Dilution</th>
                  <th className="py-2.5 px-3">Status</th>
                  <th className="py-2.5 px-3">Hardware ACK</th>
                  <th className="py-2.5 px-3">Timestamp</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 font-mono text-[11px]">
                {valves.map((v) => (
                  <tr key={v.command_id} className="hover:bg-slate-800/30 transition-colors">
                    <td className="py-2.5 px-3 font-semibold text-emerald-400">{v.command_id}</td>
                    <td className="py-2.5 px-3 font-sans text-slate-200">{v.crop_type}</td>
                    <td className="py-2.5 px-3 text-cyan-300">
                      {v.volume_dispatched_liters ? `${v.volume_dispatched_liters.toLocaleString()} L` : '0 L'}
                    </td>
                    <td className="py-2.5 px-3 text-slate-400">{v.target_coordinates}</td>
                    <td className="py-2.5 px-3 text-slate-300">
                      {v.water_salinity_ds_m != null ? `${v.water_salinity_ds_m.toFixed(1)} dS/m` : '—'}
                    </td>
                    <td className="py-2.5 px-3">
                      {v.dilution_protocol === 'ACTIVE' ? (
                        <span className="badge badge-amber text-[10px] py-0.5 px-1.5">ACTIVE</span>
                      ) : (
                        <span className="text-slate-500">INACTIVE</span>
                      )}
                    </td>
                    <td className="py-2.5 px-3">
                      {v.status === 'STOPPED' ? (
                        <span className="inline-flex items-center gap-1 text-rose-400 font-semibold">
                          <ShieldAlert className="w-3 h-3" /> STOPPED
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 text-emerald-400 font-semibold">
                          <CheckCircle2 className="w-3 h-3" /> EXECUTED
                        </span>
                      )}
                    </td>
                    <td className="py-2.5 px-3 text-slate-400">{v.hardware_ack}</td>
                    <td className="py-2.5 px-3 text-slate-500 font-sans text-[10px]">
                      {new Date(v.timestamp_utc).toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
