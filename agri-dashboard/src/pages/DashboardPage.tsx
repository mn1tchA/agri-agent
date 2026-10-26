import { useEffect, useState } from 'react';
import {
  Thermometer, Droplets, Leaf,
  Wind, Cpu, DollarSign, UserCheck, Activity, ChevronRight,
  AlertTriangle, RotateCcw, CloudRain, BadgeDollarSign, Sprout
} from 'lucide-react';

import { FarmConfigPanel } from '../components/FarmConfigPanel';
import { AgentTimeline } from '../components/AgentTimeline';
import { AgentReportCard } from '../components/AgentReportCard';
import { HumanApprovalGate } from '../components/HumanApprovalGate';
import { StatCard } from '../components/StatCard';
import { useAnalysis } from '../hooks/useAnalysis';
import { useFarmStore } from '../store/useFarmStore';
import type { FarmConfig } from '../types';

const CAPABILITIES = [
  { icon: Wind, label: 'Live Weather Telemetry' },
  { icon: Droplets, label: 'Soil Sensors' },
  { icon: Cpu, label: 'Multi-Agent Swarm' },
  { icon: DollarSign, label: 'Cost-Benefit Analysis' },
  { icon: UserCheck, label: 'Human-in-the-Loop' },
];

function WelcomeBanner({ onRun }: { onRun: () => void }) {
  return (
    <div className="glass-panel p-10 mb-8 text-center animate-slide-up max-w-3xl mx-auto relative overflow-hidden border border-slate-800">
      <div className="absolute -top-20 -left-20 w-56 h-56 rounded-full bg-emerald-500/[0.07] blur-3xl pointer-events-none" />
      <div className="absolute -bottom-20 -right-20 w-56 h-56 rounded-full bg-blue-500/[0.07] blur-3xl pointer-events-none" />

      <div className="animate-float inline-block mb-6 relative z-10">
        <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-emerald-400 to-emerald-600 flex items-center justify-center mx-auto shadow-xl shadow-emerald-500/30">
          <Leaf className="w-7 h-7 text-white" strokeWidth={2} />
        </div>
      </div>

      <div className="relative z-10">
        <h2 className="font-[var(--font-display)] text-2xl font-bold text-white mb-2">
          Precision Irrigation Decision Swarm
        </h2>
        <p className="text-slate-400 text-sm leading-relaxed max-w-md mx-auto mb-8">
          Configure farm parameters or select a registered farm, then trigger the autonomous multi-agent analysis pipeline.
        </p>

        <div className="flex flex-wrap justify-center gap-2 mb-8">
          {CAPABILITIES.map(({ icon: Icon, label }) => (
            <span
              key={label}
              className="chip bg-slate-800/80 text-slate-400 border border-slate-700/60 text-xs"
            >
              <Icon className="w-3 h-3" />
              {label}
            </span>
          ))}
        </div>

        <button onClick={onRun} className="btn-primary px-7 py-3 text-sm animate-glow-green">
          <Activity className="w-4 h-4" />
          Run Analysis Pipeline
          <ChevronRight className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}

export function DashboardPage() {
  const { selectedFarm } = useFarmStore();

  const [config, setConfig] = useState<FarmConfig>({
    cropType: selectedFarm?.crop_type || 'Wheat',
    farmArea: selectedFarm?.farm_area_sqm || 10000,
    moistureThreshold: selectedFarm?.moisture_threshold || 10.0,
    latitude: selectedFarm?.latitude || 35.6911,
    longitude: selectedFarm?.longitude || -0.6328,
    waterSalinity: selectedFarm?.water_salinity || 1.2,
    plantGrowthStage: selectedFarm?.plant_growth_stage || 'Vegetative Stage (High Water Demand)',
  });

  const [hasStarted, setHasStarted] = useState(false);

  useEffect(() => {
    if (selectedFarm) {
      setConfig({
        cropType: selectedFarm.crop_type,
        farmArea: selectedFarm.farm_area_sqm,
        moistureThreshold: selectedFarm.moisture_threshold,
        latitude: selectedFarm.latitude,
        longitude: selectedFarm.longitude,
        waterSalinity: selectedFarm.water_salinity,
        plantGrowthStage: selectedFarm.plant_growth_stage,
      });
    }
  }, [selectedFarm]);

  const {
    data,
    loading,
    hardwareStatus,
    currentStep,
    runAnalysis,
    handleApproval,
    reset,
  } = useAnalysis();

  const handleRun = () => {
    setHasStarted(true);
    runAnalysis(config);
  };

  const handleReset = () => {
    reset();
    setHasStarted(false);
  };

  const showWelcome = !hasStarted && !data && !loading;

  return (
    <div className="space-y-6">
      {/* ── Top Bar Controls ── */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-white font-[var(--font-display)] flex items-center gap-2">
            <span>Farm Operations</span>
            {selectedFarm && (
              <span className="badge badge-green text-xs font-normal">
                {selectedFarm.name}
              </span>
            )}
          </h2>
          <p className="text-xs text-slate-400">
            Real-time sensory telemetry and multi-agent biological decision engine
          </p>
        </div>

        <div className="flex items-center gap-2">
          {hasStarted && !loading && (
            <button onClick={handleReset} className="btn-secondary text-xs px-3 py-1.5 flex items-center gap-1.5">
              <RotateCcw className="w-3.5 h-3.5" />
              Reset Pipeline
            </button>
          )}

          <button
            onClick={handleRun}
            disabled={loading}
            className="btn-primary text-xs px-4 py-1.5 flex items-center gap-1.5 shadow-md shadow-emerald-500/20 disabled:opacity-50"
          >
            <Activity className="w-3.5 h-3.5" />
            {loading ? 'Analyzing...' : 'Run Pipeline'}
          </button>
        </div>
      </div>

      {showWelcome ? (
        <WelcomeBanner onRun={handleRun} />
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
          {/* Left Column: Farm Configuration & Live Sensors */}
          <div className="lg:col-span-4 space-y-4">
            <FarmConfigPanel
              config={config}
              onChange={setConfig}
            />

            {/* Live Sensor Mini Stats */}
            {data && (
              <div className="grid grid-cols-2 gap-3 animate-fade-in">
                <StatCard
                  label="Soil Moisture"
                  value={data.soil_moisture != null ? `${data.soil_moisture.toFixed(1)}%` : '—'}
                  subtext={data.soil_moisture != null ? `Target: ${config.moistureThreshold}%` : 'Reading sensors'}
                  icon={<Droplets className="w-4 h-4 text-blue-400" />}
                  accentColor="text-blue-400"
                  accentBg="bg-blue-500/10"
                  accentBorder="border-blue-500/20"
                />
                <StatCard
                  label="Temperature"
                  value={data.temperature != null ? `${data.temperature.toFixed(1)}°C` : '—'}
                  subtext="Open-Meteo Current"
                  icon={<Thermometer className="w-4 h-4 text-emerald-400" />}
                  accentColor="text-emerald-400"
                  accentBg="bg-emerald-500/10"
                  accentBorder="border-emerald-500/20"
                />
              </div>
            )}
          </div>

          {/* Right Column: Execution State Machine & Reports */}
          <div className="lg:col-span-8 space-y-6">
            {/* Timeline progression */}
            <AgentTimeline currentStep={currentStep} loading={loading} />

            {/* Anomaly warning banner if detected */}
            {data?.anomaly_detected && (
              <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/30 flex items-start gap-3 text-amber-200 animate-slide-up">
                <AlertTriangle className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
                <div>
                  <h4 className="text-sm font-semibold text-amber-300">Anomaly Warning Flagged</h4>
                  <p className="text-xs text-amber-200/90 mt-0.5">{data.anomaly_reason}</p>
                </div>
              </div>
            )}

            {/* Human Gate or Final Decision */}
            {data && (
              <HumanApprovalGate
                data={data}
                hardwareStatus={hardwareStatus}
                onApprove={handleApproval}
              />
            )}

            {/* Multi-Agent Deep Dive Report Cards */}
            {data && (
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 animate-fade-in">
                <AgentReportCard
                  title="Meteorologist"
                  icon={<CloudRain className="w-4 h-4 text-blue-400" />}
                  content={data.meteorologist_analysis}
                  loadingMessage="Analyzing weather forecast models..."
                  accentColor="text-blue-400"
                  accentBg="bg-blue-500/10"
                  accentBorder="border-blue-500/20"
                />
                <AgentReportCard
                  title="Botanist"
                  icon={<Sprout className="w-4 h-4 text-emerald-400" />}
                  content={data.botanist_analysis}
                  confidence={data.reasoning_confidence}
                  loadingMessage="Querying agronomic RAG memory..."
                  accentColor="text-emerald-400"
                  accentBg="bg-emerald-500/10"
                  accentBorder="border-emerald-500/20"
                />
                <AgentReportCard
                  title="Financial Analyst"
                  icon={<BadgeDollarSign className="w-4 h-4 text-amber-400" />}
                  content={data.financial_analysis}
                  loadingMessage="Optimizing irrigation tariff ROI..."
                  accentColor="text-amber-400"
                  accentBg="bg-amber-500/10"
                  accentBorder="border-amber-500/20"
                />
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
