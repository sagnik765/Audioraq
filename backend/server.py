from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
PROJECT_DIR = ROOT_DIR.parent
load_dotenv(ROOT_DIR / ".env")

from fastapi import APIRouter, FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field
from starlette.middleware.cors import CORSMiddleware

from array import array
import bcrypt
import asyncio
import base64
import email.utils
import hashlib
import io
import ipaddress
import json
import jwt
import logging
import math
import mimetypes
import os
import re
import requests
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import textwrap
import time
import uuid
import wave
import xml.etree.ElementTree as ET
import zipfile

from bson import ObjectId
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterator, List, Literal, Optional, Set, Tuple
from urllib.parse import quote, urlencode, urljoin, urlparse

from cryptography.fernet import Fernet, InvalidToken
from backend.voice_quality import (
    build_voice_context_from_intake,
    is_proof_studio_provider,
    score_podcast_voice_listenability,
)
from PIL import Image, ImageDraw, ImageFont


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)
social_queue_lock = None


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
SOCIAL_PUBLISH_PROVIDER_LINKEDIN = "linkedin"
SOCIAL_PUBLISH_PROVIDER_INSTAGRAM = "instagram"
SUPPORTED_SOCIAL_PUBLISH_PROVIDERS = {
    SOCIAL_PUBLISH_PROVIDER_LINKEDIN,
    SOCIAL_PUBLISH_PROVIDER_INSTAGRAM,
}
SOCIAL_POST_STATUS_DRAFT = "draft"
SOCIAL_POST_STATUS_QUEUED = "queued"
SOCIAL_POST_STATUS_PUBLISHING = "publishing"
SOCIAL_POST_STATUS_PUBLISHED = "published"
SOCIAL_POST_STATUS_FAILED = "failed"
SOCIAL_POST_STATUSES = {
    SOCIAL_POST_STATUS_DRAFT,
    SOCIAL_POST_STATUS_QUEUED,
    SOCIAL_POST_STATUS_PUBLISHING,
    SOCIAL_POST_STATUS_PUBLISHED,
    SOCIAL_POST_STATUS_FAILED,
}
LINKEDIN_DEFAULT_VERSION = os.environ.get("LINKEDIN_VERSION", "202604").strip() or "202604"
META_GRAPH_VERSION = os.environ.get("META_GRAPH_VERSION", "v22.0").strip() or "v22.0"
try:
    SOCIAL_QUEUE_POLL_SECONDS = max(15, int(os.environ.get("SOCIAL_QUEUE_POLL_SECONDS", 45)))
except (TypeError, ValueError):
    SOCIAL_QUEUE_POLL_SECONDS = 45
try:
    SOCIAL_QUEUE_BATCH_SIZE = max(1, min(20, int(os.environ.get("SOCIAL_QUEUE_BATCH_SIZE", 5))))
except (TypeError, ValueError):
    SOCIAL_QUEUE_BATCH_SIZE = 5
AGENT2_VERSION = "2026-04-19.0"
AI_TEXT_PROVIDER_DETERMINISTIC = "deterministic"
AI_TEXT_PROVIDER_EMERGENT = "emergent"
AI_TEXT_PROVIDER_OLLAMA = "ollama"
AI_TEXT_PROVIDERS = {AI_TEXT_PROVIDER_DETERMINISTIC, AI_TEXT_PROVIDER_EMERGENT, AI_TEXT_PROVIDER_OLLAMA}

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
    "Reward warm resonance and crisp articulation that reduce long-form listening fatigue.",
    "Penalize unsafe, hateful, or harmful claims found by RAG safety retrieval.",
    "Penalize AI-sounding repetition, vague buzzwords, and overlong sentences.",
    "Preserve the creator's chosen audience, tone, and episode goal.",
]

AI_AUDIO_VOICE_ROLES = {"host", "guest", "narrator"}
AI_AUDIO_DISCLOSURE = "This episode includes AI-generated voice audio."
PROOF_STUDIO_LOCAL_FILTER = "highpass=f=80,lowpass=f=12000,loudnorm=I=-16:TP=-1.5:LRA=11"
PROOF_STUDIO_APPLE_GAP_SECONDS = 1.0
PROOF_STUDIO_APPLE_NARRATIVE_GAP_SECONDS = 1.0
PROOF_STUDIO_APPLE_TARGET_PEAK_DBFS = -4.5
PROOF_STUDIO_APPLE_RATES = {
    "host": 100,
    "guest": 98,
    "narrator": 96,
}
PROOF_STUDIO_APPLE_NARRATIVE_RATES = {
    "host": 100,
    "guest": 98,
    "narrator": 96,
}
PROOF_STUDIO_APPLE_VOICES = {
    "host": ["Aman", "Daniel", "Alex"],
    "guest": ["Samantha", "Ava", "Victoria"],
    "narrator": ["Samantha", "Aman", "Alex"],
}
AI_PODCAST_VOICE_LIBRARY: List[Dict[str, Any]] = [
    {
        "id": "aman-warm-analyst",
        "name": "Aman",
        "gender": "male",
        "style": "warm analyst",
        "accent": "Indian English",
        "description": "Warm, steady, and trustworthy for education or finance.",
        "suggested_roles": ["host", "narrator"],
        "apple_voices": ["Aman", "Aman (English (India))"],
        "kokoro_voice": "am_michael",
        "openai_voice": "ash",
        "espeak": {"voice": "en-in+m3", "speed": "148", "pitch": "46", "amplitude": "142"},
        "rate_wpm": 110,
    },
    {
        "id": "rishi-clear-guide",
        "name": "Rishi",
        "gender": "male",
        "style": "clear guide",
        "accent": "Indian English",
        "description": "Crisp and composed for explainers and founder conversations.",
        "suggested_roles": ["host", "guest"],
        "apple_voices": ["Rishi"],
        "kokoro_voice": "am_adam",
        "openai_voice": "sage",
        "espeak": {"voice": "en-in+m2", "speed": "146", "pitch": "44", "amplitude": "142"},
        "rate_wpm": 112,
    },
    {
        "id": "daniel-calm-british",
        "name": "Daniel",
        "gender": "male",
        "style": "calm British host",
        "accent": "American English",
        "description": "Polished and calm for law, current affairs, and long-form analysis.",
        "suggested_roles": ["host", "narrator"],
        "apple_voices": ["Daniel"],
        "kokoro_voice": "bm_daniel",
        "openai_voice": "onyx",
        "espeak": {"voice": "en-gb+m3", "speed": "146", "pitch": "43", "amplitude": "140"},
        "rate_wpm": 112,
    },
    {
        "id": "reed-bright-teacher",
        "name": "Reed",
        "gender": "male",
        "style": "clear teacher",
        "accent": "warm Indian English",
        "description": "Friendly and articulate for practical tutorials.",
        "suggested_roles": ["host", "guest"],
        "apple_voices": ["Rishi"],
        "kokoro_voice": "am_michael",
        "openai_voice": "echo",
        "espeak": {"voice": "en-in+m2", "speed": "146", "pitch": "44", "amplitude": "142"},
        "rate_wpm": 112,
    },
    {
        "id": "eddy-casual-host",
        "name": "Eddy",
        "gender": "male",
        "style": "casual host",
        "accent": "warm Indian English",
        "description": "Conversational and approachable for creator-led shows.",
        "suggested_roles": ["host", "guest"],
        "apple_voices": ["Rishi"],
        "kokoro_voice": "am_adam",
        "openai_voice": "verse",
        "espeak": {"voice": "en-in+m2", "speed": "146", "pitch": "44", "amplitude": "142"},
        "rate_wpm": 112,
    },
    {
        "id": "rocko-energetic-host",
        "name": "Rocko",
        "gender": "male",
        "style": "energetic host",
        "accent": "American English",
        "description": "More energetic without rushing; useful for technology and startup topics.",
        "suggested_roles": ["host", "guest"],
        "apple_voices": ["Rocko (English (US))", "Rocko"],
        "kokoro_voice": "am_adam",
        "openai_voice": "ash",
        "espeak": {"voice": "en-us+m5", "speed": "152", "pitch": "52", "amplitude": "140"},
        "rate_wpm": 220,
    },
    {
        "id": "grandpa-wise-narrator",
        "name": "Grandpa",
        "gender": "male",
        "style": "wise narrator",
        "accent": "American English",
        "description": "Grounded and patient for reflective storytelling.",
        "suggested_roles": ["narrator", "guest"],
        "apple_voices": ["Grandpa (English (US))", "Grandpa"],
        "kokoro_voice": "am_michael",
        "openai_voice": "onyx",
        "espeak": {"voice": "en-us+m1", "speed": "138", "pitch": "38", "amplitude": "138"},
        "rate_wpm": 152,
    },
    {
        "id": "oliver-uk-commentator",
        "name": "Oliver",
        "gender": "male",
        "style": "UK commentator",
        "accent": "British English",
        "description": "Composed and conversational for business and current-affairs contrast.",
        "suggested_roles": ["guest", "narrator"],
        "apple_voices": ["Eddy (English (UK))"],
        "kokoro_voice": "bm_daniel",
        "openai_voice": "echo",
        "espeak": {"voice": "en-gb+m2", "speed": "148", "pitch": "45", "amplitude": "137"},
        "rate_wpm": 220,
    },
    {
        "id": "rowan-uk-analyst",
        "name": "Rowan",
        "gender": "male",
        "style": "UK analyst",
        "accent": "British English",
        "description": "Crisp, slightly brighter analyst voice for explainers.",
        "suggested_roles": ["host", "guest"],
        "apple_voices": ["Reed (English (UK))"],
        "kokoro_voice": "bm_daniel",
        "openai_voice": "sage",
        "espeak": {"voice": "en-gb+m3", "speed": "149", "pitch": "47", "amplitude": "138"},
        "rate_wpm": 162,
    },
    {
        "id": "roman-uk-host",
        "name": "Roman",
        "gender": "male",
        "style": "energetic host",
        "accent": "American English",
        "description": "Energetic but controlled for technology and startup discussions.",
        "suggested_roles": ["host", "guest"],
        "apple_voices": ["Rocko (English (US))", "Rocko"],
        "kokoro_voice": "am_adam",
        "openai_voice": "verse",
        "espeak": {"voice": "en-gb+m4", "speed": "150", "pitch": "50", "amplitude": "139"},
        "rate_wpm": 220,
    },
    {
        "id": "samantha-warm-cohost",
        "name": "Samantha",
        "gender": "female",
        "style": "warm co-host",
        "accent": "American English",
        "description": "Warm, clear, and easy to stay with for long listening.",
        "suggested_roles": ["host", "guest", "narrator"],
        "apple_voices": ["Samantha"],
        "kokoro_voice": "af_sarah",
        "openai_voice": "nova",
        "espeak": {"voice": "en-us+f3", "speed": "146", "pitch": "58", "amplitude": "136"},
        "rate_wpm": 112,
    },
    {
        "id": "tara-bright-indian",
        "name": "Tara",
        "gender": "female",
        "style": "bright Indian host",
        "accent": "Indian English",
        "description": "Bright and precise for education, health, and creator shows.",
        "suggested_roles": ["host", "guest"],
        "apple_voices": ["Samantha"],
        "kokoro_voice": "af_bella",
        "openai_voice": "coral",
        "espeak": {"voice": "en-in+f3", "speed": "146", "pitch": "59", "amplitude": "136"},
        "rate_wpm": 112,
    },
    {
        "id": "flo-friendly-guide",
        "name": "Flo",
        "gender": "female",
        "style": "friendly guide",
        "accent": "American English",
        "description": "Friendly and modern for onboarding-style episodes.",
        "suggested_roles": ["host", "guest"],
        "apple_voices": ["Tara"],
        "kokoro_voice": "af_bella",
        "openai_voice": "shimmer",
        "espeak": {"voice": "en-us+f4", "speed": "148", "pitch": "61", "amplitude": "135"},
        "rate_wpm": 112,
    },
    {
        "id": "sandy-calm-educator",
        "name": "Sandy",
        "gender": "female",
        "style": "calm educator",
        "accent": "American English",
        "description": "Clear, relaxed, and teacherly for explainers.",
        "suggested_roles": ["host", "narrator"],
        "apple_voices": ["Samantha"],
        "kokoro_voice": "af_sarah",
        "openai_voice": "alloy",
        "espeak": {"voice": "en-us+f2", "speed": "144", "pitch": "57", "amplitude": "136"},
        "rate_wpm": 112,
    },
    {
        "id": "shelley-story-host",
        "name": "Shelley",
        "gender": "female",
        "style": "story host",
        "accent": "American English",
        "description": "Expressive but controlled for narrative shows.",
        "suggested_roles": ["host", "narrator"],
        "apple_voices": ["Samantha"],
        "kokoro_voice": "af_sarah",
        "openai_voice": "nova",
        "espeak": {"voice": "en-us+f5", "speed": "143", "pitch": "60", "amplitude": "136"},
        "rate_wpm": 112,
    },
    {
        "id": "grandma-reflective-narrator",
        "name": "Grandma",
        "gender": "female",
        "style": "reflective narrator",
        "accent": "American English",
        "description": "Patient and intimate for reflective narration.",
        "suggested_roles": ["narrator", "guest"],
        "apple_voices": ["Samantha"],
        "kokoro_voice": "af_bella",
        "openai_voice": "shimmer",
        "espeak": {"voice": "en-us+f1", "speed": "136", "pitch": "52", "amplitude": "134"},
        "rate_wpm": 112,
    },
    {
        "id": "karen-australian-guide",
        "name": "Karen",
        "gender": "female",
        "style": "Australian guide",
        "accent": "Australian English",
        "description": "Clean and composed for global business and environment shows.",
        "suggested_roles": ["host", "guest"],
        "apple_voices": ["Karen"],
        "kokoro_voice": "af_bella",
        "openai_voice": "coral",
        "espeak": {"voice": "en-au+f3", "speed": "145", "pitch": "57", "amplitude": "136"},
        "rate_wpm": 112,
    },
    {
        "id": "moira-irish-storyteller",
        "name": "Moira",
        "gender": "female",
        "style": "reflective storyteller",
        "accent": "warm neutral English",
        "description": "Textured and warm for story-led episodes.",
        "suggested_roles": ["narrator", "guest"],
        "apple_voices": ["Samantha"],
        "kokoro_voice": "af_sarah",
        "openai_voice": "fable",
        "espeak": {"voice": "en-us+f3", "speed": "144", "pitch": "57", "amplitude": "136"},
        "rate_wpm": 112,
    },
    {
        "id": "tessa-global-host",
        "name": "Tessa",
        "gender": "female",
        "style": "global host",
        "accent": "South African English",
        "description": "Distinctive and articulate for international topics.",
        "suggested_roles": ["host", "guest"],
        "apple_voices": ["Tessa"],
        "kokoro_voice": "af_bella",
        "openai_voice": "shimmer",
        "espeak": {"voice": "en+f3", "speed": "144", "pitch": "56", "amplitude": "136"},
        "rate_wpm": 112,
    },
    {
        "id": "fiona-british-guide",
        "name": "Fiona",
        "gender": "female",
        "style": "British guide",
        "accent": "British English",
        "description": "Friendly and precise for educational recaps and guided explainers.",
        "suggested_roles": ["host", "guest", "narrator"],
        "apple_voices": ["Samantha"],
        "kokoro_voice": "af_sarah",
        "openai_voice": "alloy",
        "espeak": {"voice": "en-gb+f2", "speed": "148", "pitch": "57", "amplitude": "136"},
        "rate_wpm": 112,
    },
]
AI_PODCAST_VOICE_BY_ID = {voice["id"]: voice for voice in AI_PODCAST_VOICE_LIBRARY}
DEFAULT_AI_PODCAST_VOICE_IDS = ["aman-warm-analyst", "samantha-warm-cohost", "daniel-calm-british"]


def public_ai_podcast_voice(voice: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": voice["id"],
        "name": voice["name"],
        "gender": voice["gender"],
        "style": voice["style"],
        "accent": voice["accent"],
        "description": voice["description"],
        "suggested_roles": voice.get("suggested_roles", []),
    }


def sanitize_ai_voice_ids(value: Any, limit: int = 4) -> List[str]:
    values = value if isinstance(value, list) else []
    selected: List[str] = []
    for item in values:
        voice_id = str(item or "").strip()
        if voice_id in AI_PODCAST_VOICE_BY_ID and voice_id not in selected:
            selected.append(voice_id)
        if len(selected) >= limit:
            break
    return selected or DEFAULT_AI_PODCAST_VOICE_IDS[: min(limit, len(DEFAULT_AI_PODCAST_VOICE_IDS))]


def selected_ai_voice_ids_from_intake(intake: Optional[Dict[str, Any]], limit: int = 4) -> List[str]:
    voice_casting = (intake or {}).get("voiceCasting") or {}
    return sanitize_ai_voice_ids(voice_casting.get("selectedVoiceIds"), limit=limit)


def ai_voice_profile_for_turn(turn: Dict[str, str], index: int, selected_voice_ids: List[str], speaker_voice_map: Dict[str, str]) -> Dict[str, Any]:
    explicit_voice_id = str(turn.get("voice_id") or "").strip()
    if explicit_voice_id in AI_PODCAST_VOICE_BY_ID:
        return AI_PODCAST_VOICE_BY_ID[explicit_voice_id]

    speaker_key = str(turn.get("speaker") or turn.get("voice_role") or f"speaker-{index}").strip().lower()
    if speaker_key not in speaker_voice_map:
        speaker_voice_map[speaker_key] = selected_voice_ids[len(speaker_voice_map) % len(selected_voice_ids)]
    return AI_PODCAST_VOICE_BY_ID[speaker_voice_map[speaker_key]]


def apply_ai_voice_cast_to_turns(turns: List[Dict[str, str]], intake: Optional[Dict[str, Any]]) -> List[Dict[str, str]]:
    selected_voice_ids = selected_ai_voice_ids_from_intake(intake, limit=4)
    speaker_voice_map: Dict[str, str] = {}
    voiced_turns = []
    for index, turn in enumerate(turns):
        profile = ai_voice_profile_for_turn(turn, index, selected_voice_ids, speaker_voice_map)
        voiced_turns.append(
            {
                **turn,
                "voice_id": profile["id"],
                "voice_name": profile["name"],
                "voice_gender": profile["gender"],
                "voice_style": profile["style"],
            }
        )
    return voiced_turns


def ai_audio_sentence_gap_seconds() -> float:
    return max(0.0, parse_float_env("AI_AUDIO_TTS_SENTENCE_GAP_SECONDS", 1.0))


def ai_audio_edge_padding_seconds() -> float:
    return max(0.0, parse_float_env("AI_AUDIO_TTS_EDGE_PADDING_SECONDS", 1.0))


def tts_sentence_parts(text: str) -> List[str]:
    normalized = normalize_local_tts_text(text)
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", normalized) if part.strip()]


AI_STUDIO_STAGES = [
    "brief",
    "research",
    "outline",
    "script",
    "cast",
    "table_read",
    "final_render",
    "agent2_review",
    "publish",
]
AI_STUDIO_STAGE_LABELS = {
    "brief": "Creator Brief",
    "research": "Research & Claims",
    "outline": "Episode Outline",
    "script": "Dialogue Script",
    "cast": "Cast & Voices",
    "table_read": "Table Read",
    "final_render": "Final Audio Render",
    "agent2_review": "Agent 2 Review",
    "publish": "Publish",
}

try:
    AUDIORAQ_ORIGINALS_MIN_QUALITY_SCORE = float(os.environ.get("AUDIORAQ_ORIGINALS_AGENT2_MIN_SCORE", 90.0))
except (TypeError, ValueError):
    AUDIORAQ_ORIGINALS_MIN_QUALITY_SCORE = 90.0

TOPIC_FILTER_TERMS = {
    "finance": ["finance", "investing", "markets", "money", "economy", "wealth", "banking", "startups"],
    "law": ["law", "legal", "policy", "rights", "justice", "regulation", "contracts", "governance"],
    "environment": ["environment", "climate", "sustainability", "energy", "nature", "carbon", "green"],
    "emerging markets": ["emerging markets", "india", "africa", "latin america", "growth", "frontier markets"],
    "technology": ["technology", "tech", "ai", "software", "automation", "future", "innovation"],
    "upcoming technologies": ["upcoming technologies", "ai", "robotics", "quantum", "biotech", "spatial computing"],
    "current affairs": ["current affairs", "news", "geopolitics", "policy", "elections", "world"],
    "astrophysics": ["astrophysics", "space", "cosmos", "universe", "stars", "black holes", "nasa"],
    "physical health": ["physical health", "fitness", "nutrition", "sleep", "exercise", "strength", "medicine"],
    "mental health": ["mental health", "mindfulness", "stress", "therapy", "wellbeing", "resilience"],
    "business": ["business", "strategy", "founders", "startups", "management", "markets"],
    "science": ["science", "research", "biology", "physics", "chemistry", "evidence"],
    "education": ["education", "learning", "students", "teaching", "skills"],
    "entertainment": ["entertainment", "culture", "movies", "music", "media"],
}

CURATED_TOPIC_CATEGORIES = [
    "finance",
    "law",
    "environment",
    "emerging markets",
    "technology",
    "upcoming technologies",
    "current affairs",
    "astrophysics",
    "physical health",
    "mental health",
    "business",
    "science",
    "education",
    "entertainment",
]
CURATED_RECOMMENDED_EPISODE_TITLE_SNIPPETS = [
    "A decision framework for on-device AI",
    "A calm explainer on cyber incidents",
    "What most listeners misunderstand about cosmic dawn",
    "What most listeners misunderstand about Vietnam supply chains",
    "What most listeners misunderstand about workplace AI",
    "What most listeners misunderstand about supply chains",
    "Grid Hardening",
    "The practical beginner's guide to AI agents at work",
    "How migration changes behavior in the real world",
    "A decision framework for sanctions",
]


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


def get_public_app_origin(request: Optional[Request] = None) -> str:
    configured = (
        os.environ.get("PUBLIC_APP_ORIGIN")
        or os.environ.get("PUBLIC_BASE_URL")
        or os.environ.get("APP_ORIGIN")
        or ""
    ).strip().rstrip("/")
    if configured:
        return configured
    if request is not None:
        return get_public_request_origin(request)
    return "https://www.audioraq.com"


def get_social_token_encryption_key() -> bytes:
    configured = os.environ.get("SOCIAL_TOKEN_ENCRYPTION_KEY", "").strip()
    if configured:
        digest = hashlib.sha256(configured.encode("utf-8")).digest()
    else:
        digest = hashlib.sha256(get_jwt_secret().encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def get_social_token_cipher() -> Fernet:
    return Fernet(get_social_token_encryption_key())


def encrypt_social_token(value: str) -> str:
    if not value:
        return ""
    return get_social_token_cipher().encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_social_token(value: str) -> str:
    if not value:
        return ""
    try:
        return get_social_token_cipher().decrypt(value.encode("utf-8")).decode("utf-8")
    except (InvalidToken, ValueError, TypeError):
        logger.warning("Could not decrypt social provider token")
        return ""


def mask_secret(value: str) -> str:
    stripped = (value or "").strip()
    if len(stripped) <= 8:
        return "*" * len(stripped)
    return f"{stripped[:4]}{'*' * max(4, len(stripped) - 8)}{stripped[-4:]}"


def get_linkedin_social_client_id() -> str:
    return os.environ.get("LINKEDIN_SOCIAL_CLIENT_ID", "").strip()


def get_linkedin_social_client_secret() -> str:
    return os.environ.get("LINKEDIN_SOCIAL_CLIENT_SECRET", "").strip()


def get_linkedin_social_redirect_uri(request: Optional[Request] = None) -> str:
    override = os.environ.get("LINKEDIN_SOCIAL_REDIRECT_URI", "").strip()
    if override:
        return override
    return f"{get_public_app_origin(request)}/api/social/oauth/{SOCIAL_PUBLISH_PROVIDER_LINKEDIN}/callback"


def is_linkedin_social_configured() -> bool:
    return bool(get_linkedin_social_client_id() and get_linkedin_social_client_secret())


def get_meta_app_id() -> str:
    return os.environ.get("META_APP_ID", "").strip()


def get_meta_app_secret() -> str:
    return os.environ.get("META_APP_SECRET", "").strip()


def get_instagram_social_redirect_uri(request: Optional[Request] = None) -> str:
    override = os.environ.get("INSTAGRAM_SOCIAL_REDIRECT_URI", "").strip()
    if override:
        return override
    return f"{get_public_app_origin(request)}/api/social/oauth/{SOCIAL_PUBLISH_PROVIDER_INSTAGRAM}/callback"


def is_instagram_social_configured() -> bool:
    return bool(get_meta_app_id() and get_meta_app_secret())


def is_social_publish_provider_configured(provider: str) -> bool:
    if provider == SOCIAL_PUBLISH_PROVIDER_LINKEDIN:
        return is_linkedin_social_configured()
    if provider == SOCIAL_PUBLISH_PROVIDER_INSTAGRAM:
        return is_instagram_social_configured()
    return False


def build_social_publish_state(provider: str, user_id: str, return_origin: str) -> str:
    payload = {
        "type": "social_publish_state",
        "provider": provider,
        "sub": user_id,
        "return_origin": return_origin,
        "nonce": secrets.token_urlsafe(24),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=20),
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)


def decode_social_publish_state(state: str, expected_provider: str) -> Dict[str, Any]:
    try:
        payload = jwt.decode(state, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        raise HTTPException(status_code=400, detail="Invalid social publishing state")
    if payload.get("type") != "social_publish_state" or payload.get("provider") != expected_provider:
        raise HTTPException(status_code=400, detail="Invalid social publishing state")
    return payload


def get_linkedin_social_scopes() -> str:
    return "r_organization_social w_organization_social"


def build_linkedin_social_authorize_url(request: Request, state: str) -> str:
    params = {
        "response_type": "code",
        "client_id": get_linkedin_social_client_id(),
        "redirect_uri": get_linkedin_social_redirect_uri(request),
        "state": state,
        "scope": get_linkedin_social_scopes(),
    }
    return f"https://www.linkedin.com/oauth/v2/authorization?{urlencode(params)}"


def get_instagram_social_scopes() -> str:
    return ",".join(
        [
            "pages_show_list",
            "pages_read_engagement",
            "business_management",
            "instagram_basic",
            "instagram_content_publish",
            "instagram_manage_insights",
        ]
    )


def build_instagram_social_authorize_url(request: Request, state: str) -> str:
    params = {
        "client_id": get_meta_app_id(),
        "redirect_uri": get_instagram_social_redirect_uri(request),
        "response_type": "code",
        "scope": get_instagram_social_scopes(),
        "state": state,
    }
    return f"https://www.facebook.com/{META_GRAPH_VERSION}/dialog/oauth?{urlencode(params)}"


def exchange_linkedin_social_code(request: Request, code: str) -> Dict[str, Any]:
    response = requests.post(
        "https://www.linkedin.com/oauth/v2/accessToken",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "client_id": get_linkedin_social_client_id(),
            "client_secret": get_linkedin_social_client_secret(),
            "redirect_uri": get_linkedin_social_redirect_uri(request),
        },
        timeout=45,
    )
    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"LinkedIn token exchange failed: {response.text[:300]}")
    payload = response.json() or {}
    expires_in = int(payload.get("expires_in", 0) or 0)
    token_expires_at = (
        datetime.now(timezone.utc) + timedelta(seconds=expires_in)
    ).isoformat() if expires_in else ""
    return {
        "access_token": payload.get("access_token", ""),
        "refresh_token": payload.get("refresh_token", ""),
        "token_expires_at": token_expires_at,
    }


def exchange_instagram_social_code(request: Request, code: str) -> Dict[str, Any]:
    response = requests.get(
        f"https://graph.facebook.com/{META_GRAPH_VERSION}/oauth/access_token",
        params={
            "client_id": get_meta_app_id(),
            "client_secret": get_meta_app_secret(),
            "redirect_uri": get_instagram_social_redirect_uri(request),
            "code": code,
        },
        timeout=45,
    )
    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"Meta token exchange failed: {response.text[:300]}")
    payload = response.json() or {}
    access_token = payload.get("access_token", "")
    expires_in = int(payload.get("expires_in", 0) or 0)

    long_lived_response = requests.get(
        f"https://graph.facebook.com/{META_GRAPH_VERSION}/oauth/access_token",
        params={
            "grant_type": "fb_exchange_token",
            "client_id": get_meta_app_id(),
            "client_secret": get_meta_app_secret(),
            "fb_exchange_token": access_token,
        },
        timeout=45,
    )
    if long_lived_response.status_code < 400:
        long_lived_payload = long_lived_response.json() or {}
        access_token = long_lived_payload.get("access_token", access_token)
        expires_in = int(long_lived_payload.get("expires_in", expires_in) or expires_in or 0)

    token_expires_at = (
        datetime.now(timezone.utc) + timedelta(seconds=expires_in)
    ).isoformat() if expires_in else ""
    return {
        "access_token": access_token,
        "refresh_token": "",
        "token_expires_at": token_expires_at,
    }


def social_publish_redirect(request: Request, return_origin: str, params: Optional[Dict[str, Any]] = None) -> RedirectResponse:
    destination = build_frontend_url(return_origin, "/settings", params or {})
    return RedirectResponse(destination, status_code=302)


def sanitize_social_account(account: Dict[str, Any]) -> Dict[str, Any]:
    cleaned = clean_doc(account) or {}
    cleaned.pop("access_token", None)
    cleaned.pop("refresh_token", None)
    cleaned["has_access_token"] = bool(account.get("access_token"))
    cleaned["token_preview"] = mask_secret(decrypt_social_token(account.get("access_token", "")))
    return cleaned


def sanitize_social_post(post: Dict[str, Any]) -> Dict[str, Any]:
    cleaned = clean_doc(post) or {}
    cleaned.pop("provider_response", None)
    cleaned["card_image_url"] = f"{get_public_app_origin()}/api/social/posts/{cleaned.get('id')}/card.png"
    return cleaned


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


def is_production_env() -> bool:
    explicit_env = (os.environ.get("APP_ENV") or os.environ.get("ENVIRONMENT") or "").strip().lower()
    if explicit_env:
        return explicit_env in {"prod", "production"}
    public_origin = (os.environ.get("PUBLIC_APP_ORIGIN") or "").strip().lower()
    return public_origin.startswith("https://") or parse_bool(os.environ.get("COOKIE_SECURE"), default=False)


def should_return_auth_tokens() -> bool:
    configured = os.environ.get("AUTH_RETURN_BEARER_TOKENS")
    if configured is not None:
        return parse_bool(configured, default=False)
    return not is_production_env()


def attach_auth_token_payload(payload: Dict[str, Any], access_token: str) -> Dict[str, Any]:
    if should_return_auth_tokens():
        payload["access_token"] = access_token
    return payload


def validate_runtime_security() -> None:
    production = is_production_env()
    jwt_secret = (os.environ.get("JWT_SECRET") or "").strip()
    weak_jwt_values = {"", "secret", "changeme", "replace-with-a-long-random-secret", "dev-secret"}
    if jwt_secret.lower() in weak_jwt_values or len(jwt_secret) < 32:
        message = "JWT_SECRET must be a unique high-entropy value of at least 32 characters."
        if production:
            raise RuntimeError(message)
        logger.warning(message)

    admin_password = (os.environ.get("ADMIN_PASSWORD") or "").strip()
    weak_admin_values = {"", "admin", "admin123", "password", "test123", "replace-with-a-strong-admin-password"}
    if admin_password.lower() in weak_admin_values or len(admin_password) < 12:
        message = "ADMIN_PASSWORD must be explicitly configured with a strong password before production launch."
        if production:
            raise RuntimeError(message)
        logger.warning(message)


def get_admin_password_for_seed() -> str:
    admin_password = (os.environ.get("ADMIN_PASSWORD") or "").strip()
    if admin_password:
        return admin_password
    if is_production_env():
        raise RuntimeError("ADMIN_PASSWORD is required in production")
    return "admin123"


def write_test_credentials_if_enabled(admin_email: str, admin_password: str) -> None:
    if not parse_bool(os.environ.get("WRITE_TEST_CREDENTIALS"), default=not is_production_env()):
        return
    memory_dir = Path(os.environ.get("MEMORY_DIR", str(DEFAULT_MEMORY_DIR)))
    memory_dir.mkdir(parents=True, exist_ok=True)
    include_admin_password = parse_bool(os.environ.get("INCLUDE_ADMIN_TEST_PASSWORD"), default=False)
    admin_password_display = admin_password if include_admin_password and not is_production_env() else "<configured in environment>"
    with open(memory_dir / "test_credentials.md", "w", encoding="utf-8") as f:
        f.write("# Test Credentials\n\n")
        f.write(f"## Admin\n- Email: {admin_email}\n- Password: {admin_password_display}\n- Role: admin\n\n")
        f.write("## Test User\n- Email: testuser@test.com\n- Password: test123\n- Role: user\n\n")
        f.write("## Test Podcaster\n- Email: podcaster@test.com\n- Password: test123\n- Role: podcaster\n\n")
        f.write("## Auth Endpoints\n- POST /api/auth/register\n- POST /api/auth/login\n- POST /api/auth/logout\n- GET /api/auth/me\n- POST /api/auth/refresh\n")


def get_client_fingerprint(request: Request) -> str:
    forwarded_for = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
    client_ip = forwarded_for or (request.client.host if request.client else "unknown")
    digest = hashlib.sha256(f"{client_ip}:{os.environ.get('JWT_SECRET', '')[:16]}".encode("utf-8")).hexdigest()
    return digest[:32]


def is_manual_social_connect_enabled() -> bool:
    return parse_bool(os.environ.get("SOCIAL_MANUAL_TOKEN_CONNECT_ENABLED"), default=not is_production_env())


def max_upload_bytes() -> int:
    return parse_int_env("MAX_UPLOAD_BYTES", 524_288_000, minimum=1_048_576, maximum=2_147_483_648)


def max_thumbnail_bytes() -> int:
    return parse_int_env("MAX_THUMBNAIL_UPLOAD_BYTES", 8_388_608, minimum=65_536, maximum=52_428_800)


def analytics_retention_seconds() -> int:
    days = parse_int_env("ANALYTICS_EVENT_RETENTION_DAYS", 180, minimum=7, maximum=1095)
    return days * 86400


def validate_runtime_url(url: str, *, allow_local: bool = False) -> str:
    candidate = (url or "").strip()
    parsed = urlparse(candidate)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise HTTPException(status_code=400, detail="URL must be an absolute http(s) URL")
    hostname = parsed.hostname.strip().lower()
    try:
        addresses = socket.getaddrinfo(hostname, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)
    except socket.gaierror:
        raise HTTPException(status_code=400, detail="URL host could not be resolved")
    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if allow_local:
            continue
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved or ip.is_unspecified:
            raise HTTPException(status_code=400, detail="URL points to a private or unsafe network")
    return candidate


