#!/usr/bin/env python3
"""
Podcast Improvement Agent for Audioraq QA.

Agent 2 improves scripts/media from the AI Podcast Creation Agent output and
scores each episode for:
- monotony and AI-detectability risk using a GAN-inspired discriminator report
- derogatory/harmful content using a small RAG-style safety retriever

Important: this is not a trained neural GAN. It is an adversarial QA harness
that uses generator/discriminator style scoring until a real trained detector
and reference dataset are available.
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


def gan_inspired_ai_risk(text: str, audio_metrics: Dict[str, float]) -> Dict[str, Any]:
    features = text_features(text)
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
    risk = max(0, min(100, round(risk, 1)))
    label = "low" if risk < 45 else "medium" if risk < 70 else "high"
    return {"score": risk, "label": label, "features": features}


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


def summarize_result(item: Dict[str, Any], before: Dict[str, Any], after: Dict[str, Any]) -> str:
    return (
        f"AI-risk {before['label']} {before['score']} -> {after['label']} {after['score']}; "
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
    output_root.mkdir(parents=True, exist_ok=True)
    scripts_dir.mkdir(parents=True, exist_ok=True)
    media_dir.mkdir(parents=True, exist_ok=True)
    covers_dir.mkdir(parents=True, exist_ok=True)

    results = []
    selected = [item for item in manifest["results"] if int(item["index"]) >= args.start_index]
    selected = selected[: args.limit or None]
    for item in selected:
        index = int(item["index"])
        slug = f"{index:02d}-{slugify(item['title'])}"
        original_script_path = Path(item["script_path"])
        original_text = original_script_path.read_text(encoding="utf-8")
        improved_text = improve_script(original_text, item)
        improved_script_path = scripts_dir / f"{slug}-improved.txt"
        improved_script_path.write_text(improved_text + "\n", encoding="utf-8")

        improved_audio = media_dir / f"{slug}-improved.wav"
        synthesize_audio(improved_script_path, improved_audio, args.voice)
        original_metrics = wav_metrics(Path(item["media_path"]) if item["media_type"] == "audio" else Path(str(item["media_path"]).replace(".mp4", ".wav")))
        improved_metrics = wav_metrics(improved_audio)
        before_risk = gan_inspired_ai_risk(original_text, original_metrics)
        after_risk = gan_inspired_ai_risk(improved_text, improved_metrics)
        safety = rag_safety_check(improved_text)

        improved_media = improved_audio
        if item["media_type"] == "video":
            cover_path = covers_dir / f"{slug}-cover.svg"
            write_video_cover(cover_path, item["title"], "audio + video")
            improved_media = media_dir / f"{slug}-improved.mp4"
            make_video_with_remote_ffmpeg(improved_audio, cover_path, improved_media, args.remote, Path(args.ssh_key).expanduser().resolve(), run_id)

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
        "Safety note: the derogatory-content check uses a local RAG-style safety knowledge base and pattern scan.",
        "",
        "| # | Format | Title | Original | Improved Media | Improved Script | AI Risk Before | AI Risk After | RAG Safety | Summary |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for item in results:
        review_lines.append(
            "| {index} | {format} | {title} | {original_episode_url} | `{improved_media_path}` | `{improved_script_path}` | {before} | {after} | {safety} | {summary} |".format(
                index=item["index"],
                format=item["format"],
                title=item["title"],
                original_episode_url=item["original_episode_url"],
                improved_media_path=item["improved_media_path"],
                improved_script_path=item["improved_script_path"],
                before=f"{item['before_ai_detector']['label']} {item['before_ai_detector']['score']}",
                after=f"{item['after_ai_detector']['label']} {item['after_ai_detector']['score']}",
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
