"""
SQLite database layer using SQLModel.

DecisionLog stores a complete audit trail of every irrigation decision,
including the full text of each agent's analysis for compliance and review.
"""
import logging
from typing import Optional
from datetime import datetime, timezone

from sqlmodel import Field, Session, SQLModel, create_engine, select

from config import settings

log = logging.getLogger("agri_agent.database")

# ---------------------------------------------------------------------------
# SQLModel Table Definition
# ---------------------------------------------------------------------------

class DecisionLog(SQLModel, table=True):
    """Full audit record for a single farm analysis + actuation decision."""

    id: Optional[int] = Field(default=None, primary_key=True)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    thread_id: str

    # Farm identity
    crop_type: str
    farm_area_sqm: float = Field(default=0.0)
    latitude: float = Field(default=0.0)
    longitude: float = Field(default=0.0)

    # Sensor telemetry
    temperature: float
    soil_moisture: float
    water_salinity: float
    plant_growth_stage: str = Field(default="")
    weather_forecast: str = Field(default="")

    # Full agent analyses (decision audit trail)
    meteorologist_analysis: str = Field(default="")
    botanist_analysis: str = Field(default="")
    agronomist_analysis: str = Field(default="")
    pedologist_analysis: str = Field(default="")
    economist_analysis: str = Field(default="")
    harvest_analysis: str = Field(default="")
    orchestrator_analysis: str = Field(default="")
    
    # Legacy fields
    financial_analysis: str = Field(default="")
    reasoning_confidence: float = Field(default=0.0)

    # Decision outputs
    decision: str
    water_volume_liters: float
    financial_cost_dzd: float = Field(default=0.0)  # Legacy
    crop_value_at_risk_dzd: float = Field(default=0.0)  # Legacy

    # Cost model outputs (USD)
    water_cost_usd: float = Field(default=0.0)
    electricity_cost_usd: float = Field(default=0.0)
    fuel_cost_usd: float = Field(default=0.0)
    labor_cost_usd: float = Field(default=0.0)
    total_operational_cost_usd: float = Field(default=0.0)
    roi_score: float = Field(default=0.0)
    crop_value_at_risk_usd: float = Field(default=0.0)

    # Harvest and operational tracking
    fertilizer_recommendation: str = Field(default="")
    last_irrigation_date: Optional[str] = Field(default=None)
    agent_votes: str = Field(default="{}")

    # Human approval
    human_approved: bool

    # Outcome feedback (user rates the decision quality after the fact)
    outcome_rating: Optional[int] = Field(default=None)  # 1–5, None if not rated


# ---------------------------------------------------------------------------
# Engine & Lifecycle
# ---------------------------------------------------------------------------

sqlite_url = f"sqlite:///{settings.sqlite_history_db}"
connect_args = {"check_same_thread": False}
engine = create_engine(sqlite_url, echo=False, connect_args=connect_args)


def create_db_and_tables() -> None:
    """Create all tables if they don't exist, then run column migrations."""
    SQLModel.metadata.create_all(engine)
    log.info("Database tables created/verified at %s", settings.sqlite_history_db)
    # Run additive column migrations for existing databases
    try:
        from migrate_db import migrate
        migrate(settings.sqlite_history_db)
    except Exception as e:
        log.warning("Migration check failed (non-critical): %s", e)


# ---------------------------------------------------------------------------
# CRUD Operations
# ---------------------------------------------------------------------------

def save_decision_log(log_entry: DecisionLog) -> DecisionLog:
    """Persist a new decision log entry and return it with its generated ID."""
    with Session(engine) as session:
        session.add(log_entry)
        session.commit()
        session.refresh(log_entry)
        log.info("Saved decision log #%d | decision=%s | thread=%s", log_entry.id, log_entry.decision, log_entry.thread_id[:8])
        return log_entry


def get_all_decision_logs() -> list[DecisionLog]:
    """Return all decision logs, newest first."""
    with Session(engine) as session:
        logs = session.exec(
            select(DecisionLog).order_by(DecisionLog.timestamp.desc())
        ).all()
        return list(logs)


def get_days_since_last_irrigation() -> float:
    """Query DB for latest approved irrigation and calculate days elapsed."""
    latest_date = None
    with Session(engine) as session:
        result = session.exec(
            select(DecisionLog)
            .where(DecisionLog.decision.in_(["irrigate", "micro_irrigate"]))
            .where(DecisionLog.human_approved == True)
            .order_by(DecisionLog.timestamp.desc())
            .limit(1)
        ).first()
        if result and result.last_irrigation_date:
            try:
                latest_date = datetime.fromisoformat(result.last_irrigation_date)
            except Exception:
                latest_date = result.timestamp
        elif result:
            latest_date = result.timestamp
            
    if latest_date:
        # Normalize to UTC
        if latest_date.tzinfo is None:
            latest_date = latest_date.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - latest_date
        return round(delta.total_seconds() / 86400.0, 1)
    return 14.0  # Default to 14 days if never irrigated


def update_outcome_rating(log_id: int, rating: int) -> bool:
    """
    Update the outcome rating for a decision log entry.

    Args:
        log_id: The ID of the DecisionLog entry.
        rating: Integer rating 1–5.

    Returns:
        True if updated successfully, False if not found.
    """
    with Session(engine) as session:
        entry = session.get(DecisionLog, log_id)
        if not entry:
            log.warning("Outcome rating update failed — log ID %d not found", log_id)
            return False
        entry.outcome_rating = rating
        session.add(entry)
        session.commit()
        log.info("Updated outcome rating for log #%d → %d/5", log_id, rating)
        return True


def get_aggregate_stats() -> dict:
    """Return aggregate statistics for the analytics dashboard."""
    with Session(engine) as session:
        logs = session.exec(select(DecisionLog)).all()
        if not logs:
            return {
                "total_decisions": 0,
                "irrigate_count": 0,
                "wait_count": 0,
                "total_water_liters": 0.0,
                "total_cost_usd": 0.0,
                "total_electricity_cost_usd": 0.0,
                "total_labor_cost_usd": 0.0,
                "total_fuel_cost_usd": 0.0,
                "total_water_cost_usd": 0.0,
                "avg_roi": 0.0,
                "approval_rate": 0.0,
                "avg_soil_moisture": 0.0,
            }

        irrigate = [l for l in logs if l.decision in ("irrigate", "micro_irrigate")]
        total_costs_usd = sum(l.total_operational_cost_usd for l in logs)
        total_elec_usd = sum(l.electricity_cost_usd for l in logs)
        total_labor_usd = sum(l.labor_cost_usd for l in logs)
        total_fuel_usd = sum(l.fuel_cost_usd for l in logs)
        total_water_usd = sum(l.water_cost_usd for l in logs)
        
        roi_entries = [l.roi_score for l in logs if l.roi_score > 0]
        avg_roi = sum(roi_entries) / len(roi_entries) if roi_entries else 0.0

        return {
            "total_decisions": len(logs),
            "irrigate_count": len(irrigate),
            "wait_count": len(logs) - len(irrigate),
            "total_water_liters": sum(l.water_volume_liters for l in logs),
            "total_cost_usd": total_costs_usd,
            "total_electricity_cost_usd": total_elec_usd,
            "total_labor_cost_usd": total_labor_usd,
            "total_fuel_cost_usd": total_fuel_usd,
            "total_water_cost_usd": total_water_usd,
            "avg_roi": avg_roi,
            "approval_rate": (
                sum(1 for l in irrigate if l.human_approved) / len(irrigate)
                if irrigate else 0.0
            ),
            "avg_soil_moisture": sum(l.soil_moisture for l in logs) / len(logs),
        }
