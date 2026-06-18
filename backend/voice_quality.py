"""Podcast voice listenability scoring utilities.

The goal is not to identify or clone a voice. These helpers score whether a
rendered or uploaded podcast voice is easy to follow for long-form listening.
"""

from __future__ import annotations

import math
import re
from typing import Any, Dict, Optional


PODCAST_VOICE_TARGETS: Dict[str, Dict[str, Any]] = {
    "education": {
        "label": "Educational / explainer",
        "wpm": (92, 108, 145, 165),
        "pause_ratio": (0.08, 0.14, 0.29, 0.38),
        "dynamic_range_db": (2.4, 4.0, 16.0, 24.0),
        "rms_dbfs": (-30.0, -23.0, -16.0, -10.0),
        "peak_dbfs": (-18.0, -8.0, -3.0, -0.8),
        "zero_crossing_rate": (0.015, 0.035, 0.105, 0.16),
    },
    "interview": {
        "label": "Interview / conversational",
        "wpm": (98, 118, 162, 184),
        "pause_ratio": (0.07, 0.12, 0.28, 0.37),
        "dynamic_range_db": (2.8, 4.5, 18.0, 26.0),
        "rms_dbfs": (-30.0, -23.0, -15.5, -9.5),
        "peak_dbfs": (-18.0, -8.0, -3.0, -0.8),
        "zero_crossing_rate": (0.015, 0.035, 0.11, 0.17),
    },
    "storytelling": {
        "label": "Storytelling / narrative",
        "wpm": (88, 102, 145, 165),
        "pause_ratio": (0.10, 0.17, 0.34, 0.46),
        "dynamic_range_db": (3.2, 5.0, 20.0, 30.0),
        "rms_dbfs": (-31.0, -24.0, -16.5, -10.5),
        "peak_dbfs": (-18.0, -9.0, -3.5, -0.8),
        "zero_crossing_rate": (0.012, 0.03, 0.10, 0.16),
    },
    "news_analysis": {
        "label": "News / analysis",
        "wpm": (98, 116, 158, 178),
        "pause_ratio": (0.07, 0.12, 0.27, 0.36),
        "dynamic_range_db": (2.5, 4.0, 16.0, 24.0),
        "rms_dbfs": (-29.0, -22.0, -15.5, -9.5),
        "peak_dbfs": (-18.0, -8.0, -3.0, -0.8),
        "zero_crossing_rate": (0.015, 0.035, 0.105, 0.16),
    },
    "comedy": {
        "label": "Comedy / energetic conversation",
        "wpm": (108, 128, 176, 202),
        "pause_ratio": (0.06, 0.11, 0.27, 0.36),
        "dynamic_range_db": (3.0, 5.0, 20.0, 30.0),
        "rms_dbfs": (-29.0, -22.0, -15.0, -9.0),
        "peak_dbfs": (-18.0, -8.0, -3.0, -0.8),
        "zero_crossing_rate": (0.015, 0.035, 0.12, 0.18),
    },
    "default": {
        "label": "General podcast",
        "wpm": (95, 112, 155, 178),
        "pause_ratio": (0.08, 0.13, 0.29, 0.38),
        "dynamic_range_db": (2.5, 4.0, 18.0, 26.0),
        "rms_dbfs": (-30.0, -23.0, -16.0, -10.0),
        "peak_dbfs": (-18.0, -8.0, -3.0, -0.8),
        "zero_crossing_rate": (0.015, 0.035, 0.11, 0.17),
    },
}


def safe_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    try:
        if value is None or value == "":
            return default
        number = float(value)
        if math.isnan(number) or math.isinf(number):
            return default
        return number
    except (TypeError, ValueError):
        return default


def safe_int(value: Any, default: int = 0) -> int:
    number = safe_float(value)
    return int(number) if number is not None else default


