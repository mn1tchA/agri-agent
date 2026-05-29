"""
FarmState — the single source of truth flowing through the LangGraph pipeline.
"""
from typing import TypedDict, Optional


class FarmState(TypedDict):
    # --- Pipeline Run Identity ---
    thread_id: str             # pipeline run ID for MCP audit tracing

    # --- Farm Identity & Location ---
    crop_type: str
    farm_area_sqm: float
    latitude: float
    longitude: float

    # --- User-Configurable Sensor & Farm Inputs ---
    target_moisture_threshold: float
    water_salinity: float          # dS/m — user provided or sensor
    plant_growth_stage: str        # e.g. "Vegetative Stage (High Water Demand)"
    
    # Genetic & Soil Profile Config
    seed_profile: str              # "Standard", "Drought-Resistant", "High-Yield"
    upov_id: Optional[str]         # Legal patent/registration identifier
    germination_rate_pct: float    # Seed lot germination rate
    planting_date: str             # Sowing date ISO string (e.g. YYYY-MM-DD)
    soil_texture: str              # "Sandy", "Loamy", "Clay"

    # Farm Equipment & Cost Model Inputs
    pump_type: str                 # "Electric", "Diesel"
    pump_kw: float                 # Pump power rating in kW
    fuel_use_lph: float            # Diesel engine fuel consumption in L/hour
    labor_workers: int             # Number of workers involved in irrigation
    labor_hours: float             # Duration of labor in hours
    labor_wage_usd: float          # Hourly wage in USD
    market_price_usd_per_kg: float # Market price of crop in USD (0.0 for DB fallback)

    # --- Live Sensor / API Data ---
    soil_moisture: float           # % — from open-meteo
    temperature: float             # °C — from open-meteo
    satellite_water_productivity: float

    # --- Forecasting ---
    weather_forecast: str

    # --- Multi-Agent Analyses & Votes ---
    meteorologist_analysis: str
    botanist_analysis: str
    agronomist_analysis: str
    pedologist_analysis: str
    economist_analysis: str
    harvest_analysis: str
    orchestrator_analysis: str

    # --- DNA & Agronomist Metrics ---
    kc_value: float
    etc_mm_day: float
    active_bbch_stage: str
    er_emergence_probability: float
    agronomist_vote: str           # "irrigate" | "wait"
    agronomist_confidence: float   # 0.0 - 1.0

    # --- Soil Matric & Pedology Metrics ---
    days_until_wilting: float
    soil_water_deficit_mm: float
    texture_suitability_score: float
    soil_ph_status: str
    pedologist_vote: str           # "irrigate" | "wait"
    pedologist_confidence: float   # 0.0 - 1.0

    # --- Harvest & Phenological Metrics ---
    days_since_planting: int
    days_until_harvest: int
    harvest_ready: bool
    harvest_window_start: str
    harvest_window_end: str
    gdd_progress_pct: float
    fertilizer_recommendation: str
    pesticide_alert: str
    soil_amendment: str
    pre_harvest_stress_recommended: bool

    # --- ROI & Cost Model Outputs (USD) ---
    water_cost_usd: float
    electricity_cost_usd: float
    fuel_cost_usd: float
    labor_cost_usd: float
    total_operational_cost_usd: float
    roi_score: float
    yield_loss_pct_if_skipped: float
    crop_value_at_risk_usd: float
    economist_vote: str            # "irrigate" | "wait"
    economist_confidence: float    # 0.0 - 1.0

    # --- AI Reasoning (Consensus / Legacy placeholder) ---
    biological_reasoning: str
    reasoning_confidence: float    # 0.0–1.0

    # --- Decision Engine Outputs ---
    decision: str                  # "irrigate" | "wait" | "micro_irrigate" | "anomaly" | "error"
    water_volume_liters: float
    nutrient_mix: str
    agent_votes: dict              # Dict of agent name -> {"vote": vote, "confidence": conf, "weight": weight}
    last_irrigation_date: Optional[str]

    # --- Anomaly Detection ---
    anomaly_detected: bool  # True if critical sensor anomaly detected by anomaly_check_node
    anomaly_reason: str     # Human-readable description of the detected anomaly

    # --- Human-in-the-Loop ---
    human_approved: Optional[bool]

    # --- Actuation ---
    actuator_message: str
