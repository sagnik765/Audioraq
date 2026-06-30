"""Public Audioraq text-to-audio API and developer key management."""

from __future__ import annotations

import asyncio
import hashlib
import os
import re
import secrets
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable, Dict, List, Literal, Optional

from fastapi import APIRouter, HTTPException, Request, Response, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field, field_validator
from pymongo import ReturnDocument


API_KEY_PREFIX = "arq_live_"
API_SCOPE_SPEECH = "audio:speech"
QUALITY_PROFILES = {
    "podcast-dialogue",
    "podcast-education-calm",
    "podcast-storytelling",
}
api_key_bearer = HTTPBearer(
    auto_error=False,
    scheme_name="AudioraqApiKey",
    description="A developer key beginning with arq_live_. Create one at /developers.",
)


class CreateDeveloperKeyRequest(BaseModel):
    name: str = Field(default="Default", min_length=1, max_length=80)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = re.sub(r"\s+", " ", value).strip()
        if not normalized:
            raise ValueError("Key name is required")
        return normalized


class TextToAudioRequest(BaseModel):
    input: str = Field(min_length=1, max_length=20_000)
    voice: str = "aman-warm-analyst"
    format: Literal["mp3", "wav"] = "mp3"
    quality_profile: Literal[
        "podcast-dialogue",
        "podcast-education-calm",
        "podcast-storytelling",
    ] = "podcast-education-calm"

    @field_validator("input")
    @classmethod
    def normalize_input(cls, value: str) -> str:
        normalized = re.sub(r"[\t\r ]+", " ", value).strip()
        if not normalized:
            raise ValueError("Input text is required")
        return normalized


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def int_env(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.environ.get(name, default))
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(maximum, value))


def hash_api_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def generate_api_key() -> str:
    return f"{API_KEY_PREFIX}{secrets.token_urlsafe(32)}"


def extract_api_key(request: Request) -> str:
    explicit = (request.headers.get("X-Audioraq-Key") or request.headers.get("X-API-Key") or "").strip()
    if explicit:
        return explicit
    authorization = (request.headers.get("Authorization") or "").strip()
    if authorization.lower().startswith("bearer "):
        candidate = authorization[7:].strip()
        if candidate.startswith(API_KEY_PREFIX):
            return candidate
    return ""


def public_key_document(document: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": document["id"],
        "name": document.get("name", "API key"),
        "prefix": document.get("display_prefix", ""),
        "scopes": document.get("scopes", []),
        "created_at": document.get("created_at"),
        "last_used_at": document.get("last_used_at"),
        "requests_count": int(document.get("requests_count", 0) or 0),
        "characters_count": int(document.get("characters_count", 0) or 0),
    }


