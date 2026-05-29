import { useState, useEffect } from 'react';
import { fetchCropPlanner } from '../hooks/useAnalysis';
import type { CropPlannerEntry } from '../types';
import { Sprout, Calendar, Navigation, Layers, Compass, Loader2 } from 'lucide-react';
import { toast } from 'react-toastify';

export function CropPlannerTab() {
  const [lat, setLat] = useState<number>(35.6911);
  const [lon, setLon] = useState<number>(-0.6328);
  const [soil, setSoil] = useState<string>('Loamy');
  const [month, setMonth] = useState<number>(new Date().getMonth() + 1);
  const [loading, setLoading] = useState<boolean>(false);
  const [crops, setCrops] = useState<CropPlannerEntry[]>([]);

  const handleGenerate = async () => {
    setLoading(true);
    try {
      const data = await fetchCropPlanner(lat, lon, soil, month);
      setCrops(data);
      toast.success('🌱 Crop recommendation list generated!');
    } catch (e: any) {
      toast.error(`Failed to generate recommendations: ${e.message}`);
    } finally {
      setLoading(false);
    }
  };

  // Generate on mount
  useEffect(() => {
    handleGenerate();
  }, []);

  const getSuitabilityColor = (score: number) => {
    if (score >= 90) return 'text-emerald-400 border-emerald-500/20 bg-emerald-500/5';
    if (score >= 60) return 'text-amber-400 border-amber-500/20 bg-amber-500/5';
    return 'text-red-400 border-red-500/20 bg-red-500/5';
  };

  const getWaterNeedColor = (need: string) => {
    if (need === 'Low') return 'text-blue-400 bg-blue-500/10 border-blue-500/20';
    if (need === 'Medium') return 'text-teal-400 bg-teal-500/10 border-teal-500/20';
    return 'text-pink-400 bg-pink-500/10 border-pink-500/20';
  };

  return (
    <div className="space-y-6">
      {/* Search Filter Panel */}
      <div className="glass-panel border border-white/[0.06] p-6 rounded-2xl animate-slide-up">
        <div className="flex items-center gap-2 mb-5">
          <Sprout className="w-5 h-5 text-emerald-400" />
          <h2 className="text-base font-bold font-display text-white">Land Crop Planner</h2>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4 items-end">
          <div>
            <label className="section-label block mb-2 flex items-center gap-1">
              <Navigation className="w-3 h-3" /> Latitude
            </label>
            <input
              type="number"
              value={lat}
              onChange={(e) => setLat(parseFloat(e.target.value) || 0)}
              className="modern-input"
              step="0.0001"
            />
          </div>

          <div>
            <label className="section-label block mb-2 flex items-center gap-1">
              <Compass className="w-3 h-3" /> Longitude
            </label>
            <input
              type="number"
              value={lon}
              onChange={(e) => setLon(parseFloat(e.target.value) || 0)}
              className="modern-input"
              step="0.0001"
            />
          </div>

          <div>
            <label className="section-label block mb-2 flex items-center gap-1">
              <Layers className="w-3 h-3" /> Soil Texture
            </label>
            <select
              value={soil}
              onChange={(e) => setSoil(e.target.value)}
              className="modern-input cursor-pointer"
            >
              <option value="Sandy">Sandy</option>
              <option value="Loamy">Loamy</option>
              <option value="Clay">Clay</option>
            </select>
          </div>

          <div>
            <label className="section-label block mb-2 flex items-center gap-1">
              <Calendar className="w-3 h-3" /> Sowing Month
            </label>
            <select
              value={month}
              onChange={(e) => setMonth(parseInt(e.target.value))}
              className="modern-input cursor-pointer"
            >
              {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => (
                <option key={m} value={m}>
                  {new Date(0, m - 1).toLocaleString('default', { month: 'long' })}
                </option>
              ))}
            </select>
          </div>

          <div>
            <button
              onClick={handleGenerate}
              disabled={loading}
              className="btn-primary w-full justify-center py-2.5"
            >
              {loading ? (
                <Loader2 className="w-4.5 h-4.5 animate-spin" />
              ) : (
                'Generate Recommendations'
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Recommendations Table */}
      <div className="glass-panel border border-white/[0.06] rounded-2xl overflow-hidden animate-slide-up delay-75">
        <div className="p-5 border-b border-white/[0.05] flex justify-between items-center bg-slate-950/20">
          <span className="section-label">Recommended Cultivars ranked by Net Profit</span>
          <span className="text-[11px] text-slate-400 font-mono">{crops.length} suitable crops found</span>
        </div>

        <div className="overflow-x-auto">
          {loading ? (
            <div className="py-20 flex flex-col items-center justify-center gap-3">
              <Loader2 className="w-8 h-8 text-emerald-400 animate-spin" />
              <span className="text-xs text-slate-400">Modeling crop yields and financial scenarios...</span>
            </div>
          ) : crops.length === 0 ? (
            <div className="py-20 text-center text-xs text-slate-500">
              No recommendations generated. Adjust coordinates or settings and try again.
            </div>
          ) : (
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-white/[0.05] bg-white/[0.01] text-[10px] uppercase font-bold tracking-wider text-slate-400">
                  <th className="px-5 py-3">Crop Type</th>
                  <th className="px-4 py-3">Best Cultivar</th>
                  <th className="px-4 py-3 text-center">Maturity (Days)</th>
                  <th className="px-4 py-3 text-right">Investment / Ha</th>
                  <th className="px-4 py-3 text-right">Revenue / Ha</th>
                  <th className="px-4 py-3 text-right text-emerald-300">Net Profit / Ha</th>
                  <th className="px-4 py-3 text-center">Water Need</th>
                  <th className="px-4 py-3 text-center">Suitability</th>
                  <th className="px-5 py-3">Sensitivity Point</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/[0.03]">
                {crops.map((entry) => (
                  <tr
                    key={entry.eppo}
                    className="hover:bg-white/[0.02] transition-colors group cursor-pointer text-xs"
                  >
                    <td className="px-5 py-4 font-semibold text-white flex items-center gap-2">
                      <span className="text-base">🌱</span>
                      {entry.crop}
                    </td>
                    <td className="px-4 py-4 text-slate-300 font-medium">{entry.best_cultivar}</td>
                    <td className="px-4 py-4 text-center text-slate-300 font-mono font-medium">{entry.time_to_harvest}</td>
                    <td className="px-4 py-4 text-right text-slate-400 font-mono">
                      ${entry.initial_investment.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
                    </td>
                    <td className="px-4 py-4 text-right text-slate-400 font-mono">
                      ${entry.expected_revenue.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
                    </td>
                    <td className="px-4 py-4 text-right font-semibold text-emerald-400 font-mono bg-emerald-500/[0.01]">
                      ${entry.net_profit.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
                    </td>
                    <td className="px-4 py-4 text-center">
                      <span className={`text-[10px] font-semibold border rounded-full px-2 py-0.5 ${getWaterNeedColor(entry.water_need)}`}>
                        {entry.water_need}
                      </span>
                    </td>
                    <td className="px-4 py-4 text-center">
                      <span className={`text-[10px] font-bold border rounded-full px-2 py-0.5 ${getSuitabilityColor(entry.suitability_score)}`}>
                        {entry.suitability_score.toFixed(0)}%
                      </span>
                    </td>
                    <td className="px-5 py-4 text-slate-400 italic text-[11px] truncate max-w-[150px]" title={entry.bbch_sensitivity}>
                      {entry.bbch_sensitivity}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}