def safe_external_get(url: str, *, timeout: int = 30, max_bytes: int = 5_242_880, max_redirects: int = 3) -> requests.Response:
    current_url = validate_runtime_url(url)
    for _ in range(max_redirects + 1):
        response = requests.get(current_url, timeout=timeout, stream=True, allow_redirects=False)
        if response.is_redirect or response.status_code in {301, 302, 303, 307, 308}:
            location = response.headers.get("Location", "")
            response.close()
            if not location:
                raise HTTPException(status_code=400, detail="External URL redirect was missing a destination")
            current_url = validate_runtime_url(urljoin(current_url, location))
            continue
        content_length = response.headers.get("Content-Length")
        if content_length and int(content_length) > max_bytes:
            response.close()
            raise HTTPException(status_code=400, detail="External URL response is too large")
        data = bytearray()
        for chunk in response.iter_content(chunk_size=65536):
            if not chunk:
                continue
            data.extend(chunk)
            if len(data) > max_bytes:
                response.close()
                raise HTTPException(status_code=400, detail="External URL response is too large")
        response._content = bytes(data)
        response.close()
        return response
    raise HTTPException(status_code=400, detail="External URL redirected too many times")


def validate_external_redirect_url(url: str) -> str:
    return validate_runtime_url(url)


def safe_extension(filename: str, allowed_extensions: Set[str], default: str = "bin") -> str:
    raw_ext = (filename or "").rsplit(".", 1)[-1].lower().strip() if "." in (filename or "") else default
    ext = re.sub(r"[^a-z0-9]", "", raw_ext)[:12] or default
    if ext not in allowed_extensions:
        raise HTTPException(status_code=400, detail=f"Unsupported file extension: .{ext}")
    return ext


async def read_upload_limited(upload: UploadFile, max_bytes: int) -> bytes:
    data = bytearray()
    while True:
        chunk = await upload.read(1024 * 1024)
        if not chunk:
            break
        data.extend(chunk)
        if len(data) > max_bytes:
            raise HTTPException(status_code=413, detail="Uploaded file is too large")
    return bytes(data)


def validate_thumbnail_metadata(upload: UploadFile) -> str:
    allowed_thumbnail_types = {"image/jpeg", "image/png", "image/webp"}
    allowed_thumbnail_extensions = {"jpg", "jpeg", "png", "webp"}
    content_type = (upload.content_type or "").lower().strip()
    if content_type not in allowed_thumbnail_types:
        raise HTTPException(status_code=400, detail="Thumbnails must be JPG, PNG, or WebP images")
    return safe_extension(upload.filename or "", allowed_thumbnail_extensions, default="jpg")


def validate_media_extension_matches_type(filename: str, content_type: str, is_audio_upload: bool, is_video_upload: bool) -> str:
    audio_extensions = {"mp3", "wav", "ogg", "aac", "flac", "m4a"}
    video_extensions = {"mp4", "webm", "mov", "avi"}
    allowed_extensions = audio_extensions | video_extensions
    ext = safe_extension(filename or "", allowed_extensions, default="mp3" if is_audio_upload else "mp4")
    normalized_type = (content_type or "").lower()
    if is_audio_upload and ext in video_extensions and normalized_type != "audio/mp4":
        raise HTTPException(status_code=400, detail="Audio uploads must use an audio file extension")
    if is_video_upload and ext in audio_extensions:
        raise HTTPException(status_code=400, detail="Video uploads must use a video file extension")
    return ext


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
    if get_storage_backend() == "local":
        return "local"
    if storage_key:
        return storage_key
    if not EMERGENT_KEY:
        raise RuntimeError("EMERGENT_LLM_KEY is required for emergent object storage. Set STORAGE_BACKEND=local to use local disk storage.")
    resp = requests.post(f"{STORAGE_URL}/init", json={"emergent_key": EMERGENT_KEY}, timeout=30)
    resp.raise_for_status()
    storage_key = resp.json()["storage_key"]
    return storage_key


def get_storage_backend() -> str:
    backend = os.environ.get("STORAGE_BACKEND", "emergent").strip().lower()
    return backend if backend in {"emergent", "local"} else "emergent"


def local_storage_root() -> Path:
    configured = Path(os.environ.get("LOCAL_STORAGE_DIR", str(PROJECT_DIR / "data" / "media"))).expanduser()
    return (configured if configured.is_absolute() else PROJECT_DIR / configured).resolve()


def local_storage_path(path: str) -> Path:
    normalized = (path or "").strip().lstrip("/")
    if not normalized:
        raise ValueError("Storage path is required")
    destination = (local_storage_root() / normalized).resolve()
    if local_storage_root() not in destination.parents and destination != local_storage_root():
        raise ValueError("Invalid storage path")
    return destination


def local_storage_content_type_path(path: str) -> Path:
    return local_storage_path(path).with_name(f"{local_storage_path(path).name}.content-type")


def object_cache_key(path: str) -> str:
    normalized = (path or "").strip().lstrip("/")
    if not normalized:
        raise ValueError("Storage path is required")
    return f"__object_cache/{normalized}"


def cache_object_locally(path: str, data: bytes, content_type: str) -> None:
    cache_path = object_cache_key(path)
    destination = local_storage_path(cache_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp_destination = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.tmp")
    temp_destination.write_bytes(data)
    temp_destination.replace(destination)
    local_storage_content_type_path(cache_path).write_text(content_type or "application/octet-stream", encoding="utf-8")


def cached_object_exists(path: str) -> bool:
    try:
        source = local_storage_path(object_cache_key(path))
        return source.exists() and source.stat().st_size > 0
    except Exception:
        return False


def cached_object_content_type(path: str, fallback: str) -> str:
    try:
        content_type_path = local_storage_content_type_path(object_cache_key(path))
        if content_type_path.exists():
            return content_type_path.read_text(encoding="utf-8").strip() or fallback
    except Exception:
        pass
    return fallback


def delete_cached_object(path: str) -> None:
    try:
        cache_path = object_cache_key(path)
        source = local_storage_path(cache_path)
        content_type_path = local_storage_content_type_path(cache_path)
        if source.exists():
            source.unlink()
        if content_type_path.exists():
            content_type_path.unlink()
    except Exception as exc:
        logger.warning(f"Could not remove cached media object for {path}: {exc}")


def put_object(path, data, content_type):
    if get_storage_backend() == "local":
        destination = local_storage_path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
        local_storage_content_type_path(path).write_text(content_type or "application/octet-stream", encoding="utf-8")
        return {"path": path, "storage_backend": "local"}

    key = init_storage()
    for attempt in range(4):
        try:
            resp = requests.put(
                f"{STORAGE_URL}/objects/{path}",
                headers={"X-Storage-Key": key, "Content-Type": content_type},
                data=data,
                timeout=300,
            )
            resp.raise_for_status()
            break
        except requests.RequestException as exc:
            status_code = getattr(getattr(exc, "response", None), "status_code", None)
            if status_code and status_code < 500:
                raise
            if attempt == 3:
                raise
            delay = 2 ** attempt
            logger.warning(f"Storage upload retry {attempt + 1}/4 for {path} after {status_code or exc.__class__.__name__}; waiting {delay}s")
            time.sleep(delay)
    try:
        cache_object_locally(path, data, content_type)
    except Exception as exc:
        logger.warning(f"Could not cache uploaded media object {path}: {exc}")
    return resp.json()


def get_object(path):
    if get_storage_backend() == "local":
        source = local_storage_path(path)
        if not source.exists():
            raise FileNotFoundError(path)
        content_type_path = local_storage_content_type_path(path)
        guessed_type = mimetypes.guess_type(source.name)[0] or "application/octet-stream"
        content_type = content_type_path.read_text(encoding="utf-8").strip() if content_type_path.exists() else guessed_type
        return source.read_bytes(), content_type

    key = init_storage()
    resp = requests.get(
        f"{STORAGE_URL}/objects/{path}",
        headers={"X-Storage-Key": key},
        timeout=120,
    )
    resp.raise_for_status()
    return resp.content, resp.headers.get("Content-Type", "application/octet-stream")


STREAM_CHUNK_SIZE = 1024 * 1024


def safe_inline_filename(filename: str) -> str:
    safe_name = re.sub(r'[\r\n"\\]+', "", (filename or "podcast").strip()) or "podcast"
    return safe_name[:180]


def media_stream_headers(
    filename: str,
    *,
    content_length: Optional[int] = None,
    content_range: Optional[str] = None,
) -> Dict[str, str]:
    headers = {
        "Accept-Ranges": "bytes",
        "Content-Disposition": f'inline; filename="{safe_inline_filename(filename)}"',
        "Cache-Control": "private, max-age=3600, no-transform",
    }
    if content_length is not None:
        headers["Content-Length"] = str(max(0, content_length))
    if content_range:
        headers["Content-Range"] = content_range
    return headers


def parse_range_header(range_header: Optional[str], size: int) -> Optional[Tuple[int, int]]:
    if not range_header:
        return None

    header = range_header.strip().lower()
    if not header.startswith("bytes=") or "," in header:
        raise HTTPException(
            status_code=416,
            detail="Requested range not satisfiable",
            headers={"Content-Range": f"bytes */{size}", "Accept-Ranges": "bytes"},
        )

    start_text, separator, end_text = header[6:].partition("-")
    if separator != "-":
        raise HTTPException(
            status_code=416,
            detail="Requested range not satisfiable",
            headers={"Content-Range": f"bytes */{size}", "Accept-Ranges": "bytes"},
        )

    try:
        if start_text == "":
            suffix_length = int(end_text)
            if suffix_length <= 0:
                raise ValueError("suffix range must be positive")
            start = max(size - suffix_length, 0)
            end = size - 1
        else:
            start = int(start_text)
            end = int(end_text) if end_text else size - 1
            end = min(end, size - 1)
    except ValueError:
        raise HTTPException(
            status_code=416,
            detail="Requested range not satisfiable",
            headers={"Content-Range": f"bytes */{size}", "Accept-Ranges": "bytes"},
        )

    if size <= 0 or start < 0 or start >= size or end < start:
        raise HTTPException(
            status_code=416,
            detail="Requested range not satisfiable",
            headers={"Content-Range": f"bytes */{size}", "Accept-Ranges": "bytes"},
        )

    return start, end


def iter_file_range(source: Path, start: int, end: int) -> Iterator[bytes]:
    with source.open("rb") as file_handle:
        file_handle.seek(start)
        remaining = end - start + 1
        while remaining > 0:
            chunk = file_handle.read(min(STREAM_CHUNK_SIZE, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk


def should_count_stream_play(range_header: Optional[str]) -> bool:
    if not range_header:
        return True
    match = re.match(r"^\s*bytes=(\d*)-", range_header, flags=re.IGNORECASE)
    return bool(match and match.group(1) in {"", "0"})


def stream_local_object(path: str, content_type: str, request: Request, filename: str):
    source = local_storage_path(path)
    if not source.exists():
        raise FileNotFoundError(path)

    size = source.stat().st_size
    range_tuple = parse_range_header(request.headers.get("range"), size)
    if not range_tuple:
        return FileResponse(
            source,
            media_type=content_type,
            headers=media_stream_headers(filename, content_length=size),
        )

    start, end = range_tuple
    content_length = end - start + 1
    return StreamingResponse(
        iter_file_range(source, start, end),
        status_code=206,
        media_type=content_type,
        headers=media_stream_headers(
            filename,
            content_length=content_length,
            content_range=f"bytes {start}-{end}/{size}",
        ),
    )


def stream_bytes_object(data: bytes, content_type: str, request: Request, filename: str):
    size = len(data)
    range_tuple = parse_range_header(request.headers.get("range"), size)
    if not range_tuple:
        return Response(content=data, media_type=content_type, headers=media_stream_headers(filename, content_length=size))

    start, end = range_tuple
    partial_data = data[start : end + 1]
    return Response(
        content=partial_data,
        status_code=206,
        media_type=content_type,
        headers=media_stream_headers(
            filename,
            content_length=len(partial_data),
            content_range=f"bytes {start}-{end}/{size}",
        ),
    )


def stream_cached_or_remote_object(path: str, content_type: str, request: Request, filename: str):
    if cached_object_exists(path):
        return stream_local_object(object_cache_key(path), cached_object_content_type(path, content_type), request, filename)

    data, storage_content_type = get_object(path)
    resolved_content_type = content_type or storage_content_type
    try:
        cache_object_locally(path, data, resolved_content_type)
        return stream_local_object(object_cache_key(path), resolved_content_type, request, filename)
    except Exception as exc:
        logger.warning(f"Could not cache streamed media object {path}; serving from memory: {exc}")
        return stream_bytes_object(data, resolved_content_type, request, filename)


def delete_object(path, missing_ok: bool = True) -> str:
    normalized_path = (path or "").strip()
    if not normalized_path:
        return "skipped"

    if get_storage_backend() == "local":
        source = local_storage_path(normalized_path)
        content_type_path = local_storage_content_type_path(normalized_path)
        existed = source.exists()
        if source.exists():
            source.unlink()
        if content_type_path.exists():
            content_type_path.unlink()
        if existed:
            return "deleted"
        if missing_ok:
            return "missing"
        raise FileNotFoundError(normalized_path)

    delete_cached_object(normalized_path)
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


async def enforce_rate_limit(request: Request, action: str, max_attempts: int, window_seconds: int) -> None:
    now = datetime.now(timezone.utc)
    key = hashlib.sha256(f"{action}:{get_client_fingerprint(request)}".encode("utf-8")).hexdigest()
    window_start = now - timedelta(seconds=window_seconds)
    existing = await db.rate_limits.find_one({"_id": key})
    if existing:
        created_at = existing.get("created_at")
        if isinstance(created_at, str):
            try:
                created_at = datetime.fromisoformat(created_at)
            except ValueError:
                created_at = None
        if created_at and created_at > window_start:
            attempts = int(existing.get("attempts", 0)) + 1
            await db.rate_limits.update_one(
                {"_id": key},
                {"$set": {"last_attempt_at": now, "expires_at": now + timedelta(seconds=window_seconds)}, "$inc": {"attempts": 1}},
            )
            if attempts > max_attempts:
                raise HTTPException(status_code=429, detail="Too many requests. Please slow down.")
            return

    await db.rate_limits.update_one(
        {"_id": key},
        {
            "$set": {
                "action": action,
                "created_at": now,
                "last_attempt_at": now,
                "expires_at": now + timedelta(seconds=window_seconds),
                "attempts": 1,
            }
        },
        upsert=True,
    )


async def record_analytics_event(
    event_type: str,
    request: Optional[Request],
    user: Optional[Dict[str, Any]],
    podcast: Optional[Dict[str, Any]],
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    if not podcast:
        return
    try:
        timestamp = datetime.now(timezone.utc)
        bucket_date = timestamp.date().isoformat()
        user_id = user_id_str(user) if user else ""
        episode_id = podcast.get("id", "")
        show_id = podcast.get("show_id", "")
        event_doc = {
            "id": str(uuid.uuid4()),
            "event_type": event_type,
            "episode_id": episode_id,
            "show_id": show_id,
            "user_id": user_id,
            "role": user.get("role", "guest") if user else "guest",
            "category": podcast.get("category", DEFAULT_SHOW_CATEGORY),
            "bucket_date": bucket_date,
            "client_fingerprint": get_client_fingerprint(request) if request else "",
            "metadata": metadata or {},
            "created_at": timestamp,
        }
        await db.analytics_events.insert_one(event_doc)
        await db.daily_episode_metrics.update_one(
            {"episode_id": episode_id, "bucket_date": bucket_date},
            {
                "$set": {
                    "episode_id": episode_id,
                    "show_id": show_id,
                    "category": podcast.get("category", DEFAULT_SHOW_CATEGORY),
                    "bucket_date": bucket_date,
                    "updated_at": timestamp,
                },
                "$inc": {f"counts.{event_type}": 1},
                "$setOnInsert": {"created_at": timestamp},
            },
            upsert=True,
        )
    except Exception as exc:
        logger.warning(f"Analytics event write failed: {exc}")


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


def ensure_social_publishing_access(user: Dict[str, Any]):
    if user.get("role") not in {"podcaster", "admin"}:
        raise HTTPException(status_code=403, detail="Only podcasters and admins can manage social publishing")


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


def normalize_social_post_status(value: Optional[str]) -> str:
    normalized = (value or "").strip().lower()
    if normalized in SOCIAL_POST_STATUSES:
        return normalized
    return SOCIAL_POST_STATUS_DRAFT


def compose_social_post_text(post: Dict[str, Any], max_length: int = 2200) -> str:
    parts = []
    headline = (post.get("headline") or "").strip()
    caption = (post.get("caption") or "").strip()
    cta = (post.get("cta") or "").strip()
    link_url = (post.get("link_url") or "").strip()
    hashtags = [tag.strip() for tag in (post.get("hashtags") or []) if str(tag).strip()]

    if headline:
        parts.append(headline)
    if caption:
        parts.append(caption)
    if cta:
        parts.append(cta)
    if link_url:
        parts.append(link_url)
    if hashtags:
        parts.append(" ".join(tag if tag.startswith("#") else f"#{tag.replace(' ', '')}" for tag in hashtags[:8]))

    text = "\n\n".join([part for part in parts if part]).strip()
    if len(text) <= max_length:
        return text
    return textwrap.shorten(text, width=max_length, placeholder="...")


def normalize_linkedin_organization_id(value: Any) -> str:
    raw = str(value or "").strip()
    if raw.startswith("urn:li:organization:"):
        return raw.rsplit(":", 1)[-1]
    digits = "".join(ch for ch in raw if ch.isdigit())
    return digits or raw


def build_linkedin_headers(access_token: str, content_type: str = "application/json") -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {access_token}",
        "Linkedin-Version": LINKEDIN_DEFAULT_VERSION,
        "X-Restli-Protocol-Version": "2.0.0",
        "Content-Type": content_type,
    }


def linkedin_rest_request(method: str, path: str, access_token: str, **kwargs) -> requests.Response:
    response = requests.request(
        method.upper(),
        f"https://api.linkedin.com/rest{path}",
        headers=build_linkedin_headers(access_token, kwargs.pop("content_type", "application/json")),
        timeout=45,
        **kwargs,
    )
    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"LinkedIn API error: {response.text[:300]}")
    return response


def meta_graph_request(method: str, path: str, access_token: str, **kwargs) -> requests.Response:
    response = requests.request(
        method.upper(),
        f"https://graph.facebook.com/{META_GRAPH_VERSION}{path}",
        params={**kwargs.pop("params", {}), "access_token": access_token},
        timeout=45,
        **kwargs,
    )
    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"Meta API error: {response.text[:300]}")
    return response


def social_account_public_label(account: Dict[str, Any]) -> str:
    return (
        account.get("account_name")
        or account.get("username")
        or account.get("organization_name")
        or account.get("page_name")
        or account.get("account_id")
        or "Connected account"
    )


async def upsert_social_connected_account(
    user: Dict[str, Any],
    provider: str,
    account_id: str,
    *,
    account_name: str = "",
    username: str = "",
    organization_id: str = "",
    page_id: str = "",
    scopes: Optional[List[str]] = None,
    access_token: str = "",
    refresh_token: str = "",
    token_expires_at: str = "",
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    account_id = str(account_id or "").strip()
    if not account_id:
        raise HTTPException(status_code=400, detail="Connected social accounts require an account id")

    existing = await db.social_connected_accounts.find_one(
        {"user_id": user_id_str(user), "provider": provider, "account_id": account_id}
    )
    doc_id = existing.get("id") if existing else str(uuid.uuid4())
    payload = {
        "id": doc_id,
        "user_id": user_id_str(user),
        "provider": provider,
        "account_id": account_id,
        "account_name": account_name.strip(),
        "username": username.strip(),
        "organization_id": normalize_linkedin_organization_id(organization_id),
        "page_id": str(page_id or "").strip(),
        "scopes": sorted({scope.strip() for scope in (scopes or []) if str(scope).strip()}),
        "access_token": encrypt_social_token(access_token),
        "refresh_token": encrypt_social_token(refresh_token),
        "token_expires_at": token_expires_at or "",
        "metadata": metadata or {},
        "status": "connected",
        "updated_at": now_iso(),
        "last_synced_at": now_iso(),
    }
    if not existing:
        payload["created_at"] = now_iso()
    await db.social_connected_accounts.update_one({"id": doc_id}, {"$set": payload}, upsert=True)
    saved = await db.social_connected_accounts.find_one({"id": doc_id})
    return sanitize_social_account(saved)


async def fetch_user_social_accounts(user: Dict[str, Any], provider: Optional[str] = None) -> List[Dict[str, Any]]:
    query = {"user_id": user_id_str(user)}
    if provider:
        query["provider"] = provider
    accounts = await db.social_connected_accounts.find(query).sort("updated_at", -1).to_list(100)
    return [sanitize_social_account(account) for account in accounts]


async def get_social_connected_account(user: Dict[str, Any], social_account_id: str) -> Dict[str, Any]:
    account = await db.social_connected_accounts.find_one({"id": social_account_id, "user_id": user_id_str(user)})
    if not account:
        raise HTTPException(status_code=404, detail="Connected social account not found")
    return account


def generate_social_card_image(post: Dict[str, Any]) -> bytes:
    width, height = 1200, 1200
    image = Image.new("RGB", (width, height), "#0A0A0B")
    draw = ImageDraw.Draw(image)

    for index in range(height):
        ratio = index / max(1, height - 1)
        r = int(10 + (24 * ratio))
        g = int(10 + (84 * ratio))
        b = int(11 + (42 * ratio))
        draw.line([(0, index), (width, index)], fill=(r, g, b))

    try:
        title_font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 72)
        body_font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 38)
        meta_font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 28)
    except Exception:
        title_font = ImageFont.load_default()
        body_font = ImageFont.load_default()
        meta_font = ImageFont.load_default()

    headline = (post.get("headline") or post.get("caption") or "Audioraq Update").strip()
    caption = (post.get("caption") or "").strip()
    provider = (post.get("provider") or "").strip().title()
    cta = (post.get("cta") or "audioraq.com").strip()
    accent = "#F5A623" if post.get("provider") == SOCIAL_PUBLISH_PROVIDER_LINKEDIN else "#FF6A3D"

    draw.rounded_rectangle((72, 72, width - 72, height - 72), radius=44, outline="#27272A", width=3)
    draw.rounded_rectangle((90, 90, 390, 152), radius=28, fill=accent)
    draw.text((124, 104), f"{provider or 'Social'} Post", fill="#0A0A0B", font=meta_font)

    cursor_y = 240
    for line in textwrap.wrap(headline, width=24)[:4]:
        draw.text((96, cursor_y), line, fill="white", font=title_font)
        cursor_y += 92

    cursor_y += 24
    for line in textwrap.wrap(caption, width=42)[:8]:
        draw.text((96, cursor_y), line, fill="#D4D4D8", font=body_font)
        cursor_y += 56

    draw.text((96, height - 170), "Audioraq", fill="white", font=title_font)
    draw.text((96, height - 110), cta[:80], fill="#A1A1AA", font=body_font)

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


