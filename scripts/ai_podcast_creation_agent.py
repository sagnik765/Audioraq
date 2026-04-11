#!/usr/bin/env python3
"""
AI Podcast Creation Agent for Audioraq QA.

Creates synthetic podcaster accounts, generates AI podcast drafts through the
real Audioraq API, creates review media, uploads 5 audio episodes and 5 video
episodes, and writes a local review manifest for manual quality checks.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

import requests


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "qa" / "ai-podcast-agent"
DEFAULT_BASE_URL = "https://www.audioraq.com"
DEFAULT_PUBLIC_ORIGIN = "https://www.audioraq.com"
DEFAULT_SSH_HOST = "ubuntu@68.233.101.114"
DEFAULT_SSH_KEY = Path.home() / ".ssh" / "id_ed25519"
DEFAULT_VIDEO_COVER = REPO_ROOT / "branding" / "linkedin" / "company-cover.png"


@dataclass
class EpisodeSpec:
    index: int
    media_kind: str
    podcast_name: str
    niche: str
    target_audience: str
    episode_goal: str
    desired_outcome: str
    topic: str
    key_points: List[str]
    references: List[str]
    tone: str
    format: str
    length_preference: str
    optimize_for: str
    known_issues: str = ""


EPISODES: List[EpisodeSpec] = [
    EpisodeSpec(
        1,
        "audio",
        "Audioraq QA Audio Lab 01",
        "podcast listening habits",
        "busy professionals who want deeper listening routines",
        "educate",
        "leave with a practical listening habit they can try this week",
        "How to build a listening habit that actually sticks",
        [
            "Pair listening with a recurring daily anchor",
            "Use a small queue instead of endless browsing",
            "Track one idea worth remembering after each episode",
        ],
        ["habit stacking", "attention design"],
        "professional",
        "solo",
        "short",
        "clarity",
    ),
    EpisodeSpec(
        2,
        "audio",
        "Audioraq QA Audio Lab 02",
        "creator publishing workflow",
        "new podcasters preparing their first 10 episodes",
        "educate",
        "understand why show notes improve discovery and trust",
        "Why show notes still matter in podcast discovery",
        [
            "Show notes reduce uncertainty before a listener presses play",
            "Useful notes help search and recommendations work better",
            "A summary plus three takeaways is enough to start",
        ],
        ["podcast SEO", "listener trust"],
        "casual",
        "solo",
        "short",
        "retention",
    ),
    EpisodeSpec(
        3,
        "audio",
        "Audioraq QA Audio Lab 03",
        "recording preparation",
        "solo creators who want cleaner episodes without overproducing",
        "storytelling",
        "walk away with a simple pre-recording ritual",
        "The creator's first 30 minutes before recording",
        [
            "Write the promise of the episode in one sentence",
            "Mark the two transitions that need the most clarity",
            "Record a rough cold open before perfecting the outline",
        ],
        ["creator workflow", "episode planning"],
        "storytelling",
        "narrative",
        "short",
        "clarity",
    ),
    EpisodeSpec(
        4,
        "audio",
        "Audioraq QA Audio Lab 04",
        "audience-led programming",
        "podcasters with small but engaged audiences",
        "educate",
        "turn audience questions into a repeatable episode pipeline",
        "Turning listener questions into better episodes",
        [
            "Group questions by the job the listener is trying to solve",
            "Use one strong question as the cold open",
            "Close the loop by crediting the question theme, not private details",
        ],
        ["audience research", "community feedback"],
        "energetic",
        "solo",
        "short",
        "retention",
    ),
    EpisodeSpec(
        5,
        "audio",
        "Audioraq QA Audio Lab 05",
        "intentional podcast discovery",
        "listeners tired of noisy recommendation feeds",
        "educate",
        "learn how to browse with a clearer purpose",
        "Podcast discovery without the doomscroll",
        [
            "Start with an outcome, not a category",
            "Use saves as a shortlist, not a junk drawer",
            "Follow shows that deliver consistently across episodes",
        ],
        ["recommendation design", "long-form listening"],
        "professional",
        "solo",
        "short",
        "clarity",
    ),
    EpisodeSpec(
        6,
        "video",
        "Audioraq QA Video Lab 01",
        "podcast show pages",
        "creators improving their public show presence",
        "educate",
        "know the three parts of a show page that build confidence",
        "Designing a show page that converts curious listeners",
        [
            "Lead with the promise of the show",
            "Make the latest episode easy to evaluate",
            "Use artwork and cadence as trust signals",
        ],
        ["landing page design", "podcast conversion"],
        "professional",
        "solo",
        "short",
        "clarity",
    ),
    EpisodeSpec(
        7,
        "video",
        "Audioraq QA Video Lab 02",
        "AI-assisted podcast creation",
        "creators experimenting with AI but protecting their voice",
        "educate",
        "use AI as a producer without sounding generic",
        "Using AI as a producer, not a replacement",
        [
            "Ask AI for structure before asking for copy",
            "Keep your lived examples and opinions human",
            "Use the draft as a rehearsal partner, not a final script",
        ],
        ["AI creator tools", "podcast production"],
        "casual",
        "solo",
        "short",
        "clarity",
    ),
    EpisodeSpec(
        8,
        "video",
        "Audioraq QA Video Lab 03",
        "podcast trailers",
        "new listeners deciding whether to subscribe",
        "entertain",
        "understand what makes a trailer earn the next click",
        "What makes a podcast trailer work",
        [
            "Promise the transformation, not every topic",
            "Use one strong proof point or soundbite",
            "End by telling listeners exactly where to begin",
        ],
        ["podcast trailer", "listener onboarding"],
        "energetic",
        "narrative",
        "short",
        "retention",
    ),
    EpisodeSpec(
        9,
        "video",
        "Audioraq QA Video Lab 04",
        "creator analytics",
        "podcasters checking stats after publishing",
        "educate",
        "read analytics without chasing noisy vanity metrics",
        "Reading podcast analytics without chasing noise",
        [
            "Compare episodes by intent before comparing raw views",
            "Watch completion and saves alongside plays",
            "Turn one pattern into the next editorial experiment",
        ],
        ["podcast analytics", "creator growth"],
        "professional",
        "solo",
        "short",
        "clarity",
    ),
    EpisodeSpec(
        10,
        "video",
        "Audioraq QA Video Lab 05",
        "creator trust and brand quality",
        "independent podcasters building reputation",
        "storytelling",
        "choose simple trust signals that help good shows stand out",
        "Building trust signals into your podcast brand",
        [
            "Make publish cadence visible and realistic",
            "Keep claims specific and grounded",
            "Use verified ownership and clear episode context",
        ],
        ["brand trust", "quality signals"],
        "storytelling",
        "narrative",
        "short",
        "retention",
    ),
]


def slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")[:80] or "episode"


def run(cmd: List[str], **kwargs: Any) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=True, text=True, **kwargs)


def require_tool(name: str) -> None:
    if not shutil.which(name):
        raise RuntimeError(f"Required tool not found: {name}")


def build_intake(spec: EpisodeSpec) -> Dict[str, Any]:
    return {
        "identity": {
            "podcastName": spec.podcast_name,
            "niche": spec.niche,
            "targetAudience": spec.target_audience,
        },
        "episodeIntent": {
            "episodeGoal": spec.episode_goal,
            "desiredOutcome": spec.desired_outcome,
        },
        "contentInput": {
            "topic": spec.topic,
            "keyPoints": spec.key_points,
            "references": spec.references,
        },
        "toneStyle": {
            "tone": spec.tone,
            "format": spec.format,
            "lengthPreference": spec.length_preference,
        },
        "growthOptimization": {
            "optimizeFor": spec.optimize_for,
            "includeHook": True,
            "knownIssues": spec.known_issues,
        },
    }


def build_review_script(spec: EpisodeSpec, generation: Dict[str, Any]) -> str:
    outline = generation.get("outline") or []
    outline_lines = []
    for section in outline[:4]:
        beats = section.get("beats") or []
        beat_text = " ".join(str(beat).strip() for beat in beats[:2] if str(beat).strip())
        if beat_text:
            outline_lines.append(f"{section.get('section_title', 'Section')}: {beat_text}")

    talking_points = generation.get("talking_points") or spec.key_points
    point_text = " ".join(f"{point}." for point in talking_points[:4])
    script = f"""
    {generation.get('hook') or spec.topic}

    {generation.get('intro_script') or ''}

    Here is the core idea for this Audioraq quality check episode: {generation.get('one_line_promise') or spec.desired_outcome}

    {point_text}

    {' '.join(outline_lines)}

    The takeaway is simple: {spec.desired_outcome}. {generation.get('outro_cta') or 'Thanks for listening, and come back for the next episode.'}
    """
    return " ".join(script.split())


def synthesize_audio(script_path: Path, output_wav: Path, voice: str) -> None:
    require_tool("say")
    require_tool("afconvert")
    tmp_aiff = output_wav.with_suffix(".aiff")
    run(["say", "-v", voice, "-o", str(tmp_aiff), "-f", str(script_path)])
    run(["afconvert", "-f", "WAVE", "-d", "LEI16", str(tmp_aiff), str(output_wav)])
    tmp_aiff.unlink(missing_ok=True)


def make_video_with_remote_ffmpeg(
    audio_path: Path,
    output_mp4: Path,
    cover_path: Path,
    remote: str,
    ssh_key: Path,
    run_id: str,
) -> None:
    if not cover_path.exists():
        raise RuntimeError(f"Video cover not found: {cover_path}")

    remote_dir = f"/tmp/audioraq-agent-{run_id}-{output_mp4.stem}"
    container = "oracle-app-1"
    container_dir = f"/tmp/audioraq-agent-{run_id}-{output_mp4.stem}"
    ssh_base = ["ssh", "-o", "StrictHostKeyChecking=no", "-i", str(ssh_key), remote]
    rsync_base = ["rsync", "-az", "-e", f"ssh -o StrictHostKeyChecking=no -i {ssh_key}"]

    run(ssh_base + [f"mkdir -p {shlex.quote(remote_dir)}"])
    run(rsync_base + [str(audio_path), str(cover_path), f"{remote}:{remote_dir}/"])

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
        "scale=1280:-2,pad=1280:720:(ow-iw)/2:(oh-ih)/2:black,format=yuv420p",
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
    run(ssh_base + [remote_cmd])
    run(rsync_base + [f"{remote}:{remote_output}", str(output_mp4)])


def api_post(session: requests.Session, url: str, token: str = "", **kwargs: Any) -> requests.Response:
    headers = kwargs.pop("headers", {})
    if token:
        headers["Authorization"] = f"Bearer {token}"
    response = session.post(url, headers=headers, timeout=180, **kwargs)
    if response.status_code >= 400:
        raise RuntimeError(f"{response.status_code} from {url}: {response.text[:1000]}")
    return response


def main() -> None:
    parser = argparse.ArgumentParser(description="Create Audioraq AI podcast QA episodes.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--public-origin", default=DEFAULT_PUBLIC_ORIGIN)
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--password", default=f"AudioraqQA!{int(time.time())}")
    parser.add_argument("--voice", default="Samantha")
    parser.add_argument("--remote", default=DEFAULT_SSH_HOST)
    parser.add_argument("--ssh-key", default=str(DEFAULT_SSH_KEY))
    parser.add_argument("--video-cover", default=str(DEFAULT_VIDEO_COVER))
    parser.add_argument("--limit", type=int, default=0, help="Optional number of episode specs to process.")
    parser.add_argument("--only-index", type=int, default=0, help="Process just one episode spec by index.")
    parser.add_argument("--dry-run", action="store_true", help="Generate local media and manifest without uploading.")
    args = parser.parse_args()

    run_id = time.strftime("%Y%m%d-%H%M%S")
    output_root = Path(args.output_root).resolve() / run_id
    scripts_dir = output_root / "scripts"
    media_dir = output_root / "media"
    output_root.mkdir(parents=True, exist_ok=True)
    scripts_dir.mkdir(parents=True, exist_ok=True)
    media_dir.mkdir(parents=True, exist_ok=True)

    base_url = args.base_url.rstrip("/")
    public_origin = args.public_origin.rstrip("/")
    video_cover = Path(args.video_cover).resolve()
    ssh_key = Path(args.ssh_key).expanduser().resolve()
    session = requests.Session()
    results: List[Dict[str, Any]] = []

    selected_specs = EPISODES
    if args.only_index:
        selected_specs = [spec for spec in EPISODES if spec.index == args.only_index]
        if not selected_specs:
            raise RuntimeError(f"No episode spec found for index {args.only_index}")
    elif args.limit:
        selected_specs = EPISODES[: max(1, args.limit)]

    for spec in selected_specs:
        slug = f"{spec.index:02d}-{slugify(spec.topic)}"
        email = f"aiagent-{run_id}-{spec.index:02d}@audioraq.test"
        token = ""
        show_id = ""
        draft = None

        if args.dry_run:
            generation = {}
            title = spec.topic
            description = f"QA draft for {spec.topic}."
        else:
            register_payload = {
                "email": email,
                "password": args.password,
                "name": f"Audioraq AI Agent {spec.index:02d}",
                "role": "podcaster",
                "phone": "",
                "podcast_description": f"QA show for {spec.niche}. This synthetic account validates Audioraq's Create with AI flow.",
                "show_title": spec.podcast_name,
            }
            register_res = api_post(session, f"{base_url}/api/auth/register", json=register_payload).json()
            token = register_res["access_token"]
            show_id = (register_res.get("primary_show") or {}).get("id", "")
            if not show_id:
                shows = session.get(f"{base_url}/api/shows/my", headers={"Authorization": f"Bearer {token}"}, timeout=60).json()
                show_id = shows["shows"][0]["id"]

            draft_payload = {"show_id": show_id, "intake": build_intake(spec)}
            draft = api_post(session, f"{base_url}/api/ai-podcast-drafts/generate", token=token, json=draft_payload).json()
            generation = draft.get("generation") or {}
            title = draft.get("publish_prefill", {}).get("title") or generation.get("episode_title") or spec.topic
            description = draft.get("publish_prefill", {}).get("description") or generation.get("suggested_description") or ""

        script = build_review_script(spec, generation)
        script_path = scripts_dir / f"{slug}.txt"
        script_path.write_text(script + "\n", encoding="utf-8")

        audio_path = media_dir / f"{slug}.wav"
        synthesize_audio(script_path, audio_path, args.voice)

        media_path = audio_path
        content_type = "audio/wav"
        if spec.media_kind == "video":
            media_path = media_dir / f"{slug}.mp4"
            make_video_with_remote_ffmpeg(audio_path, media_path, video_cover, args.remote, ssh_key, run_id)
            content_type = "video/mp4"

        episode = {}
        if not args.dry_run:
            with media_path.open("rb") as media_file:
                files = {
                    "file": (media_path.name, media_file, content_type),
                }
                data = {
                    "show_id": show_id,
                    "ai_draft_id": draft["id"],
                    "title": f"[QA] {title}",
                    "description": description,
                    "category": draft.get("recommended_category") or "general",
                    "audience_rating": "all_ages",
                    "episode_number": str(spec.index),
                    "season_number": "1",
                }
                episode = api_post(
                    session,
                    f"{base_url}/api/podcasts/upload",
                    token=token,
                    files=files,
                    data=data,
                ).json()

        episode_id = episode.get("id", "")
        episode_url = f"{public_origin}/episodes/{episode_id}" if episode_id else ""
        result = {
            "index": spec.index,
            "format": "audio only" if spec.media_kind == "audio" else "audio + video",
            "email": email,
            "password": args.password,
            "show_id": show_id,
            "draft_id": (draft or {}).get("id", ""),
            "episode_id": episode_id,
            "episode_url": episode_url,
            "title": episode.get("title") or f"[QA] {title}",
            "moderation_status": episode.get("moderation_status", ""),
            "media_type": episode.get("media_type") or spec.media_kind,
            "script_path": str(script_path),
            "media_path": str(media_path),
        }
        results.append(result)
        print(json.dumps(result, ensure_ascii=True), flush=True)

    manifest = {
        "run_id": run_id,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "base_url": base_url,
        "public_origin": public_origin,
        "dry_run": args.dry_run,
        "results": results,
    }
    manifest_path = output_root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    review_lines = [
        f"# Audioraq AI Podcast Creation Agent QA Run {run_id}",
        "",
        f"Base URL: {base_url}",
        f"Common test password: `{args.password}`",
        "",
        "| # | Format | Title | Account | Episode URL | Local Media | Script | Moderation |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for item in results:
        review_lines.append(
            "| {index} | {format} | {title} | `{email}` | {episode_url} | `{media_path}` | `{script_path}` | {moderation_status} |".format(
                **item
            )
        )
    review_path = output_root / "review.md"
    review_path.write_text("\n".join(review_lines) + "\n", encoding="utf-8")

    print(json.dumps({"manifest": str(manifest_path), "review": str(review_path)}, ensure_ascii=True))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"AI Podcast Creation Agent failed: {exc}", file=sys.stderr)
        sys.exit(1)
