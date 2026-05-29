"""
Agent nodes for the Agri-Agent LangGraph pipeline.

Pipeline:
    data_aggregation → anomaly_check →(anomaly)  → human_approval_gate
                                     →(normal)   → parallel_agents_fanout
                                                       ┌──────────────┐
                                                  meteorologist  botanist (+ RAG)
                                                       └──────┬───────┘
                                                           financial → actuator
"""
import json
import logging
import os
from datetime import datetime
from pydantic import BaseModel, Field
from tenacity import retry, stop_after_attempt, wait_exponential, RetryError
import httpx
from langchain_google_genai import ChatGoogleGenerativeAI
try:
    from langchain_groq import ChatGroq
    _groq_available = True
except ImportError:
    _groq_available = False

from config import settings
from state import FarmState
from memory import search_memory

# ---------------------------------------------------------------------------
# Logging — structured, replacing all print() statements
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log = logging.getLogger("agri_agent")

# ---------------------------------------------------------------------------
# Financial Model Constants  (move to config.py if per-farm customisation needed)
# ---------------------------------------------------------------------------
# Fraction of soil volume (m² × depth proxy) that holds water — agronomy approximation
# for a 15 cm effective root-zone depth: 1 m² × 0.15 m = 0.15 m³/m²
WATER_FRACTION_PER_SQM = 0.15           # m³ of water per m² of farm area per % moisture deficit

# Algerian water tariff proxy — residential/agricultural water in DZD per litre
# Source: ANBT (Agence Nationale des Barrages et Transferts) 2024 tariff estimates
WATER_COST_DZD_PER_LITRE = 0.045       # DZD / litre

# Baseline crop market value proxy — Algerian wheat at ~2.5 DZD/m² farm area
# Source: MADR (Ministère de l'Agriculture et du Développement Rural) 2023 wheat price reports
CROP_BASELINE_DZD_PER_SQM = 2.5        # DZD / m²

# ---------------------------------------------------------------------------
# LLM factory — pick Groq or Gemini based on config
# ---------------------------------------------------------------------------
def _build_llm():
    """Return the configured LLM. Groq is preferred (higher free-tier limits)."""
    provider = settings.llm_provider.lower()

    if provider == "groq":
        if not _groq_available:
            raise RuntimeError(
                "langchain-groq is not installed. Run: pip install langchain-groq"
            )
        if not settings.groq_api_key:
            raise RuntimeError(
                "GROQ_API_KEY is not set in .env. "
                "Get a free key at https://console.groq.com"
            )
        log.info("LLM backend: Groq (%s)", settings.groq_model)
        return ChatGroq(
            model=settings.groq_model,
            temperature=settings.groq_temperature,
            api_key=settings.groq_api_key,
        )

    # Fallback: Gemini
    log.info("LLM backend: Gemini (%s)", settings.gemini_model)
    return ChatGoogleGenerativeAI(
        model=settings.gemini_model,
        temperature=settings.gemini_temperature,
        google_api_key=settings.google_api_key,
    )


llm = _build_llm()


# ===========================================================================
# NODE 1 — Data Aggregation
# ===========================================================================
async def data_aggregation_node(state: FarmState) -> dict:
    """
    Fetch live weather, soil moisture, precipitation forecast, and FAO ET₀
    evapotranspiration data from Open-Meteo for the farm's GPS coordinates.

    ET₀ (FAO-56 Penman-Monteith method) is used as the satellite water
    productivity index — a direct equivalent of the WaPOR (Water Productivity
    through Open access of Remotely sensed data) regional water productivity
    metric used for agricultural assessment across Algeria and North Africa.
    """
    log.info("Entering DATA AGGREGATION node")

    lat = state.get("latitude", settings.default_latitude)
    lon = state.get("longitude", settings.default_longitude)

    async with httpx.AsyncClient(timeout=15.0) as client:

        # --- 1. Current weather + soil moisture ---
        log.info("Fetching current weather from Open-Meteo (lat=%.4f, lon=%.4f)", lat, lon)
        weather_url = (
            f"https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}&longitude={lon}"
            f"&current=temperature_2m,soil_moisture_3_to_9cm"
        )
        r = await client.get(weather_url)
        r.raise_for_status()
        d = r.json()
        real_temp = d.get("current", {}).get("temperature_2m", 25.0)
        current_moisture = d.get("current", {}).get("soil_moisture_3_to_9cm", 0.12) * 100

        # --- 2. 3-day precipitation forecast ---
        log.info("Fetching 3-day precipitation forecast")
        forecast_url = (
            f"https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}&longitude={lon}"
            f"&daily=precipitation_sum&timezone=auto"
        )
        rf = await client.get(forecast_url)
        rf.raise_for_status()
        df = rf.json()
        precip = df.get("daily", {}).get("precipitation_sum", [0, 0, 0])

        # --- 3. FAO ET₀ evapotranspiration — satellite water productivity proxy ---
        # Open-Meteo computes ET₀ using the FAO-56 Penman-Monteith method, which is the
        # same scientific basis as the FAO WaPOR platform used for regional water
        # productivity monitoring in Algeria and sub-Saharan Africa.
        log.info("Fetching FAO ET₀ evapotranspiration (WaPOR satellite water productivity proxy)")
        et0_url = (
            f"https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}&longitude={lon}"
            f"&daily=et0_fao_evapotranspiration&timezone=auto"
        )
        ret0 = await client.get(et0_url)
        ret0.raise_for_status()
        det0 = ret0.json()
        et0_list = det0.get("daily", {}).get("et0_fao_evapotranspiration", [5.0])
        et0_today_mm = (et0_list[0] if et0_list else None) or 5.0

    # Normalize ET₀ → [0.1, 1.0] satellite water productivity index
    # Low ET₀ (1 mm/day)  → WP = 1.0  (cool, low evaporation — highly efficient irrigation)
    # High ET₀ (10 mm/day) → WP = 0.1 (hot, high evaporation — water lost quickly)
    satellite_water_productivity = round(
        max(0.1, min(1.0, 1.0 - (et0_today_mm - 1.0) / 9.0)), 3
    )

    p0 = precip[0] if len(precip) > 0 else 0
    p1 = precip[1] if len(precip) > 1 else 0
    p2 = precip[2] if len(precip) > 2 else 0
    weather_forecast = (
        f"Precipitation Forecast — Today: {p0}mm | Tomorrow: {p1}mm | Day 3: {p2}mm"
    )

    log.info(
        "Data aggregation complete | temp=%.1f°C | moisture=%.2f%% | "
        "ET₀=%.2fmm/day | sat_productivity=%.3f | forecast=%s",
        real_temp, current_moisture, et0_today_mm, satellite_water_productivity, weather_forecast,
    )

    return {
        "soil_moisture": current_moisture,
        "temperature": real_temp,
        "satellite_water_productivity": satellite_water_productivity,
        "weather_forecast": weather_forecast,
        "et0_today_mm": et0_today_mm,
        # Pass-through user-provided fields
        "water_salinity": state.get("water_salinity", 1.2),
        "plant_growth_stage": state.get("plant_growth_stage", "Vegetative Stage (High Water Demand)"),
        "crop_type": state.get("crop_type", "Wheat"),
        "seed_profile": state.get("seed_profile", "Standard"),
        "upov_id": state.get("upov_id", ""),
        "germination_rate_pct": state.get("germination_rate_pct", 85.0),
        "planting_date": state.get("planting_date", "2026-04-01"),
        "soil_texture": state.get("soil_texture", "Loamy"),
        "pump_type": state.get("pump_type", "Electric"),
        "pump_kw": state.get("pump_kw", 5.5),
        "fuel_use_lph": state.get("fuel_use_lph", 0.0),
        "labor_workers": state.get("labor_workers", 1),
        "labor_hours": state.get("labor_hours", 2.0),
        "labor_wage_usd": state.get("labor_wage_usd", 15.0),
        "market_price_usd_per_kg": state.get("market_price_usd_per_kg", 0.0),
        "human_approved": None,
    }


