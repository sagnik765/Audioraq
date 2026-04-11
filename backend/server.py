from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
PROJECT_DIR = ROOT_DIR.parent
load_dotenv(ROOT_DIR / ".env")

from fastapi import APIRouter, FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel
from starlette.middleware.cors import CORSMiddleware

import bcrypt
import email.utils
import json
import jwt
import logging
import os
import re
import requests
import secrets
import shutil
import subprocess
import tempfile
import uuid
import wave
import xml.etree.ElementTree as ET
import zipfile

from bson import ObjectId
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Literal, Optional, Set
from urllib.parse import urlencode, urlparse


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ.get("DB_NAME", "audioraq")]

JWT_ALGORITHM = "HS256"
DEFAULT_MEMORY_DIR = PROJECT_DIR / "memory"
FRONTEND_BUILD_DIR = Path(os.environ.get("FRONTEND_BUILD_DIR", str(PROJECT_DIR / "frontend" / "build")))

STORAGE_URL = "https://integrations.emergentagent.com/objstore/api/v1/storage"
EMERGENT_KEY = os.environ.get("EMERGENT_LLM_KEY")
APP_NAME = "audioraq"
storage_key = None
pending_social_cookie_name = "pending_social_auth"
transcription_model_cache = None
transcription_model_path = None

DEFAULT_SHOW_CATEGORY = "general"
MAX_LIBRARY_ITEMS = 2000
LEGAL_VIEWER_AGE = 18
ALL_AGES_RATING = "all_ages"
MATURE_RATING = "18+"
PUBLICATION_STATUS_PUBLISHED = "published"
PUBLICATION_STATUS_DRAFT = "draft"
MODERATION_STATUS_CLEAR = "clear"
MODERATION_STATUS_REVIEW = "review"
MODERATION_STATUS_BLOCKED = "blocked"
SOCIAL_PROVIDER_GOOGLE = "google"
SOCIAL_PROVIDER_APPLE = "apple"
SUPPORTED_SOCIAL_PROVIDERS = {SOCIAL_PROVIDER_GOOGLE, SOCIAL_PROVIDER_APPLE}
AGENT2_VERSION = "2026-04-12.1"

AGENT2_RAG_SAFETY_KB = [
    {
        "id": "protected-class-derogation",
        "text": "Demeaning claims, slurs, or inferiority claims about protected classes require review.",
        "patterns": [r"\ball\s+\w+\s+are\s+(bad|stupid|inferior|dangerous)\b", r"\b(inferior|subhuman|vermin)\b"],
        "severity": "high",
    },
    {
        "id": "harassment-targeting",
        "text": "Personal attacks, threats, or calls to exclude someone from normal life require review.",
        "patterns": [r"\b(should be banned from society|do not deserve rights|ruin their life)\b"],
        "severity": "medium",
    },
    {
        "id": "dangerous-advice",
        "text": "Dangerous medical, legal, or safety instructions should not be published automatically.",
        "patterns": [r"\b(drink bleach|stop taking insulin|ignore your doctor|build a bomb|kill yourself)\b"],
        "severity": "high",
    },
    {
        "id": "dehumanization",
        "text": "Dehumanizing language frames people as pests, animals, or diseases to justify mistreatment.",
        "patterns": [r"\b(they are animals|they are pests|eradicate them|wipe them out)\b"],
        "severity": "high",
    },
    {
        "id": "creator-quality",
        "text": "Podcast drafts should include a clear listener promise, concrete examples, and a useful takeaway.",
        "patterns": [r"\b(leverage synergies|in today's fast-paced world|game[- ]changer|unlock your potential)\b"],
        "severity": "low",
    },
]

