#!/usr/bin/env python3
"""
Audioraq Marketing Agent.

This agent creates an ethical, proof-of-work-driven growth campaign for
Audioraq's LinkedIn and Instagram presence.

Important constraints:
- It does not buy followers, fake engagement, or generate spam outreach.
- It does not post directly to LinkedIn or Instagram because those platform
  integrations are not connected in this repository.
- It produces the strategy, content calendar, post drafts, asset briefs,
  experiments, and scorecards needed to grow followers in a repeatable way.
"""

from __future__ import annotations

import argparse
import csv
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "qa" / "audioraq-marketing-agent"
DEFAULT_LINKEDIN_URL = "https://www.linkedin.com/company/audioraq/"
DEFAULT_INSTAGRAM_URL = "https://www.instagram.com/audioraq"
INTELLIGENCE_MEMO = REPO_ROOT / "marketing" / "audioraq_competitive_intelligence.md"

PRODUCT_POSITIONING = (
    "Audioraq is an AI-first podcasting platform built around a show-first "
    "workflow. It helps podcasters move from idea to polished published episode "
    "with AI strategy, creation, quality review, and packaging, while giving "
    "listeners AI-powered episode understanding and intentional discovery."
)

PRODUCT_PROOF_POINTS = [
    "Show-first catalog structure: Show > Season > Episode",
    "Create with AI for audio-first podcast creation",
    "Agent 2 quality gates for safety, quality, and listenability",
    "AI Strategist for podcasters to decide what to publish next",
    "AI Listener Brief and Ask this Episode for viewers",
    "Proof-of-work catalog via Audioraq Originals",
]


@dataclass(frozen=True)
class PlatformProfile:
    platform: str
    url: str
    current_followers: Optional[int]
    monthly_target: int
    content_goal: str
    cadence: str
    voice: str


@dataclass(frozen=True)
class ContentPillar:
    key: str
    name: str
    audience_value: str
    investor_signal: str
    proof_asset: str
    cta: str


@dataclass(frozen=True)
class PostDraft:
    day: int
    week: int
    platform: str
    format: str
    pillar: str
    objective: str
    headline: str
    hook: str
    angle: str
    caption: str
    cta: str
    asset_brief: str
    hashtags: List[str]
    follow_up: str


@dataclass(frozen=True)
class WeeklyExperiment:
    week: int
    name: str
    hypothesis: str
    success_metric: str
    action_plan: str


PILLARS: List[ContentPillar] = [
    ContentPillar(
        "creator-pain",
        "Creator pain -> product fix",
        "Shows podcasters that Audioraq solves painful workflow gaps instead of adding AI fluff.",
        "Signals a sharp creator wedge and clear problem/solution fit.",
        "screen recording of Creator Studio or publish flow",
        "Follow Audioraq for practical creator systems and product drops.",
    ),
    ContentPillar(
        "proof-of-work",
        "Proof of work and product demos",
        "Makes the product feel real because viewers can see live workflows and real episodes.",
        "Signals product execution and user-believable differentiation.",
        "UI walkthrough, published episode page, quality report screenshot",
        "Follow to watch the product improve in public.",
    ),
    ContentPillar(
        "audioraq-originals",
        "Audioraq Originals showcase",
        "Uses the catalog as credibility instead of saying 'trust us.'",
        "Signals supply-side activation and product completeness.",
        "episode artwork, show page, short clip transcript, quality score card",
        "Follow for new Originals and behind-the-scenes breakdowns.",
    ),
    ContentPillar(
        "industry-insight",
        "Podcasting insight and teardown",
        "Earns followers with useful ideas even before they become users.",
        "Signals founder clarity, market understanding, and category leadership.",
        "carousel or text-first post with 3-5 takeaways",
        "Follow if you care about the future of podcast creation.",
    ),
    ContentPillar(
        "build-in-public",
        "Build in public",
        "Humanizes the company and creates narrative momentum around the startup journey.",
        "Signals velocity and founder-market learning.",
        "founder note, product changelog, experiment result, feature screenshot",
        "Follow to see what we ship next.",
    ),
]


