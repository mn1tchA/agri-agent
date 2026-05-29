// Shared TypeScript interfaces used across all components

export interface AgentVote {
  vote: string;
  confidence: number;
  weight: number;
}

export interface AnalysisData {
  thread_id?: string;
  // Farm identity
  crop_type?: string;
  farm_area_sqm?: number;
  latitude?: number;
  longitude?: number;
  plant_growth_stage?: string;
  
  // New Genetic & Soil Config inputs
  seed_profile?: string;
  upov_id?: string | null;
  germination_rate_pct?: number;
  planting_date?: string;
  soil_texture?: string;
  pump_type?: string;
  pump_kw?: number;
  fuel_use_lph?: number;
  labor_workers?: number;
  labor_hours?: number;
  labor_wage_usd?: number;
  market_price_usd_per_kg?: number;

  // Sensor data
  temperature?: number;
  soil_moisture?: number;
  water_salinity?: number;
  satellite_water_productivity?: number;
  et0_today_mm?: number;
  
  // Weather
  weather_forecast?: string;
  
  // Agent analyses
  meteorologist_analysis?: string;
  botanist_analysis?: string;
  agronomist_analysis?: string;
  pedologist_analysis?: string;
  economist_analysis?: string;
  harvest_analysis?: string;
  orchestrator_analysis?: string;
  financial_analysis?: string;
  
  // Agronomist Agent outputs
  kc_value?: number;
  etc_mm_day?: number;
  active_bbch_stage?: string;
  er_emergence_probability?: number;
  agronomist_vote?: string;
  agronomist_confidence?: number;

  // Pedologist Agent outputs
  days_until_wilting?: number;
  soil_water_deficit_mm?: number;
  texture_suitability_score?: number;
  soil_ph_status?: string;
  pedologist_vote?: string;
  pedologist_confidence?: number;

  // Harvest Advisor outputs
  days_since_planting?: number;
  days_until_harvest?: number;
  harvest_ready?: boolean;
  harvest_window_start?: string;
  harvest_window_end?: string;
  gdd_progress_pct?: number;
  fertilizer_recommendation?: string;
  pesticide_alert?: string;
  soil_amendment?: string;
  pre_harvest_stress_recommended?: boolean;

  // Economist Agent outputs
  water_cost_usd?: number;
  electricity_cost_usd?: number;
  fuel_cost_usd?: number;
  labor_cost_usd?: number;
  total_operational_cost_usd?: number;
  roi_score?: number;
  yield_loss_pct_if_skipped?: number;
  crop_value_at_risk_usd?: number;
  economist_vote?: string;
  economist_confidence?: number;

  // Decision & Orchestrator outputs
  decision?: string;
  water_volume_liters?: number;
  nutrient_mix?: string;
  agent_votes?: Record<string, AgentVote> | string; // Can be dict or JSON string from SQLite
  last_irrigation_date?: string | null;

  reasoning_confidence?: number;

  // Anomaly detection
  anomaly_detected?: boolean;
  anomaly_reason?: string;
  
  // Actuation
  human_approved?: boolean | null;
  actuator_message?: string;
}

export interface HistoryLog extends Omit<AnalysisData, 'agent_votes'> {
  id: number;
  timestamp: string;
  thread_id: string;
  crop_type: string;
  farm_area_sqm: number;
  latitude: number;
  longitude: number;
  temperature: number;
  soil_moisture: number;
  water_salinity: number;
  plant_growth_stage: string;
  weather_forecast: string;
  decision: string;
  water_volume_liters: number;
  human_approved: boolean;
  outcome_rating: number | null;
  agent_votes?: string; // Stored as JSON string in SQL
}

export interface AggregateStats {
  total_decisions: number;
  irrigate_count: number;
  wait_count: number;
  total_water_liters: number;
  total_cost_usd: number;
  total_electricity_cost_usd: number;
  total_labor_cost_usd: number;
  total_fuel_cost_usd: number;
  total_water_cost_usd: number;
  avg_roi: number;
  approval_rate: number;
  avg_soil_moisture: number;
}

export interface FarmConfig {
  cropType: string;
  farmArea: number;
  moistureThreshold: number;
  latitude: number;
  longitude: number;
  waterSalinity: number;
  plantGrowthStage: string;
  seedProfile: string;
  upovId: string;
  germinationRatePct: number;
  plantingDate: string;
  soilTexture: string;
  pumpType: string;
  pumpKw: number;
  fuelUseLph: number;
  laborWorkers: number;
  laborHours: number;
  laborWageUsd: number;
  marketPriceUsdPerKg: number;
}

export interface CropPlannerEntry {
  eppo: string;
  crop: string;
  best_cultivar: string;
  time_to_harvest: number;
  initial_investment: number;
  expected_revenue: number;
  net_profit: number;
  water_need: string;
  suitability_score: number;
  bbch_sensitivity: string;
}

export type AgentStep =
  | 'idle'
  | 'sensors'
  | 'parallel_agents'
  | 'pedologist'
  | 'economics_harvest'
  | 'orchestrator'
  | 'awaiting'
  | 'done'
  | 'error';
