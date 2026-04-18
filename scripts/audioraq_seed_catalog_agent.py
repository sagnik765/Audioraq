#!/usr/bin/env python3
"""
Audioraq Seed Catalog Agent.

This agent creates transparent Audioraq Originals seed content through the
real "Create with AI" flow. It is intentionally not a fake-review or fake-user
bot. Every account/show it creates is named as an Audioraq Originals property.

Important constraints:
- Create with AI is audio-only on Audioraq. This agent publishes AI-created
  audio episodes only.
- "Single episodes" still need a show container because the production data
  model is show-first. The agent creates one single-episode capsule show per
  single.
- The default plan creates 300 episodes total: 275 across 25 shows plus 25
  single-episode capsule shows. The user's requested 280 show episodes plus
  25 singles would equal 305, so 275 is the default to honor "stop at 300".
- Smaller 125-episode and 65-episode campaigns are available for lower-risk
  proof-of-work seeding. The current default is 65 episodes across 7 shows.
- The default 65-episode publishing mode uses the Create-with-AI draft flow,
  then uploads locally rendered Apple proof-studio audio for the restored
  Aman/Samantha reference voice family.
"""

from __future__ import annotations

import argparse
from array import array
import json
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
import tempfile
import wave

import requests


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "qa" / "audioraq-seed-catalog-agent"
DEFAULT_BASE_URL = "https://www.audioraq.com"
DEFAULT_PUBLIC_ORIGIN = "https://www.audioraq.com"
DEFAULT_PASSWORD_PREFIX = "AudioraqSeed"
SHOW_EPISODE_COUNTS_275 = [17, 15, 14, 14, 13, 13, 12, 12, 12, 11, 11, 11, 11, 10, 10, 10, 10, 9, 9, 9, 9, 9, 8, 8, 8]
SHOW_EPISODE_COUNTS_125 = [12, 11, 11, 11, 10, 10, 10, 10, 10, 10, 10, 10]
SHOW_EPISODE_COUNTS_65 = [10, 10, 9, 9, 9, 9, 9]
PROOF_STUDIO_APPLE_GAP_SECONDS = 0.22
PROOF_STUDIO_APPLE_TARGET_PEAK_DBFS = -4.5
PROOF_STUDIO_APPLE_RATES = {
    "host": 142,
    "guest": 140,
    "narrator": 136,
}
PROOF_STUDIO_APPLE_VOICES = {
    "host": ["Aman", "Daniel", "Alex"],
    "guest": ["Samantha", "Ava", "Victoria"],
    "narrator": ["Daniel", "Oliver", "Fred"],
}


@dataclass(frozen=True)
class ShowBlueprint:
    title: str
    category: str
    niche: str
    target_audience: str
    tone: str
    format: str
    length_band: str
    episode_goal: str
    optimize_for: str
    themes: List[str]


@dataclass(frozen=True)
class EpisodeBlueprint:
    global_index: int
    account_kind: str
    show_index: int
    episode_index: int
    show_title: str
    show_description: str
    category: str
    niche: str
    target_audience: str
    topic: str
    key_points: List[str]
    references: List[str]
    tone: str
    format: str
    length_band: str
    length_preference: str
    episode_goal: str
    desired_outcome: str
    optimize_for: str
    speaker_plan: str
    requested_media_kind: str
    publish_lane: str