async def enforce_key_rate_limit(db: Any, key_id: str) -> Dict[str, int]:
    limit = int_env("TEXT_TO_AUDIO_RATE_LIMIT_PER_MINUTE", 30, 1, 10_000)
    now = utc_now()
    minute_bucket = int(now.timestamp() // 60)
    bucket_id = hashlib.sha256(f"tts:{key_id}:{minute_bucket}".encode("utf-8")).hexdigest()
    document = await db.text_to_audio_rate_limits.find_one_and_update(
        {"_id": bucket_id},
        {
            "$setOnInsert": {
                "key_id": key_id,
                "created_at": now,
                "expires_at": now + timedelta(minutes=2),
            },
            "$inc": {"requests": 1},
        },
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    used = int((document or {}).get("requests", 1))
    reset_seconds = max(1, 60 - (int(now.timestamp()) % 60))
    if used > limit:
        raise HTTPException(
            status_code=429,
            detail="Text-to-audio rate limit exceeded. Retry after the current minute.",
            headers={"Retry-After": str(reset_seconds)},
        )
    return {"limit": limit, "remaining": max(0, limit - used), "reset": reset_seconds}


async def authenticate_api_key(db: Any, request: Request) -> Dict[str, Any]:
    raw_key = extract_api_key(request)
    if not raw_key or not raw_key.startswith(API_KEY_PREFIX):
        raise HTTPException(
            status_code=401,
            detail="A valid Audioraq API key is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    document = await db.developer_api_keys.find_one(
        {"key_hash": hash_api_key(raw_key), "revoked_at": None}
    )
    if not document or API_SCOPE_SPEECH not in document.get("scopes", []):
        raise HTTPException(
            status_code=401,
            detail="The Audioraq API key is invalid or revoked.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    document["rate_limit"] = await enforce_key_rate_limit(db, document["id"])
    return document


async def ensure_text_to_audio_indexes(db: Any) -> None:
    await db.developer_api_keys.create_index("id", unique=True)
    await db.developer_api_keys.create_index("key_hash", unique=True)
    await db.developer_api_keys.create_index([("user_id", 1), ("created_at", -1)])
    await db.text_to_audio_usage.create_index("request_id", unique=True)
    await db.text_to_audio_usage.create_index([("key_id", 1), ("created_at", -1)])
    await db.text_to_audio_usage.create_index([("user_id", 1), ("created_at", -1)])
    await db.text_to_audio_rate_limits.create_index("expires_at", expireAfterSeconds=0)


def build_text_to_audio_router(
    *,
    db: Any,
    get_current_user: Callable[[Request], Awaitable[Dict[str, Any]]],
    render_audio: Callable[[str, Optional[List[Dict[str, str]]], str, str], Dict[str, Any]],
    voices: List[Dict[str, Any]],
    public_voice: Callable[[Dict[str, Any]], Dict[str, Any]],
) -> APIRouter:
    router = APIRouter()
    voice_by_id = {voice["id"]: voice for voice in voices}

    @router.get("/v1/audio/voices", tags=["Text to Audio"])
    async def list_text_to_audio_voices():
        return {
            "object": "list",
            "data": [public_voice(voice) for voice in voices],
            "default": "aman-warm-analyst",
            "quality_profiles": sorted(QUALITY_PROFILES),
        }

    @router.post("/v1/audio/speech", tags=["Text to Audio"])
    async def create_speech(
        req: TextToAudioRequest,
        request: Request,
        _credentials: Optional[HTTPAuthorizationCredentials] = Security(api_key_bearer),
    ):
        started_at = time.perf_counter()
        key_document = await authenticate_api_key(db, request)
        max_characters = int_env("TEXT_TO_AUDIO_MAX_CHARACTERS", 5_000, 100, 20_000)
        if len(req.input) > max_characters:
            raise HTTPException(
                status_code=413,
                detail=f"Input exceeds the {max_characters}-character request limit.",
            )
        if req.voice not in voice_by_id:
            raise HTTPException(status_code=400, detail=f"Unknown voice '{req.voice}'.")

        request_id = f"tts_{uuid.uuid4().hex}"
        voice = voice_by_id[req.voice]
        turns = [
            {
                "speaker": voice.get("name") or "Narrator",
                "voice_role": "narrator",
                "voice_id": req.voice,
                "text": req.input,
            }
        ]
        try:
            rendered = await asyncio.to_thread(
                render_audio,
                req.input,
                turns,
                req.format,
                req.quality_profile,
            )
        except HTTPException as exc:
            if exc.status_code < 500:
                raise
            raise HTTPException(status_code=502, detail="The audio renderer could not complete this request.") from exc
        except Exception as exc:
            raise HTTPException(status_code=502, detail="The audio renderer could not complete this request.") from exc

        audio = rendered.get("data") or b""
        if len(audio) < 1_024:
            raise HTTPException(status_code=502, detail="The audio renderer returned an incomplete file.")
        content_type = str(rendered.get("content_type") or ("audio/mpeg" if req.format == "mp3" else "audio/wav"))
        actual_extension = str(rendered.get("extension") or ("mp3" if content_type == "audio/mpeg" else "wav"))
        latency_ms = round((time.perf_counter() - started_at) * 1_000)
        created_at = utc_now()

        usage = {
            "request_id": request_id,
            "key_id": key_document["id"],
            "user_id": key_document["user_id"],
            "character_count": len(req.input),
            "voice": req.voice,
            "format_requested": req.format,
            "format_delivered": actual_extension,
            "quality_profile": req.quality_profile,
            "provider": rendered.get("provider", ""),
            "provider_kind": rendered.get("provider_kind", ""),
            "model": rendered.get("model", ""),
            "output_bytes": len(audio),
            "latency_ms": latency_ms,
            "status": "succeeded",
            "created_at": created_at,
        }
        await db.text_to_audio_usage.insert_one(usage)
        await db.developer_api_keys.update_one(
            {"id": key_document["id"]},
            {
                "$set": {"last_used_at": created_at},
                "$inc": {"requests_count": 1, "characters_count": len(req.input)},
            },
        )

        rate = key_document["rate_limit"]
        headers = {
            "Content-Disposition": f'inline; filename="audioraq-{request_id}.{actual_extension}"',
            "Cache-Control": "no-store",
            "X-Request-Id": request_id,
            "X-Audioraq-Voice": req.voice,
            "X-Audioraq-Provider": str(rendered.get("provider", "")),
            "X-Audioraq-Model": str(rendered.get("model", "")),
            "X-Audioraq-Characters": str(len(req.input)),
            "X-RateLimit-Limit": str(rate["limit"]),
            "X-RateLimit-Remaining": str(rate["remaining"]),
            "X-RateLimit-Reset": str(rate["reset"]),
        }
        return Response(content=audio, media_type=content_type, headers=headers)

    @router.get("/developer/api-keys", tags=["Developer"])
    async def list_developer_keys(request: Request):
        user = await get_current_user(request)
        documents = await db.developer_api_keys.find(
            {"user_id": str(user["_id"]), "revoked_at": None}
        ).sort("created_at", -1).to_list(25)
        return {"keys": [public_key_document(document) for document in documents]}

    @router.post("/developer/api-keys", tags=["Developer"])
    async def create_developer_key(req: CreateDeveloperKeyRequest, request: Request):
        user = await get_current_user(request)
        user_id = str(user["_id"])
        max_active_keys = int_env("TEXT_TO_AUDIO_MAX_ACTIVE_KEYS", 5, 1, 25)
        active_count = await db.developer_api_keys.count_documents(
            {"user_id": user_id, "revoked_at": None}
        )
        if active_count >= max_active_keys:
            raise HTTPException(
                status_code=409,
                detail=f"You can have up to {max_active_keys} active API keys.",
            )

        raw_key = generate_api_key()
        now = utc_now()
        document = {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "name": req.name,
            "key_hash": hash_api_key(raw_key),
            "display_prefix": f"{raw_key[:16]}...{raw_key[-4:]}",
            "scopes": [API_SCOPE_SPEECH],
            "requests_count": 0,
            "characters_count": 0,
            "created_at": now,
            "last_used_at": None,
            "revoked_at": None,
        }
        await db.developer_api_keys.insert_one(document)
        return {
            "key": raw_key,
            "api_key": public_key_document(document),
            "warning": "Store this key securely. Audioraq will not show it again.",
        }

    @router.delete("/developer/api-keys/{key_id}", tags=["Developer"])
    async def revoke_developer_key(key_id: str, request: Request):
        user = await get_current_user(request)
        result = await db.developer_api_keys.update_one(
            {"id": key_id, "user_id": str(user["_id"]), "revoked_at": None},
            {"$set": {"revoked_at": utc_now()}},
        )
        if result.modified_count != 1:
            raise HTTPException(status_code=404, detail="API key not found.")
        return {"message": "API key revoked."}

    @router.get("/developer/usage", tags=["Developer"])
    async def get_developer_usage(request: Request):
        user = await get_current_user(request)
        user_id = str(user["_id"])
        totals = await db.text_to_audio_usage.aggregate(
            [
                {"$match": {"user_id": user_id, "status": "succeeded"}},
                {
                    "$group": {
                        "_id": None,
                        "requests": {"$sum": 1},
                        "characters": {"$sum": "$character_count"},
                        "output_bytes": {"$sum": "$output_bytes"},
                        "average_latency_ms": {"$avg": "$latency_ms"},
                    }
                },
            ]
        ).to_list(1)
        summary = totals[0] if totals else {}
        return {
            "requests": int(summary.get("requests", 0) or 0),
            "characters": int(summary.get("characters", 0) or 0),
            "output_bytes": int(summary.get("output_bytes", 0) or 0),
            "average_latency_ms": round(float(summary.get("average_latency_ms", 0) or 0)),
            "text_retained": False,
        }

    return router
