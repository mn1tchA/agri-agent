import { type AnalysisData } from '../types';
import { Calendar, Bug, ShieldAlert, Sparkles, HeartPulse } from 'lucide-react';

interface HarvestCalendarProps {
  data: AnalysisData;
}

export function HarvestCalendar({ data }: HarvestCalendarProps) {
  const dsp = data.days_since_planting ?? 30;
  const dth = data.days_until_harvest ?? 0;
  const ready = data.harvest_ready ?? false;
  const gddPct = data.gdd_progress_pct ?? 0;
  
  // Calculate relative progress in terms of days since planting vs target maturity
  const targetDays = dsp + dth;
  const daysProgressPct = Math.round((dsp / Math.max(targetDays, 1)) * 100);

  return (
    <div className="glass-panel border border-white/[0.06] p-5 rounded-2xl relative overflow-hidden animate-slide-up">
      {/* Light gradient bar */}
      <div className="absolute top-0 left-0 w-full h-[1px] bg-gradient-to-r from-pink-500/20 via-transparent to-transparent" />

      <div className="flex justify-between items-start mb-6">
        <div>
          <h3 className="text-sm font-semibold font-display text-white flex items-center gap-2">
            <Calendar className="w-4.5 h-4.5 text-pink-400" />
            Harvest & Phenology Planner
          </h3>
          <p className="text-[11px] text-slate-400 mt-0.5">Phenological growth tracking & harvest metrics</p>
        </div>

        {ready ? (
          <span className="animate-glow-green text-[10px] font-bold uppercase tracking-wider px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 flex items-center gap-1.5">
            <Sparkles className="w-3.5 h-3.5" />
            Harvest Ready
          </span>
        ) : (
          <span className="text-[10px] font-semibold uppercase tracking-wider px-3 py-1 rounded-full bg-slate-500/10 border border-white/[0.06] text-slate-400">
            {dth} Days to Harvest
          </span>
        )}
      </div>

      <div className="space-y-5">
        {/* Days Progress Bar */}
        <div>
          <div className="flex justify-between text-xs mb-2">
            <span className="text-slate-300">Growth Stage Timeline</span>
            <span className="font-semibold text-white font-mono">{dsp} / {targetDays} days ({daysProgressPct}%)</span>
          </div>
          <div className="h-2 rounded-full bg-slate-950 overflow-hidden relative border border-white/[0.02]">
            <div
              className="h-full rounded-full bg-gradient-to-r from-pink-500 to-pink-400 transition-all duration-1000"
              style={{ width: `${daysProgressPct}%` }}
            />
          </div>
          {data.active_bbch_stage && (
            <p className="text-[11px] font-mono text-pink-300 mt-2">Active Phase: {data.active_bbch_stage}</p>
          )}
        </div>

        {/* GDD Tracking */}
        <div>
          <div className="flex justify-between text-xs mb-2">
            <span className="text-slate-300">Growing Degree Days (GDD) Progress</span>
            <span className="font-semibold text-white font-mono">{gddPct.toFixed(1)}%</span>
          </div>
          <div className="h-2 rounded-full bg-slate-950 overflow-hidden relative border border-white/[0.02]">
            <div
              className="h-full rounded-full bg-gradient-to-r from-teal-500 to-teal-400 transition-all duration-1000"
              style={{ width: `${gddPct}%` }}
            />
          </div>
        </div>

        {/* NPK Fertilizer Recommendation */}
        {data.fertilizer_recommendation && (
          <div className="p-3.5 rounded-xl border border-white/[0.04] bg-white/[0.01]">
            <span className="section-label block mb-2">Fertilization Schedule</span>
            <div className="text-xs text-slate-300 leading-relaxed font-sans flex items-start gap-2">
              <span className="text-emerald-400 text-sm mt-0.5">🌱</span>
              {data.fertilizer_recommendation}
            </div>
          </div>
        )}

        {/* Pest Alert Banner */}
        {data.pesticide_alert && (
          <div className={`p-3.5 rounded-xl border ${data.pesticide_alert.includes('⚠️') ? 'border-red-500/20 bg-red-500/[0.02] text-red-300' : 'border-white/[0.04] bg-white/[0.01] text-slate-300'}`}>
            <span className="section-label block mb-2 flex items-center gap-1.5 text-slate-400">
              <Bug className="w-3.5 h-3.5 text-slate-400" />
              Crop Protection Alert
            </span>
            <div className="text-xs leading-relaxed font-sans flex items-start gap-2">
              {data.pesticide_alert.includes('⚠️') ? (
                <ShieldAlert className="w-4 h-4 text-red-400 flex-shrink-0 mt-0.5" />
              ) : (
                <HeartPulse className="w-4 h-4 text-emerald-400 flex-shrink-0 mt-0.5" />
              )}
              <span>{data.pesticide_alert}</span>
            </div>
          </div>
        )}

        {/* Soil Amendment */}
        {data.soil_amendment && (
          <div className="p-3.5 rounded-xl border border-white/[0.04] bg-white/[0.01]">
            <span className="section-label block mb-2">Soil Amendment Advisory</span>
            <div className="text-xs text-slate-300 leading-relaxed font-sans">
              🍂 {data.soil_amendment}
            </div>
          </div>
        )}

        {/* Pre-harvest stress advisory */}
        {data.pre_harvest_stress_recommended && (
          <div className="p-3.5 rounded-xl border border-amber-500/10 bg-amber-500/[0.02] text-amber-300 flex items-start gap-2">
            <span className="text-sm mt-0.5">⚠️</span>
            <div className="text-xs">
              <span className="font-semibold block mb-0.5 text-amber-200">Pre-Harvest Stress Recommended</span>
              Mild moisture stress is advised to concentrate crop sugars, starches, and maximize active yield quality.
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
