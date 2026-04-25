#!/usr/bin/env python3
"""
Audioraq GTM Strategy Agent.

Builds a launch-focused go-to-market plan and an execution queue for Product
Hunt, Uneed, BetaList, AI directories, and founder-led creator acquisition.
"""

from __future__ import annotations

import argparse
import csv
import json
import time
from pathlib import Path
from typing import Dict, List


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "qa" / "audioraq-gtm-agent"
INTELLIGENCE_MEMO = REPO_ROOT / "marketing" / "audioraq_competitive_intelligence.md"

POSITIONING = "Audioraq gives podcasters an AI studio team: strategist, creator, quality reviewer, and publishing assistant in one platform."

CHANNELS = [
    {
        "channel": "Product Hunt",
        "role": "launch spike",
        "goal": "Earn comments, creator trials, and investor-visible momentum.",
        "action": "Launch after demo assets, signup gates, feedback loop, and 5 polished proof episodes are ready.",
    },
    {
        "channel": "Uneed",
        "role": "SEO and directory credibility",
        "goal": "Capture early AI tool discovery and backlinks before Product Hunt.",
        "action": "Submit as AI podcast studio, creator tool, audio tool, and productivity product.",
    },
    {
        "channel": "BetaList",
        "role": "early adopter pipeline",
        "goal": "Reach startup-friendly beta users who expect imperfect but useful tools.",
        "action": "Submit with a creator-focused promise and the first 100 creator audit offer.",
    },
    {
        "channel": "AI directories",
        "role": "long-tail discovery",
        "goal": "Own the phrase AI podcast studio across directory search results.",
        "action": "Submit to Futurepedia, Toolify, There Is An AI For That, TopAI.tools, SaaSHub, and Startup Stash.",
    },
    {
        "channel": "Founder-led outreach",
        "role": "qualified design partners",
        "goal": "Convert real podcasters instead of vanity traffic.",
        "action": "Offer a free AI Podcast Studio audit to solo podcasters, coaches, consultants, and B2B creators.",
    },
]

LAUNCH_PLATFORM_RULES = [
    {
        "platform": "Product Hunt",
        "rule": "Use a personal founder account, not a company account, and launch only when users can explore the live product.",
        "source": "https://www.producthunt.com/launch/",
    },
    {
        "platform": "Product Hunt",
        "rule": "Do not launch as an email-only waitlist; the product should be available and useful immediately.",
        "source": "https://help.producthunt.com/en/articles/484932-can-i-submit-an-unreleased-product",
    },
    {
        "platform": "BetaList",
        "rule": "Submit as a recently launched technology startup with a distinct landing page on Audioraq's own domain.",
        "source": "https://betalist.com/criteria",
    },
    {
        "platform": "Uneed",
        "rule": "Create a Uneed account before submission so the listing can be edited later.",
        "source": "https://www.uneed.best/submit-a-tool",
    },
]


