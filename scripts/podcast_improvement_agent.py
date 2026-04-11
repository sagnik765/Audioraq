#!/usr/bin/env python3
"""
Podcast Improvement Agent for Audioraq QA.

Agent 2 improves scripts/media from the AI Podcast Creation Agent output by
turning monotone monologues into 2-person or 3-person dialogue episodes. It
scores each episode for:
- monotony and AI-detectability risk using a GAN-inspired discriminator report
- derogatory/harmful content using a small RAG-style safety retriever

Important: this is not a trained neural GAN. It is an adversarial QA harness
that uses generator/discriminator style scoring until a real trained detector
and an authorized reference dataset are available.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import shlex
import shutil
import statistics
import subprocess
import sys
import time
import wave
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = REPO_ROOT / "qa" / "ai-podcast-agent" / "20260411-113544" / "manifest.json"
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "qa" / "podcast-improvement-agent"
DEFAULT_SSH_HOST = "ubuntu@68.233.101.114"
DEFAULT_SSH_KEY = Path.home() / ".ssh" / "id_ed25519"

REFERENCE_BENCHMARKS = [
    {
        "name": "Raj Shamani podcast benchmark",
        "use": "educational, founder/operator energy, curiosity-led questions, practical listener takeaways",
        "do_not_copy": "Do not copy exact episode content, voice, likeness, cadence, or personal catchphrases.",
    },
    {
        "name": "Joe Rogan podcast benchmark",
        "use": "long-form conversational looseness, natural curiosity, examples, occasional challenge, human digressions that return to the point",
        "do_not_copy": "Do not copy exact episode content, voice, likeness, cadence, or personal catchphrases.",
    },
]

RAG_SAFETY_KB = [
    {
        "id": "protected-class-derogation",
        "text": "Derogatory content includes demeaning claims, insults, slurs, or inferiority claims about protected classes such as race, caste, ethnicity, nationality, religion, gender, sexual orientation, disability, or age.",
        "patterns": [r"\ball\s+\w+\s+are\s+(bad|stupid|inferior|dangerous)", r"\b(inferior|subhuman|vermin)\b"],
    },
    {
        "id": "harassment-targeting",
        "text": "Harassment includes personal attacks, humiliating language, threats, or calls to exclude a person or group from normal civic, professional, or social life.",
        "patterns": [r"\b(should be banned from society|do not deserve rights|ruin their life)\b"],
    },
    {
        "id": "dangerous-advice",
        "text": "Dangerous advice includes medical, legal, or safety instructions that encourage harm, self-harm, or ignoring professional guidance.",
        "patterns": [r"\b(drink bleach|stop taking insulin|ignore your doctor|build a bomb|kill yourself)\b"],
    },
    {
        "id": "dehumanization",
        "text": "Dehumanization frames people as pests, animals, diseases, or objects to justify mistreatment.",
        "patterns": [r"\b(they are animals|they are pests|eradicate them|wipe them out)\b"],
    },
]

ROLE_VOICES = {
    "Host": ["Aman", "Daniel", "Alex"],
    "Co-host": ["Samantha", "Ava", "Victoria"],
    "Guest": ["Daniel", "Oliver", "Fred"],
}

AVATAR_PROFILES = {
    "Host": {
        "skin": "#B87955",
        "hair": "#1C120D",
        "shirt": "#FFD84D",
        "accent": "#E3A800",
        "mic": "#F7F2E5",
    },
    "Co-host": {
        "skin": "#8D5C3F",
        "hair": "#2F1A12",
        "shirt": "#2EC4B6",
        "accent": "#1B998B",
        "mic": "#F7F2E5",
    },
    "Guest": {
        "skin": "#C48A62",
        "hair": "#111827",
        "shirt": "#FF6B6B",
        "accent": "#C92A2A",
        "mic": "#F7F2E5",
    },
}

REALNESS_TARGET_PROFILE = {
    "min_turn_count": 10,
    "min_speaker_count": 2,
    "target_question_rate": 0.12,
    "target_sentence_length_stdev": 6.0,
    "target_rms_variation": 0.18,
}


def run(cmd: List[str], **kwargs: Any) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=True, text=True, **kwargs)


def run_with_retries(cmd: List[str], attempts: int = 3, delay_seconds: float = 5.0, **kwargs: Any) -> subprocess.CompletedProcess:
    last_error = None
    for attempt in range(1, attempts + 1):
        try:
            return run(cmd, **kwargs)
        except subprocess.CalledProcessError as exc:
            last_error = exc
            if attempt < attempts:
                time.sleep(delay_seconds * attempt)
    raise last_error


def require_tool(name: str) -> None:
    if not shutil.which(name):
        raise RuntimeError(f"Required tool not found: {name}")


def slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")[:80] or "episode"


def split_sentences(text: str) -> List[str]:
    normalized = re.sub(r"\s+", " ", text or "").strip()
    if not normalized:
        return []
    sentences = re.split(r"(?<=[.!?])\s+", normalized)
    return [sentence.strip() for sentence in sentences if sentence.strip()]


def keywords_from_title(title: str) -> List[str]:
    cleaned = re.sub(r"^\[QA\]\s*", "", title or "")
    words = [
        word
        for word in re.findall(r"[A-Za-z][A-Za-z'-]+", cleaned)
        if word.lower() not in {"the", "and", "that", "your", "with", "without", "into", "from", "what", "why", "how"}
    ]
    return words[:6] or ["podcast", "episode"]


def clean_source_sentence(value: str, fallback: str) -> str:
    cleaned = re.sub(r"\s+", " ", value or "").strip()
    cleaned = re.sub(r"^Here is the core idea for this Audioraq quality check episode:\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^The takeaway is simple:\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^[A-Z][A-Za-z ]{2,32}:\s*", "", cleaned)
    cleaned = cleaned.replace("(when/what/how long)", "when, what, and how long")
    cleaned = re.sub(r"\.{2,}", ".", cleaned)
    cleaned = re.sub(r"\s+([.,!?])", r"\1", cleaned)
    cleaned = cleaned.strip(" .")
    if len(cleaned.split()) < 6:
        return fallback
    return cleaned


def improve_script(original: str, item: Dict[str, Any]) -> str:
    title = re.sub(r"^\[QA\]\s*", "", item["title"]).strip()
    sentences = split_sentences(original)
    useful = [sentence for sentence in sentences if len(sentence.split()) > 8][:10]
    topic_words = keywords_from_title(title)
    human_example = " ".join(useful[2:4]) if len(useful) >= 4 else "This works best when the advice feels like something a listener can try today."
    point_one = useful[4] if len(useful) > 4 else f"Start with one small move around {topic_words[0].lower()}."
    point_two = useful[5] if len(useful) > 5 else "Make the choice easier before the listener is tired."
    point_three = useful[6] if len(useful) > 6 else "End with a practical next step instead of a vague reminder."

    benchmark_note = (
        "The goal here is not to imitate Raj Shamani or Joe Rogan. "
        "It is to borrow the broad quality bar: a sharper question, a more human example, and a conversational return to the listener."
    )

    script = f"""
    Quick cold open. Imagine someone has already clicked on this episode, but they are deciding in the first ten seconds whether it is worth staying.
    The job of this episode is to earn that next minute.

    Today we are talking about {title}.

    Here is the tension: a polished podcast can still feel flat if every sentence has the same weight.
    So instead of running through a list, let's make this feel more like a real conversation.

    {benchmark_note}

    First, here is the question I would put at the center of the episode:
    What would make this useful enough that a listener remembers it tomorrow?

    {human_example}

    Now let's slow down and make the idea practical.
    One: {point_one}
    Two: {point_two}
    Three: {point_three}

    If you are listening as a creator, the edit is simple.
    Keep the hook short.
    Use one concrete scene.
    Then give the listener a choice, a checklist, or a next move.

    Let me put that another way.
    The episode should not sound like a generated summary.
    It should sound like a person who has a point of view, is noticing the listener's doubt, and is willing to make the advice specific.

    So the improved takeaway is this:
    use {', '.join(topic_words[:3]).lower()} as the subject, but make the emotional promise clearer.
    Tell the listener what changes after they finish.

    And if this were the final published cut, I would close with a direct prompt:
    pick one idea from this episode, use it before your next listen or recording session, and judge the episode by whether it made that next action easier.
    """
    return "\n\n".join(line.strip() for line in script.splitlines() if line.strip())


def build_dialogue_turns(original: str, item: Dict[str, Any]) -> List[Dict[str, str]]:
    title = re.sub(r"^\[QA\]\s*", "", item["title"]).strip()
    sentences = split_sentences(original)
    useful = [sentence for sentence in sentences if len(sentence.split()) > 8]
    topic_words = keywords_from_title(title)
    speaker_count = 3 if item["media_type"] == "video" else 2

    topic_line = title.lower()
    scene = clean_source_sentence(
        useful[2] if len(useful) > 2 else "",
        f"This topic matters because {topic_words[0].lower()} changes what a listener does next.",
    )
    practical = clean_source_sentence(
        useful[4] if len(useful) > 4 else "",
        "The best version of the advice is specific enough to try right after the episode.",
    )
    example = clean_source_sentence(
        useful[5] if len(useful) > 5 else "",
        "A listener should be able to picture the moment where they use the idea.",
    )
    tension = clean_source_sentence(
        useful[6] if len(useful) > 6 else "",
        "The risk is sounding polished but forgettable.",
    )
    closing = clean_source_sentence(
        useful[-1] if useful else "",
        "Give the listener one action that makes the next step easier.",
    )

    turns = [
        {
            "speaker": "Host",
            "text": f"Quick setup. Today we are taking the idea behind {topic_line} and making it feel less like a generated summary and more like a real conversation.",
        },
        {
            "speaker": "Co-host",
            "text": "Good. Because the first version had useful ideas, but it moved in one straight line. There was no friction, no curiosity, no moment where someone pushed back.",
        },
        {
            "speaker": "Host",
            "text": f"Exactly. So here is the sharper question: what would make this episode useful enough that a listener remembers it tomorrow?",
        },
        {
            "speaker": "Co-host",
            "text": f"I would start with a concrete scene. {scene}",
        },
    ]

    if speaker_count == 3:
        turns.extend(
            [
                {
                    "speaker": "Guest",
                    "text": "Let me challenge that for a second. A concrete scene helps, but only if it changes the advice. Otherwise it is just decoration.",
                },
                {
                    "speaker": "Host",
                    "text": "That is fair. So the scene needs to reveal the problem, not just illustrate it.",
                },
            ]
        )

    turns.extend(
        [
            {
                "speaker": "Co-host",
                "text": f"Right. The practical move is this: {practical}",
            },
            {
                "speaker": "Host",
                "text": f"And the human example is: {example}",
            },
            {
                "speaker": "Co-host",
                "text": "That is stronger because it gives the audience a picture. It is not just advice floating in the air.",
            },
            {
                "speaker": "Host",
                "text": f"The tension I want to keep is this: {tension}",
            },
        ]
    )

    if speaker_count == 3:
        turns.extend(
            [
                {
                    "speaker": "Guest",
                    "text": "I would also add one imperfect moment. Something like, this sounds easy until you are tired, distracted, or trying to record after a long day.",
                },
                {
                    "speaker": "Co-host",
                    "text": "Yes. That kind of admission makes the episode sound human instead of overproduced.",
                },
            ]
        )

    turns.extend(
        [
            {
                "speaker": "Host",
                "text": f"So the clean takeaway is: use {', '.join(topic_words[:3]).lower()} as the subject, but make the promise more emotional and specific.",
            },
            {
                "speaker": "Co-host",
                "text": "And if someone only remembers one thing, make it this: tell them what changes after they finish listening.",
            },
            {
                "speaker": "Host",
                "text": f"Exactly. {closing}",
            },
        ]
    )
    return turns


def render_dialogue_script(turns: List[Dict[str, str]]) -> str:
    return "\n".join(f"{turn['speaker']}: {turn['text']}" for turn in turns)


def dialogue_metrics(turns: List[Dict[str, str]]) -> Dict[str, float]:
    if not turns:
        return {"speaker_count": 0, "turn_count": 0, "speaker_balance": 0, "question_turn_rate": 0}
    counts: Dict[str, int] = {}
    for turn in turns:
        counts[turn["speaker"]] = counts.get(turn["speaker"], 0) + 1
    max_count = max(counts.values())
    min_count = min(counts.values())
    speaker_balance = min_count / max(1, max_count)
    question_turn_rate = sum(1 for turn in turns if "?" in turn["text"]) / len(turns)
    return {
        "speaker_count": len(counts),
        "turn_count": len(turns),
        "speaker_balance": round(speaker_balance, 3),
        "question_turn_rate": round(question_turn_rate, 3),
    }


def text_features(text: str) -> Dict[str, float]:
    sentences = split_sentences(text)
    words = re.findall(r"[A-Za-z']+", text.lower())
    if not sentences or not words:
        return {
            "word_count": 0,
            "sentence_count": 0,
            "avg_sentence_words": 0,
            "sentence_length_stdev": 0,
            "question_rate": 0,
            "contraction_rate": 0,
            "generic_marker_count": 0,
            "repetition_rate": 0,
        }
    lengths = [len(re.findall(r"[A-Za-z']+", sentence)) for sentence in sentences]
    generic_markers = [
        "core idea",
        "step by step",
        "the takeaway is simple",
        "in this episode",
        "welcome back",
        "let's build",
    ]
    bigrams = list(zip(words, words[1:]))
    repeated_bigrams = len(bigrams) - len(set(bigrams)) if bigrams else 0
    contractions = [word for word in words if "'" in word]
    return {
        "word_count": len(words),
        "sentence_count": len(sentences),
        "avg_sentence_words": sum(lengths) / len(lengths),
        "sentence_length_stdev": statistics.pstdev(lengths) if len(lengths) > 1 else 0,
        "question_rate": sum(1 for sentence in sentences if sentence.endswith("?")) / len(sentences),
        "contraction_rate": len(contractions) / len(words),
        "generic_marker_count": sum(text.lower().count(marker) for marker in generic_markers),
        "repetition_rate": repeated_bigrams / max(1, len(bigrams)),
    }


def gan_inspired_ai_risk(
    text: str,
    audio_metrics: Dict[str, float],
    turns: List[Dict[str, str]] | None = None,
) -> Dict[str, Any]:
    features = text_features(text)
    dialogue = dialogue_metrics(turns or [])
    risk = 42.0
    if features["sentence_length_stdev"] < 5:
        risk += 16
    if features["question_rate"] < 0.06:
        risk += 10
    if features["contraction_rate"] < 0.003:
        risk += 6
    risk += min(14, features["generic_marker_count"] * 4)
    risk += min(10, features["repetition_rate"] * 100)
    if audio_metrics.get("rms_variation", 0) < 0.18:
        risk += 10
    if audio_metrics.get("duration_seconds", 0) < 45:
        risk += 5
    if dialogue["speaker_count"] >= 2:
        risk -= 8
    if dialogue["turn_count"] >= 10:
        risk -= 6
    if dialogue["speaker_balance"] >= 0.45:
        risk -= 5
    if dialogue["question_turn_rate"] >= 0.08:
        risk -= 4
    risk = max(0, min(100, round(risk, 1)))
    label = "low" if risk < 45 else "medium" if risk < 70 else "high"
    benchmark_similarity = max(
        0,
        min(
            100,
            round(
                100
                - risk
                + min(10, dialogue["speaker_count"] * 3)
                + min(10, dialogue["turn_count"] / 2)
                + min(8, audio_metrics.get("rms_variation", 0) * 20),
                1,
            ),
        ),
    )
    return {
        "score": risk,
        "label": label,
        "features": features,
        "dialogue_features": dialogue,
        "benchmark_similarity": benchmark_similarity,
        "benchmark_profile": REALNESS_TARGET_PROFILE,
        "model_note": "GAN-inspired adversarial discriminator; not a trained GAN model.",
    }


def retrieve_safety_docs(text: str, limit: int = 2) -> List[Dict[str, Any]]:
    tokens = set(re.findall(r"[a-z]{4,}", text.lower()))
    scored = []
    for doc in RAG_SAFETY_KB:
        doc_tokens = set(re.findall(r"[a-z]{4,}", doc["text"].lower()))
        score = len(tokens & doc_tokens)
        scored.append((score, doc))
    return [doc for score, doc in sorted(scored, key=lambda item: item[0], reverse=True)[:limit] if score > 0]


def rag_safety_check(text: str) -> Dict[str, Any]:
    docs = retrieve_safety_docs(text)
    matches = []
    lowered = text.lower()
    for doc in RAG_SAFETY_KB:
        for pattern in doc["patterns"]:
            if re.search(pattern, lowered, re.IGNORECASE):
                matches.append({"policy": doc["id"], "pattern": pattern})
    status = "clear" if not matches else "review"
    return {
        "status": status,
        "retrieved_docs": [doc["id"] for doc in docs],
        "matches": matches,
        "summary": "No derogatory or harmful content patterns detected." if status == "clear" else "Potential derogatory or harmful content needs review.",
    }


def wav_metrics(path: Path) -> Dict[str, float]:
    with wave.open(str(path), "rb") as wav:
        frames = wav.getnframes()
        rate = wav.getframerate()
        channels = wav.getnchannels()
        width = wav.getsampwidth()
        raw = wav.readframes(frames)
    if width != 2:
        return {"duration_seconds": frames / max(1, rate), "rms_variation": 0.0, "silence_ratio": 0.0}
    samples = []
    for idx in range(0, len(raw), 2 * channels):
        sample = int.from_bytes(raw[idx : idx + 2], byteorder="little", signed=True)
        samples.append(sample / 32768.0)
    window = max(1, int(rate * 0.5))
    rms_values = []
    silence_windows = 0
    for start in range(0, len(samples), window):
        chunk = samples[start : start + window]
        if not chunk:
            continue
        rms = math.sqrt(sum(sample * sample for sample in chunk) / len(chunk))
        rms_values.append(rms)
        if rms < 0.01:
            silence_windows += 1
    mean_rms = statistics.mean(rms_values) if rms_values else 0.0
    stdev_rms = statistics.pstdev(rms_values) if len(rms_values) > 1 else 0.0
    return {
        "duration_seconds": round(frames / max(1, rate), 2),
        "rms_variation": round(stdev_rms / mean_rms, 3) if mean_rms else 0.0,
        "silence_ratio": round(silence_windows / max(1, len(rms_values)), 3),
    }


def synthesize_audio(script_path: Path, output_wav: Path, voice: str) -> None:
    require_tool("say")
    require_tool("afconvert")
    voices = [voice, "Aman", "Daniel", "Alex"]
    last_error = None
    for attempt, selected_voice in enumerate(dict.fromkeys(voices), start=1):
        tmp_aiff = output_wav.with_suffix(f".{attempt}.aiff")
        try:
            run(["say", "-v", selected_voice, "-o", str(tmp_aiff), "-f", str(script_path)])
            time.sleep(0.5)
            run(["afconvert", "-f", "WAVE", "-d", "LEI16", str(tmp_aiff), str(output_wav)])
            metrics = wav_metrics(output_wav)
            if metrics["duration_seconds"] >= 5:
                return
            last_error = RuntimeError(f"Generated audio was too short with voice {selected_voice}: {metrics['duration_seconds']}s")
        except Exception as exc:
            last_error = exc
        finally:
            tmp_aiff.unlink(missing_ok=True)
    raise RuntimeError(f"Could not synthesize non-empty audio for {script_path}: {last_error}")


def synthesize_turn_audio(text: str, output_wav: Path, voices: List[str]) -> None:
    require_tool("say")
    require_tool("afconvert")
    text_file = output_wav.with_suffix(".txt")
    text_file.write_text(text, encoding="utf-8")
    last_error = None
    min_duration = 0.16 if len(text.split()) <= 3 else 0.35
    for attempt, selected_voice in enumerate(dict.fromkeys(voices + ["Aman", "Daniel", "Alex"]), start=1):
        tmp_aiff = output_wav.with_suffix(f".{attempt}.aiff")
        try:
            run(["say", "-v", selected_voice, "-o", str(tmp_aiff), "-f", str(text_file)])
            time.sleep(0.25)
            run(["afconvert", "-f", "WAVE", "-d", "LEI16", str(tmp_aiff), str(output_wav)])
            metrics = wav_metrics(output_wav)
            if metrics["duration_seconds"] >= min_duration:
                return
            last_error = RuntimeError(
                f"Generated short turn with voice {selected_voice}: {metrics['duration_seconds']}s for {text[:80]!r}"
            )
        except Exception as exc:
            last_error = exc
        finally:
            tmp_aiff.unlink(missing_ok=True)
    raise RuntimeError(f"Could not synthesize dialogue turn: {last_error}")


def concat_wavs(segment_paths: List[Path], output_wav: Path, gap_seconds: float = 0.22) -> None:
    if not segment_paths:
        raise RuntimeError("No dialogue segments to concatenate")
    with wave.open(str(segment_paths[0]), "rb") as first:
        params = first.getparams()
        framerate = first.getframerate()
        sample_width = first.getsampwidth()
        channels = first.getnchannels()
    silence_frames = int(framerate * gap_seconds)
    silence = b"\x00" * silence_frames * sample_width * channels
    with wave.open(str(output_wav), "wb") as out:
        out.setparams(params)
        for segment_path in segment_paths:
            with wave.open(str(segment_path), "rb") as segment:
                if segment.getframerate() != framerate or segment.getsampwidth() != sample_width or segment.getnchannels() != channels:
                    raise RuntimeError(f"Dialogue segment format mismatch: {segment_path}")
                out.writeframes(segment.readframes(segment.getnframes()))
                out.writeframes(silence)


def synthesize_dialogue_audio(turns: List[Dict[str, str]], output_wav: Path) -> List[Dict[str, Any]]:
    with tempfile.TemporaryDirectory(prefix="audioraq-dialogue-") as temp_dir:
        temp_path = Path(temp_dir)
        segments = []
        timings = []
        cursor = 0.0
        gap_seconds = 0.22
        for index, turn in enumerate(turns, start=1):
            segment = temp_path / f"{index:02d}-{slugify(turn['speaker'])}.wav"
            synthesize_turn_audio(turn["text"], segment, ROLE_VOICES.get(turn["speaker"], ["Aman"]))
            duration = wav_metrics(segment)["duration_seconds"]
            timings.append(
                {
                    "speaker": turn["speaker"],
                    "text": turn["text"],
                    "start": round(cursor, 3),
                    "end": round(cursor + duration, 3),
                    "duration": round(duration, 3),
                }
            )
            cursor += duration + gap_seconds
            segments.append(segment)
        concat_wavs(segments, output_wav, gap_seconds=gap_seconds)
    metrics = wav_metrics(output_wav)
    if metrics["duration_seconds"] < 20:
        raise RuntimeError(f"Dialogue output is unexpectedly short: {metrics['duration_seconds']}s")
    return timings


def svg_escape(value: str) -> str:
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def write_video_cover(path: Path, title: str, label: str) -> None:
    safe_title = svg_escape(title.replace("[QA]", "").strip())
    safe_label = svg_escape(label)
    path.write_text(
        f"""<svg width="1280" height="720" viewBox="0 0 1280 720" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="gold" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#FFD84D"/>
      <stop offset="1" stop-color="#E3A800"/>
    </linearGradient>
    <radialGradient id="glow" cx="72%" cy="42%" r="60%">
      <stop offset="0" stop-color="#FFD84D" stop-opacity="0.34"/>
      <stop offset="1" stop-color="#090909" stop-opacity="0"/>
    </radialGradient>
  </defs>
  <rect width="1280" height="720" fill="#090909"/>
  <rect width="1280" height="720" fill="url(#glow)"/>
  <path d="M0 560 C180 500 300 520 440 545 C620 580 760 470 960 500 C1110 525 1180 485 1280 440 L1280 720 L0 720 Z" fill="#121212"/>
  <text x="92" y="138" fill="#FFD84D" font-size="52" font-weight="800" font-family="Arial, sans-serif">Audioraq</text>
  <text x="92" y="210" fill="#F7F2E5" font-size="46" font-weight="800" font-family="Arial, sans-serif">{safe_title}</text>
  <text x="92" y="292" fill="#C8B993" font-size="28" font-family="Arial, sans-serif">Improved QA cut - {safe_label}</text>
  <text x="92" y="610" fill="#FFD84D" font-size="26" font-weight="700" font-family="Arial, sans-serif">www.audioraq.com</text>
  <circle cx="1010" cy="318" r="96" fill="none" stroke="#FFD84D" stroke-width="8" opacity="0.4"/>
  <rect x="968" y="260" width="84" height="126" rx="42" fill="url(#gold)"/>
  <path d="M930 326 C930 376 966 414 1010 414 C1054 414 1090 376 1090 326" fill="none" stroke="#FFD84D" stroke-width="14" stroke-linecap="round"/>
  <path d="M1010 416 L1010 488 M964 498 L1056 498" stroke="#FFD84D" stroke-width="14" stroke-linecap="round"/>
