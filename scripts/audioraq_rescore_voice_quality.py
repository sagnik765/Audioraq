#!/usr/bin/env python3
"""Re-score stored Agent 2 podcast voice reports with the current rubric.

This is intended for safe post-deploy maintenance: it does not touch media
objects and it does not rewrite episode copy. It only recalculates the nested
quality_agent.podcast_voice score from already-stored voice clarity metrics.
"""

from __future__ import annotations

import argparse
import asyncio
import copy
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from motor.motor_asyncio import AsyncIOMotorClient

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.voice_quality import score_podcast_voice_listenability


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def scorecard_item(score: Any, note: str) -> Dict[str, Any]:
    value = max(0.0, min(100.0, safe_float(score)))
    return {"score": round(value, 1), "note": note}


def build_media_analysis(quality_agent: Dict[str, Any]) -> Dict[str, Any]:
    voice_clarity = quality_agent.get("voice_clarity") or {}
    podcast_voice = quality_agent.get("podcast_voice") or {}
    metrics = podcast_voice.get("metrics") or {}
    gan_features = (quality_agent.get("gan_discriminator") or {}).get("features") or {}
    word_count = metrics.get("word_count") or gan_features.get("word_count") or 0
    return {
        "provider": voice_clarity.get("source_provider") or metrics.get("provider") or "",
        "word_count": word_count,
        "voice_clarity": voice_clarity,
    }


def profile_hint(existing_voice_review: Dict[str, Any]) -> str:
    profile = str(existing_voice_review.get("profile") or "").strip()
    if profile == "news_analysis":
        return "news analysis"
    return profile


def rebuild_quality_agent(
    episode: Dict[str, Any],
    min_score: float,
) -> tuple[Dict[str, Any], Dict[str, Any]]:
    quality_agent = copy.deepcopy(episode.get("quality_agent") or {})
    existing_voice_review = quality_agent.get("podcast_voice") or {}
    media_analysis = build_media_analysis(quality_agent)
    voice_context = {
        "format": profile_hint(existing_voice_review),
        "tone": profile_hint(existing_voice_review),
        "category": episode.get("category", ""),
        "show_title": episode.get("show_title", ""),
    }
    voice_review = score_podcast_voice_listenability(
        media_analysis,
        generation={},
        voice_context=voice_context,
        title=episode.get("title", ""),
        description=episode.get("description", ""),
    )

    old_score = existing_voice_review.get("listenability_score")
    new_score = voice_review.get("listenability_score")
    quality_agent["podcast_voice"] = voice_review

    scorecard = copy.deepcopy(quality_agent.get("scorecard") or {})
    if new_score is not None:
        scorecard["podcast_voice_listenability"] = scorecard_item(
            new_score,
            voice_review.get("summary") or "Long-form podcast voice listenability.",
        )
        readiness_inputs: List[float] = []
        for key, item in scorecard.items():
            if key == "publish_readiness" or not isinstance(item, dict):
                continue
            if item.get("score") is not None:
                readiness_inputs.append(safe_float(item.get("score")))
        if readiness_inputs:
            scorecard["publish_readiness"] = scorecard_item(
                sum(readiness_inputs) / len(readiness_inputs),
                "Combined Agent 2 signal for whether this can move toward publishing.",
            )
    quality_agent["scorecard"] = scorecard

    rlaif_score = safe_float((quality_agent.get("rlaif") or {}).get("reward_score"), 0)
    if new_score is not None and rlaif_score:
        quality_agent["quality_score"] = round((rlaif_score * 0.65) + (safe_float(new_score) * 0.35), 1)

    rag_status = (quality_agent.get("rag_safety") or {}).get("status", "")
    if rag_status == "blocked" or voice_review.get("status") == "revise":
        quality_agent["status"] = "revise"
    elif safe_float(new_score) >= min_score and quality_agent.get("status") != "blocked":
        quality_agent["status"] = "pass"

    clarity = quality_agent.get("voice_clarity") or {}
    clarity_summary = ""
    if clarity:
        clarity_summary = f"; voice clarity {clarity.get('score', 0)}/100 {clarity.get('status', '')}"
    voice_summary = ""
    if new_score is not None:
        voice_summary = f"; voice listenability {new_score}/100 {voice_review.get('status', '')}"
    gan = quality_agent.get("gan_discriminator") or {}
    quality_agent["summary"] = (
        f"Agent 2 quality score {quality_agent.get('quality_score', 0)}/100; "
        f"AI-risk {gan.get('label', 'unknown')} {gan.get('score', 'unknown')}; "
        f"RAG safety {rag_status or 'unknown'}{clarity_summary}{voice_summary}."
    )
    quality_agent["voice_rescored_at"] = now_iso()
    quality_agent["voice_rescore_note"] = "Recalculated with Audioraq long-form listenability threshold rubric."

    update_doc = {
        "quality_agent": quality_agent,
        "quality_score": quality_agent.get("quality_score", episode.get("quality_score", 0)),
        "quality_status": quality_agent.get("status", episode.get("quality_status", "")),
        "updated_at": now_iso(),
    }
    report = {
        "id": episode.get("id"),
        "title": episode.get("title", ""),
        "old_score": old_score,
        "new_score": new_score,
        "status": voice_review.get("status"),
        "meets_threshold": bool(new_score is not None and safe_float(new_score) >= min_score),
        "profile": voice_review.get("profile"),
        "summary": voice_review.get("summary", ""),
    }
    return update_doc, report


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mongo-url", default=os.environ.get("MONGO_URL", ""))
    parser.add_argument("--db-name", default=os.environ.get("DB_NAME", "audioraq"))
    parser.add_argument("--title-regex", default="^Audioraq Originals")
    parser.add_argument("--min-score", type=float, default=95.0)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    if not args.mongo_url:
        raise SystemExit("MONGO_URL is required.")

    client = AsyncIOMotorClient(args.mongo_url)
    db = client[args.db_name]
    query: Dict[str, Any] = {
        "is_deleted": False,
        "quality_agent.voice_clarity": {"$exists": True},
        "quality_agent.podcast_voice": {"$exists": True},
    }
    if args.title_regex:
        query["title"] = {"$regex": args.title_regex, "$options": "i"}

    cursor = db.podcasts.find(query).sort("created_at", 1)
    if args.limit > 0:
        cursor = cursor.limit(args.limit)

    reports: List[Dict[str, Any]] = []
    async for episode in cursor:
        update_doc, report = rebuild_quality_agent(episode, args.min_score)
        reports.append(report)
        if args.apply:
            await db.podcasts.update_one({"_id": episode["_id"]}, {"$set": update_doc})

    failures = [row for row in reports if not row["meets_threshold"]]
    result = {
        "apply": args.apply,
        "checked": len(reports),
        "threshold": args.min_score,
        "passing": len(reports) - len(failures),
        "failing": len(failures),
        "min_score": min((safe_float(row.get("new_score")) for row in reports), default=None),
        "failures": failures,
        "results": reports,
    }
    print(json.dumps(result, indent=2, default=str))
    if failures:
        raise SystemExit(2)


if __name__ == "__main__":
    asyncio.run(main())
