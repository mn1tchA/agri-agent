"""
Centralized application configuration using pydantic-settings.
All settings are loaded from environment variables / .env file.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # --- API Keys & URLs ---
    google_api_key: str = ""   # Used for embeddings (RAG memory)
    groq_api_key: str = ""     # Used for LLM inference — get free key at console.groq.com
    eppo_api_key: str = ""     # Optional EPPO Data Services API Key
    soilgrids_url: str = "https://rest.isric.org/soilgrids/v2.0"

    # --- Cost Model Defaults (USD) ---
    default_water_rate_usd: float = 0.001       # USD per Liter
    default_electricity_rate_usd: float = 0.12  # USD per kWh
    default_fuel_price_usd: float = 1.05        # USD per Liter (Diesel)
    default_labor_wage_usd: float = 15.00       # USD per Hour

    # --- LLM Backend ---
    # Set LLM_PROVIDER=groq in .env to use Groq (recommended — much higher free limits).
    # Set LLM_PROVIDER=gemini to use Google Gemini.
    llm_provider: str = "groq"

    # Groq model — llama-3.3-70b-versatile: best quality, 30 RPM / 14 400 RPD free
    groq_model: str = "llama-3.3-70b-versatile"
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

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


# Singleton instance — import this everywhere
settings = Settings()
