#!/usr/bin/env python3
"""Render synthetic animated avatar videos from existing improved dialogue audio."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any, Dict, List

import podcast_improvement_agent as improvement


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_IMPROVED_MANIFEST = REPO_ROOT / "qa" / "podcast-improvement-agent" / "20260411-124502" / "manifest.json"
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "qa" / "avatar-video-agent"


def approximate_turn_timings(turns: List[Dict[str, str]], duration_seconds: float, gap_seconds: float = 0.22) -> List[Dict[str, Any]]:
    if not turns:
        return []
    word_counts = [max(1, len(turn["text"].split())) for turn in turns]
    total_words = sum(word_counts)
    usable_duration = max(duration_seconds - gap_seconds * len(turns), duration_seconds * 0.85)
    cursor = 0.0
    timings = []
    for turn, word_count in zip(turns, word_counts):
        turn_duration = max(0.45, usable_duration * (word_count / total_words))
        timings.append(
            {
                "speaker": turn["speaker"],
                "text": turn["text"],
                "start": round(cursor, 3),
                "end": round(min(duration_seconds, cursor + turn_duration), 3),
                "duration": round(turn_duration, 3),
            }
        )
        cursor += turn_duration + gap_seconds
    return timings


def improved_audio_path(item: Dict[str, Any]) -> Path:
    media_path = Path(item["improved_media_path"])
    if media_path.suffix.lower() == ".wav":
        return media_path
    wav_path = media_path.with_suffix(".wav")
    if wav_path.exists():
        return wav_path
    raise RuntimeError(f"Could not find improved dialogue WAV for {media_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Render avatar videos from improved Audioraq QA dialogue audio.")
    parser.add_argument("--improved-manifest", default=str(DEFAULT_IMPROVED_MANIFEST))
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--remote", default=improvement.DEFAULT_SSH_HOST)
    parser.add_argument("--ssh-key", default=str(improvement.DEFAULT_SSH_KEY))
    parser.add_argument("--start-index", type=int, default=6)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    source_manifest_path = Path(args.improved_manifest).resolve()
    source_manifest = json.loads(source_manifest_path.read_text(encoding="utf-8"))
    selected = [
        item
        for item in source_manifest["results"]
        if int(item["index"]) >= args.start_index and item.get("format") == "audio + video"
    ]
    selected = selected[: args.limit or None]

    run_id = time.strftime("%Y%m%d-%H%M%S")
    output_root = Path(args.output_root).resolve() / run_id
    frames_root = output_root / "frames"
    media_dir = output_root / "media"
    output_root.mkdir(parents=True, exist_ok=True)
    frames_root.mkdir(parents=True, exist_ok=True)
    media_dir.mkdir(parents=True, exist_ok=True)

    results = []
    for item in selected:
        index = int(item["index"])
        slug = f"{index:02d}-{improvement.slugify(item['title'])}"
        audio_path = improved_audio_path(item)
        audio_metrics = improvement.wav_metrics(audio_path)
        dialogue_turns = item["dialogue_turns"]
        timings = item.get("turn_timings") or approximate_turn_timings(dialogue_turns, audio_metrics["duration_seconds"])
        frames_dir = frames_root / slug
        output_mp4 = media_dir / f"{slug}-avatar-studio.mp4"

        improvement.write_talking_studio_frames(
            frames_dir,
            item["title"],
            f"{len({turn['speaker'] for turn in dialogue_turns})}-speaker synthetic avatar conversation",
            dialogue_turns,
            timings,
            audio_metrics["duration_seconds"],
        )
        improvement.make_talking_studio_video_with_remote_ffmpeg(
            audio_path,
            frames_dir,
            output_mp4,
            args.remote,
            Path(args.ssh_key).expanduser().resolve(),
            run_id,
        )

        rendered = {
            **item,
            "improved_media_path": str(output_mp4),
            "source_improved_media_path": item["improved_media_path"],
            "source_improved_audio_path": str(audio_path),
            "audio_metrics": audio_metrics,
            "turn_timings": timings,
            "visual_style": "Synthetic animated studio avatars with active-speaker mouth/head movement; no real-person likeness.",
        }
        results.append(rendered)
        print(
            json.dumps(
                {
                    "index": index,
                    "title": item["title"],
                    "avatar_video_path": str(output_mp4),
                    "duration_seconds": audio_metrics["duration_seconds"],
                    "visual_style": rendered["visual_style"],
                },
                ensure_ascii=True,
            ),
            flush=True,
        )

    output_manifest = {
        "run_id": run_id,
        "input_manifest": str(source_manifest_path),
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "method_notes": {
            "video_note": "Uses existing improved dialogue audio with consent-safe synthetic animated avatars. It does not create real-person likenesses or clone real people.",
            "source_method_notes": source_manifest.get("method_notes", {}),
        },
        "results": results,
    }
    manifest_out = output_root / "manifest.json"
    manifest_out.write_text(json.dumps(output_manifest, indent=2), encoding="utf-8")

    review_lines = [
        f"# Avatar Video Agent QA Run {run_id}",
        "",
        "Guardrail: these are synthetic animated avatars, not real-person likenesses or cloned people.",
        "",
        "| # | Title | Avatar Video | Source Audio | Visual Style |",
        "| --- | --- | --- | --- | --- |",
    ]
    for item in results:
        review_lines.append(
            f"| {item['index']} | {item['title']} | `{item['improved_media_path']}` | `{item['source_improved_audio_path']}` | {item['visual_style']} |"
        )
    review_out = output_root / "review.md"
    review_out.write_text("\n".join(review_lines) + "\n", encoding="utf-8")
    print(json.dumps({"manifest": str(manifest_out), "review": str(review_out)}, ensure_ascii=True))


if __name__ == "__main__":
    main()