</svg>""",
        encoding="utf-8",
    )


def current_speaker_at(timings: List[Dict[str, Any]], timestamp: float) -> str:
    for timing in timings:
        if timing["start"] <= timestamp <= timing["end"]:
            return str(timing["speaker"])
    if not timings:
        return "Host"
    return str(timings[min(len(timings) - 1, int(timestamp) % len(timings))]["speaker"])


def avatar_svg(speaker: str, x: int, active: bool, frame_index: int) -> str:
    profile = AVATAR_PROFILES.get(speaker, AVATAR_PROFILES["Host"])
    bob = math.sin(frame_index * 0.42 + x * 0.01) * (4 if active else 1.5)
    mouth_height = 20 if active and frame_index % 4 in (1, 2) else 5
    mouth_y = 343 + bob
    blink = frame_index % 57 in (0, 1)
    eye_shape = "line" if blink else "circle"
    left_eye = (
        f'<line x1="{x - 33}" y1="{297 + bob:.1f}" x2="{x - 19}" y2="{297 + bob:.1f}" stroke="#130F0C" stroke-width="4" stroke-linecap="round"/>'
        if eye_shape == "line"
        else f'<circle cx="{x - 26}" cy="{296 + bob:.1f}" r="5" fill="#130F0C"/>'
    )
    right_eye = (
        f'<line x1="{x + 19}" y1="{297 + bob:.1f}" x2="{x + 33}" y2="{297 + bob:.1f}" stroke="#130F0C" stroke-width="4" stroke-linecap="round"/>'
        if eye_shape == "line"
        else f'<circle cx="{x + 26}" cy="{296 + bob:.1f}" r="5" fill="#130F0C"/>'
    )
    active_ring = (
        f'<ellipse cx="{x}" cy="327" rx="116" ry="148" fill="none" stroke="{profile["accent"]}" stroke-width="7" opacity="0.72"/>'
        if active
        else f'<ellipse cx="{x}" cy="327" rx="112" ry="144" fill="none" stroke="#F7F2E5" stroke-width="2" opacity="0.16"/>'
    )
    return f"""
    <g>
      {active_ring}
      <ellipse cx="{x}" cy="525" rx="138" ry="42" fill="#000000" opacity="0.28"/>
      <path d="M{x - 98} 505 C{x - 82} 424 {x + 82} 424 {x + 98} 505 Z" fill="{profile["shirt"]}"/>
      <rect x="{x - 30}" y="{391 + bob:.1f}" width="60" height="58" rx="28" fill="{profile["skin"]}"/>
      <ellipse cx="{x}" cy="{315 + bob:.1f}" rx="74" ry="92" fill="{profile["skin"]}"/>
      <path d="M{x - 70} {272 + bob:.1f} C{x - 52} {205 + bob:.1f} {x + 54} {204 + bob:.1f} {x + 76} {273 + bob:.1f} C{x + 34} {252 + bob:.1f} {x - 15} {248 + bob:.1f} {x - 70} {272 + bob:.1f} Z" fill="{profile["hair"]}"/>
      {left_eye}
      {right_eye}
      <path d="M{x - 10} {316 + bob:.1f} C{x - 4} {325 + bob:.1f} {x + 8} {325 + bob:.1f} {x + 13} {316 + bob:.1f}" fill="none" stroke="#5B3324" stroke-width="4" stroke-linecap="round"/>
      <ellipse cx="{x}" cy="{mouth_y:.1f}" rx="23" ry="{mouth_height}" fill="#321114"/>
      <path d="M{x - 72} 505 C{x - 38} 545 {x + 38} 545 {x + 72} 505" fill="none" stroke="{profile["accent"]}" stroke-width="9" opacity="0.72"/>
      <rect x="{x - 18}" y="458" width="36" height="84" rx="18" fill="{profile["mic"]}" opacity="0.9"/>
      <rect x="{x - 4}" y="535" width="8" height="48" rx="4" fill="{profile["mic"]}" opacity="0.7"/>
      <text x="{x}" y="636" text-anchor="middle" fill="#F7F2E5" font-size="25" font-weight="800" font-family="Arial, sans-serif">{svg_escape(speaker)}</text>
    </g>"""


def waveform_svg(frame_index: int, active_speaker: str) -> str:
    active_color = AVATAR_PROFILES.get(active_speaker, AVATAR_PROFILES["Host"])["accent"]
    bars = []
    for index in range(44):
        height = 14 + int(34 * abs(math.sin(frame_index * 0.24 + index * 0.58)))
        x = 388 + index * 12
        y = 642 - height / 2
        bars.append(f'<rect x="{x}" y="{y:.1f}" width="7" height="{height}" rx="3.5" fill="{active_color}" opacity="0.72"/>')
    return "\n".join(bars)


def write_talking_studio_frame(
    path: Path,
    title: str,
    label: str,
    speakers: List[str],
    active_speaker: str,
    frame_index: int,
) -> None:
    safe_title = svg_escape(title.replace("[QA]", "").strip())
    safe_label = svg_escape(label)
    positions_by_count = {
        1: [640],
        2: [430, 850],
        3: [300, 640, 980],
    }
    positions = positions_by_count.get(len(speakers), positions_by_count[3])
    avatars = "\n".join(
        avatar_svg(speaker, positions[index], speaker == active_speaker, frame_index)
        for index, speaker in enumerate(speakers[: len(positions)])
    )
    path.write_text(
        f"""<svg width="1280" height="720" viewBox="0 0 1280 720" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="backdrop" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#17120A"/>
      <stop offset="0.48" stop-color="#080807"/>
      <stop offset="1" stop-color="#201A10"/>
    </linearGradient>
    <radialGradient id="lamp" cx="50%" cy="16%" r="58%">
      <stop offset="0" stop-color="#FFD84D" stop-opacity="0.34"/>
      <stop offset="1" stop-color="#000000" stop-opacity="0"/>
    </radialGradient>
  </defs>
  <rect width="1280" height="720" fill="url(#backdrop)"/>
  <rect width="1280" height="720" fill="url(#lamp)"/>
  <path d="M0 548 C210 504 346 520 500 552 C700 594 828 498 1036 526 C1132 539 1200 522 1280 488 L1280 720 L0 720 Z" fill="#11100E"/>
  <rect x="70" y="54" width="1140" height="110" rx="34" fill="#0D0C0B" opacity="0.78"/>
  <text x="104" y="105" fill="#FFD84D" font-size="34" font-weight="900" font-family="Arial, sans-serif">Audioraq</text>
  <text x="104" y="145" fill="#F7F2E5" font-size="28" font-weight="800" font-family="Arial, sans-serif">{safe_title[:86]}</text>
  <text x="975" y="105" text-anchor="end" fill="#C8B993" font-size="20" font-family="Arial, sans-serif">{safe_label}</text>
  <text x="975" y="135" text-anchor="end" fill="#C8B993" font-size="17" font-family="Arial, sans-serif">Synthetic avatar preview - no real-person likeness</text>
  {avatars}
  <rect x="350" y="611" width="580" height="62" rx="31" fill="#080807" opacity="0.78"/>
  {waveform_svg(frame_index, active_speaker)}
  <text x="640" y="694" text-anchor="middle" fill="#C8B993" font-size="18" font-family="Arial, sans-serif">Active speaker: {svg_escape(active_speaker)}</text>
