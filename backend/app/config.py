"""
Algeo Verify — Application Configuration
Loads all environment variables from .env using python-dotenv.
"""

import os
from pathlib import Path
from functools import lru_cache

from dotenv import load_dotenv

# ── Load .env from the backend/ directory ────────────────────────────
_env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=_env_path)


class Settings:
    """Central configuration pulled from environment variables."""

    # ── Database ─────────────────────────────────────────────────────
    # SQLite for local dev, PostgreSQL for production.
    # Set DATABASE_URL in .env to override.
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "sqlite:///./algeo_verify.db",
    )

    # ── Geo-data paths ───────────────────────────────────────────────
    _base_dir = Path(__file__).resolve().parent.parent.parent  # project root
    GEO_DATA_DIR: Path = Path(
        os.getenv("GEO_DATA_DIR", str(_base_dir / "database"))
    )
    WILAYA_JSON: Path = GEO_DATA_DIR / "wilaya.json"
    COMMUNES_JSON: Path = GEO_DATA_DIR / "communes.json"

    # ── API ───────────────────────────────────────────────────────────
    API_V1_PREFIX: str = os.getenv("API_V1_PREFIX", "/api/v1")
    APP_NAME: str = os.getenv("APP_NAME", "Algeo Verify")
    DEBUG: bool = os.getenv("DEBUG", "true").lower() in ("true", "1", "yes")

    # ── AI (Gemini) ───────────────────────────────────────────────────
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    AI_ENABLED: bool = os.getenv("AI_ENABLED", "false").lower() in ("true", "1", "yes")

    # ── Google Maps ───────────────────────────────────────────────────
    GOOGLE_MAPS_API_KEY: str = os.getenv("GOOGLE_MAPS_API_KEY", "")
    GEOCODING_ENABLED: bool = os.getenv("GEOCODING_ENABLED", "false").lower() in ("true", "1", "yes")

    # ── CORS ──────────────────────────────────────────────────────────
    CORS_ORIGINS: list[str] = os.getenv(
        "CORS_ORIGINS", "http://localhost:3000,http://localhost:5173"
    ).split(",")


@lru_cache()
def get_settings() -> Settings:
    """Return a cached Settings instance (singleton)."""
    return Settings()
