"""Environment-derived settings, path constants, and the parsing helpers for them.

`.env` is loaded here rather than in server.py so that every module sees the same
environment no matter which one is imported first.
"""
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List, Optional

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).parent
PROJECT_DIR = ROOT_DIR.parent
load_dotenv(ROOT_DIR / ".env")

DEFAULT_MEMORY_DIR = PROJECT_DIR / "memory"
FRONTEND_BUILD_DIR = Path(os.environ.get("FRONTEND_BUILD_DIR", str(PROJECT_DIR / "frontend" / "build")))
LEGACY_STORAGE_URL = os.environ.get("LEGACY_STORAGE_URL", "").strip()
EMERGENT_KEY = os.environ.get("EMERGENT_LLM_KEY")


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def parse_int_env(name: str, default: int, minimum: Optional[int] = None, maximum: Optional[int] = None) -> int:
    try:
        value = int(os.environ.get(name, default))
    except (TypeError, ValueError):
        value = default
    if minimum is not None:
        value = max(minimum, value)
    if maximum is not None:
        value = min(maximum, value)
    return value


def parse_bool_env(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def parse_float_env(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def parse_csv_env(name: str) -> List[str]:
    return [item.strip() for item in os.environ.get(name, "").split(",") if item.strip()]


def parse_bool(value, default=False):
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def is_production_env() -> bool:
    explicit_env = (os.environ.get("APP_ENV") or os.environ.get("ENVIRONMENT") or "").strip().lower()
    if explicit_env:
        return explicit_env in {"prod", "production"}
    public_origin = (os.environ.get("PUBLIC_APP_ORIGIN") or "").strip().lower()
    return public_origin.startswith("https://") or parse_bool(os.environ.get("COOKIE_SECURE"), default=False)


def ensure_aware_utc(value: Any) -> Optional[datetime]:
    if not value:
        return None
    parsed = value
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return None
    if not isinstance(parsed, datetime):
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
