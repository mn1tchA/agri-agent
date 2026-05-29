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
from typing import Annotated

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

    @field_validator("crop_type", "plant_growth_stage")
    @classmethod
    def strip_and_validate(cls, v: str) -> str:
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
            fallback["financial_analysis"] = f"Error: {str(e)}"
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
        meteorologist_analysis=final_result.get("meteorologist_analysis", ""),
        botanist_analysis=final_result.get("botanist_analysis", ""),
        financial_analysis=final_result.get("financial_analysis", ""),
        reasoning_confidence=final_result.get("reasoning_confidence", 0.0),
        decision=final_result.get("decision", ""),
        water_volume_liters=final_result.get("water_volume_liters", 0.0),
        financial_cost_dzd=final_result.get("financial_cost_dzd", 0.0),
        crop_value_at_risk_dzd=final_result.get("crop_value_at_risk_dzd", 0.0),
        human_approved=request.is_approved,
    )
    saved = await loop.run_in_executor(None, save_decision_log, log_entry)

    # Save to RAG vector memory for future Botanist queries
    decision = final_result.get("decision")
    crop = final_result.get("crop_type", "Unknown")
    moisture = final_result.get("soil_moisture", 0)
    temp = final_result.get("temperature", 0)
    salinity = final_result.get("water_salinity", 0)

    if decision == "irrigate" and request.is_approved:
        mem_text = (
            f"IRRIGATED {final_result.get('water_volume_liters', 0):,.0f}L for {crop}. "
            f"Conditions: moisture={moisture:.1f}%, temp={temp}°C, salinity={salinity} dS/m. "
            f"Botanist analysis: {final_result.get('botanist_analysis', '')[:200]}"
        )
        add_memory(mem_text, {"thread_id": request.thread_id, "action": "irrigate", "crop_type": crop})
    elif decision == "irrigate" and not request.is_approved:
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