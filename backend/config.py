"""
DataForge AI - Configuration
Loads settings from environment variables (.env in local dev).
Every AI-related setting is optional; the app must run without any of them.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _get_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


class Settings:
    APP_NAME = "DataForge AI"
    APP_SUBTITLE = "AI-Powered Data Analysis, Insights & Reporting Platform"
    AUTHOR = "Oleh Datsyk"

    # --- Paths ---
    BASE_DIR = BASE_DIR
    DATA_DIR = BASE_DIR / "data"
    UPLOADS_DIR = DATA_DIR / "uploads"
    WORKING_DIR = DATA_DIR / "working"
    REPORTS_DIR = DATA_DIR / "reports"

    # --- Database ---
    DATABASE_URL = os.getenv("DATABASE_URL", "").strip() or f"sqlite:///{DATA_DIR / 'dataforge.db'}"

    # --- Upload limits ---
    MAX_UPLOAD_SIZE_MB = _get_int("MAX_UPLOAD_SIZE_MB", 15)
    MAX_UPLOAD_SIZE_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024
    MAX_ROWS = _get_int("MAX_ROWS", 100000)
    ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls", ".json", ".tsv"}

    # --- AI Providers ---
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()

    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "").strip() or "gpt-4o-mini"
    ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "").strip() or "claude-3-5-haiku-20241022"
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "").strip() or "gemini-1.5-flash"

    PRIMARY_AI_PROVIDER = os.getenv("PRIMARY_AI_PROVIDER", "openai").strip().lower()
    FALLBACK_AI_PROVIDER = os.getenv("FALLBACK_AI_PROVIDER", "anthropic").strip().lower()
    SECONDARY_FALLBACK_AI_PROVIDER = os.getenv("SECONDARY_FALLBACK_AI_PROVIDER", "gemini").strip().lower()

    AI_REQUEST_TIMEOUT_SECONDS = _get_int("AI_REQUEST_TIMEOUT_SECONDS", 30)

    PREVIEW_ROWS = 10


settings = Settings()

for d in (settings.DATA_DIR, settings.UPLOADS_DIR, settings.WORKING_DIR, settings.REPORTS_DIR):
    d.mkdir(parents=True, exist_ok=True)