</svg>""",
        encoding="utf-8",
    )


def write_talking_studio_frames(
    frames_dir: Path,
    title: str,
    label: str,
    turns: List[Dict[str, str]],
    timings: List[Dict[str, Any]],
    duration_seconds: float,
    fps: int = 4,
) -> None:
    frames_dir.mkdir(parents=True, exist_ok=True)
    speakers = list(dict.fromkeys(turn["speaker"] for turn in turns)) or ["Host"]
    frame_count = max(1, int(math.ceil(duration_seconds * fps)))
    for frame_index in range(frame_count):
        timestamp = frame_index / fps
        active_speaker = current_speaker_at(timings, timestamp)
        frame_path = frames_dir / f"frame-{frame_index:05d}.svg"
        write_talking_studio_frame(frame_path, title, label, speakers, active_speaker, frame_index)


def make_video_with_remote_ffmpeg(audio_path: Path, cover_path: Path, output_mp4: Path, remote: str, ssh_key: Path, run_id: str) -> None:
    remote_dir = f"/tmp/audioraq-improve-{run_id}-{output_mp4.stem}"
    container = "oracle-app-1"
    container_dir = f"/tmp/audioraq-improve-{run_id}-{output_mp4.stem}"
    ssh_base = ["ssh", "-o", "StrictHostKeyChecking=no", "-i", str(ssh_key), remote]
    rsync_base = ["rsync", "-az", "-e", f"ssh -o StrictHostKeyChecking=no -i {ssh_key}"]

    run_with_retries(ssh_base + [f"mkdir -p {shlex.quote(remote_dir)}"])
    run_with_retries(rsync_base + [str(audio_path), str(cover_path), f"{remote}:{remote_dir}/"])

    remote_audio = f"{remote_dir}/{audio_path.name}"
    remote_cover = f"{remote_dir}/{cover_path.name}"
    remote_output = f"{remote_dir}/{output_mp4.name}"
    container_audio = f"{container_dir}/{audio_path.name}"
    container_cover = f"{container_dir}/{cover_path.name}"
    container_output = f"{container_dir}/{output_mp4.name}"
    ffmpeg_args = [
        "ffmpeg",
        "-y",
        "-v",
        "error",
        "-loop",
        "1",
        "-framerate",
        "1",
        "-i",
        container_cover,
        "-i",
        container_audio,
        "-vf",
        "scale=1280:720,format=yuv420p",
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-tune",
        "stillimage",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-shortest",
        "-movflags",
        "+faststart",
        container_output,
    ]
    remote_cmd = " && ".join(
        [
            f"docker exec {container} mkdir -p {shlex.quote(container_dir)}",
            f"docker cp {shlex.quote(remote_audio)} {container}:{shlex.quote(container_audio)}",
            f"docker cp {shlex.quote(remote_cover)} {container}:{shlex.quote(container_cover)}",
            f"docker exec {container} {' '.join(shlex.quote(part) for part in ffmpeg_args)}",
            f"docker cp {container}:{shlex.quote(container_output)} {shlex.quote(remote_output)}",
        ]
    )
    run_with_retries(ssh_base + [remote_cmd], attempts=4, delay_seconds=8)
    run_with_retries(rsync_base + [f"{remote}:{remote_output}", str(output_mp4)])


def make_talking_studio_video_with_remote_ffmpeg(
    audio_path: Path,
    frames_dir: Path,
    output_mp4: Path,
    remote: str,
    ssh_key: Path,
    run_id: str,
    fps: int = 4,
) -> None:
    remote_dir = f"/tmp/audioraq-avatar-{run_id}-{output_mp4.stem}"
    remote_frames_dir = f"{remote_dir}/frames"
    container = "oracle-app-1"
    container_dir = f"/tmp/audioraq-avatar-{run_id}-{output_mp4.stem}"
    container_frames_dir = f"{container_dir}/frames"
    ssh_base = ["ssh", "-o", "StrictHostKeyChecking=no", "-i", str(ssh_key), remote]
    rsync_base = ["rsync", "-az", "-e", f"ssh -o StrictHostKeyChecking=no -i {ssh_key}"]

    run_with_retries(ssh_base + [f"mkdir -p {shlex.quote(remote_frames_dir)}"])
    run_with_retries(rsync_base + [str(audio_path), f"{remote}:{remote_dir}/"])
    run_with_retries(rsync_base + [str(frames_dir) + "/", f"{remote}:{remote_frames_dir}/"])

    remote_audio = f"{remote_dir}/{audio_path.name}"
    remote_output = f"{remote_dir}/{output_mp4.name}"
    container_audio = f"{container_dir}/{audio_path.name}"
    container_output = f"{container_dir}/{output_mp4.name}"
    container_frame_pattern = f"{container_frames_dir}/frame-%05d.svg"
    ffmpeg_args = [
        "ffmpeg",
        "-y",
        "-v",
        "error",
        "-framerate",
        str(fps),
        "-i",
        container_frame_pattern,
        "-i",
        container_audio,
        "-vf",
        "scale=1280:720,format=yuv420p",
        "-r",
        "24",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-shortest",
        "-movflags",
        "+faststart",
        container_output,
    ]
    remote_cmd = " && ".join(
        [
            f"docker exec {container} mkdir -p {shlex.quote(container_frames_dir)}",
            f"docker cp {shlex.quote(remote_audio)} {container}:{shlex.quote(container_audio)}",
            f"docker cp {shlex.quote(remote_frames_dir)}/. {container}:{shlex.quote(container_frames_dir)}/",
            f"docker exec {container} {' '.join(shlex.quote(part) for part in ffmpeg_args)}",
            f"docker cp {container}:{shlex.quote(container_output)} {shlex.quote(remote_output)}",
        ]
    )
    run_with_retries(ssh_base + [remote_cmd], attempts=4, delay_seconds=8)
    run_with_retries(rsync_base + [f"{remote}:{remote_output}", str(output_mp4)])


def summarize_result(item: Dict[str, Any], before: Dict[str, Any], after: Dict[str, Any]) -> str:
    return (
        f"AI-risk {before['label']} {before['score']} -> {after['label']} {after['score']}; "
        f"benchmark similarity {after.get('benchmark_similarity', 0)}; "
        f"safety {after.get('safety_status', 'clear')}; "
        f"duration {after['audio_metrics']['duration_seconds']}s"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Improve and evaluate Audioraq QA podcasts.")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--voice", default="Aman")
    parser.add_argument("--remote", default=DEFAULT_SSH_HOST)
    parser.add_argument("--ssh-key", default=str(DEFAULT_SSH_KEY))
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--start-index", type=int, default=1)
    args = parser.parse_args()

    manifest_path = Path(args.manifest).resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    run_id = time.strftime("%Y%m%d-%H%M%S")
    output_root = Path(args.output_root).resolve() / run_id
    scripts_dir = output_root / "scripts"
    media_dir = output_root / "media"
    covers_dir = output_root / "covers"
    frames_root = output_root / "frames"
    output_root.mkdir(parents=True, exist_ok=True)
    scripts_dir.mkdir(parents=True, exist_ok=True)
    media_dir.mkdir(parents=True, exist_ok=True)
    covers_dir.mkdir(parents=True, exist_ok=True)
    frames_root.mkdir(parents=True, exist_ok=True)

    results = []
    selected = [item for item in manifest["results"] if int(item["index"]) >= args.start_index]
    selected = selected[: args.limit or None]
    for item in selected:
        index = int(item["index"])
        slug = f"{index:02d}-{slugify(item['title'])}"
        original_script_path = Path(item["script_path"])
        original_text = original_script_path.read_text(encoding="utf-8")
        dialogue_turns = build_dialogue_turns(original_text, item)
        improved_text = render_dialogue_script(dialogue_turns)
        improved_script_path = scripts_dir / f"{slug}-improved.txt"
        improved_script_path.write_text(improved_text + "\n", encoding="utf-8")

        improved_audio = media_dir / f"{slug}-improved.wav"
        turn_timings = synthesize_dialogue_audio(dialogue_turns, improved_audio)
        original_metrics = wav_metrics(Path(item["media_path"]) if item["media_type"] == "audio" else Path(str(item["media_path"]).replace(".mp4", ".wav")))
        improved_metrics = wav_metrics(improved_audio)
        before_risk = gan_inspired_ai_risk(original_text, original_metrics)
        after_risk = gan_inspired_ai_risk(improved_text, improved_metrics, turns=dialogue_turns)
        safety = rag_safety_check(improved_text)

        improved_media = improved_audio
        if item["media_type"] == "video":
            cover_path = covers_dir / f"{slug}-cover.svg"
            write_video_cover(cover_path, item["title"], f"{len({turn['speaker'] for turn in dialogue_turns})}-speaker audio + video")
            improved_media = media_dir / f"{slug}-improved.mp4"
            frames_dir = frames_root / slug
            write_talking_studio_frames(
                frames_dir,
                item["title"],
                f"{len({turn['speaker'] for turn in dialogue_turns})}-speaker synthetic avatar conversation",
                dialogue_turns,
                turn_timings,
                improved_metrics["duration_seconds"],
            )
            make_talking_studio_video_with_remote_ffmpeg(improved_audio, frames_dir, improved_media, args.remote, Path(args.ssh_key).expanduser().resolve(), run_id)

        result = {
            "index": index,
            "format": item["format"],
            "title": item["title"],
            "original_episode_url": item["episode_url"],
            "original_script_path": item["script_path"],
            "improved_script_path": str(improved_script_path),
            "improved_media_path": str(improved_media),
            "before_ai_detector": before_risk,
            "after_ai_detector": after_risk,
            "rag_safety": safety,
            "audio_metrics": improved_metrics,
            "dialogue_turns": dialogue_turns,
            "turn_timings": turn_timings,
            "visual_style": "Synthetic animated studio avatars with active-speaker mouth/head movement; no real-person likeness.",
        }
        result["summary"] = summarize_result(
            item,
            before_risk,
            {
                **after_risk,
                "safety_status": safety["status"],
                "audio_metrics": improved_metrics,
            },
        )
        results.append(result)
        print(json.dumps({"index": index, "title": item["title"], "summary": result["summary"]}, ensure_ascii=True), flush=True)

    output_manifest = {
        "run_id": run_id,
        "input_manifest": str(manifest_path),
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "method_notes": {
            "benchmarks": REFERENCE_BENCHMARKS,
            "gan_note": "GAN-inspired adversarial discriminator, not a trained neural GAN model.",
            "rag_note": "Local RAG-style retrieval over safety policy snippets plus pattern checks.",
            "video_note": "Video episodes use consent-safe synthetic animated avatars and do not claim to depict real people.",
        },
        "results": results,
    }
    manifest_out = output_root / "manifest.json"
    manifest_out.write_text(json.dumps(output_manifest, indent=2), encoding="utf-8")

    review_lines = [
        f"# Podcast Improvement Agent QA Run {run_id}",
        "",
        "Benchmarks used as high-level quality references only:",
        "- Raj Shamani podcast: practical, curiosity-led, educational founder/operator energy.",
        "- Joe Rogan podcast: conversational long-form looseness, natural follow-up questions, concrete examples.",
        "",
        "Guardrail: this agent does not clone voices, likeness, exact cadence, or copyrighted episode content.",
        "",
        "Detector note: the AI detector is GAN-inspired/adversarial, not a trained neural GAN.",
        "Voice note: speakers use distinct generic system voices; the agent does not copy Joe Rogan or Raj Shamani resonance/articulation.",
        "Video note: audio+video cuts use synthetic animated studio avatars with active-speaker mouth/head movement; they are not real-person likenesses.",
        "Safety note: the derogatory-content check uses a local RAG-style safety knowledge base and pattern scan.",
        "",
        "| # | Format | Speakers | Title | Original | Improved Media | Improved Script | AI Risk Before | AI Risk After | Benchmark Similarity | RAG Safety | Summary |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for item in results:
        review_lines.append(
            "| {index} | {format} | {speakers} | {title} | {original_episode_url} | `{improved_media_path}` | `{improved_script_path}` | {before} | {after} | {similarity} | {safety} | {summary} |".format(
                index=item["index"],
                format=item["format"],
                speakers=item["after_ai_detector"]["dialogue_features"]["speaker_count"],
                title=item["title"],
                original_episode_url=item["original_episode_url"],
                improved_media_path=item["improved_media_path"],
                improved_script_path=item["improved_script_path"],
                before=f"{item['before_ai_detector']['label']} {item['before_ai_detector']['score']}",
                after=f"{item['after_ai_detector']['label']} {item['after_ai_detector']['score']}",
                similarity=item["after_ai_detector"]["benchmark_similarity"],
                safety=item["rag_safety"]["status"],
                summary=item["summary"],
            )
        )
    review_out = output_root / "review.md"
    review_out.write_text("\n".join(review_lines) + "\n", encoding="utf-8")
    print(json.dumps({"manifest": str(manifest_out), "review": str(review_out)}, ensure_ascii=True))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Podcast Improvement Agent failed: {exc}", file=sys.stderr)
        sys.exit(1)