LINKEDIN_TEMPLATES = [
    {
        "format": "Founder post",
        "objective": "Earn trust with a sharp creator insight.",
        "headline": "Why most podcast AI tools still feel like assistants, not a studio team",
        "hook": "Most podcast tools help you upload. Very few help you decide what to make, polish it, and publish it with confidence.",
        "angle": "Position Audioraq around the show-first workflow and AI studio value chain.",
        "caption": (
            "We keep noticing the same thing: most podcasters do not need more surfaces to upload files. "
            "They need help deciding what to make, turning that into a strong episode, and shipping it without the quality dropping.\n\n"
            "That is the bet behind Audioraq.\n\n"
            "Our wedge is not 'AI content.' It is AI strategy + AI creation + quality gates + show-first publishing.\n\n"
            "If you are building or running a podcast, what part of the workflow still takes too much time?"
        ),
        "hashtags": ["#podcasting", "#creatoreconomy", "#aiproduct", "#buildinpublic"],
        "follow_up": "Reply to every creator comment with one useful follow-up question.",
    },
    {
        "format": "Demo post",
        "objective": "Convert curiosity into profile follows via product proof.",
        "headline": "From idea to AI brief to published episode in one workflow",
        "hook": "We built Audioraq so a podcaster can move from 'what should I publish next?' to a real episode draft without juggling five tools.",
        "angle": "Show the AI Strategist -> Create with AI handoff.",
        "caption": (
            "A lot of creator tools stop at generation.\n\n"
            "We wanted the opposite.\n\n"
            "In Audioraq, the flow now looks like this:\n"
            "1. AI Strategist suggests what the show should publish next\n"
            "2. The creator sends that idea straight into Create with AI\n"
            "3. Agent 2 reviews quality before it reaches listeners\n\n"
            "That is closer to a studio team than a text box."
        ),
        "hashtags": ["#podcastcreator", "#productdemo", "#aiworkflow", "#creatortools"],
        "follow_up": "DM the post to 5 founder or creator friends who already talk about podcasting workflows.",
    },
    {
        "format": "Teardown post",
        "objective": "Grow through educational value, not pure product pitch.",
        "headline": "3 things podcast creators actually need from AI",
        "hook": "The boring answer is the right one: podcasters usually need AI to reduce friction, not add novelty.",
        "angle": "Teach with a plain-language framework that also maps to Audioraq's product.",
        "caption": (
            "If I had to compress creator-side AI value into 3 needs, it would be:\n\n"
            "1. Better decisions about what to make next\n"
            "2. Faster movement from outline to publishable package\n"
            "3. Quality protection so speed does not destroy trust\n\n"
            "That framework has become a useful filter for what we build into Audioraq and what we ignore."
        ),
        "hashtags": ["#aiforcreators", "#podcaststrategy", "#saasfounder"],
        "follow_up": "Turn the best comment into next week's carousel or founder note.",
    },
    {
        "format": "Listener insight",
        "objective": "Broaden the story beyond creation while keeping the wedge sharp.",
        "headline": "What if podcast discovery felt less like doomscrolling and more like understanding?",
        "hook": "We are experimenting with AI for listeners in a very specific way: not more noise, more clarity.",
        "angle": "Introduce the AI Listener Brief and Ask this Episode features.",
        "caption": (
            "On the viewer side, the most interesting AI question is not 'can it chat?' It is 'can it help me decide faster?'\n\n"
            "That is why Audioraq now adds:\n"
            "- an AI Listener Brief before playback\n"
            "- Ask this Episode for grounded Q&A\n\n"
            "The idea is simple: help someone understand whether an episode is worth their time before they commit 30 minutes."
        ),
        "hashtags": ["#productdesign", "#podcastapp", "#aiexperience"],
        "follow_up": "Ask followers what they want to know before pressing play on a podcast episode.",
    },
]