AGENT2_RLAIF_POLICY = [
    "Reward a clear listener promise and concrete outcome.",
    "Reward specific examples over generic motivational language.",
    "Reward human pacing: tension, questions, and useful transitions.",
    "Penalize unsafe, hateful, or harmful claims found by RAG safety retrieval.",
    "Penalize AI-sounding repetition, vague buzzwords, and overlong sentences.",
    "Preserve the creator's chosen audience, tone, and episode goal.",
]


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def parse_int_env(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def get_google_client_id() -> str:
    return os.environ.get("GOOGLE_CLIENT_ID", "").strip()


def get_google_client_secret() -> str:
    return os.environ.get("GOOGLE_CLIENT_SECRET", "").strip()


def is_google_oauth_configured() -> bool:
    return bool(get_google_client_id() and get_google_client_secret())


def get_apple_client_id() -> str:
    return os.environ.get("APPLE_CLIENT_ID", "").strip()


def get_apple_team_id() -> str:
    return os.environ.get("APPLE_TEAM_ID", "").strip()


def get_apple_key_id() -> str:
    return os.environ.get("APPLE_KEY_ID", "").strip()


def get_apple_private_key() -> str:
    return os.environ.get("APPLE_PRIVATE_KEY", "").replace("\\n", "\n").strip()


def is_apple_oauth_configured() -> bool:
    return bool(get_apple_client_id() and get_apple_team_id() and get_apple_key_id() and get_apple_private_key())


def is_social_provider_configured(provider: str) -> bool:
    if provider == SOCIAL_PROVIDER_GOOGLE:
        return is_google_oauth_configured()
    if provider == SOCIAL_PROVIDER_APPLE:
        return is_apple_oauth_configured()
    return False


def get_public_request_origin(request: Request) -> str:
    forwarded_proto = (request.headers.get("x-forwarded-proto") or "").split(",")[0].strip()
    forwarded_host = (request.headers.get("x-forwarded-host") or "").split(",")[0].strip()
    scheme = forwarded_proto or request.url.scheme
    host = forwarded_host or request.headers.get("host") or request.url.netloc
    return f"{scheme}://{host}".rstrip("/")


def get_allowed_return_origins(request: Request) -> Set[str]:
    allowed = {get_public_request_origin(request)}
    for origin in [item.strip().rstrip("/") for item in os.environ.get("CORS_ORIGINS", "").split(",") if item.strip()]:
        allowed.add(origin)
    return allowed


def sanitize_return_origin(candidate: Optional[str], request: Request) -> str:
    normalized = (candidate or "").strip().rstrip("/")
    if normalized and normalized in get_allowed_return_origins(request):
        return normalized
    return get_public_request_origin(request)


def build_frontend_url(base_origin: str, path: str, params: Optional[Dict[str, Any]] = None) -> str:
    normalized_origin = (base_origin or "").rstrip("/")
    normalized_path = path if path.startswith("/") else f"/{path}"
    query_params = {key: value for key, value in (params or {}).items() if value not in [None, ""]}
    if not query_params:
        return f"{normalized_origin}{normalized_path}"
    return f"{normalized_origin}{normalized_path}?{urlencode(query_params)}"


def get_oauth_redirect_uri(request: Request, provider: str) -> str:
    base_origin = get_public_request_origin(request)
    override_name = f"{provider.upper()}_REDIRECT_URI"
    override = os.environ.get(override_name, "").strip()
    if override:
        return override
    return f"{base_origin}/api/auth/oauth/{provider}/callback"


def build_oauth_state(provider: str, intent: str, return_origin: str, role_hint: str = "") -> str:
    payload = {
        "type": "oauth_state",
        "provider": provider,
        "intent": "register" if intent == "register" else "login",
        "return_origin": return_origin,
        "role_hint": role_hint if role_hint in {"user", "podcaster"} else "",
        "nonce": secrets.token_urlsafe(24),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)


def decode_oauth_state(state: str, expected_provider: str) -> Dict[str, Any]:
    try:
        payload = jwt.decode(state, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        raise HTTPException(status_code=400, detail="Invalid social sign-in state")
    if payload.get("type") != "oauth_state" or payload.get("provider") != expected_provider:
        raise HTTPException(status_code=400, detail="Invalid social sign-in state")
    return payload


def social_provider_record(provider: str, profile: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "sub": profile["sub"],
        "email": (profile.get("email") or "").lower().strip(),
        "email_verified": bool(profile.get("email_verified")),
        "linked_at": now_iso(),
    }


def build_social_state_error_redirect(request: Request, return_origin: str, message: str) -> RedirectResponse:
    destination = build_frontend_url(return_origin, "/login", {"auth_error": message[:180]})
    response = RedirectResponse(destination, status_code=302)
    clear_pending_social_cookie(response)
    return response


def clear_pending_social_cookie(response: Response):
    cookie_settings = {"path": "/"}
    cookie_domain = os.environ.get("COOKIE_DOMAIN")
    if cookie_domain:
        cookie_settings["domain"] = cookie_domain
    response.delete_cookie(pending_social_cookie_name, **cookie_settings)


def set_pending_social_cookie(response: Response, session_id: str, request: Optional[Request] = None):
    cookie_settings = get_cookie_settings(request)
    response.set_cookie(key=pending_social_cookie_name, value=session_id, max_age=900, **cookie_settings)


def get_pending_social_cookie(request: Request) -> str:
    return (request.cookies.get(pending_social_cookie_name) or "").strip()


def normalize_content_rating(value: Optional[str]) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"18+", "mature", "adult", "explicit", "restricted"}:
        return MATURE_RATING
    return ALL_AGES_RATING


def normalize_age_value(value: Any) -> Optional[int]:
    if value in [None, ""]:
        return None
    try:
        age = int(value)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Age must be a number")
    if age < 0 or age > 120:
        raise HTTPException(status_code=400, detail="Age must be between 0 and 120")
    return age


def is_underage_user(user: Optional[Dict[str, Any]]) -> bool:
    if not user:
        return False
    age = user.get("age")
    try:
        return age is not None and int(age) < LEGAL_VIEWER_AGE
    except (TypeError, ValueError):
        return False


def is_episode_owner(user: Optional[Dict[str, Any]], episode: Optional[Dict[str, Any]]) -> bool:
    if not user or not episode:
        return False
    if user.get("role") == "admin":
        return True
    return user_id_str(user) == str(episode.get("podcaster_id") or "")


def is_episode_publicly_listable(episode: Dict[str, Any]) -> bool:
    return (
        not episode.get("is_deleted")
        and episode.get("publication_status", PUBLICATION_STATUS_PUBLISHED) != PUBLICATION_STATUS_DRAFT
        and episode.get("moderation_status", MODERATION_STATUS_CLEAR) != MODERATION_STATUS_BLOCKED
    )


def can_access_episode(user: Optional[Dict[str, Any]], episode: Dict[str, Any]) -> bool:
    if episode.get("is_deleted"):
        return False
    if is_episode_owner(user, episode):
        return True
    if episode.get("publication_status", PUBLICATION_STATUS_PUBLISHED) == PUBLICATION_STATUS_DRAFT:
        return False
    if episode.get("moderation_status", MODERATION_STATUS_CLEAR) == MODERATION_STATUS_BLOCKED:
        return False
    if is_underage_user(user) and normalize_content_rating(episode.get("audience_rating")) == MATURE_RATING:
        return False
    return True


def build_public_episode_query(current_user: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    query = {
        "is_deleted": False,
        "publication_status": {"$ne": PUBLICATION_STATUS_DRAFT},
        "moderation_status": {"$ne": MODERATION_STATUS_BLOCKED},
    }
    if is_underage_user(current_user):
        query["audience_rating"] = {"$ne": MATURE_RATING}
    return query


def get_jwt_secret():
    return os.environ["JWT_SECRET"]


def parse_bool(value, default=False):
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def get_cookie_settings(request: Optional[Request] = None):
    forwarded_proto = request.headers.get("x-forwarded-proto") if request else None
    request_scheme = request.url.scheme if request else None
    secure_default = (forwarded_proto or request_scheme or "").lower() == "https"
    secure = parse_bool(os.environ.get("COOKIE_SECURE"), default=secure_default)
    same_site = os.environ.get("COOKIE_SAMESITE", "lax").strip().lower()
    if same_site not in {"lax", "strict", "none"}:
        same_site = "lax"

    settings = {
        "httponly": True,
        "secure": secure,
        "samesite": same_site,
        "path": "/",
    }

    cookie_domain = os.environ.get("COOKIE_DOMAIN")
    if cookie_domain:
        settings["domain"] = cookie_domain

    return settings


def set_auth_cookies(response: Response, access_token: str, refresh_token: str, request: Optional[Request] = None):
    cookie_settings = get_cookie_settings(request)
    response.set_cookie(key="access_token", value=access_token, max_age=3600, **cookie_settings)
    response.set_cookie(key="refresh_token", value=refresh_token, max_age=604800, **cookie_settings)


def clear_auth_cookies(response: Response):
    cookie_settings = {"path": "/"}
    cookie_domain = os.environ.get("COOKIE_DOMAIN")
    if cookie_domain:
        cookie_settings["domain"] = cookie_domain
    response.delete_cookie("access_token", **cookie_settings)
    response.delete_cookie("refresh_token", **cookie_settings)


def init_storage():
    global storage_key
    if storage_key:
        return storage_key
    resp = requests.post(f"{STORAGE_URL}/init", json={"emergent_key": EMERGENT_KEY}, timeout=30)
    resp.raise_for_status()
    storage_key = resp.json()["storage_key"]
    return storage_key


def put_object(path, data, content_type):
    key = init_storage()
    resp = requests.put(
        f"{STORAGE_URL}/objects/{path}",
        headers={"X-Storage-Key": key, "Content-Type": content_type},
        data=data,
        timeout=300,
    )
    resp.raise_for_status()
    return resp.json()


def get_object(path):
    key = init_storage()
    resp = requests.get(
        f"{STORAGE_URL}/objects/{path}",
        headers={"X-Storage-Key": key},
        timeout=120,
    )
    resp.raise_for_status()
    return resp.content, resp.headers.get("Content-Type", "application/octet-stream")


def delete_object(path, missing_ok: bool = True) -> str:
    normalized_path = (path or "").strip()
    if not normalized_path:
        return "skipped"

    key = init_storage()
    resp = requests.delete(
        f"{STORAGE_URL}/objects/{normalized_path}",
        headers={"X-Storage-Key": key},
        timeout=120,
    )
    if missing_ok and resp.status_code == 404:
        return "missing"
    if resp.status_code == 405:
        logger.warning(f"Storage API does not support hard delete for {normalized_path}; scrubbing object contents instead")
        scrub_resp = requests.put(
            f"{STORAGE_URL}/objects/{normalized_path}",
            headers={"X-Storage-Key": key, "Content-Type": "application/octet-stream"},
            data=b"",
            timeout=120,
        )
        scrub_resp.raise_for_status()
        return "scrubbed"
    resp.raise_for_status()
    return "deleted"


def cleanup_storage_paths(paths: List[str], strict: bool = False) -> Dict[str, Any]:
    deleted = []
    scrubbed = []
    missing = []
    failures = []

    seen = set()
    normalized_paths = []
    for raw_path in paths:
        path = (raw_path or "").strip()
        if not path or path in seen:
            continue
        seen.add(path)
        normalized_paths.append(path)

    for path in normalized_paths:
        try:
            cleanup_result = delete_object(path, missing_ok=True)
            if cleanup_result == "deleted":
                deleted.append(path)
            elif cleanup_result == "scrubbed":
                scrubbed.append(path)
            elif cleanup_result == "missing":
                missing.append(path)
        except Exception as exc:
            logger.error(f"Storage cleanup failed for {path}: {exc}")
            failures.append({"path": path, "error": str(exc)})

    if strict and failures:
        raise HTTPException(status_code=502, detail="Could not remove media from storage. Please retry.")

    return {"deleted": deleted, "scrubbed": scrubbed, "missing": missing, "failures": failures}


def hash_password(password):
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(plain_password, hashed_password):
    if not hashed_password:
        return False
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


def create_access_token(user_id, email):
    payload = {
        "sub": user_id,
        "email": email,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=60),
        "type": "access",
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)


def create_refresh_token(user_id):
    payload = {
        "sub": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(days=7),
        "type": "refresh",
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)


async def get_current_user(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
        user = await db.users.find_one({"_id": ObjectId(payload["sub"])})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        user["_id"] = str(user["_id"])
        user.pop("password_hash", None)
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


async def try_get_current_user(request: Optional[Request]):
    if request is None:
        return None
    try:
        return await get_current_user(request)
    except HTTPException as exc:
        if exc.status_code == 401:
            return None
        raise


def user_object_id(user) -> ObjectId:
    raw = user.get("_id") or user.get("id")
    if isinstance(raw, ObjectId):
        return raw
    return ObjectId(str(raw))


def user_id_str(user) -> str:
    return str(user.get("_id") or user.get("id"))


def clean_doc(doc):
    if not doc:
        return None
    cleaned = dict(doc)
    cleaned.pop("_id", None)
    return cleaned


def build_default_show_title(user_name: str) -> str:
    user_name = (user_name or "Audioraq Creator").strip()
    if user_name.lower().endswith("show"):
        return user_name
    if user_name.endswith("s"):
        return f"{user_name}' Show"
    return f"{user_name}'s Show"


def parse_iso_datetime(value: Optional[str]):
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def parse_rss_datetime(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    try:
        parsed = email.utils.parsedate_to_datetime(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).isoformat()
    except Exception:
        return None


def strip_html(value: Optional[str]) -> str:
    if not value:
        return ""
    return re.sub(r"<[^>]+>", " ", value).replace("&nbsp;", " ").strip()


def strip_code_fences(value: str) -> str:
    cleaned = (value or "").strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
        cleaned = cleaned.rsplit("```", 1)[0]
    return cleaned.strip()


def parse_json_payload(value: str) -> Any:
    return json.loads(strip_code_fences(value))


def normalize_string_list(value: Any, limit: int = 10) -> List[str]:
    if value is None:
        return []

    if isinstance(value, str):
        parts = re.split(r"[\n,]+", value)
    elif isinstance(value, list):
        parts = value
    else:
        parts = [value]

    cleaned = []
    seen = set()
    for item in parts:
        text = str(item).strip()
        if not text:
            continue
        lowered = text.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        cleaned.append(text)
        if len(cleaned) >= limit:
            break
    return cleaned


def normalize_outline_items(items: Any) -> List[Dict[str, Any]]:
    if not isinstance(items, list):
        return []

    normalized = []
    for item in items[:6]:
        if isinstance(item, dict):
            section_title = str(
                item.get("section_title")
                or item.get("title")
                or item.get("section")
                or item.get("heading")
                or ""
            ).strip()
            purpose = str(item.get("purpose") or item.get("goal") or item.get("why") or "").strip()
            beats = normalize_string_list(
                item.get("beats") or item.get("talking_points") or item.get("bullets") or []
            )
        else:
            section_title = str(item).strip()
            purpose = ""
            beats = []

        if not section_title:
            continue

        normalized.append(
            {
                "section_title": section_title,
                "purpose": purpose,
                "beats": beats[:5],
            }
        )
    return normalized


def build_ai_publish_description(generation: Dict[str, Any]) -> str:
    parts = []
    if generation.get("one_line_promise"):
        parts.append(generation["one_line_promise"])
    if generation.get("hook"):
        parts.append(f"Hook: {generation['hook']}")
    if generation.get("show_notes_summary"):
        parts.append(generation["show_notes_summary"])
    if generation.get("talking_points"):
        bullet_lines = "\n".join(f"- {point}" for point in generation["talking_points"][:5])
        parts.append(f"Highlights:\n{bullet_lines}")
    if generation.get("outro_cta"):
        parts.append(f"Closer: {generation['outro_cta']}")
    return "\n\n".join(part for part in parts if part).strip()


def build_episode_review_text(
    show: Dict[str, Any],
    title: str,
    description: str,
    category: str,
    generation: Optional[Dict[str, Any]] = None,
    media_analysis: Optional[Dict[str, Any]] = None,
) -> str:
    parts = [
        f"Show title: {show.get('title', '')}",
        f"Show description: {show.get('description', '')}",
        f"Episode title: {title}",
        f"Episode description: {description}",
        f"Category: {category}",
    ]
    if generation:
        parts.extend(
            [
                f"Hook: {generation.get('hook', '')}",
                f"Intro: {generation.get('intro_script', '')}",
                f"Talking points: {', '.join(generation.get('talking_points', [])[:6])}",
                f"Outline: {' | '.join(section.get('section_title', '') for section in generation.get('outline', [])[:5])}",
                f"Show notes summary: {generation.get('show_notes_summary', '')}",
            ]
        )
    if media_analysis and media_analysis.get("transcript_excerpt"):
        parts.extend(
            [
                f"Media transcript status: {media_analysis.get('status', 'unknown')}",
                f"Media transcript provider: {media_analysis.get('provider', '')}",
                f"Media transcript excerpt: {media_analysis.get('transcript_excerpt', '')}",
            ]
        )
    return "\n".join(part.strip() for part in parts if str(part).strip()).strip()


def heuristic_episode_safety_review(source_text: str, selected_rating: str = ALL_AGES_RATING) -> Dict[str, Any]:
    lowered = (source_text or "").lower()
    rule_map = {
        "hate speech": ["ethnic cleansing", "white power", "lynch", "gas the", "heil hitler"],
        "self-harm": ["suicide", "self-harm", "kill yourself", "cut yourself"],
        "graphic violence": ["beheading", "torture", "massacre", "bomb-making"],
        "explicit sexual content": ["porn", "hardcore sex", "fetish", "sexual assault"],
        "dangerous instructions": ["drink bleach", "build a bomb", "stop taking insulin", "ignore your doctor"],
    }
    flags = [label for label, terms in rule_map.items() if any(term in lowered for term in terms)]

    status = MODERATION_STATUS_CLEAR
    risk_level = "low"
    summary = "No obvious hateful or harmful risk detected in the episode content."
    if flags:
        status = MODERATION_STATUS_REVIEW
        risk_level = "medium"
        summary = f"Detected content that may need review: {', '.join(flags[:3])}."
        if "hate speech" in flags or len(flags) >= 2:
            status = MODERATION_STATUS_BLOCKED
            risk_level = "high"
            summary = f"Detected high-risk content that should not be published automatically: {', '.join(flags[:3])}."

    recommended_age_gate = normalize_content_rating(selected_rating)
    if flags and recommended_age_gate != MATURE_RATING:
        recommended_age_gate = MATURE_RATING

    return {
        "status": status,
        "risk_level": risk_level,
        "flags": flags,
        "summary": summary,
        "recommended_age_gate": recommended_age_gate,
        "provider": "heuristic",
        "reviewed_at": now_iso(),
    }


def normalize_episode_safety_result(
    raw: Any,
    fallback: Dict[str, Any],
    selected_rating: str,
    media_analysis: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        raw = {}

    status = str(raw.get("status") or fallback.get("status") or MODERATION_STATUS_CLEAR).strip().lower()
    if status not in {MODERATION_STATUS_CLEAR, MODERATION_STATUS_REVIEW, MODERATION_STATUS_BLOCKED}:
        status = fallback.get("status", MODERATION_STATUS_CLEAR)

    risk_level = str(raw.get("risk_level") or fallback.get("risk_level") or "low").strip().lower()
    if risk_level not in {"low", "medium", "high"}:
        risk_level = fallback.get("risk_level", "low")

    summary = str(raw.get("summary") or fallback.get("summary") or "").strip()[:300]
    flags = normalize_string_list(raw.get("flags"), limit=6)
    recommended_age_gate = normalize_content_rating(
        raw.get("recommended_age_gate") or selected_rating or fallback.get("recommended_age_gate")
    )
    media_fields = {
        "media_reviewed": False,
        "media_review_status": "not_requested",
        "media_review_provider": "",
        "media_transcript_excerpt": "",
        "media_transcript_word_count": 0,
        "media_transcript_truncated": False,
        "media_review_error": "",
    }
    if media_analysis:
        media_fields.update(
            {
                "media_reviewed": bool(media_analysis.get("media_reviewed")),
                "media_review_status": media_analysis.get("status", "unknown"),
                "media_review_provider": media_analysis.get("provider", ""),
                "media_transcript_excerpt": media_analysis.get("transcript_excerpt", "")[:2400],
                "media_transcript_word_count": int(media_analysis.get("word_count") or 0),
                "media_transcript_truncated": bool(media_analysis.get("transcript_truncated")),
                "media_review_error": str(media_analysis.get("error") or "")[:240],
            }
        )

    normalized = {
        "status": status,
        "risk_level": risk_level,
        "flags": flags,
        "summary": summary or fallback.get("summary", ""),
        "recommended_age_gate": recommended_age_gate,
        "provider": raw.get("provider") or fallback.get("provider") or "emergent",
        "reviewed_at": now_iso(),
    }
    normalized.update(media_fields)
    return normalized


def build_transcript_excerpt(transcript_text: str, max_chars: int = 2600) -> str:
    cleaned = re.sub(r"\s+", " ", (transcript_text or "")).strip()
    if len(cleaned) <= max_chars:
        return cleaned

    risk_terms = [
        "suicide",
        "kill yourself",
        "white power",
        "heil hitler",
        "bomb",
        "drink bleach",
        "sexual assault",
        "torture",
    ]
    highlighted = []
    for sentence in re.split(r"(?<=[.!?])\s+", cleaned):
        if any(term in sentence.lower() for term in risk_terms):
            highlighted.append(sentence.strip())
        if len(highlighted) >= 4:
            break

    half = max_chars // 2
    head = cleaned[:half].rsplit(" ", 1)[0]
    tail = cleaned[-half:].lstrip()
    parts = []
    if highlighted:
        parts.append("Flagged transcript moments: " + " | ".join(highlighted[:4]))
    parts.append(head)
    parts.append("...")
    parts.append(tail)
    excerpt = "\n".join(part for part in parts if part)
    return excerpt[: max_chars + 400]


def get_vosk_model():
    global transcription_model_cache, transcription_model_path
    configured_model_dir = Path(os.environ.get("VOSK_MODEL_DIR", "/tmp/vosk-model-small-en-us-0.15"))
    configured_model_url = os.environ.get(
        "VOSK_MODEL_URL",
        "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip",
    ).strip()
    if transcription_model_cache is not None and transcription_model_path == configured_model_dir:
        return transcription_model_cache

    model_dir = configured_model_dir
    if not (model_dir / "am").exists():
        model_dir.parent.mkdir(parents=True, exist_ok=True)
        archive_path = model_dir.parent / f"{model_dir.name}.zip"
        extract_parent = model_dir.parent / f"{model_dir.name}.extract"
        if extract_parent.exists():
            shutil.rmtree(extract_parent)
        if archive_path.exists():
            archive_path.unlink()

        with requests.get(configured_model_url, stream=True, timeout=300) as response:
            response.raise_for_status()
            with open(archive_path, "wb") as archive_file:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        archive_file.write(chunk)

        with zipfile.ZipFile(archive_path, "r") as archive:
            archive.extractall(extract_parent)

        extracted_dirs = [path for path in extract_parent.iterdir() if path.is_dir()]
        if not extracted_dirs:
            raise RuntimeError("Downloaded Vosk model archive did not contain a model directory")
        extracted_model_dir = extracted_dirs[0]
        if model_dir.exists():
            shutil.rmtree(model_dir)
        shutil.move(str(extracted_model_dir), str(model_dir))
        shutil.rmtree(extract_parent, ignore_errors=True)
        archive_path.unlink(missing_ok=True)

    from vosk import Model, SetLogLevel

    SetLogLevel(-1)
    transcription_model_cache = Model(str(model_dir))
    transcription_model_path = model_dir
    return transcription_model_cache


def transcribe_media_for_safety(data: bytes, filename: str, content_type: str) -> Dict[str, Any]:
    if not data:
        return {
            "status": "empty_upload",
            "provider": "",
            "media_reviewed": False,
            "transcript_text": "",
            "transcript_excerpt": "",
            "word_count": 0,
            "transcript_truncated": False,
            "error": "",
        }

    max_seconds = max(0, parse_int_env("MAX_MEDIA_TRANSCRIPT_SECONDS", 1800))
    suffix = Path(filename or "upload.bin").suffix or ".bin"
    extracted_path = ""
    source_path = ""

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as media_file:
            media_file.write(data)
            source_path = media_file.name

        extracted_path = f"{source_path}.wav"
        ffmpeg_cmd = ["ffmpeg", "-y", "-i", source_path]
        if max_seconds:
            ffmpeg_cmd.extend(["-t", str(max_seconds)])
        ffmpeg_cmd.extend(["-vn", "-ac", "1", "-ar", "16000", extracted_path])
        ffmpeg_run = subprocess.run(ffmpeg_cmd, capture_output=True, text=True, timeout=240)
        if ffmpeg_run.returncode != 0:
            raise RuntimeError((ffmpeg_run.stderr or ffmpeg_run.stdout or "ffmpeg conversion failed").strip())

        from vosk import KaldiRecognizer

        model = get_vosk_model()
        transcript_parts = []
        with wave.open(extracted_path, "rb") as wav_file:
            recognizer = KaldiRecognizer(model, wav_file.getframerate())
            recognizer.SetWords(False)
            while True:
                audio_chunk = wav_file.readframes(4000)
                if not audio_chunk:
                    break
                if recognizer.AcceptWaveform(audio_chunk):
                    payload = json.loads(recognizer.Result())
                    text = str(payload.get("text") or "").strip()
                    if text:
                        transcript_parts.append(text)
            final_payload = json.loads(recognizer.FinalResult())
            final_text = str(final_payload.get("text") or "").strip()
            if final_text:
                transcript_parts.append(final_text)

        transcript_text = " ".join(transcript_parts).strip()
        if not transcript_text:
            return {
                "status": "no_speech_detected",
                "provider": "vosk:small-en-us",
                "media_reviewed": True,
                "transcript_text": "",
                "transcript_excerpt": "",
                "word_count": 0,
                "transcript_truncated": bool(max_seconds),
                "error": "",
            }

        return {
            "status": "transcribed",
            "provider": "vosk:small-en-us",
            "media_reviewed": True,
            "transcript_text": transcript_text,
            "transcript_excerpt": build_transcript_excerpt(transcript_text),
            "word_count": len(transcript_text.split()),
            "transcript_truncated": bool(max_seconds),
            "error": "",
        }
    except Exception as exc:
        logger.error(f"Media transcription failed for {filename or content_type}: {exc}")
        return {
            "status": "transcription_failed",
            "provider": "",
            "media_reviewed": False,
            "transcript_text": "",
            "transcript_excerpt": "",
            "word_count": 0,
            "transcript_truncated": bool(max_seconds),
            "error": str(exc)[:240],
        }
    finally:
        for path in [source_path, extracted_path]:
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass


async def review_episode_safety(
    show: Dict[str, Any],
    title: str,
    description: str,
    category: str,
    selected_rating: str = ALL_AGES_RATING,
    generation: Optional[Dict[str, Any]] = None,
    media_analysis: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    review_text = build_episode_review_text(show, title, description, category, generation=generation, media_analysis=media_analysis)
    heuristic_input = review_text
    if media_analysis and media_analysis.get("transcript_text"):
        heuristic_input = f"{review_text}\n\nFull transcript text:\n{media_analysis.get('transcript_text', '')}"
    fallback = heuristic_episode_safety_review(heuristic_input, selected_rating=selected_rating)
    if not EMERGENT_KEY:
        return normalize_episode_safety_result({}, fallback, selected_rating, media_analysis=media_analysis)

    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage

        schema = {
            "status": "clear|review|blocked",
            "risk_level": "low|medium|high",
            "summary": "string",
            "flags": ["string"],
            "recommended_age_gate": "all_ages|18+",
        }
        prompt = (
            "Review this podcast episode package for hateful, harmful, or unsafe listener-facing content.\n"
            "Use the metadata, AI-generated copy, and uploaded-media transcript excerpt when available.\n"
            "Focus on hate speech, self-harm encouragement, violent or illegal instructions, dangerous health advice, "
            "or explicit sexual content.\n"
            "Return JSON only.\n\n"
            f"Episode package:\n{review_text}\n\n"
            f"Return JSON matching this schema exactly:\n{json.dumps(schema, ensure_ascii=True)}"
        )
        chat = LlmChat(
            api_key=EMERGENT_KEY,
            session_id=f"episode-safety-{uuid.uuid4()}",
            system_message="You are a careful podcast safety reviewer. Be conservative, concise, and return JSON only.",
        ).with_model("openai", "gpt-5.2")
        response = await chat.send_message(UserMessage(text=prompt))
        raw = parse_json_payload(response)
        return normalize_episode_safety_result(raw, fallback, selected_rating, media_analysis=media_analysis)
    except Exception as exc:
        logger.error(f"Episode safety review error: {exc}")
        return normalize_episode_safety_result({}, fallback, selected_rating, media_analysis=media_analysis)


def agent2_split_sentences(text: str) -> List[str]:
    cleaned = re.sub(r"\s+", " ", text or "").strip()
    if not cleaned:
        return []
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", cleaned) if part.strip()]


def agent2_build_review_text(
    title: str,
    description: str,
    generation: Optional[Dict[str, Any]] = None,
    media_analysis: Optional[Dict[str, Any]] = None,
) -> str:
    parts = [f"Title: {title}", f"Description: {description}"]
    if generation:
        outline_lines = []
        for section in generation.get("outline", [])[:6]:
            beats = ", ".join(normalize_string_list(section.get("beats"), limit=5))
            outline_lines.append(f"{section.get('section_title', '')}: {beats}".strip(": "))
        parts.extend(
            [
                f"Promise: {generation.get('one_line_promise', '')}",
                f"Hook: {generation.get('hook', '')}",
                f"Intro: {generation.get('intro_script', '')}",
                f"Talking points: {', '.join(normalize_string_list(generation.get('talking_points'), limit=10))}",
                f"Outline: {' | '.join(outline_lines)}",
                f"Notes: {generation.get('show_notes_summary', '')}",
            ]
        )
    if media_analysis and media_analysis.get("transcript_text"):
        parts.append(f"Transcript: {media_analysis.get('transcript_text', '')}")
    elif media_analysis and media_analysis.get("transcript_excerpt"):
        parts.append(f"Transcript excerpt: {media_analysis.get('transcript_excerpt', '')}")
    return "\n".join(part for part in parts if str(part).strip()).strip()


def agent2_text_features(text: str, generation: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    words = re.findall(r"[a-zA-Z][a-zA-Z']+", text or "")
    lowered_words = [word.lower() for word in words]
    sentences = agent2_split_sentences(text)
    sentence_lengths = [len(re.findall(r"[a-zA-Z][a-zA-Z']+", sentence)) for sentence in sentences] or [0]
    avg_sentence_words = sum(sentence_lengths) / max(1, len(sentence_lengths))
    mean_sentence_words = avg_sentence_words
    sentence_length_stdev = (
        (sum((length - mean_sentence_words) ** 2 for length in sentence_lengths) / len(sentence_lengths)) ** 0.5
        if len(sentence_lengths) > 1
        else 0.0
    )
    repeated_words = len(lowered_words) - len(set(lowered_words))
    generic_markers = [
        "in today's fast-paced world",
        "unlock your potential",
        "game-changer",
        "leverage synergies",
        "delve into",
        "journey of discovery",
        "at the end of the day",
    ]
    speaker_turns = len(re.findall(r"(?im)^\s*(host|co-host|guest|speaker\s*\d+)\s*:", text or ""))
    question_count = sum(1 for sentence in sentences if "?" in sentence)
    outline_sections = len(generation.get("outline", []) if generation else [])
    talking_points = len(normalize_string_list(generation.get("talking_points"), limit=20) if generation else [])
    concrete_markers = len(re.findall(r"\b(example|story|case|because|step|framework|takeaway|try|today|specific)\b", (text or "").lower()))

    return {
        "word_count": len(words),
        "sentence_count": len(sentences),
        "avg_sentence_words": round(avg_sentence_words, 2),
        "sentence_length_stdev": round(sentence_length_stdev, 2),
        "question_rate": round(question_count / max(1, len(sentences)), 3),
        "generic_marker_count": sum((text or "").lower().count(marker) for marker in generic_markers),
        "repetition_rate": round(repeated_words / max(1, len(lowered_words)), 3),
        "speaker_turn_count": speaker_turns,
        "outline_section_count": outline_sections,
        "talking_point_count": talking_points,
        "concrete_marker_count": concrete_markers,
    }


def agent2_gan_inspired_discriminator(text: str, generation: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    features = agent2_text_features(text, generation=generation)
    score = 24.0
    if features["word_count"] < 120:
        score += 11
    if features["avg_sentence_words"] > 27:
        score += min(16, (features["avg_sentence_words"] - 27) * 1.8)
    if features["sentence_length_stdev"] < 5 and features["sentence_count"] >= 4:
        score += 8
    if features["question_rate"] < 0.05:
        score += 9
    score += min(18, features["generic_marker_count"] * 6)
    score += min(16, features["repetition_rate"] * 42)
    if features["concrete_marker_count"] >= 5:
        score -= 8
    if features["speaker_turn_count"] >= 8:
        score -= 8
    if features["outline_section_count"] >= 4:
        score -= 4
    if features["talking_point_count"] >= 4:
        score -= 4

    score = round(max(0, min(100, score)), 1)
    label = "low" if score < 35 else "medium" if score < 65 else "high"
    benchmark_similarity = round(max(0, min(100, 96 - score + min(10, features["concrete_marker_count"] * 0.8))), 1)
    return {
        "score": score,
        "label": label,
        "features": features,
        "benchmark_similarity": benchmark_similarity,
        "benchmark_profile": {
            "target_question_rate": 0.08,
            "min_outline_sections": 4,
            "min_concrete_markers": 5,
            "max_generic_markers": 0,
        },
        "model_note": "GAN-inspired adversarial discriminator; not a trained neural GAN model.",
    }


def agent2_rag_safety_review(text: str) -> Dict[str, Any]:
    matched = []
    lowered = text or ""
    for doc in AGENT2_RAG_SAFETY_KB:
        for pattern in doc["patterns"]:
            if re.search(pattern, lowered, flags=re.IGNORECASE):
                matched.append(
                    {
                        "id": doc["id"],
                        "severity": doc["severity"],
                        "policy": doc["text"],
                        "pattern": pattern,
                    }
                )
                break

    severe = [item for item in matched if item["severity"] == "high"]
    medium = [item for item in matched if item["severity"] == "medium"]
    status = "clear"
    risk_level = "low"
    if severe:
        status = "blocked"
        risk_level = "high"
    elif medium:
        status = "review"
        risk_level = "medium"
    elif matched:
        status = "clear"
        risk_level = "low"

    return {
        "status": status,
        "risk_level": risk_level,
        "matches": matched,
        "retrieved_policy_ids": [item["id"] for item in matched] or ["creator-quality"],
        "summary": (
            "RAG safety retrieval found no harmful-content policy matches."
            if not matched
            else f"RAG safety retrieval matched: {', '.join(item['id'] for item in matched[:4])}."
        ),
        "model_note": "RAG-style retrieval over local safety and quality policies.",
    }


def agent2_rlaif_self_feedback(gan_review: Dict[str, Any], rag_review: Dict[str, Any], generation: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    features = gan_review.get("features", {})
    reward = 88.0
    critique = []
    actions = []

    if gan_review.get("label") == "high":
        reward -= 24
        critique.append("The draft still has a high AI-detectability risk.")
        actions.append("Add sharper questions, concrete examples, and less uniform pacing.")
    elif gan_review.get("label") == "medium":
        reward -= 11
        critique.append("The draft may still sound somewhat generated.")
        actions.append("Add one more human example or tension point.")

    if rag_review.get("status") == "blocked":
        reward -= 50
        critique.append("RAG safety retrieval found high-risk harmful content.")
        actions.append("Remove the unsafe content before publishing.")
    elif rag_review.get("status") == "review":
        reward -= 18
        critique.append("RAG retrieval found material that needs review or refinement.")
        actions.append("Rewrite the flagged passages with safer, more precise language.")

    if features.get("generic_marker_count", 0) > 0:
        reward -= min(12, features["generic_marker_count"] * 4)
        critique.append("The draft uses generic AI-sounding phrases.")
        actions.append("Replace vague phrases with specific listener-facing claims.")
    if features.get("question_rate", 0) < 0.05:
        reward -= 5
        actions.append("Add at least one curiosity-led question.")
    if features.get("concrete_marker_count", 0) < 5:
        reward -= 8
        actions.append("Add a concrete example, story, or practical step.")
    if generation and len(normalize_string_list(generation.get("production_notes"), limit=10)) < 2:
        reward -= 4
        actions.append("Add production notes that help the creator perform the episode.")

    reward = round(max(0, min(100, reward)), 1)
    if not critique:
        critique.append("The episode package meets the current Agent 2 quality bar.")
    if not actions:
        actions.append("Preserve the current structure and avoid adding unnecessary complexity.")

    return {
        "reward_score": reward,
        "policy": AGENT2_RLAIF_POLICY,
        "critique": critique[:5],
        "improvement_actions": actions[:6],
        "method_note": "RLAIF-style self-feedback loop; stores reward/critique and can drive one revision, but does not train model weights.",
    }


def evaluate_agent2_quality(
    title: str,
    description: str,
    generation: Optional[Dict[str, Any]] = None,
    media_analysis: Optional[Dict[str, Any]] = None,
    source_kind: str = "episode",
) -> Dict[str, Any]:
    review_text = agent2_build_review_text(title, description, generation=generation, media_analysis=media_analysis)
    gan_review = agent2_gan_inspired_discriminator(review_text, generation=generation)
    rag_review = agent2_rag_safety_review(review_text)
    rlaif_feedback = agent2_rlaif_self_feedback(gan_review, rag_review, generation=generation)

    status = "pass"
    if rag_review["status"] == "blocked":
        status = "blocked"
    elif rag_review["status"] == "review" or gan_review["label"] == "high" or rlaif_feedback["reward_score"] < 72:
        status = "revise"

    return {
        "agent": "Agent 2 - Podcast Quality Reviewer",
        "version": AGENT2_VERSION,
        "source_kind": source_kind,
        "status": status,
        "quality_score": rlaif_feedback["reward_score"],
        "gan_discriminator": gan_review,
        "rag_safety": rag_review,
        "rlaif": rlaif_feedback,
        "summary": (
            f"Agent 2 quality score {rlaif_feedback['reward_score']}/100; "
            f"AI-risk {gan_review['label']} {gan_review['score']}; RAG safety {rag_review['status']}."
        ),
        "created_at": now_iso(),
    }


def merge_agent2_quality_into_moderation(moderation: Dict[str, Any], quality_agent: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(moderation or {})
    rag = (quality_agent or {}).get("rag_safety", {})
    if rag.get("status") not in {"review", "blocked"}:
        return merged

    existing_flags = normalize_string_list(merged.get("flags"), limit=10)
    rag_flags = normalize_string_list(rag.get("retrieved_policy_ids"), limit=10)
    merged["flags"] = list(dict.fromkeys(existing_flags + rag_flags))[:10]
    merged["summary"] = " ".join(
        part
        for part in [
            merged.get("summary", ""),
            f"Agent 2 RAG check: {rag.get('summary', '')}",
        ]
        if part
    )[:300]
    merged["provider"] = f"{merged.get('provider') or 'heuristic'}+agent2"
    if rag.get("status") == "blocked":
        merged["status"] = MODERATION_STATUS_BLOCKED
        merged["risk_level"] = "high"
        merged["recommended_age_gate"] = MATURE_RATING
    elif merged.get("status") == MODERATION_STATUS_CLEAR:
        merged["status"] = MODERATION_STATUS_REVIEW
        merged["risk_level"] = "medium"
    return merged


async def revise_ai_generation_with_agent2_feedback(
    brief: Dict[str, Any],
    show: Dict[str, Any],
    generation: Dict[str, Any],
    quality_agent: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    if not EMERGENT_KEY:
        return None
    if quality_agent.get("status") == "blocked":
        return None
    if quality_agent.get("quality_score", 0) >= 82 and quality_agent.get("gan_discriminator", {}).get("label") == "low":
        return None

    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage

        schema = {
            "episode_title": "string",
            "one_line_promise": "string",
            "hook": "string",
            "intro_script": "string",
            "outline": [{"section_title": "string", "purpose": "string", "beats": ["string"]}],
            "talking_points": ["string"],
            "guest_questions": ["string"],
            "production_notes": ["string"],
            "outro_cta": "string",
            "show_notes_summary": "string",
            "suggested_description": "string",
            "suggested_keywords": ["string"],
            "why_this_episode_fits": "string",
            "recommended_category": "string",
        }
        prompt = (
            "Agent 2 reviewed this AI podcast package and produced RLAIF-style self-feedback.\n"
            "Revise the package once using the feedback. Keep the creator's topic, audience, tone, and goal intact.\n"
            "Do not add unsafe claims. Do not make it clickbait. Make it more concrete, human-paced, and useful.\n\n"
            f"Show:\n{json.dumps({'title': show.get('title'), 'description': show.get('description'), 'category': show.get('category')}, ensure_ascii=True)}\n\n"
            f"Creator brief:\n{json.dumps(brief, ensure_ascii=True)}\n\n"
            f"Current package:\n{json.dumps(generation, ensure_ascii=True)}\n\n"
            f"Agent 2 review:\n{json.dumps(quality_agent, ensure_ascii=True)}\n\n"
            f"Return JSON matching this schema exactly:\n{json.dumps(schema, ensure_ascii=True)}"
        )
        chat = LlmChat(
            api_key=EMERGENT_KEY,
            session_id=f"agent2-rlaif-revision-{uuid.uuid4()}",
            system_message="You are Agent 2, Audioraq's quality-improvement reviewer. Return revised JSON only.",
        ).with_model("openai", "gpt-5.2")
        response = await chat.send_message(UserMessage(text=prompt))
        raw = parse_json_payload(response)
        if not isinstance(raw, dict):
            return None
        return normalize_ai_generation_response(raw, brief, show)
    except Exception as exc:
        logger.error(f"Agent 2 RLAIF revision error: {exc}")
        return None


def build_fallback_ai_generation(brief: Dict[str, Any], show: Dict[str, Any]) -> Dict[str, Any]:
    identity = brief.get("identity", {})
    episode_intent = brief.get("episodeIntent", {})
    content = brief.get("contentInput", {})
    tone_style = brief.get("toneStyle", {})
    growth = brief.get("growthOptimization", {})

    podcast_name = identity.get("podcastName") or show.get("title") or "Your Show"
    topic = content.get("topic") or "your main topic"
    audience = identity.get("targetAudience") or "listeners who care about this space"
    desired_outcome = episode_intent.get("desiredOutcome") or "leave with a useful next step"
    tone = tone_style.get("tone") or "professional"
    format_name = tone_style.get("format") or "solo"
    optimize_for = growth.get("optimizeFor") or "clarity"
    include_hook = bool(growth.get("includeHook", True))
    key_points = normalize_string_list(content.get("keyPoints"), limit=8)
    references = normalize_string_list(content.get("references"), limit=6)
    known_issues = (growth.get("knownIssues") or "").strip()

    hook = (
        f"What most people get wrong about {topic}, and what that means for {audience}."
        if include_hook
        else f"Today we're unpacking {topic} for {audience}."
    )
    outline = [
        {
            "section_title": "Cold Open",
            "purpose": "Frame the stakes quickly and make the listener care.",
            "beats": [hook, f"Set the lens for {audience}", f"Promise the outcome: {desired_outcome}"],
        },
        {
            "section_title": "Context",
            "purpose": "Give enough background for the episode to feel grounded and credible.",
            "beats": [
                f"Why {topic} matters in the {identity.get('niche') or show.get('category') or 'podcast'} niche",
                f"Where your audience usually gets stuck with {topic}",
            ],
        },
        {
            "section_title": "Main Breakdown",
            "purpose": "Deliver the highest-signal analysis in the chosen format.",
            "beats": key_points[:3] or [f"Break down the central tension in {topic}", "Share the clearest practical lesson"],
        },
        {
            "section_title": "Takeaways",
            "purpose": "End with memorable clarity and a concrete next step.",
            "beats": [
                f"Repeat the single biggest insight for {audience}",
                desired_outcome,
                f"Close in a {tone} voice that fits a {format_name} episode",
            ],
        },
    ]

    talking_points = key_points or [
        f"The core misconception around {topic}",
        f"What actually matters for {audience}",
        f"The practical next step listeners can take",
    ]
    if references:
        talking_points.append(f"Weave in supporting references from {', '.join(references[:2])}")
    if known_issues:
        talking_points.append(f"Address this known risk directly: {known_issues}")

    generation = {
        "episode_title": f"{topic}: A clearer roadmap for {audience}",
        "one_line_promise": f"{podcast_name} helps {audience} understand {topic} and {desired_outcome}.",
        "hook": hook,
        "intro_script": (
            f"Welcome back to {podcast_name}. I'm taking a {tone} look at {topic}, "
            f"with a focus on helping {audience} {desired_outcome}."
        ),
        "outline": outline,
        "talking_points": talking_points[:8],
        "guest_questions": [
            f"What do most people misunderstand about {topic}?",
            f"What changed your own thinking about {topic}?",
            f"What should listeners do next if they want a better result?",
        ] if format_name == "interview" else [],
        "production_notes": [
            f"Optimize pacing for {optimize_for}",
            f"Keep the tone {tone} and the structure {format_name}",
            "Use one example or story beat in every major section",
        ],
        "outro_cta": f"Invite listeners to reflect on {topic} and come back for the next episode.",
        "show_notes_summary": (
            f"In this episode of {podcast_name}, we explore {topic}, unpack the major tension around it, "
            f"and leave listeners with a clearer path forward."
        ),
        "suggested_description": "",
        "suggested_keywords": normalize_string_list(
            [
                topic,
                identity.get("niche") or show.get("category") or DEFAULT_SHOW_CATEGORY,
                episode_intent.get("episodeGoal") or "podcast",
                optimize_for,
                tone,
            ] + key_points,
            limit=10,
        ),
        "why_this_episode_fits": (
            f"This episode is designed for {audience}, stays aligned with a {tone} voice, "
            f"and favors {optimize_for} over low-signal filler."
        ),
        "recommended_category": (show.get("category") or DEFAULT_SHOW_CATEGORY).lower(),
    }
    generation["suggested_description"] = build_ai_publish_description(generation)
    return generation


def normalize_ai_generation_response(raw: Dict[str, Any], brief: Dict[str, Any], show: Dict[str, Any]) -> Dict[str, Any]:
    fallback = build_fallback_ai_generation(brief, show)
    generation = dict(fallback)

    for field in [
        "episode_title",
        "one_line_promise",
        "hook",
        "intro_script",
        "outro_cta",
        "show_notes_summary",
        "suggested_description",
        "why_this_episode_fits",
    ]:
        value = str(raw.get(field, "")).strip()
        if value:
            generation[field] = value

    outline = normalize_outline_items(raw.get("outline"))
    if outline:
        generation["outline"] = outline

    for list_field in ["talking_points", "guest_questions", "production_notes", "suggested_keywords"]:
        values = normalize_string_list(raw.get(list_field), limit=10)
        if values:
            generation[list_field] = values

    recommended_category = str(raw.get("recommended_category") or "").strip().lower()
    if recommended_category:
        generation["recommended_category"] = recommended_category

    if not generation.get("suggested_description"):
        generation["suggested_description"] = build_ai_publish_description(generation)

    return generation


async def generate_ai_podcast_package(brief: Dict[str, Any], show: Dict[str, Any]) -> Dict[str, Any]:
    fallback = build_fallback_ai_generation(brief, show)
    if not EMERGENT_KEY:
        return fallback

    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage

        show_context = {
            "show_title": show.get("title", ""),
            "show_description": show.get("description", ""),
            "show_category": show.get("category", DEFAULT_SHOW_CATEGORY),
            "podcaster_name": show.get("podcaster_name", ""),
        }

        system_message = (
            "You are Audioraq's AI podcast creation team. Think like a strategist, story editor, "
            "and growth producer for high-signal long-form podcasts. Build episodes that feel intentional, "
            "credible, and aligned to the creator's audience. Avoid generic social-media gimmicks, empty hype, "
            "and short-form engagement hacks. Return JSON only."
        )
        schema = {
            "episode_title": "string",
            "one_line_promise": "string",
            "hook": "string",
            "intro_script": "string",
            "outline": [
                {
                    "section_title": "string",
                    "purpose": "string",
                    "beats": ["string"],
                }
            ],
            "talking_points": ["string"],
            "guest_questions": ["string"],
            "production_notes": ["string"],
            "outro_cta": "string",
            "show_notes_summary": "string",
            "suggested_description": "string",
            "suggested_keywords": ["string"],
            "why_this_episode_fits": "string",
            "recommended_category": "string",
        }
        prompt = (
            "Use this show context and creator brief to draft a strong podcast episode package.\n\n"
            f"Show context:\n{json.dumps(show_context, ensure_ascii=True)}\n\n"
            f"Creator brief:\n{json.dumps(brief, ensure_ascii=True)}\n\n"
            "Rules:\n"
            "- Keep the work podcast-first and long-form.\n"
            "- The hook should be sharp, but not clickbait.\n"
            "- Align the outline to the requested tone, format, audience, and desired outcome.\n"
            "- If the format is not interview, guest_questions can be an empty list.\n"
            "- Keep suggested keywords concise and usable for search/discovery.\n"
            "- recommended_category should be a single lowercase category.\n\n"
            f"Return JSON matching this schema exactly:\n{json.dumps(schema, ensure_ascii=True)}"
        )

        chat = LlmChat(
            api_key=EMERGENT_KEY,
            session_id=f"ai-podcast-{uuid.uuid4()}",
            system_message=system_message,
        ).with_model("openai", "gpt-5.2")
        response = await chat.send_message(UserMessage(text=prompt))
        raw = parse_json_payload(response)
        if not isinstance(raw, dict):
            return fallback
        return normalize_ai_generation_response(raw, brief, show)
    except Exception as exc:
        logger.error(f"AI podcast generation error: {exc}")
        return fallback


async def extract_keywords(text):
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        import json

        chat = LlmChat(
            api_key=EMERGENT_KEY,
            session_id=f"keywords-{uuid.uuid4()}",
            system_message='You are a keyword extraction expert. Extract 5-10 relevant keywords/topics from the given text. Return ONLY a JSON array of lowercase strings, no other text. Example: ["technology", "science", "ai"]',
        ).with_model("openai", "gpt-5.2")
        msg = UserMessage(text=f"Extract keywords from this text: {text}")
        response = await chat.send_message(msg)
        cleaned = response.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
            cleaned = cleaned.rsplit("```", 1)[0]
        keywords = json.loads(cleaned.strip())
        if isinstance(keywords, list):
            return [k.lower().strip() for k in keywords if isinstance(k, str)]
        return []
    except Exception as e:
        logger.error(f"Keyword extraction error: {e}")
        words = text.lower().split()
        stop_words = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been", "being", "have", "has", "had",
            "do", "does", "did", "will", "would", "could", "should", "may", "might", "shall", "can",
            "need", "dare", "ought", "used", "to", "of", "in", "for", "on", "with", "at", "by", "from",
            "as", "into", "through", "during", "before", "after", "above", "below", "between", "out",
            "off", "over", "under", "again", "further", "then", "once", "here", "there", "when", "where",
            "why", "how", "all", "both", "each", "few", "more", "most", "other", "some", "such", "no",
            "nor", "not", "only", "own", "same", "so", "than", "too", "very", "just", "because", "but",
            "and", "or", "if", "while", "about", "up", "it", "its", "i", "my", "we", "our", "you", "your",
            "he", "she", "they", "them", "this", "that", "these", "those", "what", "which", "who", "whom",
        }
        keywords = list(
            set([w.strip(".,!?;:\"'()[]{}") for w in words if len(w) > 3 and w not in stop_words])
        )
        return keywords[:10]


async def get_ai_recommendations(user_interests, viewed_keywords, all_podcasts):
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        import json

        podcast_summaries = []
        for p in all_podcasts[:50]:
            podcast_summaries.append(
                {
                    "id": p["id"],
                    "title": p["title"],
                    "show_title": p.get("show_title", ""),
                    "keywords": p.get("keywords", []),
                    "category": p.get("category", ""),
                }
            )
        chat = LlmChat(
            api_key=EMERGENT_KEY,
            session_id=f"recommend-{uuid.uuid4()}",
            system_message="You are a podcast recommendation engine. Given user interests and available podcasts, rank and return the most relevant podcast IDs. Return ONLY a JSON array of podcast ID strings, ordered by relevance. Max 20 IDs.",
        ).with_model("openai", "gpt-5.2")
        prompt = f"""User interests: {json.dumps(user_interests)}
Previously viewed podcast keywords: {json.dumps(viewed_keywords)}
Available podcasts: {json.dumps(podcast_summaries)}

Return the most relevant podcast IDs as a JSON array."""
        msg = UserMessage(text=prompt)
        response = await chat.send_message(msg)
        cleaned = response.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
            cleaned = cleaned.rsplit("```", 1)[0]
        ids = json.loads(cleaned.strip())
        if isinstance(ids, list):
            return [str(i) for i in ids]
        return []
    except Exception as e:
        logger.error(f"AI recommendation error: {e}")
        return []


def build_recommendation_reason(episode, user_interests, viewed_keywords, method):
    keywords = set(episode.get("keywords", []))
    category = episode.get("category", "")
    interest_matches = [term for term in user_interests if term == category or term in keywords]
    viewed_matches = [term for term in viewed_keywords if term in keywords]
    if episode.get("is_following_show"):
        return "New from a show you follow"
    if interest_matches:
        return f"Because you picked {', '.join(interest_matches[:2])}"
    if viewed_matches:
        return f"Similar to episodes you listened to about {', '.join(viewed_matches[:2])}"
    if episode.get("show_title"):
        if method == "ai":
            return f"Recommended from {episode['show_title']}"
        if method == "keyword":
            return f"Matched from {episode['show_title']}"
    return "Trending on Audioraq right now" if method == "popular" else "Picked for your home feed"


async def store_upload(upload: UploadFile, path_prefix: str, default_content_type: str):
    ext = upload.filename.split(".")[-1] if upload.filename and "." in upload.filename else "bin"
    object_path = f"{APP_NAME}/{path_prefix}/{uuid.uuid4()}.{ext}"
    data = await upload.read()
    put_object(object_path, data, upload.content_type or default_content_type)
    return object_path, data


async def get_followed_show_ids(user) -> Set[str]:
    if not user:
        return set()
    rows = await db.followed_shows.find({"user_id": user_id_str(user)}).to_list(MAX_LIBRARY_ITEMS)
    return {row["show_id"] for row in rows if row.get("show_id")}


async def get_saved_podcast_ids(user) -> Set[str]:
    if not user:
        return set()
    rows = await db.saved_podcasts.find({"user_id": user_id_str(user)}).to_list(MAX_LIBRARY_ITEMS)
    return {row["podcast_id"] for row in rows if row.get("podcast_id")}


async def get_hidden_podcast_ids(user) -> Set[str]:
    if not user:
        return set()
    rows = await db.hidden_podcasts.find({"user_id": user_id_str(user)}).to_list(MAX_LIBRARY_ITEMS)
    return {row["podcast_id"] for row in rows if row.get("podcast_id")}


async def get_liked_podcast_ids(user) -> Set[str]:
    if not user:
        return set()
    rows = await db.podcast_likes.find({"user_id": user_id_str(user)}).to_list(MAX_LIBRARY_ITEMS)
    return {row["podcast_id"] for row in rows if row.get("podcast_id")}


async def get_user_rating_map(user, podcast_ids: List[str]) -> Dict[str, int]:
    if not user:
        return {}
    unique_ids = list({podcast_id for podcast_id in podcast_ids if podcast_id})
    if not unique_ids:
        return {}
    rows = await db.podcast_ratings.find(
        {"user_id": user_id_str(user), "podcast_id": {"$in": unique_ids}}
    ).to_list(len(unique_ids))
    return {row["podcast_id"]: int(row.get("rating", 0) or 0) for row in rows if row.get("podcast_id")}


async def get_engagement_summary_map(podcast_ids: List[str]) -> Dict[str, Dict[str, Any]]:
    unique_ids = list({podcast_id for podcast_id in podcast_ids if podcast_id})
    if not unique_ids:
        return {}

    like_rows = await db.podcast_likes.aggregate(
        [
            {"$match": {"podcast_id": {"$in": unique_ids}}},
            {"$group": {"_id": "$podcast_id", "like_count": {"$sum": 1}}},
        ]
    ).to_list(len(unique_ids))
    rating_rows = await db.podcast_ratings.aggregate(
        [
            {"$match": {"podcast_id": {"$in": unique_ids}}},
            {
                "$group": {
                    "_id": "$podcast_id",
                    "rating_count": {"$sum": 1},
                    "rating_average": {"$avg": "$rating"},
                }
            },
        ]
    ).to_list(len(unique_ids))

    summary_map: Dict[str, Dict[str, Any]] = {podcast_id: {} for podcast_id in unique_ids}
    for row in like_rows:
        summary_map.setdefault(row["_id"], {})["like_count"] = int(row.get("like_count", 0) or 0)
    for row in rating_rows:
        summary_map.setdefault(row["_id"], {}).update(
            {
                "rating_count": int(row.get("rating_count", 0) or 0),
                "rating_average": round(float(row.get("rating_average", 0) or 0), 1),
            }
        )
    return summary_map


async def refresh_episode_engagement_fields(podcast_id: str) -> Dict[str, Any]:
    like_count = await db.podcast_likes.count_documents({"podcast_id": podcast_id})
    rating_rows = await db.podcast_ratings.aggregate(
        [
            {"$match": {"podcast_id": podcast_id}},
            {
                "$group": {
                    "_id": "$podcast_id",
                    "rating_count": {"$sum": 1},
                    "rating_average": {"$avg": "$rating"},
                }
            },
        ]
    ).to_list(1)
    rating_row = rating_rows[0] if rating_rows else {}
    engagement = {
        "like_count": int(like_count or 0),
        "rating_count": int(rating_row.get("rating_count", 0) or 0),
        "rating_average": round(float(rating_row.get("rating_average", 0) or 0), 1),
    }
    await db.podcasts.update_one({"id": podcast_id}, {"$set": engagement})
    return engagement


async def get_playback_progress_map(user, podcast_ids: List[str]):
    if not user:
        return {}
    unique_ids = list({podcast_id for podcast_id in podcast_ids if podcast_id})
    if not unique_ids:
        return {}
    progress_rows = await db.playback_progress.find(
        {"user_id": user_id_str(user), "podcast_id": {"$in": unique_ids}}
    ).to_list(len(unique_ids))
    return {row["podcast_id"]: clean_doc(row) for row in progress_rows if row.get("podcast_id")}


def build_show_cadence_label(show: Dict) -> str:
    latest_episode_at = parse_iso_datetime(show.get("latest_episode_at"))
    if latest_episode_at is None:
        return "New show"
    age_days = max(0, (datetime.now(timezone.utc) - latest_episode_at.astimezone(timezone.utc)).days)
    if age_days <= 7:
        return "Active this week"
    if age_days <= 30:
        return "Updated this month"
    return "Catalog ready"


def build_show_quality_signals(show: Dict) -> List[str]:
    signals = []
    if show.get("episode_count", 0) >= 12:
        signals.append("Deep catalog")
    elif show.get("episode_count", 0) >= 3:
        signals.append("Multi-episode show")
    if show.get("thumbnail_path") or show.get("external_thumbnail_url"):
        signals.append("Branded artwork")
    if show.get("follower_count", 0) >= 10:
        signals.append("Audience building")
    cadence_label = build_show_cadence_label(show)
    if cadence_label not in {"New show", "Catalog ready"}:
        signals.append(cadence_label)
    return signals[:3]


def build_episode_quality_signals(episode: Dict, show: Optional[Dict]) -> List[str]:
    signals = []
    if show and show.get("episode_count", 0) >= 3:
        signals.append(f"{show['episode_count']} episodes in this show")
    if episode.get("season_number") and episode.get("episode_number"):
        signals.append(f"S{episode['season_number']} E{episode['episode_number']}")
    created_at = parse_iso_datetime(episode.get("created_at"))
    if created_at is not None:
        age_days = max(0, (datetime.now(timezone.utc) - created_at.astimezone(timezone.utc)).days)
        if age_days <= 7:
            signals.append("New release")
        elif age_days <= 30:
            signals.append("Published recently")
    if show and show.get("is_following"):
        signals.append("From a show you follow")
    if episode.get("progress_percent") and not episode.get("is_completed"):
        signals.append(f"Resume at {int(episode['progress_percent'])}%")
    if float(episode.get("rating_average", 0) or 0) >= 4.5 and int(episode.get("rating_count", 0) or 0) >= 3:
        signals.append("Highly rated")
    if int(episode.get("play_count", 0) or 0) >= 25:
        signals.append("Popular listen")
    if float(episode.get("quality_score", 0) or 0) >= 82:
        signals.append("Agent 2 quality checked")
    elif episode.get("quality_status") == "revise":
        signals.append("Agent 2 suggests improvements")
    if normalize_content_rating(episode.get("audience_rating")) == MATURE_RATING:
        signals.append("18+ audience")
    if episode.get("publication_status") == PUBLICATION_STATUS_DRAFT:
        signals.append("Draft episode")
    return signals[:3]


async def enrich_shows(shows: List[Dict], current_user=None):
    if not shows:
        return []
    show_ids = [show["id"] for show in shows]
    stats_rows = await db.podcasts.aggregate(
        [
            {"$match": {"show_id": {"$in": show_ids}, "is_deleted": False}},
            {
                "$group": {
                    "_id": "$show_id",
                    "episode_count": {"$sum": 1},
                    "total_play_count": {"$sum": {"$ifNull": ["$play_count", 0]}},
                    "latest_episode_at": {"$max": "$created_at"},
                }
            },
        ]
    ).to_list(len(show_ids))
    stats_map = {row["_id"]: row for row in stats_rows}
    follower_rows = await db.followed_shows.aggregate(
        [
            {"$match": {"show_id": {"$in": show_ids}}},
            {"$group": {"_id": "$show_id", "follower_count": {"$sum": 1}}},
        ]
    ).to_list(len(show_ids))
    follower_map = {row["_id"]: row.get("follower_count", 0) for row in follower_rows}
    followed_show_ids = await get_followed_show_ids(current_user)
    enriched = []
    for show in shows:
        cleaned = clean_doc(show)
        stats = stats_map.get(cleaned["id"], {})
        cleaned["episode_count"] = stats.get("episode_count", 0)
        cleaned["total_play_count"] = stats.get("total_play_count", 0)
        cleaned["latest_episode_at"] = stats.get("latest_episode_at")
        cleaned["follower_count"] = follower_map.get(cleaned["id"], 0)
        cleaned["is_following"] = cleaned["id"] in followed_show_ids
        cleaned["cadence_label"] = build_show_cadence_label(cleaned)
        cleaned["quality_signals"] = build_show_quality_signals(cleaned)
        enriched.append(cleaned)
    return enriched


async def fetch_show_lookup(show_ids: List[str], current_user=None):
    unique_ids = list({show_id for show_id in show_ids if show_id})
    if not unique_ids:
        return {}
    shows = await db.shows.find({"id": {"$in": unique_ids}, "is_deleted": False}).to_list(len(unique_ids))
    enriched = await enrich_shows(shows, current_user=current_user)
    return {show["id"]: show for show in enriched}


async def enrich_episodes(episodes: List[Dict], current_user=None):
    if not episodes:
        return []
    show_lookup = await fetch_show_lookup([episode.get("show_id") for episode in episodes], current_user=current_user)
    saved_podcast_ids = await get_saved_podcast_ids(current_user)
    hidden_podcast_ids = await get_hidden_podcast_ids(current_user)
    liked_podcast_ids = await get_liked_podcast_ids(current_user)
    user_rating_map = await get_user_rating_map(current_user, [episode.get("id") for episode in episodes])
    engagement_summary_map = await get_engagement_summary_map([episode.get("id") for episode in episodes])
    progress_map = await get_playback_progress_map(current_user, [episode.get("id") for episode in episodes])
    enriched = []
    for episode in episodes:
        cleaned = clean_doc(episode)
        show = show_lookup.get(cleaned.get("show_id"))
        progress_doc = progress_map.get(cleaned.get("id"), {})
        engagement = engagement_summary_map.get(cleaned.get("id"), {})
        cleaned["is_saved"] = cleaned["id"] in saved_podcast_ids
        cleaned["is_hidden"] = cleaned["id"] in hidden_podcast_ids
        cleaned["is_liked"] = cleaned["id"] in liked_podcast_ids
        cleaned["viewer_rating"] = user_rating_map.get(cleaned["id"], 0)
        cleaned["is_following_show"] = bool(show and show.get("is_following"))
        cleaned["progress_seconds"] = float(progress_doc.get("progress_seconds", 0) or 0)
        cleaned["duration_seconds"] = float(progress_doc.get("duration_seconds", 0) or 0)
        if cleaned["duration_seconds"] > 0:
            cleaned["progress_percent"] = min(100, round((cleaned["progress_seconds"] / cleaned["duration_seconds"]) * 100, 1))
        else:
            cleaned["progress_percent"] = 0
        cleaned["resume_position_seconds"] = cleaned["progress_seconds"]
        cleaned["is_completed"] = bool(progress_doc.get("is_completed"))
        cleaned["last_played_at"] = progress_doc.get("last_played_at")
        cleaned["audience_rating"] = normalize_content_rating(cleaned.get("audience_rating"))
        cleaned["publication_status"] = cleaned.get("publication_status", PUBLICATION_STATUS_PUBLISHED)
        cleaned["moderation_status"] = cleaned.get("moderation_status", MODERATION_STATUS_CLEAR)
        cleaned["moderation"] = cleaned.get("moderation", {}) or {}
        cleaned["moderation_summary"] = cleaned["moderation"].get("summary", "")
        cleaned["media_reviewed"] = bool(cleaned["moderation"].get("media_reviewed"))
        cleaned["media_review_status"] = cleaned["moderation"].get("media_review_status", "")
        cleaned["media_review_provider"] = cleaned["moderation"].get("media_review_provider", "")
        cleaned["media_transcript_excerpt"] = cleaned["moderation"].get("media_transcript_excerpt", "")
        cleaned["quality_agent"] = cleaned.get("quality_agent", {}) or {}
        cleaned["quality_status"] = cleaned.get("quality_status") or cleaned["quality_agent"].get("status", "")
        cleaned["quality_score"] = cleaned.get("quality_score") or cleaned["quality_agent"].get("quality_score", 0)
        cleaned["quality_summary"] = cleaned["quality_agent"].get("summary", "")
        cleaned["is_playable"] = bool(cleaned.get("is_playable", bool(cleaned.get("media_path") or cleaned.get("external_media_url"))))
        cleaned["like_count"] = int(engagement.get("like_count", cleaned.get("like_count", 0)) or 0)
        cleaned["rating_count"] = int(engagement.get("rating_count", cleaned.get("rating_count", 0)) or 0)
        cleaned["rating_average"] = round(float(engagement.get("rating_average", cleaned.get("rating_average", 0)) or 0), 1)
        cleaned["view_count"] = int(cleaned.get("play_count", 0) or 0)
        cleaned["is_age_restricted"] = cleaned["audience_rating"] == MATURE_RATING
        cleaned["viewer_can_stream"] = can_access_episode(current_user, cleaned) and cleaned["is_playable"]
        if show:
            cleaned["show"] = {
                "id": show["id"],
                "title": show.get("title", ""),
                "description": show.get("description", ""),
                "category": show.get("category", DEFAULT_SHOW_CATEGORY),
                "thumbnail_path": show.get("thumbnail_path", ""),
                "podcaster_name": show.get("podcaster_name", cleaned.get("podcaster_name", "")),
                "episode_count": show.get("episode_count", 0),
                "total_play_count": show.get("total_play_count", 0),
                "follower_count": show.get("follower_count", 0),
                "is_following": show.get("is_following", False),
                "quality_signals": show.get("quality_signals", []),
            }
            cleaned["show_title"] = cleaned.get("show_title") or show.get("title", "")
            cleaned["show_description"] = show.get("description", "")
            cleaned["show_thumbnail_path"] = show.get("thumbnail_path", "")
            if not cleaned.get("thumbnail_path") and show.get("thumbnail_path"):
                cleaned["thumbnail_path"] = show["thumbnail_path"]
        else:
            cleaned["show"] = None
            cleaned.setdefault("show_title", "")
            cleaned.setdefault("show_description", "")
            cleaned.setdefault("show_thumbnail_path", "")
        if cleaned["progress_percent"] and not cleaned["is_completed"]:
            cleaned.setdefault("recommendation_reason", f"Resume at {int(cleaned['progress_percent'])}%")
        cleaned["quality_signals"] = build_episode_quality_signals(cleaned, show)
        enriched.append(cleaned)
    return enriched


async def fetch_primary_show_for_user(user):
    if user.get("role") != "podcaster":
        return None
    podcaster_id = user_id_str(user)
    show = None
    if user.get("primary_show_id"):
        show = await db.shows.find_one(
            {"id": user["primary_show_id"], "podcaster_id": podcaster_id, "is_deleted": False}
        )
    if show is None:
        show = await db.shows.find_one({"podcaster_id": podcaster_id, "is_primary": True, "is_deleted": False})
    if show is None:
        show = await db.shows.find_one({"podcaster_id": podcaster_id, "is_deleted": False})
    return clean_doc(show)


async def ensure_primary_show_for_user(user, title_override: Optional[str] = None):
    if user.get("role") != "podcaster":
        return None

    podcaster_id = user_id_str(user)
    existing = await fetch_primary_show_for_user(user)
    if existing:
        updates = {}
        if user.get("primary_show_id") != existing["id"]:
            updates["primary_show_id"] = existing["id"]
        if user.get("show_title") != existing.get("title"):
            updates["show_title"] = existing.get("title", "")
        if updates:
            await db.users.update_one({"_id": user_object_id(user)}, {"$set": updates})
        return existing

    title = (title_override or user.get("show_title") or "").strip() or build_default_show_title(user.get("name", ""))
    description = user.get("podcast_description", "")
    keywords = user.get("podcast_keywords", []) or await extract_keywords(f"{title} {description}")
    show_doc = {
        "id": str(uuid.uuid4()),
        "title": title,
        "description": description,
        "category": DEFAULT_SHOW_CATEGORY,
        "keywords": keywords,
        "thumbnail_path": "",
        "podcaster_id": podcaster_id,
        "podcaster_name": user.get("name", ""),
        "is_primary": True,
        "is_deleted": False,
        "created_at": user.get("created_at", now_iso()),
        "updated_at": now_iso(),
    }
    await db.shows.insert_one(show_doc)
    await db.users.update_one(
        {"_id": user_object_id(user)},
        {"$set": {"primary_show_id": show_doc["id"], "show_title": show_doc["title"]}},
    )
    return clean_doc(show_doc)


async def migrate_existing_shows():
    podcasters = await db.users.find({"role": "podcaster"}).to_list(None)
    for user in podcasters:
        primary_show = await ensure_primary_show_for_user(user)
        if primary_show is None:
            continue
        await db.podcasts.update_many(
            {"podcaster_id": str(user["_id"]), "show_id": {"$exists": False}},
            {
                "$set": {
                    "show_id": primary_show["id"],
                    "show_title": primary_show["title"],
                }
            },
        )
        await db.podcasts.update_many(
            {"podcaster_id": str(user["_id"]), "show_title": {"$in": [None, ""]}},
            {"$set": {"show_title": primary_show["title"]}},
        )


async def build_user_response(user_doc):
    primary_show = await fetch_primary_show_for_user(user_doc)
    age = normalize_age_value(user_doc.get("age"))
    auth_providers = sorted(
        [
            provider
            for provider, details in (user_doc.get("auth_providers") or {}).items()
            if isinstance(details, dict) and details.get("sub")
        ]
    )
    return {
        "id": user_id_str(user_doc),
        "email": user_doc["email"],
        "name": user_doc["name"],
        "role": user_doc["role"],
        "phone": user_doc.get("phone", ""),
        "age": age,
        "is_underage": age is not None and age < LEGAL_VIEWER_AGE,
        "interests": user_doc.get("interests", []),
        "podcast_description": user_doc.get("podcast_description", ""),
        "podcast_keywords": user_doc.get("podcast_keywords", []),
        "show_title": user_doc.get("show_title", ""),
        "avatar_url": user_doc.get("avatar_url", ""),
        "auth_providers": auth_providers,
        "primary_show": primary_show,
    }


def xml_first_text(element, paths, namespaces=None, attribute=None):
    namespaces = namespaces or {}
    for path in paths:
        node = element.find(path, namespaces)
        if node is None:
            continue
        if attribute:
            value = node.attrib.get(attribute)
            if value:
                return value.strip()
        elif node.text:
            return node.text.strip()
    return ""


async def fetch_creator_analytics(user, show_id: Optional[str] = None):
    show_query = {"podcaster_id": user["_id"], "is_deleted": False}
    if show_id:
        show_query["id"] = show_id
    shows = await db.shows.find(show_query).to_list(50)
    if not shows:
        return {
            "overview": {
                "show_count": 0,
                "episode_count": 0,
                "total_plays": 0,
                "saved_count": 0,
                "avg_completion_rate": 0,
                "listener_count": 0,
            },
            "shows": [],
            "episodes": [],
            "listener_interests": [],
        }

    show_ids = [show["id"] for show in shows]
    episode_query = {"show_id": {"$in": show_ids}, "is_deleted": False}
    episodes = await db.podcasts.find(episode_query).sort("created_at", -1).to_list(500)
    episode_ids = [episode["id"] for episode in episodes]

    saved_rows = []
    progress_rows = []
    if episode_ids:
        saved_rows = await db.saved_podcasts.aggregate(
            [
                {"$match": {"podcast_id": {"$in": episode_ids}}},
                {"$group": {"_id": "$podcast_id", "saved_count": {"$sum": 1}}},
            ]
        ).to_list(len(episode_ids))
        progress_rows = await db.playback_progress.find({"podcast_id": {"$in": episode_ids}}).to_list(MAX_LIBRARY_ITEMS)

    saved_map = {row["_id"]: row.get("saved_count", 0) for row in saved_rows}
    progress_map = {}
    listener_ids = set()
    for row in progress_rows:
        progress_map.setdefault(row["podcast_id"], []).append(row)
        if row.get("user_id"):
            listener_ids.add(row["user_id"])

    listener_docs = []
    if listener_ids:
        object_ids = []
        for raw_id in listener_ids:
            try:
                object_ids.append(ObjectId(raw_id))
            except Exception:
                continue
        if object_ids:
            listener_docs = await db.users.find({"_id": {"$in": object_ids}}, {"interests": 1}).to_list(len(object_ids))

    interest_counts = {}
    for listener in listener_docs:
        for interest in listener.get("interests", []):
            interest_counts[interest] = interest_counts.get(interest, 0) + 1

    episode_analytics = []
    for episode in episodes:
        listens = progress_map.get(episode["id"], [])
        started_count = len(listens)
        completed_count = len([listen for listen in listens if listen.get("is_completed")])
        avg_completion = 0
        if listens:
            avg_completion = round(
                sum(float(listen.get("progress_percent", 0) or 0) for listen in listens) / len(listens),
                1,
            )
        episode_analytics.append(
            {
                "id": episode["id"],
                "title": episode["title"],
                "show_id": episode.get("show_id", ""),
                "show_title": episode.get("show_title", ""),
                "play_count": episode.get("play_count", 0),
                "saved_count": saved_map.get(episode["id"], 0),
                "started_count": started_count,
                "completed_count": completed_count,
                "completion_rate": round((completed_count / started_count) * 100, 1) if started_count else 0,
                "avg_completion_percent": avg_completion,
                "created_at": episode.get("created_at"),
            }
        )

    show_analytics = []
    for show in shows:
        show_episode_rows = [episode for episode in episode_analytics if episode["show_id"] == show["id"]]
        total_plays = sum(episode["play_count"] for episode in show_episode_rows)
        total_saves = sum(episode["saved_count"] for episode in show_episode_rows)
        avg_completion = round(
            sum(episode["avg_completion_percent"] for episode in show_episode_rows) / len(show_episode_rows),
            1,
        ) if show_episode_rows else 0
        show_analytics.append(
            {
                "id": show["id"],
                "title": show["title"],
                "episode_count": len(show_episode_rows),
                "total_plays": total_plays,
                "saved_count": total_saves,
                "avg_completion_percent": avg_completion,
                "cadence_label": build_show_cadence_label(clean_doc(show)),
            }
        )

    total_plays = sum(episode["play_count"] for episode in episode_analytics)
    total_saves = sum(episode["saved_count"] for episode in episode_analytics)
    avg_completion_rate = round(
        sum(episode["completion_rate"] for episode in episode_analytics) / len(episode_analytics),
        1,
    ) if episode_analytics else 0

    listener_interest_list = [
        {"interest": interest, "count": count}
        for interest, count in sorted(interest_counts.items(), key=lambda item: item[1], reverse=True)[:6]
    ]

    return {
        "overview": {
            "show_count": len(shows),
            "episode_count": len(episode_analytics),
            "total_plays": total_plays,
            "saved_count": total_saves,
            "avg_completion_rate": avg_completion_rate,
            "listener_count": len(listener_ids),
        },
        "shows": show_analytics,
        "episodes": episode_analytics[:12],
        "listener_interests": listener_interest_list,
    }


class RegisterRequest(BaseModel):
    email: str
    password: str
    name: str
    role: str
    phone: Optional[str] = ""
    age: Optional[int] = None
    interests: Optional[List[str]] = []
    podcast_description: Optional[str] = ""
    show_title: Optional[str] = ""


class LoginRequest(BaseModel):
    email: str
    password: str


class CompleteSocialSignupRequest(BaseModel):
    name: Optional[str] = ""
    role: str
    phone: Optional[str] = ""
    age: Optional[int] = None
    interests: Optional[List[str]] = []
    podcast_description: Optional[str] = ""
    show_title: Optional[str] = ""


class UpdateInterestsRequest(BaseModel):
    interests: List[str]


class UpdatePodcastDescriptionRequest(BaseModel):
    podcast_description: str


class UpdatePlaybackProgressRequest(BaseModel):
    progress_seconds: float = 0
    duration_seconds: float = 0
    event_type: Optional[str] = "progress"


class UpdatePodcastRatingRequest(BaseModel):
    rating: int


class RssImportRequest(BaseModel):
    feed_url: str
    show_id: Optional[str] = ""
    import_limit: Optional[int] = 10


class PodcastIdentityInput(BaseModel):
    podcastName: str
    niche: str
    targetAudience: str


class EpisodeIntentInput(BaseModel):
    episodeGoal: Literal["educate", "entertain", "storytelling", "interview"]
    desiredOutcome: str


class ContentInput(BaseModel):
    topic: str
    keyPoints: List[str]
    references: Optional[List[str]] = []


class ToneStyleInput(BaseModel):
    tone: Literal["casual", "professional", "energetic", "storytelling"]
    format: Literal["solo", "interview", "narrative"]
    lengthPreference: Literal["short", "medium", "long"]


class GrowthOptimizationInput(BaseModel):
    optimizeFor: Literal["retention", "virality", "clarity"]
    includeHook: bool = True
    knownIssues: Optional[str] = ""


class AIPodcastIntake(BaseModel):
    identity: PodcastIdentityInput
    episodeIntent: EpisodeIntentInput
    contentInput: ContentInput
    toneStyle: ToneStyleInput
    growthOptimization: GrowthOptimizationInput


class GenerateAIPodcastDraftRequest(BaseModel):
    show_id: str
    intake: AIPodcastIntake


app = FastAPI()
api_router = APIRouter(prefix="/api")


@app.on_event("startup")
async def startup():
    await db.users.create_index("email", unique=True)
    await db.users.create_index("auth_providers.google.sub", unique=True, sparse=True)
    await db.users.create_index("auth_providers.apple.sub", unique=True, sparse=True)
    await db.login_attempts.create_index("identifier")
    await db.social_auth_sessions.create_index("id", unique=True)
    await db.social_auth_sessions.create_index("expires_at", expireAfterSeconds=0)
    await db.podcasts.create_index("keywords")
    await db.podcasts.create_index("podcaster_id")
    await db.podcasts.create_index("show_id")
    await db.podcasts.create_index("created_at")
    await db.view_history.create_index([("user_id", 1), ("podcast_id", 1)])
    await db.shows.create_index("id", unique=True)
    await db.shows.create_index("podcaster_id")
    await db.shows.create_index("keywords")
    await db.followed_shows.create_index([("user_id", 1), ("show_id", 1)], unique=True)
    await db.followed_shows.create_index("show_id")
    await db.saved_podcasts.create_index([("user_id", 1), ("podcast_id", 1)], unique=True)
    await db.hidden_podcasts.create_index([("user_id", 1), ("podcast_id", 1)], unique=True)
    await db.podcast_likes.create_index([("user_id", 1), ("podcast_id", 1)], unique=True)
    await db.podcast_likes.create_index("podcast_id")
    await db.podcast_ratings.create_index([("user_id", 1), ("podcast_id", 1)], unique=True)
    await db.podcast_ratings.create_index("podcast_id")
    await db.playback_progress.create_index([("user_id", 1), ("podcast_id", 1)], unique=True)
    await db.playback_progress.create_index("last_played_at")
    await db.podcasts.create_index([("show_id", 1), ("external_guid", 1)])
    await db.ai_podcast_drafts.create_index("id", unique=True)
    await db.ai_podcast_drafts.create_index("podcaster_id")
    await db.ai_podcast_drafts.create_index([("podcaster_id", 1), ("show_id", 1), ("created_at", -1)])

    admin_email = os.environ.get("ADMIN_EMAIL", "admin@audioraq.com")
    admin_password = os.environ.get("ADMIN_PASSWORD", "admin123")
    existing = await db.users.find_one({"email": admin_email})
    if existing is None:
        hashed = hash_password(admin_password)
        await db.users.insert_one(
            {
                "email": admin_email,
                "password_hash": hashed,
                "name": "Admin",
                "role": "admin",
                "interests": [],
                "phone": "",
                "age": None,
                "podcast_description": "",
                "show_title": "",
                "created_at": now_iso(),
            }
        )
        logger.info("Admin user seeded")
    elif not verify_password(admin_password, existing["password_hash"]):
        await db.users.update_one({"email": admin_email}, {"$set": {"password_hash": hash_password(admin_password)}})

    await migrate_existing_shows()

    try:
        init_storage()
        logger.info("Storage initialized")
    except Exception as e:
        logger.error(f"Storage init failed: {e}")

    memory_dir = Path(os.environ.get("MEMORY_DIR", str(DEFAULT_MEMORY_DIR)))
    memory_dir.mkdir(parents=True, exist_ok=True)
    with open(memory_dir / "test_credentials.md", "w") as f:
        f.write("# Test Credentials\n\n")
        f.write(f"## Admin\n- Email: {admin_email}\n- Password: {admin_password}\n- Role: admin\n\n")
        f.write("## Test User\n- Email: testuser@test.com\n- Password: test123\n- Role: user\n\n")
        f.write("## Test Podcaster\n- Email: podcaster@test.com\n- Password: test123\n- Role: podcaster\n\n")
        f.write("## Auth Endpoints\n- POST /api/auth/register\n- POST /api/auth/login\n- POST /api/auth/logout\n- GET /api/auth/me\n- POST /api/auth/refresh\n")


def build_social_display_name(email: str = "", fallback_name: str = "") -> str:
    if (fallback_name or "").strip():
        return fallback_name.strip()
    local_part = (email or "").split("@", 1)[0].strip()
    if not local_part:
        return "Audioraq Creator"
    pieces = [piece for piece in re.split(r"[._\-]+", local_part) if piece]
    pretty = " ".join(piece.capitalize() for piece in pieces[:3]).strip()
    return pretty or "Audioraq Creator"


async def find_user_for_social_profile(provider: str, profile: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    provider_sub = profile.get("sub")
    if provider_sub:
        user = await db.users.find_one({f"auth_providers.{provider}.sub": provider_sub})
        if user:
            return user

    email = (profile.get("email") or "").lower().strip()
    if email:
        return await db.users.find_one({"email": email})
    return None


async def upsert_social_provider_link(user_doc: Dict[str, Any], provider: str, profile: Dict[str, Any]) -> Dict[str, Any]:
    updates = {
        f"auth_providers.{provider}": social_provider_record(provider, profile),
        "updated_at": now_iso(),
    }
    if profile.get("picture_url") and not user_doc.get("avatar_url"):
        updates["avatar_url"] = profile["picture_url"]
    if profile.get("name") and not user_doc.get("name"):
        updates["name"] = profile["name"]
    target_user_id = user_object_id(user_doc)
    await db.users.update_one({"_id": target_user_id}, {"$set": updates})
    return await db.users.find_one({"_id": target_user_id})


async def complete_social_login_redirect(
    user_doc: Dict[str, Any],
    request: Request,
    return_origin: str,
) -> RedirectResponse:
    if user_doc.get("role") == "podcaster":
        await ensure_primary_show_for_user(user_doc)
        user_doc = await db.users.find_one({"_id": user_object_id(user_doc)})

    access_token = create_access_token(str(user_doc["_id"]), user_doc["email"])
    refresh_token = create_refresh_token(str(user_doc["_id"]))
    destination = "/dashboard/podcaster" if user_doc.get("role") == "podcaster" else "/dashboard"
    response = RedirectResponse(build_frontend_url(return_origin, destination), status_code=302)
    set_auth_cookies(response, access_token, refresh_token, request)
    clear_pending_social_cookie(response)
    return response


async def create_pending_social_session(
    provider: str,
    profile: Dict[str, Any],
    intent: str,
    return_origin: str,
    role_hint: str = "",
) -> str:
    session_id = str(uuid.uuid4())
    await db.social_auth_sessions.insert_one(
        {
            "id": session_id,
            "provider": provider,
            "intent": "register" if intent == "register" else "login",
            "role_hint": role_hint if role_hint in {"user", "podcaster"} else "",
            "return_origin": return_origin,
            "email": (profile.get("email") or "").lower().strip(),
            "name": build_social_display_name(profile.get("email", ""), profile.get("name", "")),
            "picture_url": profile.get("picture_url", ""),
            "provider_sub": profile["sub"],
            "email_verified": bool(profile.get("email_verified")),
            "created_at": now_iso(),
            "expires_at": datetime.now(timezone.utc) + timedelta(minutes=15),
        }
    )
    return session_id


async def get_pending_social_session(request: Request) -> Dict[str, Any]:
    session_id = get_pending_social_cookie(request)
    if not session_id:
        raise HTTPException(status_code=404, detail="No pending social sign-up session")
    session = await db.social_auth_sessions.find_one({"id": session_id})
    if not session:
        raise HTTPException(status_code=404, detail="Pending social sign-up session expired")
    return session


def build_google_authorize_url(request: Request, state: str) -> str:
    params = {
        "client_id": get_google_client_id(),
        "redirect_uri": get_oauth_redirect_uri(request, SOCIAL_PROVIDER_GOOGLE),
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "prompt": "select_account",
    }
    return f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"


def exchange_google_code_for_profile(code: str, request: Request) -> Dict[str, Any]:
    from google.auth.transport import requests as google_requests
    from google.oauth2 import id_token as google_id_token

    token_response = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "code": code,
            "client_id": get_google_client_id(),
            "client_secret": get_google_client_secret(),
            "redirect_uri": get_oauth_redirect_uri(request, SOCIAL_PROVIDER_GOOGLE),
            "grant_type": "authorization_code",
        },
        timeout=30,
    )
    token_response.raise_for_status()
    token_data = token_response.json()
    raw_id_token = token_data.get("id_token")
    if not raw_id_token:
        raise HTTPException(status_code=502, detail="Google did not return an ID token")

    id_info = google_id_token.verify_oauth2_token(raw_id_token, google_requests.Request(), get_google_client_id())
    email = (id_info.get("email") or "").lower().strip()
    if not email:
        raise HTTPException(status_code=400, detail="Google account did not provide an email address")

    return {
        "sub": id_info["sub"],
        "email": email,
        "email_verified": bool(id_info.get("email_verified")),
        "name": str(id_info.get("name") or "").strip(),
        "picture_url": str(id_info.get("picture") or "").strip(),
    }


def generate_apple_client_secret() -> str:
    now_ts = int(datetime.now(timezone.utc).timestamp())
    return jwt.encode(
        {
            "iss": get_apple_team_id(),
            "iat": now_ts,
            "exp": now_ts + 86400 * 180,
            "aud": "https://appleid.apple.com",
            "sub": get_apple_client_id(),
        },
        get_apple_private_key(),
        algorithm="ES256",
        headers={"kid": get_apple_key_id()},
    )


def exchange_apple_code_for_profile(code: str, request: Request, raw_user_payload: str = "") -> Dict[str, Any]:
    token_response = requests.post(
        "https://appleid.apple.com/auth/token",
        data={
            "client_id": get_apple_client_id(),
            "client_secret": generate_apple_client_secret(),
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": get_oauth_redirect_uri(request, SOCIAL_PROVIDER_APPLE),
        },
        timeout=30,
    )
    token_response.raise_for_status()
    token_data = token_response.json()
    raw_id_token = token_data.get("id_token")
    if not raw_id_token:
        raise HTTPException(status_code=502, detail="Apple did not return an ID token")

    jwks_client = jwt.PyJWKClient("https://appleid.apple.com/auth/keys")
    signing_key = jwks_client.get_signing_key_from_jwt(raw_id_token)
    claims = jwt.decode(
        raw_id_token,
        signing_key.key,
        algorithms=["RS256"],
        audience=get_apple_client_id(),
        issuer="https://appleid.apple.com",
    )

    name = ""
    if raw_user_payload:
        try:
            user_payload = json.loads(raw_user_payload)
            first_name = str((user_payload.get("name") or {}).get("firstName") or "").strip()
            last_name = str((user_payload.get("name") or {}).get("lastName") or "").strip()
            name = " ".join(part for part in [first_name, last_name] if part).strip()
        except json.JSONDecodeError:
            name = ""

    return {
        "sub": claims["sub"],
        "email": (claims.get("email") or "").lower().strip(),
        "email_verified": str(claims.get("email_verified") or "").lower() == "true",
        "name": name,
        "picture_url": "",
    }


@api_router.get("/auth/social/providers")
async def get_social_auth_providers():
    return {
        "google": is_google_oauth_configured(),
        "apple": is_apple_oauth_configured(),
    }


@api_router.get("/auth/oauth/{provider}/start")
async def start_social_auth(
    provider: str,
    request: Request,
    intent: str = "login",
    return_origin: str = "",
    role_hint: str = "",
):
    provider = provider.strip().lower()
    if provider not in SUPPORTED_SOCIAL_PROVIDERS:
        raise HTTPException(status_code=404, detail="Unsupported social sign-in provider")
    if not is_social_provider_configured(provider):
        raise HTTPException(status_code=503, detail=f"{provider.title()} sign-in is not configured")

    resolved_intent = "register" if intent == "register" else "login"
    resolved_return_origin = sanitize_return_origin(return_origin, request)
    state = build_oauth_state(provider, resolved_intent, resolved_return_origin, role_hint=role_hint)

    if provider == SOCIAL_PROVIDER_GOOGLE:
        return RedirectResponse(build_google_authorize_url(request, state), status_code=302)

    params = {
        "client_id": get_apple_client_id(),
        "redirect_uri": get_oauth_redirect_uri(request, SOCIAL_PROVIDER_APPLE),
        "response_type": "code",
        "response_mode": "form_post",
        "scope": "name email",
        "state": state,
    }
    return RedirectResponse(f"https://appleid.apple.com/auth/authorize?{urlencode(params)}", status_code=302)


@api_router.api_route("/auth/oauth/{provider}/callback", methods=["GET", "POST"])
async def social_auth_callback(provider: str, request: Request):
    provider = provider.strip().lower()
    if provider not in SUPPORTED_SOCIAL_PROVIDERS:
        raise HTTPException(status_code=404, detail="Unsupported social sign-in provider")

    payload_source: Dict[str, Any]
    if request.method == "POST":
        form = await request.form()
        payload_source = dict(form)
    else:
        payload_source = dict(request.query_params)

    raw_state = str(payload_source.get("state") or "").strip()
    if not raw_state:
        raise HTTPException(status_code=400, detail="Missing social sign-in state")

    state = decode_oauth_state(raw_state, provider)
    return_origin = sanitize_return_origin(state.get("return_origin"), request)

    if payload_source.get("error"):
        error_message = str(payload_source.get("error_description") or payload_source.get("error") or "Provider sign-in failed")
        return build_social_state_error_redirect(request, return_origin, error_message)

    code = str(payload_source.get("code") or "").strip()
    if not code:
        return build_social_state_error_redirect(request, return_origin, "Provider sign-in did not return an authorization code")

    try:
        if provider == SOCIAL_PROVIDER_GOOGLE:
            profile = exchange_google_code_for_profile(code, request)
        else:
            profile = exchange_apple_code_for_profile(code, request, str(payload_source.get("user") or ""))
    except HTTPException as exc:
        return build_social_state_error_redirect(request, return_origin, str(exc.detail))
    except Exception as exc:
        logger.error(f"{provider.title()} social sign-in failed: {exc}")
        return build_social_state_error_redirect(request, return_origin, f"{provider.title()} sign-in could not be completed")

    user_doc = await find_user_for_social_profile(provider, profile)
    if user_doc:
        user_doc = await upsert_social_provider_link(user_doc, provider, profile)
        return await complete_social_login_redirect(user_doc, request, return_origin)

    if not profile.get("email"):
        return build_social_state_error_redirect(
            request,
            return_origin,
            f"{provider.title()} did not share an email address for a new account",
        )

    session_id = await create_pending_social_session(
        provider,
        profile,
        state.get("intent", "login"),
        return_origin,
        role_hint=state.get("role_hint", ""),
    )
    response = RedirectResponse(
        build_frontend_url(return_origin, "/register", {"social": 1, "provider": provider}),
        status_code=302,
    )
    set_pending_social_cookie(response, session_id, request)
    return response


@api_router.get("/auth/social/pending")
async def get_pending_social_signup(request: Request):
    session = await get_pending_social_session(request)
    return {
        "provider": session["provider"],
        "intent": session.get("intent", "register"),
        "role_hint": session.get("role_hint", ""),
        "email": session.get("email", ""),
        "name": session.get("name", ""),
        "picture_url": session.get("picture_url", ""),
    }


@api_router.post("/auth/social/cancel")
async def cancel_pending_social_signup(request: Request):
    session_id = get_pending_social_cookie(request)
    if session_id:
        await db.social_auth_sessions.delete_many({"id": session_id})
    response = Response(content=json.dumps({"message": "Pending social sign-up cleared"}), media_type="application/json")
    clear_pending_social_cookie(response)
    return response


@api_router.post("/auth/social/complete")
async def complete_social_signup(req: CompleteSocialSignupRequest, request: Request, response: Response):
    session = await get_pending_social_session(request)
    email = (session.get("email") or "").lower().strip()
    if not email:
        raise HTTPException(status_code=400, detail="This social sign-up session is missing an email address")
    if req.role not in ["user", "podcaster"]:
        raise HTTPException(status_code=400, detail="Role must be 'user' or 'podcaster'")

    age = normalize_age_value(req.age)
    if req.role == "user" and age is None:
        raise HTTPException(status_code=400, detail="Age is required for listener accounts")

    provider = session["provider"]
    profile = {
        "sub": session["provider_sub"],
        "email": email,
        "email_verified": bool(session.get("email_verified")),
        "name": session.get("name", ""),
        "picture_url": session.get("picture_url", ""),
    }

    existing_user = await find_user_for_social_profile(provider, profile)
    if existing_user:
        existing_user = await upsert_social_provider_link(existing_user, provider, profile)
        await db.social_auth_sessions.delete_many({"id": session["id"]})
        clear_pending_social_cookie(response)
        access_token = create_access_token(str(existing_user["_id"]), existing_user["email"])
        refresh_token = create_refresh_token(str(existing_user["_id"]))
        set_auth_cookies(response, access_token, refresh_token, request)
        payload = await build_user_response(existing_user)
        payload["access_token"] = access_token
        return payload

    keywords = []
    if req.role == "podcaster" and req.podcast_description:
        keywords = await extract_keywords(req.podcast_description)

    name = build_social_display_name(email, req.name or session.get("name", ""))
    user_doc = {
        "email": email,
        "name": name,
        "role": req.role,
        "phone": req.phone or "",
        "age": age,
        "interests": [item.lower().strip() for item in (req.interests or [])],
        "podcast_description": req.podcast_description or "",
        "podcast_keywords": keywords,
        "show_title": (req.show_title or "").strip(),
        "avatar_url": session.get("picture_url", ""),
        "auth_providers": {provider: social_provider_record(provider, profile)},
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    result = await db.users.insert_one(user_doc)
    user_doc["_id"] = result.inserted_id

    if req.role == "podcaster":
        primary_show = await ensure_primary_show_for_user(user_doc, title_override=req.show_title)
        user_doc["primary_show_id"] = primary_show["id"] if primary_show else ""
        if primary_show:
            user_doc["show_title"] = primary_show["title"]

    await db.social_auth_sessions.delete_many({"id": session["id"]})
    clear_pending_social_cookie(response)

    access_token = create_access_token(str(result.inserted_id), email)
    refresh_token = create_refresh_token(str(result.inserted_id))
    set_auth_cookies(response, access_token, refresh_token, request)
    clear_pending_social_cookie(response)

    payload = await build_user_response(user_doc)
    payload["access_token"] = access_token
    return payload


@api_router.post("/auth/register")
async def register(req: RegisterRequest, request: Request, response: Response):
    email = req.email.lower().strip()
    if req.role not in ["user", "podcaster"]:
        raise HTTPException(status_code=400, detail="Role must be 'user' or 'podcaster'")
    age = normalize_age_value(req.age)
    if req.role == "user" and age is None:
        raise HTTPException(status_code=400, detail="Age is required for listener accounts")
    existing = await db.users.find_one({"email": email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    keywords = []
    if req.role == "podcaster" and req.podcast_description:
        keywords = await extract_keywords(req.podcast_description)

    user_doc = {
        "email": email,
        "password_hash": hash_password(req.password),
        "name": req.name,
        "role": req.role,
        "phone": req.phone or "",
        "age": age,
        "interests": [i.lower().strip() for i in (req.interests or [])],
        "podcast_description": req.podcast_description or "",
        "podcast_keywords": keywords,
        "show_title": (req.show_title or "").strip(),
        "created_at": now_iso(),
    }
    result = await db.users.insert_one(user_doc)
    user_doc["_id"] = result.inserted_id

    if req.role == "podcaster":
        primary_show = await ensure_primary_show_for_user(user_doc, title_override=req.show_title)
        user_doc["primary_show_id"] = primary_show["id"] if primary_show else ""
        if primary_show:
            user_doc["show_title"] = primary_show["title"]

    access_token = create_access_token(str(result.inserted_id), email)
    refresh_token = create_refresh_token(str(result.inserted_id))
    set_auth_cookies(response, access_token, refresh_token, request)

    payload = await build_user_response(user_doc)
    payload["access_token"] = access_token
    return payload


@api_router.post("/auth/login")
async def login(req: LoginRequest, request: Request, response: Response):
    email = req.email.lower().strip()
    ip = request.client.host if request.client else "unknown"
    identifier = f"{ip}:{email}"

    attempt = await db.login_attempts.find_one({"identifier": identifier})
    if attempt and attempt.get("attempts", 0) >= 5:
        last = attempt.get("last_attempt")
        if last:
            if isinstance(last, str):
                last = datetime.fromisoformat(last)
            if datetime.now(timezone.utc) - last < timedelta(minutes=15):
                raise HTTPException(status_code=429, detail="Too many attempts. Try again in 15 minutes.")

    user = await db.users.find_one({"email": email})
    if not user or not verify_password(req.password, user["password_hash"]):
        await db.login_attempts.update_one(
            {"identifier": identifier},
            {"$inc": {"attempts": 1}, "$set": {"last_attempt": now_iso()}},
            upsert=True,
        )
        raise HTTPException(status_code=401, detail="Invalid email or password")

    await db.login_attempts.delete_many({"identifier": identifier})
    if user.get("role") == "podcaster":
        await ensure_primary_show_for_user(user)
        user = await db.users.find_one({"_id": user["_id"]})

    user_id = str(user["_id"])
    access_token = create_access_token(user_id, email)
    refresh_token = create_refresh_token(user_id)
    set_auth_cookies(response, access_token, refresh_token, request)
    clear_pending_social_cookie(response)

    payload = await build_user_response(user)
    payload["access_token"] = access_token
    return payload


@api_router.post("/auth/logout")
async def logout(response: Response):
    clear_auth_cookies(response)
    clear_pending_social_cookie(response)
    return {"message": "Logged out"}


@api_router.get("/auth/me")
async def get_me(request: Request):
    user = await get_current_user(request)
    return await build_user_response(user)


@api_router.post("/auth/refresh")
async def refresh_token(request: Request, response: Response):
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(status_code=401, detail="No refresh token")
    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")
        user = await db.users.find_one({"_id": ObjectId(payload["sub"])})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        user_id = str(user["_id"])
        access_token = create_access_token(user_id, user["email"])
        response.set_cookie(key="access_token", value=access_token, max_age=3600, **get_cookie_settings(request))
        return {"message": "Token refreshed", "access_token": access_token}
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Refresh token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")


@api_router.put("/user/interests")
async def update_interests(req: UpdateInterestsRequest, request: Request):
    user = await get_current_user(request)
    interests = [i.lower().strip() for i in req.interests]
    await db.users.update_one({"_id": ObjectId(user["_id"])}, {"$set": {"interests": interests}})
    return {"message": "Interests updated", "interests": interests}


@api_router.put("/user/podcast-description")
async def update_podcast_description(req: UpdatePodcastDescriptionRequest, request: Request):
    user = await get_current_user(request)
    if user["role"] != "podcaster":
        raise HTTPException(status_code=403, detail="Only podcasters can update podcast description")
    keywords = await extract_keywords(req.podcast_description)
    primary_show = await ensure_primary_show_for_user(user)
    await db.users.update_one(
        {"_id": ObjectId(user["_id"])},
        {"$set": {"podcast_description": req.podcast_description, "podcast_keywords": keywords}},
    )
    if primary_show:
        await db.shows.update_one(
            {"id": primary_show["id"], "podcaster_id": user["_id"]},
            {"$set": {"description": req.podcast_description, "keywords": keywords, "updated_at": now_iso()}},
        )
    return {"message": "Description updated", "keywords": keywords}


@api_router.get("/shows")
async def get_shows(
    request: Request,
    search: Optional[str] = None,
    category: Optional[str] = None,
    following_only: bool = False,
    page: int = 1,
    limit: int = 12,
):
    current_user = await try_get_current_user(request)
    query = build_public_episode_query(current_user)
    if search:
        query["$or"] = [
            {"title": {"$regex": search, "$options": "i"}},
            {"description": {"$regex": search, "$options": "i"}},
            {"keywords": {"$in": [search.lower()]}},
            {"podcaster_name": {"$regex": search, "$options": "i"}},
        ]
    if category:
        query["category"] = category.lower()
    if following_only:
        followed_show_ids = list(await get_followed_show_ids(current_user))
        if not followed_show_ids:
            return {"shows": [], "total": 0, "page": page, "pages": 0}
        query["id"] = {"$in": followed_show_ids}

    skip = (page - 1) * limit
    total = await db.shows.count_documents(query)
    shows = await db.shows.find(query).sort("updated_at", -1).skip(skip).limit(limit).to_list(limit)
    enriched = await enrich_shows(shows, current_user=current_user)
    return {"shows": enriched, "total": total, "page": page, "pages": (total + limit - 1) // limit}


@api_router.get("/shows/my")
async def get_my_shows(request: Request):
    user = await get_current_user(request)
    if user["role"] != "podcaster":
        raise HTTPException(status_code=403, detail="Only podcasters can manage shows")
    shows = await db.shows.find({"podcaster_id": user["_id"], "is_deleted": False}).sort("created_at", 1).to_list(25)
    return {"shows": await enrich_shows(shows, current_user=user)}


@api_router.get("/creator/analytics")
async def get_creator_analytics(request: Request, show_id: Optional[str] = None):
    user = await get_current_user(request)
    if user["role"] != "podcaster":
        raise HTTPException(status_code=403, detail="Only podcasters can view analytics")
    return await fetch_creator_analytics(user, show_id=show_id)


@api_router.get("/ai-podcast-drafts/my")
async def get_my_ai_podcast_drafts(request: Request, show_id: Optional[str] = None, limit: int = 12):
    user = await get_current_user(request)
    if user["role"] != "podcaster":
        raise HTTPException(status_code=403, detail="Only podcasters can use AI podcast drafts")

    query = {"podcaster_id": user["_id"]}
    if show_id:
        query["show_id"] = show_id

    safe_limit = max(1, min(limit, 20))
    drafts = await db.ai_podcast_drafts.find(query).sort("created_at", -1).limit(safe_limit).to_list(safe_limit)
    return {"drafts": [clean_doc(draft) for draft in drafts]}


@api_router.post("/ai-podcast-drafts/generate")
async def generate_ai_podcast_draft(req: GenerateAIPodcastDraftRequest, request: Request):
    user = await get_current_user(request)
    if user["role"] != "podcaster":
        raise HTTPException(status_code=403, detail="Only podcasters can create podcasts with AI")

    show_id = req.show_id.strip()
    if not show_id:
        raise HTTPException(status_code=400, detail="Pick a show before creating an AI podcast draft")

    show = await db.shows.find_one({"id": show_id, "podcaster_id": user["_id"], "is_deleted": False})
    if show is None:
        raise HTTPException(status_code=404, detail="Show not found")

    intake = req.intake.dict()
    if not normalize_string_list(intake["contentInput"].get("keyPoints"), limit=10):
        raise HTTPException(status_code=400, detail="Add at least one key point before generating")

    generation = await generate_ai_podcast_package(intake, show)
    agent2_review = evaluate_agent2_quality(
        generation.get("episode_title") or intake["contentInput"].get("topic") or "Untitled AI Episode",
        generation.get("suggested_description") or build_ai_publish_description(generation),
        generation=generation,
        source_kind="ai_draft",
    )
    agent2_iterations = [{"iteration": 1, "event": "initial_review", "review": agent2_review}]
    revised_generation = await revise_ai_generation_with_agent2_feedback(intake, show, generation, agent2_review)
    if revised_generation:
        revised_agent2_review = evaluate_agent2_quality(
            revised_generation.get("episode_title") or generation.get("episode_title") or intake["contentInput"].get("topic") or "Untitled AI Episode",
            revised_generation.get("suggested_description") or build_ai_publish_description(revised_generation),
            generation=revised_generation,
            source_kind="ai_draft_revision",
        )
        revision_improved = revised_agent2_review.get("quality_score", 0) >= agent2_review.get("quality_score", 0)
        revision_safe = revised_agent2_review.get("rag_safety", {}).get("status") != "blocked"
        agent2_iterations.append(
            {
                "iteration": 2,
                "event": "rlaif_revision_applied" if revision_improved and revision_safe else "rlaif_revision_discarded",
                "review": revised_agent2_review,
            }
        )
        if revision_improved and revision_safe:
            generation = revised_generation
            agent2_review = revised_agent2_review

    draft_doc = {
        "id": str(uuid.uuid4()),
        "show_id": show["id"],
        "show_title": show["title"],
        "recommended_category": generation.get("recommended_category") or show.get("category") or DEFAULT_SHOW_CATEGORY,
        "podcaster_id": user["_id"],
        "podcaster_name": user["name"],
        "intake": intake,
        "generation": generation,
        "agent2_review": agent2_review,
        "agent2_iterations": agent2_iterations,
        "quality_status": agent2_review.get("status", "pass"),
        "quality_score": agent2_review.get("quality_score", 0),
        "media_policy": {
            "create_with_ai": "audio_only",
            "recorded_upload": "audio_or_video",
            "note": "AI-created podcasts must publish as audio-only; recorded non-AI uploads may be audio or video.",
        },
        "publish_prefill": {
            "title": generation.get("episode_title") or intake["contentInput"].get("topic") or "Untitled AI Episode",
            "description": generation.get("suggested_description") or build_ai_publish_description(generation),
            "category": generation.get("recommended_category") or show.get("category") or DEFAULT_SHOW_CATEGORY,
        },
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "last_used_at": "",
    }
    await db.ai_podcast_drafts.insert_one(draft_doc)
    return clean_doc(draft_doc)


@api_router.post("/shows/import-rss")
async def import_rss_feed(req: RssImportRequest, request: Request):
    user = await get_current_user(request)
    if user["role"] != "podcaster":
        raise HTTPException(status_code=403, detail="Only podcasters can import RSS feeds")

    feed_url = req.feed_url.strip()
    if not feed_url:
        raise HTTPException(status_code=400, detail="Feed URL is required")

    try:
        response = requests.get(feed_url, timeout=30)
        response.raise_for_status()
    except Exception as exc:
        logger.error(f"RSS fetch failed: {exc}")
        raise HTTPException(status_code=400, detail="Could not fetch RSS feed")

    try:
        root = ET.fromstring(response.content)
    except Exception as exc:
        logger.error(f"RSS parse failed: {exc}")
        raise HTTPException(status_code=400, detail="Invalid RSS feed")

    channel = root.find("channel")
    if channel is None and root.tag == "{http://www.w3.org/2005/Atom}feed":
        channel = root
    if channel is None:
        raise HTTPException(status_code=400, detail="RSS feed is missing channel data")

    namespaces = {
        "itunes": "http://www.itunes.com/dtds/podcast-1.0.dtd",
        "media": "http://search.yahoo.com/mrss/",
        "atom": "http://www.w3.org/2005/Atom",
        "content": "http://purl.org/rss/1.0/modules/content/",
    }

    feed_title = xml_first_text(channel, ["title", "atom:title"], namespaces) or build_default_show_title(user.get("name", ""))
    feed_description = strip_html(
        xml_first_text(channel, ["description", "itunes:summary", "itunes:subtitle", "atom:subtitle"], namespaces)
    )
    feed_category = (
        xml_first_text(channel, ["category", "itunes:category"], namespaces, attribute="text")
        or DEFAULT_SHOW_CATEGORY
    ).lower()
    feed_thumbnail = xml_first_text(
        channel,
        ["itunes:image", "image/url", "media:thumbnail"],
        namespaces,
        attribute="href",
    ) or xml_first_text(channel, ["image/url"], namespaces)

    target_show = None
    if req.show_id:
        target_show = await db.shows.find_one({"id": req.show_id, "podcaster_id": user["_id"], "is_deleted": False})
        if target_show is None:
            raise HTTPException(status_code=404, detail="Show not found")
    else:
        target_show = await db.shows.find_one(
            {"podcaster_id": user["_id"], "title": feed_title, "is_deleted": False}
        )
        if target_show is None:
            keywords = await extract_keywords(f"{feed_title} {feed_description} {feed_category}")
            show_doc = {
                "id": str(uuid.uuid4()),
                "title": feed_title,
                "description": feed_description,
                "category": feed_category,
                "keywords": keywords,
                "thumbnail_path": "",
                "external_thumbnail_url": feed_thumbnail,
                "podcaster_id": user["_id"],
                "podcaster_name": user["name"],
                "is_primary": False,
                "is_deleted": False,
                "created_at": now_iso(),
                "updated_at": now_iso(),
            }
            await db.shows.insert_one(show_doc)
            target_show = show_doc

    imported = 0
    items = channel.findall("item") or channel.findall("{http://www.w3.org/2005/Atom}entry")
    for item in items[: max(1, min(int(req.import_limit or 10), 25))]:
        title = xml_first_text(item, ["title", "atom:title"], namespaces)
        if not title:
            continue
        enclosure = item.find("enclosure")
        media_url = enclosure.attrib.get("url", "").strip() if enclosure is not None else ""
        media_type = enclosure.attrib.get("type", "").strip() if enclosure is not None else ""
        if not media_url:
            media_url = xml_first_text(item, ["media:content", "atom:link"], namespaces, attribute="url") or xml_first_text(item, ["atom:link"], namespaces, attribute="href")
        if not media_url:
            continue

        external_guid = xml_first_text(item, ["guid", "atom:id"], namespaces) or media_url
        existing = await db.podcasts.find_one(
            {"show_id": target_show["id"], "$or": [{"external_guid": external_guid}, {"external_media_url": media_url}]}
        )
        if existing:
            continue

        description = strip_html(
            xml_first_text(item, ["description", "content:encoded", "itunes:summary", "summary"], namespaces)
        )
        category = (
            xml_first_text(item, ["category", "itunes:category"], namespaces, attribute="text")
            or feed_category
            or DEFAULT_SHOW_CATEGORY
        ).lower()
        item_thumbnail = xml_first_text(
            item,
            ["itunes:image", "media:thumbnail"],
            namespaces,
            attribute="href",
        ) or feed_thumbnail
        published_at = parse_rss_datetime(xml_first_text(item, ["pubDate", "published", "updated"], namespaces)) or now_iso()
        filename = os.path.basename(urlparse(media_url).path) or f"{uuid.uuid4()}.mp3"
        normalized_media_type = "video" if media_type.startswith("video/") else "audio"
        keywords = await extract_keywords(f"{title} {description} {category} {target_show['title']}")

        podcast_doc = {
            "id": str(uuid.uuid4()),
            "show_id": target_show["id"],
            "show_title": target_show["title"],
            "title": title,
            "description": description,
            "category": category,
            "keywords": keywords,
            "media_path": "",
            "external_media_url": media_url,
            "external_thumbnail_url": item_thumbnail,
            "external_guid": external_guid,
            "media_type": normalized_media_type,
            "content_type": media_type or ("audio/mpeg" if normalized_media_type == "audio" else "video/mp4"),
            "original_filename": filename,
            "thumbnail_path": "",
            "podcaster_id": user["_id"],
            "podcaster_name": user["name"],
            "season_number": None,
            "episode_number": None,
            "play_count": 0,
            "like_count": 0,
            "rating_count": 0,
            "rating_average": 0,
            "audience_rating": ALL_AGES_RATING,
            "moderation_status": MODERATION_STATUS_CLEAR,
            "moderation": {
                "status": MODERATION_STATUS_CLEAR,
                "risk_level": "low",
                "flags": [],
                "summary": "Imported from RSS without an automated safety review.",
                "recommended_age_gate": ALL_AGES_RATING,
                "provider": "rss-import",
                "reviewed_at": now_iso(),
            },
            "publication_status": PUBLICATION_STATUS_PUBLISHED,
            "is_playable": True,
            "file_size": 0,
            "created_at": published_at,
            "updated_at": now_iso(),
            "is_deleted": False,
            "source_kind": "rss",
            "import_source": "rss",
        }
        await db.podcasts.insert_one(podcast_doc)
        imported += 1

    await db.shows.update_one(
        {"id": target_show["id"]},
        {
            "$set": {
                "updated_at": now_iso(),
                "description": target_show.get("description") or feed_description,
                "category": target_show.get("category") or feed_category,
                "external_thumbnail_url": target_show.get("external_thumbnail_url") or feed_thumbnail,
            }
        },
    )
    return {"message": "RSS import complete", "show_id": target_show["id"], "imported_count": imported}


@api_router.get("/shows/following")
async def get_following_shows(request: Request, page: int = 1, limit: int = 12):
    user = await get_current_user(request)
    followed_show_ids = list(await get_followed_show_ids(user))
    if not followed_show_ids:
        return {"shows": [], "total": 0, "page": page, "pages": 0}

    skip = (page - 1) * limit
    total = len(followed_show_ids)
    shows = await db.shows.find({"id": {"$in": followed_show_ids}, "is_deleted": False}).sort("updated_at", -1).skip(skip).limit(limit).to_list(limit)
    return {"shows": await enrich_shows(shows, current_user=user), "total": total, "page": page, "pages": (total + limit - 1) // limit}


@api_router.post("/shows")
async def create_show(
    request: Request,
    title: str = Form(...),
    description: str = Form(""),
    category: str = Form(DEFAULT_SHOW_CATEGORY),
    thumbnail: Optional[UploadFile] = File(None),
):
    user = await get_current_user(request)
    if user["role"] != "podcaster":
        raise HTTPException(status_code=403, detail="Only podcasters can create shows")

    show_title = title.strip()
    if not show_title:
        raise HTTPException(status_code=400, detail="Show title is required")

    thumbnail_path = ""
    if thumbnail:
        thumbnail_path, _ = await store_upload(thumbnail, f"show-thumbnails/{user['_id']}", "image/jpeg")

    keywords = await extract_keywords(f"{show_title} {description} {category}")
    existing_count = await db.shows.count_documents({"podcaster_id": user["_id"], "is_deleted": False})
    show_doc = {
        "id": str(uuid.uuid4()),
        "title": show_title,
        "description": description,
        "category": (category or DEFAULT_SHOW_CATEGORY).lower(),
        "keywords": keywords,
        "thumbnail_path": thumbnail_path,
        "podcaster_id": user["_id"],
        "podcaster_name": user["name"],
        "is_primary": existing_count == 0,
        "is_deleted": False,
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    await db.shows.insert_one(show_doc)

    if show_doc["is_primary"]:
        await db.users.update_one(
            {"_id": ObjectId(user["_id"])},
            {
                "$set": {
                    "primary_show_id": show_doc["id"],
                    "show_title": show_doc["title"],
                    "podcast_description": show_doc["description"],
                    "podcast_keywords": keywords,
                }
            },
        )

    shows = await enrich_shows([show_doc], current_user=user)
    return shows[0]


@api_router.get("/shows/{show_id}")
async def get_show(show_id: str, request: Request):
    current_user = await try_get_current_user(request)
    show = await db.shows.find_one({"id": show_id, "is_deleted": False})
    if not show:
        raise HTTPException(status_code=404, detail="Show not found")
    enriched = await enrich_shows([show], current_user=current_user)
    return enriched[0]


@api_router.post("/shows/{show_id}/follow")
async def follow_show(show_id: str, request: Request):
    user = await get_current_user(request)
    show = await db.shows.find_one({"id": show_id, "is_deleted": False})
    if not show:
        raise HTTPException(status_code=404, detail="Show not found")
    if show.get("podcaster_id") == user["_id"]:
        raise HTTPException(status_code=400, detail="You already manage this show")

    await db.followed_shows.update_one(
        {"user_id": user["_id"], "show_id": show_id},
        {"$set": {"followed_at": now_iso()}},
        upsert=True,
    )
    return {"message": "Show followed", "show_id": show_id}


@api_router.delete("/shows/{show_id}/follow")
async def unfollow_show(show_id: str, request: Request):
    user = await get_current_user(request)
    await db.followed_shows.delete_one({"user_id": user["_id"], "show_id": show_id})
    return {"message": "Show unfollowed", "show_id": show_id}


@api_router.put("/shows/{show_id}")
async def update_show(
    show_id: str,
    request: Request,
    title: str = Form(...),
    description: str = Form(""),
    category: str = Form(DEFAULT_SHOW_CATEGORY),
    thumbnail: Optional[UploadFile] = File(None),
):
    user = await get_current_user(request)
    if user["role"] != "podcaster":
        raise HTTPException(status_code=403, detail="Only podcasters can edit shows")

    show = await db.shows.find_one({"id": show_id, "podcaster_id": user["_id"], "is_deleted": False})
    if not show:
        raise HTTPException(status_code=404, detail="Show not found")

    updates = {
        "title": title.strip() or show["title"],
        "description": description,
        "category": (category or DEFAULT_SHOW_CATEGORY).lower(),
        "updated_at": now_iso(),
    }
    updates["keywords"] = await extract_keywords(f"{updates['title']} {updates['description']} {updates['category']}")

    previous_thumbnail_path = (show.get("thumbnail_path") or "").strip()
    if thumbnail:
        thumbnail_path, _ = await store_upload(thumbnail, f"show-thumbnails/{user['_id']}", "image/jpeg")
        updates["thumbnail_path"] = thumbnail_path

    await db.shows.update_one({"id": show_id}, {"$set": updates})
    if thumbnail:
        replacement_thumbnail_path = (updates.get("thumbnail_path") or "").strip()
        if previous_thumbnail_path and previous_thumbnail_path != replacement_thumbnail_path:
            cleanup_storage_paths([previous_thumbnail_path], strict=False)
    if show.get("is_primary"):
        await db.users.update_one(
            {"_id": ObjectId(user["_id"])},
            {
                "$set": {
                    "show_title": updates["title"],
                    "podcast_description": updates["description"],
                    "podcast_keywords": updates["keywords"],
                }
            },
        )
    updated = await db.shows.find_one({"id": show_id, "is_deleted": False})
    enriched = await enrich_shows([updated], current_user=user)
    return enriched[0]


@api_router.get("/shows/{show_id}/episodes")
async def get_show_episodes(show_id: str, request: Request, page: int = 1, limit: int = 20):
    current_user = await try_get_current_user(request)
    show = await db.shows.find_one({"id": show_id, "is_deleted": False})
    if not show:
        raise HTTPException(status_code=404, detail="Show not found")
    skip = (page - 1) * limit
    query = {"show_id": show_id, **build_public_episode_query(current_user)}
    hidden_ids = list(await get_hidden_podcast_ids(current_user))
    if hidden_ids:
        query["id"] = {"$nin": hidden_ids}
    total = await db.podcasts.count_documents(query)
    episodes = await db.podcasts.find(query).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    return {"podcasts": await enrich_episodes(episodes, current_user=current_user), "total": total, "page": page, "pages": (total + limit - 1) // limit}


@api_router.get("/shows/{show_id}/thumbnail")
async def get_show_thumbnail(show_id: str):
    show = await db.shows.find_one({"id": show_id, "is_deleted": False})
    if not show:
        raise HTTPException(status_code=404, detail="Show not found")
    thumbnail_path = show.get("thumbnail_path")
    external_thumbnail_url = show.get("external_thumbnail_url")
    if not thumbnail_path:
        latest_episode = await db.podcasts.find_one(
            {"show_id": show_id, "thumbnail_path": {"$nin": [None, ""]}, "is_deleted": False}
        )
        thumbnail_path = latest_episode.get("thumbnail_path") if latest_episode else ""
        external_thumbnail_url = external_thumbnail_url or (latest_episode.get("external_thumbnail_url") if latest_episode else "")
    if not thumbnail_path:
        if external_thumbnail_url:
            return RedirectResponse(external_thumbnail_url)
        raise HTTPException(status_code=404, detail="Thumbnail not found")
    try:
        data, ct = get_object(thumbnail_path)
        return Response(content=data, media_type=ct)
    except Exception as e:
        logger.error(f"Show thumbnail error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get show thumbnail")


@api_router.post("/podcasts/upload")
async def upload_podcast(
    request: Request,
    file: UploadFile = File(...),
    title: str = Form(...),
    description: str = Form(""),
    category: str = Form(DEFAULT_SHOW_CATEGORY),
    audience_rating: str = Form(ALL_AGES_RATING),
    show_id: str = Form(""),
    ai_draft_id: str = Form(""),
    season_number: Optional[int] = Form(None),
    episode_number: Optional[int] = Form(None),
    thumbnail: Optional[UploadFile] = File(None),
):
    user = await get_current_user(request)
    if user["role"] != "podcaster":
        raise HTTPException(status_code=403, detail="Only podcasters can upload podcasts")

    allowed_audio = ["audio/mpeg", "audio/mp3", "audio/wav", "audio/x-wav", "audio/vnd.wav", "audio/ogg", "audio/aac", "audio/flac", "audio/x-m4a", "audio/mp4"]
    allowed_video = ["video/mp4", "video/webm", "video/ogg", "video/quicktime", "video/x-msvideo"]
    content_type = file.content_type or "application/octet-stream"
    is_audio_upload = content_type in allowed_audio or content_type.startswith("audio/")
    is_video_upload = content_type in allowed_video or content_type.startswith("video/")
    if not (is_audio_upload or is_video_upload):
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {content_type}. Allowed: audio and video files.")

    show = None
    selected_show_id = (show_id or "").strip()
    if selected_show_id:
        show = await db.shows.find_one({"id": selected_show_id, "podcaster_id": user["_id"], "is_deleted": False})
        if show is None:
            raise HTTPException(status_code=404, detail="Show not found")
    if show is None:
        show = await ensure_primary_show_for_user(user)
        if show is None:
            raise HTTPException(status_code=400, detail="Create a show before publishing episodes")

    ai_draft = None
    selected_ai_draft_id = (ai_draft_id or "").strip()
    if selected_ai_draft_id:
        ai_draft = await db.ai_podcast_drafts.find_one({"id": selected_ai_draft_id, "podcaster_id": user["_id"]})
        if ai_draft is None:
            raise HTTPException(status_code=404, detail="AI draft not found")
        if not is_audio_upload:
            raise HTTPException(
                status_code=400,
                detail="Create with AI supports audio-only publishing. Use the regular Publish Episode flow for recorded video uploads.",
            )

    ext = file.filename.split(".")[-1] if "." in file.filename else "bin"
    media_path = f"{APP_NAME}/episodes/{user['_id']}/{uuid.uuid4()}.{ext}"
    data = await file.read()
    put_object(media_path, data, content_type)

    thumbnail_path = ""
    if thumbnail:
        thumbnail_path, _ = await store_upload(thumbnail, f"episode-thumbnails/{user['_id']}", "image/jpeg")

    normalized_category = (category or DEFAULT_SHOW_CATEGORY).lower()
    keywords = await extract_keywords(f"{title} {description} {normalized_category} {show['title']}")
    media_type = "video" if is_video_upload else "audio"
    selected_rating = normalize_content_rating(audience_rating)
    media_analysis = transcribe_media_for_safety(data, file.filename or "", content_type)
    moderation = await review_episode_safety(
        show,
        title,
        description,
        normalized_category,
        selected_rating=selected_rating,
        generation=ai_draft.get("generation") if ai_draft else None,
        media_analysis=media_analysis,
    )
    quality_agent = evaluate_agent2_quality(
        title,
        description,
        generation=ai_draft.get("generation") if ai_draft else None,
        media_analysis=media_analysis,
        source_kind="ai_audio_upload" if ai_draft else "recorded_upload",
    )
    moderation = merge_agent2_quality_into_moderation(moderation, quality_agent)
    resolved_rating = MATURE_RATING if moderation.get("recommended_age_gate") == MATURE_RATING else selected_rating
    podcast_doc = {
        "id": str(uuid.uuid4()),
        "show_id": show["id"],
        "show_title": show["title"],
        "title": title,
        "description": description,
        "category": normalized_category,
        "keywords": keywords,
        "media_path": media_path,
        "media_type": media_type,
        "content_type": content_type,
        "original_filename": file.filename,
        "thumbnail_path": thumbnail_path,
        "podcaster_id": user["_id"],
        "podcaster_name": user["name"],
        "season_number": season_number,
        "episode_number": episode_number,
        "play_count": 0,
        "like_count": 0,
        "rating_count": 0,
        "rating_average": 0,
        "audience_rating": resolved_rating,
        "moderation_status": moderation["status"],
        "moderation": moderation,
        "quality_agent": quality_agent,
        "quality_status": quality_agent.get("status", "pass"),
        "quality_score": quality_agent.get("quality_score", 0),
        "publication_status": PUBLICATION_STATUS_PUBLISHED,
        "is_playable": True,
        "source_kind": "upload",
        "file_size": len(data),
        "transcript_status": media_analysis.get("status", ""),
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "is_deleted": False,
    }
    if ai_draft:
        podcast_doc["ai_draft_id"] = ai_draft["id"]
        podcast_doc["ai_assisted"] = True
    await db.podcasts.insert_one(podcast_doc)
    await db.shows.update_one({"id": show["id"]}, {"$set": {"updated_at": now_iso()}})
    if ai_draft:
        await db.ai_podcast_drafts.update_one(
            {"id": ai_draft["id"]},
            {"$set": {"last_used_at": now_iso(), "updated_at": now_iso(), "published_episode_id": podcast_doc["id"]}},
        )
    enriched = await enrich_episodes([podcast_doc], current_user=user)
    return enriched[0]


@api_router.post("/podcasts/ai-create")
async def create_ai_podcast_episode(
    request: Request,
    show_id: str = Form(...),
    ai_draft_id: str = Form(...),
    title: str = Form(""),
    description: str = Form(""),
    category: str = Form(DEFAULT_SHOW_CATEGORY),
    audience_rating: str = Form(ALL_AGES_RATING),
    season_number: Optional[int] = Form(None),
    episode_number: Optional[int] = Form(None),
    thumbnail: Optional[UploadFile] = File(None),
):
    user = await get_current_user(request)
    if user["role"] != "podcaster":
        raise HTTPException(status_code=403, detail="Only podcasters can create AI episodes")

    selected_show_id = (show_id or "").strip()
    selected_ai_draft_id = (ai_draft_id or "").strip()
    if not selected_show_id or not selected_ai_draft_id:
        raise HTTPException(status_code=400, detail="Select a show and an AI draft first")

    show = await db.shows.find_one({"id": selected_show_id, "podcaster_id": user["_id"], "is_deleted": False})
    if show is None:
        raise HTTPException(status_code=404, detail="Show not found")

    ai_draft = await db.ai_podcast_drafts.find_one({"id": selected_ai_draft_id, "podcaster_id": user["_id"]})
    if ai_draft is None:
        raise HTTPException(status_code=404, detail="AI draft not found")

    final_title = (title or ai_draft.get("publish_prefill", {}).get("title") or ai_draft.get("generation", {}).get("episode_title") or "").strip()
    final_description = (description or ai_draft.get("publish_prefill", {}).get("description") or ai_draft.get("generation", {}).get("suggested_description") or "").strip()
    if not final_title:
        raise HTTPException(status_code=400, detail="AI episode title is required")

    thumbnail_path = ""
    if thumbnail:
        thumbnail_path, _ = await store_upload(thumbnail, f"episode-thumbnails/{user['_id']}", "image/jpeg")

    normalized_category = (
        category
        or ai_draft.get("publish_prefill", {}).get("category")
        or ai_draft.get("recommended_category")
        or show.get("category")
        or DEFAULT_SHOW_CATEGORY
    ).lower()
    keywords = await extract_keywords(f"{final_title} {final_description} {normalized_category} {show['title']}")
    selected_rating = normalize_content_rating(audience_rating)
    moderation = await review_episode_safety(
        show,
        final_title,
        final_description,
        normalized_category,
        selected_rating=selected_rating,
        generation=ai_draft.get("generation"),
    )
    quality_agent = evaluate_agent2_quality(
        final_title,
        final_description,
        generation=ai_draft.get("generation"),
        source_kind="ai_audio_draft",
    )
    moderation = merge_agent2_quality_into_moderation(moderation, quality_agent)
    resolved_rating = MATURE_RATING if moderation.get("recommended_age_gate") == MATURE_RATING else selected_rating

    podcast_doc = {
        "id": str(uuid.uuid4()),
        "show_id": show["id"],
        "show_title": show["title"],
        "title": final_title,
        "description": final_description,
        "category": normalized_category,
        "keywords": keywords,
        "media_path": "",
        "media_type": "audio",
        "content_type": "",
        "original_filename": "",
        "thumbnail_path": thumbnail_path,
        "podcaster_id": user["_id"],
        "podcaster_name": user["name"],
        "season_number": season_number,
        "episode_number": episode_number,
        "play_count": 0,
        "like_count": 0,
        "rating_count": 0,
        "rating_average": 0,
        "audience_rating": resolved_rating,
        "moderation_status": moderation["status"],
        "moderation": moderation,
        "quality_agent": quality_agent,
        "quality_status": quality_agent.get("status", "pass"),
        "quality_score": quality_agent.get("quality_score", 0),
        "publication_status": PUBLICATION_STATUS_DRAFT,
        "is_playable": False,
        "source_kind": "ai",
        "file_size": 0,
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "is_deleted": False,
        "ai_draft_id": ai_draft["id"],
        "ai_assisted": True,
        "media_policy": ai_draft.get("media_policy", {}),
        "script_package": ai_draft.get("generation", {}),
    }
    await db.podcasts.insert_one(podcast_doc)
    await db.shows.update_one({"id": show["id"]}, {"$set": {"updated_at": now_iso()}})
    await db.ai_podcast_drafts.update_one(
        {"id": ai_draft["id"]},
        {"$set": {"last_used_at": now_iso(), "updated_at": now_iso(), "generated_episode_id": podcast_doc["id"]}},
    )
    enriched = await enrich_episodes([podcast_doc], current_user=user)
    return enriched[0]


@api_router.get("/podcasts")
async def get_podcasts(
    request: Request,
    search: Optional[str] = None,
    category: Optional[str] = None,
    media_type: Optional[str] = None,
    show_id: Optional[str] = None,
    following_only: bool = False,
    saved_only: bool = False,
    sort: str = "recent",
    page: int = 1,
    limit: int = 20,
):
    current_user = await try_get_current_user(request)
    query = {"is_deleted": False}
    if search:
        query["$or"] = [
            {"title": {"$regex": search, "$options": "i"}},
            {"description": {"$regex": search, "$options": "i"}},
            {"keywords": {"$in": [search.lower()]}},
            {"podcaster_name": {"$regex": search, "$options": "i"}},
            {"show_title": {"$regex": search, "$options": "i"}},
        ]
    if category:
        query["category"] = category.lower()
    if media_type in {"audio", "video"}:
        query["media_type"] = media_type
    if show_id:
        query["show_id"] = show_id
    if following_only:
        followed_show_ids = list(await get_followed_show_ids(current_user))
        if not followed_show_ids:
            return {"podcasts": [], "total": 0, "page": page, "pages": 0}
        if show_id:
            if show_id not in followed_show_ids:
                return {"podcasts": [], "total": 0, "page": page, "pages": 0}
        else:
            query["show_id"] = {"$in": followed_show_ids}

    id_filters = {}
    hidden_ids = list(await get_hidden_podcast_ids(current_user))
    if hidden_ids:
        id_filters["$nin"] = hidden_ids
    if saved_only:
        saved_ids = list(await get_saved_podcast_ids(current_user))
        if not saved_ids:
            return {"podcasts": [], "total": 0, "page": page, "pages": 0}
        id_filters["$in"] = saved_ids
    if id_filters:
        query["id"] = id_filters

    sort_spec = [("created_at", -1)]
    if sort == "trending":
        sort_spec = [("play_count", -1), ("created_at", -1)]
    elif sort == "most_viewed":
        sort_spec = [("play_count", -1), ("created_at", -1)]
    elif sort == "highest_rated":
        sort_spec = [("rating_average", -1), ("rating_count", -1), ("play_count", -1), ("created_at", -1)]
    elif sort == "oldest":
        sort_spec = [("created_at", 1)]

    skip = (page - 1) * limit
    total = await db.podcasts.count_documents(query)
    podcasts = await db.podcasts.find(query).sort(sort_spec).skip(skip).limit(limit).to_list(limit)
    return {"podcasts": await enrich_episodes(podcasts, current_user=current_user), "total": total, "page": page, "pages": (total + limit - 1) // limit}


@api_router.get("/podcasts/my")
async def get_my_podcasts(request: Request, show_id: Optional[str] = None):
    user = await get_current_user(request)
    query = {"podcaster_id": user["_id"], "is_deleted": False}
    if show_id:
        query["show_id"] = show_id
    podcasts = await db.podcasts.find(query).sort("created_at", -1).to_list(100)
    return {"podcasts": await enrich_episodes(podcasts, current_user=user)}


@api_router.get("/podcasts/saved")
async def get_saved_podcasts(request: Request, page: int = 1, limit: int = 20):
    user = await get_current_user(request)
    saved_ids = list(await get_saved_podcast_ids(user))
    if not saved_ids:
        return {"podcasts": [], "total": 0, "page": page, "pages": 0}

    query = {"id": {"$in": saved_ids}, **build_public_episode_query(user)}
    hidden_ids = list(await get_hidden_podcast_ids(user))
    if hidden_ids:
        query["id"]["$nin"] = hidden_ids

    skip = (page - 1) * limit
    total = await db.podcasts.count_documents(query)
    podcasts = await db.podcasts.find(query).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    return {"podcasts": await enrich_episodes(podcasts, current_user=user), "total": total, "page": page, "pages": (total + limit - 1) // limit}


@api_router.get("/podcasts/{podcast_id}")
async def get_podcast(podcast_id: str, request: Request):
    current_user = await try_get_current_user(request)
    podcast = await db.podcasts.find_one({"id": podcast_id, "is_deleted": False})
    if not podcast:
        raise HTTPException(status_code=404, detail="Episode not found")
    if not can_access_episode(current_user, podcast):
        raise HTTPException(status_code=403, detail="This episode is restricted for your account")
    enriched = await enrich_episodes([podcast], current_user=current_user)
    return enriched[0]


@api_router.post("/podcasts/{podcast_id}/save")
async def save_podcast(podcast_id: str, request: Request):
    user = await get_current_user(request)
    podcast = await db.podcasts.find_one({"id": podcast_id, "is_deleted": False})
    if not podcast or not can_access_episode(user, podcast):
        raise HTTPException(status_code=404, detail="Episode not found")

    await db.saved_podcasts.update_one(
        {"user_id": user["_id"], "podcast_id": podcast_id},
        {"$set": {"show_id": podcast.get("show_id", ""), "saved_at": now_iso()}},
        upsert=True,
    )
    await db.hidden_podcasts.delete_one({"user_id": user["_id"], "podcast_id": podcast_id})
    return {"message": "Episode saved", "podcast_id": podcast_id}


@api_router.delete("/podcasts/{podcast_id}/save")
async def unsave_podcast(podcast_id: str, request: Request):
    user = await get_current_user(request)
    await db.saved_podcasts.delete_one({"user_id": user["_id"], "podcast_id": podcast_id})
    return {"message": "Episode removed from saved", "podcast_id": podcast_id}


@api_router.post("/podcasts/{podcast_id}/like")
async def like_podcast(podcast_id: str, request: Request):
    user = await get_current_user(request)
    podcast = await db.podcasts.find_one({"id": podcast_id, "is_deleted": False})
    if not podcast or not can_access_episode(user, podcast):
        raise HTTPException(status_code=404, detail="Episode not found")

    await db.podcast_likes.update_one(
        {"user_id": user["_id"], "podcast_id": podcast_id},
        {"$set": {"liked_at": now_iso()}},
        upsert=True,
    )
    engagement = await refresh_episode_engagement_fields(podcast_id)
    return {"message": "Episode liked", "podcast_id": podcast_id, **engagement}


@api_router.delete("/podcasts/{podcast_id}/like")
async def unlike_podcast(podcast_id: str, request: Request):
    user = await get_current_user(request)
    await db.podcast_likes.delete_one({"user_id": user["_id"], "podcast_id": podcast_id})
    engagement = await refresh_episode_engagement_fields(podcast_id)
    return {"message": "Episode unliked", "podcast_id": podcast_id, **engagement}


@api_router.put("/podcasts/{podcast_id}/rating")
async def rate_podcast(podcast_id: str, req: UpdatePodcastRatingRequest, request: Request):
    user = await get_current_user(request)
    podcast = await db.podcasts.find_one({"id": podcast_id, "is_deleted": False})
    if not podcast or not can_access_episode(user, podcast):
        raise HTTPException(status_code=404, detail="Episode not found")
    if req.rating < 1 or req.rating > 5:
        raise HTTPException(status_code=400, detail="Ratings must be between 1 and 5")

    await db.podcast_ratings.update_one(
        {"user_id": user["_id"], "podcast_id": podcast_id},
        {"$set": {"rating": req.rating, "rated_at": now_iso()}},
        upsert=True,
    )
    engagement = await refresh_episode_engagement_fields(podcast_id)
    return {"message": "Rating saved", "podcast_id": podcast_id, "viewer_rating": req.rating, **engagement}


@api_router.delete("/podcasts/{podcast_id}/rating")
async def clear_podcast_rating(podcast_id: str, request: Request):
    user = await get_current_user(request)
    await db.podcast_ratings.delete_one({"user_id": user["_id"], "podcast_id": podcast_id})
    engagement = await refresh_episode_engagement_fields(podcast_id)
    return {"message": "Rating cleared", "podcast_id": podcast_id, "viewer_rating": 0, **engagement}


@api_router.put("/podcasts/{podcast_id}")
async def update_podcast(
    podcast_id: str,
    request: Request,
    title: str = Form(...),
    description: str = Form(""),
    category: str = Form(DEFAULT_SHOW_CATEGORY),
    audience_rating: str = Form(ALL_AGES_RATING),
    show_id: str = Form(""),
    season_number: Optional[int] = Form(None),
    episode_number: Optional[int] = Form(None),
    thumbnail: Optional[UploadFile] = File(None),
):
    user = await get_current_user(request)
    podcast = await db.podcasts.find_one({"id": podcast_id})
    if not podcast:
        raise HTTPException(status_code=404, detail="Episode not found")
    if podcast["podcaster_id"] != user["_id"] and user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")

    show = None
    target_show_id = (show_id or podcast.get("show_id") or "").strip()
    if target_show_id:
        show = await db.shows.find_one({"id": target_show_id, "podcaster_id": podcast["podcaster_id"], "is_deleted": False})
    if show is None:
        raise HTTPException(status_code=404, detail="Show not found")

    updates = {
        "title": title.strip() or podcast["title"],
        "description": description,
        "category": (category or DEFAULT_SHOW_CATEGORY).lower(),
        "show_id": show["id"],
        "show_title": show["title"],
        "season_number": season_number,
        "episode_number": episode_number,
        "updated_at": now_iso(),
    }
    updates["keywords"] = await extract_keywords(f"{updates['title']} {updates['description']} {updates['category']} {show['title']}")
    moderation = await review_episode_safety(
        show,
        updates["title"],
        updates["description"],
        updates["category"],
        selected_rating=normalize_content_rating(audience_rating),
        generation=podcast.get("script_package") or None,
    )
    updates["audience_rating"] = MATURE_RATING if moderation.get("recommended_age_gate") == MATURE_RATING else normalize_content_rating(audience_rating)
    updates["moderation_status"] = moderation["status"]
    updates["moderation"] = moderation
    previous_thumbnail_path = (podcast.get("thumbnail_path") or "").strip()
    if thumbnail:
        thumbnail_path, _ = await store_upload(thumbnail, f"episode-thumbnails/{podcast['podcaster_id']}", "image/jpeg")
        updates["thumbnail_path"] = thumbnail_path

    await db.podcasts.update_one({"id": podcast_id}, {"$set": updates})
    if thumbnail:
        replacement_thumbnail_path = (updates.get("thumbnail_path") or "").strip()
        if previous_thumbnail_path and previous_thumbnail_path != replacement_thumbnail_path:
            cleanup_storage_paths([previous_thumbnail_path], strict=False)
    await db.shows.update_one({"id": show["id"]}, {"$set": {"updated_at": now_iso()}})
    updated = await db.podcasts.find_one({"id": podcast_id})
    enriched = await enrich_episodes([updated], current_user=user)
    return enriched[0]


@api_router.delete("/podcasts/{podcast_id}")
async def delete_podcast(podcast_id: str, request: Request):
    user = await get_current_user(request)
    podcast = await db.podcasts.find_one({"id": podcast_id})
    if not podcast:
        raise HTTPException(status_code=404, detail="Episode not found")
    if podcast["podcaster_id"] != user["_id"] and user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")

    cleanup_result = cleanup_storage_paths([podcast.get("media_path"), podcast.get("thumbnail_path")], strict=True)
    timestamp = now_iso()
    await db.podcasts.update_one(
        {"id": podcast_id},
        {
            "$set": {
                "is_deleted": True,
                "updated_at": timestamp,
                "deleted_at": timestamp,
                "storage_cleaned_at": timestamp,
            }
        },
    )
    return {"message": "Episode deleted", "storage_cleanup": cleanup_result}


@api_router.get("/podcasts/{podcast_id}/related")
async def get_related_podcasts(podcast_id: str, request: Request):
    current_user = await try_get_current_user(request)
    podcast = await db.podcasts.find_one({"id": podcast_id, "is_deleted": False})
    if not podcast:
        raise HTTPException(status_code=404, detail="Episode not found")
    if not can_access_episode(current_user, podcast):
        raise HTTPException(status_code=403, detail="This episode is restricted for your account")

    hidden_ids = list(await get_hidden_podcast_ids(current_user))
    base_query = {"id": {"$ne": podcast_id}, **build_public_episode_query(current_user)}
    if hidden_ids:
        base_query["id"]["$nin"] = hidden_ids

    related = await db.podcasts.find(
        {
            **base_query,
            "show_id": podcast.get("show_id"),
        }
    ).sort("created_at", -1).limit(6).to_list(6)

    if not related:
        related = await db.podcasts.find(
            {
                **base_query,
                "$or": [
                    {"category": podcast.get("category")},
                    {"keywords": {"$in": podcast.get("keywords", [])[:5]}},
                ],
            }
        ).sort("play_count", -1).limit(6).to_list(6)

    return {"podcasts": await enrich_episodes(related, current_user=current_user)}


@api_router.get("/podcasts/{podcast_id}/stream")
async def stream_podcast(podcast_id: str, request: Request):
    current_user = await try_get_current_user(request)
    podcast = await db.podcasts.find_one({"id": podcast_id, "is_deleted": False})
    if not podcast:
        raise HTTPException(status_code=404, detail="Episode not found")
    if not can_access_episode(current_user, podcast):
        raise HTTPException(status_code=403, detail="This episode is restricted for your account")
    if not podcast.get("is_playable", bool(podcast.get("media_path") or podcast.get("external_media_url"))):
        raise HTTPException(status_code=400, detail="This AI-created draft does not have playable media yet")

    await db.podcasts.update_one({"id": podcast_id}, {"$inc": {"play_count": 1}})
    if podcast.get("show_id"):
        await db.shows.update_one({"id": podcast["show_id"]}, {"$set": {"updated_at": now_iso()}})

    if podcast.get("external_media_url"):
        return RedirectResponse(podcast["external_media_url"])

    try:
        data, ct = get_object(podcast["media_path"])
        return Response(
            content=data,
            media_type=podcast.get("content_type", ct),
            headers={"Accept-Ranges": "bytes", "Content-Disposition": f'inline; filename="{podcast.get("original_filename", "podcast")}"'},
        )
    except Exception as e:
        logger.error(f"Stream error: {e}")
        raise HTTPException(status_code=500, detail="Failed to stream episode")


@api_router.get("/podcasts/{podcast_id}/thumbnail")
async def get_thumbnail(podcast_id: str, request: Request):
    current_user = await try_get_current_user(request)
    podcast = await db.podcasts.find_one({"id": podcast_id, "is_deleted": False})
    if not podcast:
        raise HTTPException(status_code=404, detail="Episode not found")
    if not can_access_episode(current_user, podcast):
        raise HTTPException(status_code=403, detail="This episode is restricted for your account")
    thumbnail_path = podcast.get("thumbnail_path")
    external_thumbnail_url = podcast.get("external_thumbnail_url")
    if not thumbnail_path and podcast.get("show_id"):
        show = await db.shows.find_one({"id": podcast["show_id"], "is_deleted": False})
        thumbnail_path = show.get("thumbnail_path") if show else ""
        external_thumbnail_url = external_thumbnail_url or (show.get("external_thumbnail_url") if show else "")
    if not thumbnail_path:
        if external_thumbnail_url:
            return RedirectResponse(external_thumbnail_url)
        raise HTTPException(status_code=404, detail="Thumbnail not found")
    try:
        data, ct = get_object(thumbnail_path)
        return Response(content=data, media_type=ct)
    except Exception as e:
        logger.error(f"Thumbnail error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get thumbnail")


@api_router.post("/podcasts/{podcast_id}/view")
async def record_view(podcast_id: str, request: Request):
    user = await get_current_user(request)
    podcast = await db.podcasts.find_one({"id": podcast_id, "is_deleted": False})
    if not podcast or not can_access_episode(user, podcast):
        raise HTTPException(status_code=404, detail="Episode not found")
    await db.view_history.update_one(
        {"user_id": user["_id"], "podcast_id": podcast_id},
        {"$set": {"viewed_at": now_iso()}},
        upsert=True,
    )
    await db.playback_progress.update_one(
        {"user_id": user["_id"], "podcast_id": podcast_id},
        {
            "$set": {"last_played_at": now_iso(), "last_event_type": "started"},
            "$setOnInsert": {
                "user_id": user["_id"],
                "podcast_id": podcast_id,
                "progress_seconds": 0,
                "duration_seconds": 0,
                "progress_percent": 0,
                "is_completed": False,
                "started_at": now_iso(),
            },
        },
        upsert=True,
    )
    return {"message": "View recorded"}


@api_router.post("/podcasts/{podcast_id}/progress")
async def update_playback_progress(podcast_id: str, req: UpdatePlaybackProgressRequest, request: Request):
    user = await get_current_user(request)
    podcast = await db.podcasts.find_one({"id": podcast_id, "is_deleted": False})
    if not podcast:
        raise HTTPException(status_code=404, detail="Episode not found")
    if not can_access_episode(user, podcast):
        raise HTTPException(status_code=403, detail="This episode is restricted for your account")

    existing = await db.playback_progress.find_one({"user_id": user["_id"], "podcast_id": podcast_id})
    progress_seconds = max(0.0, float(req.progress_seconds or 0))
    duration_seconds = max(progress_seconds, float(req.duration_seconds or 0), float((existing or {}).get("duration_seconds", 0) or 0))
    progress_percent = min(100.0, round((progress_seconds / duration_seconds) * 100, 1)) if duration_seconds else 0.0
    is_completed = req.event_type == "completed" or progress_percent >= 95
    if is_completed and duration_seconds:
        progress_seconds = duration_seconds
        progress_percent = 100.0

    timestamp = now_iso()
    await db.playback_progress.update_one(
        {"user_id": user["_id"], "podcast_id": podcast_id},
        {
            "$set": {
                "user_id": user["_id"],
                "podcast_id": podcast_id,
                "show_id": podcast.get("show_id", ""),
                "progress_seconds": progress_seconds,
                "duration_seconds": duration_seconds,
                "progress_percent": progress_percent,
                "is_completed": is_completed,
                "last_played_at": timestamp,
                "last_event_type": req.event_type or "progress",
            },
            "$setOnInsert": {
                "started_at": timestamp,
            },
        },
        upsert=True,
    )
    if is_completed:
        await db.playback_progress.update_one(
            {"user_id": user["_id"], "podcast_id": podcast_id},
            {"$set": {"completed_at": timestamp}},
        )

    await db.view_history.update_one(
        {"user_id": user["_id"], "podcast_id": podcast_id},
        {"$set": {"viewed_at": timestamp}},
        upsert=True,
    )
    return {
        "podcast_id": podcast_id,
        "progress_seconds": progress_seconds,
        "duration_seconds": duration_seconds,
        "progress_percent": progress_percent,
        "is_completed": is_completed,
    }


@api_router.get("/listening/continue")
async def get_continue_listening(request: Request, limit: int = 8):
    user = await get_current_user(request)
    rows = await db.playback_progress.find(
        {
            "user_id": user["_id"],
            "is_completed": False,
            "progress_seconds": {"$gt": 30},
            "progress_percent": {"$lt": 95},
        }
    ).sort("last_played_at", -1).limit(limit).to_list(limit)
    if not rows:
        return {"podcasts": []}
    episode_ids = [row["podcast_id"] for row in rows if row.get("podcast_id")]
    podcasts = await db.podcasts.find({"id": {"$in": episode_ids}, **build_public_episode_query(user)}).to_list(len(episode_ids))
    enriched = await enrich_episodes(podcasts, current_user=user)
    episode_map = {podcast["id"]: podcast for podcast in enriched}
    ordered = [episode_map[podcast_id] for podcast_id in episode_ids if podcast_id in episode_map]
    return {"podcasts": ordered}


@api_router.get("/listening/history")
async def get_listening_history(request: Request, limit: int = 10):
    user = await get_current_user(request)
    rows = await db.playback_progress.find({"user_id": user["_id"]}).sort("last_played_at", -1).limit(limit).to_list(limit)
    if not rows:
        return {"podcasts": []}
    episode_ids = [row["podcast_id"] for row in rows if row.get("podcast_id")]
    podcasts = await db.podcasts.find({"id": {"$in": episode_ids}, **build_public_episode_query(user)}).to_list(len(episode_ids))
    enriched = await enrich_episodes(podcasts, current_user=user)
    episode_map = {podcast["id"]: podcast for podcast in enriched}
    ordered = [episode_map[podcast_id] for podcast_id in episode_ids if podcast_id in episode_map]
    return {"podcasts": ordered}


@api_router.post("/podcasts/{podcast_id}/not-interested")
async def hide_podcast_from_feed(podcast_id: str, request: Request):
    user = await get_current_user(request)
    podcast = await db.podcasts.find_one({"id": podcast_id, "is_deleted": False})
    if not podcast or not can_access_episode(user, podcast):
        raise HTTPException(status_code=404, detail="Episode not found")

    await db.hidden_podcasts.update_one(
        {"user_id": user["_id"], "podcast_id": podcast_id},
        {"$set": {"show_id": podcast.get("show_id", ""), "hidden_at": now_iso()}},
        upsert=True,
    )
    await db.saved_podcasts.delete_one({"user_id": user["_id"], "podcast_id": podcast_id})
    return {"message": "Episode hidden from recommendations", "podcast_id": podcast_id}


@api_router.delete("/podcasts/{podcast_id}/not-interested")
async def restore_podcast_to_feed(podcast_id: str, request: Request):
    user = await get_current_user(request)
    await db.hidden_podcasts.delete_one({"user_id": user["_id"], "podcast_id": podcast_id})
    return {"message": "Episode restored to recommendations", "podcast_id": podcast_id}


@api_router.get("/recommendations")
async def get_recommendations(request: Request, sort: str = "smart"):
    user = await get_current_user(request)
    user_interests = user.get("interests", [])
    hidden_ids = list(await get_hidden_podcast_ids(user))

    progress_history = await db.playback_progress.find(
        {
            "user_id": user["_id"],
            "$or": [
                {"progress_seconds": {"$gte": 30}},
                {"progress_percent": {"$gte": 15}},
                {"is_completed": True},
            ],
        }
    ).sort("last_played_at", -1).to_list(50)
    viewed_ids = [row["podcast_id"] for row in progress_history if row.get("podcast_id")]
    if not viewed_ids:
        history = await db.view_history.find({"user_id": user["_id"]}).to_list(50)
        viewed_ids = [h["podcast_id"] for h in history]
    viewed_keywords = []
    if viewed_ids:
        viewed_podcasts = await db.podcasts.find({"id": {"$in": viewed_ids}}, {"keywords": 1, "_id": 0}).to_list(50)
        for viewed in viewed_podcasts:
            viewed_keywords.extend(viewed.get("keywords", []))
        viewed_keywords = list(set(viewed_keywords))

    base_query = build_public_episode_query(user)
    if hidden_ids:
        base_query["id"] = {"$nin": hidden_ids}

    all_podcasts = await db.podcasts.find(base_query).to_list(100)
    if not all_podcasts:
        return {"podcasts": [], "method": "empty"}

    ai_ids = await get_ai_recommendations(user_interests, viewed_keywords, all_podcasts)
    method = "popular"
    ordered = []
    if ai_ids:
        podcast_map = {p["id"]: p for p in all_podcasts}
        ordered = [podcast_map[pid] for pid in ai_ids if pid in podcast_map]
        method = "ai"

    if not ordered:
        all_terms = list(set(user_interests + viewed_keywords))
        if all_terms:
            ordered = await db.podcasts.find(
                {**base_query, "keywords": {"$in": all_terms}}
            ).sort("play_count", -1).limit(20).to_list(20)
            method = "keyword" if ordered else "popular"

    if not ordered:
        ordered = await db.podcasts.find(base_query).sort("play_count", -1).limit(20).to_list(20)

    enriched = await enrich_episodes(ordered[:20], current_user=user)
    if sort == "highest_rated":
        enriched = sorted(
            enriched,
            key=lambda episode: (
                float(episode.get("rating_average", 0) or 0),
                int(episode.get("rating_count", 0) or 0),
                int(episode.get("play_count", 0) or 0),
            ),
            reverse=True,
        )
    elif sort == "most_viewed":
        enriched = sorted(
            enriched,
            key=lambda episode: (
                int(episode.get("play_count", 0) or 0),
                float(episode.get("rating_average", 0) or 0),
            ),
            reverse=True,
        )
    for episode in enriched:
        episode["recommendation_reason"] = build_recommendation_reason(episode, user_interests, viewed_keywords, method)
    return {"podcasts": enriched, "method": method, "sort": sort}


@api_router.get("/categories")
async def get_categories():
    podcast_categories = await db.podcasts.distinct("category", build_public_episode_query())
    show_categories = await db.shows.distinct("category", {"is_deleted": False})
    cats = sorted({c for c in podcast_categories + show_categories if c})
    return {"categories": cats}


@api_router.get("/trending")
async def get_trending(request: Request):
    current_user = await try_get_current_user(request)
    query = build_public_episode_query(current_user)
    hidden_ids = list(await get_hidden_podcast_ids(current_user))
    if hidden_ids:
        query["id"] = {"$nin": hidden_ids}
    podcasts = await db.podcasts.find(query).sort("play_count", -1).limit(10).to_list(10)
    return {"podcasts": await enrich_episodes(podcasts, current_user=current_user)}


INTEREST_OPTIONS = [
    "technology",
    "science",
    "business",
    "health",
    "education",
    "entertainment",
    "sports",
    "politics",
    "music",
    "comedy",
    "true crime",
    "history",
    "philosophy",
    "art",
    "gaming",
    "finance",
    "travel",
    "food",
    "lifestyle",
    "spirituality",
    "self improvement",
    "news",
    "culture",
    "environment",
    "psychology",
]


@api_router.get("/interests/options")
async def get_interest_options():
    return {"interests": INTEREST_OPTIONS}


@api_router.get("/health")
async def health_check():
    return {"status": "ok"}


app.include_router(api_router)

cors_origin_setting = os.environ.get("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
cors_origins = [origin.strip() for origin in cors_origin_setting.split(",") if origin.strip()]
allow_origin_regex = r"https?://.*" if cors_origin_setting.strip() == "*" else None
app.add_middleware(
    CORSMiddleware,
    allow_origins=[] if allow_origin_regex else cors_origins,
    allow_origin_regex=allow_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if FRONTEND_BUILD_DIR.exists():
    static_dir = FRONTEND_BUILD_DIR / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=static_dir), name="frontend-static")

    @app.get("/", include_in_schema=False)
    async def serve_frontend_index():
        return FileResponse(FRONTEND_BUILD_DIR / "index.html")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_frontend_app(full_path: str):
        if full_path == "api" or full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not Found")
        requested_path = FRONTEND_BUILD_DIR / full_path
        if requested_path.is_file():
            return FileResponse(requested_path)
        return FileResponse(FRONTEND_BUILD_DIR / "index.html")


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
