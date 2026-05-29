import { type AnalysisData } from '../types';
import { DollarSign, Activity } from 'lucide-react';

interface CostBreakdownProps {
  data: AnalysisData;
}

export function CostBreakdown({ data }: CostBreakdownProps) {
  const water = data.water_cost_usd ?? 0;
  const electricity = data.electricity_cost_usd ?? 0;
  const fuel = data.fuel_cost_usd ?? 0;
  const labor = data.labor_cost_usd ?? 0;
  const total = data.total_operational_cost_usd ?? (water + electricity + fuel + labor);
  const roi = data.roi_score ?? 0;

  // Max value to scale progress bars
  const maxCost = Math.max(water, electricity, fuel, labor, 1);

  // Helper to format currency
  const fmt = (val: number) =>
    val.toLocaleString('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 2, maximumFractionDigits: 2 });

  return (
    <div className="glass-panel border border-white/[0.06] p-5 rounded-2xl relative overflow-hidden animate-slide-up">
      {/* Top light beam */}
      <div className="absolute top-0 left-0 w-full h-[1px] bg-gradient-to-r from-emerald-500/20 via-transparent to-transparent" />
      
      <div className="flex justify-between items-center mb-6">
        <div>
          <h3 className="text-sm font-semibold font-display text-white flex items-center gap-2">
            <DollarSign className="w-4.5 h-4.5 text-emerald-400" />
            Operational Cost Model
          </h3>
          <p className="text-[11px] text-slate-400 mt-0.5">Estimated resource allocation per run</p>
        </div>

        {roi > 0 && (
          <div className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">
            <Activity className="w-3.5 h-3.5 animate-pulse" />
            <span className="text-[11px] font-bold font-mono">ROI: {roi.toFixed(2)}x</span>
          </div>
        )}
      </div>

      <div className="space-y-4">
        {/* Cost Rows */}
        {[
          { label: 'Water Resource', value: water, color: 'bg-blue-500', barColor: 'from-blue-600 to-blue-400' },
          { label: 'Electricity (Pumping)', value: electricity, color: 'bg-amber-500', barColor: 'from-amber-600 to-amber-400' },
          { label: 'Fuel (Generator/Motors)', value: fuel, color: 'bg-red-500', barColor: 'from-red-600 to-red-400' },
          { label: 'Labor (Workforce)', value: labor, color: 'bg-purple-500', barColor: 'from-purple-600 to-purple-400' },
        ].map((item, idx) => {
          const pct = Math.round((item.value / maxCost) * 100);
          return (
            <div key={idx} className="group">
              <div className="flex justify-between items-center text-xs mb-1.5">
                <span className="text-slate-300 flex items-center gap-2">
                  <span className={`w-1.5 h-1.5 rounded-full ${item.color}`} />
                  {item.label}
                </span>
                <span className="font-semibold text-white font-mono">{fmt(item.value)}</span>
              </div>
              <div className="h-1.5 rounded-full bg-slate-950 overflow-hidden relative border border-white/[0.02]">
                <div
                  className={`h-full rounded-full bg-gradient-to-r ${item.barColor} transition-all duration-1000`}
                  style={{ width: `${pct}%` }}
                />
              </div>
            </div>
          );
        })}

        {/* Total Cost Section */}
        <div className="mt-6 pt-5 border-t border-white/[0.06] flex justify-between items-center">
          <div>
            <span className="section-label">Total Estimate</span>
            <div className="text-2xl font-bold font-display text-white mt-0.5 tracking-tight">
              {fmt(total)}
            </div>
          </div>

          <div className="text-right">
            <span className="section-label">Risk Mitigated</span>
            <div className="text-sm font-semibold text-emerald-400 font-mono mt-0.5">
              +{fmt(data.crop_value_at_risk_usd ?? 0)}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