INSTAGRAM_TEMPLATES = [
    {
        "format": "Carousel",
        "objective": "Drive saves and follows through clear creator education.",
        "headline": "Podcast creation is broken in 5 places",
        "hook": "Uploading is not the hard part.",
        "angle": "List the workflow gaps and end with how Audioraq addresses them.",
        "caption": (
            "Most podcast pain happens before and after recording.\n\n"
            "Ideas drift.\n"
            "Packaging gets rushed.\n"
            "Publishing feels fragmented.\n"
            "Quality gets inconsistent.\n"
            "Discovery becomes guesswork.\n\n"
            "That is the problem Audioraq is trying to solve."
        ),
        "hashtags": ["#podcastcreator", "#creatorworkflow", "#audioraq", "#contentstudio"],
        "follow_up": "Reply to every comment with the slide number that answers the question best.",
    },
    {
        "format": "Reel",
        "objective": "Create product curiosity with quick proof.",
        "headline": "Idea -> AI Strategist -> Create with AI",
        "hook": "This is how a podcast episode moves through Audioraq in seconds.",
        "angle": "Fast screen recording with on-screen captions.",
        "caption": (
            "We want podcast creation to feel like running a studio, not juggling tabs.\n\n"
            "This reel shows the flow from show strategy into Create with AI.\n\n"
            "Follow if you want to watch Audioraq keep shipping."
        ),
        "hashtags": ["#podcastreel", "#aicreator", "#startupbuild", "#creatortech"],
        "follow_up": "Post the same reel to Stories with a poll: 'Would this help your workflow?'",
    },
    {
        "format": "Carousel",
        "objective": "Position the brand as useful even for non-users.",
        "headline": "3 ways to make AI podcast output feel less generic",
        "hook": "The goal is not to sound more AI. It is to sound more intentional.",
        "angle": "Teach specificity, structure, and quality review.",
        "caption": (
            "If you use AI for podcast creation, push harder on:\n"
            "1. audience clarity\n"
            "2. a single episode promise\n"
            "3. quality review before publish\n\n"
            "That is a much better path than asking for a 'viral script.'"
        ),
        "hashtags": ["#podcasttips", "#aipodcasting", "#creatoradvice"],
        "follow_up": "Turn the second slide into a standalone Story card later that day.",
    },
    {
        "format": "Behind-the-scenes Reel",
        "objective": "Humanize the startup and create narrative continuity.",
        "headline": "What we shipped this week at Audioraq",
        "hook": "We are building this in public, feature by feature.",
        "angle": "Quick changelog with motion and product UI.",
        "caption": (
            "This week at Audioraq:\n"
            "- AI Listener Brief\n"
            "- Ask this Episode\n"
            "- AI Strategist for creators\n\n"
            "Small steps, but the product is getting closer to what we believe podcasting should feel like."
        ),
        "hashtags": ["#buildinpublic", "#startupjourney", "#saasbuilder", "#audioraq"],
        "follow_up": "Save the top comments as raw material for next week's educational post.",
    },
    {
        "format": "Social proof carousel",
        "objective": "Make the product feel credible without fake hype.",
        "headline": "What makes Audioraq different",
        "hook": "Not another upload shelf.",
        "angle": "Compare show-first workflow, AI strategy, and quality gates to generic tooling.",
        "caption": (
            "The category is crowded, so the product has to be specific.\n\n"
            "Audioraq is strongest when it feels like:\n"
            "- a studio team for podcasters\n"
            "- an understanding layer for listeners\n"
            "- a show-first workflow instead of a file dump"
        ),
        "hashtags": ["#podcastplatform", "#productpositioning", "#creatorstartup"],
        "follow_up": "Pin the best-performing carousel after the first 2 weeks.",
    },
]


def timestamp() -> str:
    return time.strftime("%Y%m%d-%H%M%S", time.gmtime())


def follower_target(current: Optional[int], platform: str) -> int:
    if current is None:
        return 150 if platform == "linkedin" else 300
    growth_floor = 80 if platform == "linkedin" else 150
    return current + max(growth_floor, int(current * 0.25))


def build_profiles(linkedin_followers: Optional[int], instagram_followers: Optional[int]) -> List[PlatformProfile]:
    return [
        PlatformProfile(
            platform="linkedin",
            url=DEFAULT_LINKEDIN_URL,
            current_followers=linkedin_followers,
            monthly_target=follower_target(linkedin_followers, "linkedin"),
            content_goal="Earn trust with creator insights, product demos, and founder thinking.",
            cadence="3 company posts + 2 founder amplification moments per week",
            voice="clear, credible, specific, founder-led",
        ),
        PlatformProfile(
            platform="instagram",
            url=DEFAULT_INSTAGRAM_URL,
            current_followers=instagram_followers,
            monthly_target=follower_target(instagram_followers, "instagram"),
            content_goal="Turn product workflows and creator lessons into short visual hooks people save and share.",
            cadence="4 feed posts/reels + 5 stories per week",
            voice="punchy, visual, practical, high-signal",
        ),
    ]


