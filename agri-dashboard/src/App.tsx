import { useState } from 'react';
import { ToastContainer } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';
import {
  Thermometer, Droplets, Sprout, CloudRain, Leaf,
  BadgeDollarSign, MapPin, Activity, ChevronRight,
  Wind, Cpu, DollarSign, UserCheck, Layers, Calendar,
} from 'lucide-react';

import { Header } from './components/Header';
import { FarmConfigPanel } from './components/FarmConfigPanel';
import { AgentTimeline } from './components/AgentTimeline';
import { AgentReportCard } from './components/AgentReportCard';
import { HumanApprovalGate } from './components/HumanApprovalGate';
import { AnalyticsDashboard } from './components/AnalyticsDashboard';
import { StatCard } from './components/StatCard';
import { CropPlannerTab } from './components/CropPlannerTab';
import { HarvestCalendar } from './components/HarvestCalendar';
import { useAnalysis } from './hooks/useAnalysis';
import type { FarmConfig } from './types';

const DEFAULT_CONFIG: FarmConfig = {
  cropType: 'Wheat',
  farmArea: 10000,
  moistureThreshold: 10.0,
  latitude: 35.6911,
  longitude: -0.6328,
  waterSalinity: 1.2,
  plantGrowthStage: 'Vegetative Stage (High Water Demand)',
  seedProfile: 'Standard',
  upovId: '',
  germinationRatePct: 85,
  plantingDate: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0], // 30 days ago
  soilTexture: 'Loamy',
  pumpType: 'Electric',
  pumpKw: 5.5,
  fuelUseLph: 0.0,
  laborWorkers: 1,
  laborHours: 2.0,
  laborWageUsd: 15.0,
  marketPriceUsdPerKg: 0.0,
};

const CAPABILITIES = [
  { icon: Wind,        label: 'Live weather data'    },
  { icon: Droplets,    label: 'Soil moisture sensors' },
  { icon: Cpu,         label: 'Multi-agent AI'        },
  { icon: DollarSign,  label: 'Cost-benefit analysis' },
  { icon: UserCheck,   label: 'Human-in-the-loop'     },
];