# ===========================================================================
# NODE 1b — Anomaly Check
# Runs after data_aggregation, before any LLM agents.
# Critical readings trigger an immediate human-review bypass.
# ===========================================================================
async def anomaly_check_node(state: FarmState) -> dict:
    """
    Inspect live sensor readings for critical anomalies requiring immediate human review.

    If a critical condition is detected:
      - Sets anomaly_detected = True, decision = "anomaly"
      - The graph routes DIRECTLY to the human approval gate, bypassing all LLM agents
        (no wasted Gemini API calls during a hardware emergency).

    Anomaly thresholds:
      - Temperature  > 45°C   : Extreme heat event — shading/cooling required
      - Soil moisture > 92%   : Sensor flooding or field waterlogging
      - Soil moisture < 1%    : Sensor failure / disconnection
      - Salinity     > 8 dS/m : Critical crop damage threshold exceeded
    """
    log.info("Entering ANOMALY CHECK node")

    temp     = state.get("temperature", 25.0)
    moisture = state.get("soil_moisture", 20.0)
    salinity = state.get("water_salinity", 1.2)

    anomaly_reasons: list[str] = []

    if temp > 45.0:
        anomaly_reasons.append(
            f"🌡️ EXTREME HEAT: {temp}°C exceeds the 45°C safe operational limit. "
            f"Immediate shading and emergency cooling required."
        )
    if moisture > 92.0:
        anomaly_reasons.append(
            f"🌊 SENSOR FLOOD / WATERLOGGING: Soil moisture {moisture:.1f}% above 92%. "
            f"Possible sensor submersion or field flooding — do NOT irrigate."
        )
    if moisture < 1.0:
        anomaly_reasons.append(
            f"⚠️ SENSOR FAILURE: Soil moisture {moisture:.1f}% below physical minimum (1%). "
            f"Sensor may be damaged or disconnected — readings are unreliable."
        )
    if salinity > 8.0:
        anomaly_reasons.append(
            f"🧪 CRITICAL SALINITY: {salinity} dS/m far exceeds the 8.0 dS/m emergency threshold. "
            f"Severe crop damage imminent — halt all irrigation immediately."
        )

    if anomaly_reasons:
        full_reason = " | ".join(anomaly_reasons)
        log.warning("CRITICAL ANOMALY DETECTED — bypassing LLM agents: %s", full_reason)
        return {
            "anomaly_detected": True,
            "anomaly_reason": full_reason,
            "decision": "anomaly",
            "meteorologist_analysis": "",
            "botanist_analysis": "",
            "financial_analysis": (
                f"⛔ LLM pipeline bypassed — critical sensor anomaly detected: {full_reason}"
            ),
        }

    log.info("Anomaly check PASSED — proceeding to parallel agent analysis")
    return {
        "anomaly_detected": False,
        "anomaly_reason": "",
    }


# ===========================================================================
# NODE 1c — Parallel Agents Fan-out  (pass-through node)
# ===========================================================================
async def parallel_agents_fanout(state: FarmState) -> dict:
    """
    Pass-through node enabling conditional fan-out to both Meteorologist and Botanist
    in parallel. Only executed when anomaly_check_node finds no critical conditions.
    Two outgoing edges from this node cause LangGraph to run both agents concurrently.
    """
    return {}


# ===========================================================================
# NODE 2 — Meteorologist Agent  (runs in parallel with Botanist)
# ===========================================================================
class MeteorologistOutput(BaseModel):
    meteorologist_analysis: str = Field(
        description="Analysis of the weather forecast and irrigation recommendation."
    )
    rain_imminent: bool = Field(
        description="True if significant rain (>2mm) is expected in the next 48 hours."
    )


# NOTE: The Gemini SDK already performs its own internal exponential-backoff retries
# (typically 5-6 attempts). Tenacity is kept here only as an outer safety net for
# transient 5xx errors that slip past the SDK. Using stop_after_attempt(2) + a long
# minimum wait prevents the double-retry storm that burns free-tier quota.
@retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=2, min=60, max=120))
async def meteorologist_agent_node(state: FarmState) -> dict:
    """Analyze weather forecast and assess rain probability."""
    log.info("Entering METEOROLOGIST node")
    prompt = f"""You are an expert agricultural meteorologist.

Forecast Data:
{state.get('weather_forecast')}

Task:
1. Analyze if significant rain (>2mm) is expected in the next 48 hours.
2. If so, recommend delaying irrigation to save water costs.
3. Provide a clear, actionable analysis.

Be concise and specific. Reference the actual forecast numbers."""

    structured_llm = llm.with_structured_output(MeteorologistOutput)
    response = await structured_llm.ainvoke(prompt)
    log.info("Meteorologist complete | rain_imminent=%s", response.rain_imminent)
    return {"meteorologist_analysis": response.meteorologist_analysis}