def pillar_lookup() -> Dict[str, ContentPillar]:
    return {pillar.key: pillar for pillar in PILLARS}


def linkedin_post_for_day(day: int, week: int, template_index: int, pillar_key: str) -> PostDraft:
    template = LINKEDIN_TEMPLATES[template_index % len(LINKEDIN_TEMPLATES)]
    pillar = pillar_lookup()[pillar_key]
    return PostDraft(
        day=day,
        week=week,
        platform="LinkedIn",
        format=template["format"],
        pillar=pillar.name,
        objective=template["objective"],
        headline=template["headline"],
        hook=template["hook"],
        angle=template["angle"],
        caption=template["caption"],
        cta=pillar.cta,
        asset_brief=f"Use {pillar.proof_asset}. End card should say: {pillar.cta}",
        hashtags=template["hashtags"],
        follow_up=template["follow_up"],
    )


def instagram_post_for_day(day: int, week: int, template_index: int, pillar_key: str) -> PostDraft:
    template = INSTAGRAM_TEMPLATES[template_index % len(INSTAGRAM_TEMPLATES)]
    pillar = pillar_lookup()[pillar_key]
    return PostDraft(
        day=day,
        week=week,
        platform="Instagram",
        format=template["format"],
        pillar=pillar.name,
        objective=template["objective"],
        headline=template["headline"],
        hook=template["hook"],
        angle=template["angle"],
        caption=template["caption"],
        cta=pillar.cta,
        asset_brief=f"Build a vertical asset using {pillar.proof_asset}. Make the first frame stop the scroll in under 2 seconds.",
        hashtags=template["hashtags"],
        follow_up=template["follow_up"],
    )


