"""
Centralized application configuration using pydantic-settings.
All settings are loaded from environment variables / .env file.
"""
import logging

from pydantic_settings import BaseSettings, SettingsConfigDict

log = logging.getLogger("agri_agent.config")

_INSECURE_JWT_SENTINEL = "CHANGE-ME-GENERATE-A-REAL-SECRET"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=[".env", "../.env"],
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- API Keys ---
    google_api_key: str = ""   # Used for embeddings (RAG memory)
    groq_api_key: str = ""     # Used for LLM inference — get free key at console.groq.com

    # --- LLM Backend ---
    # Set LLM_PROVIDER=groq in .env to use Groq (recommended — much higher free limits).
    # Set LLM_PROVIDER=gemini to use Google Gemini.
    llm_provider: str = "groq"

    # Groq model — qwen/qwen3.8-27b: high speed, active on Groq free tier
    groq_model: str = "qwen/qwen3.8-27b"
    groq_temperature: float = 0.0

    # Gemini model (fallback / alternative)
    gemini_model: str = "gemini-2.5-flash"
    gemini_temperature: float = 0.0

    # --- Default Farm Location (Oran, Algeria — overridable per request) ---
    default_latitude: float = 35.6911
    default_longitude: float = -0.6328

    # --- Database Paths ---
    sqlite_history_db: str = "history.db"
    sqlite_checkpoints_db: str = "checkpoints.sqlite"
    chroma_persist_dir: str = "./chroma_db"

    # --- CORS ---
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:80,http://127.0.0.1:80"

    # --- JWT Authentication ---
    # Generate a strong secret with: python -c "import secrets; print(secrets.token_hex(32))"
    # Set JWT_SECRET_KEY in .env — NEVER use the default in production!
    jwt_secret_key: str = _INSECURE_JWT_SENTINEL
    access_token_expire_minutes: int = 60  # 1 hour; reduce for high-security environments

    # --- User Credentials (env-var backed; swap for DB in multi-tenant phase) ---
    # Operator: full access including analysis runs + hardware actuation
    admin_username: str = "admin"
    admin_password: str = "changeme"
    # Viewer: read-only access to history, stats, health
    viewer_username: str = "viewer"
    viewer_password: str = "viewerpass"

    # --- Scheduler & Alerting ---
    scheduler_enabled: bool = True
    scheduler_interval_minutes: int = 60
    alert_email_enabled: bool = False
    alert_email_to: str = "farmer@example.com"
    alert_webhook_url: str = ""

    # --- Observability ---
    prometheus_enabled: bool = True
    otel_enabled: bool = False
    otel_service_name: str = "agri-agent-swarm"
    langsmith_tracing: bool = False
    langsmith_project: str = "agri-agent-swarm"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def validate_security(self) -> None:
        """Warn loudly if insecure defaults are detected at startup."""
        if self.jwt_secret_key == _INSECURE_JWT_SENTINEL:
            log.critical(
                "⚠️  JWT_SECRET_KEY is using the insecure default! "
                "Generate a real secret: python -c \"import secrets; print(secrets.token_hex(32))\" "
                "and set JWT_SECRET_KEY in your .env file."
            )
        if self.admin_password in ("changeme", "password", "admin", ""):
            log.warning("⚠️  ADMIN_PASSWORD is weak or using the default. Change it in .env!")
        if self.viewer_password in ("viewerpass", "password", "viewer", ""):
            log.warning("⚠️  VIEWER_PASSWORD is weak or using the default. Change it in .env!")


# Singleton instance — import this everywhere
settings = Settings()