def write_csv(path: Path, rows: List[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def build_directory_queue() -> List[Dict[str, str]]:
    return [
        {"priority": "1", "platform": "Product Hunt", "url": "https://www.producthunt.com/", "asset_needed": "90-second demo, gallery, founder comment", "status": "prepare"},
        {"priority": "2", "platform": "Uneed", "url": "https://www.uneed.best/submit-a-tool", "asset_needed": "SEO description, logo, screenshots", "status": "submit-before-ph"},
        {"priority": "3", "platform": "BetaList", "url": "https://betalist.com/submit", "asset_needed": "startup description, domain proof, founder story", "status": "submit-before-ph"},
        {"priority": "4", "platform": "There Is An AI For That", "url": "https://theresanaiforthat.com/submit/", "asset_needed": "AI podcast studio category copy", "status": "submit"},
        {"priority": "5", "platform": "AlternativeTo", "url": "https://alternativeto.net/software/submit/", "asset_needed": "competitor alternatives and product screenshots", "status": "submit-after-ph"},
        {"priority": "6", "platform": "SaaSHub", "url": "https://www.saashub.com/submit", "asset_needed": "SaaS profile and categories", "status": "submit"},
        {"priority": "7", "platform": "Startup Stash", "url": "https://startupstash.com/", "asset_needed": "startup tooling summary", "status": "submit"},
    ]


def build_launch_calendar() -> List[Dict[str, str]]:
    return [
        {"day": "T-21", "owner": "GTM Strategy Agent", "task": "Finalize positioning and launch offer", "success_metric": "One headline, one tagline, one offer"},
        {"day": "T-18", "owner": "Tech Strategy Agent", "task": "Verify signup gating, feedback loop, playback, Create with AI", "success_metric": "No critical smoke failures"},
        {"day": "T-14", "owner": "GTM Strategy Agent", "task": "Submit Uneed, BetaList, and AI directories", "success_metric": "5 listings submitted"},
        {"day": "T-10", "owner": "AI Podcast Creation Agent", "task": "Publish 5 polished proof episodes", "success_metric": "5 shareable links"},
        {"day": "T-7", "owner": "Founder", "task": "Warm up Product Hunt account through helpful comments", "success_metric": "10 genuine comments"},
        {"day": "T-3", "owner": "Business Analyst Agent", "task": "Review early feedback and sharpen launch copy", "success_metric": "Top objections addressed"},
        {"day": "T-1", "owner": "Standup Agent", "task": "Send founder launch readiness report", "success_metric": "Clear go/no-go"},
        {"day": "Launch", "owner": "Founder + GTM Strategy Agent", "task": "Product Hunt launch and comment response", "success_metric": "Creator signups and useful comments"},
        {"day": "T+3", "owner": "Business Analyst Agent", "task": "Analyze launch traffic and feedback", "success_metric": "Next retention experiment chosen"},
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Audioraq GTM launch artifacts.")
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    args = parser.parse_args()

    run_id = time.strftime("%Y%m%d-%H%M%S")
    output_dir = Path(args.output_root) / run_id
    output_dir.mkdir(parents=True, exist_ok=True)

    memo_excerpt = INTELLIGENCE_MEMO.read_text(encoding="utf-8")[:4000] if INTELLIGENCE_MEMO.exists() else ""
    directory_queue = build_directory_queue()
    launch_calendar = build_launch_calendar()
    write_csv(output_dir / "directory_submission_queue.csv", directory_queue)
    write_csv(output_dir / "launch_calendar.csv", launch_calendar)

    strategy = {
        "agent": "GTM Strategy Agent",
        "positioning": POSITIONING,
        "launch_offer": "First 100 creators get a free AI Podcast Studio audit: show positioning, three episode ideas, and one AI-generated episode draft.",
        "primary_launch": "Product Hunt",
        "supporting_channels": CHANNELS,
        "north_star_metric": "Creators who generate or publish an episode after landing on Audioraq",
        "prelaunch_requirements": [
            "Signup gates make high-value viewer and creator workflows member-only.",
            "Feedback widget is live and founder review workbook is generated.",
            "Five proof podcasts are polished enough to show voice and workflow quality.",
            "Product Hunt assets include creator studio, AI strategy, Agent 2 gate, and episode page screenshots.",
        ],
        "launch_platform_rules": LAUNCH_PLATFORM_RULES,
        "competitive_intelligence_excerpt": memo_excerpt,
    }
    (output_dir / "gtm_strategy.json").write_text(json.dumps(strategy, indent=2, ensure_ascii=True), encoding="utf-8")
    (output_dir / "business_analyst_payload.json").write_text(
        json.dumps(
            {
                "source_agent": "gtm_strategy_agent",
                "recommended_focus": "Product Hunt launch readiness and creator audit funnel",
                "tasks": launch_calendar,
                "directory_queue": directory_queue,
            },
            indent=2,
            ensure_ascii=True,
        ),
        encoding="utf-8",
    )
    (output_dir / "gtm_strategy.md").write_text(
        "\n".join(
            [
                "# Audioraq GTM Strategy",
                "",
                f"Positioning: {POSITIONING}",
                "",
                "Launch offer: First 100 creators get a free AI Podcast Studio audit.",
                "",
                "Primary launch: Product Hunt.",
                "",
                "Execution channels:",
                *[f"- {item['channel']}: {item['goal']}" for item in CHANNELS],
                "",
                "Platform rules:",
                *[f"- {item['platform']}: {item['rule']}" for item in LAUNCH_PLATFORM_RULES],
            ]
        ),
        encoding="utf-8",
    )
    print(json.dumps({"output_dir": str(output_dir), "directory_count": len(directory_queue)}, indent=2))


if __name__ == "__main__":
    main()