def build_posts(days: int) -> List[PostDraft]:
    posts: List[PostDraft] = []
    linkedin_pillars = ["creator-pain", "proof-of-work", "industry-insight", "build-in-public"]
    instagram_pillars = ["creator-pain", "proof-of-work", "audioraq-originals", "build-in-public", "industry-insight"]

    for day in range(1, days + 1):
        week = ((day - 1) // 7) + 1
        weekday = (day - 1) % 7

        if weekday in {0, 2, 4}:  # Mon, Wed, Fri
            posts.append(
                linkedin_post_for_day(
                    day,
                    week,
                    template_index=(day + week) % len(LINKEDIN_TEMPLATES),
                    pillar_key=linkedin_pillars[(day + week) % len(linkedin_pillars)],
                )
            )

        if weekday in {1, 2, 4, 6}:  # Tue, Wed, Fri, Sun
            posts.append(
                instagram_post_for_day(
                    day,
                    week,
                    template_index=(day * 2 + week) % len(INSTAGRAM_TEMPLATES),
                    pillar_key=instagram_pillars[(day + week * 2) % len(instagram_pillars)],
                )
            )

    return sorted(posts, key=lambda item: (item.day, item.platform))


def build_experiments() -> List[WeeklyExperiment]:
    return [
        WeeklyExperiment(
            week=1,
            name="Profile clarity upgrade",
            hypothesis="Cleaner bios, banner copy, and pinned posts will improve profile-to-follow conversion immediately.",
            success_metric="Higher profile visits -> follows ratio on both platforms.",
            action_plan="Refresh banner, bio, pinned LinkedIn post, pinned Instagram reel, and highlight covers before posting the first content block.",
        ),
        WeeklyExperiment(
            week=2,
            name="Demo-first posts",
            hypothesis="Concrete product proof will outperform generic founder commentary for net follower growth.",
            success_metric="Post saves, shares, and new follows from demo posts vs founder-only posts.",
            action_plan="Publish one strong product walkthrough on LinkedIn and one fast UI reel on Instagram, then compare saves and follows.",
        ),
        WeeklyExperiment(
            week=3,
            name="Comment-to-content loop",
            hypothesis="Turning real questions into follow-up posts will improve relevance and comment depth.",
            success_metric="Average comments per post and quality of inbound creator conversations.",
            action_plan="Collect the top 10 comments and DMs from weeks 1-2, then build 3 posts directly from those questions.",
        ),
        WeeklyExperiment(
            week=4,
            name="Proof-of-work spotlight",
            hypothesis="Featuring Audioraq Originals and AI workflow outputs will build more trust than abstract positioning alone.",
            success_metric="Follower lift and profile visits on showcase posts vs theory posts.",
            action_plan="Package one strong Audioraq Originals episode or workflow case study into a LinkedIn carousel and Instagram reel.",
        ),
    ]


def build_profile_upgrade_notes() -> Dict[str, List[str]]:
    return {
        "linkedin": [
            "Banner copy should say what Audioraq does in one sentence: AI-first podcast creation and listening, built around a show-first workflow.",
            "Pinned company post should be a clean product demo or proof-of-work case study, not a generic welcome post.",
            "Founder should repost company posts with a personal, operator-level angle instead of copying the same caption.",
            "Every LinkedIn post should end with one question or sharp CTA that invites creator replies.",
        ],
        "instagram": [
            "Bio should make the product legible fast: AI-first podcast creation studio plus smart listening layer.",
            "Pin 3 posts: a product reel, a creator-education carousel, and one proof-of-work showcase.",
            "Create Highlights for Product, Originals, Build, and Creator Tips.",
            "Stories should be used for polls, behind-the-scenes snippets, and soft CTAs back to the profile.",
        ],
    }


def build_engagement_loops() -> List[str]:
    return [
        "Spend 20 minutes each weekday leaving thoughtful comments on podcaster, creator-tools, and media-workflow posts. Do not sell in the comments.",
        "Turn one question from comments or DMs into one new post every week.",
        "Use company-page posts for product proof and founder posts for interpretation, lessons, and conviction.",
        "At the end of each week, identify the top save/share post and create one sequel post while the topic is still warm.",
        "Use new product launches and strong Audioraq Originals episodes as campaign anchors, not just random social content.",
    ]


def build_kpis(profiles: Iterable[PlatformProfile]) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    for profile in profiles:
        rows.append(
            {
                "platform": profile.platform,
                "current_followers": "" if profile.current_followers is None else str(profile.current_followers),
                "monthly_target_followers": str(profile.monthly_target),
                "impressions": "",
                "profile_visits": "",
                "new_followers": "",
                "engagement_rate": "",
                "saves": "",
                "shares": "",
                "comments": "",
                "top_post_url": "",
                "notes": "",
            }
        )
    return rows


def write_markdown(
    output_path: Path,
    profiles: List[PlatformProfile],
    posts: List[PostDraft],
    experiments: List[WeeklyExperiment],
) -> None:
    lines: List[str] = [
        "# Audioraq Marketing Agent Campaign",
        "",
        f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}",
        "",
        "## Positioning",
        "",
        PRODUCT_POSITIONING,
        "",
        "## Product Proof",
        "",
    ]
    for proof in PRODUCT_PROOF_POINTS:
        lines.append(f"- {proof}")

    lines.extend(["", "## Platform Targets", ""])
    for profile in profiles:
        current = "unknown" if profile.current_followers is None else str(profile.current_followers)
        lines.extend(
            [
                f"### {profile.platform.title()}",
                "",
                f"- URL: {profile.url}",
                f"- Current followers: {current}",
                f"- 30-day target: {profile.monthly_target}",
                f"- Content goal: {profile.content_goal}",
                f"- Cadence: {profile.cadence}",
                f"- Voice: {profile.voice}",
                "",
            ]
        )

    lines.extend(["## Profile Upgrades", ""])
    profile_notes = build_profile_upgrade_notes()
    for platform, notes in profile_notes.items():
        lines.append(f"### {platform.title()}")
        lines.append("")
        for note in notes:
            lines.append(f"- {note}")
        lines.append("")

    lines.extend(["## Weekly Experiments", ""])
    for experiment in experiments:
        lines.extend(
            [
                f"### Week {experiment.week}: {experiment.name}",
                "",
                f"- Hypothesis: {experiment.hypothesis}",
                f"- Success metric: {experiment.success_metric}",
                f"- Action plan: {experiment.action_plan}",
                "",
            ]
        )

    lines.extend(["## Engagement Loops", ""])
    for item in build_engagement_loops():
        lines.append(f"- {item}")

    lines.extend(["", "## 30-Day Content Calendar", ""])
    current_week = None
    for post in posts:
        if post.week != current_week:
            current_week = post.week
            lines.extend([f"### Week {current_week}", ""])
        lines.extend(
            [
                f"#### Day {post.day} · {post.platform} · {post.format}",
                "",
                f"- Pillar: {post.pillar}",
                f"- Objective: {post.objective}",
                f"- Headline: {post.headline}",
                f"- Hook: {post.hook}",
                f"- Angle: {post.angle}",
                f"- CTA: {post.cta}",
                f"- Asset brief: {post.asset_brief}",
                f"- Hashtags: {' '.join(post.hashtags)}",
                f"- Follow-up: {post.follow_up}",
                "",
                "Caption:",
                "",
                post.caption,
                "",
            ]
        )

    output_path.write_text("\n".join(lines), encoding="utf-8")


