#!/usr/bin/env python3
"""Publish improved Podcast Improvement Agent media to Audioraq."""

from __future__ import annotations

import argparse
import json
import mimetypes
import time
from pathlib import Path
from typing import Any, Dict

import requests


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ORIGINAL_MANIFEST = REPO_ROOT / "qa" / "ai-podcast-agent" / "20260411-113544" / "manifest.json"
DEFAULT_IMPROVED_MANIFEST = REPO_ROOT / "qa" / "podcast-improvement-agent" / "20260411-124502" / "manifest.json"
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "qa" / "published-improved-podcasts"


def post(session: requests.Session, url: str, token: str = "", **kwargs: Any) -> requests.Response:
    headers = kwargs.pop("headers", {})
    if token:
        headers["Authorization"] = f"Bearer {token}"
    response = session.post(url, headers=headers, timeout=240, **kwargs)
    if response.status_code >= 400:
        raise RuntimeError(f"{response.status_code} from {url}: {response.text[:1000]}")
    return response


def get(session: requests.Session, url: str, token: str = "") -> requests.Response:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    response = session.get(url, headers=headers, timeout=120)
    if response.status_code >= 400:
        raise RuntimeError(f"{response.status_code} from {url}: {response.text[:1000]}")
    return response


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish improved dialogue QA podcasts.")
    parser.add_argument("--base-url", default="https://www.audioraq.com")
    parser.add_argument("--original-manifest", default=str(DEFAULT_ORIGINAL_MANIFEST))
    parser.add_argument("--improved-manifest", default=str(DEFAULT_IMPROVED_MANIFEST))
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--start-index", type=int, default=1)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--title-prefix", default="[QA Dialogue]")
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    original_manifest = json.loads(Path(args.original_manifest).read_text(encoding="utf-8"))
    improved_manifest = json.loads(Path(args.improved_manifest).read_text(encoding="utf-8"))
    originals_by_index = {int(item["index"]): item for item in original_manifest["results"]}

    run_id = time.strftime("%Y%m%d-%H%M%S")
    output_root = Path(args.output_root).resolve() / run_id
    output_root.mkdir(parents=True, exist_ok=True)
    published = []

    selected = [item for item in improved_manifest["results"] if int(item["index"]) >= args.start_index]
    selected = selected[: args.limit or None]
    for improved in selected:
        index = int(improved["index"])
        original = originals_by_index[index]
        session = requests.Session()

        login = post(
            session,
            f"{base_url}/api/auth/login",
            json={"email": original["email"], "password": original["password"]},
        ).json()
        token = login["access_token"]

        original_episode = get(session, f"{base_url}/api/podcasts/{original['episode_id']}", token=token).json()
        media_path = Path(improved["improved_media_path"])
        if not media_path.exists():
            raise RuntimeError(f"Improved media file not found: {media_path}")

        if media_path.suffix.lower() == ".wav":
            content_type = "audio/wav"
        elif media_path.suffix.lower() == ".mp4":
            content_type = "video/mp4"
        else:
            content_type = mimetypes.guess_type(media_path.name)[0] or "application/octet-stream"
        clean_title = improved["title"].replace("[QA]", "").strip()
        title = f"{args.title_prefix} {clean_title}"
        description = (
            f"Dialogue-based improved QA cut for Audioraq.\n\n"
            f"Original episode: {original['episode_url']}\n"
            f"GAN-style discriminator: {improved['before_ai_detector']['label']} {improved['before_ai_detector']['score']} "
            f"-> {improved['after_ai_detector']['label']} {improved['after_ai_detector']['score']}.\n"
            f"Benchmark similarity: {improved['after_ai_detector']['benchmark_similarity']}.\n"
            f"RAG safety check: {improved['rag_safety']['status']}.\n\n"
            f"Visual style: {improved.get('visual_style', 'Dialogue-focused media cut')}.\n\n"
            f"{original_episode.get('description') or ''}"
        ).strip()

        with media_path.open("rb") as media_file:
            response = post(
                session,
                f"{base_url}/api/podcasts/upload",
                token=token,
                files={"file": (media_path.name, media_file, content_type)},
                data={
                    "show_id": original["show_id"],
                    "ai_draft_id": original["draft_id"],
                    "title": title,
                    "description": description,
                    "category": original_episode.get("category") or "general",
                    "audience_rating": original_episode.get("audience_rating") or "all_ages",
                    "season_number": "2",
                    "episode_number": str(index),
                },
            ).json()

        item = {
            "index": index,
            "format": improved["format"],
            "email": original["email"],
            "original_episode_url": original["episode_url"],
            "published_episode_id": response["id"],
            "published_episode_url": f"{base_url}/episodes/{response['id']}",
            "title": response["title"],
            "media_type": response["media_type"],
            "moderation_status": response.get("moderation_status", ""),
            "benchmark_similarity": improved["after_ai_detector"]["benchmark_similarity"],
            "ai_risk_before": improved["before_ai_detector"],
            "ai_risk_after": improved["after_ai_detector"],
        }
        published.append(item)
        print(json.dumps(item, ensure_ascii=True), flush=True)

    manifest = {
        "run_id": run_id,
        "base_url": base_url,
        "original_manifest": str(Path(args.original_manifest).resolve()),
        "improved_manifest": str(Path(args.improved_manifest).resolve()),
        "published": published,
    }
    manifest_path = output_root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    review_lines = [
        f"# Published Improved Dialogue Podcasts {run_id}",
        "",
        "| # | Format | Title | URL | Media Type | Moderation | Benchmark Similarity |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for item in published:
        review_lines.append(
            f"| {item['index']} | {item['format']} | {item['title']} | {item['published_episode_url']} | {item['media_type']} | {item['moderation_status']} | {item['benchmark_similarity']} |"
        )
    review_path = output_root / "review.md"
    review_path.write_text("\n".join(review_lines) + "\n", encoding="utf-8")
    print(json.dumps({"manifest": str(manifest_path), "review": str(review_path)}, ensure_ascii=True))


if __name__ == "__main__":
    main()
