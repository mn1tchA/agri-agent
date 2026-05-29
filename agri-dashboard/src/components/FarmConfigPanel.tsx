import { Settings, MapPin, Navigation, ChevronDown, Sprout, Droplets, Shield, Cpu, BadgeDollarSign } from 'lucide-react';
import { useEffect, useState } from 'react';
import type { FarmConfig } from '../types';

interface FarmConfigPanelProps {
  config: FarmConfig;
  onChange: (c: FarmConfig) => void;
}

const GROWTH_STAGES = [
  'Germination Stage (Low Water Demand)',
  'Seedling Stage (Moderate Water Demand)',
  'Vegetative Stage (High Water Demand)',
  'Flowering Stage (Critical Water Demand)',
  'Fruit Development Stage (High Water Demand)',
  'Maturation Stage (Reduced Water Demand)',
];

const CROP_SUGGESTIONS = ['Wheat', 'Corn', 'Barley', 'Tomato', 'Potato', 'Sunflower', 'Cotton', 'Alfalfa', 'Chickpea', 'Watermelon', 'Onion'];

function FieldGroup({ label, hint, warn, children }: {
  label: string; hint?: string; warn?: boolean; children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <label className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">{label}</label>
      {children}
      {hint && (
        <p className={`text-[11px] leading-snug ${warn ? 'text-amber-400' : 'text-slate-600'}`}>{hint}</p>
      )}
    </div>
  );
}

function SectionHeader({ icon, title }: { icon: React.ReactNode; title: string }) {
  return (
    <div className="flex items-center gap-2 mb-4">
      <div className="w-5 h-5 flex items-center justify-center text-slate-500">
        {icon}
      </div>
      <span className="section-label">{title}</span>
      <div className="flex-1 h-px bg-white/[0.05] ml-1" />
    </div>
  );
}

function SalinityBar({ value }: { value: number }) {
  const pct = Math.min(100, (value / 10) * 100);
  const { color, level } =
    value > 4 ? { color: '#ef4444', level: 'Critical' } :
    value > 2 ? { color: '#f59e0b', level: 'Elevated' } :
               { color: '#10b981', level: 'Normal'   };

  return (
    <div className="mt-2.5">
      <div className="flex justify-between items-center mb-1.5">
        <span className="text-[10px] text-slate-600">Salinity level</span>
        <span className="text-[10px] font-semibold" style={{ color }}>{level}</span>
      </div>
      <div className="h-1.5 rounded-full bg-slate-800 overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{ width: `${pct}%`, backgroundColor: color }}
        />
      </div>
    </div>
  );
}