SHOWS: List[ShowBlueprint] = [
    ShowBlueprint("Audioraq Finance Field Notes", "finance", "personal finance and markets", "young professionals and first-time investors", "professional", "interview", "short", "educate", "clarity", ["emergency funds", "interest rates", "index funds", "credit scores", "tax planning", "financial scams"]),
    ShowBlueprint("The Plain-English Law Desk", "law", "law and civic rights", "non-lawyers who want practical legal literacy", "professional", "interview", "moderate", "educate", "clarity", ["contracts", "consumer rights", "privacy", "employment law", "creator rights", "AI regulation"]),
    ShowBlueprint("Climate Signals", "environment", "climate and environment", "listeners who want solutions without doomscrolling", "storytelling", "narrative", "moderate", "storytelling", "retention", ["heat waves", "water scarcity", "climate adaptation", "clean energy", "plastic policy", "urban trees"]),
    ShowBlueprint("Emerging Market Brief", "emerging markets", "emerging markets and global business", "founders and operators watching growth markets", "professional", "interview", "long", "educate", "clarity", ["India growth", "ASEAN supply chains", "African fintech", "LatAm startups", "currency risk", "infrastructure"]),
    ShowBlueprint("Tomorrow Stack", "technology", "upcoming technologies", "builders and product-minded listeners", "energetic", "interview", "short", "educate", "virality", ["AI agents", "spatial computing", "battery tech", "robotics", "quantum", "privacy tech"]),
    ShowBlueprint("Current Affairs With Context", "current affairs", "news context and explainers", "busy listeners who need grounded context", "professional", "interview", "moderate", "educate", "clarity", ["elections", "trade policy", "media literacy", "geopolitics", "public finance", "internet policy"]),
    ShowBlueprint("Cosmic Common Sense", "astrophysics", "astrophysics and space science", "curious non-scientists", "storytelling", "narrative", "short", "storytelling", "retention", ["black holes", "dark matter", "exoplanets", "JWST", "space weather", "time dilation"]),
    ShowBlueprint("The Body Maintenance Manual", "physical health", "physical health and longevity", "listeners building sustainable health habits", "professional", "interview", "moderate", "educate", "clarity", ["strength training", "sleep", "mobility", "metabolic health", "recovery", "nutrition myths"]),
    ShowBlueprint("Mind Care Lab", "mental health", "mental health and self-regulation", "listeners managing stress and attention", "casual", "interview", "short", "educate", "retention", ["anxiety tools", "burnout", "journaling", "attention", "grief", "digital boundaries"]),
    ShowBlueprint("Scam Radar", "technology", "digital trust and scams", "families and professionals who want to spot fraud", "energetic", "interview", "short", "educate", "virality", ["deepfakes", "OTP scams", "romance scams", "phishing", "investment fraud", "identity theft"]),
    ShowBlueprint("Creator Ops Weekly", "creator economy", "creator operations and media business", "independent creators and small media teams", "casual", "interview", "moderate", "educate", "retention", ["show notes", "clips", "creator analytics", "newsletter funnels", "sponsorships", "community"]),
    ShowBlueprint("Startup Operator Notes", "business", "startup operations", "early-stage founders and operators", "professional", "interview", "long", "educate", "clarity", ["pricing", "customer interviews", "retention", "hiring", "fundraising", "enterprise sales"]),
    ShowBlueprint("Career Switchboard", "careers", "career transitions and workplace strategy", "professionals planning a next move", "casual", "interview", "short", "educate", "retention", ["resumes", "networking", "AI at work", "negotiation", "portfolio careers", "burnout"]),
    ShowBlueprint("Parenting In The Algorithm Age", "parenting", "parenting and technology", "parents navigating phones, school, and identity", "storytelling", "interview", "moderate", "storytelling", "retention", ["screen time", "teen privacy", "AI homework", "online safety", "sleep", "attention"]),
    ShowBlueprint("Sports Strategy Room", "sports", "sports business and performance", "fans who like strategy beyond highlights", "energetic", "interview", "short", "entertain", "virality", ["football analytics", "cricket leagues", "fan culture", "sports betting risk", "training loads", "media rights"]),
    ShowBlueprint("Food Systems Future", "environment", "food, agriculture, and sustainability", "curious eaters and climate-minded professionals", "professional", "narrative", "moderate", "educate", "clarity", ["regenerative farming", "supply chains", "food waste", "protein alternatives", "water", "soil health"]),
    ShowBlueprint("Policy Without Panic", "public policy", "public policy explainers", "listeners who want calm policy context", "professional", "interview", "long", "educate", "clarity", ["housing", "taxes", "public health", "education", "transport", "AI policy"]),
    ShowBlueprint("Culture Decoder", "culture", "internet culture and social trends", "listeners who want smart cultural analysis", "storytelling", "narrative", "short", "entertain", "retention", ["fandoms", "memes", "parasociality", "creator drama", "music trends", "streaming"]),
    ShowBlueprint("Language Of Money", "finance", "financial literacy for beginners", "students and new earners", "casual", "interview", "short", "educate", "clarity", ["budgeting", "insurance", "compound interest", "debt traps", "UPI habits", "first salary"]),
    ShowBlueprint("Ethics Of AI", "technology", "AI safety and ethics", "builders, students, and policy-curious listeners", "professional", "interview", "long", "educate", "clarity", ["bias", "deepfake disclosure", "AI labor", "data rights", "model evaluations", "synthetic media"]),
    ShowBlueprint("Cities That Work", "urbanism", "urban design and civic systems", "city dwellers and local builders", "storytelling", "narrative", "moderate", "storytelling", "retention", ["public transport", "walkability", "waste", "air quality", "housing", "public space"]),
    ShowBlueprint("Sleep, Stress, Repeat", "mental health", "sleep and stress", "busy professionals rebuilding routines", "casual", "interview", "short", "educate", "retention", ["circadian rhythm", "night anxiety", "caffeine", "shift work", "wind-down routines", "naps"]),
    ShowBlueprint("Deep Space Coffee", "astrophysics", "space science and philosophy", "curious lifelong learners", "storytelling", "interview", "moderate", "storytelling", "retention", ["cosmic scale", "Mars", "asteroids", "SETI", "space telescopes", "origin stories"]),
    ShowBlueprint("India Growth Lab", "emerging markets", "India, policy, and startup growth", "founders tracking India's next decade", "professional", "interview", "long", "educate", "clarity", ["DPI", "manufacturing", "EVs", "semiconductors", "rural markets", "financial inclusion"]),
    ShowBlueprint("The Better Questions Show", "education", "learning and decision-making", "curious listeners who want sharper thinking", "casual", "interview", "short", "educate", "retention", ["critical thinking", "learning science", "decision journals", "expert interviews", "curiosity", "attention"]),
]


SHOWS_125_TRENDING: List[ShowBlueprint] = [
    ShowBlueprint("Tariff Desk", "finance", "trade, tariffs, and market risk", "founders, CFOs, operators, and investors watching global trade", "professional", "interview", "short", "educate", "clarity", ["tariff playbooks", "FX hedging", "supply chains", "friendshoring", "commodity shocks", "inflation pass-through"]),
    ShowBlueprint("The Reg Stack", "law", "AI regulation, privacy, consumer protection, and creator rights", "in-house counsel, founders, compliance teams, and policy-curious listeners", "professional", "interview", "moderate", "educate", "clarity", ["AI liability", "deepfake privacy", "workplace AI", "creator rights", "consumer fraud", "antitrust"]),
    ShowBlueprint("Adaptation Ledger", "environment", "climate adaptation as finance and infrastructure", "investors, planners, builders, and public-sector operators", "storytelling", "narrative", "moderate", "storytelling", "retention", ["heat insurance", "water scarcity", "flood finance", "grid hardening", "climate migration", "resilient housing"]),
    ShowBlueprint("Frontier Markets Now", "emerging markets", "where growth is compounding outside the US and Europe", "operators, VCs, exporters, and policy watchers", "professional", "interview", "long", "educate", "clarity", ["India manufacturing", "Nigeria fintech", "Vietnam supply chains", "Brazil agri-tech", "Gulf capital", "Africa mobile money"]),
    ShowBlueprint("Agentic Era", "technology", "AI agents, robotics, spatial computing, and workflow automation", "builders, operators, and early adopters", "energetic", "interview", "short", "educate", "virality", ["AI agents at work", "robotics reality checks", "on-device AI", "workflow orchestration", "spatial computing", "model governance"]),
    ShowBlueprint("The Briefing Room", "current affairs", "calm explainers on the week's biggest events", "busy listeners who want context without panic", "professional", "interview", "moderate", "educate", "clarity", ["tariff diplomacy", "misinformation", "sanctions", "election aftershocks", "migration", "cyber incidents"]),
    ShowBlueprint("Cosmos Next", "astrophysics", "near-term space missions and big cosmic questions", "curious generalists, STEM fans, and educators", "storytelling", "narrative", "short", "storytelling", "retention", ["Roman telescope", "exoplanet atmospheres", "cosmic dawn", "dark matter", "astrobiology", "citizen science"]),
    ShowBlueprint("The Movement Dividend", "physical health", "evidence-based health habits for real life", "desk workers, founders, and fitness-curious listeners", "professional", "interview", "moderate", "educate", "clarity", ["sedentary work", "strength after 40", "sleep and recovery", "zone 2 myths", "mobility", "habit design"]),
    ShowBlueprint("Nervous System Nation", "mental health", "stress, burnout, attention, and practical self-regulation", "professionals, caregivers, parents, and managers", "casual", "interview", "short", "educate", "retention", ["burnout", "teen anxiety", "digital overload", "grief", "men's mental health", "stress resets"]),
    ShowBlueprint("Scam School", "finance", "fraud, impersonation, and digital trust", "consumers, small businesses, and compliance teams", "energetic", "interview", "short", "educate", "virality", ["invoice fraud", "romance scams", "crypto fraud", "AI impersonation", "payroll theft", "consumer recovery"]),
    ShowBlueprint("The Audience Shift", "creator economy", "how podcasts grow across video, clips, and community", "creators, media teams, and brands", "casual", "interview", "moderate", "educate", "retention", ["clips to full episodes", "titles that convert", "transcript SEO", "newsletter loops", "sponsor packaging", "chapter strategy"]),
    ShowBlueprint("Binge Nation", "culture", "why sports, true crime, comedy, and fandom shows become habits", "mainstream listeners and fandom-heavy audiences", "energetic", "interview", "short", "entertain", "virality", ["sports second screens", "true-crime ethics", "comedy room dynamics", "fandom wars", "recap formats", "meme cycles"]),
]
SHOWS_65_TRENDING: List[ShowBlueprint] = SHOWS_125_TRENDING[:7]


