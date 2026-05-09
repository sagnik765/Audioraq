#!/usr/bin/env python3
"""
Audioraq LinkedIn Marketing Agent.

This agent operates the founder-led LinkedIn growth system for Audioraq.
It creates strategy, post drafts, publish slots, engagement routines, and
queue-ready payloads that can be reviewed by a human before publishing.

It intentionally does not automate fake engagement, password-based browser
posting, or unsolicited spam. The durable growth engine is useful creator
education, product proof, founder conviction, and disciplined follow-up.
"""

from __future__ import annotations

import argparse
import csv
import json
import time
from dataclasses import asdict, dataclass
from datetime import date, datetime, time as dt_time, timedelta, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple
from zoneinfo import ZoneInfo


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "qa" / "audioraq-linkedin-marketing-agent"
DEFAULT_FOUNDER_LINKEDIN_URL = "https://www.linkedin.com/in/sagnik-roy-2001/"
DEFAULT_COMPANY_LINKEDIN_URL = "https://www.linkedin.com/company/audioraq/"
DEFAULT_PRODUCT_URL = "https://www.audioraq.com/?utm_campaign=linkedin_agent&utm_medium=social&utm_source=linkedin"
DEFAULT_TIMEZONE = "Asia/Kolkata"


POSITIONING = (
    "Audioraq is an AI-first podcast creation studio for serious creators. "
    "It helps podcasters plan, create, quality-check, publish, and improve "
    "show-first podcast workflows with Agentic AI quality gates."
)

FOUNDER_VOICE = (
    "Specific, warm, builder-led, and useful. The channel should sound like a "
    "founder teaching what he is learning while building Audioraq, not like a "
    "brand account shouting feature lists."
)

GUARDRAILS = [
    "No fake followers, fake comments, fake reviews, bought engagement, or mass unsolicited DMs.",
    "Every post should give readers a useful idea even if they never sign up.",
    "Every product claim should be backed by a visible workflow, screenshot, episode, or measurable proof point.",
    "The agent prepares and prioritizes work; a human reviews posts before they are published.",
    "Direct publishing should use the app's OAuth-backed social queue once LinkedIn permissions are connected.",
]

BEST_SLOT_RULES = [
    "Primary slot: Tuesday at 4:00 PM IST for founder/product insight.",
    "Primary slot: Thursday at 4:00 PM IST for demo/proof content.",
    "Primary slot: Friday at 3:00 PM IST for concise lessons and community prompts.",
    "If publishing four times in a week, add Wednesday at 4:00 PM IST.",
    "Avoid posting low-signal updates only because a slot exists.",
]


@dataclass(frozen=True)
class ContentPillar:
    key: str
    name: str
    goal: str
    investor_signal: str
    default_cta: str


@dataclass(frozen=True)
class PostBlueprint:
    pillar_key: str
    format: str
    headline: str
    hook: str
    body: str
    cta: str
    asset_brief: str
    hashtags: List[str]
    engagement_prompt: str


@dataclass(frozen=True)
class ScheduledPost:
    post_id: str
    publish_at_local: str
    publish_at_utc: str
    weekday: str
    channel_url: str
    company_page_url: str
    pillar: str
    format: str
    headline: str
    caption: str
    cta: str
    link_url: str
    hashtags: List[str]
    asset_brief: str
    engagement_prompt: str
    pre_publish_checklist: List[str]
    post_publish_checklist: List[str]


PILLARS: List[ContentPillar] = [
    ContentPillar(
        key="creator-pain",
        name="Creator Pain To Product Fix",
        goal="Show podcasters that Audioraq solves a painful workflow gap instead of adding another generic AI toy.",
        investor_signal="Sharp wedge, clear ICP, repeatable pain.",
        default_cta="If you are building a show, follow Audioraq for the systems we are learning.",
    ),
    ContentPillar(
        key="product-proof",
        name="Product Proof",
        goal="Make the product feel real through screenshots, workflows, episode pages, and quality scorecards.",
        investor_signal="Execution velocity and believable product differentiation.",
        default_cta="Try the workflow at Audioraq and tell us where it still feels too slow.",
    ),
    ContentPillar(
        key="creator-education",
        name="Creator Education",
        goal="Earn audience trust by teaching better podcast strategy, packaging, and publishing habits.",
        investor_signal="Category authority and audience pull.",
        default_cta="Save this if you are planning your next podcast episode.",
    ),
    ContentPillar(
        key="founder-conviction",
        name="Founder Conviction",
        goal="Explain why Audioraq exists and where the market is going.",
        investor_signal="Founder insight and long-term category clarity.",
        default_cta="If this future of podcasting feels right, follow along.",
    ),
    ContentPillar(
        key="audioraq-originals",
        name="Audioraq Originals Proof",
        goal="Use polished proof episodes as credibility instead of abstract claims.",
        investor_signal="Supply-side activation and product completeness.",
        default_cta="Listen to one Audioraq Original and tell us whether the quality bar feels high enough.",
    ),
    ContentPillar(
        key="listener-intelligence",
        name="Listener Intelligence",
        goal="Show that Audioraq is not only for creators; listeners get clearer discovery and episode understanding too.",
        investor_signal="Two-sided product potential and retention loops.",
        default_cta="What do you want to know before committing 30 minutes to an episode?",
    ),
]


