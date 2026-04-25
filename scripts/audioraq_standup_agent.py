#!/usr/bin/env python3
"""
Audioraq Standup Agent.

Prepares a concise Sunday founder status report and Business Analyst payload.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "qa" / "audioraq-standup-agent"


def run_git_log() -> List[str]:
    try:
        output = subprocess.check_output(
            ["git", "-C", str(REPO_ROOT), "log", "--oneline", "-8"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
        return [line.strip() for line in output.splitlines() if line.strip()]
    except Exception:
        return []


def list_recent_agent_outputs() -> List[str]:
    outputs = []
    qa_root = REPO_ROOT / "qa"
    if not qa_root.exists():
        return outputs
    for path in sorted(qa_root.glob("audioraq-*/*"), key=lambda item: item.stat().st_mtime, reverse=True)[:12]:
        outputs.append(str(path))
    return outputs


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Audioraq weekly standup artifacts.")
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--founder-email", default="founder@audioraq.com")
    args = parser.parse_args()

    run_id = time.strftime("%Y%m%d-%H%M%S")
    output_dir = Path(args.output_root) / run_id
    output_dir.mkdir(parents=True, exist_ok=True)

    git_lines = run_git_log()
    agent_outputs = list_recent_agent_outputs()
    report = {
        "agent": "Standup Agent",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "founder_email": args.founder_email,
        "headline": "Audioraq launch readiness is moving through product gating, feedback capture, and GTM preparation.",
        "progress": [
            "Public browsing remains available, while playback, listener AI, queueing, saving, following, and ratings are member-only.",
            "Feedback collection is now structured for founder review and Business Analyst Agent prioritization.",
            "GTM and Business Analyst agents can now produce launch queues, status reports, and task allocations.",
        ],
        "risks": [
            "Before Product Hunt, verify signup conversion does not feel too aggressive.",
            "Run live smoke tests for feedback submit, signup, playback gate, and Create with AI.",
            "Keep proof-of-work episode quality high; do not flood the catalog with filler.",
        ],
        "recent_commits": git_lines,
        "recent_agent_outputs": agent_outputs,
    }

    (output_dir / "standup_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=True), encoding="utf-8")
    (output_dir / "business_analyst_payload.json").write_text(
        json.dumps(
            {
                "source_agent": "standup_agent",
                "recommended_focus": "launch readiness and smoke-test discipline",
                "risks": report["risks"],
                "progress": report["progress"],
            },
            indent=2,
            ensure_ascii=True,
        ),
        encoding="utf-8",
    )
    markdown = "\n".join(
        [
            "# Audioraq Weekly Standup",
            "",
            report["headline"],
            "",
            "Progress:",
            *[f"- {item}" for item in report["progress"]],
            "",
            "Risks:",
            *[f"- {item}" for item in report["risks"]],
            "",
            "Recent commits:",
            *[f"- {item}" for item in git_lines],
        ]
    )
    (output_dir / "standup_report.md").write_text(markdown, encoding="utf-8")
    (output_dir / "founder_gmail_draft.md").write_text(
        "\n".join(
            [
                "Subject: Audioraq Sunday standup",
                "",
                report["headline"],
                "",
                "Progress:",
                *[f"- {item}" for item in report["progress"]],
                "",
                "Risks:",
                *[f"- {item}" for item in report["risks"]],
                "",
                f"Full report: {output_dir / 'standup_report.md'}",
            ]
        ),
        encoding="utf-8",
    )
    print(json.dumps({"output_dir": str(output_dir), "founder_email": args.founder_email}, indent=2))


if __name__ == "__main__":
    main()
