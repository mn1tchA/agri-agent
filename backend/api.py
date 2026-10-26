"""
FastAPI backend for the Agri-Agent Swarm — v2.2.

Features:
  - API versioned under /api/v1/* prefix (APIRouter)
  - JWT Bearer authentication with role-based access control (admin, operator, viewer)
  - Multi-tenant Farm management with per-farm telemetry and history isolation
  - Persistent hardware valve command tracking surviving server restarts
  - APScheduler background farm health and anomaly surveillance
  - Anomaly alerting (In-App, Webhook, Email)
  - Full Observability: OpenTelemetry tracing + Prometheus /metrics + LangSmith LLM cost tracking
  - LangGraph human-in-the-loop state machine with SSE streaming
"""
import asyncio
import json
import logging
import uuid
from contextlib import asynccontextmanager
from datetime import timedelta
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from fastapi.security import OAuth2PasswordRequestForm
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from pydantic import BaseModel, Field, field_validator
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from config import settings
from database import (
    AlertLog,
    DecisionLog,
    Farm,
    ValveCommand,
    acknowledge_alert,
    create_db_and_tables,
    create_farm,
    delete_farm,
    emergency_stop_all_valves,
    get_aggregate_stats,
    get_alert_logs,
    get_all_decision_logs,
    get_farm,
    get_valve_command,
    list_farms_for_user,
    list_valve_commands,
    save_decision_log,
    update_farm,
    update_outcome_rating,
)
from graph import create_workflow
from memory import add_memory
from observability import (
    ANALYSIS_RUNS_TOTAL,
    IRRIGATION_VOLUME_LITERS,
    VALVE_COMMANDS_TOTAL,
    get_langsmith_status,
    setup_opentelemetry,
    setup_prometheus,
)
from scheduler import run_scheduled_farm_check, start_scheduler, stop_scheduler
from security import (
    Token,
    TokenData,
    authenticate_user,
    create_access_token,
    require_admin,
    require_operator,
    require_viewer,
)

log = logging.getLogger("agri_agent.api")

# ---------------------------------------------------------------------------
# Rate Limiter
# ---------------------------------------------------------------------------
limiter = Limiter(key_func=get_remote_address)


