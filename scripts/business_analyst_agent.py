#!/usr/bin/env python3
"""
Audioraq Business Analyst Agent.

Reads outputs from other Audioraq agents, converts them into product/business
priorities, and allocates work based on agent capabilities.
"""

from __future__ import annotations

import argparse
import csv
import json
import time
from pathlib import Path
from typing import Any, Dict, List


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "qa" / "audioraq-business-analyst-agent"
QA_ROOT = REPO_ROOT / "qa"

AGENT_CAPABILITIES = {
    "Feedback Collection and Analyzer Agent": "turns user feedback into product problem statements, follow-up queues, and founder review sheets",
    "GTM Strategy Agent": "plans and executes launch channels, directory submissions, and founder-led acquisition experiments",
    "Tech Strategy Agent": "protects deployment stability, database health, playback reliability, and AI worker performance",
    "AI Podcast Creation Agent": "creates proof-of-work Audioraq Originals and creator workflow test episodes",
    "Podcast Improvement Agent": "reviews audio quality, safety, listenability, and publish-readiness gates",
    "Standup Agent": "summarizes weekly platform progress and open risks for the founder",
}


def latest_payloads() -> List[Dict[str, Any]]:
    payloads = []
    for path in sorted(QA_ROOT.glob("audioraq-*/*/business_analyst_payload.json"), reverse=True):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["_path"] = str(path)
            payloads.append(payload)
        except Exception:
            continue
    return payloads[:25]


def allocate_tasks(payloads: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    tasks = []
    seen_focus = set()
    for payload in payloads:
        source = payload.get("source_agent", "unknown")
        focus = payload.get("priority_signal") or payload.get("recommended_focus") or "launch_readiness"
        if focus in seen_focus:
            continue
        seen_focus.add(focus)
        if "feedback" in source:
            tasks.append({
                "owner": "Feedback Collection and Analyzer Agent",
                "priority": "P0",
                "task": f"Run follow-up interviews for {focus}",
                "success_metric": "At least 5 specific user quotes and one clear problem statement",
            })
            tasks.append({
                "owner": "Tech Strategy Agent",
                "priority": "P1",
                "task": f"Review whether {focus} requires product or infrastructure changes",
                "success_metric": "Risk and implementation note produced before launch",
            })
        elif "gtm" in source:
            tasks.append({
                "owner": "GTM Strategy Agent",
                "priority": "P0",
                "task": "Prepare Product Hunt, Uneed, BetaList, and AI directory launch queue",
                "success_metric": "Launch assets and submission queue ready before launch week",
            })
        elif "standup" in source:
            tasks.append({
                "owner": "Standup Agent",
                "priority": "P1",
                "task": "Keep weekly founder status concise and decision-oriented",
                "success_metric": "One founder email draft every Sunday",
            })

    if not tasks:
        tasks.extend([
            {
                "owner": "GTM Strategy Agent",
                "priority": "P0",
                "task": "Create launch submission queue and creator audit funnel",
                "success_metric": "Three qualified creator trials before Product Hunt",
            },
            {
                "owner": "Feedback Collection and Analyzer Agent",
                "priority": "P0",
                "task": "Collect first 20 launch feedback records",
                "success_metric": "Founder review workbook with repeated problem areas",
            },
        ])
    return tasks


def write_csv(path: Path, rows: List[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze agent outputs and allocate Audioraq tasks.")
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    args = parser.parse_args()

    run_id = time.strftime("%Y%m%d-%H%M%S")
    output_dir = Path(args.output_root) / run_id
    output_dir.mkdir(parents=True, exist_ok=True)

    payloads = latest_payloads()
    tasks = allocate_tasks(payloads)
    rlaif_log = [
        {
            "rule": "Reward repeated user pain over founder preference",
            "application": "Feedback-backed tasks receive P0/P1 priority.",
            "status": "active",
        },
        {
            "rule": "Reward launch work that produces real users, not vanity traffic",
            "application": "GTM tasks optimize for creator trials and published episodes.",
            "status": "active",
        },
        {
            "rule": "Penalize work that risks platform stability before launch",
            "application": "Tech Strategy Agent reviews infrastructure-heavy changes before execution.",
            "status": "active",
        },
    ]

    write_csv(output_dir / "task_allocations.csv", tasks)
    write_csv(output_dir / "rlaif_decision_log.csv", rlaif_log)
    (output_dir / "business_analysis.json").write_text(
        json.dumps(
            {
                "agent": "Business Analyst Agent",
                "payload_count": len(payloads),
                "capabilities": AGENT_CAPABILITIES,
                "task_allocations": tasks,
                "rlaif_decision_log": rlaif_log,
            },
            indent=2,
            ensure_ascii=True,
        ),
        encoding="utf-8",
    )
    (output_dir / "business_analysis.md").write_text(
        "\n".join(
            [
                "# Audioraq Business Analyst Review",
                "",
                f"Agent payloads reviewed: {len(payloads)}",
                "",
                "Task allocations:",
                *[f"- {task['priority']} - {task['owner']}: {task['task']}" for task in tasks],
                "",
                "RLAIF policy:",
                *[f"- {item['rule']}" for item in rlaif_log],
            ]
        ),
        encoding="utf-8",
    )
    print(json.dumps({"output_dir": str(output_dir), "tasks": len(tasks)}, indent=2))


if __name__ == "__main__":
    main()
