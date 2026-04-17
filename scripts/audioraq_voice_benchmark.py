#!/usr/bin/env python3
"""Benchmark podcast voice candidates for long-form listenability.

This script uses the seed dataset as a rubric target and can score either:
- an existing audio file, or
- audio rendered by the local AI Studio TTS worker.

It does not train a model and it does not clone voices. It measures whether a
candidate voice is easy to follow over time.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import subprocess
import sys
import tempfile
import time
import wave
from array import array
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.voice_quality import score_podcast_voice_listenability


DEFAULT_OUTPUT_ROOT = REPO_ROOT / "qa" / "voice-benchmarks"
DEFAULT_DATASET = Path("/Users/sagnikroy/Downloads/podcast_voice_seed_dataset.csv")
DEFAULT_SCRIPT = (
    "This is an Audioraq voice benchmark for long-form podcast listening. "
    "The goal is not drama. The goal is trust, clarity, warmth, and pacing that a listener can stay with. "
    "Here is the practical test: can the listener understand the words without effort, follow the idea without stress, "
    "and keep listening without feeling pushed by the voice? A good podcast voice gives the mind room to breathe. "
    "It varies pace when the meaning changes. It leaves short pauses after important ideas. "
    "It sounds sincere rather than theatrical. If this sample feels easy to follow on laptop speakers and in earphones, "
    "it is moving in the right direction. If it feels sharp, rushed, flat, or fake, the voice needs more work before publishing."
)


def timestamp() -> str:
    return time.strftime("%Y%m%d-%H%M%S", time.gmtime())


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


def ffmpeg_path() -> str:
    for candidate in ["ffmpeg", "/usr/bin/ffmpeg", "/opt/homebrew/bin/ffmpeg"]:
        result = subprocess.run(["which", candidate], capture_output=True, text=True)
        if result.returncode == 0:
            return result.stdout.strip()
        if Path(candidate).exists():
            return candidate
    raise RuntimeError("ffmpeg is required for audio analysis")


def analyze_audio_file(path: Path, script_text: str, provider: str, max_seconds: int = 900) -> Dict[str, Any]:
    ffmpeg = ffmpeg_path()
    with tempfile.TemporaryDirectory(prefix="audioraq-voice-benchmark-") as temp_dir:
        extracted = Path(temp_dir) / "analysis.wav"
        cmd = [ffmpeg, "-y", "-i", str(path)]
        if max_seconds:
            cmd.extend(["-t", str(max_seconds)])
        cmd.extend(["-vn", "-ac", "1", "-ar", "16000", "-sample_fmt", "s16", str(extracted)])
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            raise RuntimeError(result.stderr or result.stdout or "ffmpeg conversion failed")

        total_samples = 0
        sum_squares = 0.0
        peak_abs = 0
        quiet_samples = 0
        clipped_samples = 0
        zero_crossings = 0
        previous_sign = 0
        window_values: List[float] = []
        quiet_windows = 0
        window_sum = 0.0
        window_count = 0

        with wave.open(str(extracted), "rb") as wav_file:
            sample_rate = wav_file.getframerate()
            window_size = max(1, sample_rate // 10)
            silence_threshold = int(32768 * 0.012)
            clipping_threshold = int(32768 * 0.98)

            def finish_window():
                nonlocal window_sum, window_count, quiet_windows
                if window_count <= 0:
                    return
                rms = math.sqrt(window_sum / window_count)
                db = 20 * math.log10(max(rms, 1) / 32768)
                window_values.append(db)
                if db <= -35:
                    quiet_windows += 1
                window_sum = 0.0
                window_count = 0

            while True:
                frames = wav_file.readframes(sample_rate)
                if not frames:
                    break
                samples = array("h")
                samples.frombytes(frames)
                if os.sys.byteorder != "little":
                    samples.byteswap()
                for sample in samples:
                    value = int(sample)
                    abs_value = abs(value)
                    total_samples += 1
                    sum_squares += value * value
                    peak_abs = max(peak_abs, abs_value)
                    quiet_samples += 1 if abs_value <= silence_threshold else 0
                    clipped_samples += 1 if abs_value >= clipping_threshold else 0
                    sign = 1 if value > silence_threshold else -1 if value < -silence_threshold else 0
                    if sign and previous_sign and sign != previous_sign:
                        zero_crossings += 1
                    if sign:
                        previous_sign = sign
                    window_sum += value * value
                    window_count += 1
                    if window_count >= window_size:
                        finish_window()
            finish_window()

    duration = total_samples / 16000 if total_samples else 0
    rms = math.sqrt(sum_squares / total_samples) if total_samples else 0
    rms_dbfs = 20 * math.log10(max(rms, 1) / 32768)
    peak_dbfs = 20 * math.log10(max(peak_abs, 1) / 32768)
    voiced_windows = [value for value in window_values if value > -60]
    low = percentile(voiced_windows, 0.10)
    high = percentile(voiced_windows, 0.90)
    dynamic_range = high - low if low is not None and high is not None else None
    clarity = {
        "status": "clear",
        "score": 100 if total_samples else 0,
        "summary": "Signal decoded for benchmark analysis.",
        "source_provider": provider,
        "duration_seconds": round(duration, 2),
        "rms_dbfs": round(rms_dbfs, 2),
        "peak_dbfs": round(peak_dbfs, 2),
        "silence_ratio": round(quiet_samples / max(1, total_samples), 4),
        "pause_ratio": round(quiet_windows / max(1, len(window_values)), 4),
        "dynamic_range_db": round(dynamic_range, 2) if dynamic_range is not None else None,
        "crest_factor_db": round(peak_dbfs - rms_dbfs, 2),
        "clipping_ratio": round(clipped_samples / max(1, total_samples), 6),
        "zero_crossing_rate": round(zero_crossings / max(1, total_samples), 6),
    }
    return {
        "provider": provider,
        "word_count": len(re.findall(r"[A-Za-z0-9']+", script_text)),
        "transcript_text": script_text,
        "voice_clarity": clarity,
    }


def dataset_summary(dataset_path: Path) -> Dict[str, Any]:
    if not dataset_path.exists():
        return {"available": False, "path": str(dataset_path)}
    rows = list(csv.DictReader(dataset_path.open(newline="", encoding="utf-8")))
    best = [row for row in rows if row.get("best_for_podcast") == "Yes"]
    def avg(field: str, source: List[Dict[str, str]]) -> Optional[float]:
        values = [float(row[field]) for row in source if row.get(field)]
        return round(sum(values) / len(values), 2) if values else None

    by_format: Dict[str, Dict[str, Any]] = {}
    for podcast_format in sorted({row.get("podcast_format", "") for row in rows if row.get("podcast_format")}):
        selected = [row for row in best if row.get("podcast_format") == podcast_format]
        by_format[podcast_format] = {
            "best_count": len(selected),
            "avg_pacing_wpm": avg("pacing_wpm", selected),
            "avg_clarity": avg("clarity", selected),
            "avg_warmth": avg("warmth", selected),
            "avg_authenticity": avg("authenticity", selected),
            "avg_listener_fatigue_risk": avg("listener_fatigue_risk", selected),
            "avg_long_form_stamina": avg("long_form_stamina", selected),
            "avg_overall_podcast_fit": avg("overall_podcast_fit", selected),
        }

    return {
        "available": True,
        "path": str(dataset_path),
        "rows": len(rows),
        "best_for_podcast_rows": len(best),
        "overall_best_targets": {
            "avg_pacing_wpm": avg("pacing_wpm", best),
            "avg_clarity": avg("clarity", best),
            "avg_warmth": avg("warmth", best),
            "avg_authenticity": avg("authenticity", best),
            "avg_listener_fatigue_risk": avg("listener_fatigue_risk", best),
            "avg_long_form_stamina": avg("long_form_stamina", best),
            "avg_overall_podcast_fit": avg("overall_podcast_fit", best),
        },
        "by_format": by_format,
    }


def render_with_worker(worker_url: str, engine: str, profile: str, script_text: str, output_dir: Path) -> Dict[str, Any]:
    payload = {
        "script_text": script_text,
        "turns": [{"speaker": "Host", "voice_role": "host", "text": script_text}],
        "quality_profile": profile,
        "format": "wav",
        "engine": engine,
    }
    response = requests.post(f"{worker_url.rstrip('/')}/v1/render", json=payload, timeout=900)
    if response.status_code >= 400:
        return {"engine": engine, "status": "failed", "error": response.text[:600]}
    content_type = response.headers.get("Content-Type", "audio/wav").split(";")[0]
    extension = "mp3" if "mpeg" in content_type else "wav"
    path = output_dir / f"{engine}-{profile}.{extension}"
    path.write_bytes(response.content)
    return {
        "engine": engine,
        "status": "rendered",
        "audio_path": str(path),
        "provider": response.headers.get("X-Audioraq-TTS-Provider", engine),
        "provider_kind": response.headers.get("X-Audioraq-TTS-Provider-Kind", ""),
        "model": response.headers.get("X-Audioraq-TTS-Model", ""),
        "content_type": content_type,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark Audioraq podcast voice candidates.")
    parser.add_argument("--dataset", default=str(DEFAULT_DATASET if DEFAULT_DATASET.exists() else ""))
    parser.add_argument("--audio", action="append", default=[], help="Existing audio file to score. Can be repeated.")
    parser.add_argument("--worker-url", default="", help="Optional AI Studio TTS worker URL, e.g. http://127.0.0.1:8015")
    parser.add_argument("--engines", default="kokoro,chatterbox,espeak", help="Comma-separated worker engines to render.")
    parser.add_argument("--quality-profile", default="podcast-education-calm")
    parser.add_argument("--voice-profile", default="education", help="Scoring profile: education, interview, storytelling, news_analysis, comedy, default.")
    parser.add_argument("--script-text", default=DEFAULT_SCRIPT)
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    args = parser.parse_args()

    run_dir = Path(args.output_root).resolve() / timestamp()
    run_dir.mkdir(parents=True, exist_ok=True)
    candidates = []

    for audio_path in args.audio:
        path = Path(audio_path).expanduser().resolve()
        media = analyze_audio_file(path, args.script_text, provider=f"file:{path.name}")
        score = score_podcast_voice_listenability(
            media,
            generation={"audio_script_turns": [{"speaker": "Host", "voice_role": "host", "text": args.script_text}]},
            voice_context={"format": args.voice_profile, "category": args.voice_profile},
            title="Audioraq voice benchmark",
            description="Offline voice benchmark",
        )
        candidates.append({"source": "file", "audio_path": str(path), "media_analysis": media, "score": score})

    if args.worker_url:
        for engine in [item.strip() for item in args.engines.split(",") if item.strip()]:
            render = render_with_worker(args.worker_url, engine, args.quality_profile, args.script_text, run_dir)
            if render.get("status") != "rendered":
                candidates.append({"source": "worker", **render})
                continue
            media = analyze_audio_file(Path(render["audio_path"]), args.script_text, provider=render.get("provider", engine))
            score = score_podcast_voice_listenability(
                media,
                generation={"audio_script_turns": [{"speaker": "Host", "voice_role": "host", "text": args.script_text}]},
                voice_context={"format": args.voice_profile, "category": args.voice_profile},
                title="Audioraq voice benchmark",
                description="Offline voice benchmark",
            )
            candidates.append({"source": "worker", **render, "media_analysis": media, "score": score})

    report = {
        "created_at": timestamp(),
        "dataset_summary": dataset_summary(Path(args.dataset).expanduser()) if args.dataset else {"available": False},
        "quality_profile": args.quality_profile,
        "voice_profile": args.voice_profile,
        "script_word_count": len(re.findall(r"[A-Za-z0-9']+", args.script_text)),
        "candidates": candidates,
    }
    report_path = run_dir / "voice_benchmark_report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"report_path": str(report_path), "candidate_count": len(candidates)}, ensure_ascii=True))


if __name__ == "__main__":
    main()