export function FarmConfigPanel({ config, onChange }: FarmConfigPanelProps) {
  const [geoLoading, setGeoLoading] = useState(false);
  const [mounted, setMounted] = useState(false);
  useEffect(() => { setMounted(true); }, []);

  const set = (k: keyof FarmConfig, v: string | number) => onChange({ ...config, [k]: v });

  const useLocation = () => {
    if (!navigator.geolocation) return;
    setGeoLoading(true);
    navigator.geolocation.getCurrentPosition(
      p => {
        onChange({
          ...config,
          latitude: +p.coords.latitude.toFixed(4),
          longitude: +p.coords.longitude.toFixed(4),
        });
        setGeoLoading(false);
      },
      () => setGeoLoading(false)
    );
  };

  const areaHa = (config.farmArea / 10000).toFixed(2);
  const salinityWarn = config.waterSalinity > 2;

  return (
    <div className={`glass-panel p-6 mb-5 max-w-4xl mx-auto transition-all duration-500 ${mounted ? 'animate-slide-up' : 'opacity-0'}`}>

      {/* Header */}
      <div className="flex items-center gap-3 mb-6 pb-5 border-b border-white/[0.06]">
        <div className="w-9 h-9 rounded-xl bg-emerald-500/15 flex items-center justify-center flex-shrink-0">
          <Settings className="w-4 h-4 text-emerald-400" />
        </div>
        <div>
          <h2 className="font-semibold text-sm text-white">Farm Configuration</h2>
          <p className="text-[11px] text-slate-500 mt-0.5">Set your farm parameters before running the analysis</p>
        </div>
      </div>

      {/* Section 1: Farm Identity */}
      <div className="mb-6">
        <SectionHeader icon={<Sprout className="w-3.5 h-3.5" />} title="Farm Identity" />
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <FieldGroup label="Crop Type" hint="Type or select from suggestions">
            <input
              type="text"
              list="crop-list"
              value={config.cropType}
              onChange={e => set('cropType', e.target.value)}
              placeholder="e.g. Wheat"
              className="modern-input"
            />
            <datalist id="crop-list">
              {CROP_SUGGESTIONS.map(c => <option key={c} value={c} />)}
            </datalist>
          </FieldGroup>

          <FieldGroup label="Farm Area (m²)" hint={`≈ ${areaHa} hectares`}>
            <input
              type="number"
              min={1}
              max={10000000}
              value={config.farmArea}
              onChange={e => set('farmArea', +e.target.value)}
              className="modern-input"
            />
          </FieldGroup>

          <FieldGroup
            label="Dryness Threshold (%)"
            hint={
              config.moistureThreshold < 5
                ? 'Very low — irrigation rarely triggers'
                : config.moistureThreshold > 40
                ? 'Very high — will trigger often'
                : 'Irrigate when moisture drops below this'
            }
          >
            <input
              type="number"
              min={0}
              max={100}
              step={0.5}
              value={config.moistureThreshold}
              onChange={e => set('moistureThreshold', +e.target.value)}
              className="modern-input"
            />
          </FieldGroup>
        </div>
      </div>

      {/* Section 2: Genetic & Soil Profile */}
      <div className="mb-6">
        <SectionHeader icon={<Shield className="w-3.5 h-3.5" />} title="Genetic & Soil Profile" />
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <FieldGroup label="Seed Cultivar Profile" hint="Drives evapotranspiration curve">
            <div className="relative">
              <select
                value={config.seedProfile}
                onChange={e => set('seedProfile', e.target.value)}
                className="modern-input appearance-none pr-8 cursor-pointer"
              >
                <option value="Standard">Standard (Heirloom)</option>
                <option value="Drought-Resistant">Drought-Resistant (GMO)</option>
                <option value="High-Yield">High-Yield (Hybrid)</option>
              </select>
              <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-500 pointer-events-none" />
            </div>
          </FieldGroup>

          <FieldGroup label="UPOV Variety ID" hint="Patent tracking code (optional)">
            <input
              type="text"
              value={config.upovId}
              onChange={e => set('upovId', e.target.value)}
              placeholder="e.g. UPOV-9827-X"
              className="modern-input"
            />
          </FieldGroup>

          <FieldGroup label="Germination Rate (%)" hint="Target seed viability probability">
            <input
              type="number"
              min={0}
              max={100}
              value={config.germinationRatePct}
              onChange={e => set('germinationRatePct', +e.target.value)}
              className="modern-input"
            />
          </FieldGroup>

          <FieldGroup label="Sowing Date" hint="Date crop was planted">
            <input
              type="date"
              value={config.plantingDate}
              onChange={e => set('plantingDate', e.target.value)}
              className="modern-input"
            />
          </FieldGroup>

          <FieldGroup label="Soil Texture" hint="Drives matric water potential">
            <div className="relative">
              <select
                value={config.soilTexture}
                onChange={e => set('soilTexture', e.target.value)}
                className="modern-input appearance-none pr-8 cursor-pointer"
              >
                <option value="Sandy">Sandy</option>
                <option value="Loamy">Loamy</option>
                <option value="Clay">Clay</option>
              </select>
              <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-500 pointer-events-none" />
            </div>
          </FieldGroup>
        </div>
      </div>

      {/* Section 3: Farm Equipment & Costs */}
      <div className="mb-6">
        <SectionHeader icon={<Cpu className="w-3.5 h-3.5" />} title="Farm Equipment & Costs (USD)" />
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <FieldGroup label="Pumping Method" hint="Equipment power source">
            <div className="relative">
              <select
                value={config.pumpType}
                onChange={e => set('pumpType', e.target.value)}
                className="modern-input appearance-none pr-8 cursor-pointer"
              >
                <option value="Electric">Electric Pump</option>
                <option value="Diesel">Diesel Generator</option>
              </select>
              <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-500 pointer-events-none" />
            </div>
          </FieldGroup>

          <FieldGroup label="Pump Power (kW)" hint="Active electrical consumption">
            <input
              type="number"
              min={0}
              step={0.1}
              value={config.pumpKw}
              onChange={e => set('pumpKw', +e.target.value)}
              className="modern-input"
            />
          </FieldGroup>

          <FieldGroup label="Fuel Consumption (L/hr)" hint="Diesel fuel rate (if diesel)">
            <input
              type="number"
              min={0}
              step={0.1}
              value={config.fuelUseLph}
              onChange={e => set('fuelUseLph', +e.target.value)}
              className="modern-input"
              disabled={config.pumpType === 'Electric'}
            />
          </FieldGroup>

          <FieldGroup label="Required Workforce" hint="Number of workers to irrigate">
            <input
              type="number"
              min={0}
              value={config.laborWorkers}
              onChange={e => set('laborWorkers', +e.target.value)}
              className="modern-input"
            />
          </FieldGroup>

          <FieldGroup label="Labor Duration (Hours)" hint="Hours spent setting up/monitoring">
            <input
              type="number"
              min={0}
              step={0.5}
              value={config.laborHours}
              onChange={e => set('laborHours', +e.target.value)}
              className="modern-input"
            />
          </FieldGroup>

          <FieldGroup label="Hourly Labor Wage ($)" hint="Hourly wage per worker (USD)">
            <input
              type="number"
              min={0}
              step={0.5}
              value={config.laborWageUsd}
              onChange={e => set('laborWageUsd', +e.target.value)}
              className="modern-input"
            />
          </FieldGroup>
        </div>
      </div>

      {/* Section 4: GPS Location */}
      <div className="mb-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <div className="w-5 h-5 flex items-center justify-center text-slate-500">
              <MapPin className="w-3.5 h-3.5" />
            </div>
            <span className="section-label">GPS Location</span>
            <div className="flex-1 h-px bg-white/[0.05] ml-1 w-12" />
          </div>
          <button
            onClick={useLocation}
            disabled={geoLoading}
            className="btn-secondary px-3 py-1.5 text-xs"
          >
            <Navigation className={`w-3 h-3 ${geoLoading ? 'animate-spin-icon' : ''}`} />
            {geoLoading ? 'Locating…' : 'Use My Location'}
          </button>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <FieldGroup label="Latitude" hint="Decimal degrees · −90 to 90">
            <input
              type="number"
              min={-90}
              max={90}
              step={0.0001}
              value={config.latitude}
              onChange={e => set('latitude', +e.target.value)}
              className="modern-input"
            />
          </FieldGroup>
          <FieldGroup label="Longitude" hint="Decimal degrees · −180 to 180">
            <input
              type="number"
              min={-180}
              max={180}
              step={0.0001}
              value={config.longitude}
              onChange={e => set('longitude', +e.target.value)}
              className="modern-input"
            />
          </FieldGroup>
        </div>
      </div>

      {/* Section 5: Conditions & Market */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div>
          <SectionHeader icon={<Droplets className="w-3.5 h-3.5" />} title="Conditions" />
          <div className="grid grid-cols-1 gap-4">
            <FieldGroup
              label="Water Salinity (dS/m)"
              hint={salinityWarn ? '⚠ Above 2.0 dS/m causes crop stress' : 'Normal range: 0 – 2.0 dS/m'}
              warn={salinityWarn}
            >
              <input
                type="number"
                min={0}
                max={20}
                step={0.1}
                value={config.waterSalinity}
                onChange={e => set('waterSalinity', +e.target.value)}
                className="modern-input"
              />
              <SalinityBar value={config.waterSalinity} />
            </FieldGroup>

            <FieldGroup label="Growth Stage" hint="Affects water demand calculation">
              <div className="relative">
                <select
                  value={config.plantGrowthStage}
                  onChange={e => set('plantGrowthStage', e.target.value)}
                  className="modern-input appearance-none pr-8 cursor-pointer"
                >
                  {GROWTH_STAGES.map(s => <option key={s} value={s}>{s}</option>)}
                </select>
                <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-500 pointer-events-none" />
              </div>
            </FieldGroup>
          </div>
        </div>

        <div>
          <SectionHeader icon={<BadgeDollarSign className="w-3.5 h-3.5" />} title="Market Valuations" />
          <FieldGroup label="Local Crop Price ($/kg)" hint="Leave at 0.00 for default scientific database values">
            <input
              type="number"
              min={0}
              step={0.01}
              value={config.marketPriceUsdPerKg}
              onChange={e => set('marketPriceUsdPerKg', +e.target.value)}
              className="modern-input"
            />
          </FieldGroup>
        </div>
      </div>
    </div>
  );
}