# ===========================================================================
# NODE 3 — Botanist Agent  (runs in parallel with Meteorologist)
# ===========================================================================
class BotanistOutput(BaseModel):
    botanist_analysis: str = Field(
        description="Biological analysis of plant health, stress level, and water needs."
    )
    stress_level: str = Field(description="Plant stress level: 'Low', 'Medium', or 'High'")


@retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=2, min=60, max=120))
async def botanist_agent_node(state: FarmState) -> dict:
    """Analyze plant health using current sensor data, satellite productivity, and RAG memory."""
    log.info("Entering BOTANIST node")

    # RAG Memory Retrieval — filter by crop type for relevance
    query = (
        f"Soil moisture {state.get('soil_moisture'):.1f}%, "
        f"salinity {state.get('water_salinity')} dS/m, "
        f"temp {state.get('temperature')}°C for {state.get('crop_type')}."
    )
    log.info("Querying RAG memory: %s", query)
    try:
        past_memories = search_memory(query, k=3, crop_type=state.get("crop_type"))
        memory_context = "\n".join(f"- {m}" for m in past_memories) if past_memories else "No relevant past data available yet."
    except Exception as e:
        log.warning("RAG memory retrieval failed: %s", e)
        memory_context = "Memory retrieval failed. Proceeding with current data only."

    # Satellite water productivity context for the botanist
    swp = state.get("satellite_water_productivity", 0.5)
    if swp > 0.7:
        swp_label = "High efficiency (cool conditions, low evaporation)"
    elif swp > 0.4:
        swp_label = "Moderate efficiency"
    else:
        swp_label = "Low efficiency (high evaporation stress — irrigated water will be lost quickly)"

    prompt = f"""You are an expert plant biologist specializing in precision agriculture.

Crop Profile:
- Crop: {state.get('crop_type')} at {state.get('plant_growth_stage')}
- Temperature: {state.get('temperature')}°C
- Soil Moisture: {state.get('soil_moisture'):.1f}%
- Water Salinity: {state.get('water_salinity')} dS/m (note: >2.0 dS/m causes significant stress for most crops)
- Satellite Water Productivity Index: {swp:.3f} — {swp_label}
  (Derived from FAO ET₀ Penman-Monteith, equivalent to WaPOR regional water productivity data)

Historical Knowledge (from Vector Memory — similar past scenarios):
{memory_context}

Task:
1. Assess the plant's current water stress level (Low/Medium/High).
2. Explain the biological reasoning, considering the growth stage and salinity.
3. Factor in satellite water productivity — if evaporation is high (low WP index), note that timing irrigation for cooler periods will reduce water waste.
4. Reference historical patterns if relevant.
5. State clearly whether the plant needs water now.

Be specific and quantitative where possible."""

    structured_llm = llm.with_structured_output(BotanistOutput)
    response = await structured_llm.ainvoke(prompt)
    log.info("Botanist complete | stress_level=%s", response.stress_level)
    return {
        "botanist_analysis": response.botanist_analysis,
        "reasoning_confidence": {"Low": 0.3, "Medium": 0.6, "High": 0.9}.get(
            response.stress_level, 0.5
        ),
    }


