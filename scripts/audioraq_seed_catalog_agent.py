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
- Use --require-provider-kind elevenlabs for production proof-of-work runs so
  provider fallbacks are deleted instead of quietly seeding lower-quality audio.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import requests


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "qa" / "audioraq-seed-catalog-agent"
DEFAULT_BASE_URL = "https://www.audioraq.com"
DEFAULT_PUBLIC_ORIGIN = "https://www.audioraq.com"
DEFAULT_PASSWORD_PREFIX = "AudioraqSeed"
SHOW_EPISODE_COUNTS_275 = [17, 15, 14, 14, 13, 13, 12, 12, 12, 11, 11, 11, 11, 10, 10, 10, 10, 9, 9, 9, 9, 9, 8, 8, 8]


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


def api_post(session: requests.Session, url: str, token: str = "", **kwargs: Any) -> requests.Response:
    headers = kwargs.pop("headers", {})
    if token:
        headers["Authorization"] = f"Bearer {token}"
    response = session.post(url, headers=headers, timeout=360, **kwargs)
    if response.status_code >= 400:
        raise RuntimeError(f"{response.status_code} from {url}: {response.text[:1000]}")
    return response


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
    requested_media_kind = "audio" if global_index % 5 else "planned_video"
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
    show_episode_total = target_total - single_count
    if show_episode_total != 275:
        raise RuntimeError("This version is tuned for 275 show episodes plus 25 singles")
    plans: List[EpisodeBlueprint] = []
    global_index = 1
    for show_index, (show, episode_count) in enumerate(zip(SHOWS, SHOW_EPISODE_COUNTS_275), start=1):
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
    parser.add_argument("--target-total", type=int, default=300)
    parser.add_argument("--single-count", type=int, default=25)
    parser.add_argument("--start", type=int, default=1)
    parser.add_argument("--limit", type=int, default=1, help="Safety limit. Use 0 only when intentionally publishing the full selected range.")
    parser.add_argument("--publish", action="store_true", help="Actually create accounts, drafts, and episodes on the target Audioraq deployment.")
    parser.add_argument("--password", default="", help="Optional shared password for generated seed accounts.")
    parser.add_argument("--require-provider-kind", default="", help="If set, delete and reject episodes that publish with a different TTS provider kind.")
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    public_origin = args.public_origin.rstrip("/")
    password = args.password or f"{DEFAULT_PASSWORD_PREFIX}!{args.run_id}"
    output_dir = Path(args.output_root).resolve() / args.run_id
    plans = build_catalog_plan(target_total=args.target_total, single_count=args.single_count)
    selected = select_plans(plans, args.start, args.limit)
    session = requests.Session()
    account_cache: Dict[int, Dict[str, str]] = {}
    results = []

    for plan in selected:
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
            episode_result = create_ai_episode(session, base_url, public_origin, auth["token"], auth["show_id"], plan)
            result.update(episode_result)
            result["status"] = "published"
            required_provider = args.require_provider_kind.strip().lower()
            actual_provider = (episode_result.get("ai_audio_provider_kind") or "").strip().lower()
            if required_provider and actual_provider != required_provider:
                result["delete_result"] = delete_episode(session, base_url, auth["token"], episode_result["episode_id"])
                result["status"] = "deleted_provider_mismatch"
                result["provider_requirement"] = required_provider
            print(json.dumps(result, ensure_ascii=True), flush=True)
        else:
            print(json.dumps(result, ensure_ascii=True), flush=True)
        results.append(result)
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
                "safety_note": "Transparent Audioraq Originals seed content. No fake reviews or fake customer claims.",
                "constraints": [
                    "Create with AI publishes audio-only episodes.",
                    "Single episodes use one-episode capsule shows because the data model is show-first.",
                    "Default distribution is 275 show episodes plus 25 singles, totaling 300.",
                ],
                "results": results,
            },
        )

    print(json.dumps({"output_dir": str(output_dir), "published": args.publish, "processed": len(results)}, ensure_ascii=True))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Audioraq Seed Catalog Agent failed: {exc}", file=sys.stderr)
        sys.exit(1)
