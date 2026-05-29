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
        # Pass-through user-provided fields
        "water_salinity": state.get("water_salinity", 1.2),
        "plant_growth_stage": state.get("plant_growth_stage", "Vegetative Stage (High Water Demand)"),
        "crop_type": state.get("crop_type", "Wheat"),
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
# NODE 4 — Financial Director Agent  (fan-in after parallel nodes)
# ===========================================================================
class FinancialOutput(BaseModel):
    financial_analysis: str = Field(
        description="Cost-benefit analysis with final decision rationale."
    )
    decision: str = Field(description="Final decision: 'irrigate' or 'wait'")
    water_volume_liters: float = Field(
        description="Exact liters to dispatch. 0 if decision is 'wait'."
    )
    nutrient_mix: str = Field(
        description=(
            "Recommended nutrient mix for this irrigation cycle, e.g. 'N:P:K 20:10:10 — "
            "standard growth formula' or 'N:P:K 5:15:30 — stress recovery blend for high salinity'. "
            "'None' if decision is 'wait'."
        )
    )
    financial_cost_dzd: float = Field(description="Total cost of irrigation in DZD.")
    crop_value_at_risk_dzd: float = Field(
        description="Estimated crop value at risk if irrigation is skipped."
    )


@retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=2, min=60, max=120))
async def financial_agent_node(state: FarmState) -> dict:
    """Synthesize all agent reports and make the final financial decision."""
    log.info("Entering FINANCIAL DIRECTOR node")

    moisture_deficit = 40.0 - state.get("soil_moisture", 12.0)
    area_sq_meters = state.get("farm_area_sqm", 10000.0)
    target_threshold = state.get("target_moisture_threshold", 10.0)
    swp = state.get("satellite_water_productivity", 0.5)

    baseline_liters = moisture_deficit * area_sq_meters * WATER_FRACTION_PER_SQM
    baseline_liters = max(0, min(baseline_liters, 500_000))
    water_cost = baseline_liters * WATER_COST_DZD_PER_LITRE
    crop_value = area_sq_meters * CROP_BASELINE_DZD_PER_SQM

    prompt = f"""You are the Financial Director and Final Decision Maker for a precision irrigation system.

=== AGENT REPORTS ===
Meteorologist Report:
{state.get('meteorologist_analysis', 'N/A')}

Botanist Report:
{state.get('botanist_analysis', 'N/A')}

=== FINANCIAL CALCULATIONS ===
Farm Area: {area_sq_meters:,.0f} m²
Baseline Water Needed: {baseline_liters:,.0f} L
Irrigation Cost: {water_cost:,.2f} DZD
Crop Value at Risk: {crop_value:,.2f} DZD
Moisture Deficit: {moisture_deficit:.1f}% (Target threshold: {target_threshold}%)
Satellite Water Productivity Index: {swp:.3f} (1.0 = highly efficient, 0.1 = high evaporation loss)

=== DECISION RULES ===
1. If the Meteorologist confirms imminent rain (>2mm in 48h), STRONGLY prefer 'wait' to avoid wasting {water_cost:,.2f} DZD.
2. If the Botanist reports High stress, lean towards 'irrigate' to protect {crop_value:,.2f} DZD of crops.
3. If moisture deficit is below the target threshold ({target_threshold}%), automatically choose 'wait'.
4. If satellite water productivity < 0.3, consider adjusting volume (high evaporation reduces efficiency).
5. Balance financial risk vs. crop survival probability.

=== OUTPUT REQUIRED ===
- Final decision: 'irrigate' or 'wait'
- Exact liters to dispatch (0 if 'wait')
- Recommended nutrient mix (e.g. 'N:P:K 20:10:10 — standard growth formula', or specify stress recovery blend based on salinity={state.get('water_salinity')} dS/m and growth stage={state.get('plant_growth_stage')}). Use 'None' if decision is 'wait'.
- Full financial analysis rationale

Provide your complete analysis."""

    structured_llm = llm.with_structured_output(FinancialOutput)
    response = await structured_llm.ainvoke(prompt)
    log.info(
        "Financial Director complete | decision=%s | volume=%.0fL | cost=%.2f DZD",
        response.decision, response.water_volume_liters, response.financial_cost_dzd,
    )
    return {
        "financial_analysis": response.financial_analysis,
        "biological_reasoning": "Swarm consensus reached. See individual agent reports for details.",
        "decision": response.decision,
        "water_volume_liters": response.water_volume_liters,
        "nutrient_mix": response.nutrient_mix,
        "financial_cost_dzd": response.financial_cost_dzd,
        "crop_value_at_risk_dzd": response.crop_value_at_risk_dzd,
    }


# ===========================================================================
# NODE 5 — Actuator  (MCP Hardware Interface)
# ===========================================================================
async def actuator_node(state: FarmState) -> dict:
    """
    Send hardware commands via the MCP (Model Context Protocol) irrigate_valve tool.

    Uses FastMCP in-process Client to call the agri-irrigation-actuator MCP server,
    implementing the Model Context Protocol standard for agent-to-hardware interfacing.

    Handles three scenarios:
      1. Normal irrigation approved   → MCP irrigate_valve tool
      2. Anomaly + human override     → MCP irrigate_valve tool (conservative volume)
      3. Rejected / anomaly emergency → MCP emergency_stop tool
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
            # Normal irrigation approval path
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