# ===========================================================================
# Crop Database Loader & Helper
# ===========================================================================
def _load_crop_db():
    path = os.path.join(os.path.dirname(__file__), "crop_db.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        log.error("Failed to load crop_db.json: %s", e)
        return {}

CROP_DB = _load_crop_db()

def get_crop_profile(crop_type: str) -> tuple[str, dict]:
    """
    Returns (eppo_code, crop_data_dict) for the crop_type.
    Tries case-insensitive match on keys (EPPO codes) and common_name.
    """
    cleaned = crop_type.strip().upper()
    # 1. Direct EPPO code lookup
    if cleaned in CROP_DB:
        return cleaned, CROP_DB[cleaned]
    
    # 2. Case-insensitive common name lookup
    for eppo, data in CROP_DB.items():
        common = data.get("common_name", "").upper()
        if cleaned in common or common in cleaned:
            return eppo, data
            
    # 3. Fuzzy match of common mappings
    mappings = {
        "WHEAT": "TRZAW",
        "BARLEY": "HORVV",
        "MAIZE": "ZEAMX",
        "CORN": "ZEAMX",
        "TOMATO": "LYPES",
        "POTATO": "SOLTU",
        "SUNFLOWER": "HEFAN",
        "ONION": "ALLCE",
        "WATERMELON": "CITLA",
        "PEPPER": "CPSAN",
        "BELL PEPPER": "CPSAN",
        "SWEET PEPPER": "CPSAN",
        "COTTON": "GOSHI",
        "CHICKPEA": "CICAR",
        "ALFALFA": "MEDSA",
        "LUCERNE": "MEDSA"
    }
    for name, eppo in mappings.items():
        if name in cleaned or cleaned in name:
            if eppo in CROP_DB:
                return eppo, CROP_DB[eppo]
                
    # Fallback to Wheat (TRZAW)
    return "TRZAW", CROP_DB.get("TRZAW", {})


# ===========================================================================
# Structured LLM Output Schemas for New Agents
# ===========================================================================

class AgronomistOutput(BaseModel):
    kc_value: float = Field(description="Selected Crop Coefficient Kc.")
    etc_mm_day: float = Field(description="Evapotranspiration rate ETc in mm/day.")
    active_bbch_stage: str = Field(description="Active BBCH stage code and description.")
    er_emergence_probability: float = Field(description="Expected Field Emergence probability (0-1).")
    agronomist_vote: str = Field(description="Vote: 'irrigate' or 'wait'.")
    agronomist_confidence: float = Field(description="Confidence score (0.0 to 1.0).")
    agronomist_analysis: str = Field(description="DNA and genetic analysis explanation.")


class PedologistOutput(BaseModel):
    days_until_wilting: float = Field(description="Days until crop reaches wilting point.")
    soil_water_deficit_mm: float = Field(description="Soil water deficit in mm.")
    texture_suitability_score: float = Field(description="Suitability score (0-100) of this soil texture for this crop.")
    soil_ph_status: str = Field(description="pH suitability assessment, e.g. 'Optimal', 'Tolerable', or 'Critical Acidic/Alkaline'.")
    pedologist_vote: str = Field(description="Vote: 'irrigate' or 'wait'.")
    pedologist_confidence: float = Field(description="Confidence score (0.0 to 1.0).")
    pedologist_analysis: str = Field(description="Soil physics and water retention analysis.")


class EconomistOutput(BaseModel):
    water_cost_usd: float = Field(description="Calculated water cost in USD.")
    electricity_cost_usd: float = Field(description="Calculated electricity pump cost in USD.")
    fuel_cost_usd: float = Field(description="Calculated fuel cost in USD.")
    labor_cost_usd: float = Field(description="Calculated labor cost in USD.")
    total_operational_cost_usd: float = Field(description="Sum of all operational costs in USD.")
    roi_score: float = Field(description="Return on investment score.")
    yield_loss_pct_if_skipped: float = Field(description="Estimated yield loss percentage (0.0 to 1.0) if skipped.")
    crop_value_at_risk_usd: float = Field(description="Crop value at risk in USD.")
    economist_vote: str = Field(description="Vote: 'irrigate' or 'wait'.")
    economist_confidence: float = Field(description="Confidence score (0.0 to 1.0).")
    economist_analysis: str = Field(description="Cost-benefit and ROI analysis explanation.")


class HarvestOutput(BaseModel):
    days_since_planting: int = Field(description="Days since planting.")
    days_until_harvest: int = Field(description="Estimated days until harvest.")
    harvest_ready: bool = Field(description="Whether the crop is ready for harvest.")
    harvest_window_start: str = Field(description="Start date of harvest window.")
    harvest_window_end: str = Field(description="End date of harvest window.")
    gdd_progress_pct: float = Field(description="Growing Degree Days progress percentage (0-100).")
    fertilizer_recommendation: str = Field(description="NPK and fertilizer recommendations.")
    pesticide_alert: str = Field(description="Pest or disease warnings.")
    soil_amendment: str = Field(description="Soil amendment recommendation.")
    pre_harvest_stress_recommended: bool = Field(description="Whether pre-harvest drought stress is recommended.")
    harvest_analysis: str = Field(description="Harvest timing and crop maturity analysis.")


class OrchestratorOutput(BaseModel):
    orchestrator_analysis: str = Field(description="Detailed synthesis of the decision and conflict resolution.")
    decision: str = Field(description="Final resolved decision: 'irrigate', 'wait', or 'micro_irrigate'.")
    water_volume_liters: float = Field(description="Final water volume in liters.")
    nutrient_mix: str = Field(description="Recommended nutrient mix (e.g. NPK ratio or 'None').")


# ===========================================================================
# NEW AGENTS IMPLEMENTATION
# ===========================================================================

@retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=2, min=60, max=120))
async def agronomist_agent_node(state: FarmState) -> dict:
    """Analyze crop genetics, growth stage, Kc curve, and vote based on DNA stress response."""
    log.info("Entering AGRONOMIST node")
    crop_type = state.get("crop_type", "Wheat")
    eppo_code, crop_data = get_crop_profile(crop_type)
    
    # Determine days since planting
    days_since_planting = 30
    try:
        pdate = datetime.fromisoformat(state.get("planting_date", "").split("T")[0])
        days_since_planting = (datetime.now() - pdate).days
    except Exception:
        pass
        
    seed_profile = state.get("seed_profile", "Standard")
    cultivar_profiles = crop_data.get("cultivar_profiles", {})
    cultivar_data = cultivar_profiles.get(seed_profile, cultivar_profiles.get("Standard", {}))
    
    # Calculate Kc active and BBCH stage
    bbch_matrix = crop_data.get("bbch_matrix", {})
    active_stage = "Unknown Stage"
    bbch_code = "10-19"
    for code, info in bbch_matrix.items():
        r = info.get("days_range", [0, 999])
        if r[0] <= days_since_planting <= r[1]:
            bbch_code = code
            active_stage = f"BBCH {code}: {info.get('stage', '')} (Sensitivity: {info.get('sensitivity', '')})"
            break
            
    hydrology = crop_data.get("hydrology", {})
    kc_ini = hydrology.get("kc_ini", 0.4)
    kc_mid = hydrology.get("kc_mid", 1.1)
    kc_end = hydrology.get("kc_end", 0.4)
    
    # Simple rule-based Kc active
    stage_name = active_stage.lower()
    if any(kw in stage_name for kw in ["flowering", "heading", "silking", "bloom", "pollination"]):
        kc_active = kc_mid
    elif any(kw in stage_name for kw in ["matur", "ripen", "harvest"]):
        kc_active = kc_end
    elif any(kw in stage_name for kw in ["germination", "sprout"]):
        kc_active = kc_ini
    else:
        kc_active = (kc_ini + kc_mid) / 2.0
        
    # ET0
    et0 = state.get("et0_today_mm") or 5.0
    etc = kc_active * et0
    
    # Emergence
    soil_texture = state.get("soil_texture", "Loamy")
    soil_factor = 0.95 if soil_texture == "Sandy" else (0.80 if soil_texture == "Clay" else 0.90)
    current_month = datetime.now().month
    season_factor = 0.95 if 5 <= current_month <= 9 else 0.85
    germ_rate = state.get("germination_rate_pct", cultivar_data.get("germination_rate_pct", 85.0)) / 100.0
    er = germ_rate * soil_factor * season_factor
    
    prompt = f"""You are the Agronomist Agent (Genetics & DNA Expert).
    
    Crop Profile (EPPO: {eppo_code}):
    - Crop: {crop_data.get('common_name', crop_type)}
    - Seed Cultivar Profile: {seed_profile}
    - Cultivar Data: {json.dumps(cultivar_data)}
    - Days since planting: {days_since_planting}
    - Computed BBCH Stage: {active_stage}
    
    Environmental parameters:
    - Current Temperature: {state.get('temperature')}°C
    - Soil Texture: {soil_texture}
    - Water Salinity: {state.get('water_salinity')} dS/m
    
    Your computed baseline values:
    - Selected Kc: {kc_active}
    - ETc (evapotranspiration rate): {etc:.2f} mm/day (based on ET0 = {et0} mm/day)
    - Expected emergence rate (Er): {er:.2f}
    
    DNA Voting Rules:
    1. If temperature is high (>30°C) and water stress is likely:
       - If cultivar is "High-Yield" (High-Yield / Low-Resistance, low drought tolerance): vote 'irrigate' immediately to protect yield.
       - If cultivar is "Drought-Resistant" (high drought tolerance): vote 'wait' and override panic, since it can tolerate stress.
    2. Set confidence scale (0.0 to 1.0) higher for drought-tolerant or high-yield variants based on their profile.
    
    Analyze the genetic profile, explain crop coefficients and evapotranspiration, and vote.
    """
    
    structured_llm = llm.with_structured_output(AgronomistOutput)
    response = await structured_llm.ainvoke(prompt)
    log.info("Agronomist complete | vote=%s | Kc=%.2f", response.agronomist_vote, response.kc_value)
    return {
        "kc_value": response.kc_value,
        "etc_mm_day": response.etc_mm_day,
        "active_bbch_stage": response.active_bbch_stage,
        "er_emergence_probability": response.er_emergence_probability,
        "agronomist_vote": response.agronomist_vote,
        "agronomist_confidence": response.agronomist_confidence,
        "agronomist_analysis": response.agronomist_analysis,
        "days_since_planting": days_since_planting
    }


@retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=2, min=60, max=120))
async def pedologist_agent_node(state: FarmState) -> dict:
    """Analyze soil physics, moisture depletion, wilting points, and vote."""
    log.info("Entering PEDOLOGIST node")
    
    from database import get_days_since_last_irrigation
    days_since_last_irrigation = get_days_since_last_irrigation()
    
    crop_type = state.get("crop_type", "Wheat")
    eppo_code, crop_data = get_crop_profile(crop_type)
    
    soil_texture = state.get("soil_texture", "Loamy")
    current_moisture = state.get("soil_moisture", 20.0)
    etc = state.get("etc_mm_day") or 4.0
    
    # Soil properties
    soil_props = {
        "Sandy": {"fc": 0.15, "wp": 0.05},
        "Loamy": {"fc": 0.28, "wp": 0.12},
        "Clay": {"fc": 0.38, "wp": 0.22}
    }.get(soil_texture, {"fc": 0.28, "wp": 0.12})
    
    fc = soil_props["fc"]
    wp = soil_props["wp"]
    
    # Root depth estimate based on days_since_planting
    days_since_planting = state.get("days_since_planting", 30)
    seed_profile = state.get("seed_profile", "Standard")
    cultivar_profiles = crop_data.get("cultivar_profiles", {})
    cultivar_data = cultivar_profiles.get(seed_profile, cultivar_profiles.get("Standard", {}))
    dtm_target = cultivar_data.get("dtm", 100)
    progress = min(1.0, days_since_planting / dtm_target)
    root_depth_m = round(0.15 + 0.35 * progress, 2)
    
    p_depletion = crop_data.get("hydrology", {}).get("p_depletion", 0.5)
    
    # Calculations
    raw = p_depletion * (fc - wp) * root_depth_m * 1000.0
    soil_water_deficit_mm = max(0.0, (fc - (current_moisture / 100.0)) * root_depth_m * 1000.0)
    
    moisture_pct = current_moisture
    wp_pct = wp * 100.0
    if etc > 0:
        days_until_wilting = max(0.0, (moisture_pct - wp_pct) / etc)
    else:
        days_until_wilting = 14.0
    
    # Texture suitability
    texture_range = crop_data.get("hydrology", {}).get("soil_texture_range", [])
    matched = False
    for tr in texture_range:
        if soil_texture.lower() in tr.lower():
            matched = True
            break
    suitability_score = 95.0 if matched else 50.0
    
    ph_optimal = crop_data.get("hydrology", {}).get("ph_optimal", [6.0, 7.5])
    ph_absolute = crop_data.get("hydrology", {}).get("ph_absolute", [5.5, 8.5])
    ec_max = crop_data.get("hydrology", {}).get("ec_max_ds_m", 4.0)
    salinity = state.get("water_salinity", 1.2)
    
    prompt = f"""You are the Pedologist Agent (Soil Physicist).
    
    Soil & Water Profile:
    - Soil Texture: {soil_texture} (FC = {fc*100}%, WP = {wp*100}%)
    - Current Soil Moisture: {current_moisture:.1f}%
    - Crop ETc water demand: {etc:.2f} mm/day
    - Root depth proxy: {root_depth_m} m
    - Critical depletion fraction (p): {p_depletion}
    - Days since last irrigation: {days_since_last_irrigation} days
    
    Your computed baseline values:
    - RAW (Readily Available Water): {raw:.2f} mm
    - Soil Water Deficit: {soil_water_deficit_mm:.2f} mm
    - Days until wilting: {days_until_wilting:.2f} days
    - Soil suitability score: {suitability_score}%
    
    Crop Tolerance Info:
    - Max Ec salinity: {ec_max} dS/m (Current: {salinity} dS/m)
    - pH Optimal: {ph_optimal}, Absolute: {ph_absolute}
    
    Voting Rules:
    1. If days_until_wilting < 1.0: vote 'irrigate' immediately (override everything, plant is wilting).
    2. If soil is Clay (high retention): lean towards 'wait' (can delay irrigation).
    3. If soil is Sandy (low retention): lean towards 'irrigate' (deficit is urgent).
    
    Provide a scientific explanation of soil matric potential, salinity/pH compatibility, and vote.
    """
    
    structured_llm = llm.with_structured_output(PedologistOutput)
    response = await structured_llm.ainvoke(prompt)
    log.info("Pedologist complete | vote=%s | days_to_wilting=%.1f", response.pedologist_vote, response.days_until_wilting)
    return {
        "days_until_wilting": response.days_until_wilting,
        "soil_water_deficit_mm": response.soil_water_deficit_mm,
        "texture_suitability_score": response.texture_suitability_score,
        "soil_ph_status": response.soil_ph_status,
        "pedologist_vote": response.pedologist_vote,
        "pedologist_confidence": response.pedologist_confidence,
        "pedologist_analysis": response.pedologist_analysis
    }


@retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=2, min=60, max=120))
async def economist_agent_node(state: FarmState) -> dict:
    """Run a 4-type USD operational cost model, calculate expected revenue + ROI, and vote."""
    log.info("Entering ECONOMIST node")
    crop_type = state.get("crop_type", "Wheat")
    eppo_code, crop_data = get_crop_profile(crop_type)
    
    # Calculate water volume
    moisture = state.get("soil_moisture", 20.0)
    moisture_deficit = 40.0 - moisture
    area_sq_meters = state.get("farm_area_sqm", 10000.0)
    
    baseline_liters = moisture_deficit * area_sq_meters * WATER_FRACTION_PER_SQM
    volume_L = max(0.0, min(baseline_liters, 500_000.0))
    
    # 4-Type Operational Cost Model (USD)
    water_cost = volume_L * settings.default_water_rate_usd
    
    pump_kw = state.get("pump_kw", 5.5)
    labor_hours = state.get("labor_hours", 2.0)
    elec_cost = pump_kw * labor_hours * settings.default_electricity_rate_usd
    
    fuel_use_lph = state.get("fuel_use_lph", 0.0)
    fuel_cost = fuel_use_lph * labor_hours * settings.default_fuel_price_usd
    
    labor_workers = state.get("labor_workers", 1)
    labor_wage_usd = state.get("labor_wage_usd", 15.0)
    labor_cost = labor_workers * labor_hours * labor_wage_usd
    
    total_cost = water_cost + elec_cost + fuel_cost + labor_cost
    
    # Revenue and ROI calculations
    seed_profile = state.get("seed_profile", "Standard")
    cultivar_profiles = crop_data.get("cultivar_profiles", {})
    cultivar_data = cultivar_profiles.get(seed_profile, cultivar_profiles.get("Standard", {}))
    yield_kg_ha = cultivar_data.get("yield_kg_ha", 3500.0)
    
    market_price = state.get("market_price_usd_per_kg") or 0.0
    if market_price <= 0.0:
        market_price = crop_data.get("economics", {}).get("market_price_usd_per_kg", 0.22)
        
    farm_area_ha = area_sq_meters / 10000.0
    expected_revenue = yield_kg_ha * farm_area_ha * market_price
    
    # Dynamic yield loss based on current stress
    botanist_analysis = state.get("botanist_analysis", "").lower()
    if "high stress" in botanist_analysis:
        yield_loss_pct = 0.30
    elif "medium stress" in botanist_analysis or "moderate stress" in botanist_analysis:
        yield_loss_pct = 0.15
    else:
        yield_loss_pct = 0.05
        
    value_at_risk = expected_revenue * yield_loss_pct
    
    roi = (value_at_risk - total_cost) / total_cost if total_cost > 0 else 0.0
    
    faostat_5yr = crop_data.get("economics", {}).get("faostat_5yr_avg_usd_per_kg", market_price)
    
    prompt = f"""You are the Economist Agent (Yield Optimizer).
    
    Financial Cost & ROI Model:
    - Crop: {crop_data.get('common_name', crop_type)}
    - Cultivar: {seed_profile} (Yield Ceiling: {yield_kg_ha} kg/ha)
    - Farm Area: {farm_area_ha:.4f} ha ({area_sq_meters:,.0f} m²)
    
    Operational Cost Inputs:
    - Calculated Water Cost: ${water_cost:.2f} (volume = {volume_L:,.0f}L)
    - Electricity Cost: ${elec_cost:.2f} (pump kW = {pump_kw}, hours = {labor_hours})
    - Fuel Cost: ${fuel_cost:.2f} (fuel use LPH = {fuel_use_lph})
    - Labor Cost: ${labor_cost:.2f} (workers = {labor_workers}, wage = ${labor_wage_usd}/hr)
    - TOTAL OPERATIONAL COST: ${total_cost:.2f}
    
    Revenue Optimization:
    - Expected Revenue: ${expected_revenue:.2f} (market price = ${market_price}/kg)
    - Estimated Yield Loss %: {yield_loss_pct * 100}%
    - Crop Value at Risk: ${value_at_risk:.2f}
    - Computed ROI: {roi:.2f}
    - FAOSTAT 5-Year Average Price: ${faostat_5yr}/kg
    
    Voting Rules:
    1. If market price (${market_price}) is unusually low (below FAOSTAT 5-yr avg of ${faostat_5yr}): vote 'wait' (saves operational costs, stresses plant slightly).
    2. If market price is at an all-time high: vote 'irrigate' (maximizing yield value outweighs any operational expense).
    3. If ROI > 2.0: vote 'irrigate'.
    4. If ROI < 0.5: vote 'wait'.
    
    Provide a complete cost-benefit analysis, detailing all 4 cost types in USD, and submit your vote.
    """
    
    structured_llm = llm.with_structured_output(EconomistOutput)
    response = await structured_llm.ainvoke(prompt)
    log.info("Economist complete | vote=%s | ROI=%.2f | total_cost=%.2f USD", response.economist_vote, response.roi_score, response.total_operational_cost_usd)
    return {
        "water_cost_usd": response.water_cost_usd,
        "electricity_cost_usd": response.electricity_cost_usd,
        "fuel_cost_usd": response.fuel_cost_usd,
        "labor_cost_usd": response.labor_cost_usd,
        "total_operational_cost_usd": response.total_operational_cost_usd,
        "roi_score": response.roi_score,
        "yield_loss_pct_if_skipped": response.yield_loss_pct_if_skipped,
        "crop_value_at_risk_usd": response.crop_value_at_risk_usd,
        "economist_vote": response.economist_vote,
        "economist_confidence": response.economist_confidence,
        "economist_analysis": response.economist_analysis
    }


@retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=2, min=60, max=120))
async def harvest_agent_node(state: FarmState) -> dict:
    """Predict maturity dates, track GDD progress, recommend BBCH phase NPK, flag disease risks."""
    log.info("Entering HARVEST ADVISOR node")
    crop_type = state.get("crop_type", "Wheat")
    eppo_code, crop_data = get_crop_profile(crop_type)
    
    days_since_planting = state.get("days_since_planting", 30)
    
    seed_profile = state.get("seed_profile", "Standard")
    cultivar_profiles = crop_data.get("cultivar_profiles", {})
    cultivar_data = cultivar_profiles.get(seed_profile, cultivar_profiles.get("Standard", {}))
    
    dtm = cultivar_data.get("dtm", 100)
    gdd_target = cultivar_data.get("gdd_target", 1200)
    
    t_base = crop_data.get("hydrology", {}).get("gdd_base_temp_c", 5.0)
    temp = state.get("temperature", 22.0)
    gdd_est = days_since_planting * max(0.0, temp - t_base)
    gdd_pct = min(100.0, round((gdd_est / gdd_target) * 100.0, 1))
    
    days_until_harvest = max(0, dtm - days_since_planting)
    harvest_ready = (days_until_harvest == 0)
    
    # NPK recommendation lookup based on stage
    npk_phases = crop_data.get("npk_phases", [])
    npk_rec = "No specific NPK recommendation for this stage."
    # Find matching stage based on days_since_planting or BBCH
    for phase in npk_phases:
        npk_rec = f"Apply N:{phase.get('N_kg_ha')} P:{phase.get('P_kg_ha')} K:{phase.get('K_kg_ha')} kg/ha — {phase.get('note')}"
        break
        
    phytosanitary = crop_data.get("phytosanitary", {})
    vuln = ", ".join(phytosanitary.get("high_vulnerability", ["Pests"]))
    pesticide_alert = f"Monitor crop for: {vuln}."
    
    # Fungal risk check
    fungal_cond = phytosanitary.get("fungal_risk_conditions", {})
    temp_threshold = fungal_cond.get("temp_above_c", 25)
    if temp > temp_threshold:
        pesticide_alert += f" ⚠️ High temperature ({temp}°C) increases fungal/pest disease risks."
        
    soil_amendment = "Apply standard organic compost if organic matter is low."
    
    prompt = f"""You are the Harvest Advisor Agent.
    
    Crop Stage Info:
    - Crop: {crop_data.get('common_name', crop_type)}
    - Days Since Sowing: {days_since_planting}
    - Target Days to Maturity (DTM): {dtm}
    - Estimated GDD: {gdd_est:.1f} / {gdd_target} ({gdd_pct}%)
    
    Crop parameters:
    - NPK schedules: {json.dumps(npk_phases)}
    - Phytosanitary profile: {json.dumps(phytosanitary)}
    
    Your computed baseline recommendations:
    - Estimated Days until harvest: {days_until_harvest}
    - Fertilizer recommendation: {npk_rec}
    - Pesticide alert: {pesticide_alert}
    - Soil amendment: {soil_amendment}
    
    Provide a harvest window projection, confirm fertilizer requirements for the current BBCH stage, alert for any pest/fungal threats, and write your analysis.
    """
    
    structured_llm = llm.with_structured_output(HarvestOutput)
    response = await structured_llm.ainvoke(prompt)
    log.info("Harvest complete | days_until_harvest=%d", response.days_until_harvest)
    return {
        "days_since_planting": response.days_since_planting,
        "days_until_harvest": response.days_until_harvest,
        "harvest_ready": response.harvest_ready,
        "harvest_window_start": response.harvest_window_start,
        "harvest_window_end": response.harvest_window_end,
        "gdd_progress_pct": response.gdd_progress_pct,
        "fertilizer_recommendation": response.fertilizer_recommendation,
        "pesticide_alert": response.pesticide_alert,
        "soil_amendment": response.soil_amendment,
        "pre_harvest_stress_recommended": response.pre_harvest_stress_recommended,
        "harvest_analysis": response.harvest_analysis
    }


# ===========================================================================
# NODE 5 — Orchestrator Node  (fan-in conflict resolution)
# ===========================================================================

@retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=2, min=60, max=120))
async def orchestrator_node(state: FarmState) -> dict:
    """Synthesize all agent reports and votes, apply consensus rules, and resolve conflicts."""
    log.info("Entering ORCHESTRATOR node")
    
    # Calculate base water volume for reference
    moisture = state.get("soil_moisture", 20.0)
    moisture_deficit = 40.0 - moisture
    area_sq_meters = state.get("farm_area_sqm", 10000.0)
    baseline_liters = moisture_deficit * area_sq_meters * WATER_FRACTION_PER_SQM
    base_volume = max(0.0, min(baseline_liters, 500_000.0))
    
    # Gather votes & confidences
    weights = {
        "agronomist": 0.25,
        "pedologist": 0.22,
        "economist": 0.20,
        "meteorologist": 0.18,
        "botanist": 0.15,
        "harvest": 0.10
    }
    
    # Derive votes dynamically from agent analyses and state
    votes = {
        "agronomist": {
            "vote": state.get("agronomist_vote", "wait"), 
            "confidence": state.get("agronomist_confidence", 0.8)
        },
        "pedologist": {
            "vote": state.get("pedologist_vote", "wait"), 
            "confidence": state.get("pedologist_confidence", 0.8)
        },
        "economist": {
            "vote": state.get("economist_vote", "wait"), 
            "confidence": state.get("economist_confidence", 0.8)
        },
        "meteorologist": {
            "vote": "wait" if any(kw in state.get("meteorologist_analysis", "").lower() for kw in ["delay", "rain", "precip"]) else "irrigate",
            "confidence": 0.8
        },
        "botanist": {
            "vote": "irrigate" if state.get("reasoning_confidence", 0.5) > 0.5 else "wait",
            "confidence": state.get("reasoning_confidence", 0.5)
        },
        "harvest": {
            "vote": "wait" if state.get("pre_harvest_stress_recommended", False) else "irrigate",
            "confidence": 0.7
        }
    }
    
    weighted_irrigate = 0.0
    weighted_wait = 0.0
    
    for agent, info in votes.items():
        w = weights[agent]
        v = info["vote"].lower()
        conf = info["confidence"]
        if v == "irrigate":
            weighted_irrigate += w * conf
        elif v == "wait":
            weighted_wait += w * conf
            
    gap = abs(weighted_irrigate - weighted_wait)
    if gap < 0.15:
        decision = "micro_irrigate"
        final_volume = base_volume * 0.5
    elif weighted_irrigate > weighted_wait:
        decision = "irrigate"
        final_volume = base_volume
    else:
        decision = "wait"
        final_volume = 0.0
        
    # Serialize agent votes
    agent_votes_dict = {}
    for agent, info in votes.items():
        agent_votes_dict[agent] = {
            "vote": info["vote"],
            "confidence": round(info["confidence"], 2),
            "weight": weights[agent]
        }
        
    nutrient_mix = "None"
    if decision in ("irrigate", "micro_irrigate"):
        nutrient_mix = state.get("fertilizer_recommendation", "") or "N:P:K 20:10:10 — standard growth formula"
        
    prompt = f"""You are the Orchestrator (The Swarm Decision Maker & Critic).
    
    Consensus Calculations:
    - Weighted Irrigate Score: {weighted_irrigate:.2f}
    - Weighted Wait Score: {weighted_wait:.2f}
    - Difference Gap: {gap:.2f}
    - Target Resolved Decision: {decision}
    - Target Water Volume: {final_volume:.0f} L
    
    Here is the voting profile of each agent:
    {json.dumps(votes, indent=2)}
    
    Agent Reports:
    - Meteorologist: {state.get('meteorologist_analysis', 'N/A')[:150]}
    - Botanist: {state.get('botanist_analysis', 'N/A')[:150]}
    - Agronomist: {state.get('agronomist_analysis', 'N/A')[:150]}
    - Pedologist: {state.get('pedologist_analysis', 'N/A')[:150]}
    - Economist: {state.get('economist_analysis', 'N/A')[:150]}
    - Harvest Advisor: {state.get('harvest_analysis', 'N/A')[:150]}
    
    Provide a unified critical synthesis. Explain the conflict and the rationale for the final decision.
    """
    
    structured_llm = llm.with_structured_output(OrchestratorOutput)
    response = await structured_llm.ainvoke(prompt)
    
    # Enforce resolved values based on code logic for absolute correctness
    resolved_decision = response.decision if response.decision in ("irrigate", "wait", "micro_irrigate") else decision
    if resolved_decision == "micro_irrigate":
        resolved_volume = base_volume * 0.5
    elif resolved_decision == "irrigate":
        resolved_volume = base_volume
    else:
        resolved_volume = 0.0
        
    log.info("Orchestrator complete | decision=%s | volume=%.0fL", resolved_decision, resolved_volume)
    return {
        "decision": resolved_decision,
        "water_volume_liters": resolved_volume,
        "nutrient_mix": response.nutrient_mix if response.nutrient_mix else nutrient_mix,
        "orchestrator_analysis": response.orchestrator_analysis,
        "agent_votes": agent_votes_dict
    }