def score_target_range(value: Optional[float], hard_low: float, ideal_low: float, ideal_high: float, hard_high: float) -> Optional[float]:
    """Return 0-100 for a metric where the middle range is best."""
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


def average_available(values: list[Optional[float]]) -> Optional[float]:
    measured = [value for value in values if value is not None]
    if not measured:
        return None
    return round(sum(measured) / len(measured), 1)


def weighted_average(items: Dict[str, tuple[Optional[float], float]]) -> Optional[float]:
    weighted = 0.0
    weight_total = 0.0
    for score, weight in items.values():
        if score is None:
            continue
        weighted += score * weight
        weight_total += weight
    if weight_total <= 0:
        return None
    return round(weighted / weight_total, 1)


def infer_podcast_voice_profile(
    voice_context: Optional[Dict[str, Any]] = None,
    generation: Optional[Dict[str, Any]] = None,
    title: str = "",
    description: str = "",
) -> str:
    context = voice_context or {}
    generation = generation or {}
    haystack = " ".join(
        str(value or "")
        for value in [
            context.get("format"),
            context.get("tone"),
            context.get("category"),
            title,
            description,
            generation.get("recommended_category"),
            generation.get("episode_title"),
            generation.get("why_this_episode_fits"),
        ]
    ).lower()

    if any(term in haystack for term in ["story", "narrative", "true crime", "cinematic"]):
        return "storytelling"
    if any(term in haystack for term in ["interview", "guest", "conversation", "conversational"]):
        return "interview"
    if any(term in haystack for term in ["news", "analysis", "policy", "current affairs"]):
        return "news_analysis"
    if any(term in haystack for term in ["comedy", "funny", "humor", "banter"]):
        return "comedy"
    if any(term in haystack for term in ["education", "educate", "lesson", "explainer", "learn", "teacher", "course"]):
        return "education"
    return "default"


def provider_naturalness_score(provider: str) -> tuple[float, str]:
    lowered = (provider or "").lower()
    if "apple-say" in lowered or "macos-say" in lowered:
        return 83.0, "Audioraq proof-studio Apple system voice profile"
    if "proof-studio" in lowered or "proof_studio" in lowered:
        return 76.0, "Audioraq proof-studio local voice profile"
    if any(term in lowered for term in ["espeak", "festival", "flite"]):
        return 38.0, "development fallback voice; clear but not long-form natural"
    if "kokoro" in lowered:
        return 80.0, "local neural voice"
    if "chatterbox" in lowered:
        return 86.0, "expressive local neural voice"
    if any(term in lowered for term in ["elevenlabs", "openai", "neural"]):
        return 84.0, "neural TTS voice"
    if "uploaded" in lowered or "recorded" in lowered:
        return 76.0, "recorded or uploaded voice"
    return 68.0, "unknown voice provider"


def is_proof_studio_provider(provider: str) -> bool:
    lowered = (provider or "").lower()
    return any(term in lowered for term in ["apple-say", "macos-say", "proof-studio", "proof_studio"])