def write_posts_json(output_path: Path, posts: List[PostDraft]) -> None:
    output_path.write_text(
        json.dumps([asdict(post) for post in posts], indent=2, ensure_ascii=True),
        encoding="utf-8",
    )


def write_kpi_csv(output_path: Path, rows: List[Dict[str, str]]) -> None:
    fieldnames = list(rows[0].keys()) if rows else []
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_calendar_csv(output_path: Path, posts: List[PostDraft]) -> None:
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "day",
                "week",
                "platform",
                "format",
                "pillar",
                "objective",
                "headline",
                "hook",
                "angle",
                "cta",
                "asset_brief",
                "hashtags",
                "follow_up",
            ]
        )
        for post in posts:
            writer.writerow(
                [
                    post.day,
                    post.week,
                    post.platform,
                    post.format,
                    post.pillar,
                    post.objective,
                    post.headline,
                    post.hook,
                    post.angle,
                    post.cta,
                    post.asset_brief,
                    " ".join(post.hashtags),
                    post.follow_up,
                ]
            )


def build_summary(
    profiles: List[PlatformProfile],
    posts: List[PostDraft],
    experiments: List[WeeklyExperiment],
    output_dir: Path,
) -> Dict[str, object]:
    return {
        "agent": "Audioraq Marketing Agent",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "output_dir": str(output_dir),
        "intelligence_memo": str(INTELLIGENCE_MEMO),
        "positioning": PRODUCT_POSITIONING,
        "proof_points": PRODUCT_PROOF_POINTS,
        "profiles": [asdict(profile) for profile in profiles],
        "pillar_count": len(PILLARS),
        "post_count": len(posts),
        "experiments": [asdict(experiment) for experiment in experiments],
        "guardrails": [
            "No fake followers, fake comments, or bought engagement.",
            "No spam DMs or mass unsolicited outreach.",
            "No fake reviews or fake customer stories.",
            "Use proof of work, creator education, and product demos as the growth engine.",
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a 30-day LinkedIn + Instagram growth campaign for Audioraq.")
    parser.add_argument("--days", type=int, default=30, help="Campaign length in days. Default: 30")
    parser.add_argument("--linkedin-followers", type=int, default=None, help="Current LinkedIn follower count, if known")
    parser.add_argument("--instagram-followers", type=int, default=None, help="Current Instagram follower count, if known")
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT, help="Directory for generated campaign outputs")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_id = timestamp()
    output_dir = args.output_root / run_id
    output_dir.mkdir(parents=True, exist_ok=True)

    profiles = build_profiles(args.linkedin_followers, args.instagram_followers)
    posts = build_posts(max(7, args.days))
    experiments = build_experiments()
    kpis = build_kpis(profiles)

    write_markdown(output_dir / "campaign.md", profiles, posts, experiments)
    write_posts_json(output_dir / "posts.json", posts)
    write_calendar_csv(output_dir / "calendar.csv", posts)
    write_kpi_csv(output_dir / "kpi_scorecard.csv", kpis)
    (output_dir / "summary.json").write_text(
        json.dumps(build_summary(profiles, posts, experiments, output_dir), indent=2, ensure_ascii=True),
        encoding="utf-8",
    )

    print(f"Audioraq Marketing Agent campaign created at: {output_dir}")
    print(f"- campaign.md")
    print(f"- posts.json")
    print(f"- calendar.csv")
    print(f"- kpi_scorecard.csv")
    print(f"- summary.json")


if __name__ == "__main__":
    main()