# ---------------------------------------------------------------------------
# Lifespan — startup / shutdown
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Initialize DB, start scheduler, setup observability, and compile LangGraph on startup.
    Stores the compiled agent app on app.state (process-safe; no module globals).
    """
    settings.validate_security()

    create_db_and_tables()
    start_scheduler()

    async with AsyncSqliteSaver.from_conn_string(settings.sqlite_checkpoints_db) as checkpointer:
        workflow = create_workflow()
        app.state.agent_app = workflow.compile(
            checkpointer=checkpointer,
            interrupt_before=["human_approval_gate"],
        )
        log.info("LangGraph workflow compiled and ready")
        yield

    stop_scheduler()
    log.info("LangGraph workflow and scheduler shut down")


# ---------------------------------------------------------------------------
# FastAPI App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Agri-Agent Swarm API",
    description=(
        "Autonomous multi-agent precision agriculture system with multi-tenancy, "
        "hardware actuation via MCP, background anomaly scheduling, and full observability."
    ),
    version="2.2.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register Prometheus and OpenTelemetry instrumentation
setup_opentelemetry(app)
setup_prometheus(app)


# ---------------------------------------------------------------------------
# Request / Response Models
# ---------------------------------------------------------------------------

class FarmCreatePayload(BaseModel):
    name: str = "My Farm"
    crop_type: str = "Wheat"
    farm_area_sqm: Annotated[float, Field(gt=0, le=10_000_000)] = 10_000.0
    latitude: float = settings.default_latitude
    longitude: float = settings.default_longitude
    moisture_threshold: Annotated[float, Field(ge=0, le=100)] = 10.0
    water_salinity: Annotated[float, Field(ge=0, le=20)] = 1.2
    plant_growth_stage: str = "Vegetative Stage (High Water Demand)"
    auto_irrigate_enabled: bool = False


class FarmUpdatePayload(BaseModel):
    name: Optional[str] = None
    crop_type: Optional[str] = None
    farm_area_sqm: Optional[float] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    moisture_threshold: Optional[float] = None
    water_salinity: Optional[float] = None
    plant_growth_stage: Optional[str] = None
    auto_irrigate_enabled: Optional[bool] = None


class ConfigPayload(BaseModel):
    """Input parameters for a new farm analysis run."""
    farm_id: Optional[int] = None
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
    farm_id: Optional[int] = None


class FeedbackRequest(BaseModel):
    log_id: int
    rating: Annotated[int, Field(ge=1, le=5)]


class HealthResponse(BaseModel):
    status: str
    version: str
    scheduler_running: bool


class ActuateResponse(BaseModel):
    status: str
    log_id: int
    hardware_command: str
    message: str


class FeedbackResponse(BaseModel):
    status: str
    log_id: int
    rating: int


class HistoryResponse(BaseModel):
    history: list[dict[str, Any]]


# ---------------------------------------------------------------------------
# Versioned Router (/api/v1/*)
# ---------------------------------------------------------------------------
v1 = APIRouter(prefix="/api/v1", tags=["v1"])


# ── Auth ────────────────────────────────────────────────────────────────────

@v1.post(
    "/auth/token",
    response_model=Token,
    summary="Obtain a JWT access token",
    tags=["Auth"],
)
async def login(form_data: Annotated[OAuth2PasswordRequestForm, Depends()]) -> Token:
    """OAuth2 password flow — submit username + password to get a Bearer token."""
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    expires = timedelta(minutes=settings.access_token_expire_minutes)
    token = create_access_token(
        data={"sub": user.username, "role": user.role, "user_id": user.user_id},
        expires_delta=expires,
    )
    return Token(
        access_token=token,
        token_type="bearer",
        expires_in=int(expires.total_seconds()),
        role=user.role,
        user_id=user.user_id,
    )


# ── Multi-Tenancy Farms ──────────────────────────────────────────────────────

@v1.get("/farms", response_model=list[dict], summary="List farms for user", tags=["Farms"])
async def list_farms(
    current_user: Annotated[TokenData, Depends(require_viewer)],
) -> list[dict]:
    """List farms owned by user (or all farms if admin/operator)."""
    loop = asyncio.get_running_loop()
    owner_id = None if current_user.role in ("admin", "operator") else current_user.user_id
    farms = await loop.run_in_executor(None, list_farms_for_user, owner_id)
    return [f.model_dump() for f in farms]


@v1.post("/farms", response_model=dict, summary="Create a new farm", tags=["Farms"])
async def create_new_farm(
    payload: FarmCreatePayload,
    current_user: Annotated[TokenData, Depends(require_operator)],
) -> dict:
    """Register a new farm with coordinates and sensor thresholds."""
    loop = asyncio.get_running_loop()
    farm = Farm(
        name=payload.name,
        owner_id=current_user.user_id,
        crop_type=payload.crop_type,
        farm_area_sqm=payload.farm_area_sqm,
        latitude=payload.latitude,
        longitude=payload.longitude,
        moisture_threshold=payload.moisture_threshold,
        water_salinity=payload.water_salinity,
        plant_growth_stage=payload.plant_growth_stage,
        auto_irrigate_enabled=payload.auto_irrigate_enabled,
    )
    saved = await loop.run_in_executor(None, create_farm, farm)
    return saved.model_dump()


@v1.get("/farms/{farm_id}", response_model=dict, summary="Get farm by ID", tags=["Farms"])
async def get_single_farm(
    farm_id: int,
    _current_user: Annotated[TokenData, Depends(require_viewer)],
) -> dict:
    """Get single farm configuration."""
    loop = asyncio.get_running_loop()
    farm = await loop.run_in_executor(None, get_farm, farm_id)
    if not farm:
        raise HTTPException(status_code=404, detail="Farm not found")
    return farm.model_dump()


@v1.put("/farms/{farm_id}", response_model=dict, summary="Update farm", tags=["Farms"])
async def update_existing_farm(
    farm_id: int,
    payload: FarmUpdatePayload,
    _current_user: Annotated[TokenData, Depends(require_operator)],
) -> dict:
    """Update farm configuration."""
    loop = asyncio.get_running_loop()
    updated = await loop.run_in_executor(
        None, update_farm, farm_id, payload.model_dump(exclude_unset=True)
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Farm not found")
    return updated.model_dump()


@v1.delete("/farms/{farm_id}", response_model=dict, summary="Delete farm", tags=["Farms"])
async def delete_existing_farm(
    farm_id: int,
    _current_user: Annotated[TokenData, Depends(require_admin)],
) -> dict:
    """Delete a farm (admin only)."""
    loop = asyncio.get_running_loop()
    deleted = await loop.run_in_executor(None, delete_farm, farm_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Farm not found")
    return {"status": "success", "message": f"Farm {farm_id} deleted"}


# ── Analysis ─────────────────────────────────────────────────────────────────

@v1.post(
    "/analyze",
    summary="Start a new farm analysis (SSE stream)",
    tags=["Analysis"],
)
@limiter.limit("10/minute")
async def run_analysis(
    request: Request,
    payload: ConfigPayload,
    _current_user: Annotated[TokenData, Depends(require_operator)],
) -> StreamingResponse:
    """Start a multi-agent farm analysis with Server-Sent Events."""
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    initial_state = {
        "thread_id": thread_id,
        "farm_id": payload.farm_id,
        "user_id": _current_user.user_id,
        "crop_type": payload.crop_type,
        "farm_area_sqm": payload.farm_area_sqm,
        "target_moisture_threshold": payload.target_moisture_threshold,
        "latitude": payload.latitude,
        "longitude": payload.longitude,
        "water_salinity": payload.water_salinity,
        "plant_growth_stage": payload.plant_growth_stage,
    }

    log.info(
        "Starting analysis | user=%s | thread=%s | farm_id=%s | crop=%s | area=%.0fm²",
        _current_user.username, thread_id[:8], payload.farm_id, payload.crop_type, payload.farm_area_sqm,
    )

    agent_app = request.app.state.agent_app

    async def event_generator():
        last_decision = "wait"
        try:
            async for state_snapshot in agent_app.astream(
                initial_state, config=config, stream_mode="values"
            ):
                state_snapshot["thread_id"] = thread_id
                state_snapshot["farm_id"] = payload.farm_id
                if "decision" in state_snapshot:
                    last_decision = state_snapshot["decision"]
                yield f"data: {json.dumps(state_snapshot, default=str)}\n\n"

            # Record Prometheus metric
            ANALYSIS_RUNS_TOTAL.labels(crop_type=payload.crop_type, decision=last_decision).inc()

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


# ── Actuation ─────────────────────────────────────────────────────────────────

@v1.post(
    "/actuate",
    response_model=ActuateResponse,
    summary="Approve or reject an irrigation decision",
    tags=["Actuation"],
)
async def execute_hardware(
    request: Request,
    approval: ApprovalRequest,
    _current_user: Annotated[TokenData, Depends(require_operator)],
) -> ActuateResponse:
    """Resume a paused workflow with human approval/rejection and persist audit log."""
    config = {"configurable": {"thread_id": approval.thread_id}}
    log.info(
        "Actuation | user=%s | thread=%s | approved=%s",
        _current_user.username, approval.thread_id[:8], approval.is_approved,
    )

    agent_app = request.app.state.agent_app

    # Resume graph
    await agent_app.aupdate_state(config, {"human_approved": approval.is_approved})
    final_result = await agent_app.ainvoke(None, config=config)

    loop = asyncio.get_running_loop()

    # Persist audit trail with multi-tenant farm and user IDs
    log_entry = DecisionLog(
        thread_id=approval.thread_id,
        farm_id=approval.farm_id or final_result.get("farm_id"),
        user_id=_current_user.user_id,
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
        human_approved=approval.is_approved,
    )
    saved = await loop.run_in_executor(None, save_decision_log, log_entry)

    # Record Prometheus metrics
    if approval.is_approved and log_entry.water_volume_liters > 0:
        IRRIGATION_VOLUME_LITERS.labels(crop_type=log_entry.crop_type).inc(log_entry.water_volume_liters)
        VALVE_COMMANDS_TOTAL.labels(command="OPEN_VALVE", status="EXECUTED").inc()

    # Save to RAG vector memory
    decision = final_result.get("decision")
    crop = final_result.get("crop_type", "Unknown")
    moisture = final_result.get("soil_moisture", 0)
    temp = final_result.get("temperature", 0)
    salinity = final_result.get("water_salinity", 0)

    try:
        if decision == "irrigate" and approval.is_approved:
            mem_text = (
                f"IRRIGATED {final_result.get('water_volume_liters', 0):,.0f}L for {crop}. "
                f"Conditions: moisture={moisture:.1f}%, temp={temp}°C, salinity={salinity} dS/m. "
                f"Botanist: {final_result.get('botanist_analysis', '')[:200]}"
            )
            add_memory(mem_text, {"thread_id": approval.thread_id, "action": "irrigate", "crop_type": crop})
        elif decision == "irrigate" and not approval.is_approved:
            mem_text = (
                f"IRRIGATION REJECTED by operator for {crop}. "
                f"Conditions: moisture={moisture:.1f}%, temp={temp}°C, salinity={salinity} dS/m."
            )
            add_memory(mem_text, {"thread_id": approval.thread_id, "action": "rejected", "crop_type": crop})
    except Exception as e:
        log.warning("Memory persistence failed: %s", e)

    return ActuateResponse(
        status="success",
        log_id=saved.id,
        hardware_command="EXECUTED" if approval.is_approved else "REJECTED",
        message=final_result.get("actuator_message", "No message."),
    )


# ── Hardware Actuator Valves ──────────────────────────────────────────────────

@v1.get("/valves", response_model=list[dict], summary="List valve commands", tags=["Valves"])
async def list_valves(
    farm_id: Optional[int] = None,
    limit: int = 50,
    _current_user: Annotated[TokenData, Depends(require_viewer)] = None,
) -> list[dict]:
    """List persistent valve actuation commands from SQLite."""
    loop = asyncio.get_running_loop()
    commands = await loop.run_in_executor(None, list_valve_commands, farm_id, limit)
    return [c.model_dump() for c in commands]


@v1.get("/valves/{command_id}", response_model=dict, summary="Get valve status", tags=["Valves"])
async def get_single_valve(
    command_id: str,
    _current_user: Annotated[TokenData, Depends(require_viewer)],
) -> dict:
    """Query valve hardware state by unique command ID."""
    loop = asyncio.get_running_loop()
    cmd = await loop.run_in_executor(None, get_valve_command, command_id)
    if not cmd:
        raise HTTPException(status_code=404, detail="Valve command not found")
    return cmd.model_dump()


@v1.post("/valves/emergency-stop", response_model=dict, summary="Emergency stop all valves", tags=["Valves"])
async def trigger_emergency_stop(
    _current_user: Annotated[TokenData, Depends(require_operator)],
) -> dict:
    """Emergency halt all active field valves."""
    loop = asyncio.get_running_loop()
    count = await loop.run_in_executor(None, emergency_stop_all_valves)
    VALVE_COMMANDS_TOTAL.labels(command="EMERGENCY_STOP", status="STOPPED").inc()
    return {"status": "success", "valves_halted": count}


# ── Alerts & Scheduled Analysis ───────────────────────────────────────────────

@v1.get("/alerts", response_model=list[dict], summary="List anomaly alerts", tags=["Alerts"])
async def list_alerts(
    farm_id: Optional[int] = None,
    limit: int = 50,
    _current_user: Annotated[TokenData, Depends(require_viewer)] = None,
) -> list[dict]:
    """List recent anomaly alerts."""
    loop = asyncio.get_running_loop()
    alerts = await loop.run_in_executor(None, get_alert_logs, farm_id, limit)
    return [a.model_dump() for a in alerts]


@v1.post("/alerts/{alert_id}/ack", response_model=dict, summary="Acknowledge alert", tags=["Alerts"])
async def ack_alert(
    alert_id: int,
    _current_user: Annotated[TokenData, Depends(require_viewer)],
) -> dict:
    """Mark an anomaly alert as acknowledged."""
    loop = asyncio.get_running_loop()
    success = await loop.run_in_executor(None, acknowledge_alert, alert_id)
    if not success:
        raise HTTPException(status_code=404, detail="Alert not found")
    return {"status": "success", "alert_id": alert_id}


@v1.post("/scheduler/run-now", response_model=dict, summary="Trigger instant farm check", tags=["Scheduler"])
async def run_scheduler_now(
    _current_user: Annotated[TokenData, Depends(require_operator)],
) -> dict:
    """Trigger an immediate automated farm health and anomaly check."""
    results = await run_scheduled_farm_check()
    return {"status": "success", "farms_inspected": len(results), "details": results}


# ── Observability & LangSmith ────────────────────────────────────────────────

@v1.get("/observability/langsmith", response_model=dict, summary="LangSmith tracing status", tags=["Observability"])
async def langsmith_status(
    _current_user: Annotated[TokenData, Depends(require_viewer)],
) -> dict:
    """Diagnostic info on LangSmith LLM tracing and cost tracking."""
    return get_langsmith_status()


# ── Analytics ─────────────────────────────────────────────────────────────────

@v1.get(
    "/history",
    response_model=HistoryResponse,
    summary="Decision audit log",
    tags=["Analytics"],
)
async def get_history(
    farm_id: Optional[int] = None,
    _current_user: Annotated[TokenData, Depends(require_viewer)] = None,
) -> HistoryResponse:
    """Return decision logs, optionally filtered by farm_id."""
    loop = asyncio.get_running_loop()
    logs = await loop.run_in_executor(None, get_all_decision_logs, farm_id)
    return HistoryResponse(history=[l.model_dump() for l in logs])


@v1.get(
    "/stats",
    response_model=dict,
    summary="Aggregate statistics",
    tags=["Analytics"],
)
async def get_stats(
    farm_id: Optional[int] = None,
    _current_user: Annotated[TokenData, Depends(require_viewer)] = None,
) -> dict:
    """Return aggregate statistics for the analytics dashboard, optionally per farm."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, get_aggregate_stats, farm_id)