POST_BLUEPRINTS: List[PostBlueprint] = [
    PostBlueprint(
        pillar_key="founder-conviction",
        format="Founder insight",
        headline="AI podcasting should not mean more slop",
        hook="The biggest problem with AI content is not that it is AI. It is that too much of it skips taste, structure, and quality control.",
        body=(
            "That is the belief behind Audioraq.\n\n"
            "We are not building a button that says 'make me a podcast' and floods the catalog.\n\n"
            "We are building a production workflow:\n"
            "1. choose the show direction\n"
            "2. shape the episode promise\n"
            "3. generate the audio package\n"
            "4. run Agentic AI quality gates\n"
            "5. publish into a real show structure\n\n"
            "The goal is not more content. The goal is better creator consistency."
        ),
        cta="If you are a podcaster or creator, what part of your workflow still feels too manual?",
        asset_brief="Text-first founder post with a simple yellow/black Audioraq quote card: 'Quality-controlled AI podcast creation.'",
        hashtags=["#podcasting", "#aiforcreators", "#buildinpublic", "#creatoreconomy"],
        engagement_prompt="Reply to every comment with one specific follow-up question about the creator's workflow.",
    ),
    PostBlueprint(
        pillar_key="creator-pain",
        format="Problem breakdown",
        headline="Most podcasters do not quit because they lack ideas",
        hook="They quit because the workflow turns one idea into seven separate jobs.",
        body=(
            "A serious podcast creator has to think about:\n\n"
            "Audience\n"
            "Topic selection\n"
            "Episode structure\n"
            "Recording quality\n"
            "Packaging\n"
            "Publishing\n"
            "Promotion\n"
            "Feedback\n\n"
            "Audioraq exists because those should not feel like disconnected chores.\n\n"
            "A creator should be able to run a show like a studio, even when they are a team of one."
        ),
        cta="Which part of podcast production slows you down the most?",
        asset_brief="Carousel: 7 workflow jobs on slide 1, Audioraq studio workflow on slide 2, CTA on slide 3.",
        hashtags=["#podcastcreator", "#creatorworkflow", "#startup", "#audioraq"],
        engagement_prompt="Invite podcasters in comments to name their slowest production step.",
    ),
    PostBlueprint(
        pillar_key="product-proof",
        format="Workflow demo",
        headline="The Audioraq workflow in one sentence",
        hook="Plan the show. Create the episode. Check the quality. Publish with context.",
        body=(
            "The product is moving toward one simple promise:\n\n"
            "A podcaster should not have to start from a blank page or stitch together five tools.\n\n"
            "Inside Audioraq, the workflow is:\n"
            "Show setup\n"
            "Season structure\n"
            "Create with AI\n"
            "Agentic AI quality review\n"
            "Episode detail page\n"
            "Listener feedback and analytics\n\n"
            "That is the studio system we are building."
        ),
        cta="If you want to test the workflow, visit Audioraq and send us the roughest part.",
        asset_brief="Use a 30 to 45 second screen recording or screenshot strip of Creator Studio to episode detail.",
        hashtags=["#productdemo", "#saas", "#podcastplatform", "#aiproduct"],
        engagement_prompt="Ask one founder or podcaster in the comments if this flow matches their current process.",
    ),
    PostBlueprint(
        pillar_key="creator-education",
        format="Creator lesson",
        headline="A good podcast episode needs a promise",
        hook="A topic is not enough. 'AI in finance' is a topic. 'How CFOs should think about AI risk in 2026' is a promise.",
        body=(
            "This is one of the biggest things we are building into Audioraq.\n\n"
            "Before the AI creates anything, the creator should know:\n"
            "Who is this for?\n"
            "What will they understand by the end?\n"
            "Why should they trust this episode?\n"
            "What should they do next?\n\n"
            "Better inputs create better podcast episodes.\n\n"
            "That sounds obvious, but most AI tools still make the creator do that thinking alone."
        ),
        cta="Steal this test: before recording, write the one-sentence promise of your episode.",
        asset_brief="Simple educational graphic: Topic vs Promise, with one before/after example.",
        hashtags=["#podcasttips", "#contentstrategy", "#creatoradvice", "#aiforcreators"],
        engagement_prompt="Ask commenters to share a topic and reply with a sharper episode promise.",
    ),
    PostBlueprint(
        pillar_key="audioraq-originals",
        format="Proof episode spotlight",
        headline="Proof-of-work matters more than product claims",
        hook="We are building Audioraq with published examples because creators should be able to hear the quality bar, not just read about it.",
        body=(
            "Audioraq Originals are our way of pressure-testing the product.\n\n"
            "Each proof episode helps us test:\n"
            "Voice listenability\n"
            "Script structure\n"
            "Topic selection\n"
            "Episode packaging\n"
            "Quality scoring\n"
            "Listener trust signals\n\n"
            "This keeps us honest.\n\n"
            "A podcast platform should not only look good in screenshots. It should sound good after 20 minutes."
        ),
        cta="If you listen to one Original, tell us where the voice or pacing still needs work.",
        asset_brief="Episode-card graphic using one polished Audioraq Original, quality score, and a short listener promise.",
        hashtags=["#podcasts", "#audioraqoriginals", "#creatorquality", "#ai"],
        engagement_prompt="Pin the strongest listener feedback as a public product-learning comment.",
    ),
    PostBlueprint(
        pillar_key="listener-intelligence",
        format="Listener insight",
        headline="Podcast discovery has a trust problem",
        hook="A title and thumbnail are not enough to know whether an episode is worth 45 minutes.",
        body=(
            "This is why Audioraq cannot only be AI-first for creators.\n\n"
            "Listeners need help too.\n\n"
            "The experience we want is:\n"
            "What is this episode really about?\n"
            "Why is it recommended to me?\n"
            "What are the key ideas?\n"
            "Can I ask a question before or after listening?\n\n"
            "Better discovery should feel less like doomscrolling and more like understanding."
        ),
        cta="Before you press play on a podcast, what information do you wish you had?",
        asset_brief="Graphic showing an episode detail page with quality, views, saves, ratings, and AI listener brief.",
        hashtags=["#podcastdiscovery", "#productdesign", "#listenerexperience", "#aiux"],
        engagement_prompt="Collect answers and convert the top 3 into a listener-experience roadmap post.",
    ),
    PostBlueprint(
        pillar_key="product-proof",
        format="Quality gate explainer",
        headline="Speed without quality control is not a creator advantage",
        hook="AI can help a creator move faster, but speed becomes dangerous if the output is tiring, unclear, or unsafe.",
        body=(
            "That is why Audioraq has quality gates in the podcast workflow.\n\n"
            "The system reviews:\n"
            "Clarity\n"
            "Listenability\n"
            "Safety risk\n"
            "Episode structure\n"
            "Improvement opportunities\n\n"
            "The point is not to pretend software can replace human taste.\n\n"
            "The point is to give creators a second set of eyes before publishing."
        ),
        cta="Would you trust a quality score before publishing, or would you want a human review option too?",
        asset_brief="Scorecard screenshot or mockup with five quality dimensions and a pass/fix recommendation.",
        hashtags=["#qualitycontrol", "#podcastproduction", "#aiworkflow", "#creatortools"],
        engagement_prompt="Separate replies from creators, listeners, and investors into three notes for the weekly review.",
    ),
    PostBlueprint(
        pillar_key="creator-education",
        format="Mini framework",
        headline="The 3-part test for a podcast idea",
        hook="Before you record, ask: is it useful, specific, and repeatable?",
        body=(
            "A podcast idea is stronger when it passes three checks:\n\n"
            "Useful: Does it help a specific listener make sense of something?\n"
            "Specific: Could someone else make the same episode from the same title? If yes, sharpen it.\n"
            "Repeatable: Can this episode fit into a show the audience will come back to?\n\n"
            "This is the kind of thinking Audioraq should help every creator do before generation starts."
        ),
        cta="Try it on your next episode title. If it feels generic, rewrite the promise.",
        asset_brief="Three-column yellow/black checklist graphic: Useful, Specific, Repeatable.",
        hashtags=["#contentcreation", "#podcaststrategy", "#creatorstudio", "#audioraq"],
        engagement_prompt="Offer to help rewrite 3 episode ideas in the comments.",
    ),
    PostBlueprint(
        pillar_key="founder-conviction",
        format="Build-in-public note",
        headline="What we are optimizing Audioraq for",
        hook="Not maximum AI output. Not vanity uploads. Not a content dump.",
        body=(
            "We are optimizing for:\n\n"
            "Time to first publishable episode\n"
            "Voice listenability over long sessions\n"
            "Show-level organization\n"
            "Creator trust in the quality workflow\n"
            "Listener confidence before pressing play\n\n"
            "If Audioraq gets those right, the product becomes more than a generator.\n\n"
            "It becomes an operating system for podcast creation."
        ),
        cta="If you were testing this product, which metric would you care about first?",
        asset_brief="Founder quote card with five metrics as small checkmarks.",
        hashtags=["#buildinpublic", "#startupmetrics", "#aistartup", "#podcasting"],
        engagement_prompt="Save every metric suggestion into the GTM/product feedback backlog.",
    ),
    PostBlueprint(
        pillar_key="creator-pain",
        format="Direct creator CTA",
        headline="Looking for 10 podcast creators to pressure-test Audioraq",
        hook="Not for polite feedback. For honest workflow feedback.",
        body=(
            "I am looking for creators who have either:\n\n"
            "Started a podcast and struggled to stay consistent\n"
            "Wanted to start a podcast but got stuck before episode one\n"
            "Already publish and want faster planning or packaging\n\n"
            "The ask is simple:\n"
            "Use Audioraq, create or upload an episode, and tell us exactly where it breaks your flow.\n\n"
            "That feedback is more valuable than vague praise."
        ),
        cta="Comment 'podcast' or message me if you want to test it.",
        asset_brief="Founder-led text post with a clean Audioraq creator beta card.",
        hashtags=["#podcasters", "#betatesting", "#founderled", "#creators"],
        engagement_prompt="Manually follow up with every qualified commenter within 24 hours.",
    ),
]