SINGLE_TOPICS = [
    ("finance", "Why emergency funds feel boring until they become freedom"),
    ("law", "The one contract clause creators skip too often"),
    ("environment", "What urban heat islands teach us about climate adaptation"),
    ("emerging markets", "Why payment infrastructure changes how small businesses grow"),
    ("technology", "The practical difference between AI assistants and AI agents"),
    ("current affairs", "How to read a breaking-news story without getting manipulated"),
    ("astrophysics", "What dark matter is, and why scientists still care"),
    ("physical health", "The minimum effective dose for strength training"),
    ("mental health", "A practical reset for Sunday-night anxiety"),
    ("business", "How to price a new product without copying competitors"),
    ("creator economy", "What makes a podcast clip worth sharing"),
    ("culture", "Why fandoms behave like informal media companies"),
    ("urbanism", "Why walkable streets change local economies"),
    ("parenting", "How parents can talk about AI homework without panic"),
    ("sports", "What sports analytics can and cannot explain"),
    ("education", "Why spaced repetition beats last-minute studying"),
    ("public policy", "How housing supply becomes a mental health issue"),
    ("food systems", "Why food waste is a climate problem you can actually picture"),
    ("digital trust", "How to verify a voice note in the age of deepfakes"),
    ("AI ethics", "What AI disclosure should look like in everyday media"),
    ("careers", "How to build career optionality without quitting tomorrow"),
    ("space science", "What exoplanets teach us about scientific patience"),
    ("longevity", "Why recovery is part of training, not a break from it"),
    ("marketing", "The difference between a launch and a campaign"),
    ("personal growth", "How to turn one useful idea into a weekly ritual"),
]


def timestamp() -> str:
    return time.strftime("%Y%m%d-%H%M%S", time.gmtime())


def api_post(session: requests.Session, url: str, token: str = "", timeout_seconds: int = 360, **kwargs: Any) -> requests.Response:
    headers = kwargs.pop("headers", {})
    if token:
        headers["Authorization"] = f"Bearer {token}"
    response = session.post(url, headers=headers, timeout=timeout_seconds, **kwargs)
    if response.status_code >= 400:
        raise RuntimeError(f"{response.status_code} from {url}: {response.text[:1000]}")
    return response


def api_get(session: requests.Session, url: str, token: str = "", **kwargs: Any) -> requests.Response:
    headers = kwargs.pop("headers", {})
    if token:
        headers["Authorization"] = f"Bearer {token}"
    response = session.get(url, headers=headers, timeout=120, **kwargs)
    if response.status_code >= 400:
        raise RuntimeError(f"{response.status_code} from {url}: {response.text[:1000]}")
    return response


def run(cmd: List[str], **kwargs: Any) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=True, text=True, **kwargs)


