"""Report generation: Markdown, JSON, and Telegram summary."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from dateutil import tz

logger = logging.getLogger(__name__)

_DISCLAIMER = (
    "> **Disclaimer:** This report is for informational purposes only and does not constitute legal or "
    "trade compliance advice. Always verify with CBP binding rulings and official tariff schedules. "
    "V1 scope does NOT include Section 301/232 additional duties, AD/CVD orders, complex exclusions, "
    "or classification disputes."
)

_CHANGE_TYPE_LABELS = {
    "added": "➕ Added",
    "removed": "➖ Removed",
    "changed_rate_general": "⚠️ Rate Changed",
    "changed_description": "📝 Description Changed",
}


def _now_local(timezone_str: str) -> datetime:
    local_tz = tz.gettz(timezone_str) or tz.tzlocal()
    return datetime.now(tz=local_tz)


def _top_changes(changes: list[dict[str, Any]], n: int = 3) -> list[dict[str, Any]]:
    """Return up to n changes prioritising rate changes, then added/removed."""
    priority = {"changed_rate_general": 0, "added": 1, "removed": 2, "changed_description": 3}
    return sorted(changes, key=lambda c: priority.get(c["change_type"], 99))[:n]


def _md_table(changes: list[dict[str, Any]]) -> str:
    if not changes:
        return "_No changes detected._\n"
    header = "| HTS Code | Change Type | Old Value | New Value |\n"
    separator = "|---|---|---|---|\n"
    rows = []
    for c in changes:
        ct = _CHANGE_TYPE_LABELS.get(c["change_type"], c["change_type"])
        old = str(c.get("old_raw") or c.get("old_value") or "—")
        new = str(c.get("new_raw") or c.get("new_value") or "—")
        rows.append(f"| `{c['hts_code']}` | {ct} | {old} | {new} |")
    return header + separator + "\n".join(rows) + "\n"


def generate_markdown_report(
    changes: list[dict[str, Any]],
    run_date_str: str,
    source_url: str,
    mode: str,
    tracked_hts: list[str],
    timezone_str: str = "America/Los_Angeles",
) -> str:
    top = _top_changes(changes)
    highlights = []
    for c in top:
        ct = _CHANGE_TYPE_LABELS.get(c["change_type"], c["change_type"])
        if c["change_type"] == "changed_rate_general":
            highlights.append(
                f"- {ct}: `{c['hts_code']}` — `{c.get('old_raw','?')}` → `{c.get('new_raw','?')}`"
            )
        elif c["change_type"] in ("added", "removed"):
            highlights.append(f"- {ct}: `{c['hts_code']}` — {c.get('new_value') or c.get('old_value','')}")
        else:
            highlights.append(f"- {ct}: `{c['hts_code']}`")

    highlights_md = "\n".join(highlights) if highlights else "- No significant changes this week."

    return f"""# Tariff Watch — Weekly Update

**Date:** {run_date_str} ({timezone_str})
**Mode:** {mode}
**Tracked HTS codes:** {len(tracked_hts) if mode == 'tracked_only' else 'all'}

---

## 📌 Weekly Highlights

{highlights_md}

---

## 🔍 Detailed Changes

{_md_table(changes)}

---

## ⚠️ Disclaimer

{_DISCLAIMER}

---

**Source:** {source_url or '_not configured_'}
"""


def generate_json_report(
    changes: list[dict[str, Any]],
    run_date_str: str,
    source_url: str,
    mode: str,
    tracked_hts: list[str],
    timezone_str: str = "America/Los_Angeles",
) -> dict[str, Any]:
    return {
        "meta": {
            "date": run_date_str,
            "timezone": timezone_str,
            "source_urls": [source_url] if source_url else [],
            "mode": mode,
            "tracked_hts": tracked_hts,
            "total_changes": len(changes),
        },
        "changes": changes,
    }


def generate_telegram_summary(
    changes: list[dict[str, Any]],
    run_date_str: str,
    md_path: str,
    json_path: str,
) -> str:
    """Return a ≤20-line Telegram-ready plain-text summary."""
    top = _top_changes(changes)
    lines = [
        f"📊 *Tariff Watch* — Weekly Update ({run_date_str})",
        f"Total changes detected: {len(changes)}",
        "",
    ]

    if not changes:
        lines.append("✅ No changes detected this week.")
    else:
        lines.append("🔑 Top highlights:")
        for c in top:
            ct = c["change_type"].replace("_", " ").title()
            if c["change_type"] == "changed_rate_general":
                lines.append(f"  • [{ct}] {c['hts_code']}: {c.get('old_raw','?')} → {c.get('new_raw','?')}")
            elif c["change_type"] in ("added", "removed"):
                lines.append(f"  • [{ct}] {c['hts_code']}")
            else:
                lines.append(f"  • [{ct}] {c['hts_code']}")

    lines += [
        "",
        f"📄 Report (MD):   {md_path}",
        f"📋 Report (JSON): {json_path}",
        "",
        "⚠️ For reference only. Verify with CBP/official rulings.",
    ]
    return "\n".join(lines)


def write_reports(
    changes: list[dict[str, Any]],
    reports_dir: str | Path,
    source_url: str,
    mode: str,
    tracked_hts: list[str],
    timezone_str: str = "America/Los_Angeles",
) -> tuple[Path, Path, str]:
    """
    Write Markdown + JSON reports to reports_dir.
    Returns (md_path, json_path, telegram_summary).
    """
    reports_dir = Path(reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)

    now = _now_local(timezone_str)
    date_str = now.strftime("%Y-%m-%d")
    file_stem = f"report_{now.strftime('%Y%m%d')}"

    md_content = generate_markdown_report(
        changes, date_str, source_url, mode, tracked_hts, timezone_str
    )
    json_content = generate_json_report(
        changes, date_str, source_url, mode, tracked_hts, timezone_str
    )

    md_path = reports_dir / f"{file_stem}.md"
    json_path = reports_dir / f"{file_stem}.json"

    md_path.write_text(md_content, encoding="utf-8")
    json_path.write_text(json.dumps(json_content, indent=2, default=str), encoding="utf-8")

    logger.info("Report written: %s", md_path)
    logger.info("Report written: %s", json_path)

    summary = generate_telegram_summary(changes, date_str, str(md_path), str(json_path))
    return md_path, json_path, summary
