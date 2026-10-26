import { useEffect, useState } from 'react';
import { Sprout, Plus, MapPin, Droplets, Thermometer, AlertTriangle, ShieldCheck, Check, Trash2, RefreshCw } from 'lucide-react';
import { toast } from 'react-toastify';
import { useFarmStore } from '../store/useFarmStore';
import { useAuthStore } from '../store/useAuthStore';
import { apiClient } from '../api/client';
import type { Farm } from '../types';

export function FarmsPage() {
  const { farms, selectedFarm, selectFarm, fetchFarms, createFarm, deleteFarm, alerts, fetchAlerts } = useFarmStore();
  const { user } = useAuthStore();

  const [showModal, setShowModal] = useState(false);
  const [isScanning, setIsScanning] = useState(false);

  // New Farm form state
  const [name, setName] = useState('');
  const [cropType, setCropType] = useState('Wheat');
  const [farmArea, setFarmArea] = useState(10000);
  const [moistureThreshold, setMoistureThreshold] = useState(10.0);
  const [latitude, setLatitude] = useState(35.6911);
  const [longitude, setLongitude] = useState(-0.6328);
  const [waterSalinity, setWaterSalinity] = useState(1.2);

  useEffect(() => {
    fetchFarms();
    fetchAlerts();
  }, [fetchFarms, fetchAlerts]);

  const handleCreateFarm = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await createFarm({
        name,
        crop_type: cropType,
        farm_area_sqm: farmArea,
        moisture_threshold: moistureThreshold,
        latitude,
        longitude,
        water_salinity: waterSalinity,
      });
      toast.success(`Farm '${name}' created successfully!`);
      setShowModal(false);
      setName('');
    } catch {
      toast.error('Failed to create farm.');
    }
  };

  const handleDelete = async (farm: Farm) => {
    if (!window.confirm(`Are you sure you want to delete farm '${farm.name}'?`)) return;
    const ok = await deleteFarm(farm.id);
    if (ok) toast.success(`Farm '${farm.name}' deleted.`);
    else toast.error('Failed to delete farm.');
  };

  const handleRunScanNow = async () => {
    setIsScanning(true);
    try {
      const res = await apiClient.post<{ farms_inspected: number; details: unknown[] }>('/api/v1/scheduler/run-now', {});
      toast.success(`Automated surveillance check completed across ${res.farms_inspected} farms.`);
      await fetchAlerts();
    } catch {
      toast.error('Scan execution failed.');
    } finally {
      setIsScanning(false);
    }
  };

  const isOperator = user?.role === 'operator' || user?.role === 'admin';
  const isAdmin = user?.role === 'admin';

  return (
    <div className="space-y-8 animate-fade-in">
      {/* ── Page Header ── */}
      <div className="flex flex-wrap items-center justify-between gap-4 pb-4 border-b border-slate-800">
        <div>
          <h2 className="text-xl font-bold text-white font-[var(--font-display)] flex items-center gap-2">
            <Sprout className="w-5 h-5 text-emerald-400" />
            <span>Farm Directory & Multi-Tenancy</span>
          </h2>
          <p className="text-xs text-slate-400">
            Manage your agricultural holdings, geospatial coordinates, and automated surveillance rules.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={handleRunScanNow}
            disabled={isScanning}
            className="btn-secondary text-xs px-3.5 py-2 flex items-center gap-2"
            title="Trigger APScheduler anomaly check"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isScanning ? 'animate-spin' : ''}`} />
            {isScanning ? 'Scanning...' : 'Run Anomaly Scan Now'}
          </button>

          {isOperator && (
            <button
              onClick={() => setShowModal(true)}
              className="btn-primary text-xs px-3.5 py-2 flex items-center gap-1.5"
            >
              <Plus className="w-4 h-4" />
              Add New Farm
            </button>
          )}
        </div>
      </div>

      {/* ── Farm Cards Grid ── */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
        {farms.map((farm) => {
          const isSelected = selectedFarm?.id === farm.id;
          return (
            <div
              key={farm.id}
              className={`glass-panel p-5 border transition-all duration-200 relative flex flex-col justify-between ${
                isSelected
                  ? 'border-emerald-500/60 bg-emerald-500/[0.04] shadow-lg shadow-emerald-500/10'
                  : 'border-slate-800 hover:border-slate-700'
              }`}
            >
              <div>
                <div className="flex items-start justify-between gap-2 mb-3">
                  <div>
                    <h3 className="font-semibold text-white text-base leading-tight">{farm.name}</h3>
                    <span className="inline-block mt-1 badge badge-green text-[10px] py-0.5 px-2">
                      {farm.crop_type}
                    </span>
                  </div>

                  {isSelected && (
                    <span className="flex items-center gap-1 text-[11px] font-semibold text-emerald-400 bg-emerald-500/10 border border-emerald-500/30 px-2 py-0.5 rounded-full">
                      <Check className="w-3 h-3" /> Active
                    </span>
                  )}
                </div>

                <div className="space-y-2 text-xs text-slate-400 mt-4">
                  <div className="flex items-center justify-between py-1 border-b border-slate-800/60">
                    <span className="flex items-center gap-1.5">
                      <MapPin className="w-3.5 h-3.5 text-slate-500" /> Location
                    </span>
                    <span className="font-mono text-slate-200">
                      {farm.latitude.toFixed(4)}, {farm.longitude.toFixed(4)}
                    </span>
                  </div>

                  <div className="flex items-center justify-between py-1 border-b border-slate-800/60">
                    <span className="flex items-center gap-1.5">
                      <Droplets className="w-3.5 h-3.5 text-blue-400" /> Moisture Target
                    </span>
                    <span className="font-semibold text-slate-200">{farm.moisture_threshold}%</span>
                  </div>

                  <div className="flex items-center justify-between py-1 border-b border-slate-800/60">
                    <span className="flex items-center gap-1.5">
                      <Thermometer className="w-3.5 h-3.5 text-amber-400" /> Water Salinity
                    </span>
                    <span className="font-semibold text-slate-200">{farm.water_salinity} dS/m</span>
                  </div>

                  <div className="flex items-center justify-between py-1">
                    <span>Farm Area</span>
                    <span className="text-slate-200">
                      {(farm.farm_area_sqm / 10000).toFixed(1)} ha ({farm.farm_area_sqm.toLocaleString()} m²)
                    </span>
                  </div>
                </div>
              </div>

              <div className="mt-5 pt-3 border-t border-slate-800/80 flex items-center justify-between gap-2">
                <button
                  onClick={() => selectFarm(farm)}
                  disabled={isSelected}
                  className={`text-xs py-1.5 px-3 rounded-lg font-medium transition-all ${
                    isSelected
                      ? 'bg-slate-800 text-slate-500 cursor-default'
                      : 'btn-secondary hover:border-emerald-500/40 text-emerald-400'
                  }`}
                >
                  {isSelected ? 'Currently Selected' : 'Select Farm'}
                </button>

                {isAdmin && (
                  <button
                    onClick={() => handleDelete(farm)}
                    className="p-1.5 rounded-lg text-slate-500 hover:text-rose-400 hover:bg-rose-500/10 transition-colors"
                    title="Delete Farm"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* ── Background Anomaly Alerts Feed ── */}
      <div className="glass-panel p-6 border border-slate-800 shadow-xl space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-slate-800">
          <div className="flex items-center gap-2.5">
            <AlertTriangle className="w-5 h-5 text-amber-400" />
            <h3 className="font-semibold text-white text-base font-[var(--font-display)]">
              Surveillance Alerts & Anomaly Feed
            </h3>
          </div>
          <span className="text-xs text-slate-400">APScheduler Automated Diagnostics</span>
        </div>

        {alerts.length === 0 ? (
          <p className="text-xs text-slate-500 py-6 text-center">
            No active anomalies detected. All farms within safe agronomic parameters.
          </p>
        ) : (
          <div className="space-y-2.5">
            {alerts.slice(0, 5).map((a) => (
              <div
                key={a.id}
                className="p-3 rounded-lg bg-slate-900/60 border border-slate-800 flex items-start justify-between gap-3 text-xs"
              >
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <span
                      className={`badge text-[10px] py-0.5 px-1.5 ${
                        a.severity === 'CRITICAL' ? 'badge-rose' : 'badge-amber'
                      }`}
                    >
                      {a.alert_type}
                    </span>
                    <span className="text-slate-500 text-[10px]">
                      {new Date(a.timestamp).toLocaleTimeString()}
                    </span>
                  </div>
                  <p className="text-slate-300">{a.message}</p>
                </div>
                {a.acknowledged ? (
                  <span className="text-[10px] text-slate-500 font-semibold flex items-center gap-1">
                    <ShieldCheck className="w-3.5 h-3.5 text-emerald-500" /> Ack
                  </span>
                ) : (
                  <button
                    onClick={async () => {
                      await apiClient.post(`/api/v1/alerts/${a.id}/ack`, {});
                      await fetchAlerts();
                      toast.info(`Alert #${a.id} acknowledged.`);
                    }}
                    className="btn-secondary text-[10px] py-1 px-2 shrink-0"
                  >
                    Acknowledge
                  </button>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* ── Add New Farm Modal ── */}
      {showModal && (
        <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="glass-panel max-w-md w-full p-6 border border-slate-700 shadow-2xl animate-scale-up space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <h3 className="font-semibold text-white text-base">Register New Farm</h3>
              <button
                onClick={() => setShowModal(false)}
                className="text-slate-400 hover:text-white text-lg font-bold"
              >
                &times;
              </button>
            </div>

            <form onSubmit={handleCreateFarm} className="space-y-4 text-xs">
              <div>
                <label className="block text-slate-300 font-semibold mb-1">Farm Name</label>
                <input
                  type="text"
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g. Mitidja Citrus Orchard"
                  className="input-field w-full text-xs"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-300 font-semibold mb-1">Crop Type</label>
                  <select
                    value={cropType}
                    onChange={(e) => setCropType(e.target.value)}
                    className="input-field w-full text-xs"
                  >
                    <option value="Wheat">Wheat</option>
                    <option value="Tomato">Tomato</option>
                    <option value="Potato">Potato</option>
                    <option value="Barley">Barley</option>
                    <option value="Date Palm">Date Palm</option>
                    <option value="Citrus">Citrus</option>
                    <option value="Olive">Olive</option>
                  </select>
                </div>

                <div>
                  <label className="block text-slate-300 font-semibold mb-1">Area (m²)</label>
                  <input
                    type="number"
                    min="100"
                    step="100"
                    value={farmArea}
                    onChange={(e) => setFarmArea(Number(e.target.value))}
                    className="input-field w-full text-xs"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-300 font-semibold mb-1">Latitude</label>
                  <input
                    type="number"
                    step="0.0001"
                    value={latitude}
                    onChange={(e) => setLatitude(Number(e.target.value))}
                    className="input-field w-full text-xs"
                  />
                </div>
                <div>
                  <label className="block text-slate-300 font-semibold mb-1">Longitude</label>
                  <input
                    type="number"
                    step="0.0001"
                    value={longitude}
                    onChange={(e) => setLongitude(Number(e.target.value))}
                    className="input-field w-full text-xs"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-300 font-semibold mb-1">Moisture Target (%)</label>
                  <input
                    type="number"
                    step="0.5"
                    min="1"
                    max="50"
                    value={moistureThreshold}
                    onChange={(e) => setMoistureThreshold(Number(e.target.value))}
                    className="input-field w-full text-xs"
                  />
                </div>
                <div>
                  <label className="block text-slate-300 font-semibold mb-1">Salinity (dS/m)</label>
                  <input
                    type="number"
                    step="0.1"
                    min="0"
                    max="15"
                    value={waterSalinity}
                    onChange={(e) => setWaterSalinity(Number(e.target.value))}
                    className="input-field w-full text-xs"
                  />
                </div>
              </div>

              <div className="pt-3 border-t border-slate-800 flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  className="btn-secondary text-xs px-3 py-2"
                >
                  Cancel
                </button>
                <button type="submit" className="btn-primary text-xs px-4 py-2">
                  Save Farm
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