def require_tool(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise RuntimeError(f"Required tool not found: {name}")
    return path


def slugify(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower())
    return value.strip("-")[:90] or "episode"


def normalize_length_preference(length_band: str) -> str:
    if length_band == "short":
        return "short"
    if length_band == "moderate":
        return "medium"
    return "long"


def show_description(show: ShowBlueprint) -> str:
    return (
        f"Audioraq Originals seed show about {show.niche}. "
        "This transparent proof-of-work catalog demonstrates Audioraq's AI-assisted, show-first podcast workflow."
    )


def build_episode_topic(show: ShowBlueprint, episode_number: int) -> str:
    theme = show.themes[(episode_number - 1) % len(show.themes)]
    pattern = [
        "The practical beginner's guide to {theme}",
        "What most listeners misunderstand about {theme}",
        "A decision framework for {theme}",
        "The hidden tradeoffs inside {theme}",
        "How {theme} changes behavior in the real world",
        "A calm explainer on {theme}",
        "The one question to ask before acting on {theme}",
    ][(episode_number - 1) % 7]
    return pattern.format(theme=theme)


def normalize_voice_role(speaker: str, voice_role: str = "") -> str:
    speaker_key = (speaker or "").strip().lower()
    role_key = (voice_role or "").strip().lower()
    if speaker_key in {"co-host", "cohost", "guest", "expert guest"} or role_key == "guest":
        return "guest"
    if speaker_key == "narrator" or role_key == "narrator":
        return "narrator"
    return "host"


def normalize_tts_text(text: str) -> str:
    text = " ".join(str(text or "").split())
    text = text.replace(" - ", ", ")
    if text and text[-1] not in ".!?":
        text = f"{text}."
    return text


def normalize_audio_turns(items: Any) -> List[Dict[str, str]]:
    turns = []
    if isinstance(items, list):
        for item in items:
            if not isinstance(item, dict):
                continue
            text = normalize_tts_text(str(item.get("text") or ""))
            if not text:
                continue
            speaker = str(item.get("speaker") or item.get("name") or "Host").strip() or "Host"
            voice_role = normalize_voice_role(speaker, str(item.get("voice_role") or item.get("voiceRole") or ""))
            turns.append({"speaker": speaker, "voice_role": voice_role, "text": text})
    return turns


def fallback_audio_turns(plan: EpisodeBlueprint, title: str, generation: Dict[str, Any]) -> List[Dict[str, str]]:
    hook = generation.get("hook") or f"Today on {plan.show_title}, we are unpacking {title}."
    promise = generation.get("one_line_promise") or plan.desired_outcome
    turns = [
        {"speaker": "Host", "voice_role": "host", "text": hook},
        {
            "speaker": "Co-host" if plan.format == "interview" else "Narrator",
            "voice_role": "guest" if plan.format == "interview" else "narrator",
            "text": f"The useful promise is simple: {promise}",
        },
    ]
    for index, point in enumerate(plan.key_points[:6], start=1):
        if plan.format == "solo":
            turns.append({"speaker": "Host", "voice_role": "host", "text": point})
        else:
            speaker = "Host" if index % 2 else "Co-host"
            turns.append({"speaker": speaker, "voice_role": normalize_voice_role(speaker), "text": point})
    turns.append(
        {
            "speaker": "Host",
            "voice_role": "host",
            "text": f"The closing takeaway: {plan.desired_outcome}. This is an Audioraq Originals episode made with Audioraq's AI-assisted workflow.",
        }
    )
    return turns


def audio_turns_from_generation(plan: EpisodeBlueprint, title: str, generation: Dict[str, Any]) -> List[Dict[str, str]]:
    turns = normalize_audio_turns(generation.get("audio_script_turns") or generation.get("audioScriptTurns"))
    if turns:
        return turns
    return fallback_audio_turns(plan, title, generation)


def synthesize_turn_audio(text: str, output_wav: Path, voices: List[str], rate_wpm: int) -> str:
    require_tool("say")
    require_tool("afconvert")
    text_file = output_wav.with_suffix(".txt")
    text_file.write_text(normalize_tts_text(text), encoding="utf-8")
    last_error: Optional[Exception] = None
    min_duration = 0.16 if len(text.split()) <= 3 else 0.35
    for attempt, selected_voice in enumerate(dict.fromkeys(voices + ["Aman", "Samantha", "Daniel", "Alex"]), start=1):
        tmp_aiff = output_wav.with_suffix(f".{attempt}.aiff")
        try:
            run(["say", "-v", selected_voice, "-r", str(rate_wpm), "-o", str(tmp_aiff), "-f", str(text_file)])
            run(["afconvert", "-f", "WAVE", "-d", "LEI16", str(tmp_aiff), str(output_wav)])
            with wave.open(str(output_wav), "rb") as wav_file:
                duration = wav_file.getnframes() / max(1, wav_file.getframerate())
            if duration >= min_duration:
                return selected_voice
            last_error = RuntimeError(f"Generated short turn with voice {selected_voice}: {duration:.2f}s")
        except Exception as exc:
            last_error = exc
        finally:
            tmp_aiff.unlink(missing_ok=True)
    raise RuntimeError(f"Could not synthesize dialogue turn: {last_error}")


def concat_wavs(segment_paths: List[Path], output_wav: Path, gap_seconds: float = PROOF_STUDIO_APPLE_GAP_SECONDS) -> None:
    if not segment_paths:
        raise RuntimeError("No dialogue segments to concatenate")
    with wave.open(str(segment_paths[0]), "rb") as first:
        params = first.getparams()
        framerate = first.getframerate()
        sample_width = first.getsampwidth()
        channels = first.getnchannels()
    silence = b"\x00" * int(framerate * gap_seconds) * sample_width * channels
    with wave.open(str(output_wav), "wb") as out:
        out.setparams(params)
        for segment_path in segment_paths:
            with wave.open(str(segment_path), "rb") as segment:
                if segment.getframerate() != framerate or segment.getsampwidth() != sample_width or segment.getnchannels() != channels:
                    raise RuntimeError(f"Dialogue segment format mismatch: {segment_path}")
                out.writeframes(segment.readframes(segment.getnframes()))
                out.writeframes(silence)


def master_wav_headroom(path: Path, target_peak_dbfs: float = PROOF_STUDIO_APPLE_TARGET_PEAK_DBFS) -> Dict[str, Any]:
    """Apply transparent peak gain so proof-studio renders are comfortable over long sessions."""
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
        "peak_before": round(20 * math_log10(max_abs / full_scale), 2),
        "peak_after": round(20 * math_log10(max(1, peak_after) / full_scale), 2),
    }


def math_log10(value: float) -> float:
    import math

    return math.log10(max(value, 0.0000001))


def render_apple_say_audio(turns: List[Dict[str, str]], output_wav: Path) -> Dict[str, Any]:
    selected_voices: Dict[str, str] = {}
    with tempfile.TemporaryDirectory(prefix="audioraq-originals-dialogue-") as temp_dir:
        temp_path = Path(temp_dir)
        segments = []
        for index, turn in enumerate(turns, start=1):
            role = normalize_voice_role(turn.get("speaker", ""), turn.get("voice_role", ""))
            segment = temp_path / f"{index:03d}-{role}.wav"
            selected_voice = synthesize_turn_audio(
                turn["text"],
                segment,
                PROOF_STUDIO_APPLE_VOICES.get(role, PROOF_STUDIO_APPLE_VOICES["host"]),
                PROOF_STUDIO_APPLE_RATES.get(role, PROOF_STUDIO_APPLE_RATES["host"]),
            )
            selected_voices.setdefault(role, selected_voice)
            segments.append(segment)
        concat_wavs(segments, output_wav)
    mastering = master_wav_headroom(output_wav)
    return {
        "provider": "apple-say:proof-studio",
        "provider_kind": "local-proof",
        "voices": selected_voices,
        "turn_count": len(turns),
        "rates_wpm": PROOF_STUDIO_APPLE_RATES,
        "mastering": mastering,
    }