function WelcomeBanner({ onRun }: { onRun: () => void }) {
  return (
    <div className="glass-panel p-10 mb-8 text-center animate-slide-up max-w-3xl mx-auto relative overflow-hidden">
      <div className="absolute -top-20 -left-20 w-56 h-56 rounded-full bg-emerald-500/[0.07] blur-3xl pointer-events-none" />
      <div className="absolute -bottom-20 -right-20 w-56 h-56 rounded-full bg-blue-500/[0.07] blur-3xl pointer-events-none" />

      {/* Icon */}
      <div className="animate-float inline-block mb-6 relative z-10">
        <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-emerald-400 to-emerald-600 flex items-center justify-center mx-auto shadow-xl shadow-emerald-500/30">
          <Leaf className="w-7 h-7 text-white" strokeWidth={2} />
        </div>
      </div>

      <div className="relative z-10">
        <h2 className="font-[var(--font-display)] text-2xl font-bold text-white mb-2">
          Agri Agent
        </h2>
        <p className="text-slate-400 text-sm leading-relaxed max-w-md mx-auto mb-8">
          A multi-agent AI system for precision irrigation decisions.
          Configure your farm parameters, then run the analysis pipeline.
        </p>

        {/* Capability chips — icons only, no emojis */}
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
          Run Analysis
          <ChevronRight className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}

const getDaysSinceLastIrrigation = (dateStr?: string | null) => {
  if (!dateStr) return '14 days ago';
  try {
    const lastDate = new Date(dateStr);
    const diffTime = Math.abs(Date.now() - lastDate.getTime());
    const diffDays = Math.floor(diffTime / (1000 * 60 * 60 * 24));
    if (diffDays === 0) return 'Today';
    if (diffDays === 1) return 'Yesterday';
    return `${diffDays} days ago`;
  } catch {
    return '14 days ago';
  }
};

function App() {
  const [config, setConfig] = useState<FarmConfig>(DEFAULT_CONFIG);
  const [activeTab, setActiveTab] = useState<'dashboard' | 'planner' | 'analytics'>('dashboard');
  const [hasStarted, setHasStarted] = useState(false);

  const { data, loading, hardwareStatus, currentStep, runAnalysis, handleApproval, submitFeedback, reset } = useAnalysis();

  const handleRun = () => { setHasStarted(true); setActiveTab('dashboard'); runAnalysis(config); };
  const handleReset = () => { reset(); setHasStarted(false); setActiveTab('dashboard'); };

  const showWelcome = !hasStarted && !data && !loading && activeTab === 'dashboard';

  return (
    <div className="min-h-screen p-4 md:p-8 overflow-x-hidden relative">
      <ToastContainer
        theme="dark"
        position="bottom-right"
        toastStyle={{
          backgroundColor: '#1e293b',
          border: '1px solid rgba(255,255,255,0.08)',
          borderRadius: '12px',
          color: '#f1f5f9',
          fontFamily: 'Inter, sans-serif',
          fontSize: '13px',
        }}
      />

      <div className="max-w-7xl mx-auto relative z-10">
        <Header
          loading={loading}
          showAnalytics={activeTab === 'analytics'}
          hasData={!!data}
          onToggleAnalytics={() => setActiveTab(activeTab === 'analytics' ? 'dashboard' : 'analytics')}
          onRunAnalysis={handleRun}
          onReset={handleReset}
        />

        {/* Custom sleek Tab bar right below the header */}
        <div className="flex border-b border-white/[0.06] mb-6 gap-6 text-sm">
          <button
            className={`pb-2.5 font-medium transition-all relative ${
              activeTab === 'dashboard' ? 'text-emerald-400 font-semibold' : 'text-slate-400 hover:text-slate-200'
            }`}
            onClick={() => setActiveTab('dashboard')}
          >
            Dashboard
            {activeTab === 'dashboard' && (
              <div className="absolute bottom-0 left-0 w-full h-0.5 bg-emerald-500 rounded-full" />
            )}
          </button>
          <button
            className={`pb-2.5 font-medium transition-all relative ${
              activeTab === 'planner' ? 'text-emerald-400 font-semibold' : 'text-slate-400 hover:text-slate-200'
            }`}
            onClick={() => setActiveTab('planner')}
          >
            Crop Planner
            {activeTab === 'planner' && (
              <div className="absolute bottom-0 left-0 w-full h-0.5 bg-emerald-500 rounded-full" />
            )}
          </button>
          <button
            className={`pb-2.5 font-medium transition-all relative ${
              activeTab === 'analytics' ? 'text-emerald-400 font-semibold' : 'text-slate-400 hover:text-slate-200'
            }`}
            onClick={() => setActiveTab('analytics')}
          >
            Analytics
            {activeTab === 'analytics' && (
              <div className="absolute bottom-0 left-0 w-full h-0.5 bg-emerald-500 rounded-full" />
            )}
          </button>
        </div>

        <AgentTimeline currentStep={currentStep} loading={loading} />

        {activeTab === 'analytics' && (
          <div className="animate-slide-up">
            <AnalyticsDashboard onFeedback={submitFeedback} />
          </div>
        )}

        {activeTab === 'planner' && (
          <div className="animate-slide-up">
            <CropPlannerTab />
          </div>
        )}

        {showWelcome && <WelcomeBanner onRun={handleRun} />}

        {!data && activeTab === 'dashboard' && <FarmConfigPanel config={config} onChange={setConfig} />}

        {data && activeTab === 'dashboard' && (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">

            {/* Left: Telemetry */}
            <div className="lg:col-span-4 space-y-4">
              <div className="glass-panel p-5 animate-slide-up">
                <div className="flex items-center gap-2 mb-4 pb-3 border-b border-white/[0.06]">
                  <Activity className="w-3.5 h-3.5 text-slate-500" />
                  <h2 className="font-semibold text-xs text-slate-400 uppercase tracking-wider">Live Telemetry</h2>
                </div>
                <div className="space-y-3">
                  <StatCard
                    icon={<Thermometer className="w-4 h-4" strokeWidth={2} />}
                    label="Temperature"
                    value={data.temperature ?? '—'}
                    unit="°C"
                    accentColor="text-red-400"
                    accentBg="bg-red-500/10"
                    accentBorder="border-red-500/20"
                  />
                  <StatCard
                    icon={<Droplets className="w-4 h-4" strokeWidth={2} />}
                    label="Soil Moisture"
                    value={data.soil_moisture?.toFixed(1) ?? '—'}
                    unit="%"
                    accentColor="text-blue-400"
                    accentBg="bg-blue-500/10"
                    accentBorder="border-blue-500/20"
                  />
                  <StatCard
                    icon={<Sprout className="w-4 h-4" strokeWidth={2} />}
                    label="Water Salinity"
                    value={data.water_salinity ?? '—'}
                    unit="dS/m"
                    accentColor="text-amber-400"
                    accentBg="bg-amber-500/10"
                    accentBorder="border-amber-500/20"
                  />
                  <StatCard
                    icon={<Calendar className="w-4 h-4" strokeWidth={2} />}
                    label="Last Irrigated"
                    value={getDaysSinceLastIrrigation(data.last_irrigation_date)}
                    unit=""
                    accentColor="text-pink-400"
                    accentBg="bg-pink-500/10"
                    accentBorder="border-pink-500/20"
                  />

                  {data.latitude !== undefined && data.longitude !== undefined && (
                    <div className="glass-panel px-3.5 py-2.5 flex items-center gap-2 border border-slate-700/40">
                      <MapPin className="w-3.5 h-3.5 text-slate-600 flex-shrink-0" />
                      <span className="font-[var(--font-mono)] text-xs text-slate-500 tabular-nums">
                        {data.latitude?.toFixed(4)}, {data.longitude?.toFixed(4)}
                      </span>
                    </div>
                  )}
                </div>
              </div>

              {data.weather_forecast && (
                <div className="glass-panel p-5 animate-slide-up border border-blue-500/15">
                  <div className="flex items-center gap-2 mb-3">
                    <CloudRain className="w-3.5 h-3.5 text-blue-400" />
                    <h3 className="font-semibold text-xs text-blue-400 uppercase tracking-wider">Weather Forecast</h3>
                  </div>
                  <p className="text-sm text-slate-400 leading-relaxed">{data.weather_forecast}</p>
                </div>
              )}

              {data.plant_growth_stage && (
                <div className="glass-panel px-4 py-3.5 animate-slide-up border border-emerald-500/15">
                  <p className="section-label mb-1">Growth Stage</p>
                  <p className="text-sm text-slate-300">{data.plant_growth_stage}</p>
                </div>
              )}

              {/* Harvest Calendar */}
              <HarvestCalendar data={data} />
            </div>

            {/* Right: Agent Reports */}
            <div className="lg:col-span-8 space-y-4">
              <AgentReportCard
                title="Meteorologist"
                icon={<CloudRain className="w-4 h-4" />}
                content={data.meteorologist_analysis}
                loadingMessage="Analyzing precipitation forecast…"
                accentColor="text-blue-400"
                accentBg="bg-blue-500/10"
                accentBorder="border-blue-500/20"
              />
              <AgentReportCard
                title="Botanist"
                icon={<Leaf className="w-4 h-4" />}
                content={data.botanist_analysis}
                loadingMessage="Querying vector memory and analyzing plant health…"
                accentColor="text-emerald-400"
                accentBg="bg-emerald-500/10"
                accentBorder="border-emerald-500/20"
                confidence={data.reasoning_confidence}
              />
              <AgentReportCard
                title="Agronomist"
                icon={<Sprout className="w-4 h-4" />}
                content={data.agronomist_analysis}
                loadingMessage="Analyzing seed genetic profile and emergence rate…"
                accentColor="text-emerald-400"
                accentBg="bg-emerald-500/10"
                accentBorder="border-emerald-500/20"
                confidence={data.agronomist_confidence}
              />
              <AgentReportCard
                title="Pedologist"
                icon={<Layers className="w-4 h-4" />}
                content={data.pedologist_analysis}
                loadingMessage="Modeling soil water potential and wilting progress…"
                accentColor="text-amber-400"
                accentBg="bg-amber-500/10"
                accentBorder="border-amber-500/20"
                confidence={data.pedologist_confidence}
              />
              <AgentReportCard
                title="Economist"
                icon={<BadgeDollarSign className="w-4 h-4" />}
                content={data.economist_analysis}
                loadingMessage="Analyzing operational cost models and estimating ROI…"
                accentColor="text-purple-400"
                accentBg="bg-purple-500/10"
                accentBorder="border-purple-500/20"
                confidence={data.economist_confidence}
              />
              <AgentReportCard
                title="Harvest Advisor"
                icon={<Calendar className="w-4 h-4" />}
                content={data.harvest_analysis}
                loadingMessage="Calculating maturity indicators, GDD, and disease risk factors…"
                accentColor="text-pink-400"
                accentBg="bg-pink-500/10"
                accentBorder="border-pink-500/20"
              />
              <AgentReportCard
                title="Orchestrator"
                icon={<Cpu className="w-4 h-4" />}
                content={data.orchestrator_analysis || data.financial_analysis}
                loadingMessage="Resolving agent conflicts and computing consensus vote…"
                accentColor="text-blue-400"
                accentBg="bg-blue-500/10"
                accentBorder="border-blue-500/20"
              />

              {data.decision && (
                <HumanApprovalGate
                  data={data}
                  hardwareStatus={hardwareStatus}
                  onApprove={handleApproval}
                />
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;