# ===========================================================================
# NODE 6 — Actuator  (MCP Hardware Interface)
# ===========================================================================
async def actuator_node(state: FarmState) -> dict:
    """
    Send hardware commands via the MCP (Model Context Protocol) irrigate_valve tool.
    """
    from mcp_server import mcp as irrigation_mcp
    from fastmcp import Client

    log.info(
        "Entering ACTUATOR node | human_approved=%s | decision=%s",
        state.get("human_approved"), state.get("decision"),
    )

    decision    = state.get("decision", "wait")
    is_approved = state.get("human_approved", False)
    thread_id   = state.get("thread_id", "pipeline")
    crop        = state.get("crop_type", "Unknown")
    lat         = state.get("latitude", settings.default_latitude)
    lon         = state.get("longitude", settings.default_longitude)
    salinity    = state.get("water_salinity", 1.2)
    volume      = state.get("water_volume_liters", 0) or 0.0

    try:
        if decision == "anomaly" and is_approved:
            # Human overrode the anomaly — dispatch conservative irrigation volume
            async with Client(irrigation_mcp) as client:
                result = await client.call_tool("irrigate_valve", {
                    "crop_type": crop,
                    "volume_liters": max(volume, 5000.0),
                    "latitude": lat,
                    "longitude": lon,
                    "water_salinity": salinity,
                    "thread_id": thread_id,
                })
            ack = json.loads(result.content[0].text) if result and hasattr(result, "content") and result.content else {}
            cmd_id = ack.get("command_id", "N/A")
            msg = (
                f"⚠️ Anomaly Override authorized by human operator. "
                f"MCP irrigate_valve executed | Command ID: {cmd_id}. "
                f"Anomaly context: {state.get('anomaly_reason', 'See logs.')}"
            )
            log.warning("ANOMALY OVERRIDE — human authorized irrigation | cmd=%s", cmd_id)

        elif decision == "anomaly" and not is_approved:
            # Human confirmed: issue emergency stop, close all valves
            async with Client(irrigation_mcp) as client:
                result = await client.call_tool("emergency_stop", {
                    "reason": state.get("anomaly_reason", "Critical anomaly detected by sensors"),
                    "thread_id": thread_id,
                })
            ack = json.loads(result.content[0].text) if result and hasattr(result, "content") and result.content else {}
            msg = (
                f"🛑 Emergency Stop issued via MCP. All valves CLOSED. "
                f"Hardware ACK: {ack.get('status', 'EXECUTED')}. "
                f"Anomaly: {state.get('anomaly_reason', 'Unknown')}"
            )
            log.warning("MCP EMERGENCY STOP issued via actuator_node")

        elif is_approved:
            # Normal or micro irrigation approval path
            async with Client(irrigation_mcp) as client:
                result = await client.call_tool("irrigate_valve", {
                    "crop_type": crop,
                    "volume_liters": volume,
                    "latitude": lat,
                    "longitude": lon,
                    "water_salinity": salinity,
                    "thread_id": thread_id,
                })
            ack = json.loads(result.content[0].text) if result and hasattr(result, "content") and result.content else {}
            cmd_id = ack.get("command_id", "N/A")
            hw_ack = ack.get("hardware_ack", "ACK")
            msg = (
                f"✅ MCP irrigate_valve executed successfully. "
                f"Command ID: {cmd_id} | {volume:,.0f}L dispatched to {crop} "
                f"at ({lat:.4f}, {lon:.4f}). Hardware: {hw_ack}"
            )
            log.info("MCP hardware actuated | volume=%.0fL | cmd=%s", volume, cmd_id)

        else:
            msg = "❌ Actuation rejected by human operator. No MCP commands sent."
            log.info("Hardware actuation rejected by human")

    except Exception as e:
        log.error("MCP actuation error: %s", e)
        msg = f"⚠️ MCP actuation encountered an error: {e}. Check MCP server logs."

    return {"actuator_message": msg}
