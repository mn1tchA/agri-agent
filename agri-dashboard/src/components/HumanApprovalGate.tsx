import { CheckCircle, XCircle, AlertTriangle, Droplets, Timer, Leaf } from 'lucide-react';
import { useEffect, useState } from 'react';
import type { AnalysisData } from '../types';
import { CostBreakdown } from './CostBreakdown';
import { AgentVoteBoard } from './AgentVoteBoard';

interface HumanApprovalGateProps {
  data: AnalysisData;
  hardwareStatus: string | null;
  onApprove: (approved: boolean) => void;
}

function useCountdown(seconds: number, active: boolean) {
  const [rem, setRem] = useState(seconds);
  useEffect(() => {
    if (!active) return;
    setRem(seconds);
    const id = setInterval(() => setRem(s => Math.max(0, s - 1)), 1000);
    return () => clearInterval(id);
  }, [active, seconds]);
  return rem;
}

function WaterGauge({ liters, isMicro }: { liters: number; isMicro: boolean }) {
  const max = Math.max(liters, 50000);
  const pct = Math.min(100, (liters / max) * 100);
  return (
    <div>
      <div className="flex items-center justify-between mb-2.5">
        <span className="flex items-center gap-1.5 text-xs text-slate-500">
          <Droplets className="w-3.5 h-3.5 text-blue-400" />
          {isMicro ? 'Micro-Irrigation Volume' : 'Water Volume Required'}
        </span>
        <span className="font-[var(--font-mono)] text-sm font-bold text-blue-300 tabular-nums">
          {liters?.toLocaleString()} L
        </span>
      </div>
      <div className="h-2 rounded-full bg-slate-800 overflow-hidden">
        <div
          className={`h-full rounded-full bg-gradient-to-r ${isMicro ? 'from-teal-500 to-blue-400' : 'from-blue-500 to-blue-400'}`}
          style={{ width: `${pct}%`, animation: 'progress-in 0.8s ease both' }}
        />
      </div>
    </div>
  );
}

/* ── Irrigate decision panel ─────────────────────────────── */
function IrrigateGate({ data, onApprove }: { data: AnalysisData; onApprove: (v: boolean) => void }) {
  const [confirmed, setConfirmed] = useState<boolean | null>(null);
  const countdown = useCountdown(120, true);
  const urgent = countdown < 30;
  const pct = Math.round((countdown / 120) * 100);
  const isMicro = data.decision === 'micro_irrigate';

  const decide = (v: boolean) => { setConfirmed(v); onApprove(v); };

  return (
    <div className="glass-panel border border-emerald-500/20 overflow-hidden animate-slide-up">
      <div className="h-0.5 bg-gradient-to-r from-emerald-500 via-blue-500 to-transparent" />

      <div className="p-5 space-y-6">
        {/* Header */}
        <div className="flex justify-between items-center">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-xl bg-emerald-500/15 flex items-center justify-center flex-shrink-0 border border-emerald-500/20">
              <CheckCircle className="w-4 h-4 text-emerald-400" />
            </div>
            <div>
              <h3 className="font-semibold text-sm text-white">
                {isMicro ? 'Micro-Irrigation' : 'Full Irrigation'} Decision Required
              </h3>
              <p className="text-[11px] text-slate-500">Review and authorize the sprinkler command</p>
            </div>
          </div>

          <div className={`flex items-center gap-1.5 chip border ${
            urgent
              ? 'bg-red-500/10 text-red-400 border-red-500/30 animate-glow-red'
              : 'bg-slate-800 text-slate-400 border-slate-700'
          }`}>
            <Timer className="w-3 h-3" />
            <span className="font-[var(--font-mono)] tabular-nums text-[11px]">{countdown}s</span>
          </div>
        </div>

        {/* Countdown bar */}
        <div className="h-0.5 rounded-full bg-slate-800 overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-1000 ${urgent ? 'bg-red-500' : 'bg-emerald-500/60'}`}
            style={{ width: `${pct}%` }}
          />
        </div>

        {/* Water gauge */}
        <div className="bg-blue-500/[0.05] border border-blue-500/12 rounded-xl p-4">
          <WaterGauge liters={data.water_volume_liters ?? 0} isMicro={isMicro} />
        </div>

        {/* Cost Breakdown Panel */}
        <CostBreakdown data={data} />

        {/* Vote board showing how each agent voted */}
        <AgentVoteBoard votes={data.agent_votes} />

        {/* Nutrient mix */}
        {data.nutrient_mix && data.nutrient_mix !== 'None' && (
          <div className="flex items-start gap-3 bg-emerald-500/[0.05] border border-emerald-500/15 rounded-xl p-4">
            <Leaf className="w-4 h-4 text-emerald-400 flex-shrink-0 mt-0.5" />
            <div>
              <p className="section-label mb-1">Recommended Nutrient Mix</p>
              <p className="text-sm text-emerald-300 leading-relaxed">{data.nutrient_mix}</p>
            </div>
          </div>
        )}

        {/* Buttons */}
        {confirmed === null ? (
          <div className="flex gap-3">
            <button
              id="approve-irrigate-btn"
              onClick={() => decide(true)}
              className="btn-primary flex-1 justify-center py-3 text-[13px] animate-glow-green"
            >
              <CheckCircle className="w-4 h-4" />
              Authorize Irrigation
            </button>
            <button
              id="skip-irrigate-btn"
              onClick={() => decide(false)}
              className="btn-secondary flex-1 justify-center py-3 text-[13px]"
            >
              <XCircle className="w-4 h-4" />
              Skip Cycle
            </button>
          </div>
        ) : (
          <div className="flex items-center justify-center gap-2 py-3 text-sm text-slate-400">
            {confirmed
              ? <><Droplets className="w-4 h-4 text-blue-400" /> Sending command to hardware...</>
              : <><XCircle className="w-4 h-4 text-slate-600" /> Irrigation execution skipped.</>
            }
          </div>
        )}
      </div>
    </div>
  );
}