def timestamp() -> str:
    return time.strftime("%Y%m%d-%H%M%S", time.gmtime())


def get_zone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except Exception as exc:
        raise SystemExit(f"Unknown timezone '{name}'. Use a valid IANA timezone like Asia/Kolkata.") from exc


def parse_date(value: Optional[str]) -> date:
    if not value:
        return date.today() + timedelta(days=1)
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise SystemExit("--start-date must use YYYY-MM-DD format") from exc


def selected_slots(posts_per_week: int) -> Sequence[Tuple[int, dt_time]]:
    base_slots = [
        (1, dt_time(16, 0)),  # Tuesday
        (3, dt_time(16, 0)),  # Thursday
        (4, dt_time(15, 0)),  # Friday
        (2, dt_time(16, 0)),  # Wednesday
        (0, dt_time(16, 0)),  # Monday fallback
    ]
    return base_slots[: max(1, min(posts_per_week, len(base_slots)))]


def build_publish_datetimes(start: date, weeks: int, posts_per_week: int, tz: ZoneInfo) -> List[datetime]:
    total_posts = max(1, weeks) * max(1, posts_per_week)
    slot_map: Dict[int, List[dt_time]] = {}
    for weekday, publish_time in selected_slots(posts_per_week):
        slot_map.setdefault(weekday, []).append(publish_time)

    publish_datetimes: List[datetime] = []
    cursor = start
    search_limit = start + timedelta(days=max(weeks * 7 + 14, 21))
    while cursor <= search_limit and len(publish_datetimes) < total_posts:
        for publish_time in slot_map.get(cursor.weekday(), []):
            publish_datetimes.append(datetime.combine(cursor, publish_time, tzinfo=tz))
            if len(publish_datetimes) >= total_posts:
                break
        cursor += timedelta(days=1)

    return publish_datetimes


