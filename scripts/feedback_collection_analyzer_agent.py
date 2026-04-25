#!/usr/bin/env python3
"""
Audioraq Feedback Collection and Analyzer Agent.

Collects in-app feedback from MongoDB, classifies product problems, prepares
founder review spreadsheets, and produces Business Analyst Agent input.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
import time
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List

try:
    from pymongo import MongoClient
except ImportError:  # pragma: no cover - local convenience fallback
    MongoClient = None


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "qa" / "audioraq-feedback-agent"
DEFAULT_DB_NAME = "audioraq"

PROBLEM_LABELS = {
    "signup_conversion": "Signup and activation",
    "creator_ai_studio": "AI Podcast Creator Studio",
    "podcast_discovery": "Discovery and recommendations",
    "playback_reliability": "Playback and queue reliability",
    "creator_workflow": "Creator publishing workflow",
    "trust_safety": "Trust, safety, and moderation",
    "pricing_value": "Pricing and willingness to pay",
    "investor_signal": "Launch, growth, and investor proof",
    "general_product_learning": "General product learning",
}


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def safe_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=True)
    return str(value)


def col_name(index: int) -> str:
    name = ""
    index += 1
    while index:
        index, remainder = divmod(index - 1, 26)
        name = chr(65 + remainder) + name
    return name


def write_xlsx(path: Path, sheets: Dict[str, List[List[Any]]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook_sheets = list(sheets.items())

    def worksheet_xml(rows: List[List[Any]]) -> str:
        row_xml = []
        for row_index, row in enumerate(rows, start=1):
            cells = []
            for col_index, value in enumerate(row):
                ref = f"{col_name(col_index)}{row_index}"
                text = html.escape(safe_cell(value), quote=True)
                cells.append(f'<c r="{ref}" t="inlineStr"><is><t>{text}</t></is></c>')
            row_xml.append(f'<row r="{row_index}">{"".join(cells)}</row>')
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            f'<sheetData>{"".join(row_xml)}</sheetData></worksheet>'
        )

    workbook_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets>'
        + "".join(
            f'<sheet name="{html.escape(name[:31], quote=True)}" sheetId="{index}" r:id="rId{index}"/>'
            for index, (name, _) in enumerate(workbook_sheets, start=1)
        )
        + '</sheets></workbook>'
    )
    workbook_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        + "".join(
            f'<Relationship Id="rId{index}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{index}.xml"/>'
            for index in range(1, len(workbook_sheets) + 1)
        )
        + '</Relationships>'
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        + "".join(
            f'<Override PartName="/xl/worksheets/sheet{index}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            for index in range(1, len(workbook_sheets) + 1)
        )
        + '</Types>'
    )
    root_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        '</Relationships>'
    )

    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as workbook:
        workbook.writestr("[Content_Types].xml", content_types)
        workbook.writestr("_rels/.rels", root_rels)
        workbook.writestr("xl/workbook.xml", workbook_xml)
        workbook.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        for index, (_, rows) in enumerate(workbook_sheets, start=1):
            workbook.writestr(f"xl/worksheets/sheet{index}.xml", worksheet_xml(rows))


def fetch_feedback(limit: int) -> List[Dict[str, Any]]:
    load_env_file(REPO_ROOT / "backend" / ".env")
    mongo_url = os.environ.get("MONGO_URL")
    db_name = os.environ.get("DB_NAME", DEFAULT_DB_NAME)
    if not mongo_url or MongoClient is None:
        return []
    client = MongoClient(mongo_url, serverSelectionTimeoutMS=3000)
    try:
        client.admin.command("ping")
        records = list(client[db_name].feedback_submissions.find({}).sort("created_at", -1).limit(limit))
    except Exception:
        return []
    for record in records:
        record.pop("_id", None)
    return records


def summarize(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    problem_counter: Counter[str] = Counter()
    urgency_counter: Counter[str] = Counter()
    persona_counter: Counter[str] = Counter()
    category_counter: Counter[str] = Counter()
    followup_queue = []

    for record in records:
        analysis = record.get("analysis") or {}
        persona_counter[record.get("persona") or "unknown"] += 1
        category_counter[record.get("category") or "other"] += 1
        urgency_counter[analysis.get("urgency") or "medium"] += 1
        for problem in analysis.get("problem_areas") or ["general_product_learning"]:
            problem_counter[problem] += 1
        if record.get("contact_ok") and record.get("email"):
            followup_queue.append(
                {
                    "email": record["email"],
                    "persona": record.get("persona", ""),
                    "problem_area": (analysis.get("problem_areas") or ["general_product_learning"])[0],
                    "message": record.get("message", ""),
                    "suggested_question": "What outcome were you hoping Audioraq would help you reach in that moment?",
                }
            )

    top_problem = problem_counter.most_common(1)[0][0] if problem_counter else "general_product_learning"
    return {
        "record_count": len(records),
        "top_problem_area": top_problem,
        "top_problem_label": PROBLEM_LABELS.get(top_problem, top_problem),
        "problem_counts": dict(problem_counter),
        "urgency_counts": dict(urgency_counter),
        "persona_counts": dict(persona_counter),
        "category_counts": dict(category_counter),
        "followup_queue": followup_queue[:25],
        "business_analyst_rlaif": {
            "reward": "prioritize repeated high-friction user language over founder assumptions",
            "penalty": "do not overbuild one-off requests without repeated evidence",
            "next_decision": f"Investigate {PROBLEM_LABELS.get(top_problem, top_problem)} first.",
        },
    }


def build_workbook_rows(records: List[Dict[str, Any]], summary: Dict[str, Any]) -> Dict[str, List[List[Any]]]:
    summary_rows = [
        ["Metric", "Value"],
        ["Generated at", datetime.now(timezone.utc).isoformat()],
        ["Feedback records", summary["record_count"]],
        ["Top problem area", summary["top_problem_label"]],
        ["RLAIF reward", summary["business_analyst_rlaif"]["reward"]],
        ["RLAIF next decision", summary["business_analyst_rlaif"]["next_decision"]],
        [],
        ["Problem area", "Count"],
    ]
    for key, count in summary["problem_counts"].items():
        summary_rows.append([PROBLEM_LABELS.get(key, key), count])

    feedback_rows = [[
        "Created at", "Persona", "Category", "Rating", "Urgency", "Sentiment",
        "Problem areas", "Message", "Desired outcome", "Contact OK", "Email",
    ]]
    for record in records:
        analysis = record.get("analysis") or {}
        feedback_rows.append([
            record.get("created_at", ""),
            record.get("persona", ""),
            record.get("category", ""),
            record.get("rating", ""),
            analysis.get("urgency", ""),
            analysis.get("sentiment", ""),
            ", ".join(PROBLEM_LABELS.get(item, item) for item in analysis.get("problem_areas", [])),
            record.get("message", ""),
            record.get("desired_outcome", ""),
            "yes" if record.get("contact_ok") else "no",
            record.get("email", ""),
        ])

    outreach_rows = [["Email", "Persona", "Problem area", "Suggested question", "Original message"]]
    for item in summary["followup_queue"]:
        outreach_rows.append([
            item["email"],
            item["persona"],
            PROBLEM_LABELS.get(item["problem_area"], item["problem_area"]),
            item["suggested_question"],
            item["message"],
        ])

    return {
        "Summary": summary_rows,
        "Feedback": feedback_rows,
        "Outreach Queue": outreach_rows,
    }


def write_csv(path: Path, rows: Iterable[Dict[str, Any]]) -> None:
    rows = list(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze Audioraq feedback and prepare founder review artifacts.")
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    args = parser.parse_args()

    run_id = time.strftime("%Y%m%d-%H%M%S")
    output_dir = Path(args.output_root) / run_id
    output_dir.mkdir(parents=True, exist_ok=True)

    records = fetch_feedback(args.limit)
    summary = summarize(records)
    workbook_path = output_dir / "audioraq_feedback_founder_review.xlsx"
    write_xlsx(workbook_path, build_workbook_rows(records, summary))
    write_csv(output_dir / "feedback_followup_queue.csv", summary["followup_queue"])

    (output_dir / "feedback_analysis.json").write_text(
        json.dumps({"agent": "Feedback Collection and Analyzer Agent", "summary": summary, "records": records}, indent=2, ensure_ascii=True),
        encoding="utf-8",
    )
    (output_dir / "business_analyst_payload.json").write_text(
        json.dumps(
            {
                "source_agent": "feedback_collection_analyzer_agent",
                "priority_signal": summary["top_problem_area"],
                "rlaif": summary["business_analyst_rlaif"],
                "followup_count": len(summary["followup_queue"]),
                "artifact_paths": {
                    "workbook": str(workbook_path),
                    "analysis": str(output_dir / "feedback_analysis.json"),
                    "outreach": str(output_dir / "feedback_followup_queue.csv"),
                },
            },
            indent=2,
            ensure_ascii=True,
        ),
        encoding="utf-8",
    )
    (output_dir / "founder_gmail_draft.md").write_text(
        "\n".join(
            [
                "Subject: Audioraq feedback review is ready",
                "",
                f"Feedback records analyzed: {summary['record_count']}",
                f"Top product problem: {summary['top_problem_label']}",
                f"Suggested next decision: {summary['business_analyst_rlaif']['next_decision']}",
                "",
                f"Founder review workbook: {workbook_path}",
                f"Follow-up queue: {output_dir / 'feedback_followup_queue.csv'}",
            ]
        ),
        encoding="utf-8",
    )

    print(json.dumps({"output_dir": str(output_dir), "records": len(records), "workbook": str(workbook_path)}, indent=2))


if __name__ == "__main__":
    main()
