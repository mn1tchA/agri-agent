"""
SQLite database layer using SQLModel.

Stores:
- User: Multi-tenant user accounts and roles.
- Farm: Farm profiles, geospatial data, and sensor baseline configs.
- DecisionLog: Complete audit trail of irrigation decisions per farm.
- ValveCommand: Hardware actuator state and command history surviving restarts.
- AlertLog: Dispatched alerts and anomalies.
"""

import logging
from datetime import UTC, datetime

from sqlmodel import Field, Session, SQLModel, col, create_engine, select

from config import settings

log = logging.getLogger("agri_agent.database")

# ---------------------------------------------------------------------------
# SQLModel Table Definitions
# ---------------------------------------------------------------------------


class User(SQLModel, table=True):
    """User account with role-based access control."""

    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True)
    hashed_password: str
    role: str = Field(default="viewer")  # "viewer", "operator", "admin"
    full_name: str = Field(default="")
    email: str | None = Field(default=None)
    phone_number: str | None = Field(default=None)
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Farm(SQLModel, table=True):
    """Farm profile with geo-coordinates, crop configuration, and thresholds."""

    id: int | None = Field(default=None, primary_key=True)
    name: str
    owner_id: int | None = Field(default=None, foreign_key="user.id", index=True)
    crop_type: str = Field(default="Wheat")
    farm_area_sqm: float = Field(default=10000.0)
    latitude: float = Field(default=35.6911)
    longitude: float = Field(default=-0.6328)
    moisture_threshold: float = Field(default=10.0)
    water_salinity: float = Field(default=1.2)
    plant_growth_stage: str = Field(default="Vegetative Stage (High Water Demand)")
    auto_irrigate_enabled: bool = Field(default=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ValveCommand(SQLModel, table=True):
    """Persisted hardware valve command log surviving server restarts."""

    id: int | None = Field(default=None, primary_key=True)
    command_id: str = Field(index=True, unique=True)
    thread_id: str = Field(default="", index=True)
    farm_id: int | None = Field(default=None, foreign_key="farm.id", index=True)
    crop_type: str = Field(default="")
    command: str = Field(default="OPEN_VALVE")
    volume_dispatched_liters: float = Field(default=0.0)
    target_coordinates: str = Field(default="")
    water_salinity_ds_m: float = Field(default=0.0)
    dilution_protocol: str = Field(default="INACTIVE")
    status: str = Field(default="EXECUTED")  # EXECUTED, STOPPED, CANCELLED
    hardware_ack: str = Field(default="VALVE_OPENED_OK")
    timestamp_utc: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AlertLog(SQLModel, table=True):
    """Persisted anomaly and automated alert log."""

    id: int | None = Field(default=None, primary_key=True)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    farm_id: int | None = Field(default=None, foreign_key="farm.id", index=True)
    alert_type: str = Field(default="ANOMALY")
    severity: str = Field(default="WARNING")  # INFO, WARNING, CRITICAL
    message: str
    channel: str = Field(default="IN_APP")  # EMAIL, SMS, WEBHOOK, IN_APP
    acknowledged: bool = Field(default=False)


class DecisionLog(SQLModel, table=True):
    """Full audit record for a single farm analysis + actuation decision."""

    id: int | None = Field(default=None, primary_key=True)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    thread_id: str

    # Multi-tenancy links
    farm_id: int | None = Field(default=None, foreign_key="farm.id", index=True)
    user_id: int | None = Field(default=None, foreign_key="user.id", index=True)

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
    financial_analysis: str = Field(default="")
    reasoning_confidence: float = Field(default=0.0)

    # Decision outputs
    decision: str
    water_volume_liters: float
    financial_cost_dzd: float
    crop_value_at_risk_dzd: float = Field(default=0.0)

    # Human approval
    human_approved: bool

    # Outcome feedback (user rates the decision quality after the fact)
    outcome_rating: int | None = Field(default=None)  # 1-5, None if not rated


# ---------------------------------------------------------------------------
# Engine & Lifecycle
# ---------------------------------------------------------------------------

sqlite_url = f"sqlite:///{settings.sqlite_history_db}"
connect_args = {"check_same_thread": False}
engine = create_engine(sqlite_url, echo=False, connect_args=connect_args)


def create_db_and_tables() -> None:
    """Create all tables if they don't exist, then run migrations and seed data."""
    SQLModel.metadata.create_all(engine)
    log.info("Database tables created/verified at %s", settings.sqlite_history_db)

    # Run additive column migrations for existing databases
    try:
        from migrate_db import migrate

        migrate(settings.sqlite_history_db)
    except Exception as e:
        log.warning("Migration check failed (non-critical): %s", e)

    seed_initial_data()


def seed_initial_data() -> None:
    """Seed initial admin/viewer users and default pilot farm if empty."""
    import bcrypt

    with Session(engine) as session:
        # 1. Seed users if none exist
        existing_users = session.exec(select(User)).first()
        if not existing_users:
            admin_hash = bcrypt.hashpw(
                settings.admin_password.encode("utf-8"), bcrypt.gensalt()
            ).decode("utf-8")
            viewer_hash = bcrypt.hashpw(
                settings.viewer_password.encode("utf-8"), bcrypt.gensalt()
            ).decode("utf-8")

            admin_user = User(
                username=settings.admin_username,
                hashed_password=admin_hash,
                role="operator",
                full_name="Farm Administrator",
                email="admin@agri-agent.dz",
            )
            viewer_user = User(
                username=settings.viewer_username,
                hashed_password=viewer_hash,
                role="viewer",
                full_name="Agronomy Observer",
                email="viewer@agri-agent.dz",
            )
            session.add(admin_user)
            session.add(viewer_user)
            session.commit()
            session.refresh(admin_user)
            log.info("Seeded initial default users (admin, viewer)")

            # 2. Seed default farm
            default_farm = Farm(
                name="Oran Pilot Farm",
                owner_id=admin_user.id,
                crop_type="Wheat",
                farm_area_sqm=10000.0,
                latitude=settings.default_latitude,
                longitude=settings.default_longitude,
                moisture_threshold=10.0,
                water_salinity=1.2,
                plant_growth_stage="Vegetative Stage (High Water Demand)",
            )
            session.add(default_farm)
            session.commit()
            log.info("Seeded default pilot farm: %s", default_farm.name)


# ---------------------------------------------------------------------------
# User CRUD Operations
# ---------------------------------------------------------------------------


def get_user_by_username(username: str) -> User | None:
    """Retrieve user by username."""
    with Session(engine) as session:
        return session.exec(select(User).where(User.username == username)).first()


def get_user_by_id(user_id: int) -> User | None:
    """Retrieve user by ID."""
    with Session(engine) as session:
        return session.get(User, user_id)


def create_user(user: User) -> User:
    """Create a new user account."""
    with Session(engine) as session:
        session.add(user)
        session.commit()
        session.refresh(user)
        log.info("Created user %s (role=%s)", user.username, user.role)
        return user


def list_users() -> list[User]:
    """List all registered users."""
    with Session(engine) as session:
        return list(session.exec(select(User)).all())


# ---------------------------------------------------------------------------
# Farm CRUD Operations (Multi-Tenancy)
# ---------------------------------------------------------------------------


def create_farm(farm: Farm) -> Farm:
    """Create a new farm record."""
    with Session(engine) as session:
        session.add(farm)
        session.commit()
        session.refresh(farm)
        log.info("Created farm #%d: %s", farm.id, farm.name)
        return farm


def get_farm(farm_id: int) -> Farm | None:
    """Retrieve a farm by ID."""
    with Session(engine) as session:
        return session.get(Farm, farm_id)


def list_farms_for_user(owner_id: int | None = None) -> list[Farm]:
    """List farms, optionally filtered by owner."""
    with Session(engine) as session:
        if owner_id is not None:
            stmt = select(Farm).where(Farm.owner_id == owner_id)
        else:
            stmt = select(Farm)
        return list(session.exec(stmt).all())


def update_farm(farm_id: int, updates: dict) -> Farm | None:
    """Update farm fields."""
    with Session(engine) as session:
        farm = session.get(Farm, farm_id)
        if not farm:
            return None
        for k, v in updates.items():
            if hasattr(farm, k) and v is not None:
                setattr(farm, k, v)
        session.add(farm)
        session.commit()
        session.refresh(farm)
        log.info("Updated farm #%d (%s)", farm.id, farm.name)
        return farm


def delete_farm(farm_id: int) -> bool:
    """Delete a farm record."""
    with Session(engine) as session:
        farm = session.get(Farm, farm_id)
        if not farm:
            return False
        session.delete(farm)
        session.commit()
        log.info("Deleted farm #%d", farm_id)
        return True


# ---------------------------------------------------------------------------
# MCP Valve Command Operations (Persistent Registry)
# ---------------------------------------------------------------------------


def save_valve_command(record: ValveCommand) -> ValveCommand:
    """Persist or update an MCP valve command in SQLite."""
    with Session(engine) as session:
        existing = session.exec(
            select(ValveCommand).where(ValveCommand.command_id == record.command_id)
        ).first()
        if existing:
            for k, v in record.model_dump(exclude_unset=True).items():
                setattr(existing, k, v)
            session.add(existing)
            session.commit()
            session.refresh(existing)
            return existing
        else:
            session.add(record)
            session.commit()
            session.refresh(record)
            log.info("Persisted valve command %s to database", record.command_id)
            return record


def get_valve_command(command_id: str) -> ValveCommand | None:
    """Query valve status by unique command ID."""
    with Session(engine) as session:
        return session.exec(
            select(ValveCommand).where(ValveCommand.command_id == command_id)
        ).first()


def list_valve_commands(farm_id: int | None = None, limit: int = 100) -> list[ValveCommand]:
    """List recent valve commands, optionally filtered by farm."""
    with Session(engine) as session:
        stmt = select(ValveCommand).order_by(col(ValveCommand.timestamp_utc).desc()).limit(limit)
        if farm_id is not None:
            stmt = stmt.where(ValveCommand.farm_id == farm_id)
        return list(session.exec(stmt).all())


def emergency_stop_all_valves() -> int:
    """Mark all active valve commands as STOPPED in SQLite."""
    with Session(engine) as session:
        active_valves = session.exec(
            select(ValveCommand).where(ValveCommand.status == "EXECUTED")
        ).all()
        count = len(active_valves)
        for v in active_valves:
            v.status = "STOPPED"
            v.hardware_ack = "EMERGENCY_STOP_EXECUTED"
            session.add(v)
        session.commit()
        log.warning("Emergency stop triggered across %d active valve commands", count)
        return count


# ---------------------------------------------------------------------------
# AlertLog CRUD Operations
# ---------------------------------------------------------------------------


def save_alert_log(alert: AlertLog) -> AlertLog:
    """Save an alert or anomaly log entry."""
    with Session(engine) as session:
        session.add(alert)
        session.commit()
        session.refresh(alert)
        log.info(
            "Saved alert log #%d | type=%s | severity=%s",
            alert.id,
            alert.alert_type,
            alert.severity,
        )
        return alert


def get_alert_logs(farm_id: int | None = None, limit: int = 50) -> list[AlertLog]:
    """Return recent alert logs."""
    with Session(engine) as session:
        stmt = select(AlertLog).order_by(col(AlertLog.timestamp).desc()).limit(limit)
        if farm_id is not None:
            stmt = stmt.where(AlertLog.farm_id == farm_id)
        return list(session.exec(stmt).all())


def acknowledge_alert(alert_id: int) -> bool:
    """Mark an alert as acknowledged."""
    with Session(engine) as session:
        alert = session.get(AlertLog, alert_id)
        if not alert:
            return False
        alert.acknowledged = True
        session.add(alert)
        session.commit()
        return True


# ---------------------------------------------------------------------------
# DecisionLog CRUD Operations
# ---------------------------------------------------------------------------


def save_decision_log(log_entry: DecisionLog) -> DecisionLog:
    """Persist a new decision log entry and return it with its generated ID."""
    with Session(engine) as session:
        session.add(log_entry)
        session.commit()
        session.refresh(log_entry)
        log.info(
            "Saved decision log #%d | decision=%s | thread=%s | farm_id=%s",
            log_entry.id,
            log_entry.decision,
            log_entry.thread_id[:8],
            log_entry.farm_id,
        )
        return log_entry


def get_all_decision_logs(farm_id: int | None = None) -> list[DecisionLog]:
    """Return decision logs, newest first, optionally filtered by farm_id."""
    with Session(engine) as session:
        stmt = select(DecisionLog).order_by(col(DecisionLog.timestamp).desc())
        if farm_id is not None:
            stmt = stmt.where(DecisionLog.farm_id == farm_id)
        logs = session.exec(stmt).all()
        return list(logs)


def update_outcome_rating(log_id: int, rating: int) -> bool:
    """Update the outcome rating for a decision log entry."""
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


def get_aggregate_stats(farm_id: int | None = None) -> dict:
    """Return aggregate statistics for the analytics dashboard, optionally per farm."""
    with Session(engine) as session:
        stmt = select(DecisionLog)
        if farm_id is not None:
            stmt = stmt.where(DecisionLog.farm_id == farm_id)
        logs = session.exec(stmt).all()
        if not logs:
            return {
                "total_decisions": 0,
                "irrigate_count": 0,
                "wait_count": 0,
                "total_water_liters": 0.0,
                "total_cost_dzd": 0.0,
                "approval_rate": 0.0,
                "avg_soil_moisture": 0.0,
            }

        irrigate = [entry for entry in logs if entry.decision == "irrigate"]
        return {
            "total_decisions": len(logs),
            "irrigate_count": len(irrigate),
            "wait_count": len(logs) - len(irrigate),
            "total_water_liters": sum(entry.water_volume_liters for entry in logs),
            "total_cost_dzd": sum(entry.financial_cost_dzd for entry in logs),
            "approval_rate": (
                sum(1 for entry in irrigate if entry.human_approved) / len(irrigate)
                if irrigate
                else 0.0
            ),
            "avg_soil_moisture": sum(entry.soil_moisture for entry in logs) / len(logs),
        }