def speaker_plan_for(index: int, base_format: str) -> str:
    if base_format == "solo":
        return "one host"
    if base_format == "narrative":
        return "host plus narrator" if index % 2 else "narrator-led story with host wrap"
    return "host plus guest" if index % 3 else "host, co-host, and expert guest"


def build_key_points(show: ShowBlueprint, topic: str, episode_number: int) -> List[str]:
    theme = show.themes[(episode_number - 1) % len(show.themes)]
    return [
        f"Define {theme} in plain language before giving advice",
        f"Use one real-world scenario that makes {topic.lower()} concrete",
        "Name the tradeoff or limitation so the episode does not sound like hype",
        "End with one action listeners can try this week",
    ]


def build_episode_plan(
    global_index: int,
    show: ShowBlueprint,
    show_index: int,
    episode_number: int,
    account_kind: str,
) -> EpisodeBlueprint:
    topic = build_episode_topic(show, episode_number)
    length_preference = normalize_length_preference(show.length_band)
    requested_media_kind = "audio" if global_index % 4 else "video_ready_audio"
    return EpisodeBlueprint(
        global_index=global_index,
        account_kind=account_kind,
        show_index=show_index,
        episode_index=episode_number,
        show_title=show.title,
        show_description=show_description(show),
        category=show.category,
        niche=show.niche,
        target_audience=show.target_audience,
        topic=topic,
        key_points=build_key_points(show, topic, episode_number),
        references=["Audioraq Originals editorial brief", "Agent 2 topic strategy memo"],
        tone=show.tone,
        format=show.format,
        length_band=show.length_band,
        length_preference=length_preference,
        episode_goal=show.episode_goal,
        desired_outcome=f"leave with a practical way to understand and act on {topic.lower()}",
        optimize_for=show.optimize_for,
        speaker_plan=speaker_plan_for(global_index, show.format),
        requested_media_kind=requested_media_kind,
        publish_lane="create_with_ai_audio",
    )


def build_single_plan(global_index: int, single_index: int, category: str, topic: str) -> EpisodeBlueprint:
    title = f"Audioraq Singles {single_index:02d}: {category.title()}"
    length_band = ["short", "moderate", "long"][single_index % 3]
    format_name = ["solo", "interview", "narrative"][single_index % 3]
    return EpisodeBlueprint(
        global_index=global_index,
        account_kind="single",
        show_index=single_index,
        episode_index=1,
        show_title=title,
        show_description=(
            f"Audioraq Originals single-episode capsule on {category}. "
            "This transparent proof-of-work account exists to demonstrate one focused AI-assisted episode."
        ),
        category=category,
        niche=f"{category} explainers",
        target_audience="curious listeners discovering Audioraq's proof-of-work catalog",
        topic=topic,
        key_points=[
            "Start with a concrete listener problem",
            "Explain the concept without jargon",
            "Use one example or scenario",
            "Close with a memorable next step",
        ],
        references=["Audioraq Originals editorial brief", "Agent 2 topic strategy memo"],
        tone=["professional", "casual", "storytelling"][single_index % 3],
        format=format_name,
        length_band=length_band,
        length_preference=normalize_length_preference(length_band),
        episode_goal="educate" if single_index % 4 else "storytelling",
        desired_outcome=f"understand {topic.lower()} well enough to explain it to a friend",
        optimize_for="clarity" if single_index % 2 else "retention",
        speaker_plan=speaker_plan_for(global_index, format_name),
        requested_media_kind="audio",
        publish_lane="create_with_ai_audio",
    )


def build_catalog_plan(target_total: int = 300, single_count: int = 25) -> List[EpisodeBlueprint]:
    if len(SHOWS) != 25:
        raise RuntimeError("The seed catalog requires exactly 25 show blueprints")
    if target_total == 300 and single_count == 25:
        selected_shows = SHOWS
        show_episode_counts = SHOW_EPISODE_COUNTS_275
    elif target_total == 125 and single_count == 0:
        selected_shows = SHOWS_125_TRENDING
        show_episode_counts = SHOW_EPISODE_COUNTS_125
    elif target_total == 65 and single_count == 0:
        selected_shows = SHOWS_65_TRENDING
        show_episode_counts = SHOW_EPISODE_COUNTS_65
    else:
        raise RuntimeError("Supported seed plans are 300 total with 25 singles, 125 total with 0 singles, or 65 total with 0 singles")
    show_episode_total = target_total - single_count
    if sum(show_episode_counts) != show_episode_total:
        raise RuntimeError(f"Expected {show_episode_total} show episodes, got {sum(show_episode_counts)}")
    plans: List[EpisodeBlueprint] = []
    global_index = 1
    for show_index, (show, episode_count) in enumerate(zip(selected_shows, show_episode_counts), start=1):
        for episode_number in range(1, episode_count + 1):
            plans.append(build_episode_plan(global_index, show, show_index, episode_number, "show"))
            global_index += 1
    for single_index, (category, topic) in enumerate(SINGLE_TOPICS[:single_count], start=1):
        plans.append(build_single_plan(global_index, single_index, category, topic))
        global_index += 1
    if len(plans) != target_total:
        raise RuntimeError(f"Expected {target_total} planned episodes, got {len(plans)}")
    return plans