def pillar_by_key(key: str) -> ContentPillar:
    for pillar in PILLARS:
        if pillar.key == key:
            return pillar
    raise KeyError(key)


def build_caption(blueprint: PostBlueprint, pillar: ContentPillar) -> str:
    hashtags = " ".join(blueprint.hashtags)
    return "\n\n".join(
        [
            blueprint.hook,
            blueprint.body,
            blueprint.cta,
            hashtags,
        ]
    )


def build_scheduled_posts(
    publish_times: Sequence[datetime],
    channel_url: str,
    company_page_url: str,
    product_url: str,
) -> List[ScheduledPost]:
    posts: List[ScheduledPost] = []
    for index, publish_at in enumerate(publish_times, start=1):
        blueprint = POST_BLUEPRINTS[(index - 1) % len(POST_BLUEPRINTS)]
        pillar = pillar_by_key(blueprint.pillar_key)
        post_id = f"linkedin-{publish_at.strftime('%Y%m%d')}-{index:02d}"
        utc_publish = publish_at.astimezone(timezone.utc)
        posts.append(
            ScheduledPost(
                post_id=post_id,
                publish_at_local=publish_at.isoformat(),
                publish_at_utc=utc_publish.isoformat(),
                weekday=publish_at.strftime("%A"),
                channel_url=channel_url,
                company_page_url=company_page_url,
                pillar=pillar.name,
                format=blueprint.format,
                headline=blueprint.headline,
                caption=build_caption(blueprint, pillar),
                cta=blueprint.cta,
                link_url=product_url,
                hashtags=blueprint.hashtags,
                asset_brief=blueprint.asset_brief,
                engagement_prompt=blueprint.engagement_prompt,
                pre_publish_checklist=[
                    "Confirm the linked product flow is working.",
                    "Attach the matching screenshot, carousel, or short video if available.",
                    "Read the caption aloud once; remove anything that sounds like generic marketing.",
                    "Confirm the CTA asks for feedback, not fake engagement.",
                ],
                post_publish_checklist=[
                    "Reply to meaningful comments within the first 2 hours.",
                    "Save useful objections or questions into the feedback backlog.",
                    "Repost from the company page only if the founder post is performing or strategically important.",
                    "Log impressions, reactions, comments, reposts, profile visits, and follows after 24 hours.",
                ],
            )
        )
    return posts


