"""
FastAPI backend for the Agri-Agent Swarm.

Endpoints:
    POST /api/analyze       — Start a new analysis run (SSE streaming)
    POST /api/actuate       — Approve/reject irrigation and resume graph
    GET  /api/history       — Full decision audit log
    GET  /api/stats         — Aggregate statistics
    POST /api/feedback      — Submit outcome rating for a decision
    GET  /health            — Health check for Docker/load balancer
"""
import uuid
import json
import logging
import asyncio
from contextlib import asynccontextmanager
from typing import Annotated, Optional

from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from config import settings
from graph import create_workflow
from database import (
    create_db_and_tables,
    save_decision_log,
    get_all_decision_logs,
    update_outcome_rating,
    get_aggregate_stats,
    DecisionLog,
)
from memory import add_memory

log = logging.getLogger("agri_agent.api")

# ---------------------------------------------------------------------------
# Rate Limiter — protects Gemini API quota from request flooding
# Limit: 10 analysis runs per minute per IP (Gemini free tier: 15 req/min)
# ---------------------------------------------------------------------------
limiter = Limiter(key_func=get_remote_address)

# ---------------------------------------------------------------------------
# Global app reference
# ---------------------------------------------------------------------------
agent_app = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize DB + LangGraph on startup."""
    global agent_app
    create_db_and_tables()

    async with AsyncSqliteSaver.from_conn_string(settings.sqlite_checkpoints_db) as checkpointer:
        workflow = create_workflow()
        agent_app = workflow.compile(
            checkpointer=checkpointer,
            interrupt_before=["human_approval_gate"],
        )
        log.info("LangGraph workflow compiled and ready")
        yield


# ---------------------------------------------------------------------------
# FastAPI App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Agri-Agent Swarm API",
    description="Multi-agent autonomous agricultural decision system.",
    version="2.0.0",
    lifespan=lifespan,
)

# Attach rate limiter state and error handler
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request / Response Models
# ---------------------------------------------------------------------------

class ConfigPayload(BaseModel):
    """Input parameters for a new farm analysis run."""
    crop_type: str = "Wheat"
    farm_area_sqm: Annotated[float, Field(gt=0, le=10_000_000)] = 10_000.0
    target_moisture_threshold: Annotated[float, Field(ge=0, le=100)] = 10.0
    latitude: float = settings.default_latitude
    longitude: float = settings.default_longitude
    water_salinity: Annotated[float, Field(ge=0, le=20)] = 1.2
    plant_growth_stage: str = "Vegetative Stage (High Water Demand)"
    
    # New Config Fields
    seed_profile: str = "Standard"
    upov_id: Optional[str] = None
    germination_rate_pct: Annotated[float, Field(ge=0, le=100)] = 85.0
    planting_date: str = "2026-04-01"
    soil_texture: str = "Loamy"
    pump_type: str = "Electric"
    pump_kw: Annotated[float, Field(ge=0, le=1000)] = 5.5
    fuel_use_lph: Annotated[float, Field(ge=0, le=1000)] = 0.0
    labor_workers: Annotated[int, Field(ge=0, le=100)] = 1
    labor_hours: Annotated[float, Field(ge=0, le=1000)] = 2.0
    labor_wage_usd: Annotated[float, Field(ge=0, le=1000)] = 15.0
    market_price_usd_per_kg: Annotated[float, Field(ge=0, le=1000)] = 0.0

    @field_validator("crop_type", "plant_growth_stage", "seed_profile", "soil_texture", "pump_type", "planting_date")
    @classmethod
    def strip_and_validate(cls, v: str) -> str:
        if v is None:
            return ""
        v = v.strip()
        if not v:
            raise ValueError("Field cannot be empty")
        if len(v) > 100:
            raise ValueError("Field too long (max 100 chars)")
        return v

    @field_validator("latitude")
    @classmethod
    def validate_latitude(cls, v: float) -> float:
        if not -90 <= v <= 90:
            raise ValueError("Latitude must be between -90 and 90")
        return v

    @field_validator("longitude")
    @classmethod
    def validate_longitude(cls, v: float) -> float:
        if not -180 <= v <= 180:
            raise ValueError("Longitude must be between -180 and 180")
        return v


class ApprovalRequest(BaseModel):
    thread_id: str
    is_approved: bool


class FeedbackRequest(BaseModel):
    log_id: int
    rating: Annotated[int, Field(ge=1, le=5)]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health", tags=["System"])
async def health_check():
    """Health check endpoint for Docker and load balancers."""
    return {"status": "healthy", "version": app.version}


@app.post("/api/analyze", tags=["Analysis"])
@limiter.limit("10/minute")
async def run_analysis(request: Request, payload: ConfigPayload):
    """
    Start a new multi-agent farm analysis.
    Returns a Server-Sent Events stream with incremental state updates.
    Rate limited to 10 requests/minute per IP to protect Gemini API quota.
    """
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    initial_state = {
        "thread_id": thread_id,
        "crop_type": payload.crop_type,
        "farm_area_sqm": payload.farm_area_sqm,
        "target_moisture_threshold": payload.target_moisture_threshold,
        "latitude": payload.latitude,
        "longitude": payload.longitude,
        "water_salinity": payload.water_salinity,
        "plant_growth_stage": payload.plant_growth_stage,
        "seed_profile": payload.seed_profile,
        "upov_id": payload.upov_id,
        "germination_rate_pct": payload.germination_rate_pct,
        "planting_date": payload.planting_date,
        "soil_texture": payload.soil_texture,
        "pump_type": payload.pump_type,
        "pump_kw": payload.pump_kw,
        "fuel_use_lph": payload.fuel_use_lph,
        "labor_workers": payload.labor_workers,
        "labor_hours": payload.labor_hours,
        "labor_wage_usd": payload.labor_wage_usd,
        "market_price_usd_per_kg": payload.market_price_usd_per_kg,
    }

    log.info(
        "Starting analysis | thread=%s | crop=%s | area=%.0fm² | lat=%.4f | lon=%.4f",
        thread_id[:8], payload.crop_type, payload.farm_area_sqm,
        payload.latitude, payload.longitude,
    )

    async def event_generator():
        try:
            async for state_snapshot in agent_app.astream(
                initial_state, config=config, stream_mode="values"
            ):
                state_snapshot["thread_id"] = thread_id
                yield f"data: {json.dumps(state_snapshot, default=str)}\n\n"
        except Exception as e:
            log.error("SSE stream error for thread %s: %s", thread_id[:8], e)
            fallback = {**initial_state, "thread_id": thread_id}
            fallback["meteorologist_analysis"] = "⚠️ API error — please wait 60 seconds and retry."
            fallback["botanist_analysis"] = "⚠️ API error — please wait 60 seconds and retry."
            fallback["agronomist_analysis"] = "⚠️ API error — please wait 60 seconds and retry."
            fallback["pedologist_analysis"] = "⚠️ API error — please wait 60 seconds and retry."
            fallback["economist_analysis"] = "⚠️ API error — please wait 60 seconds and retry."
            fallback["harvest_analysis"] = "⚠️ API error — please wait 60 seconds and retry."
            fallback["orchestrator_analysis"] = f"Error: {str(e)}"
            fallback["decision"] = "error"
            yield f"data: {json.dumps(fallback)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/actuate", tags=["Actuation"])
async def execute_hardware(request: ApprovalRequest):
    """
    Approve or reject irrigation for a paused workflow.
    Resumes the graph, persists the full audit log, and saves to RAG memory.
    """
    config = {"configurable": {"thread_id": request.thread_id}}
    log.info(
        "Actuation request | thread=%s | approved=%s",
        request.thread_id[:8], request.is_approved,
    )

    # Resume graph
    await agent_app.aupdate_state(config, {"human_approved": request.is_approved})
    final_result = await agent_app.ainvoke(None, config=config)

    loop = asyncio.get_event_loop()

    # Save full audit trail to DB (sync SQLModel — run in threadpool to avoid blocking event loop)
    log_entry = DecisionLog(
        thread_id=request.thread_id,
        crop_type=final_result.get("crop_type", ""),
        farm_area_sqm=final_result.get("farm_area_sqm", 0.0),
        latitude=final_result.get("latitude", settings.default_latitude),
        longitude=final_result.get("longitude", settings.default_longitude),
        temperature=final_result.get("temperature", 0.0),
        soil_moisture=final_result.get("soil_moisture", 0.0),
        water_salinity=final_result.get("water_salinity", 0.0),
        plant_growth_stage=final_result.get("plant_growth_stage", ""),
        weather_forecast=final_result.get("weather_forecast", ""),
        
        # New Agent Analyses
        meteorologist_analysis=final_result.get("meteorologist_analysis", ""),
        botanist_analysis=final_result.get("botanist_analysis", ""),
        agronomist_analysis=final_result.get("agronomist_analysis", ""),
        pedologist_analysis=final_result.get("pedologist_analysis", ""),
        economist_analysis=final_result.get("economist_analysis", ""),
        harvest_analysis=final_result.get("harvest_analysis", ""),
        orchestrator_analysis=final_result.get("orchestrator_analysis", ""),
        
        reasoning_confidence=final_result.get("reasoning_confidence", 0.0),
        decision=final_result.get("decision", ""),
        water_volume_liters=final_result.get("water_volume_liters", 0.0),
        
        # USD Cost Fields
        water_cost_usd=final_result.get("water_cost_usd", 0.0),
        electricity_cost_usd=final_result.get("electricity_cost_usd", 0.0),
        fuel_cost_usd=final_result.get("fuel_cost_usd", 0.0),
        labor_cost_usd=final_result.get("labor_cost_usd", 0.0),
        total_operational_cost_usd=final_result.get("total_operational_cost_usd", 0.0),
        roi_score=final_result.get("roi_score", 0.0),
        crop_value_at_risk_usd=final_result.get("crop_value_at_risk_usd", 0.0),
        
        fertilizer_recommendation=final_result.get("fertilizer_recommendation", ""),
        agent_votes=json.dumps(final_result.get("agent_votes", {})),
        last_irrigation_date=datetime.now(timezone.utc).isoformat() if request.is_approved and final_result.get("decision") in ("irrigate", "micro_irrigate") else None,
        
        human_approved=request.is_approved,
    )
    saved = await loop.run_in_executor(None, save_decision_log, log_entry)

    # Save to RAG vector memory for future Botanist queries
    decision = final_result.get("decision")
    crop = final_result.get("crop_type", "Unknown")
    moisture = final_result.get("soil_moisture", 0)
    temp = final_result.get("temperature", 0)
    salinity = final_result.get("water_salinity", 0)

    if decision in ("irrigate", "micro_irrigate") and request.is_approved:
        mem_text = (
            f"IRRIGATED {final_result.get('water_volume_liters', 0):,.0f}L for {crop}. "
            f"Conditions: moisture={moisture:.1f}%, temp={temp}°C, salinity={salinity} dS/m. "
            f"Botanist analysis: {final_result.get('botanist_analysis', '')[:200]}"
        )
        add_memory(mem_text, {"thread_id": request.thread_id, "action": "irrigate", "crop_type": crop})
    elif decision in ("irrigate", "micro_irrigate") and not request.is_approved:
        mem_text = (
            f"IRRIGATION REJECTED by operator for {crop}. "
            f"Conditions: moisture={moisture:.1f}%, temp={temp}°C, salinity={salinity} dS/m."
        )
        add_memory(mem_text, {"thread_id": request.thread_id, "action": "rejected", "crop_type": crop})
    elif decision == "wait":
        mem_text = (
            f"WAITED (no irrigation) for {crop}. "
            f"Conditions: moisture={moisture:.1f}%, temp={temp}°C, salinity={salinity} dS/m. "
            f"Meteorologist: {final_result.get('meteorologist_analysis', '')[:200]}"
        )
        add_memory(mem_text, {"thread_id": request.thread_id, "action": "wait", "crop_type": crop})
    elif decision == "anomaly":
        action_taken = "OVERRIDDEN (irrigated)" if request.is_approved else "EMERGENCY STOPPED"
        mem_text = (
            f"CRITICAL ANOMALY for {crop} — human operator {action_taken}. "
            f"Anomaly: {final_result.get('anomaly_reason', 'Unknown')}. "
            f"Conditions: moisture={moisture:.1f}%, temp={temp}°C, salinity={salinity} dS/m."
        )
        add_memory(mem_text, {"thread_id": request.thread_id, "action": "anomaly", "crop_type": crop})

    return {
        "status": "success",
        "log_id": saved.id,
        "hardware_command": "EXECUTED" if request.is_approved else "REJECTED",
        "message": final_result.get("actuator_message", "No message."),
    }


@app.get("/api/crop-planner", tags=["Analysis"])
async def get_crop_planner(lat: float, lon: float, soil: str, month: int):
    """
    Rank and return crop recommendations based on location, soil, and month.
    """
    # 1. Koppen Zone calculation
    if lat > 35.0:
        koppen = "Csa"
    elif 32.0 <= lat <= 35.0:
        koppen = "BSk"
    elif 28.0 <= lat < 32.0:
        koppen = "BSh"
    else:
        koppen = "BWh"

    # 2. Load crop database
    import os
    db_path = os.path.join(os.path.dirname(__file__), "crop_db.json")
    try:
        with open(db_path, "r", encoding="utf-8") as f:
            crop_db = json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load crop database: {e}")

    # 3. Planting windows
    planting_windows = {
        "TRZAW": [10, 11, 12, 1], # Winter Wheat: Oct - Jan
        "HORVV": [10, 11, 12, 1], # Barley: Oct - Jan
        "ZEAMX": [3, 4, 5, 6],    # Maize/Corn: Mar - Jun
        "LYPES": [2, 3, 4, 5],    # Tomato: Feb - May
        "SOLTU": [1, 2, 3, 9, 10],# Potato: Jan-Mar, Sept-Oct
        "HEFAN": [3, 4, 5, 6],    # Sunflower: Mar - Jun
        "ALLCE": [10, 11, 12, 1, 2],# Onion: Oct - Feb
        "CITLA": [3, 4, 5],       # Watermelon: Mar - May
        "CPSAN": [2, 3, 4, 5],    # Bell Pepper: Feb - May
        "GOSHI": [3, 4, 5],       # Cotton: Mar - May
        "CICAR": [2, 3, 4],       # Chickpea: Feb - Apr
        "MEDSA": [3, 4, 5, 9, 10] # Alfalfa: Mar-May, Sept-Oct
    }

    # 4. Water needs
    water_needs = {
        "TRZAW": "Medium", "HORVV": "Medium", "ZEAMX": "High", "LYPES": "High",
        "SOLTU": "Medium", "HEFAN": "Medium", "ALLCE": "Low", "CITLA": "Low",
        "CPSAN": "Medium", "GOSHI": "High", "CICAR": "Low", "MEDSA": "High"
    }

    recommendations = []
    for eppo, crop_data in crop_db.items():
        # Climate suitability check
        botanical = crop_data.get("botanical", {})
        koppen_zones = botanical.get("koppen_zones", [])
        climate_match = koppen in koppen_zones

        # Soil suitability check
        hydrology = crop_data.get("hydrology", {})
        texture_range = hydrology.get("soil_texture_range", [])
        
        soil_match = False
        selected_soil_lower = soil.lower()
        for tr in texture_range:
            tr_lower = tr.lower()
            if selected_soil_lower in tr_lower or ("loam" in selected_soil_lower and "loam" in tr_lower):
                soil_match = True
                break

        # Month match check
        window = planting_windows.get(eppo, [])
        month_match = month in window

        # Calculate suitability score
        score = 100.0
        if not climate_match:
            score -= 30.0
        if not soil_match:
            score -= 30.0
        if not month_match:
            score -= 20.0
        score = max(10.0, score)

        # Select best cultivar profile
        if soil in ("Sandy", "Clay") or koppen in ("BSk", "BSh", "BWh"):
            best_cultivar = "Drought-Resistant"
        elif soil == "Loamy" and koppen in ("Csa", "Csb"):
            best_cultivar = "High-Yield"
        else:
            best_cultivar = "Standard"

        profiles = crop_data.get("cultivar_profiles", {})
        cultivar_profiles_data = profiles.get(best_cultivar, profiles.get("Standard", {}))
        
        # Financial projection
        yield_kg_ha = cultivar_profiles_data.get("yield_kg_ha", 3000.0)
        dtm = cultivar_profiles_data.get("dtm", 100)
        
        economics = crop_data.get("economics", {})
        price = economics.get("market_price_usd_per_kg", 0.20)
        initial_invest = economics.get("initial_investment_usd_per_ha", 500.0)
        
        expected_revenue = yield_kg_ha * price
        
        water_need = water_needs.get(eppo, "Medium")
        # Estimate water + pumping costs per ha
        est_water_cost = {"Low": 150.0, "Medium": 300.0, "High": 500.0}[water_need]
        total_costs = initial_invest + est_water_cost
        net_profit = expected_revenue - total_costs

        bbch_matrix = crop_data.get("bbch_matrix", {})
        # Find highest sensitivity BBCH stage
        critical_stage = "None"
        for code, info in bbch_matrix.items():
            if info.get("sensitivity") == "Critical":
                critical_stage = f"BBCH {code} ({info.get('stage')})"
                break
        if critical_stage == "None" and bbch_matrix:
            critical_stage = f"BBCH {list(bbch_matrix.keys())[0]}"

        recommendations.append({
            "eppo": eppo,
            "crop": crop_data.get("common_name", eppo),
            "best_cultivar": best_cultivar,
            "time_to_harvest": dtm,
            "initial_investment": initial_invest,
            "expected_revenue": expected_revenue,
            "net_profit": net_profit,
            "water_need": water_need,
            "suitability_score": score,
            "bbch_sensitivity": critical_stage
        })

    # Sort recommendations by net_profit descending
    recommendations.sort(key=lambda x: x["net_profit"], reverse=True)
    return recommendations


@app.get("/api/history", tags=["Analytics"])
async def get_history():
    """Return full decision audit log, newest first."""
    loop = asyncio.get_event_loop()
    logs = await loop.run_in_executor(None, get_all_decision_logs)
    return {"history": [l.model_dump() for l in logs]}


@app.get("/api/stats", tags=["Analytics"])
async def get_stats():
    """Return aggregate statistics for the analytics dashboard."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, get_aggregate_stats)


@app.post("/api/feedback", tags=["Analytics"])
async def submit_feedback(request: FeedbackRequest):
    """Submit an outcome rating (1–5) for a completed decision."""
    loop = asyncio.get_event_loop()
    success = await loop.run_in_executor(None, update_outcome_rating, request.log_id, request.rating)
    if not success:
        raise HTTPException(status_code=404, detail=f"Log entry {request.log_id} not found")
    return {"status": "success", "log_id": request.log_id, "rating": request.rating}