def build_intake(plan: EpisodeBlueprint) -> Dict[str, Any]:
    known_issues = (
        f"Transparent Audioraq Originals seed content. Target length band: {plan.length_band}. "
        f"Speaker plan: {plan.speaker_plan}. Do not imitate real people or claim to be a human-recorded guest."
    )
    return {
        "identity": {
            "podcastName": plan.show_title,
            "niche": plan.niche,
            "targetAudience": plan.target_audience,
        },
        "episodeIntent": {
            "episodeGoal": plan.episode_goal,
            "desiredOutcome": plan.desired_outcome,
        },
        "contentInput": {
            "topic": plan.topic,
            "keyPoints": plan.key_points,
            "references": plan.references,
        },
        "toneStyle": {
            "tone": plan.tone,
            "format": plan.format,
            "lengthPreference": plan.length_preference,
        },
        "growthOptimization": {
            "optimizeFor": plan.optimize_for,
            "includeHook": True,
            "knownIssues": known_issues,
        },
    }


def create_account(session: requests.Session, base_url: str, email: str, password: str, plan: EpisodeBlueprint) -> Dict[str, Any]:
    payload = {
        "email": email,
        "password": password,
        "name": f"Audioraq Originals {plan.show_index:02d}",
        "role": "podcaster",
        "phone": "",
        "age": 25,
        "podcast_description": plan.show_description,
        "show_title": plan.show_title,
    }
    return api_post(session, f"{base_url}/api/auth/register", json=payload).json()


def login_account(session: requests.Session, base_url: str, email: str, password: str) -> Dict[str, Any]:
    return api_post(session, f"{base_url}/api/auth/login", json={"email": email, "password": password}).json()


def get_token_and_show_id(
    session: requests.Session,
    base_url: str,
    email: str,
    password: str,
    plan: EpisodeBlueprint,
) -> Dict[str, str]:
    try:
        auth = create_account(session, base_url, email, password, plan)
    except RuntimeError as exc:
        if "Email already registered" not in str(exc):
            raise
        auth = login_account(session, base_url, email, password)

    token = auth["access_token"]
    show_id = (auth.get("primary_show") or {}).get("id", "")
    if not show_id:
        shows = session.get(f"{base_url}/api/shows/my", headers={"Authorization": f"Bearer {token}"}, timeout=60).json()
        if shows.get("shows"):
            show_id = shows["shows"][0]["id"]
    if not show_id:
        raise RuntimeError(f"No show_id returned for {email}")
    return {"token": token, "show_id": show_id}


def create_ai_episode(
    session: requests.Session,
    base_url: str,
    public_origin: str,
    token: str,
    show_id: str,
    plan: EpisodeBlueprint,
    publish_mode: str,
    media_dir: Path,
) -> Dict[str, Any]:
    draft = api_post(
        session,
        f"{base_url}/api/ai-podcast-drafts/generate",
        token=token,
        json={"show_id": show_id, "intake": build_intake(plan)},
    ).json()

    title = draft.get("publish_prefill", {}).get("title") or draft.get("generation", {}).get("episode_title") or plan.topic
    if not title.lower().startswith("audioraq originals"):
        title = f"Audioraq Originals: {title}"
    description = draft.get("publish_prefill", {}).get("description") or draft.get("generation", {}).get("suggested_description") or ""
    description = (
        f"{description}\n\n"
        "Disclosure: this is transparent Audioraq Originals proof-of-work content created with Audioraq's AI-assisted workflow."
    ).strip()

    if publish_mode == "apple-say-upload":
        media_dir.mkdir(parents=True, exist_ok=True)
        turns = audio_turns_from_generation(plan, title, draft.get("generation") or {})
        audio_path = media_dir / f"{plan.global_index:03d}-{slugify(title)}.wav"
        render_metadata = render_apple_say_audio(turns, audio_path)
        with audio_path.open("rb") as media_file:
            episode = api_post(
                session,
                f"{base_url}/api/podcasts/upload",
                token=token,
                files={"file": (audio_path.name, media_file, "audio/wav")},
                timeout_seconds=900,
                data={
                    "show_id": show_id,
                    "ai_draft_id": draft["id"],
                    "ai_audio_provider": render_metadata["provider"],
                    "ai_audio_provider_kind": render_metadata["provider_kind"],
                    "ai_audio_voice_profile": "apple_proof_studio",
                    "title": title,
                    "description": description,
                    "category": plan.category,
                    "audience_rating": "all_ages",
                    "season_number": "1",
                    "episode_number": str(plan.episode_index),
                },
            ).json()
        return {
            "draft_id": draft.get("id", ""),
            "episode_id": episode.get("id", ""),
            "episode_url": f"{public_origin}/episodes/{episode.get('id')}" if episode.get("id") else "",
            "title": episode.get("title", title),
            "show_id": show_id,
            "moderation_status": episode.get("moderation_status", ""),
            "quality_status": episode.get("quality_status", ""),
            "quality_score": episode.get("quality_score", 0),
            "media_type": episode.get("media_type", ""),
            "content_type": episode.get("content_type", ""),
            "ai_audio_provider": render_metadata["provider"],
            "ai_audio_provider_kind": render_metadata["provider_kind"],
            "ai_audio_turn_count": render_metadata["turn_count"],
            "ai_audio_voices": render_metadata["voices"],
            "local_media_path": str(audio_path),
            "is_playable": episode.get("is_playable", False),
        }

    episode = api_post(
        session,
        f"{base_url}/api/podcasts/ai-create",
        token=token,
        data={
            "show_id": show_id,
            "ai_draft_id": draft["id"],
            "title": title,
            "description": description,
            "category": plan.category,
            "audience_rating": "all_ages",
            "season_number": "1",
            "episode_number": str(plan.episode_index),
        },
    ).json()

    return {
        "draft_id": draft.get("id", ""),
        "episode_id": episode.get("id", ""),
        "episode_url": f"{public_origin}/episodes/{episode.get('id')}" if episode.get("id") else "",
        "title": episode.get("title", title),
        "show_id": show_id,
        "moderation_status": episode.get("moderation_status", ""),
        "quality_status": episode.get("quality_status", ""),
        "quality_score": episode.get("quality_score", 0),
        "media_type": episode.get("media_type", ""),
        "content_type": episode.get("content_type", ""),
        "ai_audio_provider": episode.get("ai_audio_provider", ""),
        "ai_audio_provider_kind": episode.get("ai_audio_provider_kind", ""),
        "ai_audio_turn_count": episode.get("ai_audio_turn_count", 0),
        "is_playable": episode.get("is_playable", False),
    }