def build_strategy_markdown(
    posts: Sequence[ScheduledPost],
    current_followers: Optional[int],
    target_followers: Optional[int],
) -> str:
    current = "unknown" if current_followers is None else str(current_followers)
    if target_followers is None:
        target = "current followers + 80 qualified followers in 30 days"
    else:
        target = str(target_followers)

    lines: List[str] = [
        "# Audioraq LinkedIn Marketing Agent",
        "",
        f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}",
        "",
        "## Mission",
        "",
        "Grow Audioraq from the founder's LinkedIn channel by turning product proof, creator education, and founder insight into repeatable audience growth.",
        "",
        "## Positioning",
        "",
        POSITIONING,
        "",
        "## Voice",
        "",
        FOUNDER_VOICE,
        "",
        "## 30-Day Target",
        "",
        f"- Current LinkedIn followers: {current}",
        f"- Target: {target}",
        "- Primary conversion: qualified creator conversations and creator signups, not vanity impressions.",
        "- Secondary conversion: profile follows from podcasters, creators, founders, and investor-adjacent operators.",
        "",
        "## Operating Guardrails",
        "",
    ]
    for item in GUARDRAILS:
        lines.append(f"- {item}")

    lines.extend(["", "## Best Publishing Slots", ""])
    for item in BEST_SLOT_RULES:
        lines.append(f"- {item}")

    lines.extend(["", "## Content Pillars", ""])
    for pillar in PILLARS:
        lines.extend(
            [
                f"### {pillar.name}",
                "",
                f"- Goal: {pillar.goal}",
                f"- Investor signal: {pillar.investor_signal}",
                f"- Default CTA: {pillar.default_cta}",
                "",
            ]
        )

    lines.extend(["## Daily Operating System", ""])
    daily_ops = [
        "Spend 10 minutes reading comments and DMs before creating anything new.",
        "Leave 3 thoughtful comments on podcaster, creator economy, audio, AI product, or startup posts. No pitching.",
        "If a post is scheduled today, publish only after checking the pre-publish checklist.",
        "Within 2 hours of posting, reply to every meaningful comment with a useful follow-up.",
        "Capture one audience question, objection, or phrase each day for future content.",
    ]
    for item in daily_ops:
        lines.append(f"- {item}")

    lines.extend(["", "## Weekly Review", ""])
    weekly_review = [
        "Pick the top post by comments and the top post by profile visits.",
        "Identify which hook format performed best: contrarian, framework, proof, or ask.",
        "Turn the best comment into next week's post.",
        "Send product-relevant feedback into the Audioraq feedback backlog.",
        "Kill formats that get impressions but no qualified creator conversations.",
    ]
    for item in weekly_review:
        lines.append(f"- {item}")

    lines.extend(["", "## Scheduled Posts", ""])
    for post in posts:
        lines.extend(
            [
                f"### {post.weekday} · {post.publish_at_local} · {post.headline}",
                "",
                f"- ID: {post.post_id}",
                f"- Pillar: {post.pillar}",
                f"- Format: {post.format}",
                f"- Link: {post.link_url}",
                f"- Asset: {post.asset_brief}",
                f"- Engagement: {post.engagement_prompt}",
                "",
                "Caption:",
                "",
                post.caption,
                "",
            ]
        )

    return "\n".join(lines)


