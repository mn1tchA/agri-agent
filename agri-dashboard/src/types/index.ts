// Shared TypeScript interfaces used across all components

export interface AnalysisData {
  thread_id?: string;
  // Farm identity
  crop_type?: string;
  farm_area_sqm?: number;
  latitude?: number;
  longitude?: number;
  plant_growth_stage?: string;
  // Sensor data
  temperature?: number;
  soil_moisture?: number;
  water_salinity?: number;
  satellite_water_productivity?: number;
  // Weather
  weather_forecast?: string;
  // Agent analyses
  meteorologist_analysis?: string;
  botanist_analysis?: string;
  financial_analysis?: string;
  reasoning_confidence?: number;
  // Decision
  decision?: string;
  water_volume_liters?: number;
  nutrient_mix?: string;
  financial_cost_dzd?: number;
  crop_value_at_risk_dzd?: number;
  // Anomaly detection
  anomaly_detected?: boolean;
  anomaly_reason?: string;
  // Actuation
  human_approved?: boolean | null;
  actuator_message?: string;
}

export interface HistoryLog {
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
  meteorologist_analysis: string;
  botanist_analysis: string;
  financial_analysis: string;
  reasoning_confidence: number;
  decision: string;
  water_volume_liters: number;
  financial_cost_dzd: number;
  crop_value_at_risk_dzd: number;
  human_approved: boolean;
  outcome_rating: number | null;
}

export interface AggregateStats {
  total_decisions: number;
  irrigate_count: number;
  wait_count: number;
  total_water_liters: number;
  total_cost_dzd: number;
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
}

export type AgentStep =
  | 'idle'
  | 'sensors'
  | 'meteorologist'
  | 'botanist'
  | 'financial'
  | 'awaiting'
  | 'done'
  | 'error';