def find_existing_episode(
    session: requests.Session,
    base_url: str,
    public_origin: str,
    token: str,
    show_id: str,
    plan: EpisodeBlueprint,
) -> Optional[Dict[str, Any]]:
    body = api_get(session, f"{base_url}/api/podcasts/my?show_id={show_id}", token=token).json()
    for episode in body.get("podcasts", []):
        if int(episode.get("season_number") or 0) != 1:
            continue
        if int(episode.get("episode_number") or 0) != plan.episode_index:
            continue
        if not str(episode.get("title") or "").lower().startswith("audioraq originals"):
            continue
        return {
            "draft_id": episode.get("ai_draft_id", ""),
            "episode_id": episode.get("id", ""),
            "episode_url": f"{public_origin}/episodes/{episode.get('id')}" if episode.get("id") else "",
            "title": episode.get("title", plan.topic),
            "show_id": show_id,
            "moderation_status": episode.get("moderation_status", ""),
            "quality_status": episode.get("quality_status", ""),
            "quality_score": episode.get("quality_score", 0),
            "media_type": episode.get("media_type", ""),
            "content_type": episode.get("content_type", ""),
            "ai_audio_provider": episode.get("ai_audio_provider", ""),
            "ai_audio_provider_kind": episode.get("ai_audio_provider_kind", ""),
            "ai_audio_turn_count": episode.get("ai_audio_turn_count", 0),
            "is_playable": episode.get("is_playable", False),
        }
    return None


def quality_failure_reason(result: Dict[str, Any], min_quality_score: float, require_moderation: str, require_quality_status: str) -> str:
    if require_moderation and (result.get("moderation_status") or "").lower() != require_moderation.lower():
        return f"moderation_status={result.get('moderation_status') or 'unknown'}"
    allowed_statuses = {part.strip().lower() for part in require_quality_status.split(",") if part.strip()}
    if allowed_statuses and (result.get("quality_status") or "").lower() not in allowed_statuses:
        return f"quality_status={result.get('quality_status') or 'unknown'}"
    if min_quality_score and float(result.get("quality_score") or 0) < min_quality_score:
        return f"quality_score={result.get('quality_score') or 0} below {min_quality_score}"
    return ""


def delete_episode(session: requests.Session, base_url: str, token: str, episode_id: str) -> Dict[str, Any]:
    response = session.delete(
        f"{base_url}/api/podcasts/{episode_id}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=120,
    )
    if response.status_code >= 400:
        raise RuntimeError(f"{response.status_code} from delete {episode_id}: {response.text[:1000]}")
    return response.json()