def build_daily_ops_markdown(posts: Sequence[ScheduledPost]) -> str:
    lines = [
        "# LinkedIn Daily Ops",
        "",
        "Use this as the recurring operating checklist for the founder channel.",
        "",
        "## Every Weekday",
        "",
        "- Review comments and DMs before publishing anything new.",
        "- Leave 3 useful comments on relevant posts from creators, podcasters, founders, AI builders, and media operators.",
        "- Save one audience question or objection into the content backlog.",
        "- Do not pitch in comments unless someone asks directly.",
        "",
        "## On Publishing Days",
        "",
    ]
    for post in posts:
        lines.extend(
            [
                f"### {post.weekday} · {post.publish_at_local} · {post.headline}",
                "",
                "Pre-publish:",
            ]
        )
        for item in post.pre_publish_checklist:
            lines.append(f"- {item}")
        lines.append("")
        lines.append("Post-publish:")
        for item in post.post_publish_checklist:
            lines.append(f"- {item}")
        lines.append("")
    return "\n".join(lines)


def build_social_queue_payload(posts: Sequence[ScheduledPost]) -> List[Dict[str, object]]:
    payloads: List[Dict[str, object]] = []
    for post in posts:
        payloads.append(
            {
                "provider": "linkedin",
                "social_account_id": "",
                "headline": post.headline,
                "caption": post.caption,
                "cta": post.cta,
                "link_url": post.link_url,
                "hashtags": post.hashtags,
                "scheduled_at": post.publish_at_utc,
                "asset_url": "",
                "use_generated_card": True,
                "source": "audioraq_linkedin_marketing_agent",
                "status": "draft",
                "publish_now": False,
            }
        )
    return payloads


def write_posts_json(path: Path, posts: Sequence[ScheduledPost]) -> None:
    path.write_text(json.dumps([asdict(post) for post in posts], indent=2, ensure_ascii=True), encoding="utf-8")


def write_queue_json(path: Path, posts: Sequence[ScheduledPost]) -> None:
    path.write_text(json.dumps(build_social_queue_payload(posts), indent=2, ensure_ascii=True), encoding="utf-8")


