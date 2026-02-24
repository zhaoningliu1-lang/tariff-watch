"""Tests for diff.py"""

import pandas as pd
import pytest

from tariff_watch.diff import compute_diff


def _make_df(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows)


PREV = _make_df(
    [
        {"hts_code": "8471300000", "description": "Portable machines", "rate_general_raw": "Free"},
        {"hts_code": "8542310000", "description": "IC processors", "rate_general_raw": "Free"},
        {"hts_code": "0101210000", "description": "Breeding horses", "rate_general_raw": "Free"},
    ]
)

CURRENT = _make_df(
    [
        {"hts_code": "8471300000", "description": "Portable machines", "rate_general_raw": "Free"},
        {"hts_code": "8542310000", "description": "IC processors updated", "rate_general_raw": "5%"},
        {"hts_code": "0202300050", "description": "Frozen boneless beef", "rate_general_raw": "26.4%"},
    ]
)


def test_detects_added():
    changes = compute_diff(PREV, CURRENT, detected_at="2025-01-01T00:00:00+00:00")
    added = [c for c in changes if c["change_type"] == "added"]
    assert any(c["hts_code"] == "0202300050" for c in added)


def test_detects_removed():
    changes = compute_diff(PREV, CURRENT, detected_at="2025-01-01T00:00:00+00:00")
    removed = [c for c in changes if c["change_type"] == "removed"]
    assert any(c["hts_code"] == "0101210000" for c in removed)


def test_detects_rate_change():
    changes = compute_diff(PREV, CURRENT, detected_at="2025-01-01T00:00:00+00:00")
    rate_changes = [c for c in changes if c["change_type"] == "changed_rate_general"]
    assert any(c["hts_code"] == "8542310000" for c in rate_changes)
    match = next(c for c in rate_changes if c["hts_code"] == "8542310000")
    assert match["old_raw"] == "Free"
    assert match["new_raw"] == "5%"


def test_detects_description_change():
    changes = compute_diff(PREV, CURRENT, detected_at="2025-01-01T00:00:00+00:00")
    desc_changes = [c for c in changes if c["change_type"] == "changed_description"]
    assert any(c["hts_code"] == "8542310000" for c in desc_changes)


def test_no_changes_when_identical():
    changes = compute_diff(PREV, PREV, detected_at="2025-01-01T00:00:00+00:00")
    assert changes == []


def test_empty_prev_no_changes():
    changes = compute_diff(pd.DataFrame(), CURRENT)
    assert changes == []