def write_outputs(output_dir: Path, manifest: Dict[str, Any]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    review_lines = [
        f"# Audioraq Seed Catalog Agent Run {manifest['run_id']}",
        "",
        f"Base URL: {manifest['base_url']}",
        f"Dry run: `{manifest['dry_run']}`",
        f"Requested total: `{manifest['target_total']}`",
        "",
        "| # | Lane | Show | Episode | URL | Provider | Quality | Moderation |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for item in manifest["results"]:
        review_lines.append(
            "| {global_index} | {publish_lane} | {show_title} | {title} | {episode_url} | {ai_audio_provider} | {quality_score} {quality_status} | {moderation_status} |".format(
                **item
            )
        )
    (output_dir / "review.md").write_text("\n".join(review_lines) + "\n", encoding="utf-8")


def plan_to_dict(plan: EpisodeBlueprint) -> Dict[str, Any]:
    return {
        "global_index": plan.global_index,
        "account_kind": plan.account_kind,
        "show_index": plan.show_index,
        "episode_index": plan.episode_index,
        "show_title": plan.show_title,
        "show_description": plan.show_description,
        "category": plan.category,
        "niche": plan.niche,
        "target_audience": plan.target_audience,
        "topic": plan.topic,
        "key_points": plan.key_points,
        "references": plan.references,
        "tone": plan.tone,
        "format": plan.format,
        "length_band": plan.length_band,
        "length_preference": plan.length_preference,
        "episode_goal": plan.episode_goal,
        "desired_outcome": plan.desired_outcome,
        "optimize_for": plan.optimize_for,
        "speaker_plan": plan.speaker_plan,
        "requested_media_kind": plan.requested_media_kind,
        "publish_lane": plan.publish_lane,
    }


def select_plans(plans: List[EpisodeBlueprint], start: int, limit: int) -> List[EpisodeBlueprint]:
    selected = [plan for plan in plans if plan.global_index >= start]
    if limit > 0:
        return selected[:limit]
    return selected


def main() -> None:
    parser = argparse.ArgumentParser(description="Plan or publish the Audioraq Originals seed catalog.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--public-origin", default=DEFAULT_PUBLIC_ORIGIN)
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--run-id", default=timestamp())
    parser.add_argument("--target-total", type=int, default=65)
    parser.add_argument("--single-count", type=int, default=0)
    parser.add_argument("--start", type=int, default=1)
    parser.add_argument("--limit", type=int, default=1, help="Safety limit. Use 0 only when intentionally publishing the full selected range.")
    parser.add_argument("--publish", action="store_true", help="Actually create accounts, drafts, and episodes on the target Audioraq deployment.")
    parser.add_argument("--publish-mode", choices=["apple-say-upload", "ai-create"], default="apple-say-upload", help="apple-say-upload uses the Create-with-AI draft plus the restored local proof-studio voices; ai-create renders on the server.")
    parser.add_argument("--password", default="", help="Optional shared password for generated seed accounts.")
    parser.add_argument("--require-provider-kind", default="", help="If set, delete and reject episodes that publish with a different TTS provider kind.")
    parser.add_argument("--continue-on-provider-mismatch", action="store_true", help="Keep processing after a required-provider mismatch. Off by default to avoid burning credits or seeding low-quality audio.")
    parser.add_argument("--min-quality-score", type=float, default=60.0, help="Delete the episode if Agent 2 returns a lower quality score.")
    parser.add_argument("--require-moderation", default="clear", help="Delete the episode if moderation_status does not match. Set empty to disable.")
    parser.add_argument("--require-quality-status", default="pass,review", help="Comma-separated accepted quality statuses. Set empty to disable.")
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    public_origin = args.public_origin.rstrip("/")
    password = args.password or f"{DEFAULT_PASSWORD_PREFIX}!{args.run_id}"
    output_dir = Path(args.output_root).resolve() / args.run_id
    media_dir = output_dir / "media"
    plans = build_catalog_plan(target_total=args.target_total, single_count=args.single_count)
    selected = select_plans(plans, args.start, args.limit)
    session = requests.Session()
    account_cache: Dict[int, Dict[str, str]] = {}
    run_results: List[Dict[str, Any]] = []
    manifest_path = output_dir / "manifest.json"
    manifest_by_index: Dict[int, Dict[str, Any]] = {}
    previous_by_index: Dict[int, Dict[str, Any]] = {}
    if manifest_path.exists():
        previous_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest_by_index = {
            int(item["global_index"]): item
            for item in previous_manifest.get("results", [])
            if item.get("global_index") is not None
        }
        previous_by_index = {int(item["global_index"]): item for item in previous_manifest.get("results", []) if item.get("status") in {"published", "skipped_existing"}}

    def persist_outputs() -> None:
        write_outputs(
            output_dir,
            {
                "run_id": args.run_id,
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "base_url": base_url,
                "public_origin": public_origin,
                "target_total": args.target_total,
                "single_count": args.single_count,
                "dry_run": not args.publish,
                "publish_mode": args.publish_mode,
                "safety_note": "Transparent Audioraq Originals seed content. No fake reviews or fake customer claims.",
                "constraints": [
                    "Create with AI publishes audio-only episodes.",
                    "Single episodes use one-episode capsule shows because the data model is show-first.",
                    "Default distribution is 275 show episodes plus 25 singles, totaling 300.",
                    "The 125-episode campaign is 125 show episodes across 12 topic shows.",
                    "The current 65-episode campaign is 65 show episodes across 7 topic shows.",
                    "Video-suitable episodes are tagged video_ready_audio, but Create with AI publishes audio only.",
                ],
                "results": [manifest_by_index[index] for index in sorted(manifest_by_index)],
            },
        )

    for plan in selected:
        previous = previous_by_index.get(plan.global_index)
        if previous:
            previous = {**previous, "status": "skipped_manifest"}
            print(json.dumps(previous, ensure_ascii=True), flush=True)
            run_results.append(previous)
            continue
        provider_mismatch = False
        email = f"audioraq-originals-{args.run_id}-{plan.account_kind}-{plan.show_index:02d}@audioraq.test"
        result = {
            **plan_to_dict(plan),
            "email": email,
            "draft_id": "",
            "episode_id": "",
            "episode_url": "",
            "title": plan.topic,
            "moderation_status": "",
            "quality_status": "",
            "quality_score": 0,
            "media_type": "",
            "content_type": "",
            "ai_audio_provider": "",
            "ai_audio_provider_kind": "",
            "ai_audio_turn_count": 0,
            "is_playable": False,
            "status": "planned",
        }
        if args.publish:
            cache_key = plan.show_index if plan.account_kind == "show" else 1000 + plan.show_index
            if cache_key not in account_cache:
                account_cache[cache_key] = get_token_and_show_id(session, base_url, email, password, plan)
            auth = account_cache[cache_key]
            existing_episode = find_existing_episode(session, base_url, public_origin, auth["token"], auth["show_id"], plan)
            if existing_episode:
                result.update(existing_episode)
                result["status"] = "skipped_existing"
                print(json.dumps(result, ensure_ascii=True), flush=True)
                run_results.append(result)
                manifest_by_index[plan.global_index] = result
                persist_outputs()
                continue
            episode_result = create_ai_episode(
                session,
                base_url,
                public_origin,
                auth["token"],
                auth["show_id"],
                plan,
                args.publish_mode,
                media_dir,
            )
            result.update(episode_result)
            result["status"] = "published"
            failure_reason = quality_failure_reason(
                episode_result,
                args.min_quality_score,
                args.require_moderation.strip(),
                args.require_quality_status.strip(),
            )
            if failure_reason:
                result["delete_result"] = delete_episode(session, base_url, auth["token"], episode_result["episode_id"])
                result["status"] = "deleted_quality_failure"
                result["quality_failure_reason"] = failure_reason
                print(json.dumps(result, ensure_ascii=True), flush=True)
                run_results.append(result)
                manifest_by_index[plan.global_index] = result
                persist_outputs()
                raise RuntimeError(f"Stopped after quality failure: {failure_reason}; deleted the episode to protect product quality.")
            required_provider = args.require_provider_kind.strip().lower()
            actual_provider = (episode_result.get("ai_audio_provider_kind") or "").strip().lower()
            if required_provider and actual_provider != required_provider:
                result["delete_result"] = delete_episode(session, base_url, auth["token"], episode_result["episode_id"])
                result["status"] = "deleted_provider_mismatch"
                result["provider_requirement"] = required_provider
                provider_mismatch = True
            print(json.dumps(result, ensure_ascii=True), flush=True)
        else:
            print(json.dumps(result, ensure_ascii=True), flush=True)
        run_results.append(result)
        manifest_by_index[plan.global_index] = result
        persist_outputs()
        if provider_mismatch and not args.continue_on_provider_mismatch:
            raise RuntimeError(
                f"Stopped after provider mismatch. Required {required_provider}, got {actual_provider or 'unknown'}; "
                "deleted the fallback episode to protect product quality."
            )

    print(json.dumps({"output_dir": str(output_dir), "published": args.publish, "processed": len(run_results)}, ensure_ascii=True))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Audioraq Seed Catalog Agent failed: {exc}", file=sys.stderr)
        sys.exit(1)