def write_calendar_csv(path: Path, posts: Sequence[ScheduledPost]) -> None:
    fieldnames = [
        "post_id",
        "publish_at_local",
        "publish_at_utc",
        "weekday",
        "pillar",
        "format",
        "headline",
        "caption",
        "cta",
        "link_url",
        "hashtags",
        "asset_brief",
        "engagement_prompt",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for post in posts:
            writer.writerow(
                {
                    "post_id": post.post_id,
                    "publish_at_local": post.publish_at_local,
                    "publish_at_utc": post.publish_at_utc,
                    "weekday": post.weekday,
                    "pillar": post.pillar,
                    "format": post.format,
                    "headline": post.headline,
                    "caption": post.caption,
                    "cta": post.cta,
                    "link_url": post.link_url,
                    "hashtags": " ".join(post.hashtags),
                    "asset_brief": post.asset_brief,
                    "engagement_prompt": post.engagement_prompt,
                }
            )


def write_metrics_csv(path: Path, posts: Sequence[ScheduledPost]) -> None:
    fieldnames = [
        "post_id",
        "publish_at_local",
        "headline",
        "impressions_24h",
        "reactions_24h",
        "comments_24h",
        "reposts_24h",
        "profile_visits_24h",
        "new_followers_24h",
        "creator_conversations",
        "creator_signups",
        "top_learning",
        "next_action",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for post in posts:
            writer.writerow(
                {
                    "post_id": post.post_id,
                    "publish_at_local": post.publish_at_local,
                    "headline": post.headline,
                    "impressions_24h": "",
                    "reactions_24h": "",
                    "comments_24h": "",
                    "reposts_24h": "",
                    "profile_visits_24h": "",
                    "new_followers_24h": "",
                    "creator_conversations": "",
                    "creator_signups": "",
                    "top_learning": "",
                    "next_action": "",
                }
            )


def write_summary(path: Path, output_dir: Path, posts: Sequence[ScheduledPost], args: argparse.Namespace) -> None:
    summary = {
        "agent": "Audioraq LinkedIn Marketing Agent",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "output_dir": str(output_dir),
        "channel_url": args.channel_url,
        "company_page_url": args.company_page_url,
        "weeks": args.weeks,
        "posts_per_week": args.posts_per_week,
        "post_count": len(posts),
        "timezone": args.timezone,
        "product_url": args.product_url,
        "guardrails": GUARDRAILS,
        "outputs": [
            "linkedin_strategy.md",
            "linkedin_posts.json",
            "linkedin_calendar.csv",
            "linkedin_social_queue_payload.json",
            "linkedin_daily_ops.md",
            "linkedin_metrics_template.csv",
            "summary.json",
        ],
    }
    path.write_text(json.dumps(summary, indent=2, ensure_ascii=True), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a founder-led LinkedIn marketing operating system for Audioraq.")
    parser.add_argument("--start-date", default=None, help="First date to consider for scheduling, in YYYY-MM-DD. Defaults to tomorrow.")
    parser.add_argument("--weeks", type=int, default=4, help="Number of weeks to plan. Default: 4")
    parser.add_argument("--posts-per-week", type=int, default=3, help="LinkedIn posts per week. Default: 3")
    parser.add_argument("--timezone", default=DEFAULT_TIMEZONE, help="IANA timezone for local publishing slots. Default: Asia/Kolkata")
    parser.add_argument("--channel-url", default=DEFAULT_FOUNDER_LINKEDIN_URL, help="Founder LinkedIn URL to operate from")
    parser.add_argument("--company-page-url", default=DEFAULT_COMPANY_LINKEDIN_URL, help="Audioraq LinkedIn company page URL")
    parser.add_argument("--product-url", default=DEFAULT_PRODUCT_URL, help="UTM-tagged Audioraq URL for campaign CTAs")
    parser.add_argument("--current-followers", type=int, default=None, help="Current founder-channel follower count, if known")
    parser.add_argument("--target-followers", type=int, default=None, help="Optional target follower count for this campaign")
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT, help="Directory for generated agent outputs")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    tz = get_zone(args.timezone)
    start = parse_date(args.start_date)
    output_dir = args.output_root / timestamp()
    output_dir.mkdir(parents=True, exist_ok=True)

    publish_times = build_publish_datetimes(
        start=start,
        weeks=max(1, args.weeks),
        posts_per_week=max(1, args.posts_per_week),
        tz=tz,
    )
    posts = build_scheduled_posts(
        publish_times=publish_times,
        channel_url=args.channel_url,
        company_page_url=args.company_page_url,
        product_url=args.product_url,
    )

    (output_dir / "linkedin_strategy.md").write_text(
        build_strategy_markdown(posts, args.current_followers, args.target_followers),
        encoding="utf-8",
    )
    (output_dir / "linkedin_daily_ops.md").write_text(build_daily_ops_markdown(posts), encoding="utf-8")
    write_posts_json(output_dir / "linkedin_posts.json", posts)
    write_calendar_csv(output_dir / "linkedin_calendar.csv", posts)
    write_queue_json(output_dir / "linkedin_social_queue_payload.json", posts)
    write_metrics_csv(output_dir / "linkedin_metrics_template.csv", posts)
    write_summary(output_dir / "summary.json", output_dir, posts, args)

    print(f"Audioraq LinkedIn Marketing Agent created: {output_dir}")
    print("- linkedin_strategy.md")
    print("- linkedin_posts.json")
    print("- linkedin_calendar.csv")
    print("- linkedin_social_queue_payload.json")
    print("- linkedin_daily_ops.md")
    print("- linkedin_metrics_template.csv")
    print("- summary.json")


if __name__ == "__main__":
    main()
