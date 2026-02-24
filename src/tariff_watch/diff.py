"""Change detection between two HTS snapshots."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

CHANGE_TYPES = ("added", "removed", "changed_rate_general", "changed_description")


def _iso_now() -> str:
    return datetime.now(tz=timezone.utc).isoformat(timespec="seconds")


def _get(row: pd.Series, col: str) -> Any:
    return row[col] if col in row.index else None


def compute_diff(
    prev: pd.DataFrame,
    current: pd.DataFrame,
    detected_at: str | None = None,
) -> list[dict[str, Any]]:
    """
    Compare two normalised HTS DataFrames keyed on hts_code.

    Returns a list of change dicts with keys:
        hts_code, change_type, old_value, new_value, detected_at, notes
    """
    if detected_at is None:
        detected_at = _iso_now()

    changes: list[dict[str, Any]] = []

        # Guard: allow empty/column-missing inputs (treat as "no diff" baseline)
    if prev is None or prev.empty or "hts_code" not in prev.columns:
        logger.info("Prev snapshot is empty or missing hts_code; returning no changes.")
        return []
    if current is None or current.empty or "hts_code" not in current.columns:
        logger.info("Current snapshot is empty or missing hts_code; returning no changes.")
        return []

    prev_clean = prev[prev["hts_code"].notna()].copy()
    curr_clean = current[current["hts_code"].notna()].copy()

    prev_indexed = prev_clean.set_index("hts_code")
    curr_indexed = curr_clean.set_index("hts_code")

    prev_codes = set(prev_indexed.index)
    curr_codes = set(curr_indexed.index)

    # Added
    for code in sorted(curr_codes - prev_codes):
        row = curr_indexed.loc[code]
        changes.append(
            {
                "hts_code": code,
                "change_type": "added",
                "old_value": None,
                "new_value": _get(row, "description"),
                "old_raw": None,
                "new_raw": _get(row, "rate_general_raw"),
                "detected_at": detected_at,
                "notes": "New HTS code detected",
            }
        )

    # Removed
    for code in sorted(prev_codes - curr_codes):
        row = prev_indexed.loc[code]
        changes.append(
            {
                "hts_code": code,
                "change_type": "removed",
                "old_value": _get(row, "description"),
                "new_value": None,
                "old_raw": _get(row, "rate_general_raw"),
                "new_raw": None,
                "detected_at": detected_at,
                "notes": "HTS code no longer present",
            }
        )

    # Changed rows
    for code in sorted(prev_codes & curr_codes):
        prev_row = prev_indexed.loc[code]
        curr_row = curr_indexed.loc[code]

        # Rate change
        old_rate = _get(prev_row, "rate_general_raw")
        new_rate = _get(curr_row, "rate_general_raw")
        if str(old_rate).strip() != str(new_rate).strip():
            old_val = _get(prev_row, "rate_general_value") if "rate_general_value" in prev_row.index else None
            new_val = _get(curr_row, "rate_general_value") if "rate_general_value" in curr_row.index else None
            changes.append(
                {
                    "hts_code": code,
                    "change_type": "changed_rate_general",
                    "old_value": old_val,
                    "new_value": new_val,
                    "old_raw": old_rate,
                    "new_raw": new_rate,
                    "detected_at": detected_at,
                    "notes": None,
                }
            )

        # Description change
        old_desc = str(_get(prev_row, "description") or "").strip()
        new_desc = str(_get(curr_row, "description") or "").strip()
        if old_desc != new_desc:
            changes.append(
                {
                    "hts_code": code,
                    "change_type": "changed_description",
                    "old_value": old_desc or None,
                    "new_value": new_desc or None,
                    "old_raw": None,
                    "new_raw": None,
                    "detected_at": detected_at,
                    "notes": None,
                }
            )

    logger.info(
        "Diff complete: %d added, %d removed, %d rate changes, %d desc changes",
        sum(1 for c in changes if c["change_type"] == "added"),
        sum(1 for c in changes if c["change_type"] == "removed"),
        sum(1 for c in changes if c["change_type"] == "changed_rate_general"),
        sum(1 for c in changes if c["change_type"] == "changed_description"),
    )
    return changes