async def create_social_post_record(
    user: Dict[str, Any],
    payload: Dict[str, Any],
    *,
    publish_now: bool = False,
) -> Dict[str, Any]:
    status = SOCIAL_POST_STATUS_PUBLISHING if publish_now else normalize_social_post_status(payload.get("status"))
    if status == SOCIAL_POST_STATUS_DRAFT and payload.get("scheduled_at"):
        status = SOCIAL_POST_STATUS_QUEUED

    doc = {
        "id": str(uuid.uuid4()),
        "user_id": user_id_str(user),
        "provider": payload["provider"],
        "social_account_id": payload["social_account_id"],
        "headline": (payload.get("headline") or "").strip(),
        "caption": (payload.get("caption") or "").strip(),
        "cta": (payload.get("cta") or "").strip(),
        "link_url": (payload.get("link_url") or "").strip(),
        "hashtags": [str(tag).strip() for tag in (payload.get("hashtags") or []) if str(tag).strip()],
        "scheduled_at": (payload.get("scheduled_at") or "").strip(),
        "status": status,
        "asset_url": (payload.get("asset_url") or "").strip(),
        "use_generated_card": bool(payload.get("use_generated_card", True)),
        "source": (payload.get("source") or "manual").strip(),
        "metrics": {},
        "attempt_count": 0,
        "last_attempt_at": "",
        "failure_reason": "",
        "provider_response": {},
        "published_at": "",
        "external_post_id": "",
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    await db.social_posts.insert_one(doc)
    if publish_now:
        return await publish_social_post_record(doc["id"], user=user)
    saved = await db.social_posts.find_one({"id": doc["id"]})
    return sanitize_social_post(saved)


def build_social_post_card_url(post_id: str) -> str:
    return f"{get_public_app_origin()}/api/social/posts/{post_id}/card.png"


async def fetch_linkedin_admin_organizations(access_token: str) -> List[Dict[str, Any]]:
    response = linkedin_rest_request(
        "GET",
        "/organizationAcls",
        access_token,
        params={"q": "roleAssignee", "state": "APPROVED", "count": 25},
    )
    elements = response.json().get("elements", []) or []
    organizations = []
    seen = set()
    for item in elements:
        org_urn = item.get("organization") or ""
        org_id = normalize_linkedin_organization_id(org_urn)
        role = (item.get("role") or "").strip().upper()
        if not org_id or org_id in seen:
            continue
        if role not in {"ADMINISTRATOR", "DIRECT_SPONSORED_CONTENT_POSTER", "CONTENT_ADMIN"}:
            continue
        seen.add(org_id)
        name = f"LinkedIn Organization {org_id}"
        try:
            org_resp = linkedin_rest_request("GET", f"/organizations/{org_id}", access_token)
            org_data = org_resp.json() or {}
            name = org_data.get("localizedName") or org_data.get("name", {}).get("localized", {}).get("en_US") or name
        except HTTPException:
            pass
        organizations.append(
            {
                "organization_id": org_id,
                "organization_urn": f"urn:li:organization:{org_id}",
                "account_id": org_id,
                "account_name": name,
                "role": role,
            }
        )
    return organizations


async def connect_linkedin_social_accounts(
    user: Dict[str, Any],
    access_token: str,
    *,
    refresh_token: str = "",
    token_expires_at: str = "",
    organization_id: str = "",
    organization_name: str = "",
) -> List[Dict[str, Any]]:
    organizations = await fetch_linkedin_admin_organizations(access_token)
    requested_org_id = normalize_linkedin_organization_id(organization_id)
    if requested_org_id:
        organizations = [item for item in organizations if item["organization_id"] == requested_org_id]
    if not organizations and requested_org_id:
        organizations = [
            {
                "organization_id": requested_org_id,
                "organization_urn": f"urn:li:organization:{requested_org_id}",
                "account_id": requested_org_id,
                "account_name": organization_name.strip() or f"LinkedIn Organization {requested_org_id}",
                "role": "ADMINISTRATOR",
            }
        ]
    if not organizations:
        raise HTTPException(
            status_code=400,
            detail="No administered LinkedIn organization was found for this token. Confirm the app has organization posting permissions and the member is a page admin.",
        )

    connected = []
    for organization in organizations:
        connected.append(
            await upsert_social_connected_account(
                user,
                SOCIAL_PUBLISH_PROVIDER_LINKEDIN,
                organization["account_id"],
                account_name=organization["account_name"],
                organization_id=organization["organization_id"],
                scopes=get_linkedin_social_scopes().split(),
                access_token=access_token,
                refresh_token=refresh_token,
                token_expires_at=token_expires_at,
                metadata={"organization_urn": organization["organization_urn"], "role": organization["role"]},
            )
        )
    return connected


async def fetch_instagram_business_accounts(access_token: str) -> List[Dict[str, Any]]:
    response = meta_graph_request(
        "GET",
        "/me/accounts",
        access_token,
        params={
            "fields": "id,name,instagram_business_account{id,username,profile_picture_url}",
            "limit": 25,
        },
    )
    accounts = []
    for page in response.json().get("data", []) or []:
        instagram = page.get("instagram_business_account") or {}
        if not instagram.get("id"):
            continue
        accounts.append(
            {
                "account_id": str(instagram["id"]),
                "username": (instagram.get("username") or "").strip(),
                "account_name": (instagram.get("username") or page.get("name") or "Instagram Account").strip(),
                "page_id": str(page.get("id") or "").strip(),
                "page_name": (page.get("name") or "").strip(),
                "profile_picture_url": (instagram.get("profile_picture_url") or "").strip(),
            }
        )
    return accounts


async def connect_instagram_social_accounts(
    user: Dict[str, Any],
    access_token: str,
    *,
    refresh_token: str = "",
    token_expires_at: str = "",
    page_id: str = "",
    instagram_account_id: str = "",
    account_name: str = "",
) -> List[Dict[str, Any]]:
    accounts = await fetch_instagram_business_accounts(access_token)
    requested_account_id = str(instagram_account_id or "").strip()
    if requested_account_id:
        accounts = [item for item in accounts if item["account_id"] == requested_account_id]
    if not accounts and requested_account_id:
        accounts = [
            {
                "account_id": requested_account_id,
                "username": "",
                "account_name": account_name.strip() or "Instagram Professional Account",
                "page_id": str(page_id or "").strip(),
                "page_name": "",
                "profile_picture_url": "",
            }
        ]
    if not accounts:
        raise HTTPException(
            status_code=400,
            detail="No Instagram Professional account linked to a Facebook Page was found for this token.",
        )

    connected = []
    for account in accounts:
        connected.append(
            await upsert_social_connected_account(
                user,
                SOCIAL_PUBLISH_PROVIDER_INSTAGRAM,
                account["account_id"],
                account_name=account["account_name"],
                username=account["username"],
                page_id=account["page_id"],
                scopes=get_instagram_social_scopes().split(","),
                access_token=access_token,
                refresh_token=refresh_token,
                token_expires_at=token_expires_at,
                metadata={
                    "page_name": account["page_name"],
                    "profile_picture_url": account["profile_picture_url"],
                },
            )
        )
    return connected


async def publish_linkedin_social_post(post: Dict[str, Any], account: Dict[str, Any]) -> Dict[str, Any]:
    access_token = decrypt_social_token(account.get("access_token", ""))
    if not access_token:
        raise HTTPException(status_code=400, detail="LinkedIn access token is missing")
    organization_id = normalize_linkedin_organization_id(account.get("organization_id") or account.get("account_id"))
    if not organization_id:
        raise HTTPException(status_code=400, detail="LinkedIn organization id is missing")
    payload = {
        "author": f"urn:li:organization:{organization_id}",
        "commentary": compose_social_post_text(post, max_length=2800),
        "visibility": "PUBLIC",
        "distribution": {
            "feedDistribution": "MAIN_FEED",
            "targetEntities": [],
            "thirdPartyDistributionChannels": [],
        },
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False,
    }
    response = linkedin_rest_request("POST", "/posts", access_token, json=payload)
    response_json = response.json() if response.content else {}
    external_post_id = response_json.get("id") or response.headers.get("x-restli-id", "")
    return {
        "external_post_id": external_post_id,
        "provider_response": response_json,
    }


async def publish_instagram_social_post(post: Dict[str, Any], account: Dict[str, Any]) -> Dict[str, Any]:
    access_token = decrypt_social_token(account.get("access_token", ""))
    if not access_token:
        raise HTTPException(status_code=400, detail="Instagram access token is missing")
    account_id = str(account.get("account_id") or "").strip()
    if not account_id:
        raise HTTPException(status_code=400, detail="Instagram account id is missing")
    image_url = (post.get("asset_url") or "").strip()
    if not image_url and post.get("use_generated_card", True):
        image_url = build_social_post_card_url(post["id"])
    if not image_url:
        raise HTTPException(status_code=400, detail="Instagram publishing requires a public image URL")

    create_container = meta_graph_request(
        "POST",
        f"/{account_id}/media",
        access_token,
        params={
            "image_url": image_url,
            "caption": compose_social_post_text(post, max_length=2200),
        },
    ).json()
    creation_id = create_container.get("id")
    if not creation_id:
        raise HTTPException(status_code=502, detail="Instagram media container could not be created")

    publish_response = meta_graph_request(
        "POST",
        f"/{account_id}/media_publish",
        access_token,
        params={"creation_id": creation_id},
    ).json()
    return {
        "external_post_id": publish_response.get("id", ""),
        "provider_response": {
            "container": create_container,
            "publish": publish_response,
        },
    }


async def publish_social_post_record(post_id: str, *, user: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    query = {"id": post_id}
    if user is not None:
        query["user_id"] = user_id_str(user)
    post = await db.social_posts.find_one(query)
    if not post:
        raise HTTPException(status_code=404, detail="Social post not found")

    account = await db.social_connected_accounts.find_one(
        {"id": post["social_account_id"], "user_id": post["user_id"]}
    )
    if not account:
        raise HTTPException(status_code=400, detail="Connected social account is missing for this post")

    await db.social_posts.update_one(
        {"id": post_id},
        {
            "$set": {
                "status": SOCIAL_POST_STATUS_PUBLISHING,
                "last_attempt_at": now_iso(),
                "updated_at": now_iso(),
                "failure_reason": "",
            },
            "$inc": {"attempt_count": 1},
        },
    )

    try:
        if account["provider"] == SOCIAL_PUBLISH_PROVIDER_LINKEDIN:
            publish_result = await publish_linkedin_social_post(post, account)
        elif account["provider"] == SOCIAL_PUBLISH_PROVIDER_INSTAGRAM:
            publish_result = await publish_instagram_social_post(post, account)
        else:
            raise HTTPException(status_code=400, detail="Unsupported social publishing provider")

        await db.social_posts.update_one(
            {"id": post_id},
            {
                "$set": {
                    "status": SOCIAL_POST_STATUS_PUBLISHED,
                    "published_at": now_iso(),
                    "updated_at": now_iso(),
                    "external_post_id": publish_result.get("external_post_id", ""),
                    "provider_response": publish_result.get("provider_response", {}),
                    "failure_reason": "",
                }
            },
        )
        await db.social_connected_accounts.update_one(
            {"id": account["id"]},
            {"$set": {"last_published_at": now_iso(), "updated_at": now_iso()}},
        )
    except HTTPException as exc:
        await db.social_posts.update_one(
            {"id": post_id},
            {"$set": {"status": SOCIAL_POST_STATUS_FAILED, "updated_at": now_iso(), "failure_reason": exc.detail}},
        )
        raise
    except Exception as exc:
        await db.social_posts.update_one(
            {"id": post_id},
            {
                "$set": {
                    "status": SOCIAL_POST_STATUS_FAILED,
                    "updated_at": now_iso(),
                    "failure_reason": str(exc),
                }
            },
        )
        raise HTTPException(status_code=500, detail=f"Social publish failed: {exc}")

    updated = await db.social_posts.find_one({"id": post_id})
    return sanitize_social_post(updated)


async def process_due_social_posts(limit: int = SOCIAL_QUEUE_BATCH_SIZE) -> List[Dict[str, Any]]:
    global social_queue_lock
    if social_queue_lock is None:
        social_queue_lock = asyncio.Lock()
    if social_queue_lock.locked():
        return []

    async with social_queue_lock:
        queued = await db.social_posts.find({"status": SOCIAL_POST_STATUS_QUEUED}).sort("scheduled_at", 1).limit(max(5, limit * 3)).to_list(max(5, limit * 3))
        now_dt = datetime.now(timezone.utc)
        due_posts = []
        for post in queued:
            scheduled_at = parse_iso_datetime(post.get("scheduled_at"))
            if scheduled_at is None or scheduled_at <= now_dt:
                due_posts.append(post)
            if len(due_posts) >= limit:
                break

        results = []
        for post in due_posts:
            try:
                results.append(await publish_social_post_record(post["id"]))
            except Exception as exc:
                logger.error(f"Queued social publish failed for {post['id']}: {exc}")
        return results


async def social_queue_daemon():
    while True:
        try:
            await process_due_social_posts()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error(f"Social queue daemon error: {exc}")
        await asyncio.sleep(SOCIAL_QUEUE_POLL_SECONDS)


async def build_social_analytics(user: Dict[str, Any]) -> Dict[str, Any]:
    accounts = await db.social_connected_accounts.find({"user_id": user_id_str(user)}).to_list(50)
    posts = await db.social_posts.find({"user_id": user_id_str(user)}).sort("created_at", -1).to_list(200)
    by_provider: Dict[str, Dict[str, Any]] = {}
    for provider in SUPPORTED_SOCIAL_PUBLISH_PROVIDERS:
        provider_accounts = [account for account in accounts if account.get("provider") == provider]
        provider_posts = [post for post in posts if post.get("provider") == provider]
        by_provider[provider] = {
            "connected_accounts": len(provider_accounts),
            "queued": len([post for post in provider_posts if post.get("status") == SOCIAL_POST_STATUS_QUEUED]),
            "published": len([post for post in provider_posts if post.get("status") == SOCIAL_POST_STATUS_PUBLISHED]),
            "failed": len([post for post in provider_posts if post.get("status") == SOCIAL_POST_STATUS_FAILED]),
            "latest_post_at": next((post.get("published_at") or post.get("created_at") for post in provider_posts if post.get("published_at") or post.get("created_at")), ""),
        }

    published_posts = [post for post in posts if post.get("status") == SOCIAL_POST_STATUS_PUBLISHED]
    queued_posts = [post for post in posts if post.get("status") == SOCIAL_POST_STATUS_QUEUED]
    failed_posts = [post for post in posts if post.get("status") == SOCIAL_POST_STATUS_FAILED]

    return {
        "overview": {
            "connected_accounts": len(accounts),
            "published_posts": len(published_posts),
            "queued_posts": len(queued_posts),
            "failed_posts": len(failed_posts),
            "recent_success_rate": round((len(published_posts) / max(1, len(published_posts) + len(failed_posts))) * 100, 1),
        },
        "by_provider": by_provider,
        "recent_posts": [sanitize_social_post(post) for post in posts[:12]],
        "connected_accounts_detail": [sanitize_social_account(account) for account in accounts],
    }


FEEDBACK_PROBLEM_PATTERNS = [
    ("signup_conversion", ["signup", "sign up", "login", "account", "register", "onboarding"]),
    ("creator_ai_studio", ["create with ai", "ai studio", "draft", "script", "voice", "tts", "agent 2", "quality"]),
    ("podcast_discovery", ["browse", "recommend", "search", "filter", "discover", "category", "home feed"]),
    ("playback_reliability", ["play", "audio", "video", "buffer", "loading", "stream", "queue", "resume"]),
    ("creator_workflow", ["upload", "publish", "show", "season", "episode", "thumbnail", "rss"]),
    ("trust_safety", ["safety", "harmful", "hateful", "fact", "moderation", "trust", "age"]),
    ("pricing_value", ["price", "pricing", "pay", "subscription", "cost", "free", "plan"]),
    ("investor_signal", ["investor", "traction", "launch", "product hunt", "growth", "users"]),
]


def normalize_feedback_rating(value: Optional[int]) -> Optional[int]:
    if value in [None, ""]:
        return None
    try:
        rating = int(value)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Feedback rating must be a number")
    if rating < 1 or rating > 5:
        raise HTTPException(status_code=400, detail="Feedback rating must be between 1 and 5")
    return rating


def classify_feedback_text(message: str, desired_outcome: str = "", friction_area: str = "") -> Dict[str, Any]:
    text = f"{message} {desired_outcome} {friction_area}".lower()
    matched = []
    for problem_key, patterns in FEEDBACK_PROBLEM_PATTERNS:
        if any(pattern in text for pattern in patterns):
            matched.append(problem_key)
    if not matched:
        matched.append("general_product_learning")

    urgency = "medium"
    if any(term in text for term in ["broken", "cannot", "can't", "not working", "does not work", "failed", "crash"]):
        urgency = "high"
    elif any(term in text for term in ["nice", "wish", "maybe", "could", "confusing"]):
        urgency = "medium"
    elif any(term in text for term in ["love", "great", "useful", "delight"]):
        urgency = "low"

    sentiment = "neutral"
    if any(term in text for term in ["love", "great", "amazing", "useful", "delight", "excellent"]):
        sentiment = "positive"
    if any(term in text for term in ["bad", "confusing", "frustrating", "broken", "slow", "not working", "hate"]):
        sentiment = "negative"

    return {
        "problem_areas": matched[:4],
        "urgency": urgency,
        "sentiment": sentiment,
        "business_analyst_rlaif": {
            "reward_signal": "prioritize" if urgency == "high" or sentiment == "negative" else "learn",
            "reason": "High-friction feedback should feed product prioritization before launch." if urgency == "high" else "Use this as a product-learning signal for positioning and roadmap decisions.",
        },
    }


def build_feedback_summary(feedback: Dict[str, Any]) -> Dict[str, Any]:
    analysis = feedback.get("analysis") or {}
    problem_areas = analysis.get("problem_areas") or []
    first_problem = problem_areas[0] if problem_areas else "general_product_learning"
    persona = feedback.get("persona") or "visitor"
    return {
        "id": feedback.get("id"),
        "persona": persona,
        "category": feedback.get("category", "other"),
        "rating": feedback.get("rating"),
        "problem_area": first_problem,
        "urgency": analysis.get("urgency", "medium"),
        "sentiment": analysis.get("sentiment", "neutral"),
        "message": feedback.get("message", ""),
        "desired_outcome": feedback.get("desired_outcome", ""),
        "created_at": feedback.get("created_at"),
        "contact_ok": bool(feedback.get("contact_ok")),
        "email": feedback.get("email", ""),
    }


def sanitize_feedback_record(feedback: Dict[str, Any], include_email: bool = False) -> Dict[str, Any]:
    cleaned = clean_doc(feedback) or {}
    if not include_email:
        cleaned.pop("email", None)
    return cleaned


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


def get_ai_text_local_base_url() -> str:
    return (
        os.environ.get("AI_TEXT_LOCAL_BASE_URL")
        or os.environ.get("OLLAMA_BASE_URL")
        or "http://localhost:11434"
    ).strip().rstrip("/")


def get_ai_text_provider_order() -> List[str]:
    requested = os.environ.get("AI_TEXT_PROVIDER", "auto").strip().lower() or "auto"
    allow_remote = parse_bool_env("AI_TEXT_ALLOW_REMOTE", True)
    aliases = {
        "fallback": AI_TEXT_PROVIDER_DETERMINISTIC,
        "local": AI_TEXT_PROVIDER_OLLAMA,
        "local_ollama": AI_TEXT_PROVIDER_OLLAMA,
        "none": AI_TEXT_PROVIDER_DETERMINISTIC,
    }

    if requested == "auto":
        order = []
        local_requested = parse_bool_env("AI_TEXT_LOCAL_ENABLED", False)
        if local_requested:
            order.append(AI_TEXT_PROVIDER_OLLAMA)
        if allow_remote and EMERGENT_KEY:
            order.append(AI_TEXT_PROVIDER_EMERGENT)
        order.append(AI_TEXT_PROVIDER_DETERMINISTIC)
    else:
        order = [aliases.get(item.strip(), item.strip()) for item in requested.split(",") if item.strip()]

    normalized = []
    for provider in order:
        if provider not in AI_TEXT_PROVIDERS:
            continue
        if provider == AI_TEXT_PROVIDER_EMERGENT and (not allow_remote or not EMERGENT_KEY):
            continue
        if provider not in normalized:
            normalized.append(provider)

    return normalized or [AI_TEXT_PROVIDER_DETERMINISTIC]


def call_ollama_chat_json_sync(system_message: str, prompt: str, task_name: str) -> str:
    base_url = get_ai_text_local_base_url()
    if not base_url:
        raise RuntimeError("AI_TEXT_LOCAL_BASE_URL or OLLAMA_BASE_URL is required for local text generation")

    payload = {
        "model": os.environ.get("AI_TEXT_LOCAL_MODEL", "llama3.2:3b").strip() or "llama3.2:3b",
        "stream": False,
        "format": "json",
        "messages": [
            {"role": "system", "content": system_message},
            {"role": "user", "content": prompt},
        ],
        "options": {
            "temperature": parse_float_env("AI_TEXT_TEMPERATURE", 0.7),
            "num_ctx": parse_int_env("AI_TEXT_CONTEXT_TOKENS", 8192),
        },
    }
    response = requests.post(
        f"{base_url}/api/chat",
        json=payload,
        timeout=parse_int_env("AI_TEXT_TIMEOUT_SECONDS", 240),
    )
    response.raise_for_status()
    body = response.json()
    content = (body.get("message") or {}).get("content") or body.get("response") or ""
    if not content:
        raise RuntimeError(f"Ollama returned an empty response for {task_name}")
    return content


async def call_emergent_chat_json(system_message: str, prompt: str, task_name: str) -> str:
    if not EMERGENT_KEY:
        raise RuntimeError("EMERGENT_LLM_KEY is not configured")

    from emergentintegrations.llm.chat import LlmChat, UserMessage

    chat = LlmChat(
        api_key=EMERGENT_KEY,
        session_id=f"{task_name}-{uuid.uuid4()}",
        system_message=system_message,
    ).with_model(os.environ.get("AI_TEXT_REMOTE_PROVIDER", "openai"), os.environ.get("AI_TEXT_REMOTE_MODEL", "gpt-5.2"))
    return await chat.send_message(UserMessage(text=prompt))


async def run_ai_json_chat(
    task_name: str,
    system_message: str,
    prompt: str,
    expected_type: Any = dict,
) -> Dict[str, Any]:
    errors = []
    for provider in get_ai_text_provider_order():
        if provider == AI_TEXT_PROVIDER_DETERMINISTIC:
            return {"provider": provider, "raw": None, "errors": errors}
        try:
            if provider == AI_TEXT_PROVIDER_OLLAMA:
                response_text = await asyncio.to_thread(call_ollama_chat_json_sync, system_message, prompt, task_name)
            elif provider == AI_TEXT_PROVIDER_EMERGENT:
                response_text = await call_emergent_chat_json(system_message, prompt, task_name)
            else:
                continue

            raw = parse_json_payload(response_text)
            if isinstance(raw, expected_type):
                return {"provider": provider, "raw": raw, "errors": errors}
            errors.append(f"{provider}: expected {expected_type}, got {type(raw).__name__}")
        except Exception as exc:
            logger.warning(f"AI text provider {provider} failed for {task_name}: {exc}")
            errors.append(f"{provider}: {str(exc)[:240]}")

    return {"provider": AI_TEXT_PROVIDER_DETERMINISTIC, "raw": None, "errors": errors}


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


def normalize_audio_script_turns(items: Any, limit: int = 48) -> List[Dict[str, str]]:
    if not isinstance(items, list):
        return []

    normalized = []
    for item in items[:limit]:
        if isinstance(item, dict):
            speaker = str(item.get("speaker") or item.get("name") or item.get("role") or "Host").strip() or "Host"
            voice_role = str(item.get("voice_role") or item.get("voiceRole") or item.get("role") or "").strip().lower()
            voice_id = str(item.get("voice_id") or item.get("voiceId") or "").strip()
            text = str(item.get("text") or item.get("line") or item.get("script") or "").strip()
        else:
            speaker = "Host"
            voice_role = "host"
            voice_id = ""
            text = str(item).strip()

        if not text:
            continue

        if voice_role not in AI_AUDIO_VOICE_ROLES:
            lowered_speaker = speaker.lower()
            if "guest" in lowered_speaker or "cohost" in lowered_speaker or "co-host" in lowered_speaker:
                voice_role = "guest"
            elif "narrator" in lowered_speaker or "story" in lowered_speaker:
                voice_role = "narrator"
            else:
                voice_role = "host"

        text = re.sub(r"\s+", " ", text).strip()
        turn = {"speaker": speaker[:80], "voice_role": voice_role, "text": text}
        if voice_id in AI_PODCAST_VOICE_BY_ID:
            profile = AI_PODCAST_VOICE_BY_ID[voice_id]
            turn.update({"voice_id": profile["id"], "voice_name": profile["name"], "voice_gender": profile["gender"], "voice_style": profile["style"]})
        normalized.append(turn)

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
        "voice_clarity": {},
        "voice_clarity_status": "",
        "voice_clarity_score": 0,
    }
    if media_analysis:
        voice_clarity = media_analysis.get("voice_clarity") or {}
        media_fields.update(
            {
                "media_reviewed": bool(media_analysis.get("media_reviewed")),
                "media_review_status": media_analysis.get("status", "unknown"),
                "media_review_provider": media_analysis.get("provider", ""),
                "media_transcript_excerpt": media_analysis.get("transcript_excerpt", "")[:2400],
                "media_transcript_word_count": int(media_analysis.get("word_count") or 0),
                "media_transcript_truncated": bool(media_analysis.get("transcript_truncated")),
                "media_review_error": str(media_analysis.get("error") or "")[:240],
                "voice_clarity": voice_clarity,
                "voice_clarity_status": voice_clarity.get("status", ""),
                "voice_clarity_score": voice_clarity.get("score", 0),
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


def voice_clarity_unavailable(status: str, error: str = "") -> Dict[str, Any]:
    return {
        "status": status,
        "score": 0,
        "summary": error or "Voice clarity could not be measured.",
        "provider": "ffmpeg+pcm-metrics",
        "duration_seconds": 0,
        "rms_dbfs": None,
        "peak_dbfs": None,
        "silence_ratio": None,
        "pause_ratio": None,
        "dynamic_range_db": None,
        "crest_factor_db": None,
        "clipping_ratio": None,
        "zero_crossing_rate": None,
        "error": error[:240],
        "method_note": "Signal-level clarity heuristic over extracted mono PCM audio; not a human listening review.",
    }


def analyze_voice_clarity(data: bytes, filename: str, content_type: str, provider: str = "") -> Dict[str, Any]:
    if not data:
        return voice_clarity_unavailable("empty_audio", "No audio data was available for voice clarity analysis.")
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return voice_clarity_unavailable("unavailable", "ffmpeg is required for voice clarity analysis.")

    max_seconds = max(0, parse_int_env("AI_AUDIO_CLARITY_MAX_SECONDS", 180))
    suffix = Path(filename or "episode.bin").suffix or ".bin"
    source_path = ""
    extracted_path = ""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as media_file:
            media_file.write(data)
            source_path = media_file.name

        extracted_path = f"{source_path}.clarity.wav"
        ffmpeg_cmd = [ffmpeg, "-y", "-i", source_path]
        if max_seconds:
            ffmpeg_cmd.extend(["-t", str(max_seconds)])
        ffmpeg_cmd.extend(["-vn", "-ac", "1", "-ar", "16000", "-sample_fmt", "s16", extracted_path])
        ffmpeg_run = subprocess.run(ffmpeg_cmd, capture_output=True, text=True, timeout=240)
        if ffmpeg_run.returncode != 0:
            raise RuntimeError((ffmpeg_run.stderr or ffmpeg_run.stdout or "ffmpeg conversion failed").strip())

        total_samples = 0
        sum_squares = 0.0
        peak_abs = 0
        quiet_samples = 0
        clipped_samples = 0
        zero_crossings = 0
        previous_sign = 0
        sample_rate = 16000
        silence_threshold = int(32768 * 0.012)
        clipping_threshold = int(32768 * 0.98)
        window_rms_values: List[float] = []
        quiet_windows = 0
        window_sum_squares = 0.0
        window_count = 0
        low_mid_energy = 0.0
        high_freq_energy = 0.0
        low_mid_state = 0.0
        high_cut_state = 0.0

        with wave.open(extracted_path, "rb") as wav_file:
            sample_rate = wav_file.getframerate() or sample_rate
            if wav_file.getsampwidth() != 2:
                raise RuntimeError("Voice clarity analyzer expected 16-bit PCM audio")
            window_size = max(1, sample_rate // 10)
            low_mid_alpha = 1 - math.exp(-2 * math.pi * 280 / sample_rate)
            high_cut_alpha = 1 - math.exp(-2 * math.pi * 3200 / sample_rate)

            def finalize_window():
                nonlocal quiet_windows, window_count, window_sum_squares
                if window_count <= 0:
                    return
                window_rms = math.sqrt(window_sum_squares / window_count)
                window_rms_dbfs = 20 * math.log10(max(window_rms, 1) / 32768)
                window_rms_values.append(window_rms_dbfs)
                if window_rms_dbfs <= -35:
                    quiet_windows += 1
                window_sum_squares = 0.0
                window_count = 0

            while True:
                frames = wav_file.readframes(sample_rate)
                if not frames:
                    break
                samples = array("h")
                samples.frombytes(frames)
                if sys.byteorder != "little":
                    samples.byteswap()
                for sample in samples:
                    value = int(sample)
                    float_value = float(value)
                    abs_value = abs(value)
                    total_samples += 1
                    sum_squares += value * value
                    window_sum_squares += value * value
                    window_count += 1
                    low_mid_state += low_mid_alpha * (float_value - low_mid_state)
                    high_cut_state += high_cut_alpha * (float_value - high_cut_state)
                    high_value = float_value - high_cut_state
                    low_mid_energy += low_mid_state * low_mid_state
                    high_freq_energy += high_value * high_value
                    peak_abs = max(peak_abs, abs_value)
                    if abs_value <= silence_threshold:
                        quiet_samples += 1
                    if abs_value >= clipping_threshold:
                        clipped_samples += 1
                    sign = 1 if value > silence_threshold else -1 if value < -silence_threshold else 0
                    if sign and previous_sign and sign != previous_sign:
                        zero_crossings += 1
                    if sign:
                        previous_sign = sign
                    if window_count >= window_size:
                        finalize_window()
            finalize_window()

        if total_samples <= 0:
            return voice_clarity_unavailable("empty_audio", "No decodable audio samples were found.")

        duration_seconds = total_samples / max(1, sample_rate)
        rms = math.sqrt(sum_squares / total_samples)
        rms_dbfs = 20 * math.log10(max(rms, 1) / 32768)
        peak_dbfs = 20 * math.log10(max(peak_abs, 1) / 32768)
        silence_ratio = quiet_samples / total_samples
        pause_ratio = quiet_windows / max(1, len(window_rms_values))
        clipping_ratio = clipped_samples / total_samples
        zero_crossing_rate = zero_crossings / total_samples
        crest_factor_db = peak_dbfs - rms_dbfs
        energy_denominator = max(sum_squares, 1.0)
        resonance_low_mid_ratio = max(0.0, min(1.0, low_mid_energy / energy_denominator))
        articulation_high_freq_ratio = max(0.0, min(1.0, high_freq_energy / energy_denominator))

        def percentile(values: List[float], pct: float) -> Optional[float]:
            if not values:
                return None
            ordered = sorted(values)
            position = (len(ordered) - 1) * pct
            lower = math.floor(position)
            upper = math.ceil(position)
            if lower == upper:
                return ordered[int(position)]
            return ordered[lower] * (upper - position) + ordered[upper] * (position - lower)

        voiced_windows = [value for value in window_rms_values if value > -60]
        low_dynamic = percentile(voiced_windows, 0.10)
        high_dynamic = percentile(voiced_windows, 0.90)
        dynamic_range_db = (high_dynamic - low_dynamic) if low_dynamic is not None and high_dynamic is not None else None

        def score_target_range(value: Optional[float], hard_low: float, ideal_low: float, ideal_high: float, hard_high: float) -> Optional[float]:
            if value is None:
                return None
            if ideal_low <= value <= ideal_high:
                return 100.0
            if value < hard_low or value > hard_high:
                return 0.0
            if value < ideal_low:
                span = max(ideal_low - hard_low, 0.0001)
                return max(0.0, min(100.0, ((value - hard_low) / span) * 100.0))
            span = max(hard_high - ideal_high, 0.0001)
            return max(0.0, min(100.0, ((hard_high - value) / span) * 100.0))

        def weighted_score(items: List[tuple[Optional[float], float]]) -> float:
            total = 0.0
            weight_total = 0.0
            for value, weight in items:
                if value is None:
                    continue
                total += value * weight
                weight_total += weight
            return round(total / weight_total, 1) if weight_total else 0.0

        loudness_comfort = score_target_range(rms_dbfs, -30.0, -23.0, -15.0, -9.0)
        dynamic_comfort = score_target_range(dynamic_range_db, 2.5, 4.0, 19.0, 28.0)
        zcr_comfort = score_target_range(zero_crossing_rate, 0.012, 0.03, 0.125, 0.19)
        pause_comfort = score_target_range(pause_ratio, 0.06, 0.11, 0.26, 0.38)
        resonance_band = score_target_range(resonance_low_mid_ratio, 0.02, 0.10, 0.60, 0.82)
        articulation_band = score_target_range(articulation_high_freq_ratio, 0.003, 0.006, 0.22, 0.38)
        resonance_score = weighted_score(
            [
                (resonance_band, 0.42),
                (dynamic_comfort, 0.20),
                (loudness_comfort, 0.20),
                (zcr_comfort, 0.18),
            ]
        )
        articulation_score = weighted_score(
            [
                (articulation_band, 0.30),
                (zcr_comfort, 0.24),
                (pause_comfort, 0.18),
                (loudness_comfort, 0.14),
                (100.0 if clipping_ratio <= 0.0005 else max(0.0, 100.0 - clipping_ratio * 2400), 0.14),
            ]
        )

        score = 100.0
        if duration_seconds < 5:
            score -= 35
        if rms_dbfs < -32:
            score -= min(28, (-32 - rms_dbfs) * 1.4)
        elif rms_dbfs > -8:
            score -= min(20, (rms_dbfs + 8) * 4)
        if peak_dbfs > -0.5:
            score -= 8
        if clipping_ratio > 0.0005:
            score -= min(30, clipping_ratio * 2400)
        if silence_ratio > 0.72:
            score -= min(24, (silence_ratio - 0.72) * 100)
        if zero_crossing_rate > 0.18:
            score -= min(12, (zero_crossing_rate - 0.18) * 80)
        elif zero_crossing_rate < 0.005 and duration_seconds > 10:
            score -= 8

        score = round(max(0, min(100, score)), 1)
        status = "clear" if score >= 75 else "review" if score >= 55 else "poor"
        if status == "clear":
            summary = "Voice signal is clear enough for publishing based on loudness, clipping, silence, and noise heuristics."
        elif status == "review":
            summary = "Voice signal is usable but should be reviewed for loudness, silence, or harshness before promotion."
        else:
            summary = "Voice signal has clarity risks and should be re-rendered or re-uploaded before publishing."

        return {
            "status": status,
            "score": score,
            "summary": summary,
            "provider": "ffmpeg+pcm-metrics",
            "source_provider": provider,
            "content_type": content_type,
            "duration_seconds": round(duration_seconds, 2),
            "rms_dbfs": round(rms_dbfs, 2),
            "peak_dbfs": round(peak_dbfs, 2),
            "silence_ratio": round(silence_ratio, 4),
            "pause_ratio": round(pause_ratio, 4),
            "dynamic_range_db": round(dynamic_range_db, 2) if dynamic_range_db is not None else None,
            "crest_factor_db": round(crest_factor_db, 2),
            "clipping_ratio": round(clipping_ratio, 6),
            "zero_crossing_rate": round(zero_crossing_rate, 6),
            "resonance_score": resonance_score,
            "resonance_low_mid_ratio": round(resonance_low_mid_ratio, 6),
            "articulation_score": articulation_score,
            "articulation_high_freq_ratio": round(articulation_high_freq_ratio, 6),
            "error": "",
            "method_note": "Signal-level clarity plus resonance/articulation proxy heuristics over extracted mono PCM audio; not a human listening review.",
        }
    except Exception as exc:
        logger.error(f"Voice clarity analysis failed for {filename or content_type}: {exc}")
        return voice_clarity_unavailable("analysis_failed", str(exc))
    finally:
        for path in [source_path, extracted_path]:
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass


def attach_voice_clarity(
    media_analysis: Dict[str, Any],
    data: bytes,
    filename: str,
    content_type: str,
    provider: str = "",
) -> Dict[str, Any]:
    enriched = dict(media_analysis or {})
    clarity = analyze_voice_clarity(data, filename, content_type, provider=provider)
    enriched["voice_clarity"] = clarity
    enriched["voice_clarity_status"] = clarity.get("status", "")
    enriched["voice_clarity_score"] = clarity.get("score", 0)
    return enriched


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

    max_seconds = max(0, parse_int_env("MAX_MEDIA_TRANSCRIPT_SECONDS", 180))
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
    if parse_bool_env("EPISODE_SAFETY_FAST_PATH", True) and fallback.get("status") == MODERATION_STATUS_CLEAR:
        fast_result = dict(fallback)
        fast_result["provider"] = "heuristic-fast-path"
        fast_result["summary"] = (
            f"{fallback.get('summary', 'No obvious safety risk detected')} "
            "Clean packages use the local fast path so publishing stays responsive; risky packages still escalate."
        ).strip()
        return normalize_episode_safety_result(fast_result, fallback, selected_rating, media_analysis=media_analysis)

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
    result = await run_ai_json_chat(
        "episode-safety",
        "You are a careful podcast safety reviewer. Be conservative, concise, and return JSON only.",
        prompt,
        expected_type=dict,
    )
    raw = result.get("raw")
    if isinstance(raw, dict):
        return normalize_episode_safety_result(raw, fallback, selected_rating, media_analysis=media_analysis)
    if result.get("errors"):
        logger.warning(f"Episode safety review used heuristic fallback after provider errors: {result['errors'][-2:]}")
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
        dialogue_turns = normalize_audio_script_turns(generation.get("audio_script_turns"), limit=24)
        dialogue_lines = [
            f"{turn.get('speaker') or turn.get('voice_role') or 'Speaker'}: {turn.get('text', '')[:360]}"
            for turn in dialogue_turns[:18]
            if turn.get("text")
        ]
        parts.extend(
            [
                f"Promise: {generation.get('one_line_promise', '')}",
                f"Hook: {generation.get('hook', '')}",
                f"Intro: {generation.get('intro_script', '')}",
                f"Talking points: {', '.join(normalize_string_list(generation.get('talking_points'), limit=10))}",
                f"Outline: {' | '.join(outline_lines)}",
                "Audio dialogue turns:\n" + "\n".join(dialogue_lines),
                f"Notes: {generation.get('show_notes_summary', '')}",
            ]
        )
    if media_analysis and media_analysis.get("transcript_text"):
        parts.append(f"Transcript: {media_analysis.get('transcript_text', '')}")
    elif media_analysis and media_analysis.get("transcript_excerpt"):
        parts.append(f"Transcript excerpt: {media_analysis.get('transcript_excerpt', '')}")
    if media_analysis and media_analysis.get("voice_clarity"):
        clarity = media_analysis.get("voice_clarity") or {}
        parts.append(
            "Voice clarity: "
            f"{clarity.get('score', 0)}/100 {clarity.get('status', '')}; "
            f"resonance {clarity.get('resonance_score', 'n/a')}/100; "
            f"articulation {clarity.get('articulation_score', 'n/a')}/100; "
            f"rms {clarity.get('rms_dbfs')}; peak {clarity.get('peak_dbfs')}; "
            f"silence {clarity.get('silence_ratio')}; clipping {clarity.get('clipping_ratio')}. "
            f"{clarity.get('summary', '')}"
        )
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
    speaker_turn_pattern = r"(?im)^\s*(host|co[-\s]?host|guest|narrator|analyst|expert|speaker\s*\d+)\s*:"
    speaker_turns = len(re.findall(speaker_turn_pattern, text or ""))
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
    human_narrative_depth = features["speaker_turn_count"] >= 8 and features["concrete_marker_count"] >= 10
    high_dialogue_depth = features["speaker_turn_count"] >= 12 and features["concrete_marker_count"] >= 12
    if features["question_rate"] < 0.05:
        score += 2 if human_narrative_depth else 9
    elif high_dialogue_depth:
        score -= 2
    score += min(18, features["generic_marker_count"] * 6)
    score += min(16, features["repetition_rate"] * 42)
    if features["concrete_marker_count"] >= 12:
        score -= 12
    elif features["concrete_marker_count"] >= 5:
        score -= 8
    if features["speaker_turn_count"] >= 16:
        score -= 12
    elif features["speaker_turn_count"] >= 8:
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
    has_human_depth = features.get("speaker_turn_count", 0) >= 8 and features.get("concrete_marker_count", 0) >= 10
    if features.get("question_rate", 0) < 0.05 and not has_human_depth:
        reward -= 5
        actions.append("Add at least one curiosity-led question.")
    elif has_human_depth:
        reward += 1
    if features.get("concrete_marker_count", 0) < 5:
        reward -= 8
        actions.append("Add a concrete example, story, or practical step.")
    elif features.get("concrete_marker_count", 0) >= 12:
        reward += 3
    if features.get("speaker_turn_count", 0) >= 8:
        reward += 4
    if 0.07 <= features.get("question_rate", 0) <= 0.22:
        reward += 2
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


def agent2_scorecard_item(score: float, note: str) -> Dict[str, Any]:
    return {
        "score": round(max(0, min(100, score)), 1),
        "note": note,
    }


def build_agent2_scorecard(
    gan_review: Dict[str, Any],
    rag_review: Dict[str, Any],
    rlaif_feedback: Dict[str, Any],
    generation: Optional[Dict[str, Any]] = None,
    media_analysis: Optional[Dict[str, Any]] = None,
    voice_review: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    generation = generation or {}
    features = gan_review.get("features", {})
    outline = normalize_outline_items(generation.get("outline"))
    turns = normalize_audio_script_turns(generation.get("audio_script_turns"), limit=64)
    talking_points = normalize_string_list(generation.get("talking_points"), limit=12)
    production_notes = normalize_string_list(generation.get("production_notes"), limit=12)
    hook = str(generation.get("hook") or generation.get("intro_script") or "").strip()
    voice_clarity = (media_analysis or {}).get("voice_clarity") or {}

    speaker_count = len({(turn.get("speaker") or turn.get("voice_role") or "Host").strip().lower() for turn in turns if turn.get("text")})
    concrete_count = float(features.get("concrete_marker_count", 0) or 0)
    generic_count = float(features.get("generic_marker_count", 0) or 0)
    question_rate = float(features.get("question_rate", 0) or 0)
    media_words = int((media_analysis or {}).get("word_count") or 0)
    voice_clarity_score = float(voice_clarity.get("score", 0) or 0) if voice_clarity else None
    resonance_score = float(voice_clarity.get("resonance_score", 0) or 0) if voice_clarity.get("resonance_score") is not None else None
    articulation_score = float(voice_clarity.get("articulation_score", 0) or 0) if voice_clarity.get("articulation_score") is not None else None

    hook_score = 72 + min(len(hook.split()), 28) * 0.6 - generic_count * 3
    dialogue_score = 68 + min(speaker_count, 3) * 8 + min(len(turns), 16) * 0.7 + min(question_rate * 100, 12)
    specificity_score = 62 + min(concrete_count, 8) * 4 + min(len(talking_points), 8) * 2 - generic_count * 5
    structure_score = 64 + min(len(outline), 5) * 5 + min(sum(len(section.get("beats") or []) for section in outline), 16) * 1.2
    factual_score = 90 if rag_review.get("status") == "clear" else 66 if rag_review.get("status") == "review" else 20
    script_audio_score = 70 + min(len(turns), 18) * 0.8 + min(len(production_notes), 6) * 2 + min(media_words / 50, 8)
    audio_metric_inputs = [script_audio_score]
    if voice_clarity_score is not None:
        audio_metric_inputs.append(voice_clarity_score)
    if resonance_score is not None:
        audio_metric_inputs.append(resonance_score)
    if articulation_score is not None:
        audio_metric_inputs.append(articulation_score)
    audio_score = sum(audio_metric_inputs) / max(1, len(audio_metric_inputs))
    readiness_inputs = [
        hook_score,
        dialogue_score,
        specificity_score,
        structure_score,
        factual_score,
        audio_score,
        rlaif_feedback.get("reward_score", 0),
    ]
    if voice_clarity_score is not None:
        readiness_inputs.append(voice_clarity_score)
    if resonance_score is not None:
        readiness_inputs.append(resonance_score)
    if articulation_score is not None:
        readiness_inputs.append(articulation_score)
    voice_listenability_score = (voice_review or {}).get("listenability_score")
    if voice_listenability_score is not None:
        readiness_inputs.append(float(voice_listenability_score))
    readiness_score = min(100, sum(readiness_inputs) / max(1, len(readiness_inputs)))

    scorecard = {
        "hook_strength": agent2_scorecard_item(hook_score, "Cold-open clarity, listener promise, and avoidance of generic setup."),
        "dialogue_realism": agent2_scorecard_item(dialogue_score, "Speaker variation, turn-taking, and question-led pacing."),
        "specificity": agent2_scorecard_item(specificity_score, "Concrete examples, named constraints, and low filler density."),
        "structure": agent2_scorecard_item(structure_score, "Outline completeness and section-to-beat cohesion."),
        "factual_safety": agent2_scorecard_item(factual_score, "RAG-style safety retrieval and claim-risk screening."),
        "audio_readiness": agent2_scorecard_item(audio_score, "Voice-ready turns, production notes, render preparedness, and measured audio clarity."),
    }
    if voice_clarity_score is not None:
        scorecard["voice_clarity"] = agent2_scorecard_item(voice_clarity_score, voice_clarity.get("summary") or "Measured signal clarity from rendered or uploaded audio.")
    if resonance_score is not None:
        scorecard["voice_resonance"] = agent2_scorecard_item(
            resonance_score,
            "Warm low-mid presence, stable timbre, and non-fatiguing brightness proxy.",
        )
    if articulation_score is not None:
        scorecard["voice_articulation"] = agent2_scorecard_item(
            articulation_score,
            "Word-formation clarity proxy: consonant definition, pacing room, and controlled sibilance.",
        )
    if voice_review and voice_review.get("listenability_score") is not None:
        scorecard["podcast_voice_listenability"] = agent2_scorecard_item(
            float(voice_review.get("listenability_score") or 0),
            voice_review.get("summary") or "Long-form podcast voice listenability.",
        )
    scorecard["publish_readiness"] = agent2_scorecard_item(readiness_score, "Combined Agent 2 signal for whether this can move toward publishing.")
    return scorecard


def evaluate_agent2_quality(
    title: str,
    description: str,
    generation: Optional[Dict[str, Any]] = None,
    media_analysis: Optional[Dict[str, Any]] = None,
    source_kind: str = "episode",
    voice_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    review_text = agent2_build_review_text(title, description, generation=generation, media_analysis=media_analysis)
    gan_review = agent2_gan_inspired_discriminator(review_text, generation=generation)
    rag_review = agent2_rag_safety_review(review_text)
    rlaif_feedback = agent2_rlaif_self_feedback(gan_review, rag_review, generation=generation)
    voice_review = score_podcast_voice_listenability(
        media_analysis,
        generation=generation,
        voice_context=voice_context,
        title=title,
        description=description,
    )
    scorecard = build_agent2_scorecard(
        gan_review,
        rag_review,
        rlaif_feedback,
        generation=generation,
        media_analysis=media_analysis,
        voice_review=voice_review,
    )
    voice_score = voice_review.get("listenability_score")
    if voice_score is not None:
        quality_score = round((rlaif_feedback["reward_score"] * 0.65) + (float(voice_score) * 0.35), 1)
    else:
        quality_score = rlaif_feedback["reward_score"]

    status = "pass"
    if rag_review["status"] == "blocked":
        status = "blocked"
    voice_clarity = (media_analysis or {}).get("voice_clarity") or {}
    if voice_clarity.get("status") == "poor":
        status = "revise"
    elif voice_review.get("status") == "revise":
        status = "revise"
    elif rag_review["status"] == "review" or gan_review["label"] == "high" or quality_score < 72:
        status = "revise"

    clarity_summary = ""
    if voice_clarity:
        clarity_summary = f"; voice clarity {voice_clarity.get('score', 0)}/100 {voice_clarity.get('status', '')}"
    voice_summary = ""
    if voice_score is not None:
        voice_summary = f"; voice listenability {voice_score}/100 {voice_review.get('status', '')}"

    return {
        "agent": "Agent 2 - Podcast Quality Reviewer",
        "version": AGENT2_VERSION,
        "source_kind": source_kind,
        "status": status,
        "quality_score": quality_score,
        "gan_discriminator": gan_review,
        "rag_safety": rag_review,
        "rlaif": rlaif_feedback,
        "scorecard": scorecard,
        "voice_clarity": voice_clarity,
        "podcast_voice": voice_review,
        "summary": (
            f"Agent 2 quality score {quality_score}/100; "
            f"AI-risk {gan_review['label']} {gan_review['score']}; RAG safety {rag_review['status']}"
            f"{clarity_summary}{voice_summary}."
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


def enforce_episode_moderation_gate(moderation: Dict[str, Any], stored_paths: Optional[List[str]] = None) -> None:
    if (moderation or {}).get("status") != MODERATION_STATUS_BLOCKED:
        return
    if stored_paths:
        cleanup_storage_paths(stored_paths, strict=False)
    raise HTTPException(
        status_code=422,
        detail=(moderation or {}).get("summary") or "Episode safety review blocked publishing.",
    )


async def revise_ai_generation_with_agent2_feedback(
    brief: Dict[str, Any],
    show: Dict[str, Any],
    generation: Dict[str, Any],
    quality_agent: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    if quality_agent.get("status") == "blocked":
        return None
    if quality_agent.get("quality_score", 0) >= 82 and quality_agent.get("gan_discriminator", {}).get("label") == "low":
        return None

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
        "audio_script_turns": [
            {
                "speaker": "Host | Guest | Narrator",
                "voice_role": "host | guest | narrator",
                "text": "voice-ready spoken text for this turn",
            }
        ],
        "recommended_category": "string",
    }
    prompt = (
        "Agent 2 reviewed this AI podcast package and produced RLAIF-style self-feedback.\n"
        "Revise the package once using the feedback. Keep the creator's topic, audience, tone, and goal intact.\n"
        "Do not add unsafe claims. Do not make it clickbait. Make it more concrete, human-paced, and useful.\n\n"
        "Also revise audio_script_turns so they are voice-ready spoken text, preserve speaker roles, and never imitate any real person's voice.\n\n"
        f"Show:\n{json.dumps({'title': show.get('title'), 'description': show.get('description'), 'category': show.get('category')}, ensure_ascii=True)}\n\n"
        f"Creator brief:\n{json.dumps(brief, ensure_ascii=True)}\n\n"
        f"Current package:\n{json.dumps(generation, ensure_ascii=True)}\n\n"
        f"Agent 2 review:\n{json.dumps(quality_agent, ensure_ascii=True)}\n\n"
        f"Return JSON matching this schema exactly:\n{json.dumps(schema, ensure_ascii=True)}"
    )
    result = await run_ai_json_chat(
        "agent2-rlaif-revision",
        "You are Agent 2, Audioraq's quality-improvement reviewer. Return revised JSON only.",
        prompt,
        expected_type=dict,
    )
    raw = result.get("raw")
    if isinstance(raw, dict):
        revised = normalize_ai_generation_response(raw, brief, show)
        revised["ai_text_revision_provider"] = result.get("provider", AI_TEXT_PROVIDER_DETERMINISTIC)
        return revised
    if result.get("errors"):
        logger.warning(f"Agent 2 RLAIF revision skipped after provider errors: {result['errors'][-2:]}")
    return None


def slugify_filename(value: str, fallback: str = "episode") -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (value or "").lower()).strip("-")
    return (slug or fallback)[:80]


def build_ai_audio_script(show: Dict[str, Any], title: str, generation: Dict[str, Any]) -> str:
    lines = [
        title,
        "",
    ]
    if generation.get("hook"):
        lines.extend([generation["hook"], ""])
    if generation.get("intro_script"):
        lines.extend([generation["intro_script"], ""])
    elif generation.get("one_line_promise"):
        lines.extend([generation["one_line_promise"], ""])

    outline = generation.get("outline") or []
    for section in outline[:5]:
        section_title = str(section.get("section_title") or "").strip()
        purpose = str(section.get("purpose") or "").strip()
        beats = normalize_string_list(section.get("beats"), limit=4)
        if section_title:
            lines.append(section_title)
        if purpose:
            lines.append(purpose)
        for beat in beats:
            lines.append(beat)
        lines.append("")

    talking_points = normalize_string_list(generation.get("talking_points"), limit=6)
    if talking_points:
        lines.append("Here are the main takeaways.")
        lines.extend(talking_points)
        lines.append("")

    if generation.get("show_notes_summary"):
        lines.extend([generation["show_notes_summary"], ""])
    if generation.get("outro_cta"):
        lines.append(generation["outro_cta"])
    else:
        lines.append(f"If this helped, follow {show.get('title') or 'this show'} on Audioraq for the next episode.")

    script = "\n".join(line.strip() for line in lines if line is not None)
    script = re.sub(r"\n{3,}", "\n\n", script).strip()
    words = script.split()
    max_words = parse_int_env("AI_AUDIO_MAX_WORDS", 1200)
    if len(words) > max_words:
        script = " ".join(words[:max_words]).rsplit(".", 1)[0].strip() + "."
    return script


def build_script_media_analysis(script_text: str, provider: str, voice_clarity: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return {
        "status": "script_reviewed",
        "provider": provider,
        "media_reviewed": True,
        "transcript_text": script_text,
        "transcript_excerpt": build_transcript_excerpt(script_text),
        "word_count": len((script_text or "").split()),
        "transcript_truncated": False,
        "error": "",
        "voice_clarity": voice_clarity or {},
        "voice_clarity_status": (voice_clarity or {}).get("status", ""),
        "voice_clarity_score": (voice_clarity or {}).get("score", 0),
    }


def audio_turns_to_script(turns: List[Dict[str, str]]) -> str:
    return "\n\n".join(
        f"{turn.get('speaker', 'Host')}: {turn.get('text', '').strip()}"
        for turn in turns
        if turn.get("text", "").strip()
    ).strip()


def cap_audio_script_turns(turns: List[Dict[str, str]]) -> List[Dict[str, str]]:
    max_words = parse_int_env("AI_AUDIO_MAX_WORDS", 1200)
    max_chars = parse_int_env("AI_AUDIO_TTS_MAX_CHARS", 4500)
    min_final_turn_words = parse_int_env("AI_AUDIO_MIN_FINAL_TURN_WORDS", 18)
    reserved_end_turns = max(0, parse_int_env("AI_AUDIO_RESERVED_END_TURNS", 2))

    def trim_text_to_budget(text: str, remaining_words: int, remaining_chars: int) -> str:
        text = (text or "").strip()
        if not text or remaining_words <= 0 or remaining_chars <= 0:
            return ""

        truncated = False
        words = text.split()
        if len(words) > remaining_words:
            if remaining_words < min_final_turn_words:
                return ""
            text = " ".join(words[:remaining_words])
            truncated = True

        if len(text) > remaining_chars:
            if remaining_chars < 140:
                return ""
            text = text[:remaining_chars].rsplit(" ", 1)[0].strip()
            sentence_boundary = max(text.rfind("."), text.rfind("?"), text.rfind("!"))
            if sentence_boundary >= 120:
                text = text[: sentence_boundary + 1].strip()
            elif text and text[-1] not in ".!?":
                text = f"{text.rstrip(' ,;:')}."
            truncated = True

        if truncated and len(text.split()) < min_final_turn_words:
            return ""
        return text.strip()

    normalized_turns = []
    for turn in turns:
        text = (turn.get("text") or "").strip()
        if text:
            normalized_turns.append({**turn, "text": text})

    if not normalized_turns:
        return []

    reserved_turns = []
    main_turns = normalized_turns
    if reserved_end_turns and len(normalized_turns) > reserved_end_turns + 2:
        reserved_turns = normalized_turns[-reserved_end_turns:]
        main_turns = normalized_turns[:-reserved_end_turns]

    reserved_words = sum(len(turn["text"].split()) for turn in reserved_turns)
    reserved_chars = sum(len(turn["text"]) for turn in reserved_turns)
    main_word_budget = max(max_words - reserved_words, 0) if reserved_turns else max_words
    main_char_budget = max(max_chars - reserved_chars, 0) if reserved_turns else max_chars
    capped = []
    word_count = 0
    char_count = 0

    for turn in main_turns:
        remaining_words = main_word_budget - word_count
        remaining_chars = main_char_budget - char_count
        text = trim_text_to_budget(turn["text"], remaining_words, remaining_chars)
        if not text:
            break
        capped.append({**turn, "text": text})
        word_count += len(text.split())
        char_count += len(text)

    for turn in reserved_turns:
        remaining_words = max_words - word_count
        remaining_chars = max_chars - char_count
        text = trim_text_to_budget(turn["text"], remaining_words, remaining_chars)
        if not text:
            continue
        capped.append({**turn, "text": text})
        word_count += len(text.split())
        char_count += len(text)
    return capped


def split_audio_turns_for_tts(turns: List[Dict[str, str]]) -> List[Dict[str, str]]:
    max_chars = parse_int_env("AI_AUDIO_TTS_MAX_CHARS_PER_TURN", 1400)
    max_sentences = parse_int_env("AI_AUDIO_TTS_MAX_SENTENCES_PER_TURN", 1, minimum=1, maximum=4)
    split_turns = []
    for turn in turns:
        text = (turn.get("text") or "").strip()
        if not text:
            continue
        sentences = tts_sentence_parts(text)
        if not sentences:
            continue
        if len(text) <= max_chars and len(sentences) <= max_sentences:
            split_turns.append({**turn, "text": normalize_local_tts_text(text)})
            continue
        buffer = ""
        sentence_count = 0
        for sentence in sentences:
            candidate = f"{buffer} {sentence}".strip()
            if len(candidate) <= max_chars and sentence_count < max_sentences:
                buffer = candidate
                sentence_count += 1
                continue
            if buffer:
                split_turns.append({**turn, "text": buffer})
            if len(sentence) > max_chars:
                buffer = sentence[:max_chars].rsplit(" ", 1)[0].strip()
            else:
                buffer = sentence
            sentence_count = 1
        if buffer:
            split_turns.append({**turn, "text": buffer})
    return split_turns


def build_ai_audio_turns(
    show: Dict[str, Any],
    title: str,
    generation: Dict[str, Any],
    intake: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, str]]:
    turns = normalize_audio_script_turns(generation.get("audio_script_turns"), limit=48)
    if not turns:
        format_name = ((intake or {}).get("toneStyle") or {}).get("format", "")
        questions = normalize_string_list(generation.get("guest_questions"), limit=5)
        talking_points = normalize_string_list(generation.get("talking_points"), limit=8)
        if format_name == "interview" and questions:
            turns = [
                {
                    "speaker": "Host",
                    "voice_role": "host",
                    "text": generation.get("intro_script")
                    or f"Welcome back to {show.get('title') or 'Audioraq'}. Today we are talking about {title}.",
                }
            ]
            for index, question in enumerate(questions[:4]):
                answer = talking_points[index] if index < len(talking_points) else generation.get("one_line_promise", "")
                turns.extend(
                    [
                        {"speaker": "Host", "voice_role": "host", "text": question},
                        {
                            "speaker": "Guest",
                            "voice_role": "guest",
                            "text": answer or "The important part is making the idea practical and memorable for the listener.",
                        },
                    ]
                )
            if generation.get("outro_cta"):
                turns.append({"speaker": "Host", "voice_role": "host", "text": generation["outro_cta"]})
        else:
            script = build_ai_audio_script(show, title, generation)
            paragraphs = [part.strip() for part in re.split(r"\n{2,}", script) if part.strip()]
            default_role = "narrator" if format_name == "narrative" else "host"
            default_speaker = "Narrator" if default_role == "narrator" else "Host"
            turns = [{"speaker": default_speaker, "voice_role": default_role, "text": paragraph} for paragraph in paragraphs]

    return apply_ai_voice_cast_to_turns(cap_audio_script_turns(turns), intake)


def get_ai_audio_provider_order() -> List[str]:
    requested = os.environ.get("AI_AUDIO_TTS_PROVIDER", "auto").strip().lower() or "auto"
    if requested == "auto":
        order = []
        if os.environ.get("AI_AUDIO_LOCAL_TTS_URL"):
            order.append("local_http")
        if os.environ.get("ELEVENLABS_API_KEY"):
            order.append("elevenlabs")
        if os.environ.get("OPENAI_API_KEY"):
            order.append("openai")
        if (
            apple_say_tts_available()
            and parse_bool_env("AI_AUDIO_TTS_APPLE_SAY_ENABLED", True)
            and not parse_bool_env("AI_AUDIO_REQUIRE_NEURAL_WORKER", False)
        ):
            order.append("apple_say")
        if not parse_bool_env("AI_AUDIO_REQUIRE_NEURAL_WORKER", False):
            order.append("local")
        return order or (["local_http"] if parse_bool_env("AI_AUDIO_REQUIRE_NEURAL_WORKER", False) else ["local"])

    aliases = {
        "apple": "apple_say",
        "apple-say": "apple_say",
        "macos": "apple_say",
        "macos_say": "apple_say",
        "macos-say": "apple_say",
        "say": "apple_say",
        "espeak": "local",
        "espeak-ng": "local",
        "local-neural": "local_http",
        "http": "local_http",
    }
    order = [aliases.get(provider.strip(), provider.strip()) for provider in requested.split(",") if provider.strip()]
    if parse_bool_env("AI_AUDIO_TTS_LOCAL_FALLBACK", True) and "local" not in order and not parse_bool_env("AI_AUDIO_REQUIRE_NEURAL_WORKER", False):
        order.append("local")
    if parse_bool_env("AI_AUDIO_REQUIRE_NEURAL_WORKER", False):
        order = [provider for provider in order if provider not in {"local", "apple_say"}]
    return order or (["local_http"] if parse_bool_env("AI_AUDIO_REQUIRE_NEURAL_WORKER", False) else ["local"])


def safe_tts_error(exc: Exception) -> str:
    return re.sub(r"\s+", " ", str(exc)).strip()[:220]


def content_type_for_tts_output(output_format: str) -> str:
    if output_format.startswith("mp3"):
        return "audio/mpeg"
    if output_format.startswith("wav"):
        return "audio/wav"
    if output_format.startswith("pcm"):
        return "audio/L16"
    return "audio/mpeg"


def extension_for_content_type(content_type: str) -> str:
    if content_type == "audio/wav":
        return "wav"
    if content_type == "audio/L16":
        return "pcm"
    return "mp3"


def wav_silence_bytes(duration_seconds: float, reference_segment: bytes) -> bytes:
    sample_rate = 44100
    channels = 1
    sample_width = 2
    try:
        with wave.open(io.BytesIO(reference_segment), "rb") as wav_file:
            sample_rate = wav_file.getframerate() or sample_rate
            channels = wav_file.getnchannels() or channels
            sample_width = wav_file.getsampwidth() or sample_width
    except Exception:
        pass
    output = io.BytesIO()
    with wave.open(output, "wb") as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(sample_width)
        wav_file.setframerate(sample_rate)
        frame_count = max(1, int(sample_rate * max(0.0, duration_seconds)))
        wav_file.writeframes(b"\x00" * frame_count * channels * sample_width)
    return output.getvalue()


def compressed_silence_bytes(duration_seconds: float, extension: str) -> bytes:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return b""
    with tempfile.TemporaryDirectory(prefix="audioraq-tts-silence-") as temp_dir:
        temp_path = Path(temp_dir)
        output_path = temp_path / f"silence.{extension}"
        codec_args = ["-acodec", "libmp3lame", "-b:a", "128k"] if extension == "mp3" else ["-acodec", "pcm_s16le"]
        cmd = [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=r=44100:cl=mono",
            "-t",
            f"{max(0.01, duration_seconds):.3f}",
            *codec_args,
            str(output_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            logger.warning(f"Could not generate {extension} silence: {result.stderr or result.stdout}")
            return b""
        return output_path.read_bytes()


def audio_silence_segment(duration_seconds: float, extension: str, reference_segment: bytes) -> bytes:
    if duration_seconds <= 0:
        return b""
    if extension == "wav":
        return wav_silence_bytes(duration_seconds, reference_segment)
    return compressed_silence_bytes(duration_seconds, extension)


def apply_audio_segment_padding(
    segments: List[bytes],
    extension: str,
    gap_seconds: float,
    edge_padding_seconds: float,
) -> List[bytes]:
    if not segments:
        return segments
    silence_gap = audio_silence_segment(gap_seconds, extension, segments[0]) if gap_seconds > 0 else b""
    silence_edge = audio_silence_segment(edge_padding_seconds, extension, segments[0]) if edge_padding_seconds > 0 else b""
    padded = []
    if silence_edge:
        padded.append(silence_edge)
    for index, segment in enumerate(segments):
        if index and silence_gap:
            padded.append(silence_gap)
        padded.append(segment)
    if silence_edge:
        padded.append(silence_edge)
    return padded


def stitch_audio_segments(
    segments: List[bytes],
    extension: str = "mp3",
    gap_seconds: Optional[float] = None,
    edge_padding_seconds: Optional[float] = None,
) -> bytes:
    gap = ai_audio_sentence_gap_seconds() if gap_seconds is None else max(0.0, gap_seconds)
    edge = ai_audio_edge_padding_seconds() if edge_padding_seconds is None else max(0.0, edge_padding_seconds)
    segments = apply_audio_segment_padding(segments, extension, gap, edge)
    if len(segments) == 1:
        return segments[0]
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg is required to stitch multi-voice TTS audio segments")

    with tempfile.TemporaryDirectory(prefix="audioraq-tts-stitch-") as temp_dir:
        temp_path = Path(temp_dir)
        concat_path = temp_path / "concat.txt"
        output_path = temp_path / f"episode.{extension}"
        concat_lines = []
        for index, segment in enumerate(segments):
            segment_path = temp_path / f"segment-{index:03d}.{extension}"
            segment_path.write_bytes(segment)
            concat_lines.append(f"file '{segment_path}'")
        concat_path.write_text("\n".join(concat_lines) + "\n", encoding="utf-8")
        cmd = [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_path),
            "-vn",
            "-acodec",
            "libmp3lame" if extension == "mp3" else "pcm_s16le",
            "-b:a",
            "128k",
            str(output_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=240)
        if result.returncode != 0:
            if extension == "mp3":
                logger.warning(f"ffmpeg MP3 stitching failed; using safe byte concatenation fallback: {result.stderr or result.stdout}")
                data = b"".join(segments)
                if len(data) < 1024:
                    raise RuntimeError("byte-concatenated audio was empty after ffmpeg stitching failed")
                return data
            raise RuntimeError(result.stderr or result.stdout or "ffmpeg stitching failed")
        data = output_path.read_bytes()
        if len(data) < 1024:
            raise RuntimeError("ffmpeg stitched an empty audio file")
        return data


def local_tts_voice_profile() -> str:
    raw_profile = os.environ.get("AI_AUDIO_TTS_LOCAL_VOICE_PROFILE", "proof_studio").strip().lower()
    normalized = raw_profile.replace("-", "_")
    if normalized in {"proof_studio", "proof", "audioraq_proof"}:
        return "proof_studio"
    if normalized in {"dialogue", "multi_voice", "multivoice"}:
        return "dialogue"
    return "proof_studio"


def local_tts_role_config(voice_role: str) -> Dict[str, str]:
    role = voice_role if voice_role in AI_AUDIO_VOICE_ROLES else "host"
    role_key = role.upper()
    if local_tts_voice_profile() == "proof_studio":
        voice_defaults = {"host": "en-us+m3", "guest": "en-us+m3", "narrator": "en-us+m3"}
        speed_defaults = {"host": "158", "guest": "158", "narrator": "158"}
        pitch_defaults = {"host": "48", "guest": "48", "narrator": "48"}
        amplitude_defaults = {"host": "145", "guest": "145", "narrator": "145"}
    else:
        voice_defaults = {"host": "en-us+m3", "guest": "en-us+f3", "narrator": "en-us+m1"}
        speed_defaults = {"host": "158", "guest": "150", "narrator": "142"}
        pitch_defaults = {"host": "48", "guest": "58", "narrator": "42"}
        amplitude_defaults = {"host": "145", "guest": "135", "narrator": "140"}
    return {
        "voice": os.environ.get(f"AI_AUDIO_TTS_LOCAL_VOICE_{role_key}", voice_defaults[role]).strip() or voice_defaults[role],
        "speed": os.environ.get(f"AI_AUDIO_TTS_LOCAL_SPEED_{role_key}", speed_defaults[role]).strip() or speed_defaults[role],
        "pitch": os.environ.get(f"AI_AUDIO_TTS_LOCAL_PITCH_{role_key}", pitch_defaults[role]).strip() or pitch_defaults[role],
        "amplitude": os.environ.get(f"AI_AUDIO_TTS_LOCAL_AMPLITUDE_{role_key}", amplitude_defaults[role]).strip() or amplitude_defaults[role],
    }


def shape_tts_pronunciation(text: str) -> str:
    """Make synthetic speech easier to articulate without changing meaning."""
    text = text.replace("&", " and ")
    text = re.sub(r"\bQ\s*&\s*A\b", "Q and A", text, flags=re.IGNORECASE)
    text = re.sub(r"\bvs\.?\b", "versus", text, flags=re.IGNORECASE)
    text = re.sub(r"\be\.g\.", "for example", text, flags=re.IGNORECASE)
    text = re.sub(r"\bi\.e\.", "that is", text, flags=re.IGNORECASE)
    text = re.sub(r"(?<=\w)/(?=\w)", " and ", text)
    text = re.sub(r"(?<=\d)%", " percent", text)

    def spell_acronym(match: re.Match) -> str:
        acronym = match.group(0)
        if "." in acronym:
            return acronym
        return ".".join(acronym) + "."

    return re.sub(r"\b[A-Z]{2,6}\b", spell_acronym, text)


def normalize_local_tts_text(text: str) -> str:
    text = re.sub(r"\s+", " ", (text or "").strip())
    text = text.replace(" - ", ", ")
    text = shape_tts_pronunciation(text)
    text = re.sub(r"\s+", " ", text).strip()
    if text and text[-1] not in ".!?":
        text = f"{text}."
    return text


def postprocess_local_wav_audio(data: bytes) -> bytes:
    if not parse_bool_env("AI_AUDIO_TTS_LOCAL_POSTPROCESS", True):
        return data
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return data
    audio_filter = os.environ.get(
        "AI_AUDIO_TTS_LOCAL_FILTER",
        PROOF_STUDIO_LOCAL_FILTER,
    ).strip()
    with tempfile.TemporaryDirectory(prefix="audioraq-local-tts-post-") as temp_dir:
        temp_path = Path(temp_dir)
        input_path = temp_path / "input.wav"
        output_path = temp_path / "output.wav"
        input_path.write_bytes(data)
        cmd = [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(input_path),
            "-af",
            audio_filter,
            "-ar",
            "44100",
            "-ac",
            "1",
            str(output_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=240)
        if result.returncode != 0:
            logger.warning(f"Local TTS post-processing failed; using raw local output: {result.stderr or result.stdout}")
            return data
        processed = output_path.read_bytes()
        return processed if len(processed) >= 1024 else data


def transcode_local_tts_output(data: bytes) -> Tuple[bytes, str, str]:
    output_format = os.environ.get("AI_AUDIO_TTS_LOCAL_OUTPUT_FORMAT", "wav").strip().lower() or "wav"
    if output_format in {"wav", "wave"}:
        return data, "audio/wav", "wav"
    if output_format not in {"mp3", "mpeg"}:
        logger.warning(f"Unsupported AI_AUDIO_TTS_LOCAL_OUTPUT_FORMAT={output_format}; using WAV output")
        return data, "audio/wav", "wav"

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        logger.warning("ffmpeg is not installed; using WAV local TTS output")
        return data, "audio/wav", "wav"

    bitrate = os.environ.get("AI_AUDIO_TTS_LOCAL_MP3_BITRATE", "160k").strip() or "160k"
    with tempfile.TemporaryDirectory(prefix="audioraq-local-tts-transcode-") as temp_dir:
        temp_path = Path(temp_dir)
        input_path = temp_path / "input.wav"
        output_path = temp_path / "output.mp3"
        input_path.write_bytes(data)
        cmd = [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(input_path),
            "-vn",
            "-acodec",
            "libmp3lame",
            "-b:a",
            bitrate,
            "-ar",
            "44100",
            "-ac",
            "1",
            str(output_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=240)
        if result.returncode != 0:
            logger.warning(f"Local TTS MP3 transcode failed; using WAV output: {result.stderr or result.stdout}")
            return data, "audio/wav", "wav"
        transcoded = output_path.read_bytes()
        if len(transcoded) < 1024:
            logger.warning("Local TTS MP3 transcode produced an empty file; using WAV output")
            return data, "audio/wav", "wav"
        return transcoded, "audio/mpeg", "mp3"


def apple_say_tts_available() -> bool:
    return bool(shutil.which("say") and shutil.which("afconvert"))


def proof_studio_apple_role(voice_role: str, speaker: str = "") -> str:
    normalized_speaker = (speaker or "").strip().lower()
    if normalized_speaker in {"co-host", "cohost", "guest"}:
        return "guest"
    if normalized_speaker == "narrator":
        return "narrator"
    return voice_role if voice_role in AI_AUDIO_VOICE_ROLES else "host"


def synthesize_apple_say_turn(text: str, output_wav: Path, voices: List[str], rate_wpm: int) -> Tuple[str, float]:
    say = shutil.which("say")
    afconvert = shutil.which("afconvert")
    if not say or not afconvert:
        raise RuntimeError("Apple proof-studio voices require macOS say and afconvert")

    text_path = output_wav.with_suffix(".txt")
    text_path.write_text(normalize_local_tts_text(text), encoding="utf-8")
    last_error: Optional[Exception] = None
    for attempt, selected_voice in enumerate(dict.fromkeys(voices), start=1):
        tmp_aiff = output_wav.with_suffix(f".{attempt}.aiff")
        try:
            say_result = subprocess.run(
                [say, "-v", selected_voice, "-r", str(rate_wpm), "-o", str(tmp_aiff), "-f", str(text_path)],
                capture_output=True,
                text=True,
                timeout=240,
            )
            if say_result.returncode != 0:
                raise RuntimeError(say_result.stderr or say_result.stdout or "Apple say rendering failed")
            convert_result = subprocess.run([afconvert, "-f", "WAVE", "-d", "LEI16", str(tmp_aiff), str(output_wav)], capture_output=True, text=True, timeout=240)
            if convert_result.returncode != 0:
                raise RuntimeError(convert_result.stderr or convert_result.stdout or "Apple say WAV conversion failed")
            with wave.open(str(output_wav), "rb") as wav_file:
                duration_seconds = wav_file.getnframes() / max(1, wav_file.getframerate())
            min_duration = 0.16 if len((text or "").split()) <= 3 else 0.35
            if duration_seconds >= min_duration:
                return selected_voice, duration_seconds
            last_error = RuntimeError(f"Apple say voice {selected_voice} produced a short turn: {duration_seconds:.2f}s")
        except Exception as exc:
            last_error = exc
        finally:
            tmp_aiff.unlink(missing_ok=True)
    raise RuntimeError(f"Could not synthesize Apple proof-studio dialogue turn: {last_error}")


def concat_wav_files_with_silence(
    segment_paths: List[Path],
    output_wav: Path,
    gap_seconds: float = PROOF_STUDIO_APPLE_GAP_SECONDS,
    edge_padding_seconds: float = 1.0,
) -> None:
    if not segment_paths:
        raise RuntimeError("No Apple proof-studio audio segments were generated")
    with wave.open(str(segment_paths[0]), "rb") as first:
        params = first.getparams()
        framerate = first.getframerate()
        sample_width = first.getsampwidth()
        channels = first.getnchannels()
    silence_frames = int(framerate * max(0.0, gap_seconds))
    silence = b"\x00" * silence_frames * sample_width * channels
    edge_frames = int(framerate * max(0.0, edge_padding_seconds))
    edge_silence = b"\x00" * edge_frames * sample_width * channels
    with wave.open(str(output_wav), "wb") as out:
        out.setparams(params)
        if edge_silence:
            out.writeframes(edge_silence)
        for index, segment_path in enumerate(segment_paths):
            with wave.open(str(segment_path), "rb") as segment:
                if segment.getframerate() != framerate or segment.getsampwidth() != sample_width or segment.getnchannels() != channels:
                    raise RuntimeError(f"Apple proof-studio segment format mismatch: {segment_path}")
                out.writeframes(segment.readframes(segment.getnframes()))
                if index < len(segment_paths) - 1 and silence:
                    out.writeframes(silence)
        if edge_silence:
            out.writeframes(edge_silence)


def master_wav_peak_headroom(path: Path, target_peak_dbfs: float = PROOF_STUDIO_APPLE_TARGET_PEAK_DBFS) -> Dict[str, Any]:
    with wave.open(str(path), "rb") as wav_in:
        params = wav_in.getparams()
        frames = wav_in.readframes(wav_in.getnframes())
    if params.sampwidth != 2 or not frames:
        return {"target_peak_dbfs": target_peak_dbfs, "gain": 1.0, "peak_before": None, "peak_after": None}

    samples = array("h")
    samples.frombytes(frames)
    if sys.byteorder != "little":
        samples.byteswap()

    max_abs = max((abs(sample) for sample in samples), default=0)
    if max_abs <= 0:
        return {"target_peak_dbfs": target_peak_dbfs, "gain": 1.0, "peak_before": None, "peak_after": None}

    full_scale = float((1 << (params.sampwidth * 8 - 1)) - 1)
    target_abs = max(1, int(full_scale * (10 ** (target_peak_dbfs / 20.0))))
    gain = target_abs / max_abs
    mastered = array("h", (max(-32768, min(32767, int(round(sample * gain)))) for sample in samples))
    peak_after = max((abs(sample) for sample in mastered), default=0)
    if sys.byteorder != "little":
        mastered.byteswap()

    with wave.open(str(path), "wb") as wav_out:
        wav_out.setparams(params)
        wav_out.writeframes(mastered.tobytes())

    return {
        "target_peak_dbfs": target_peak_dbfs,
        "gain": round(gain, 4),
        "peak_before": round(20 * math.log10(max(max_abs / full_scale, 0.0000001)), 2),
        "peak_after": round(20 * math.log10(max(max(1, peak_after) / full_scale, 0.0000001)), 2),
    }


def render_apple_say_proof_audio(script_text: str, turns: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
    if not apple_say_tts_available():
        raise RuntimeError("Apple proof-studio TTS is only available on macOS with say and afconvert")

    rendered_turns = split_audio_turns_for_tts(turns or [{"speaker": "Host", "voice_role": "host", "text": script_text}])
    if not rendered_turns:
        raise RuntimeError("no voice turns were available for Apple proof-studio TTS")
    rendered_roles = [
        proof_studio_apple_role(str(turn.get("voice_role") or "host"), str(turn.get("speaker") or ""))
        for turn in rendered_turns
    ]
    narrative_mode = "narrator" in rendered_roles
    active_rates = PROOF_STUDIO_APPLE_NARRATIVE_RATES if narrative_mode else PROOF_STUDIO_APPLE_RATES
    turn_gap_seconds = ai_audio_sentence_gap_seconds()
    edge_padding_seconds = ai_audio_edge_padding_seconds()

    with tempfile.TemporaryDirectory(prefix="audioraq-apple-proof-") as temp_dir:
        temp_path = Path(temp_dir)
        segments = []
        voices = {}
        timings = []
        cursor = edge_padding_seconds
        for index, turn in enumerate(rendered_turns, start=1):
            role = rendered_roles[index - 1]
            voice_profile = AI_PODCAST_VOICE_BY_ID.get(str(turn.get("voice_id") or ""))
            voice_candidates = (
                list(voice_profile.get("apple_voices") or []) + PROOF_STUDIO_APPLE_VOICES.get(role, PROOF_STUDIO_APPLE_VOICES["host"])
                if voice_profile
                else PROOF_STUDIO_APPLE_VOICES.get(role, PROOF_STUDIO_APPLE_VOICES["host"])
            )
            rate_wpm = int(voice_profile.get("rate_wpm") or active_rates.get(role, active_rates["host"])) if voice_profile else active_rates.get(role, active_rates["host"])
            segment_path = temp_path / f"segment-{index:03d}-{role}.wav"
            selected_voice, duration_seconds = synthesize_apple_say_turn(
                turn.get("text") or "",
                segment_path,
                voice_candidates,
                rate_wpm,
            )
            speaker_key = turn.get("speaker") or role
            voices[speaker_key] = {
                "voice_id": voice_profile.get("id") if voice_profile else "",
                "display_name": voice_profile.get("name") if voice_profile else selected_voice,
                "gender": voice_profile.get("gender") if voice_profile else "",
                "style": voice_profile.get("style") if voice_profile else "",
                "engine_voice": selected_voice,
            }
            timings.append(
                {
                    "speaker": turn.get("speaker") or role.title(),
                    "voice_role": role,
                    "voice_id": voice_profile.get("id") if voice_profile else "",
                    "voice_name": voice_profile.get("name") if voice_profile else selected_voice,
                    "voice": selected_voice,
                    "start": round(cursor, 3),
                    "end": round(cursor + duration_seconds, 3),
                    "duration": round(duration_seconds, 3),
                }
            )
            cursor += duration_seconds + (turn_gap_seconds if index < len(rendered_turns) else edge_padding_seconds)
            segments.append(segment_path)

        output_path = temp_path / "episode.wav"
        concat_wav_files_with_silence(segments, output_path, gap_seconds=turn_gap_seconds, edge_padding_seconds=edge_padding_seconds)
        mastering = master_wav_peak_headroom(output_path)
        data = output_path.read_bytes()
        if len(data) < 1024:
            raise RuntimeError("Apple proof-studio TTS produced an empty audio file")
        return {
            "data": data,
            "content_type": "audio/wav",
            "provider": "apple-say:proof-studio",
            "provider_kind": "local-proof",
            "model": "macOS say",
            "voices": voices,
            "turn_count": len(rendered_turns),
            "chunk_count": len(segments),
            "timings": timings,
            "rates_wpm": active_rates,
            "turn_gap_seconds": turn_gap_seconds,
            "edge_padding_seconds": edge_padding_seconds,
            "mastering": mastering,
            "enhancement_profile": f"audioraq-qa-proof-dialogue+20-voice-library+calm-podcast-rate+{turn_gap_seconds}s-sentence-gaps+{edge_padding_seconds}s-edge-padding",
            "benchmark_note": "Replicates the April 11 QA proof-studio recipe using generic macOS system voices; does not clone a real person's voice.",
            "voice_profile": "apple_proof_studio",
            "extension": "wav",
            "filename": "ai-generated-episode.wav",
        }


def render_local_ai_audio(script_text: str, turns: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
    renderer = shutil.which("espeak-ng") or shutil.which("espeak")
    if not renderer:
        raise RuntimeError("local AI audio renderer is not installed")

    use_multivoice = parse_bool_env("AI_AUDIO_TTS_LOCAL_MULTIVOICE", True)
    if use_multivoice and turns:
        rendered_turns = split_audio_turns_for_tts(turns)
    else:
        host_config = local_tts_role_config("host")
        rendered_turns = [{"speaker": "Host", "voice_role": "host", "text": script_text, **host_config}]

    with tempfile.TemporaryDirectory(prefix="audioraq-ai-audio-") as temp_dir:
        temp_path = Path(temp_dir)
        segments = []
        voices = {}
        for index, turn in enumerate(rendered_turns):
            role = turn.get("voice_role") if turn.get("voice_role") in AI_AUDIO_VOICE_ROLES else "host"
            voice_profile = AI_PODCAST_VOICE_BY_ID.get(str(turn.get("voice_id") or ""))
            host_config = local_tts_role_config("host")
            if voice_profile and voice_profile.get("espeak"):
                profile_config = voice_profile["espeak"]
                config = {
                    "voice": str(profile_config.get("voice") or host_config["voice"]),
                    "speed": str(profile_config.get("speed") or host_config["speed"]),
                    "pitch": str(profile_config.get("pitch") or host_config["pitch"]),
                    "amplitude": str(profile_config.get("amplitude") or host_config["amplitude"]),
                }
            else:
                config = (
                    local_tts_role_config(role)
                    if use_multivoice and turns
                    else {
                        "voice": turn.get("voice") or host_config["voice"],
                        "speed": turn.get("speed") or host_config["speed"],
                        "pitch": turn.get("pitch") or host_config["pitch"],
                        "amplitude": turn.get("amplitude") or host_config["amplitude"],
                    }
                )
            speaker_key = turn.get("speaker") or role
            voices[speaker_key] = {
                "voice_id": voice_profile.get("id") if voice_profile else "",
                "display_name": voice_profile.get("name") if voice_profile else config["voice"],
                "gender": voice_profile.get("gender") if voice_profile else "",
                "style": voice_profile.get("style") if voice_profile else "",
                "engine_voice": config["voice"],
            }
            script_path = temp_path / f"script-{index:03d}.txt"
            output_path = temp_path / f"segment-{index:03d}.wav"
            script_path.write_text(normalize_local_tts_text(turn.get("text") or ""), encoding="utf-8")
            cmd = [
                renderer,
                "-v",
                config["voice"],
                "-s",
                config["speed"],
                "-p",
                config["pitch"],
                "-a",
                config["amplitude"],
                "-f",
                str(script_path),
                "-w",
                str(output_path),
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=240)
            if result.returncode != 0:
                logger.error(f"AI audio renderer failed: {result.stderr or result.stdout}")
                raise RuntimeError("local AI audio rendering failed")
            segment = output_path.read_bytes()
            if len(segment) >= 1024:
                segments.append(segment)
        if not segments:
            raise RuntimeError("local AI audio renderer produced no usable segments")
        data = stitch_audio_segments(segments, extension="wav")
        data = postprocess_local_wav_audio(data)
        data, content_type, extension = transcode_local_tts_output(data)
        if len(data) < 1024:
            raise RuntimeError("local AI audio renderer produced an empty file")
        return {
            "data": data,
            "content_type": content_type,
            "provider": f"{Path(renderer).name}:{local_tts_voice_profile()}-enhanced-local",
            "provider_kind": "local",
            "model": Path(renderer).name,
            "voices": voices or {"host": os.environ.get("AI_AUDIO_TTS_VOICE", "en-us").strip() or "en-us"},
            "turn_count": len(rendered_turns),
            "chunk_count": len(segments),
            "enhancement_profile": f"role-voice-variants+pacing+ffmpeg-normalization+{extension}-delivery",
            "benchmark_note": "Local espeak-ng fallback optimized for clarity; not equivalent to neural ElevenLabs production TTS.",
            "voice_profile": local_tts_voice_profile(),
            "extension": extension,
            "filename": f"ai-generated-episode.{extension}",
        }


def render_elevenlabs_ai_audio(turns: List[Dict[str, str]]) -> Dict[str, Any]:
    api_key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("ELEVENLABS_API_KEY is not configured")

    host_voice = os.environ.get("ELEVENLABS_VOICE_ID_HOST", "JBFqnCBsd6RMkjVDRZzb").strip() or "JBFqnCBsd6RMkjVDRZzb"
    voice_ids = {
        "host": host_voice,
        "guest": os.environ.get("ELEVENLABS_VOICE_ID_GUEST", "").strip() or host_voice,
        "narrator": os.environ.get("ELEVENLABS_VOICE_ID_NARRATOR", "").strip() or host_voice,
    }

    model_id = os.environ.get("ELEVENLABS_MODEL_ID", "eleven_v3").strip() or "eleven_v3"
    output_format = os.environ.get("ELEVENLABS_OUTPUT_FORMAT", "mp3_44100_128").strip() or "mp3_44100_128"
    content_type = content_type_for_tts_output(output_format)
    extension = extension_for_content_type(content_type)
    rendered_turns = split_audio_turns_for_tts(turns)
    if not rendered_turns:
        raise RuntimeError("no voice turns were available for ElevenLabs TTS")

    def build_inputs(active_voice_ids: Dict[str, str]) -> List[Dict[str, str]]:
        tts_inputs = []
        for turn in rendered_turns:
            voice_role = turn.get("voice_role") if turn.get("voice_role") in AI_AUDIO_VOICE_ROLES else "host"
            profile = AI_PODCAST_VOICE_BY_ID.get(str(turn.get("voice_id") or ""))
            env_key = f"ELEVENLABS_VOICE_ID_{re.sub(r'[^A-Z0-9]+', '_', (profile or {}).get('id', '').upper()).strip('_')}" if profile else ""
            selected_voice_id = os.environ.get(env_key, "").strip() if env_key else ""
            tts_inputs.append({"text": turn["text"], "voice_id": selected_voice_id or active_voice_ids[voice_role]})
        return tts_inputs

    body_template = {"model_id": model_id}
    language_code = os.environ.get("ELEVENLABS_LANGUAGE_CODE", "").strip()
    if language_code:
        body_template["language_code"] = language_code

    request_timeout = parse_int_env("AI_AUDIO_TTS_TIMEOUT_SECONDS", 240)
    max_request_chars = max(1000, parse_int_env("ELEVENLABS_MAX_REQUEST_CHARS", 4500))

    def post_dialogue(tts_inputs: List[Dict[str, str]]):
        return requests.post(
            "https://api.elevenlabs.io/v1/text-to-dialogue",
            params={"output_format": output_format},
            headers={"xi-api-key": api_key, "Content-Type": "application/json", "Accept": content_type},
            json={**body_template, "inputs": tts_inputs},
            timeout=request_timeout,
        )

    inputs = build_inputs(voice_ids)
    input_chars = sum(len(item.get("text") or "") for item in inputs)
    if input_chars > max_request_chars:
        raise RuntimeError(f"ElevenLabs TTS input has {input_chars} characters, above the configured {max_request_chars}-character cap")

    response = post_dialogue(inputs)
    if response.status_code == 404 and "voice_not_found" in response.text and len(set(voice_ids.values())) > 1:
        logger.warning("ElevenLabs secondary voice was not available; retrying dialogue render with host voice only")
        voice_ids = {role: voice_ids["host"] for role in voice_ids}
        inputs = build_inputs(voice_ids)
        response = post_dialogue(inputs)
    if response.status_code >= 400:
        raise RuntimeError(f"ElevenLabs TTS failed with {response.status_code}: {response.text[:300]}")

    data = response.content
    if len(data) < 1024:
        raise RuntimeError("ElevenLabs TTS produced an empty file")
    return {
        "data": data,
        "content_type": content_type,
        "provider": f"elevenlabs:{model_id}",
        "provider_kind": "elevenlabs",
        "model": model_id,
        "voices": {role: voice for role, voice in voice_ids.items() if voice},
        "turn_count": len(rendered_turns),
        "chunk_count": 1,
        "extension": extension,
        "filename": f"ai-generated-episode.{extension}",
    }


def render_openai_ai_audio(turns: List[Dict[str, str]]) -> Dict[str, Any]:
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")

    model = os.environ.get("OPENAI_TTS_MODEL", "gpt-4o-mini-tts").strip() or "gpt-4o-mini-tts"
    response_format = os.environ.get("OPENAI_TTS_RESPONSE_FORMAT", "mp3").strip() or "mp3"
    content_type = "audio/mpeg" if response_format == "mp3" else f"audio/{response_format}"
    gpt4o_voice_defaults = {"host": "marin", "guest": "cedar", "narrator": "coral"}
    legacy_voice_defaults = {"host": "alloy", "guest": "nova", "narrator": "onyx"}
    defaults = gpt4o_voice_defaults if model.startswith("gpt-4o") else legacy_voice_defaults
    voices = {
        "host": os.environ.get("OPENAI_TTS_VOICE_HOST", defaults["host"]).strip() or defaults["host"],
        "guest": os.environ.get("OPENAI_TTS_VOICE_GUEST", defaults["guest"]).strip() or defaults["guest"],
        "narrator": os.environ.get("OPENAI_TTS_VOICE_NARRATOR", defaults["narrator"]).strip() or defaults["narrator"],
    }
    base_instructions = os.environ.get(
        "OPENAI_TTS_INSTRUCTIONS",
        "Natural podcast delivery: warm, clear, conversational, and expressive without imitating any real person.",
    ).strip()

    segments = []
    actual_voices: Dict[str, Any] = {}
    rendered_turns = split_audio_turns_for_tts(turns)
    if not rendered_turns:
        raise RuntimeError("no voice turns were available for OpenAI TTS")
    for turn in rendered_turns:
        voice_role = turn.get("voice_role") if turn.get("voice_role") in AI_AUDIO_VOICE_ROLES else "host"
        voice_profile = AI_PODCAST_VOICE_BY_ID.get(str(turn.get("voice_id") or ""))
        selected_voice = (voice_profile.get("openai_voice") if voice_profile else "") or voices[voice_role]
        speaker_key = turn.get("speaker") or voice_role
        actual_voices[speaker_key] = {
            "voice_id": voice_profile.get("id") if voice_profile else "",
            "display_name": voice_profile.get("name") if voice_profile else selected_voice,
            "gender": voice_profile.get("gender") if voice_profile else "",
            "style": voice_profile.get("style") if voice_profile else "",
            "engine_voice": selected_voice,
        }
        payload = {
            "model": model,
            "voice": selected_voice,
            "input": turn["text"],
            "response_format": response_format,
        }
        if model.startswith("gpt-4o") and base_instructions:
            payload["instructions"] = f"{base_instructions} Speaker role: {turn.get('speaker') or voice_role}."
        response = requests.post(
            "https://api.openai.com/v1/audio/speech",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=parse_int_env("AI_AUDIO_TTS_TIMEOUT_SECONDS", 240),
        )
        if response.status_code >= 400:
            raise RuntimeError(f"OpenAI TTS failed with {response.status_code}: {response.text[:300]}")
        if len(response.content) < 1024:
            raise RuntimeError("OpenAI TTS produced an empty segment")
        segments.append(response.content)

    extension = "mp3" if response_format == "mp3" else response_format
    data = stitch_audio_segments(segments, extension=extension)
    return {
        "data": data,
        "content_type": content_type,
        "provider": f"openai:{model}",
        "provider_kind": "openai",
        "model": model,
        "voices": actual_voices or voices,
        "turn_count": len(rendered_turns),
        "extension": extension,
        "filename": f"ai-generated-episode.{extension}",
    }


def render_local_http_ai_audio(script_text: str, turns: List[Dict[str, str]]) -> Dict[str, Any]:
    base_url = os.environ.get("AI_AUDIO_LOCAL_TTS_URL", "").strip().rstrip("/")
    if not base_url:
        raise RuntimeError("AI_AUDIO_LOCAL_TTS_URL is not configured")

    payload = {
        "script_text": script_text,
        "turns": split_audio_turns_for_tts(turns),
        "target_loudness_lufs": parse_float_env("AI_AUDIO_TARGET_LUFS", -16.0),
        "format": os.environ.get("AI_AUDIO_LOCAL_TTS_FORMAT", "wav").strip().lower() or "wav",
        "quality_profile": os.environ.get("AI_AUDIO_LOCAL_TTS_PROFILE", "podcast-dialogue").strip() or "podcast-dialogue",
        "pacing": {
            "sentence_gap_seconds": ai_audio_sentence_gap_seconds(),
            "edge_padding_seconds": ai_audio_edge_padding_seconds(),
        },
    }
    response = requests.post(
        f"{base_url}/v1/render",
        json=payload,
        timeout=parse_int_env("AI_AUDIO_LOCAL_TTS_TIMEOUT_SECONDS", 900),
    )
    if response.status_code >= 400:
        raise RuntimeError(f"Local TTS worker failed with {response.status_code}: {response.text[:300]}")

    if (response.headers.get("Content-Type") or "").startswith("audio/"):
        data = response.content
        content_type = response.headers.get("Content-Type", "audio/wav").split(";")[0]
        extension = extension_for_content_type(content_type)
        provider = response.headers.get("X-Audioraq-TTS-Provider", "local-http:audio")
        provider_kind = response.headers.get("X-Audioraq-TTS-Provider-Kind", "local-neural")
        model = response.headers.get("X-Audioraq-TTS-Model", "")
    else:
        body = response.json()
        encoded_audio = body.get("audio_base64") or body.get("data_base64") or ""
        if not encoded_audio:
            raise RuntimeError("Local TTS worker did not return audio_base64")
        data = base64.b64decode(encoded_audio)
        content_type = body.get("content_type") or "audio/wav"
        extension = body.get("extension") or extension_for_content_type(content_type)
        provider = body.get("provider") or "local-http:audio"
        provider_kind = body.get("provider_kind") or "local-neural"
        model = body.get("model") or ""

    if len(data) < 1024:
        raise RuntimeError("Local TTS worker produced an empty audio file")
    if parse_bool_env("AI_AUDIO_REQUIRE_NEURAL_WORKER", False) and provider_kind != "local-neural":
        raise RuntimeError(f"Local TTS worker returned {provider_kind} audio, but AI_AUDIO_REQUIRE_NEURAL_WORKER=true")

    return {
        "data": data,
        "content_type": content_type,
        "provider": provider,
        "provider_kind": provider_kind,
        "model": model,
        "voices": {"source": "local-http-worker"},
        "turn_count": len(payload["turns"]),
        "extension": extension,
        "filename": f"ai-generated-episode.{extension}",
        "quality_profile": payload["quality_profile"],
    }


def render_ai_audio_bytes(script_text: str, turns: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
    voice_turns = cap_audio_script_turns(turns or [{"speaker": "Host", "voice_role": "host", "text": script_text}])
    provider_errors = []
    for provider in get_ai_audio_provider_order():
        try:
            if provider == "local_http":
                return render_local_http_ai_audio(script_text, voice_turns)
            if provider == "apple_say":
                return render_apple_say_proof_audio(script_text, voice_turns)
            if provider == "elevenlabs":
                return render_elevenlabs_ai_audio(voice_turns)
            if provider == "openai":
                return render_openai_ai_audio(voice_turns)
            if provider == "local":
                return render_local_ai_audio(script_text, voice_turns)
            raise RuntimeError(f"unknown provider '{provider}'")
        except Exception as exc:
            error = safe_tts_error(exc)
            provider_errors.append(f"{provider}: {error}")
            logger.warning(f"AI audio provider {provider} failed; trying fallback if available: {error}")

    raise HTTPException(
        status_code=502,
        detail=f"AI audio rendering failed across configured providers. Last errors: {'; '.join(provider_errors[-3:])}",
    )


def enforce_ai_audio_listenability_gate(quality_agent: Dict[str, Any], stored_paths: Optional[List[str]] = None) -> None:
    if not parse_bool_env("AI_AUDIO_ENFORCE_LISTENABILITY_GATE", True):
        return
    voice_review = (quality_agent or {}).get("podcast_voice") or {}
    min_score = parse_float_env("AI_AUDIO_MIN_LISTENABILITY_SCORE", 82.0)
    score = voice_review.get("listenability_score")
    status = voice_review.get("status")
    effective_min_score = min_score
    require_metrics = parse_bool_env("AI_AUDIO_REQUIRE_VOICE_METRICS", False)

    if score is None:
        if require_metrics:
            if stored_paths:
                cleanup_storage_paths(stored_paths, strict=False)
            raise HTTPException(
                status_code=422,
                detail="Agent 2 could not measure voice listenability. Install ffmpeg or disable AI_AUDIO_REQUIRE_VOICE_METRICS for development.",
            )
        return

    if status == "revise" or float(score) < effective_min_score:
        if stored_paths:
            cleanup_storage_paths(stored_paths, strict=False)
        actions = normalize_string_list(voice_review.get("improvement_actions"), limit=3)
        guidance = " ".join(actions) if actions else "Use a local neural TTS worker and re-render with a calmer podcast profile."
        raise HTTPException(
            status_code=422,
            detail=(
                f"Agent 2 blocked publishing because podcast voice listenability scored {score}/100 "
                f"below the required {effective_min_score}/100. {guidance}"
            ),
        )


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

    if format_name == "interview":
        audio_script_turns = [
            {
                "speaker": "Host",
                "voice_role": "host",
                "text": f"Welcome back to {podcast_name}. Today we are unpacking {topic} for {audience}. {hook}",
            }
        ]
        questions = [
            f"What do most people misunderstand about {topic}?",
            f"What changed your own thinking about {topic}?",
            f"What should listeners do next if they want a better result?",
        ]
        for index, question in enumerate(questions[:3]):
            answer = talking_points[index] if index < len(talking_points) else desired_outcome
            audio_script_turns.extend(
                [
                    {"speaker": "Host", "voice_role": "host", "text": question},
                    {
                        "speaker": "Guest",
                        "voice_role": "guest",
                        "text": f"The useful way to think about it is this: {answer}. For {audience}, the practical takeaway is to connect that idea back to {desired_outcome}.",
                    },
                ]
            )
        audio_script_turns.append(
            {
                "speaker": "Host",
                "voice_role": "host",
                "text": f"That is the roadmap for {topic}. Follow {podcast_name} on Audioraq for the next episode.",
            }
        )
    elif format_name == "narrative":
        audio_script_turns = [
            {"speaker": "Narrator", "voice_role": "narrator", "text": hook},
            {
                "speaker": "Host",
                "voice_role": "host",
                "text": f"This episode follows {topic} through the lens of {audience}, with one promise: {desired_outcome}.",
            },
        ]
        for point in talking_points[:4]:
            audio_script_turns.append({"speaker": "Narrator", "voice_role": "narrator", "text": point})
        audio_script_turns.append(
            {
                "speaker": "Host",
                "voice_role": "host",
                "text": f"Keep this takeaway close: {desired_outcome}.",
            }
        )
    else:
        audio_script_turns = [
            {
                "speaker": "Host",
                "voice_role": "host",
                "text": f"Welcome back to {podcast_name}. {hook}",
            },
            {
                "speaker": "Host",
                "voice_role": "host",
                "text": f"Today I am taking a {tone} look at {topic}, with a focus on helping {audience} {desired_outcome}.",
            },
        ]
        for point in talking_points[:5]:
            audio_script_turns.append({"speaker": "Host", "voice_role": "host", "text": point})
        audio_script_turns.append(
            {
                "speaker": "Host",
                "voice_role": "host",
                "text": f"If this was useful, follow {podcast_name} on Audioraq for the next episode.",
            }
        )

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
        "audio_script_turns": audio_script_turns,
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

    audio_script_turns = normalize_audio_script_turns(
        raw.get("audio_script_turns") or raw.get("audioScriptTurns") or raw.get("audio_script"),
        limit=48,
    )
    if audio_script_turns:
        generation["audio_script_turns"] = audio_script_turns

    recommended_category = str(raw.get("recommended_category") or "").strip().lower()
    if recommended_category:
        generation["recommended_category"] = recommended_category

    if not generation.get("suggested_description"):
        generation["suggested_description"] = build_ai_publish_description(generation)

    return enforce_voice_ready_generation_depth(generation, brief, show)


def enforce_voice_ready_generation_depth(generation: Dict[str, Any], brief: Dict[str, Any], show: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure AI drafts contain enough spoken evidence for high-quality audio review."""
    enriched = dict(generation or {})
    identity = brief.get("identity", {}) if isinstance(brief, dict) else {}
    content = brief.get("contentInput", {}) if isinstance(brief, dict) else {}
    tone_style = brief.get("toneStyle", {}) if isinstance(brief, dict) else {}
    topic = content.get("topic") or enriched.get("episode_title") or "today's topic"
    audience = identity.get("targetAudience") or "the listener"
    desired_outcome = (brief.get("episodeIntent", {}) if isinstance(brief, dict) else {}).get("desiredOutcome") or "leave with a useful next step"
    format_name = (tone_style.get("format") or "solo").strip().lower()
    turns = normalize_audio_script_turns(enriched.get("audio_script_turns"), limit=64)
    talking_points = normalize_string_list(enriched.get("talking_points"), limit=12)
    key_points = normalize_string_list(content.get("keyPoints"), limit=12)
    point_pool = talking_points + [point for point in key_points if point not in talking_points]
    if not point_pool:
        point_pool = [f"why {topic} matters", f"a practical framework for {topic}", desired_outcome]

    target_turns = 12 if format_name == "interview" else 10
    if format_name == "narrative":
        target_turns = 13

    def turn_text_exists(text: str) -> bool:
        normalized = re.sub(r"\s+", " ", text or "").strip().lower()
        return any(re.sub(r"\s+", " ", turn.get("text", "")).strip().lower() == normalized for turn in turns)

    attempts = 0
    while len(turns) < target_turns and attempts < target_turns * 3:
        attempts += 1
        point = point_pool[attempts % len(point_pool)]
        if format_name == "interview":
            host_text = (
                f"Let's make that specific. What is one concrete example of {topic} that {audience} can recognize this week?"
            )
            guest_text = (
                f"A useful case is this: {point}. The reason it matters is that it turns a broad idea into a decision, "
                f"a tradeoff, and one practical step instead of a slogan."
            )
            for candidate in [
                {"speaker": "Host", "voice_role": "host", "text": host_text},
                {"speaker": "Guest", "voice_role": "guest", "text": guest_text},
            ]:
                if len(turns) < target_turns and not turn_text_exists(candidate["text"]):
                    turns.append(candidate)
        elif format_name == "narrative":
            is_question_pivot = attempts % 4 == 0
            narrative_text = (
                f"What should the listener notice inside this example? {point}. Because the decision is visible, "
                f"the idea becomes easier to trust and easier to act on."
                if is_question_pivot
                else (
                    f"Here is the specific scene to hold onto: {point}. Because the listener can picture the decision, "
                    f"the idea becomes easier to trust and easier to act on."
                )
            )
            candidate = {
                "speaker": "Host" if is_question_pivot else "Narrator",
                "voice_role": "host" if is_question_pivot else "narrator",
                "text": narrative_text,
            }
            if not turn_text_exists(candidate["text"]):
                turns.append(candidate)
        else:
            candidate = {
                "speaker": "Host",
                "voice_role": "host",
                "text": (
                    f"Here is a concrete example: {point}. The framework is simple, name the situation, name the tradeoff, "
                    f"then choose one step that moves {audience} toward {desired_outcome}."
                ),
            }
            if not turn_text_exists(candidate["text"]):
                turns.append(candidate)
        if len(point_pool) == 1 and len(turns) >= target_turns:
            break

    question_turns = sum(1 for turn in turns if "?" in (turn.get("text") or ""))
    target_questions = 4 if format_name == "interview" else 3 if format_name == "narrative" else 2
    if question_turns < target_questions:
        enriched_turns = []
        question_templates = [
            "What is the decision hiding inside that example?",
            "Where do smart teams usually get this wrong?",
            "What is the smallest useful step a listener can take after hearing this?",
            "What tradeoff should they name before they act?",
        ]
        inserted = 0
        for index, turn in enumerate(turns):
            enriched_turns.append(turn)
            role = turn.get("voice_role") or "host"
            should_insert = role == "guest" if format_name == "interview" else (index + 1) % 3 == 0
            if should_insert and question_turns + inserted < target_questions:
                point = point_pool[(index + inserted) % len(point_pool)]
                enriched_turns.append(
                    {
                        "speaker": "Host",
                        "voice_role": "host",
                        "text": f"{question_templates[inserted % len(question_templates)]} In this case, how should they think about {point}?",
                    }
                )
                inserted += 1
        while question_turns + inserted < target_questions and len(enriched_turns) < 64:
            point = point_pool[inserted % len(point_pool)]
            enriched_turns.append(
                {
                    "speaker": "Host",
                    "voice_role": "host",
                    "text": f"{question_templates[inserted % len(question_templates)]} In this case, how should they think about {point}?",
                }
            )
            inserted += 1
        turns = enriched_turns[:64]

    enriched["audio_script_turns"] = normalize_audio_script_turns(turns, limit=64)
    production_notes = normalize_string_list(enriched.get("production_notes"), limit=12)
    production_notes.extend(
        [
            "Voice direction: prioritize warm chest-and-mouth resonance, not thin nasal brightness.",
            "Articulation direction: expand acronyms, leave micro-pauses around key terms, and keep consonants crisp without sounding theatrical.",
            "Performance direction: vary energy by meaning so the voice feels trustworthy over a long listen.",
        ]
    )
    enriched["production_notes"] = normalize_string_list(production_notes, limit=12)
    return enriched


async def generate_ai_podcast_package(brief: Dict[str, Any], show: Dict[str, Any]) -> Dict[str, Any]:
    fallback = build_fallback_ai_generation(brief, show)

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
        "audio_script_turns": [
            {
                "speaker": "Host | Guest | Narrator",
                "voice_role": "host | guest | narrator",
                "text": "voice-ready spoken text for this turn",
            }
        ],
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
        "- audio_script_turns should be ready for text-to-speech and sound like a polished podcast, not outline notes.\n"
        "- For interview or dialogue formats, alternate Host and Guest turns with distinct voices; for solo formats, use Host only unless a Narrator improves clarity.\n"
        "- For narrative formats, use Narrator for scene-setting and Host for reflective question pivots; include at least 12 spoken turns and 3 curiosity-led questions.\n"
        f"- Do not imitate or claim to be any real person's voice. Add no disclosure text unless it fits naturally; the platform stores this separately: {AI_AUDIO_DISCLOSURE}\n"
        "- Keep suggested keywords concise and usable for search/discovery.\n"
        "- recommended_category should be a single lowercase category.\n\n"
        f"Return JSON matching this schema exactly:\n{json.dumps(schema, ensure_ascii=True)}"
    )

    result = await run_ai_json_chat("ai-podcast", system_message, prompt, expected_type=dict)
    raw = result.get("raw")
    if not isinstance(raw, dict):
        if result.get("errors"):
            logger.warning(f"AI podcast generation used deterministic fallback after provider errors: {result['errors'][-2:]}")
        fallback = enforce_voice_ready_generation_depth(fallback, brief, show)
        fallback["ai_text_provider"] = AI_TEXT_PROVIDER_DETERMINISTIC
        return fallback

    generation = normalize_ai_generation_response(raw, brief, show)
    generation["ai_text_provider"] = result.get("provider", AI_TEXT_PROVIDER_DETERMINISTIC)
    return generation


def default_ai_studio_stage_state() -> Dict[str, Dict[str, Any]]:
    return {
        stage: {
            "label": AI_STUDIO_STAGE_LABELS[stage],
            "status": "pending",
            "notes": "",
            "updated_at": "",
        }
        for stage in AI_STUDIO_STAGES
    }


def update_ai_studio_stage_state(
    stage_state: Dict[str, Dict[str, Any]],
    stage: str,
    status: str,
    notes: str = "",
) -> Dict[str, Dict[str, Any]]:
    state = dict(stage_state or default_ai_studio_stage_state())
    current = dict(state.get(stage) or {})
    current["label"] = AI_STUDIO_STAGE_LABELS.get(stage, stage.replace("_", " ").title())
    current["status"] = status
    if notes:
        current["notes"] = notes
    current["updated_at"] = now_iso()
    state[stage] = current
    return state


def build_ai_studio_show_bible(show: Dict[str, Any], intake: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    intake = intake or {}
    identity = intake.get("identity", {})
    tone_style = intake.get("toneStyle", {})
    growth = intake.get("growthOptimization", {})
    audience = identity.get("targetAudience") or show.get("target_audience") or "curious listeners"
    niche = identity.get("niche") or show.get("category") or DEFAULT_SHOW_CATEGORY
    tone = tone_style.get("tone") or "professional"
    format_name = tone_style.get("format") or "solo"
    known_issues = normalize_string_list(growth.get("knownIssues"), limit=6)

    return {
        "show_id": show.get("id", ""),
        "show_title": show.get("title", ""),
        "show_description": show.get("description", ""),
        "niche": niche,
        "target_audience": audience,
        "positioning": f"{show.get('title') or 'This show'} helps {audience} understand {niche} with useful, podcast-first depth.",
        "tone_contract": f"Keep the delivery {tone}, built as a {format_name} episode, and avoid generic AI filler.",
        "creator_constraints": known_issues,
        "audio_policy": "AI-created episodes render as audio-only; recorded uploads can still be audio or audio plus video.",
    }


def build_ai_studio_claim_cards(generation: Dict[str, Any], intake: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    intake = intake or {}
    references = normalize_string_list((intake.get("contentInput") or {}).get("references"), limit=10)
    candidates = []
    if generation.get("hook"):
        candidates.append(generation["hook"])
    candidates.extend(normalize_string_list(generation.get("talking_points"), limit=12))
    for section in normalize_outline_items(generation.get("outline")):
        candidates.extend(normalize_string_list(section.get("beats"), limit=6))

    cards = []
    seen = set()
    for claim in candidates:
        normalized = claim.strip()
        if not normalized or normalized.lower() in seen:
            continue
        seen.add(normalized.lower())
        source = references[len(cards)] if len(cards) < len(references) else ""
        cards.append(
            {
                "id": f"claim-{len(cards) + 1}",
                "claim": normalized,
                "source": source,
                "confidence": "creator_reference" if source else "needs_creator_review",
                "needs_review": not bool(source),
                "review_note": "Supported by creator-provided reference." if source else "Review before recording if this is a factual claim.",
            }
        )
        if len(cards) >= 10:
            break
    return cards


def build_ai_studio_cast(intake: Optional[Dict[str, Any]], generation: Dict[str, Any]) -> List[Dict[str, Any]]:
    intake = intake or {}
    format_name = ((intake.get("toneStyle") or {}).get("format") or "solo").strip().lower()
    tone = ((intake.get("toneStyle") or {}).get("tone") or "professional").strip().lower()
    turns = normalize_audio_script_turns(generation.get("audio_script_turns"), limit=64)
    if not turns:
        turns = [{"speaker": "Host", "voice_role": "host", "text": ""}]
        if format_name == "interview":
            turns.append({"speaker": "Guest", "voice_role": "guest", "text": ""})
        if format_name == "narrative":
            turns.append({"speaker": "Narrator", "voice_role": "narrator", "text": ""})

    voiced_turns = apply_ai_voice_cast_to_turns(turns, intake)
    cast = []
    seen = set()
    for turn in voiced_turns:
        role = turn.get("voice_role") if turn.get("voice_role") in AI_AUDIO_VOICE_ROLES else "host"
        speaker = (turn.get("speaker") or role.title()).strip() or role.title()
        key = f"{speaker.lower()}:{role}"
        if key in seen:
            continue
        seen.add(key)
        cast.append(
            {
                "speaker": speaker,
                "voice_role": role,
                "voice_id": turn.get("voice_id", ""),
                "voice_name": turn.get("voice_name", ""),
                "voice_gender": turn.get("voice_gender", ""),
                "voice_style": turn.get("voice_style", ""),
                "delivery": f"{tone} podcast delivery; distinct from the other speakers and never imitating a real person.",
                "purpose": "Guide the listener" if role == "host" else "Add perspective" if role == "guest" else "Carry narrative transitions",
            }
        )
    return cast[:6]


def build_ai_studio_artifacts(
    intake: Optional[Dict[str, Any]],
    show: Dict[str, Any],
    generation: Optional[Dict[str, Any]] = None,
    agent2_review: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    generation = generation or {}
    title = generation.get("episode_title") or ((intake or {}).get("contentInput") or {}).get("topic") or "Untitled AI Episode"
    turns = build_ai_audio_turns(show, title, generation, intake or {}) if generation else []
    script_text = audio_turns_to_script(turns) if turns else ""
    claim_cards = build_ai_studio_claim_cards(generation, intake) if generation else []

    return {
        "brief": intake or {},
        "show_bible": build_ai_studio_show_bible(show, intake),
        "research": {
            "mode": "creator-guided-local-rag",
            "references": normalize_string_list(((intake or {}).get("contentInput") or {}).get("references"), limit=10),
            "claim_cards": claim_cards,
            "needs_creator_review_count": len([card for card in claim_cards if card.get("needs_review")]),
        },
        "outline": normalize_outline_items(generation.get("outline")) if generation else [],
        "script": {
            "title": title,
            "hook": generation.get("hook", ""),
            "intro_script": generation.get("intro_script", ""),
            "audio_script_turns": turns,
            "table_read_script": script_text,
            "estimated_words": len(script_text.split()),
        },
        "cast": build_ai_studio_cast(intake, generation) if generation else [],
        "quality": agent2_review or {},
        "publish": {
            "title": title,
            "description": (generation.get("suggested_description") or build_ai_publish_description(generation)) if generation else "",
            "category": generation.get("recommended_category") or show.get("category") or DEFAULT_SHOW_CATEGORY,
            "media_policy": "audio_only_ai_creation",
        },
    }


def build_ai_studio_stage_state(
    intake: Optional[Dict[str, Any]] = None,
    generation: Optional[Dict[str, Any]] = None,
    agent2_review: Optional[Dict[str, Any]] = None,
    published_episode_id: str = "",
) -> Dict[str, Dict[str, Any]]:
    state = default_ai_studio_stage_state()
    if intake:
        state = update_ai_studio_stage_state(state, "brief", "complete", "Structured creator brief captured.")
    if generation:
        state = update_ai_studio_stage_state(state, "research", "needs_review", "Claim cards are ready for creator review.")
        state = update_ai_studio_stage_state(state, "outline", "complete", "Episode outline generated.")
        state = update_ai_studio_stage_state(state, "script", "complete", "Dialogue-ready script turns generated.")
        state = update_ai_studio_stage_state(state, "cast", "complete", "Voice roles and speaker purposes assigned.")
        state = update_ai_studio_stage_state(state, "table_read", "ready", "Table-read script is ready to inspect.")
        state = update_ai_studio_stage_state(state, "final_render", "ready", "Ready to render an audio-only AI episode.")
    if agent2_review:
        review_status = agent2_review.get("status") or "pass"
        if review_status == "blocked":
            stage_status = "blocked"
        elif review_status == "revise":
            stage_status = "needs_revision"
        else:
            stage_status = "complete"
        state = update_ai_studio_stage_state(
            state,
            "agent2_review",
            stage_status,
            agent2_review.get("summary", "Agent 2 review complete."),
        )
        if review_status == "pass":
            state = update_ai_studio_stage_state(state, "publish", "ready", "Quality gate passed; ready for creator approval.")
        elif review_status == "revise":
            state = update_ai_studio_stage_state(state, "publish", "needs_revision", "Revise before publishing.")
        else:
            state = update_ai_studio_stage_state(state, "publish", "blocked", "Safety gate blocked publishing.")
    if published_episode_id:
        state = update_ai_studio_stage_state(state, "final_render", "complete", "Final audio rendered and stored.")
        state = update_ai_studio_stage_state(state, "publish", "published", f"Published episode {published_episode_id}.")
    return state


def resolve_ai_studio_active_stage(
    generation: Optional[Dict[str, Any]] = None,
    agent2_review: Optional[Dict[str, Any]] = None,
    published_episode_id: str = "",
) -> str:
    if published_episode_id:
        return "publish"
    if agent2_review and agent2_review.get("status") in {"blocked", "revise"}:
        return "agent2_review"
    if generation:
        return "final_render"
    return "brief"


def build_ai_studio_project_doc(
    user: Dict[str, Any],
    show: Dict[str, Any],
    intake: Optional[Dict[str, Any]] = None,
    generation: Optional[Dict[str, Any]] = None,
    agent2_review: Optional[Dict[str, Any]] = None,
    source_draft_id: str = "",
    title: str = "",
) -> Dict[str, Any]:
    created_at = now_iso()
    episode_title = (
        title
        or (generation or {}).get("episode_title")
        or ((intake or {}).get("contentInput") or {}).get("topic")
        or "Untitled AI Studio Project"
    )
    return {
        "id": str(uuid.uuid4()),
        "title": episode_title,
        "show_id": show["id"],
        "show_title": show.get("title", ""),
        "podcaster_id": user["_id"],
        "podcaster_name": user.get("name", ""),
        "source_draft_id": source_draft_id,
        "intake": intake or {},
        "generation": generation or {},
        "show_bible": build_ai_studio_show_bible(show, intake),
        "artifacts": build_ai_studio_artifacts(intake, show, generation, agent2_review),
        "agent2_review": agent2_review or {},
        "stage_state": build_ai_studio_stage_state(intake, generation, agent2_review),
        "active_stage": resolve_ai_studio_active_stage(generation, agent2_review),
        "status": "draft",
        "media_policy": {
            "create_with_ai": "audio_only",
            "recorded_upload": "audio_or_video",
        },
        "created_at": created_at,
        "updated_at": created_at,
        "published_episode_id": "",
        "is_deleted": False,
    }


async def extract_keywords(text):
    result = await run_ai_json_chat(
        "keywords",
        'You are a keyword extraction expert. Extract 5-10 relevant keywords/topics from the given text. Return ONLY a JSON array of lowercase strings, no other text. Example: ["technology", "science", "ai"]',
        f"Extract keywords from this text: {text}",
        expected_type=list,
    )
    keywords = result.get("raw")
    if isinstance(keywords, list):
        cleaned_keywords = [k.lower().strip() for k in keywords if isinstance(k, str) and k.strip()]
        if cleaned_keywords:
            return cleaned_keywords[:10]

    if result.get("errors"):
        logger.warning(f"Keyword extraction used deterministic fallback after provider errors: {result['errors'][-2:]}")
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

    prompt = f"""User interests: {json.dumps(user_interests)}
Previously viewed podcast keywords: {json.dumps(viewed_keywords)}
Available podcasts: {json.dumps(podcast_summaries)}

Return the most relevant podcast IDs as a JSON array."""
    result = await run_ai_json_chat(
        "recommend",
        "You are a podcast recommendation engine. Given user interests and available podcasts, rank and return the most relevant podcast IDs. Return ONLY a JSON array of podcast ID strings, ordered by relevance. Max 20 IDs.",
        prompt,
        expected_type=list,
    )
    ids = result.get("raw")
    if isinstance(ids, list):
        return [str(i) for i in ids]
    if result.get("errors"):
        logger.warning(f"AI recommendation skipped after provider errors: {result['errors'][-2:]}")
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


def clip_text(value: Any, limit: int = 220) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(text) <= limit:
        return text
    trimmed = text[: max(0, limit - 1)].rsplit(" ", 1)[0].strip()
    return f"{trimmed or text[:limit].strip()}…"


def first_meaningful_sentence(value: Any, limit: int = 220) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if not text:
        return ""
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        cleaned = sentence.strip()
        if cleaned:
            return clip_text(cleaned, limit=limit)
    return clip_text(text, limit=limit)


def infer_episode_difficulty(episode: Dict[str, Any], show: Optional[Dict[str, Any]] = None) -> str:
    combined = " ".join(
        [
            str(episode.get("title") or ""),
            str(episode.get("description") or ""),
            str((show or {}).get("description") or ""),
            " ".join(episode.get("keywords") or []),
        ]
    ).lower()
    category = normalize_topic_name(episode.get("category") or (show or {}).get("category"))
    if any(term in combined for term in ["beginner", "intro", "basics", "plain english", "explained simply", "starter"]):
        return "Beginner-friendly"
    if any(term in combined for term in ["deep dive", "advanced", "regulatory", "litigation", "macro", "technical breakdown", "astrophysics"]):
        return "Deep dive"
    if category in {"law", "finance", "emerging markets", "astrophysics", "current affairs"}:
        return "Intermediate"
    return "Easy to follow"


def infer_episode_tone(episode: Dict[str, Any], show: Optional[Dict[str, Any]] = None) -> str:
    combined = " ".join(
        [
            str(episode.get("title") or ""),
            str(episode.get("description") or ""),
            str((show or {}).get("description") or ""),
        ]
    ).lower()
    category = normalize_topic_name(episode.get("category") or (show or {}).get("category"))
    if any(term in combined for term in ["story", "storytelling", "behind the scenes", "journey"]):
        return "Story-led"
    if category in {"mental health", "physical health"}:
        return "Calm and supportive"
    if category in {"law", "finance", "business", "current affairs", "science", "astrophysics"}:
        return "Clear and analytical"
    if category in {"entertainment", "music", "comedy", "sports"}:
        return "Lively and conversational"
    return "Warm and informative"


def infer_listen_mode(episode: Dict[str, Any], show: Optional[Dict[str, Any]] = None) -> str:
    category = normalize_topic_name(episode.get("category") or (show or {}).get("category"))
    title = str(episode.get("title") or "").lower()
    description = str(episode.get("description") or "").lower()
    if episode.get("progress_percent") and not episode.get("is_completed"):
        return "Easy to resume in short bursts"
    if category == "current affairs":
        return "Good for a fast catch-up"
    if any(term in f"{title} {description}" for term in ["story", "narrative", "interview"]):
        return "Best when you can listen straight through"
    if category in {"mental health", "physical health"}:
        return "Works well as a calm, focused listen"
    return "Good for a focused listen"


def build_episode_assistant_prompts(episode: Dict[str, Any]) -> List[str]:
    title = clip_text(episode.get("title") or "this episode", limit=60)
    category = normalize_topic_name(episode.get("category") or "").title() or "this topic"
    return [
        "What will I get out of this episode?",
        "Who is this best for?",
        f"What should I listen for in {title}?",
        f"What is the main idea behind this {category} episode?",
    ]


def build_listener_brief_fallback(episode: Dict[str, Any], show: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    category = normalize_topic_name(episode.get("category") or (show or {}).get("category")) or DEFAULT_SHOW_CATEGORY
    description_sentence = (
        first_meaningful_sentence(episode.get("description"))
        or first_meaningful_sentence((show or {}).get("description"))
        or f"A focused {category} episode from Audioraq."
    )
    recommendation_reason = first_meaningful_sentence(episode.get("recommendation_reason"), limit=120)
    keywords = normalize_string_list(episode.get("keywords"), limit=4)
    keyword_phrase = ", ".join(keywords[:2]) if keywords else category
    why_now = description_sentence
    if recommendation_reason:
        why_now = clip_text(f"{recommendation_reason}. {description_sentence}", limit=220)
    best_for = f"Listeners who want a clearer take on {keyword_phrase} without digging through a full catalog first."
    takeaway = clip_text(
        first_meaningful_sentence(episode.get("description"), limit=200)
        or f"You should leave with a stronger handle on {keyword_phrase}.",
        limit=200,
    )
    suggested_next = (
        f"Open {show.get('title')} for more episodes in this lane."
        if show and show.get("episode_count", 0) > 1
        else f"Queue another {category} episode if you want to keep the thread going."
    )
    return {
        "why_now": why_now,
        "best_for": clip_text(best_for, limit=180),
        "takeaway": takeaway,
        "difficulty": infer_episode_difficulty(episode, show),
        "tone": infer_episode_tone(episode, show),
        "listen_mode": infer_listen_mode(episode, show),
        "suggested_next": clip_text(suggested_next, limit=180),
        "grounding": "metadata",
        "generated_at": now_iso(),
        "provider": AI_TEXT_PROVIDER_DETERMINISTIC,
    }


def normalize_listener_brief(raw: Any, fallback: Dict[str, Any]) -> Dict[str, Any]:
    raw = raw if isinstance(raw, dict) else {}
    brief = {
        "why_now": clip_text(raw.get("why_now") or fallback.get("why_now"), limit=220),
        "best_for": clip_text(raw.get("best_for") or fallback.get("best_for"), limit=180),
        "takeaway": clip_text(raw.get("takeaway") or fallback.get("takeaway"), limit=200),
        "difficulty": clip_text(raw.get("difficulty") or fallback.get("difficulty"), limit=40),
        "tone": clip_text(raw.get("tone") or fallback.get("tone"), limit=50),
        "listen_mode": clip_text(raw.get("listen_mode") or fallback.get("listen_mode"), limit=60),
        "suggested_next": clip_text(raw.get("suggested_next") or fallback.get("suggested_next"), limit=180),
        "grounding": clip_text(raw.get("grounding") or fallback.get("grounding") or "metadata", limit=80),
        "generated_at": raw.get("generated_at") or fallback.get("generated_at") or now_iso(),
        "provider": raw.get("provider") or fallback.get("provider") or AI_TEXT_PROVIDER_DETERMINISTIC,
    }
    return brief


def listener_brief_needs_refresh(cached: Any, episode: Dict[str, Any]) -> bool:
    if not isinstance(cached, dict):
        return True
    required_fields = ["why_now", "best_for", "takeaway", "difficulty", "tone", "listen_mode", "suggested_next"]
    if any(not str(cached.get(field) or "").strip() for field in required_fields):
        return True
    brief_time = parse_iso_datetime(cached.get("generated_at"))
    episode_time = parse_iso_datetime(episode.get("updated_at") or episode.get("created_at"))
    if brief_time is None:
        return True
    if episode_time is not None and episode_time > brief_time:
        return True
    return False


def extract_episode_grounding_excerpt(episode: Dict[str, Any], show: Optional[Dict[str, Any]] = None, limit: int = 1600) -> str:
    chunks = [
        str(episode.get("description") or "").strip(),
        str(episode.get("ai_audio_script") or "").strip(),
        str((episode.get("moderation") or {}).get("media_transcript_excerpt") or "").strip(),
        str((show or {}).get("description") or "").strip(),
    ]
    combined = "\n\n".join(chunk for chunk in chunks if chunk)
    return clip_text(combined, limit=limit)


async def ensure_listener_brief_cache(episode: Dict[str, Any], show: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    fallback = build_listener_brief_fallback(episode, show)
    cached = clean_doc(episode.get("listener_brief_cache")) if isinstance(episode.get("listener_brief_cache"), dict) else None
    if cached and not listener_brief_needs_refresh(cached, episode):
        return normalize_listener_brief(cached, fallback)

    context = {
        "episode_title": episode.get("title", ""),
        "episode_description": episode.get("description", ""),
        "show_title": (show or {}).get("title", episode.get("show_title", "")),
        "show_description": (show or {}).get("description", ""),
        "category": episode.get("category", ""),
        "keywords": normalize_string_list(episode.get("keywords"), limit=8),
        "recommendation_reason": episode.get("recommendation_reason", ""),
        "grounding_excerpt": extract_episode_grounding_excerpt(episode, show, limit=1200),
    }
    prompt = f"""Build a concise AI listener brief for this podcast episode.

Context: {json.dumps(context, ensure_ascii=False)}

Return JSON with exactly these keys:
- why_now
- best_for
- takeaway
- difficulty
- tone
- listen_mode
- suggested_next
- grounding

Rules:
- Stay grounded in the supplied context only.
- Keep each field concise and practical.
- Make the brief useful before playback, not marketing fluff.
"""
    result = await run_ai_json_chat(
        "listener_brief",
        "You create concise, trustworthy listener briefs for podcast episodes. Return only JSON and never invent details not present in the supplied context.",
        prompt,
        expected_type=dict,
    )
    brief = normalize_listener_brief(result.get("raw"), fallback)
    brief["provider"] = result.get("provider") or brief.get("provider") or AI_TEXT_PROVIDER_DETERMINISTIC
    if context["grounding_excerpt"]:
        brief["grounding"] = "metadata plus episode excerpt"
    await db.podcasts.update_one(
        {"id": episode["id"]},
        {"$set": {"listener_brief_cache": brief, "listener_brief_generated_at": brief["generated_at"]}},
    )
    return brief


def build_episode_assistant_fallback(
    question: str,
    episode: Dict[str, Any],
    show: Optional[Dict[str, Any]],
    listener_brief: Dict[str, Any],
) -> Dict[str, Any]:
    question_lower = question.lower()
    if "who" in question_lower and "for" in question_lower:
        answer = listener_brief.get("best_for")
    elif any(term in question_lower for term in ["takeaway", "learn", "get out of", "main idea", "main takeaway"]):
        answer = listener_brief.get("takeaway")
    elif "why" in question_lower and "listen" in question_lower:
        answer = listener_brief.get("why_now")
    elif any(term in question_lower for term in ["tone", "vibe", "feel"]):
        answer = f"Expect a {listener_brief.get('tone', 'clear')} episode. {listener_brief.get('listen_mode', '')}".strip()
    elif any(term in question_lower for term in ["safe", "harmful", "age", "mature"]):
        audience_rating = normalize_content_rating(episode.get("audience_rating"))
        moderation_status = episode.get("moderation_status") or "clear"
        if audience_rating == MATURE_RATING:
            answer = "This episode is marked 18+ on Audioraq."
        else:
            answer = f"This episode is currently marked for all ages, with moderation status set to {moderation_status}."
    else:
        answer = (
            first_meaningful_sentence(episode.get("description"), limit=260)
            or first_meaningful_sentence((show or {}).get("description"), limit=260)
            or listener_brief.get("takeaway")
        )
    return {
        "answer": clip_text(answer, limit=320),
        "confidence": "medium",
        "grounding": "metadata and available episode excerpt",
        "follow_up_questions": build_episode_assistant_prompts(episode)[:3],
        "provider": AI_TEXT_PROVIDER_DETERMINISTIC,
    }


def normalize_episode_assistant_reply(raw: Any, fallback: Dict[str, Any], episode: Dict[str, Any]) -> Dict[str, Any]:
    raw = raw if isinstance(raw, dict) else {}
    follow_ups = raw.get("follow_up_questions")
    if not isinstance(follow_ups, list):
        follow_ups = fallback.get("follow_up_questions") or build_episode_assistant_prompts(episode)[:3]
    normalized = {
        "answer": clip_text(raw.get("answer") or fallback.get("answer"), limit=360),
        "confidence": clip_text(raw.get("confidence") or fallback.get("confidence") or "medium", limit=24).lower(),
        "grounding": clip_text(raw.get("grounding") or fallback.get("grounding") or "metadata", limit=90),
        "follow_up_questions": normalize_string_list(follow_ups, limit=4) or build_episode_assistant_prompts(episode)[:3],
        "provider": raw.get("provider") or fallback.get("provider") or AI_TEXT_PROVIDER_DETERMINISTIC,
    }
    return normalized


async def answer_episode_question(question: str, episode: Dict[str, Any], show: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    listener_brief = await ensure_listener_brief_cache(episode, show)
    fallback = build_episode_assistant_fallback(question, episode, show, listener_brief)
    context = {
        "episode_title": episode.get("title", ""),
        "episode_description": episode.get("description", ""),
        "show_title": (show or {}).get("title", episode.get("show_title", "")),
        "show_description": (show or {}).get("description", ""),
        "category": episode.get("category", ""),
        "keywords": normalize_string_list(episode.get("keywords"), limit=8),
        "listener_brief": listener_brief,
        "quality_summary": (episode.get("quality_agent") or {}).get("summary", ""),
        "moderation_summary": (episode.get("moderation") or {}).get("summary", ""),
        "grounding_excerpt": extract_episode_grounding_excerpt(episode, show, limit=1800),
        "question": question,
    }
    prompt = f"""Answer a listener question about a podcast episode using only the supplied episode context.

Context: {json.dumps(context, ensure_ascii=False)}

Return JSON with exactly these keys:
- answer
- confidence
- grounding
- follow_up_questions

Rules:
- If the context is thin, say that plainly instead of guessing.
- Keep the answer concise, useful, and listener-facing.
- follow_up_questions should be 2 to 4 short, natural follow-ups.
"""
    result = await run_ai_json_chat(
        "episode_listener_assistant",
        "You are a grounded podcast listening assistant. Answer only from the supplied episode metadata and excerpts. If information is missing, say so clearly. Return only JSON.",
        prompt,
        expected_type=dict,
    )
    return normalize_episode_assistant_reply(result.get("raw"), fallback, episode)


def normalize_topic_name(value: Optional[str]) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def topic_filter_terms(topic: Optional[str]) -> List[str]:
    normalized = normalize_topic_name(topic)
    if not normalized:
        return []
    terms = TOPIC_FILTER_TERMS.get(normalized, [])
    return list(dict.fromkeys([normalized, *terms]))


def topic_match_clause(topic: Optional[str]) -> Optional[Dict[str, Any]]:
    terms = topic_filter_terms(topic)
    if not terms:
        return None
    regex_terms = [re.escape(term) for term in terms if len(term) > 2]
    text_regex = "|".join(regex_terms[:12])
    clause: Dict[str, Any] = {
        "$or": [
            {"category": {"$in": terms}},
            {"keywords": {"$in": terms}},
        ]
    }
    if text_regex:
        clause["$or"].extend(
            [
                {"title": {"$regex": text_regex, "$options": "i"}},
                {"description": {"$regex": text_regex, "$options": "i"}},
                {"show_title": {"$regex": text_regex, "$options": "i"}},
            ]
        )
    return clause


def add_query_clause(query: Dict[str, Any], clause: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not clause:
        return query
    if not query:
        return clause
    return {"$and": [query, clause]}


def xml_escape(value: Any) -> str:
    return (
        str(value or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def wrap_thumbnail_text(value: Any, max_chars: int = 28, max_lines: int = 3) -> List[str]:
    words = re.findall(r"[A-Za-z0-9+&'-]+", str(value or ""))
    lines: List[str] = []
    current = ""
    for word in words:
        next_line = f"{current} {word}".strip()
        if current and len(next_line) > max_chars:
            lines.append(current)
            current = word
        else:
            current = next_line
        if len(lines) >= max_lines:
            break
    if current and len(lines) < max_lines:
        lines.append(current)
    return lines or ["Audioraq", "Originals"]


def thumbnail_palette(category: Optional[str]) -> Tuple[str, str, str]:
    normalized = normalize_topic_name(category)
    palettes = {
        "finance": ("#0E3B2E", "#D8A63A", "#F7F1E8"),
        "law": ("#182033", "#BFA46A", "#F7F1E8"),
        "environment": ("#12382A", "#69C08E", "#F4F9F0"),
        "emerging markets": ("#2A1E4A", "#FFB86B", "#F7F1E8"),
        "technology": ("#0E2338", "#45C4F9", "#EEF8FF"),
        "upcoming technologies": ("#181C3A", "#B086F5", "#F4F0FF"),
        "current affairs": ("#2D1B1B", "#F97316", "#FFF7ED"),
        "astrophysics": ("#0B1026", "#8EA7FF", "#F2F5FF"),
        "physical health": ("#173126", "#5EEAD4", "#ECFEFF"),
        "mental health": ("#2B2442", "#C4B5FD", "#F5F3FF"),
        "business": ("#1F2937", "#F5A623", "#F7F1E8"),
        "science": ("#102A43", "#38BDF8", "#F0F9FF"),
        "education": ("#243B2F", "#FACC15", "#FEFCE8"),
        "entertainment": ("#3A162E", "#F472B6", "#FDF2F8"),
    }
    return palettes.get(normalized, ("#0E1117", "#F5A623", "#F7F1E8"))


def build_generated_thumbnail_svg(title: str, subtitle: str = "", category: str = DEFAULT_SHOW_CATEGORY, kind: str = "episode") -> bytes:
    background, accent, foreground = thumbnail_palette(category)
    title_lines = wrap_thumbnail_text(title, max_chars=26, max_lines=3)
    subtitle_text = (subtitle or category or APP_NAME).strip()
    eyebrow = "AUDIORAQ ORIGINALS" if "audioraq originals" in f"{title} {subtitle}".lower() else f"AUDIORAQ {kind.upper()}"

    title_nodes = []
    y = 238
    for line in title_lines:
        title_nodes.append(
            f'<text x="80" y="{y}" font-family="Outfit, Arial, sans-serif" font-size="58" font-weight="800" fill="{foreground}">{xml_escape(line)}</text>'
        )
        y += 66

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720" role="img" aria-label="{xml_escape(title)} thumbnail">
  <defs>
    <radialGradient id="glow" cx="78%" cy="20%" r="58%">
      <stop offset="0%" stop-color="{accent}" stop-opacity="0.42"/>
      <stop offset="55%" stop-color="{accent}" stop-opacity="0.10"/>
      <stop offset="100%" stop-color="{background}" stop-opacity="0"/>
    </radialGradient>
    <linearGradient id="wave" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="{accent}" stop-opacity="0.20"/>
      <stop offset="50%" stop-color="{accent}" stop-opacity="0.95"/>
      <stop offset="100%" stop-color="{accent}" stop-opacity="0.20"/>
    </linearGradient>
  </defs>
  <rect width="1280" height="720" fill="{background}"/>
  <rect width="1280" height="720" fill="url(#glow)"/>
  <circle cx="1080" cy="130" r="210" fill="{accent}" opacity="0.12"/>
  <circle cx="1120" cy="610" r="260" fill="{accent}" opacity="0.08"/>
  <path d="M80 548 C210 500 330 596 460 548 S710 500 840 548 1085 596 1200 548" fill="none" stroke="url(#wave)" stroke-width="12" stroke-linecap="round"/>
  <path d="M80 586 C210 538 330 634 460 586 S710 538 840 586 1085 634 1200 586" fill="none" stroke="{foreground}" stroke-opacity="0.18" stroke-width="6" stroke-linecap="round"/>
  <rect x="70" y="70" width="1140" height="580" rx="44" fill="none" stroke="{foreground}" stroke-opacity="0.16" stroke-width="2"/>
  <text x="80" y="132" font-family="Outfit, Arial, sans-serif" font-size="24" font-weight="800" letter-spacing="5" fill="{accent}">{xml_escape(eyebrow)}</text>
  {''.join(title_nodes)}
  <text x="80" y="492" font-family="Outfit, Arial, sans-serif" font-size="28" font-weight="600" fill="{foreground}" opacity="0.72">{xml_escape(subtitle_text[:70])}</text>
  <g transform="translate(1040 430)">
    <rect x="0" y="0" width="120" height="120" rx="30" fill="{accent}" opacity="0.94"/>
    <path d="M39 30 v60 M60 18 v84 M81 35 v50" stroke="{background}" stroke-width="12" stroke-linecap="round"/>
  </g>
</svg>'''
    return svg.encode("utf-8")


def generated_thumbnail_response(title: str, subtitle: str = "", category: str = DEFAULT_SHOW_CATEGORY, kind: str = "episode") -> Response:
    return Response(
        content=build_generated_thumbnail_svg(title, subtitle, category, kind),
        media_type="image/svg+xml",
        headers={"Cache-Control": "public, max-age=86400"},
    )


def store_generated_thumbnail(path_prefix: str, title: str, subtitle: str = "", category: str = DEFAULT_SHOW_CATEGORY, kind: str = "episode") -> str:
    object_path = f"{APP_NAME}/{path_prefix}/{uuid.uuid4()}.svg"
    put_object(object_path, build_generated_thumbnail_svg(title, subtitle, category, kind), "image/svg+xml")
    return object_path


def is_audioraq_original_package(show: Optional[Dict[str, Any]], title: str = "", episode: Optional[Dict[str, Any]] = None) -> bool:
    combined = " ".join(
        [
            str(title or ""),
            str((episode or {}).get("title") or ""),
            str((episode or {}).get("show_title") or ""),
            str((episode or {}).get("podcaster_name") or ""),
            str((show or {}).get("title") or ""),
            str((show or {}).get("podcaster_name") or ""),
        ]
    ).lower()
    return "audioraq originals" in combined


def enforce_audioraq_originals_quality_gate(
    show: Optional[Dict[str, Any]],
    title: str,
    quality_agent: Dict[str, Any],
    stored_paths: Optional[List[str]] = None,
) -> None:
    if not is_audioraq_original_package(show, title):
        return
    score = float((quality_agent or {}).get("quality_score", 0) or 0)
    status = (quality_agent or {}).get("status", "")
    if status == "blocked" or score < AUDIORAQ_ORIGINALS_MIN_QUALITY_SCORE:
        if stored_paths:
            cleanup_storage_paths(stored_paths, strict=False)
        raise HTTPException(
            status_code=422,
            detail=(
                "Audioraq Originals must pass the Agent 2 quality gate before publishing. "
                f"Current score: {score}/100; required: {AUDIORAQ_ORIGINALS_MIN_QUALITY_SCORE}/100."
            ),
        )


async def store_upload(upload: UploadFile, path_prefix: str, default_content_type: str):
    ext = validate_thumbnail_metadata(upload)
    object_path = f"{APP_NAME}/{path_prefix}/{uuid.uuid4()}.{ext}"
    data = await read_upload_limited(upload, max_thumbnail_bytes())
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
    if is_audioraq_original_package(show, episode.get("title", ""), episode):
        signals.append("Audioraq Originals")
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
        cleaned["voice_clarity"] = cleaned["quality_agent"].get("voice_clarity") or cleaned["moderation"].get("voice_clarity", {})
        cleaned["voice_clarity_status"] = cleaned["voice_clarity"].get("status", "")
        cleaned["voice_clarity_score"] = cleaned["voice_clarity"].get("score", 0)
        cleaned["is_playable"] = bool(cleaned.get("is_playable", bool(cleaned.get("media_path") or cleaned.get("external_media_url"))))
        cleaned["like_count"] = int(engagement.get("like_count", cleaned.get("like_count", 0)) or 0)
        cleaned["rating_count"] = int(engagement.get("rating_count", cleaned.get("rating_count", 0)) or 0)
        cleaned["rating_average"] = round(float(engagement.get("rating_average", cleaned.get("rating_average", 0)) or 0), 1)
        cleaned["view_count"] = int(cleaned.get("play_count", 0) or 0)
        cleaned["is_age_restricted"] = cleaned["audience_rating"] == MATURE_RATING
        cleaned["requires_signup_for_playback"] = current_user is None and cleaned["is_playable"]
        cleaned["viewer_can_stream"] = bool(current_user) and can_access_episode(current_user, cleaned) and cleaned["is_playable"]
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
        cleaned["listener_brief"] = normalize_listener_brief(cleaned.get("listener_brief_cache"), build_listener_brief_fallback(cleaned, show))
        cleaned["assistant_prompts"] = build_episode_assistant_prompts(cleaned)
        if current_user is None:
            cleaned["listener_brief_teaser"] = {
                "why_now": cleaned["listener_brief"].get("why_now", ""),
                "unlock_message": "Sign up to see the full AI listener brief, ask this episode questions, and build a personal queue.",
            }
            cleaned["listener_brief"] = None
            cleaned["assistant_prompts"] = []
            cleaned["media_transcript_excerpt"] = ""
            cleaned.pop("media_path", None)
            cleaned.pop("external_media_url", None)
            if isinstance(cleaned.get("moderation"), dict):
                cleaned["moderation"].pop("media_transcript_excerpt", None)
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
    metric_rows = []
    if episode_ids:
        saved_rows = await db.saved_podcasts.aggregate(
            [
                {"$match": {"podcast_id": {"$in": episode_ids}}},
                {"$group": {"_id": "$podcast_id", "saved_count": {"$sum": 1}}},
            ]
        ).to_list(len(episode_ids))
        progress_rows = await db.playback_progress.find({"podcast_id": {"$in": episode_ids}}).to_list(MAX_LIBRARY_ITEMS)
        metric_since = (datetime.now(timezone.utc).date() - timedelta(days=30)).isoformat()
        metric_rows = await db.daily_episode_metrics.find(
            {"episode_id": {"$in": episode_ids}, "bucket_date": {"$gte": metric_since}}
        ).to_list(max(len(episode_ids) * 31, 100))

    saved_map = {row["_id"]: row.get("saved_count", 0) for row in saved_rows}
    metric_map: Dict[str, Dict[str, int]] = {}
    for row in metric_rows:
        episode_counts = metric_map.setdefault(row.get("episode_id", ""), {})
        for key, value in (row.get("counts") or {}).items():
            episode_counts[key] = episode_counts.get(key, 0) + int(value or 0)
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
                "last_30d_plays": metric_map.get(episode["id"], {}).get("play_started", 0),
                "last_30d_saves": metric_map.get(episode["id"], {}).get("save", 0),
                "last_30d_likes": metric_map.get(episode["id"], {}).get("like", 0),
                "last_30d_ratings": metric_map.get(episode["id"], {}).get("rating", 0),
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
            "analytics_storage_mode": "mongo_event_log_plus_daily_rollups",
        },
        "shows": show_analytics,
        "episodes": episode_analytics[:12],
        "listener_interests": listener_interest_list,
    }


SHOW_STRATEGY_PLAYBOOK = {
    "finance": [
        {"title": "The framework behind smarter money decisions", "angle": "Turn one fuzzy finance habit into a repeatable decision framework.", "format": "solo", "optimize_for": "clarity"},
        {"title": "What people miss about market headlines", "angle": "Decode a noisy finance headline into signal, risk, and real-world implications.", "format": "narrative", "optimize_for": "retention"},
        {"title": "A founder's guide to financial tradeoffs", "angle": "Translate finance concepts into operator decisions listeners can actually use.", "format": "interview", "optimize_for": "clarity"},
    ],
    "law": [
        {"title": "The law behind the headline", "angle": "Break one legal issue into stakes, precedents, and what non-lawyers should understand.", "format": "solo", "optimize_for": "clarity"},
        {"title": "Where legal risk quietly shows up", "angle": "Explain hidden legal risk in business or everyday decisions without jargon overload.", "format": "narrative", "optimize_for": "retention"},
        {"title": "Ask a lawyer, but make it usable", "angle": "Use question-and-answer structure so the episode feels practical, not academic.", "format": "interview", "optimize_for": "clarity"},
    ],
    "environment": [
        {"title": "The climate story behind the data", "angle": "Make one environmental topic feel concrete, local, and actionable.", "format": "narrative", "optimize_for": "retention"},
        {"title": "Where sustainability gets misunderstood", "angle": "Challenge a shallow narrative with a more nuanced, useful explanation.", "format": "solo", "optimize_for": "clarity"},
        {"title": "What changes if this trend keeps growing", "angle": "Project a current environmental trend forward and explore realistic outcomes.", "format": "interview", "optimize_for": "retention"},
    ],
    "emerging markets": [
        {"title": "The opportunity beneath the noise", "angle": "Translate broad emerging-market narratives into specific listener insight.", "format": "solo", "optimize_for": "clarity"},
        {"title": "What the next growth map could look like", "angle": "Use one country, sector, or policy shift to anchor a bigger trend story.", "format": "narrative", "optimize_for": "retention"},
        {"title": "How operators read emerging-market signals", "angle": "Frame the episode around practical decision-making instead of abstract geopolitics.", "format": "interview", "optimize_for": "clarity"},
    ],
    "upcoming technologies": [
        {"title": "The real use case behind the hype", "angle": "Separate what is shipping now from what is still speculative.", "format": "solo", "optimize_for": "clarity"},
        {"title": "What this new tech changes downstream", "angle": "Trace one technology into jobs, products, or behavior shifts listeners can picture.", "format": "narrative", "optimize_for": "retention"},
        {"title": "The next adoption wave explained", "angle": "Give listeners a credible way to track whether a technology is actually maturing.", "format": "interview", "optimize_for": "clarity"},
    ],
    "current affairs": [
        {"title": "The fast brief behind the story", "angle": "Turn a current event into a calm, structured update with stakes and context.", "format": "solo", "optimize_for": "clarity"},
        {"title": "What everyone is arguing about, actually explained", "angle": "Map the competing viewpoints so listeners can follow the issue without doomscrolling.", "format": "narrative", "optimize_for": "retention"},
        {"title": "The second-order effects worth watching", "angle": "Go beyond the headline into what might happen next.", "format": "interview", "optimize_for": "retention"},
    ],
    "astrophysics": [
        {"title": "The big idea behind the observation", "angle": "Make one astrophysics concept feel legible and emotionally exciting.", "format": "solo", "optimize_for": "clarity"},
        {"title": "What this discovery changes in our picture of the universe", "angle": "Frame the science around worldview, not only raw facts.", "format": "narrative", "optimize_for": "retention"},
        {"title": "The question scientists still cannot answer", "angle": "Build tension around uncertainty while staying intellectually honest.", "format": "interview", "optimize_for": "retention"},
    ],
    "physical health": [
        {"title": "The small habit with outsized payoff", "angle": "Turn a health topic into a specific, humane weekly practice listeners can try.", "format": "solo", "optimize_for": "clarity"},
        {"title": "The health advice people hear but rarely understand", "angle": "Slow down and explain a familiar recommendation with more nuance.", "format": "narrative", "optimize_for": "retention"},
        {"title": "What actually works in the real world", "angle": "Keep the episode grounded in consistency and behavior change, not hype.", "format": "interview", "optimize_for": "clarity"},
    ],
    "mental health": [
        {"title": "The feeling behind the habit", "angle": "Explore one emotional or mental pattern with warmth and practical usefulness.", "format": "solo", "optimize_for": "retention"},
        {"title": "What helps when advice feels too generic", "angle": "Translate vague wellness language into specific, safer next steps.", "format": "narrative", "optimize_for": "clarity"},
        {"title": "How to talk about this without making it heavier", "angle": "Use conversation design that feels emotionally safe and non-performative.", "format": "interview", "optimize_for": "retention"},
    ],
    "technology": [
        {"title": "The product shift hiding in plain sight", "angle": "Make one product or platform shift feel meaningful and concrete.", "format": "solo", "optimize_for": "clarity"},
        {"title": "Why this technology is starting to matter now", "angle": "Tie the episode to timing, adoption, and user behavior instead of abstract trend language.", "format": "narrative", "optimize_for": "retention"},
        {"title": "What builders should pay attention to next", "angle": "Aim the episode at operators who want signal more than hype.", "format": "interview", "optimize_for": "clarity"},
    ],
    "business": [
        {"title": "The operating principle that changes execution", "angle": "Take one business principle and show how it changes real decisions.", "format": "solo", "optimize_for": "clarity"},
        {"title": "What strong operators notice early", "angle": "Use concrete examples to make business intuition teachable.", "format": "narrative", "optimize_for": "retention"},
        {"title": "The tradeoff behind the growth story", "angle": "Make the episode feel like a producer-led breakdown, not a generic business monologue.", "format": "interview", "optimize_for": "retention"},
    ],
}


def build_show_strategy_seed(
    show: Dict[str, Any],
    title: str,
    angle: str,
    why_now: str,
    format_name: str,
    desired_outcome: str,
    optimize_for: str,
) -> Dict[str, Any]:
    category = normalize_topic_name(show.get("category")) or DEFAULT_SHOW_CATEGORY
    tone = "storytelling" if format_name == "narrative" else "professional"
    return {
        "identity": {
            "podcastName": show.get("title", ""),
            "niche": category,
            "targetAudience": f"listeners who care about {category} and want sharper signal fast",
        },
        "episodeIntent": {
            "episodeGoal": "interview" if format_name == "interview" else "educate",
            "desiredOutcome": desired_outcome,
        },
        "contentInput": {
            "topic": title,
            "keyPoints": normalize_string_list([angle, why_now, desired_outcome], limit=5),
            "references": [],
        },
        "toneStyle": {
            "tone": tone,
            "format": format_name if format_name in {"solo", "interview", "narrative"} else "solo",
            "lengthPreference": "medium",
        },
        "growthOptimization": {
            "optimizeFor": optimize_for if optimize_for in {"retention", "virality", "clarity"} else "clarity",
            "includeHook": True,
            "knownIssues": "Avoid generic filler. Keep the structure specific and podcast-first.",
        },
    }


def build_show_strategy_snapshot(show: Dict[str, Any], analytics: Dict[str, Any], recent_episodes: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "show_updated_at": show.get("updated_at") or show.get("created_at") or "",
        "episode_count": int((analytics.get("overview") or {}).get("episode_count", 0) or 0),
        "listener_interests": [item.get("interest") for item in (analytics.get("listener_interests") or [])[:4]],
        "recent_titles": [episode.get("title", "") for episode in recent_episodes[:4]],
    }


def show_strategy_needs_refresh(cached: Any, snapshot: Dict[str, Any]) -> bool:
    if not isinstance(cached, dict):
        return True
    required = ["positioning", "audience_promise", "what_is_working", "underused_angles", "next_episode_ideas", "growth_moves"]
    if any(field not in cached or cached.get(field) in [None, "", []] for field in required):
        return True
    cached_snapshot = cached.get("snapshot") or {}
    return cached_snapshot != snapshot


def build_show_strategy_fallback(show: Dict[str, Any], analytics: Dict[str, Any], recent_episodes: List[Dict[str, Any]]) -> Dict[str, Any]:
    category = normalize_topic_name(show.get("category")) or DEFAULT_SHOW_CATEGORY
    playbook = SHOW_STRATEGY_PLAYBOOK.get(category, SHOW_STRATEGY_PLAYBOOK.get("technology", []))
    recent_titles = [episode.get("title", "") for episode in recent_episodes if episode.get("title")]
    listener_interests = [item.get("interest") for item in (analytics.get("listener_interests") or []) if item.get("interest")]
    overview = analytics.get("overview") or {}
    show_title = show.get("title", "This show")
    episode_count = int(overview.get("episode_count", 0) or 0)
    avg_completion = float(overview.get("avg_completion_rate", 0) or 0)
    total_plays = int(overview.get("total_plays", 0) or 0)
    total_saves = int(overview.get("saved_count", 0) or 0)

    what_is_working = []
    if episode_count:
        what_is_working.append(f"{show_title} already has {episode_count} published episode{'s' if episode_count != 1 else ''}, so listeners can see a real catalog instead of a one-off upload.")
    if recent_titles:
        what_is_working.append(f"Recent publishing momentum exists around {', '.join(recent_titles[:2])}.")
    if avg_completion >= 45:
        what_is_working.append(f"Average completion is {round(avg_completion, 1)}%, which suggests listeners are staying with the material once they start.")
    elif episode_count:
        what_is_working.append("The show has a foundation, but sharper hooks and clearer episode promises should improve completion.")
    if total_saves > 0 or total_plays > 0:
        what_is_working.append(f"The catalog has already generated {total_plays} plays and {total_saves} saves, which is enough signal to iterate intentionally.")
    if listener_interests:
        what_is_working.append(f"Current listeners cluster around {', '.join(listener_interests[:2])}, which gives the show a clearer demand signal.")
    if not what_is_working:
        what_is_working.append("The strongest opportunity right now is defining a repeatable angle so the show feels more like a series than a pile of uploads.")

    underused_angles = []
    if category == "current affairs":
        underused_angles.extend(["second-order effects instead of headline summary", "calmer explainers for listeners who want signal without outrage"])
    elif category == "finance":
        underused_angles.extend(["decision frameworks instead of only commentary", "finance explained through operator tradeoffs"])
    elif category == "mental health":
        underused_angles.extend(["emotionally safe practical routines", "language that feels human instead of therapeutic cliches"])
    else:
        underused_angles.extend(["stronger opinionated framing", "episode arcs that build from confusion to clarity"])
    if listener_interests:
        underused_angles.append(f"crossing {category} with listener demand around {listener_interests[0]}")

    next_episode_ideas = []
    for seed in playbook[:5]:
        desired_outcome = f"Leave with a more usable view of {category} and one concrete angle worth following next."
        idea = {
            "title": seed["title"],
            "angle": seed["angle"],
            "why_now": f"It strengthens {show_title}'s position by making {category} feel immediately useful instead of abstract.",
            "format": seed.get("format", "solo"),
            "desired_outcome": desired_outcome,
            "optimize_for": seed.get("optimize_for", "clarity"),
        }
        idea["ai_seed"] = build_show_strategy_seed(
            show,
            idea["title"],
            idea["angle"],
            idea["why_now"],
            idea["format"],
            idea["desired_outcome"],
            idea["optimize_for"],
        )
        next_episode_ideas.append(idea)

    title_starters = [idea["title"] for idea in next_episode_ideas[:4]]
    growth_moves = [
        "Keep each new episode promise specific enough that a listener can decide in five seconds whether it is for them.",
        "Build follow-up episodes as a sequence, so each release pulls the listener deeper into the show rather than restarting from zero.",
        "Use the AI Studio brief to lock audience, outcome, and format before generation so the podcast sounds intentional instead of generic.",
    ]
    snapshot = build_show_strategy_snapshot(show, analytics, recent_episodes)
    return {
        "positioning": f"{show_title} should feel like a trusted {category} show with a clear point of view, not just another upload surface.",
        "audience_promise": f"Listeners should leave each episode with clearer signal on {category} and a stronger sense of what matters next.",
        "what_is_working": what_is_working[:4],
        "underused_angles": underused_angles[:4],
        "next_episode_ideas": next_episode_ideas,
        "title_starters": title_starters,
        "growth_moves": growth_moves,
        "snapshot": snapshot,
        "generated_at": now_iso(),
        "provider": AI_TEXT_PROVIDER_DETERMINISTIC,
    }


def normalize_show_strategy(raw: Any, fallback: Dict[str, Any], show: Dict[str, Any]) -> Dict[str, Any]:
    raw = raw if isinstance(raw, dict) else {}
    normalized = {
        "positioning": clip_text(raw.get("positioning") or fallback.get("positioning"), limit=220),
        "audience_promise": clip_text(raw.get("audience_promise") or fallback.get("audience_promise"), limit=220),
        "what_is_working": normalize_string_list(raw.get("what_is_working"), limit=4) or fallback.get("what_is_working", []),
        "underused_angles": normalize_string_list(raw.get("underused_angles"), limit=4) or fallback.get("underused_angles", []),
        "title_starters": normalize_string_list(raw.get("title_starters"), limit=5) or fallback.get("title_starters", []),
        "growth_moves": normalize_string_list(raw.get("growth_moves"), limit=4) or fallback.get("growth_moves", []),
        "snapshot": raw.get("snapshot") if isinstance(raw.get("snapshot"), dict) else fallback.get("snapshot", {}),
        "generated_at": raw.get("generated_at") or fallback.get("generated_at") or now_iso(),
        "provider": raw.get("provider") or fallback.get("provider") or AI_TEXT_PROVIDER_DETERMINISTIC,
    }

    raw_ideas = raw.get("next_episode_ideas")
    ideas = []
    if isinstance(raw_ideas, list):
        for item in raw_ideas[:5]:
            if not isinstance(item, dict):
                continue
            title = clip_text(item.get("title"), limit=120)
            angle = clip_text(item.get("angle"), limit=180)
            why_now = clip_text(item.get("why_now"), limit=180)
            format_name = str(item.get("format") or "solo").strip().lower()
            desired_outcome = clip_text(item.get("desired_outcome"), limit=180)
            optimize_for = str(item.get("optimize_for") or "clarity").strip().lower()
            if not title or not angle:
                continue
            idea = {
                "title": title,
                "angle": angle,
                "why_now": why_now or fallback["next_episode_ideas"][0]["why_now"],
                "format": format_name if format_name in {"solo", "interview", "narrative"} else "solo",
                "desired_outcome": desired_outcome or fallback["next_episode_ideas"][0]["desired_outcome"],
                "optimize_for": optimize_for if optimize_for in {"retention", "virality", "clarity"} else "clarity",
            }
            idea["ai_seed"] = build_show_strategy_seed(
                show,
                idea["title"],
                idea["angle"],
                idea["why_now"],
                idea["format"],
                idea["desired_outcome"],
                idea["optimize_for"],
            )
            ideas.append(idea)
    normalized["next_episode_ideas"] = ideas or fallback.get("next_episode_ideas", [])
    return normalized


async def ensure_show_ai_strategy(
    show: Dict[str, Any],
    analytics: Dict[str, Any],
    recent_episodes: List[Dict[str, Any]],
    refresh: bool = False,
) -> Dict[str, Any]:
    snapshot = build_show_strategy_snapshot(show, analytics, recent_episodes)
    cached = clean_doc(show.get("ai_strategy")) if isinstance(show.get("ai_strategy"), dict) else None
    if cached and not refresh and not show_strategy_needs_refresh(cached, snapshot):
        return normalize_show_strategy(cached, build_show_strategy_fallback(show, analytics, recent_episodes), show)

    fallback = build_show_strategy_fallback(show, analytics, recent_episodes)
    context = {
        "show_title": show.get("title", ""),
        "show_description": show.get("description", ""),
        "category": show.get("category", DEFAULT_SHOW_CATEGORY),
        "recent_episode_titles": [episode.get("title", "") for episode in recent_episodes[:6]],
        "analytics": {
            "overview": analytics.get("overview", {}),
            "listener_interests": analytics.get("listener_interests", []),
            "top_episode_titles": [episode.get("title", "") for episode in (analytics.get("episodes") or [])[:5]],
        },
    }
    prompt = f"""Create a concise AI strategy memo for a podcast creator.

Context: {json.dumps(context, ensure_ascii=False)}

Return JSON with exactly these keys:
- positioning
- audience_promise
- what_is_working
- underused_angles
- next_episode_ideas
- title_starters
- growth_moves

Rules:
- Be concrete and podcast-specific, not generic startup advice.
- next_episode_ideas should be an array of objects with title, angle, why_now, format, desired_outcome, optimize_for.
- Keep the advice realistic for the existing show state.
"""
    result = await run_ai_json_chat(
        "show_ai_strategy",
        "You are a strong podcast strategist for creators. Give concrete, useful guidance that improves listener retention and show clarity. Return only JSON.",
        prompt,
        expected_type=dict,
    )
    strategy = normalize_show_strategy(result.get("raw"), fallback, show)
    strategy["snapshot"] = snapshot
    strategy["provider"] = result.get("provider") or strategy.get("provider") or AI_TEXT_PROVIDER_DETERMINISTIC
    await db.shows.update_one(
        {"id": show["id"]},
        {"$set": {"ai_strategy": strategy, "ai_strategy_generated_at": strategy["generated_at"]}},
    )
    return strategy


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


class EpisodeAssistantRequest(BaseModel):
    question: str


class ManualSocialConnectRequest(BaseModel):
    provider: Literal["linkedin", "instagram"]
    access_token: str
    refresh_token: Optional[str] = ""
    organization_id: Optional[str] = ""
    organization_name: Optional[str] = ""
    page_id: Optional[str] = ""
    instagram_account_id: Optional[str] = ""
    account_name: Optional[str] = ""


class SocialPostCreateRequest(BaseModel):
    provider: Literal["linkedin", "instagram"]
    social_account_id: str
    headline: str
    caption: Optional[str] = ""
    cta: Optional[str] = ""
    link_url: Optional[str] = ""
    hashtags: Optional[List[str]] = []
    scheduled_at: Optional[str] = ""
    asset_url: Optional[str] = ""
    use_generated_card: bool = True
    source: Optional[str] = "manual"
    status: Optional[str] = SOCIAL_POST_STATUS_DRAFT
    publish_now: bool = False


class FeedbackSubmissionRequest(BaseModel):
    persona: Optional[Literal["listener", "podcaster", "visitor", "investor", "other"]] = "visitor"
    category: Optional[Literal["bug", "confusing", "missing_feature", "delight", "pricing", "launch", "other"]] = "other"
    rating: Optional[int] = None
    page_url: Optional[str] = ""
    message: str
    desired_outcome: Optional[str] = ""
    friction_area: Optional[str] = ""
    email: Optional[str] = ""
    contact_ok: bool = False


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


class VoiceCastingInput(BaseModel):
    selectedVoiceIds: List[str] = Field(default_factory=lambda: DEFAULT_AI_PODCAST_VOICE_IDS[:3])


class AIPodcastIntake(BaseModel):
    identity: PodcastIdentityInput
    episodeIntent: EpisodeIntentInput
    contentInput: ContentInput
    toneStyle: ToneStyleInput
    growthOptimization: GrowthOptimizationInput
    voiceCasting: VoiceCastingInput = Field(default_factory=VoiceCastingInput)


class GenerateAIPodcastDraftRequest(BaseModel):
    show_id: str
    intake: AIPodcastIntake


class CreateAIStudioProjectRequest(BaseModel):
    show_id: str
    intake: Optional[AIPodcastIntake] = None
    title: Optional[str] = ""


class UpdateAIStudioProjectRequest(BaseModel):
    title: Optional[str] = None
    intake: Optional[AIPodcastIntake] = None
    active_stage: Optional[Literal[
        "brief",
        "research",
        "outline",
        "script",
        "cast",
        "table_read",
        "final_render",
        "agent2_review",
        "publish",
    ]] = None
    show_bible: Optional[Dict[str, Any]] = None
    cast: Optional[List[Dict[str, Any]]] = None


class UpdateAIStudioProjectStageRequest(BaseModel):
    stage: Literal[
        "brief",
        "research",
        "outline",
        "script",
        "cast",
        "table_read",
        "final_render",
        "agent2_review",
        "publish",
    ]
    status: str = "in_progress"
    notes: Optional[str] = ""
    artifact: Optional[Dict[str, Any]] = None


class CreateAIStudioRenderJobRequest(BaseModel):
    project_id: str
    draft_id: Optional[str] = ""
    render_type: Literal["preview", "final"] = "preview"


app = FastAPI()
api_router = APIRouter(prefix="/api")


@api_router.get("/ai-voice-library")
async def get_ai_voice_library():
    return {
        "voices": [public_ai_podcast_voice(voice) for voice in AI_PODCAST_VOICE_LIBRARY],
        "defaults": DEFAULT_AI_PODCAST_VOICE_IDS[:3],
        "selection_limit": 4,
        "pacing": {
            "sentence_gap_seconds": ai_audio_sentence_gap_seconds(),
            "start_padding_seconds": ai_audio_edge_padding_seconds(),
            "end_padding_seconds": ai_audio_edge_padding_seconds(),
        },
    }


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=()")
    response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
    if (request.headers.get("x-forwarded-proto") or request.url.scheme).lower() == "https":
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains; preload")
    return response


@app.on_event("startup")
async def startup():
    validate_runtime_security()
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
    await db.podcasts.create_index(
        [("podcaster_id", 1), ("ai_draft_id", 1)],
        unique=True,
        partialFilterExpression={"ai_draft_id": {"$exists": True}, "is_deleted": False},
    )
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
    await db.ai_studio_projects.create_index("id", unique=True)
    await db.ai_studio_projects.create_index("podcaster_id")
    await db.ai_studio_projects.create_index([("podcaster_id", 1), ("show_id", 1), ("updated_at", -1)])
    await db.ai_studio_render_jobs.create_index("id", unique=True)
    await db.ai_studio_render_jobs.create_index([("podcaster_id", 1), ("project_id", 1), ("created_at", -1)])
    await db.social_connected_accounts.create_index("id", unique=True)
    await db.social_connected_accounts.create_index([("user_id", 1), ("provider", 1), ("account_id", 1)], unique=True)
    await db.social_connected_accounts.create_index([("user_id", 1), ("provider", 1)])
    await db.social_posts.create_index("id", unique=True)
    await db.social_posts.create_index([("user_id", 1), ("status", 1), ("scheduled_at", 1)])
    await db.social_posts.create_index([("user_id", 1), ("provider", 1), ("created_at", -1)])
    await db.feedback_submissions.create_index("id", unique=True)
    await db.feedback_submissions.create_index([("created_at", -1)])
    await db.feedback_submissions.create_index([("analysis.problem_areas", 1), ("analysis.urgency", 1)])
    await db.feedback_submissions.create_index([("user_id", 1), ("created_at", -1)])
    await db.rate_limits.create_index("expires_at", expireAfterSeconds=0)
    await db.analytics_events.create_index("created_at", expireAfterSeconds=analytics_retention_seconds())
    await db.analytics_events.create_index([("event_type", 1), ("created_at", -1)])
    await db.analytics_events.create_index([("episode_id", 1), ("created_at", -1)])
    await db.analytics_events.create_index([("user_id", 1), ("created_at", -1)])
    await db.analytics_events.create_index([("show_id", 1), ("bucket_date", 1)])
    await db.daily_episode_metrics.create_index([("episode_id", 1), ("bucket_date", 1)], unique=True)
    await db.daily_episode_metrics.create_index([("show_id", 1), ("bucket_date", -1)])
    await db.podcasts.create_index([("is_deleted", 1), ("publication_status", 1), ("moderation_status", 1), ("category", 1), ("created_at", -1)])
    await db.podcasts.create_index([("is_deleted", 1), ("publication_status", 1), ("moderation_status", 1), ("play_count", -1), ("created_at", -1)])
    await db.podcasts.create_index([("is_deleted", 1), ("publication_status", 1), ("moderation_status", 1), ("rating_average", -1), ("rating_count", -1)])
    await db.podcasts.create_index([("show_id", 1), ("season_number", 1), ("episode_number", 1)])

    admin_email = os.environ.get("ADMIN_EMAIL", "admin@audioraq.com")
    admin_password = get_admin_password_for_seed()
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
    app.state.social_queue_task = asyncio.create_task(social_queue_daemon())


@app.on_event("shutdown")
async def shutdown():
    task = getattr(app.state, "social_queue_task", None)
    if task:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    try:
        init_storage()
        logger.info("Storage initialized")
    except Exception as e:
        logger.error(f"Storage init failed: {e}")

    write_test_credentials_if_enabled(admin_email, admin_password)


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
        return attach_auth_token_payload(payload, access_token)

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
    return attach_auth_token_payload(payload, access_token)


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
    return attach_auth_token_payload(payload, access_token)


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
    return attach_auth_token_payload(payload, access_token)


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
        payload = {"message": "Token refreshed"}
        return attach_auth_token_payload(payload, access_token)
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


@api_router.get("/social/providers")
async def get_social_publish_providers():
    manual_supported = is_manual_social_connect_enabled()
    return {
        "linkedin": {
            "configured": is_linkedin_social_configured(),
            "oauth_supported": is_linkedin_social_configured(),
            "manual_token_supported": manual_supported,
            "scopes": get_linkedin_social_scopes().split(),
        },
        "instagram": {
            "configured": is_instagram_social_configured(),
            "oauth_supported": is_instagram_social_configured(),
            "manual_token_supported": manual_supported,
            "scopes": get_instagram_social_scopes().split(","),
        },
    }


@api_router.get("/social/accounts")
async def get_social_accounts(request: Request):
    user = await get_current_user(request)
    ensure_social_publishing_access(user)
    return {"accounts": await fetch_user_social_accounts(user)}


@api_router.get("/social/oauth/{provider}/start")
async def start_social_publish_connect(provider: str, request: Request, return_origin: Optional[str] = None):
    user = await get_current_user(request)
    ensure_social_publishing_access(user)
    if provider not in SUPPORTED_SOCIAL_PUBLISH_PROVIDERS:
        raise HTTPException(status_code=404, detail="Unsupported social publishing provider")
    if not is_social_publish_provider_configured(provider):
        raise HTTPException(status_code=400, detail=f"{provider.title()} publishing is not configured on the server yet")

    resolved_return_origin = sanitize_return_origin(return_origin, request)
    state = build_social_publish_state(provider, user_id_str(user), resolved_return_origin)
    if provider == SOCIAL_PUBLISH_PROVIDER_LINKEDIN:
        return RedirectResponse(build_linkedin_social_authorize_url(request, state), status_code=302)
    if provider == SOCIAL_PUBLISH_PROVIDER_INSTAGRAM:
        return RedirectResponse(build_instagram_social_authorize_url(request, state), status_code=302)
    raise HTTPException(status_code=404, detail="Unsupported social publishing provider")


@api_router.get("/social/oauth/{provider}/callback")
async def social_publish_connect_callback(provider: str, request: Request, code: Optional[str] = None, state: Optional[str] = None, error: Optional[str] = None):
    if provider not in SUPPORTED_SOCIAL_PUBLISH_PROVIDERS:
        raise HTTPException(status_code=404, detail="Unsupported social publishing provider")
    if not state:
        raise HTTPException(status_code=400, detail="Missing social publishing state")
    decoded = decode_social_publish_state(state, provider)
    return_origin = decoded.get("return_origin") or get_public_app_origin(request)
    if error:
        return social_publish_redirect(request, return_origin, {"social_error": error[:180]})
    if not code:
        return social_publish_redirect(request, return_origin, {"social_error": "Provider did not return an authorization code"})

    user = await db.users.find_one({"_id": ObjectId(decoded["sub"])})
    if not user:
        return social_publish_redirect(request, return_origin, {"social_error": "User session expired before provider connection completed"})
    user["_id"] = str(user["_id"])
    user.pop("password_hash", None)

    try:
        if provider == SOCIAL_PUBLISH_PROVIDER_LINKEDIN:
            tokens = exchange_linkedin_social_code(request, code)
            connected = await connect_linkedin_social_accounts(
                user,
                tokens["access_token"],
                refresh_token=tokens.get("refresh_token", ""),
                token_expires_at=tokens.get("token_expires_at", ""),
            )
        else:
            tokens = exchange_instagram_social_code(request, code)
            connected = await connect_instagram_social_accounts(
                user,
                tokens["access_token"],
                token_expires_at=tokens.get("token_expires_at", ""),
            )
    except HTTPException as exc:
        return social_publish_redirect(request, return_origin, {"social_error": str(exc.detail)[:180]})
    except Exception as exc:
        logger.error(f"Social publish OAuth callback failed for {provider}: {exc}")
        return social_publish_redirect(request, return_origin, {"social_error": f"{provider.title()} connection could not be completed"})

    success_message = f"{provider.title()} connected"
    if len(connected) > 1:
        success_message = f"{provider.title()} connected with {len(connected)} accounts"
    return social_publish_redirect(request, return_origin, {"social_success": success_message[:180]})


@api_router.post("/social/connect/manual")
async def manual_social_publish_connect(req: ManualSocialConnectRequest, request: Request):
    user = await get_current_user(request)
    ensure_social_publishing_access(user)
    if not is_manual_social_connect_enabled():
        raise HTTPException(status_code=403, detail="Manual token connect is disabled. Use OAuth connection instead.")
    await enforce_rate_limit(request, "manual_social_connect", 8, 3600)
    access_token = (req.access_token or "").strip()
    if not access_token:
        raise HTTPException(status_code=400, detail="Access token is required")

    if req.provider == SOCIAL_PUBLISH_PROVIDER_LINKEDIN:
        connected = await connect_linkedin_social_accounts(
            user,
            access_token,
            refresh_token=(req.refresh_token or "").strip(),
            organization_id=req.organization_id or "",
            organization_name=req.organization_name or "",
        )
    elif req.provider == SOCIAL_PUBLISH_PROVIDER_INSTAGRAM:
        connected = await connect_instagram_social_accounts(
            user,
            access_token,
            refresh_token=(req.refresh_token or "").strip(),
            page_id=req.page_id or "",
            instagram_account_id=req.instagram_account_id or "",
            account_name=req.account_name or "",
        )
    else:
        raise HTTPException(status_code=404, detail="Unsupported social publishing provider")
    return {"accounts": connected}


@api_router.delete("/social/accounts/{social_account_id}")
async def disconnect_social_account(social_account_id: str, request: Request):
    user = await get_current_user(request)
    ensure_social_publishing_access(user)
    await db.social_connected_accounts.delete_one({"id": social_account_id, "user_id": user_id_str(user)})
    await db.social_posts.update_many(
        {"social_account_id": social_account_id, "user_id": user_id_str(user), "status": {"$in": [SOCIAL_POST_STATUS_DRAFT, SOCIAL_POST_STATUS_QUEUED]}},
        {"$set": {"status": SOCIAL_POST_STATUS_FAILED, "failure_reason": "Connected account was removed", "updated_at": now_iso()}},
    )
    return {"message": "Connected social account removed"}


@api_router.get("/social/posts")
async def get_social_posts(request: Request, provider: Optional[str] = None, status: Optional[str] = None, limit: int = 40):
    user = await get_current_user(request)
    ensure_social_publishing_access(user)
    query = {"user_id": user_id_str(user)}
    if provider:
        query["provider"] = provider
    normalized_status = normalize_social_post_status(status)
    if status:
        query["status"] = normalized_status
    posts = await db.social_posts.find(query).sort("created_at", -1).limit(max(1, min(limit, 100))).to_list(max(1, min(limit, 100)))
    return {"posts": [sanitize_social_post(post) for post in posts]}


@api_router.post("/social/posts")
async def create_social_post(req: SocialPostCreateRequest, request: Request):
    user = await get_current_user(request)
    ensure_social_publishing_access(user)
    await get_social_connected_account(user, req.social_account_id)

    payload = req.model_dump()
    if payload.get("scheduled_at"):
        scheduled = parse_iso_datetime(payload["scheduled_at"])
        if scheduled is None:
            raise HTTPException(status_code=400, detail="scheduled_at must be a valid ISO timestamp")
        payload["scheduled_at"] = scheduled.astimezone(timezone.utc).isoformat()
    post = await create_social_post_record(user, payload, publish_now=bool(req.publish_now))
    return post


@api_router.post("/social/posts/{post_id}/publish")
async def publish_social_post_endpoint(post_id: str, request: Request):
    user = await get_current_user(request)
    ensure_social_publishing_access(user)
    return await publish_social_post_record(post_id, user=user)


@api_router.delete("/social/posts/{post_id}")
async def delete_social_post(post_id: str, request: Request):
    user = await get_current_user(request)
    ensure_social_publishing_access(user)
    await db.social_posts.delete_one({"id": post_id, "user_id": user_id_str(user)})
    return {"message": "Social post removed"}


@api_router.post("/social/queue/process")
async def process_social_queue_endpoint(request: Request):
    user = await get_current_user(request)
    ensure_social_publishing_access(user)
    results = await process_due_social_posts()
    owned_results = [post for post in results if post.get("user_id") == user_id_str(user) or not post.get("user_id")]
    return {"processed_count": len(results), "posts": owned_results}


@api_router.get("/social/analytics")
async def get_social_analytics(request: Request):
    user = await get_current_user(request)
    ensure_social_publishing_access(user)
    return await build_social_analytics(user)


@api_router.get("/social/posts/{post_id}/card.png")
async def get_social_post_card(post_id: str):
    post = await db.social_posts.find_one({"id": post_id})
    if not post:
        raise HTTPException(status_code=404, detail="Social post not found")
    image_bytes = generate_social_card_image(post)
    return StreamingResponse(io.BytesIO(image_bytes), media_type="image/png")


@api_router.post("/feedback")
async def submit_feedback(req: FeedbackSubmissionRequest, request: Request):
    await enforce_rate_limit(request, "feedback_submit", 20, 3600)
    current_user = await try_get_current_user(request)
    message = str(req.message or "").strip()
    if len(message) < 8:
        raise HTTPException(status_code=400, detail="Tell us a little more so the feedback is useful")

    rating = normalize_feedback_rating(req.rating)
    email = (req.email or "").lower().strip()
    if current_user and current_user.get("email"):
        email = current_user["email"]
    if req.contact_ok and not email:
        raise HTTPException(status_code=400, detail="Add an email if you want us to follow up")

    desired_outcome = str(req.desired_outcome or "").strip()
    friction_area = str(req.friction_area or "").strip()
    analysis = classify_feedback_text(message, desired_outcome=desired_outcome, friction_area=friction_area)
    user_role = current_user.get("role") if current_user else "guest"
    persona = req.persona or ("podcaster" if user_role == "podcaster" else "listener" if user_role == "user" else "visitor")

    feedback_doc = {
        "id": str(uuid.uuid4()),
        "user_id": user_id_str(current_user) if current_user else "",
        "user_role": user_role,
        "user_name": current_user.get("name", "") if current_user else "",
        "email": email,
        "persona": persona,
        "category": req.category or "other",
        "rating": rating,
        "page_url": str(req.page_url or "").strip()[:500],
        "message": message[:4000],
        "desired_outcome": desired_outcome[:1200],
        "friction_area": friction_area[:240],
        "contact_ok": bool(req.contact_ok),
        "analysis": analysis,
        "status": "new",
        "source": "in_app_feedback_widget",
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    await db.feedback_submissions.insert_one(feedback_doc)
    return {
        "message": "Feedback received",
        "feedback": sanitize_feedback_record(feedback_doc),
        "analysis": analysis,
    }


@api_router.get("/feedback/summary")
async def get_feedback_summary(request: Request, limit: int = 80):
    user = await get_current_user(request)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Only founders can view feedback summaries")
    records = await db.feedback_submissions.find({}).sort("created_at", -1).limit(max(1, min(limit, 250))).to_list(max(1, min(limit, 250)))
    summaries = [build_feedback_summary(record) for record in records]
    problem_counts: Dict[str, int] = {}
    urgency_counts: Dict[str, int] = {}
    sentiment_counts: Dict[str, int] = {}
    for record in records:
        analysis = record.get("analysis") or {}
        for problem in analysis.get("problem_areas") or ["general_product_learning"]:
            problem_counts[problem] = problem_counts.get(problem, 0) + 1
        urgency = analysis.get("urgency", "medium")
        sentiment = analysis.get("sentiment", "neutral")
        urgency_counts[urgency] = urgency_counts.get(urgency, 0) + 1
        sentiment_counts[sentiment] = sentiment_counts.get(sentiment, 0) + 1

    return {
        "total": len(records),
        "problem_counts": problem_counts,
        "urgency_counts": urgency_counts,
        "sentiment_counts": sentiment_counts,
        "recent": summaries,
    }


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
        query = add_query_clause(query, topic_match_clause(category))
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


@api_router.get("/ai-studio/status")
async def get_ai_studio_status(request: Request):
    user = await get_current_user(request)
    if user["role"] != "podcaster":
        raise HTTPException(status_code=403, detail="Only podcasters can view AI Studio status")

    text_order = get_ai_text_provider_order()
    audio_order = get_ai_audio_provider_order()
    warnings = []
    if AI_TEXT_PROVIDER_EMERGENT in text_order:
        warnings.append("Text generation can still use the remote Emergent provider. Set AI_TEXT_PROVIDER=ollama,deterministic and AI_TEXT_ALLOW_REMOTE=false for local-first mode.")
    if any(provider in audio_order for provider in ["elevenlabs", "openai"]):
        warnings.append("Audio rendering can still use production TTS APIs. Set AI_AUDIO_TTS_PROVIDER=local_http,local for local-first mode.")
    if get_storage_backend() == "emergent":
        warnings.append("Media storage is still using the Emergent object store. Set STORAGE_BACKEND=local after migrating existing media.")

    return {
        "mode": os.environ.get("AI_STUDIO_MODE", "sync").strip().lower() or "sync",
        "text_generation": {
            "provider_order": text_order,
            "local_provider": AI_TEXT_PROVIDER_OLLAMA,
            "local_model": os.environ.get("AI_TEXT_LOCAL_MODEL", "llama3.2:3b"),
            "local_endpoint_configured": bool(os.environ.get("AI_TEXT_LOCAL_BASE_URL") or os.environ.get("OLLAMA_BASE_URL")),
            "remote_allowed": parse_bool_env("AI_TEXT_ALLOW_REMOTE", True),
        },
        "audio_rendering": {
            "provider_order": audio_order,
            "local_neural_worker_configured": bool(os.environ.get("AI_AUDIO_LOCAL_TTS_URL")),
            "require_neural_worker": parse_bool_env("AI_AUDIO_REQUIRE_NEURAL_WORKER", False),
            "local_fallback": "local" in audio_order,
            "local_fallback_quality": "espeak-ng enhanced fallback; not production neural TTS",
        },
        "storage": {
            "backend": get_storage_backend(),
            "local_storage_configured": get_storage_backend() == "local",
        },
        "quality_gate": {
            "agent2_version": AGENT2_VERSION,
            "publishes_after_agent2_review": True,
            "ai_creation_media_policy": "audio_only",
        },
        "warnings": warnings,
    }


@api_router.get("/ai-studio/projects/my")
async def get_my_ai_studio_projects(request: Request, show_id: Optional[str] = None, limit: int = 12):
    user = await get_current_user(request)
    if user["role"] != "podcaster":
        raise HTTPException(status_code=403, detail="Only podcasters can use AI Studio projects")

    query = {"podcaster_id": user["_id"], "is_deleted": {"$ne": True}}
    if show_id:
        query["show_id"] = show_id

    safe_limit = max(1, min(limit, 30))
    projects = await db.ai_studio_projects.find(query).sort("updated_at", -1).limit(safe_limit).to_list(safe_limit)
    return {"projects": [clean_doc(project) for project in projects]}


@api_router.get("/ai-studio/projects/{project_id}")
async def get_ai_studio_project(project_id: str, request: Request):
    user = await get_current_user(request)
    if user["role"] != "podcaster":
        raise HTTPException(status_code=403, detail="Only podcasters can use AI Studio projects")

    project = await db.ai_studio_projects.find_one({"id": project_id, "podcaster_id": user["_id"], "is_deleted": {"$ne": True}})
    if project is None:
        raise HTTPException(status_code=404, detail="AI Studio project not found")
    return clean_doc(project)


@api_router.post("/ai-studio/projects")
async def create_ai_studio_project(req: CreateAIStudioProjectRequest, request: Request):
    user = await get_current_user(request)
    if user["role"] != "podcaster":
        raise HTTPException(status_code=403, detail="Only podcasters can use AI Studio projects")

    show_id = req.show_id.strip()
    if not show_id:
        raise HTTPException(status_code=400, detail="Pick a show before creating an AI Studio project")
    show = await db.shows.find_one({"id": show_id, "podcaster_id": user["_id"], "is_deleted": False})
    if show is None:
        raise HTTPException(status_code=404, detail="Show not found")

    intake = req.intake.dict() if req.intake else None
    project_doc = build_ai_studio_project_doc(user, show, intake=intake, title=(req.title or "").strip())
    await db.ai_studio_projects.insert_one(project_doc)
    return clean_doc(project_doc)


@api_router.patch("/ai-studio/projects/{project_id}")
async def update_ai_studio_project(project_id: str, req: UpdateAIStudioProjectRequest, request: Request):
    user = await get_current_user(request)
    if user["role"] != "podcaster":
        raise HTTPException(status_code=403, detail="Only podcasters can use AI Studio projects")

    project = await db.ai_studio_projects.find_one({"id": project_id, "podcaster_id": user["_id"], "is_deleted": {"$ne": True}})
    if project is None:
        raise HTTPException(status_code=404, detail="AI Studio project not found")

    updates: Dict[str, Any] = {"updated_at": now_iso()}
    if req.title is not None:
        updates["title"] = req.title.strip() or project.get("title") or "Untitled AI Studio Project"
    if req.active_stage is not None:
        updates["active_stage"] = req.active_stage
    if req.intake is not None:
        intake = req.intake.dict()
        show = await db.shows.find_one({"id": project["show_id"], "podcaster_id": user["_id"], "is_deleted": False})
        if show is None:
            raise HTTPException(status_code=404, detail="Show not found")
        updates["intake"] = intake
        updates["show_bible"] = build_ai_studio_show_bible(show, intake)
        updates["artifacts"] = build_ai_studio_artifacts(intake, show, project.get("generation") or {}, project.get("agent2_review") or {})
        updates["stage_state"] = build_ai_studio_stage_state(intake, project.get("generation") or {}, project.get("agent2_review") or {}, project.get("published_episode_id") or "")
    if req.show_bible is not None:
        updates["show_bible"] = req.show_bible
        if "artifacts" in updates:
            updates["artifacts"]["show_bible"] = req.show_bible
        else:
            updates["artifacts.show_bible"] = req.show_bible
    if req.cast is not None:
        if "artifacts" in updates:
            updates["artifacts"]["cast"] = req.cast
        else:
            updates["artifacts.cast"] = req.cast

    await db.ai_studio_projects.update_one({"id": project_id}, {"$set": updates})
    updated = await db.ai_studio_projects.find_one({"id": project_id, "podcaster_id": user["_id"]})
    return clean_doc(updated)


@api_router.post("/ai-studio/projects/{project_id}/stage")
async def update_ai_studio_project_stage(project_id: str, req: UpdateAIStudioProjectStageRequest, request: Request):
    user = await get_current_user(request)
    if user["role"] != "podcaster":
        raise HTTPException(status_code=403, detail="Only podcasters can use AI Studio projects")

    project = await db.ai_studio_projects.find_one({"id": project_id, "podcaster_id": user["_id"], "is_deleted": {"$ne": True}})
    if project is None:
        raise HTTPException(status_code=404, detail="AI Studio project not found")

    stage_state = update_ai_studio_stage_state(project.get("stage_state") or {}, req.stage, req.status.strip() or "in_progress", req.notes or "")
    updates: Dict[str, Any] = {
        "stage_state": stage_state,
        "active_stage": req.stage,
        "updated_at": now_iso(),
    }
    if req.artifact is not None:
        updates[f"artifacts.{req.stage}"] = req.artifact

    await db.ai_studio_projects.update_one({"id": project_id}, {"$set": updates})
    updated = await db.ai_studio_projects.find_one({"id": project_id, "podcaster_id": user["_id"]})
    return clean_doc(updated)


@api_router.get("/ai-studio/render-jobs/my")
async def get_my_ai_studio_render_jobs(request: Request, project_id: Optional[str] = None, limit: int = 12):
    user = await get_current_user(request)
    if user["role"] != "podcaster":
        raise HTTPException(status_code=403, detail="Only podcasters can use AI Studio render jobs")

    query = {"podcaster_id": user["_id"]}
    if project_id:
        query["project_id"] = project_id
    safe_limit = max(1, min(limit, 30))
    jobs = await db.ai_studio_render_jobs.find(query).sort("created_at", -1).limit(safe_limit).to_list(safe_limit)
    return {"jobs": [clean_doc(job) for job in jobs]}


@api_router.post("/ai-studio/render-jobs")
async def create_ai_studio_render_job(req: CreateAIStudioRenderJobRequest, request: Request):
    user = await get_current_user(request)
    if user["role"] != "podcaster":
        raise HTTPException(status_code=403, detail="Only podcasters can use AI Studio render jobs")

    project_id = req.project_id.strip()
    project = await db.ai_studio_projects.find_one({"id": project_id, "podcaster_id": user["_id"], "is_deleted": {"$ne": True}})
    if project is None:
        raise HTTPException(status_code=404, detail="AI Studio project not found")

    draft_id = (req.draft_id or project.get("source_draft_id") or "").strip()
    if draft_id:
        draft = await db.ai_podcast_drafts.find_one({"id": draft_id, "podcaster_id": user["_id"]})
        if draft is None:
            raise HTTPException(status_code=404, detail="AI draft not found")

    job = {
        "id": str(uuid.uuid4()),
        "project_id": project["id"],
        "draft_id": draft_id,
        "show_id": project.get("show_id", ""),
        "podcaster_id": user["_id"],
        "podcaster_name": user.get("name", ""),
        "render_type": req.render_type,
        "status": "queued",
        "provider_order": get_ai_audio_provider_order(),
        "message": "Queued for the AI Studio render layer. The current publish action can still render synchronously while the async worker is scaled.",
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    await db.ai_studio_render_jobs.insert_one(job)
    stage_state = update_ai_studio_stage_state(project.get("stage_state") or {}, "final_render", "queued", "Audio render job queued.")
    await db.ai_studio_projects.update_one(
        {"id": project["id"]},
        {"$set": {"stage_state": stage_state, "active_stage": "final_render", "updated_at": now_iso(), "last_render_job_id": job["id"]}},
    )
    return clean_doc(job)


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
    intake["voiceCasting"] = {
        **(intake.get("voiceCasting") or {}),
        "selectedVoiceIds": selected_ai_voice_ids_from_intake(intake, limit=4),
    }
    if not normalize_string_list(intake["contentInput"].get("keyPoints"), limit=10):
        raise HTTPException(status_code=400, detail="Add at least one key point before generating")

    generation = await generate_ai_podcast_package(intake, show)
    agent2_review = evaluate_agent2_quality(
        generation.get("episode_title") or intake["contentInput"].get("topic") or "Untitled AI Episode",
        generation.get("suggested_description") or build_ai_publish_description(generation),
        generation=generation,
        source_kind="ai_draft",
        voice_context=build_voice_context_from_intake(intake, generation.get("recommended_category") or show.get("category", ""), show),
    )
    agent2_iterations = [{"iteration": 1, "event": "initial_review", "review": agent2_review}]
    revised_generation = await revise_ai_generation_with_agent2_feedback(intake, show, generation, agent2_review)
    if revised_generation:
        revised_agent2_review = evaluate_agent2_quality(
            revised_generation.get("episode_title")
            or generation.get("episode_title")
            or intake["contentInput"].get("topic")
            or "Untitled AI Episode",
            revised_generation.get("suggested_description") or build_ai_publish_description(revised_generation),
            generation=revised_generation,
            source_kind="ai_draft_revision",
            voice_context=build_voice_context_from_intake(
                intake,
                revised_generation.get("recommended_category") or show.get("category", ""),
                show,
            ),
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
    project_doc = build_ai_studio_project_doc(
        user,
        show,
        intake=intake,
        generation=generation,
        agent2_review=agent2_review,
        source_draft_id=draft_doc["id"],
    )
    draft_doc["ai_studio_project_id"] = project_doc["id"]
    draft_doc["ai_studio_project"] = clean_doc(project_doc)
    await db.ai_studio_projects.insert_one(project_doc)
    await db.ai_podcast_drafts.insert_one(draft_doc)
    return clean_doc(draft_doc)


@api_router.post("/shows/import-rss")
async def import_rss_feed(req: RssImportRequest, request: Request):
    user = await get_current_user(request)
    if user["role"] != "podcaster":
        raise HTTPException(status_code=403, detail="Only podcasters can import RSS feeds")
    await enforce_rate_limit(request, "rss_import", 12, 3600)

    feed_url = validate_runtime_url(req.feed_url.strip())
    if not feed_url:
        raise HTTPException(status_code=400, detail="Feed URL is required")

    try:
        response = safe_external_get(feed_url, timeout=30, max_bytes=8_388_608)
        response.raise_for_status()
    except HTTPException:
        raise
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
    if feed_thumbnail:
        try:
            feed_thumbnail = validate_external_redirect_url(feed_thumbnail)
        except HTTPException:
            feed_thumbnail = ""

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
        try:
            media_url = validate_external_redirect_url(media_url)
        except HTTPException:
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
        if item_thumbnail:
            try:
                item_thumbnail = validate_external_redirect_url(item_thumbnail)
            except HTTPException:
                item_thumbnail = ""
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
    auto_generate_thumbnail: bool = Form(True),
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
    elif auto_generate_thumbnail:
        thumbnail_path = store_generated_thumbnail(
            f"show-thumbnails/{user['_id']}",
            title.strip() or "Audioraq Show",
            user.get("name", ""),
            category or DEFAULT_SHOW_CATEGORY,
            kind="show",
        )

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


@api_router.get("/shows/{show_id}/ai-strategy")
async def get_show_ai_strategy(show_id: str, request: Request, refresh: bool = False):
    user = await get_current_user(request)
    if user["role"] not in {"podcaster", "admin"}:
        raise HTTPException(status_code=403, detail="Only creators can view show strategy")

    show_query = {"id": show_id, "is_deleted": False}
    if user["role"] != "admin":
        show_query["podcaster_id"] = user["_id"]
    show = await db.shows.find_one(show_query)
    if not show:
        raise HTTPException(status_code=404, detail="Show not found")

    analytics_user = {"_id": show["podcaster_id"]}
    analytics = await fetch_creator_analytics(analytics_user, show_id=show_id)
    recent_episodes = await db.podcasts.find({"show_id": show_id, "is_deleted": False}).sort("created_at", -1).limit(12).to_list(12)
    strategy = await ensure_show_ai_strategy(show, analytics, recent_episodes, refresh=refresh)
    return strategy


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
    auto_generate_thumbnail: bool = Form(False),
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
    elif auto_generate_thumbnail:
        updates["thumbnail_path"] = store_generated_thumbnail(
            f"show-thumbnails/{user['_id']}",
            updates["title"],
            user.get("name", ""),
            updates["category"],
            kind="show",
        )

    await db.shows.update_one({"id": show_id}, {"$set": updates})
    if thumbnail or auto_generate_thumbnail:
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


@api_router.post("/shows/{show_id}/thumbnail/generate")
async def generate_show_thumbnail(show_id: str, request: Request):
    user = await get_current_user(request)
    if user["role"] != "podcaster" and user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Only creators can generate show thumbnails")
    owner_filter = {"id": show_id, "is_deleted": False}
    if user["role"] != "admin":
        owner_filter["podcaster_id"] = user["_id"]
    show = await db.shows.find_one(owner_filter)
    if not show:
        raise HTTPException(status_code=404, detail="Show not found")

    previous_thumbnail_path = (show.get("thumbnail_path") or "").strip()
    thumbnail_path = store_generated_thumbnail(
        f"show-thumbnails/{show['podcaster_id']}",
        show.get("title", "Audioraq Show"),
        show.get("podcaster_name", ""),
        show.get("category", DEFAULT_SHOW_CATEGORY),
        kind="show",
    )
    await db.shows.update_one({"id": show_id}, {"$set": {"thumbnail_path": thumbnail_path, "updated_at": now_iso()}})
    if previous_thumbnail_path and previous_thumbnail_path != thumbnail_path:
        cleanup_storage_paths([previous_thumbnail_path], strict=False)
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
            return RedirectResponse(validate_external_redirect_url(external_thumbnail_url))
        return generated_thumbnail_response(
            show.get("title", "Audioraq Show"),
            show.get("podcaster_name", ""),
            show.get("category", DEFAULT_SHOW_CATEGORY),
            kind="show",
        )
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
    ai_audio_provider: str = Form(""),
    ai_audio_provider_kind: str = Form(""),
    ai_audio_voice_profile: str = Form(""),
    season_number: Optional[int] = Form(None),
    episode_number: Optional[int] = Form(None),
    thumbnail: Optional[UploadFile] = File(None),
    auto_generate_thumbnail: bool = Form(True),
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
    ext = validate_media_extension_matches_type(file.filename or "", content_type, is_audio_upload, is_video_upload)

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
        existing_ai_episode = await db.podcasts.find_one(
            {"ai_draft_id": ai_draft["id"], "podcaster_id": user["_id"], "is_deleted": False}
        )
        if existing_ai_episode:
            enriched = await enrich_episodes([existing_ai_episode], current_user=user)
            return enriched[0]

    media_path = f"{APP_NAME}/episodes/{user['_id']}/{uuid.uuid4()}.{ext}"
    data = await read_upload_limited(file, max_upload_bytes())
    put_object(media_path, data, content_type)

    thumbnail_path = ""
    if thumbnail:
        thumbnail_path, _ = await store_upload(thumbnail, f"episode-thumbnails/{user['_id']}", "image/jpeg")

    normalized_category = (category or DEFAULT_SHOW_CATEGORY).lower()
    if not thumbnail_path and auto_generate_thumbnail:
        thumbnail_path = store_generated_thumbnail(
            f"episode-thumbnails/{user['_id']}",
            title,
            show.get("title", ""),
            normalized_category,
            kind="episode",
        )
    keywords = await extract_keywords(f"{title} {description} {normalized_category} {show['title']}")
    media_type = "video" if is_video_upload else "audio"
    selected_rating = normalize_content_rating(audience_rating)
    analysis_provider = "uploaded-media"
    if ai_draft:
        analysis_provider = (ai_audio_provider or "ai-audio-upload").strip()[:120] or "ai-audio-upload"
    media_analysis = attach_voice_clarity(
        transcribe_media_for_safety(data, file.filename or "", content_type),
        data,
        file.filename or "",
        content_type,
        provider=analysis_provider,
    )
    moderation = await review_episode_safety(
        show,
        title,
        description,
        normalized_category,
        selected_rating=selected_rating,
        generation=ai_draft.get("generation") if ai_draft else None,
        media_analysis=media_analysis,
    )
    voice_context = build_voice_context_from_intake(ai_draft.get("intake") if ai_draft else {}, normalized_category, show)
    quality_agent = evaluate_agent2_quality(
        title,
        description,
        generation=ai_draft.get("generation") if ai_draft else None,
        media_analysis=media_analysis,
        source_kind="ai_audio_upload" if ai_draft else "recorded_upload",
        voice_context=voice_context,
    )
    if ai_draft:
        enforce_ai_audio_listenability_gate(quality_agent, [media_path, thumbnail_path])
    enforce_audioraq_originals_quality_gate(show, title, quality_agent, [media_path, thumbnail_path])
    moderation = merge_agent2_quality_into_moderation(moderation, quality_agent)
    enforce_episode_moderation_gate(moderation, [media_path, thumbnail_path])
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
        podcast_doc["ai_audio_provider"] = analysis_provider
        podcast_doc["ai_audio_provider_kind"] = (ai_audio_provider_kind or "").strip()[:80]
        podcast_doc["ai_audio_voice_profile"] = (ai_audio_voice_profile or "").strip()[:80]
    await db.podcasts.insert_one(podcast_doc)
    await db.shows.update_one({"id": show["id"]}, {"$set": {"updated_at": now_iso()}})
    if ai_draft:
        await db.ai_podcast_drafts.update_one(
            {"id": ai_draft["id"]},
            {"$set": {"last_used_at": now_iso(), "updated_at": now_iso(), "published_episode_id": podcast_doc["id"]}},
        )
        if ai_draft.get("ai_studio_project_id"):
            await db.ai_studio_projects.update_one(
                {"id": ai_draft["ai_studio_project_id"], "podcaster_id": user["_id"]},
                {
                    "$set": {
                        "status": "published",
                        "published_episode_id": podcast_doc["id"],
                        "agent2_review": quality_agent,
                        "artifacts": build_ai_studio_artifacts(ai_draft.get("intake") or {}, show, ai_draft.get("generation") or {}, quality_agent),
                        "stage_state": build_ai_studio_stage_state(ai_draft.get("intake") or {}, ai_draft.get("generation") or {}, quality_agent, podcast_doc["id"]),
                        "active_stage": "publish",
                        "updated_at": now_iso(),
                    }
                },
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
    auto_generate_thumbnail: bool = Form(True),
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
    existing_ai_episode = await db.podcasts.find_one(
        {"ai_draft_id": ai_draft["id"], "podcaster_id": user["_id"], "is_deleted": False}
    )
    if existing_ai_episode:
        enriched = await enrich_episodes([existing_ai_episode], current_user=user)
        return enriched[0]

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
    if not thumbnail_path and auto_generate_thumbnail:
        thumbnail_path = store_generated_thumbnail(
            f"episode-thumbnails/{user['_id']}",
            final_title,
            show.get("title", ""),
            normalized_category,
            kind="episode",
        )
    keywords = await extract_keywords(f"{final_title} {final_description} {normalized_category} {show['title']}")
    selected_rating = normalize_content_rating(audience_rating)
    audio_turns = build_ai_audio_turns(show, final_title, ai_draft.get("generation", {}), ai_draft.get("intake", {}))
    audio_script = audio_turns_to_script(audio_turns) or build_ai_audio_script(show, final_title, ai_draft.get("generation", {}))
    rendered_audio = render_ai_audio_bytes(audio_script, audio_turns)
    voice_clarity = analyze_voice_clarity(
        rendered_audio["data"],
        rendered_audio.get("filename") or f"{slugify_filename(final_title)}.{rendered_audio.get('extension') or 'audio'}",
        rendered_audio["content_type"],
        provider=rendered_audio.get("provider", ""),
    )
    media_analysis = build_script_media_analysis(audio_script, f"ai-script:{rendered_audio['provider']}", voice_clarity=voice_clarity)
    moderation = await review_episode_safety(
        show,
        final_title,
        final_description,
        normalized_category,
        selected_rating=selected_rating,
        generation=ai_draft.get("generation"),
        media_analysis=media_analysis,
    )
    voice_context = build_voice_context_from_intake(ai_draft.get("intake") or {}, normalized_category, show)
    quality_agent = evaluate_agent2_quality(
        final_title,
        final_description,
        generation=ai_draft.get("generation"),
        media_analysis=media_analysis,
        source_kind="ai_audio_render",
        voice_context=voice_context,
    )
    enforce_ai_audio_listenability_gate(quality_agent, [thumbnail_path])
    enforce_audioraq_originals_quality_gate(show, final_title, quality_agent, [thumbnail_path])
    moderation = merge_agent2_quality_into_moderation(moderation, quality_agent)
    enforce_episode_moderation_gate(moderation, [thumbnail_path])
    resolved_rating = MATURE_RATING if moderation.get("recommended_age_gate") == MATURE_RATING else selected_rating
    episode_id = str(uuid.uuid4())
    audio_extension = rendered_audio.get("extension") or extension_for_content_type(rendered_audio["content_type"])
    original_filename = f"{slugify_filename(final_title)}.{audio_extension}"
    media_path = f"{APP_NAME}/episodes/{user['_id']}/{episode_id}.{audio_extension}"
    put_object(media_path, rendered_audio["data"], rendered_audio["content_type"])

    podcast_doc = {
        "id": episode_id,
        "show_id": show["id"],
        "show_title": show["title"],
        "title": final_title,
        "description": final_description,
        "category": normalized_category,
        "keywords": keywords,
        "media_path": media_path,
        "media_type": "audio",
        "content_type": rendered_audio["content_type"],
        "original_filename": original_filename,
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
        "source_kind": "ai",
        "file_size": len(rendered_audio["data"]),
        "transcript_status": media_analysis.get("status", ""),
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "is_deleted": False,
        "ai_draft_id": ai_draft["id"],
        "ai_assisted": True,
        "ai_audio_provider": rendered_audio["provider"],
        "ai_audio_provider_kind": rendered_audio.get("provider_kind", ""),
        "ai_audio_model": rendered_audio.get("model", ""),
        "ai_audio_voices": rendered_audio.get("voices", {}),
        "ai_audio_voice_profile": rendered_audio.get("voice_profile", ""),
        "ai_audio_turn_count": rendered_audio.get("turn_count", len(audio_turns)),
        "ai_audio_script": audio_script,
        "ai_audio_turns": audio_turns,
        "ai_voice_disclosure": AI_AUDIO_DISCLOSURE,
        "media_policy": ai_draft.get("media_policy", {}),
        "script_package": ai_draft.get("generation", {}),
    }
    await db.podcasts.insert_one(podcast_doc)
    await db.shows.update_one({"id": show["id"]}, {"$set": {"updated_at": now_iso()}})
    await db.ai_podcast_drafts.update_one(
        {"id": ai_draft["id"]},
        {"$set": {"last_used_at": now_iso(), "updated_at": now_iso(), "generated_episode_id": podcast_doc["id"]}},
    )
    if ai_draft.get("ai_studio_project_id"):
        await db.ai_studio_projects.update_one(
            {"id": ai_draft["ai_studio_project_id"], "podcaster_id": user["_id"]},
            {
                "$set": {
                    "status": "published",
                    "published_episode_id": podcast_doc["id"],
                    "agent2_review": quality_agent,
                    "artifacts": build_ai_studio_artifacts(ai_draft.get("intake") or {}, show, ai_draft.get("generation") or {}, quality_agent),
                    "stage_state": build_ai_studio_stage_state(ai_draft.get("intake") or {}, ai_draft.get("generation") or {}, quality_agent, podcast_doc["id"]),
                    "active_stage": "publish",
                    "updated_at": now_iso(),
                }
            },
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
        query = add_query_clause(query, topic_match_clause(category))
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

    if sort == "recommended":
        recommended_query = add_query_clause(
            query,
            {
                "$or": [
                    {"title": {"$regex": re.escape(snippet), "$options": "i"}}
                    for snippet in CURATED_RECOMMENDED_EPISODE_TITLE_SNIPPETS
                ]
            },
        )
        candidates = await db.podcasts.find(recommended_query).to_list(80)
        ordered = []
        used_ids: Set[str] = set()
        for snippet in CURATED_RECOMMENDED_EPISODE_TITLE_SNIPPETS:
            match = next(
                (
                    episode
                    for episode in candidates
                    if episode.get("id") not in used_ids and snippet.lower() in str(episode.get("title") or "").lower()
                ),
                None,
            )
            if match:
                used_ids.add(match["id"])
                ordered.append(match)
        if limit:
            ordered = ordered[:limit]
        enriched = await enrich_episodes(ordered, current_user=current_user)
        for episode in enriched:
            episode["recommendation_reason"] = "Founder recommended Audioraq Original"
        return {"podcasts": enriched, "total": len(ordered), "page": 1, "pages": 1 if ordered else 0}

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
    show = None
    if podcast.get("show_id"):
        show = await db.shows.find_one({"id": podcast["show_id"], "is_deleted": False})
    if current_user is not None and listener_brief_needs_refresh(podcast.get("listener_brief_cache"), podcast):
        podcast["listener_brief_cache"] = await ensure_listener_brief_cache(podcast, show)
    enriched = await enrich_episodes([podcast], current_user=current_user)
    return enriched[0]


@api_router.post("/podcasts/{podcast_id}/assistant")
async def ask_episode_assistant(podcast_id: str, req: EpisodeAssistantRequest, request: Request):
    current_user = await get_current_user(request)
    question = str(req.question or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="Ask a question first")

    podcast = await db.podcasts.find_one({"id": podcast_id, "is_deleted": False})
    if not podcast:
        raise HTTPException(status_code=404, detail="Episode not found")
    if not can_access_episode(current_user, podcast):
        raise HTTPException(status_code=403, detail="This episode is restricted for your account")

    show = None
    if podcast.get("show_id"):
        show = await db.shows.find_one({"id": podcast["show_id"], "is_deleted": False})
    answer = await answer_episode_question(question, podcast, show)
    answer["question"] = question
    return answer


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
    await record_analytics_event("save", request, user, podcast)
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
    await record_analytics_event("like", request, user, podcast)
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
    await record_analytics_event("rating", request, user, podcast, {"rating": req.rating})
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
    auto_generate_thumbnail: bool = Form(False),
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
    elif auto_generate_thumbnail:
        updates["thumbnail_path"] = store_generated_thumbnail(
            f"episode-thumbnails/{podcast['podcaster_id']}",
            updates["title"],
            show.get("title", ""),
            updates["category"],
            kind="episode",
        )

    await db.podcasts.update_one({"id": podcast_id}, {"$set": updates})
    if thumbnail or auto_generate_thumbnail:
        replacement_thumbnail_path = (updates.get("thumbnail_path") or "").strip()
        if previous_thumbnail_path and previous_thumbnail_path != replacement_thumbnail_path:
            cleanup_storage_paths([previous_thumbnail_path], strict=False)
    await db.shows.update_one({"id": show["id"]}, {"$set": {"updated_at": now_iso()}})
    updated = await db.podcasts.find_one({"id": podcast_id})
    enriched = await enrich_episodes([updated], current_user=user)
    return enriched[0]


@api_router.post("/podcasts/{podcast_id}/thumbnail/generate")
async def generate_podcast_thumbnail(podcast_id: str, request: Request):
    user = await get_current_user(request)
    podcast = await db.podcasts.find_one({"id": podcast_id, "is_deleted": False})
    if not podcast:
        raise HTTPException(status_code=404, detail="Episode not found")
    if podcast["podcaster_id"] != user["_id"] and user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")

    show = None
    if podcast.get("show_id"):
        show = await db.shows.find_one({"id": podcast["show_id"], "is_deleted": False})

    previous_thumbnail_path = (podcast.get("thumbnail_path") or "").strip()
    thumbnail_path = store_generated_thumbnail(
        f"episode-thumbnails/{podcast['podcaster_id']}",
        podcast.get("title", "Audioraq Episode"),
        (show or {}).get("title", podcast.get("show_title", "")),
        podcast.get("category", DEFAULT_SHOW_CATEGORY),
        kind="episode",
    )
    await db.podcasts.update_one({"id": podcast_id}, {"$set": {"thumbnail_path": thumbnail_path, "updated_at": now_iso()}})
    if previous_thumbnail_path and previous_thumbnail_path != thumbnail_path:
        cleanup_storage_paths([previous_thumbnail_path], strict=False)
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

    cleanup_result = cleanup_storage_paths([podcast.get("media_path"), podcast.get("thumbnail_path")], strict=False)
    cleanup_pending = bool(cleanup_result.get("failures"))
    timestamp = now_iso()
    delete_updates = {
        "is_deleted": True,
        "updated_at": timestamp,
        "deleted_at": timestamp,
        "storage_cleanup_pending": cleanup_pending,
        "storage_cleanup_result": cleanup_result,
        "storage_cleanup_last_attempt_at": timestamp,
    }
    if not cleanup_pending:
        delete_updates["storage_cleaned_at"] = timestamp
    await db.podcasts.update_one(
        {"id": podcast_id},
        {"$set": delete_updates},
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
    current_user = await get_current_user(request)
    podcast = await db.podcasts.find_one({"id": podcast_id, "is_deleted": False})
    if not podcast:
        raise HTTPException(status_code=404, detail="Episode not found")
    if not can_access_episode(current_user, podcast):
        raise HTTPException(status_code=403, detail="This episode is restricted for your account")
    if not podcast.get("is_playable", bool(podcast.get("media_path") or podcast.get("external_media_url"))):
        raise HTTPException(status_code=400, detail="This AI-created draft does not have playable media yet")

    range_header = request.headers.get("range")
    should_count_play = should_count_stream_play(range_header)

    if podcast.get("external_media_url"):
        external_media_url = validate_external_redirect_url(podcast["external_media_url"])
        if should_count_play:
            await db.podcasts.update_one({"id": podcast_id}, {"$inc": {"play_count": 1}})
            if podcast.get("show_id"):
                await db.shows.update_one({"id": podcast["show_id"]}, {"$set": {"updated_at": now_iso()}})
            await record_analytics_event("play_started", request, current_user, podcast, {"source": "external_redirect"})
        return RedirectResponse(external_media_url)

    try:
        content_type = podcast.get("content_type") or mimetypes.guess_type(podcast.get("original_filename", ""))[0] or "application/octet-stream"
        filename = podcast.get("original_filename", "podcast")
        if get_storage_backend() == "local":
            response = stream_local_object(podcast["media_path"], content_type, request, filename)
        else:
            response = stream_cached_or_remote_object(podcast["media_path"], content_type, request, filename)

        if should_count_play:
            await db.podcasts.update_one({"id": podcast_id}, {"$inc": {"play_count": 1}})
            if podcast.get("show_id"):
                await db.shows.update_one({"id": podcast["show_id"]}, {"$set": {"updated_at": now_iso()}})
            await record_analytics_event("play_started", request, current_user, podcast, {"source": "media_stream"})
        return response
    except HTTPException:
        raise
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
            return RedirectResponse(validate_external_redirect_url(external_thumbnail_url))
        return generated_thumbnail_response(
            podcast.get("title", "Audioraq Episode"),
            podcast.get("show_title", podcast.get("podcaster_name", "")),
            podcast.get("category", DEFAULT_SHOW_CATEGORY),
            kind="episode",
        )
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
    await record_analytics_event("view_recorded", request, user, podcast)
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
    await record_analytics_event(
        "play_completed" if is_completed else "play_progress",
        request,
        user,
        podcast,
        {"progress_percent": progress_percent, "duration_seconds": duration_seconds},
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
    await record_analytics_event("not_interested", request, user, podcast)
    return {"message": "Episode hidden from recommendations", "podcast_id": podcast_id}


@api_router.delete("/podcasts/{podcast_id}/not-interested")
async def restore_podcast_to_feed(podcast_id: str, request: Request):
    user = await get_current_user(request)
    await db.hidden_podcasts.delete_one({"user_id": user["_id"], "podcast_id": podcast_id})
    return {"message": "Episode restored to recommendations", "podcast_id": podcast_id}


@api_router.get("/recommendations")
async def get_recommendations(request: Request, sort: str = "smart", category: Optional[str] = None):
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
    topic_terms = topic_filter_terms(category)
    if category:
        base_query = add_query_clause(base_query, topic_match_clause(category))
    if hidden_ids:
        base_query = add_query_clause(base_query, {"id": {"$nin": hidden_ids}})

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
        all_terms = list(set(user_interests + viewed_keywords + topic_terms))
        if all_terms:
            ordered = await db.podcasts.find(
                {**base_query, "keywords": {"$in": all_terms}}
            ).sort("play_count", -1).limit(20).to_list(20)
            method = "topic" if category and ordered else "keyword" if ordered else "popular"

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
        if category:
            episode["recommendation_reason"] = f"Recommended under {normalize_topic_name(category)}"
        else:
            episode["recommendation_reason"] = build_recommendation_reason(episode, user_interests, viewed_keywords, method)
    return {"podcasts": enriched, "method": method, "sort": sort, "category": normalize_topic_name(category)}


@api_router.get("/categories")
async def get_categories():
    podcast_categories = await db.podcasts.distinct("category", build_public_episode_query())
    show_categories = await db.shows.distinct("category", {"is_deleted": False})
    cats = sorted(set(CURATED_TOPIC_CATEGORIES) | {c for c in podcast_categories + show_categories if c})
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
allow_origin_regex = None
if cors_origin_setting.strip() == "*":
    if parse_bool(os.environ.get("ALLOW_WILDCARD_CORS"), default=not is_production_env()):
        allow_origin_regex = r"https?://.*"
    else:
        logger.warning("Ignoring wildcard CORS_ORIGINS in production; configure explicit origins instead.")
        cors_origins = []
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
