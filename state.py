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

    # --- User-Configurable Sensor Inputs ---
    target_moisture_threshold: float
    water_salinity: float          # dS/m — user provided or sensor
    plant_growth_stage: str        # e.g. "Vegetative Stage (High Water Demand)"

    # --- Live Sensor / API Data ---
    soil_moisture: float           # % — from open-meteo
    temperature: float             # °C — from open-meteo
    satellite_water_productivity: float

    # --- Forecasting ---
    weather_forecast: str

    # --- Multi-Agent Analyses ---
    meteorologist_analysis: str
    botanist_analysis: str
    financial_analysis: str

    # --- AI Reasoning (Botanist structured output) ---
    biological_reasoning: str
    reasoning_confidence: float    # 0.0–1.0

    # --- Decision Engine Outputs ---
    decision: str                  # "irrigate" | "wait" | "error"
    water_volume_liters: float
    nutrient_mix: str
    financial_cost_dzd: float
    crop_value_at_risk_dzd: float

    # --- Anomaly Detection ---
    anomaly_detected: bool  # True if critical sensor anomaly detected by anomaly_check_node
    anomaly_reason: str     # Human-readable description of the detected anomaly

    # --- Human-in-the-Loop ---
    human_approved: Optional[bool]

    # --- Actuation ---
    actuator_message: str
