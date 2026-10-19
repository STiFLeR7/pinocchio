"""Design-time email preview renderer.

Renders every Nexus email template with sample_context.json and writes
HTML previews. Asserts no unresolved Jinja tags remain. Not imported by
any service — pure design QA tooling.

    python scripts/render_emails.py            # render all + write previews
    python scripts/render_emails.py morning_digest   # render one to stdout check
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

ROOT = Path(__file__).resolve().parent.parent
TPL_DIR = ROOT / "nexus" / "communication" / "email" / "templates"
PREVIEW_DIR = TPL_DIR / "previews"

# template file (relative to TPL_DIR) -> context key in sample_context.json
TEMPLATES: dict[str, str] = {
    "emails/morning_digest.html": "morning_digest",
    "emails/operational_intelligence.html": "operational_intelligence",
    "emails/research_report.html": "research_report",
    "emails/todo_digest.html": "todo_digest",
    "emails/reminder.html": "reminder",
    "emails/approval_required.html": "approval_required",
    "emails/execution_completed.html": "execution_completed",
    "emails/execution_failed.html": "execution_failed",
    "emails/security_alert.html": "security_alert",
    "emails/scheduler_report.html": "scheduler_report",
    "emails/weekly_review.html": "weekly_review",
    "emails/monthly_executive.html": "monthly_executive",
    "emails/conversations/qa_transcript.html": "qa_transcript",
    "emails/conversations/conversation_summary.html": "conversation_summary",
    "emails/conversations/action_items.html": "action_items",
    "emails/conversations/decision_summary.html": "decision_summary",
}


def build_env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(TPL_DIR)),
        autoescape=select_autoescape(["html"]),
    )


def load_ctx() -> dict:
    return json.loads((TPL_DIR / "sample_context.json").read_text(encoding="utf-8"))


def render_one(env: Environment, ctx: dict, tpl: str, key: str) -> str:
    shared = ctx.get("_shared", {})
    payload = ctx.get(key, {})
    return env.get_template(tpl).render(**shared, **payload)


def main() -> int:
    env = build_env()
    ctx = load_ctx()
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)

    only = sys.argv[1] if len(sys.argv) > 1 else None
    failures: list[str] = []
    rendered = 0

    for tpl, key in TEMPLATES.items():
        name = key
        if only and only not in (tpl, key):
            continue
        try:
            html = render_one(env, ctx, tpl, key)
        except Exception as exc:  # design tooling: report every failure
            failures.append(f"{tpl}: {type(exc).__name__}: {exc}")
            continue
        if "{{" in html or "{%" in html:
            failures.append(f"{tpl}: unresolved Jinja tag remains")
        out = PREVIEW_DIR / f"{name}.preview.html"
        out.write_text(html, encoding="utf-8")
        rendered += 1
        print(f"  ok  {tpl}  ->  previews/{name}.preview.html  ({len(html):,} bytes)")

    print(f"\nRendered {rendered} template(s).")
    if failures:
        print(f"\n{len(failures)} FAILURE(S):")
        for f in failures:
            print(f"  X  {f}")
        return 1
    print("All templates rendered cleanly — no unresolved tags.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