@v1.post(
    "/feedback",
    response_model=FeedbackResponse,
    summary="Submit outcome rating",
    tags=["Analytics"],
)
async def submit_feedback(
    feedback: FeedbackRequest,
    _current_user: Annotated[TokenData, Depends(require_viewer)],
) -> FeedbackResponse:
    """Submit an outcome rating (1–5 stars) for a completed decision."""
    loop = asyncio.get_running_loop()
    success = await loop.run_in_executor(
        None, update_outcome_rating, feedback.log_id, feedback.rating
    )
    if not success:
        raise HTTPException(status_code=404, detail=f"Log entry {feedback.log_id} not found")
    return FeedbackResponse(status="success", log_id=feedback.log_id, rating=feedback.rating)


# Mount router
app.include_router(v1)


# ---------------------------------------------------------------------------
# Unauthenticated health check
# ---------------------------------------------------------------------------
@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["System"],
    summary="Health check",
)
async def health_check() -> HealthResponse:
    """Unauthenticated endpoint for Docker health checks."""
    from scheduler import scheduler
    return HealthResponse(
        status="healthy",
        version=app.version,
        scheduler_running=scheduler.running,
    )


@app.get("/metrics", tags=["Observability"], summary="Prometheus metrics")
async def metrics_endpoint() -> Response:
    """Expose Prometheus metrics for scraping."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


# ---------------------------------------------------------------------------
# Backward-compat aliases (/api/*)
# ---------------------------------------------------------------------------
@app.post("/api/analyze", include_in_schema=False)
@limiter.limit("10/minute")
async def _compat_analyze(request: Request, payload: ConfigPayload) -> StreamingResponse:
    return await run_analysis(request, payload, TokenData(username="compat", role="operator", user_id=1))


@app.post("/api/actuate", include_in_schema=False)
async def _compat_actuate(request: Request, approval: ApprovalRequest):
    return await execute_hardware(request, approval, TokenData(username="compat", role="operator", user_id=1))


@app.get("/api/history", include_in_schema=False)
async def _compat_history(farm_id: Optional[int] = None):
    res = await get_history(farm_id)
    return res.model_dump()


@app.get("/api/stats", include_in_schema=False)
async def _compat_stats(farm_id: Optional[int] = None):
    return await get_stats(farm_id)


@app.post("/api/feedback", include_in_schema=False)
async def _compat_feedback(feedback: FeedbackRequest):
    return await submit_feedback(feedback, TokenData(username="compat", role="viewer", user_id=2))