/* ── Main component ─────────────────────────────────────── */
export function HumanApprovalGate({ data, hardwareStatus, onApprove }: HumanApprovalGateProps) {

  if ((data.decision === 'wait' || data.decision === 'wait_for_conditions') && !hardwareStatus) {
    return (
      <div className="glass-panel border border-emerald-500/20 p-5 animate-slide-up">
        <div className="flex items-start gap-3">
          <div className="w-8 h-8 rounded-xl bg-emerald-500/15 border border-emerald-500/20 flex items-center justify-center flex-shrink-0">
            <CheckCircle className="w-4 h-4 text-emerald-400" />
          </div>
          <div>
            <h3 className="font-semibold text-sm text-emerald-300 mb-1">No irrigation needed</h3>
            <p className="text-sm text-slate-500">
              Soil moisture is optimal and forecasts show adequate reserves. No action required.
            </p>
          </div>
        </div>
      </div>
    );
  }

  if (data.decision === 'error') {
    return (
      <div className="glass-panel border border-red-500/20 p-5 animate-slide-up">
        <div className="flex items-start gap-3">
          <div className="w-8 h-8 rounded-xl bg-red-500/15 border border-red-500/20 flex items-center justify-center flex-shrink-0">
            <XCircle className="w-4 h-4 text-red-400" />
          </div>
          <div>
            <h3 className="font-semibold text-sm text-red-300 mb-1">Rate Limit Exceeded</h3>
            <p className="text-sm text-slate-500">
              Free tier limit reached. Please wait 60 seconds and retry.
            </p>
          </div>
        </div>
      </div>
    );
  }

  if (hardwareStatus) {
    return (
      <div className="glass-panel border border-emerald-500/20 p-5 animate-slide-up">
        <div className="h-0.5 bg-gradient-to-r from-emerald-500 to-transparent mb-4" />
        <div className="flex items-start gap-3">
          <div className="w-8 h-8 rounded-xl bg-emerald-500/15 border border-emerald-500/20 flex items-center justify-center flex-shrink-0">
            <CheckCircle className="w-4 h-4 text-emerald-400" />
          </div>
          <div>
            <h3 className="font-semibold text-sm text-emerald-300 mb-1">Decision Logged</h3>
            <p className="text-sm text-slate-500 leading-relaxed">{hardwareStatus}</p>
          </div>
        </div>
      </div>
    );
  }

  if (data.decision === 'anomaly') {
    return (
      <div className="glass-panel border border-red-500/30 overflow-hidden animate-slide-up animate-glow-red">
        <div className="h-0.5 bg-gradient-to-r from-red-500 to-transparent" />
        <div className="p-5">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-8 h-8 rounded-xl bg-red-500/15 border border-red-500/20 flex items-center justify-center flex-shrink-0">
              <AlertTriangle className="w-4 h-4 text-red-400" />
            </div>
            <div>
              <h3 className="font-semibold text-sm text-red-300">Critical Anomaly Detected</h3>
              <p className="text-[11px] text-slate-500">Agent pipeline bypassed — manual review required</p>
            </div>
          </div>

          <div className="bg-red-500/[0.06] border border-red-500/20 rounded-xl p-4 mb-5">
            <p className="section-label mb-2">Anomaly Report</p>
            <p className="text-sm text-red-200 leading-relaxed">
              {data.anomaly_reason ?? 'Critical sensor reading detected. Manual review required.'}
            </p>
          </div>

          <div className="flex gap-3">
            <button
              id="anomaly-emergency-stop"
              onClick={() => onApprove(false)}
              className="btn-danger flex-1 justify-center py-3 text-[13px]"
            >
              <XCircle className="w-4 h-4" /> Emergency Stop
            </button>
            <button
              id="anomaly-override-irrigate"
              onClick={() => onApprove(true)}
              className="flex-1 py-3 rounded-[10px] border border-amber-500/30 text-amber-300 bg-amber-500/[0.06] hover:bg-amber-500/12 flex items-center justify-center gap-2 text-[13px] font-semibold transition-all duration-200"
            >
              <AlertTriangle className="w-4 h-4" /> Override
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (data.decision === 'irrigate' || data.decision === 'micro_irrigate') {
    return <IrrigateGate data={data} onApprove={onApprove} />;
  }

  return null;
}