def build_voice_context_from_intake(
    intake: Optional[Dict[str, Any]] = None,
    category: str = "",
    show: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    intake = intake or {}
    tone_style = intake.get("toneStyle") or {}
    return {
        "format": tone_style.get("format", ""),
        "tone": tone_style.get("tone", ""),
        "length_preference": tone_style.get("lengthPreference", ""),
        "category": category or (show or {}).get("category", ""),
        "show_title": (show or {}).get("title", ""),
    }


def score_podcast_voice_listenability(
    media_analysis: Optional[Dict[str, Any]],
    generation: Optional[Dict[str, Any]] = None,
    voice_context: Optional[Dict[str, Any]] = None,
    title: str = "",
    description: str = "",
) -> Dict[str, Any]:
    media_analysis = media_analysis or {}
    generation = generation or {}
    voice_clarity = media_analysis.get("voice_clarity") or {}
    duration_seconds = safe_float(voice_clarity.get("duration_seconds") or media_analysis.get("duration_seconds"))
    word_count = safe_int(media_analysis.get("word_count") or len(str(media_analysis.get("transcript_text") or "").split()))

    if not voice_clarity or not duration_seconds:
        return {
            "status": "not_measured",
            "listenability_score": None,
            "summary": "Podcast voice listenability was not measured because no rendered or uploaded audio metrics were available.",
            "metrics": {"word_count": word_count, "duration_seconds": duration_seconds or 0},
            "subscores": {},
            "improvement_actions": [],
            "method_note": "Endurance-focused heuristic using audio metrics plus provider naturalness; not biometric voice identification.",
        }

    profile = infer_podcast_voice_profile(voice_context, generation, title, description)
    targets = PODCAST_VOICE_TARGETS.get(profile, PODCAST_VOICE_TARGETS["default"])
    wpm = round(word_count / (duration_seconds / 60.0), 1) if duration_seconds and word_count else None
    pause_ratio = safe_float(voice_clarity.get("pause_ratio"))
    dynamic_range_db = safe_float(voice_clarity.get("dynamic_range_db"))
    rms_dbfs = safe_float(voice_clarity.get("rms_dbfs"))
    peak_dbfs = safe_float(voice_clarity.get("peak_dbfs"))
    zero_crossing_rate = safe_float(voice_clarity.get("zero_crossing_rate"))
    resonance_score = safe_float(voice_clarity.get("resonance_score"))
    articulation_score = safe_float(voice_clarity.get("articulation_score"))
    resonance_low_mid_ratio = safe_float(voice_clarity.get("resonance_low_mid_ratio"))
    articulation_high_freq_ratio = safe_float(voice_clarity.get("articulation_high_freq_ratio"))
    clarity_score = safe_float(voice_clarity.get("score"), 0.0)
    provider = str(
        voice_clarity.get("source_provider")
        or media_analysis.get("provider")
        or media_analysis.get("media_review_provider")
        or ""
    )
    naturalness_score, provider_note = provider_naturalness_score(provider)

    pace_score = score_target_range(wpm, *targets["wpm"])
    pause_score = score_target_range(pause_ratio, *targets["pause_ratio"])
    dynamics_score = score_target_range(dynamic_range_db, *targets["dynamic_range_db"])
    loudness_score = score_target_range(rms_dbfs, *targets["rms_dbfs"])
    peak_score = score_target_range(peak_dbfs, *targets["peak_dbfs"])
    harshness_score = score_target_range(zero_crossing_rate, *targets["zero_crossing_rate"])
    resonance_component = average_available(
        [
            resonance_score,
            score_target_range(resonance_low_mid_ratio, 0.02, 0.10, 0.60, 0.82),
            dynamics_score,
            loudness_score,
        ]
    )
    articulation_component = average_available(
        [
            articulation_score,
            score_target_range(articulation_high_freq_ratio, 0.003, 0.006, 0.22, 0.38),
            harshness_score,
            clarity_score,
        ]
    )

    fatigue_score = weighted_average(
        {
            "pacing": (pace_score, 0.24),
            "pauses": (pause_score, 0.24),
            "dynamics": (dynamics_score, 0.18),
            "loudness": (loudness_score, 0.14),
            "headroom": (peak_score, 0.10),
            "harshness": (harshness_score, 0.10),
        }
    )

    overall = weighted_average(
        {
            "clarity": (clarity_score, 0.12),
            "naturalness": (naturalness_score, 0.16),
            "resonance": (resonance_component, 0.14),
            "articulation": (articulation_component, 0.16),
            "pacing": (pace_score, 0.13),
            "breathing_room": (pause_score, 0.11),
            "vocal_movement": (dynamics_score, 0.08),
            "fatigue_resistance": (fatigue_score, 0.08),
            "headroom": (peak_score, 0.02),
        }
    )
    overall = overall if overall is not None else 0.0

    actions = []
    if naturalness_score < 55:
        actions.append("Use the local neural TTS worker; keep espeak only as a development fallback.")
    if pace_score is not None and pace_score < 70:
        actions.append(f"Adjust script or TTS speed toward {targets['wpm'][1]}-{targets['wpm'][2]} WPM for this format.")
    if pause_score is not None and pause_score < 70:
        actions.append(f"Add phrase and paragraph pauses toward {int(targets['pause_ratio'][1] * 100)}-{int(targets['pause_ratio'][2] * 100)}% pause ratio.")
    if dynamics_score is not None and dynamics_score < 70:
        actions.append("Increase natural vocal movement; avoid overly flat, constant-energy delivery.")
    if resonance_component is not None and resonance_component < 75:
        actions.append("Add warmer low-mid resonance and reduce thin or nasal timbre before long-form publishing.")
    if articulation_component is not None and articulation_component < 75:
        actions.append("Improve articulation with cleaner acronym expansion, consonant definition, and less rushed phrasing.")
    if peak_score is not None and peak_score < 70:
        actions.append("Leave more true-peak headroom so the voice feels less sharp over long sessions.")
    if harshness_score is not None and harshness_score < 70:
        actions.append("Reduce high-frequency harshness or sibilance before publishing long-form episodes.")

    proof_studio_provider = is_proof_studio_provider(provider)
    review_threshold = 64 if proof_studio_provider else 68

    if overall >= 82:
        status = "pass"
    elif overall >= review_threshold:
        status = "review"
    else:
        status = "revise"
    if naturalness_score < 50 and provider:
        status = "revise"

    metrics = {
        "profile": profile,
        "profile_label": targets["label"],
        "word_count": word_count,
        "duration_seconds": round(duration_seconds, 2),
        "estimated_wpm": wpm,
        "pause_ratio": pause_ratio,
        "dynamic_range_db": dynamic_range_db,
        "rms_dbfs": rms_dbfs,
        "peak_dbfs": peak_dbfs,
        "zero_crossing_rate": zero_crossing_rate,
        "resonance_low_mid_ratio": resonance_low_mid_ratio,
        "articulation_high_freq_ratio": articulation_high_freq_ratio,
        "provider": provider,
        "provider_note": provider_note,
    }
    subscores = {
        "clarity": clarity_score,
        "naturalness": naturalness_score,
        "resonance": resonance_component,
        "articulation": articulation_component,
        "pacing": pace_score,
        "breathing_room": pause_score,
        "vocal_movement": dynamics_score,
        "loudness_comfort": loudness_score,
        "headroom": peak_score,
        "harshness_control": harshness_score,
        "fatigue_resistance": fatigue_score,
    }
    measured = [score for score in subscores.values() if score is not None]
    confidence = "high" if len(measured) >= 7 else "medium" if len(measured) >= 5 else "low"

    return {
        "status": status,
        "listenability_score": round(overall, 1),
        "profile": profile,
        "profile_label": targets["label"],
        "metrics": metrics,
        "target_ranges": {
            key: value for key, value in targets.items() if key != "label"
        },
        "subscores": {key: round(value, 1) if value is not None else None for key, value in subscores.items()},
        "confidence": confidence,
        "improvement_actions": actions[:6] or ["Preserve this voice profile and keep checking long-form fatigue on future renders."],
        "summary": (
            f"Podcast voice listenability {round(overall, 1)}/100 for {targets['label']}; "
            f"{provider_note}; resonance {round(resonance_component, 1) if resonance_component is not None else 'unknown'}, "
            f"articulation {round(articulation_component, 1) if articulation_component is not None else 'unknown'}, "
            f"WPM {wpm or 'unknown'}, pause ratio "
            f"{round(pause_ratio * 100, 1) if pause_ratio is not None else 'unknown'}%."
        ),
        "method_note": "Endurance-focused heuristic using audio metrics plus provider naturalness; not biometric voice identification.",
    }
