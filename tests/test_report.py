"""Tests for report.py"""

import json
import tempfile
from pathlib import Path

import pytest

from tariff_watch.report import (
    generate_markdown_report,
    generate_json_report,
    generate_telegram_summary,
    write_reports,
)

SAMPLE_CHANGES = [
    {
        "hts_code": "8542310000",
        "change_type": "changed_rate_general",
        "old_value": 0.0,
        "new_value": 5.0,
        "old_raw": "Free",
        "new_raw": "5%",
        "detected_at": "2025-01-01T00:00:00+00:00",
        "notes": None,
    },
    {
        "hts_code": "0202300050",
        "change_type": "added",
        "old_value": None,
        "new_value": "Frozen boneless beef",
        "old_raw": None,
        "new_raw": "26.4%",
        "detected_at": "2025-01-01T00:00:00+00:00",
        "notes": "New HTS code detected",
    },
]


def test_markdown_contains_title():
    md = generate_markdown_report(SAMPLE_CHANGES, "2025-01-06", "http://example.com", "tracked_only", [])
    assert "# Tariff Watch" in md


def test_markdown_contains_table_headers():
    md = generate_markdown_report(SAMPLE_CHANGES, "2025-01-06", "http://example.com", "tracked_only", [])
    assert "HTS Code" in md
    assert "Change Type" in md
    assert "Old Value" in md


def test_markdown_contains_disclaimer():
    md = generate_markdown_report(SAMPLE_CHANGES, "2025-01-06", "http://example.com", "tracked_only", [])
    assert "Disclaimer" in md


def test_telegram_summary_not_empty():
    summary = generate_telegram_summary(SAMPLE_CHANGES, "2025-01-06", "reports/report_20250106.md", "reports/report_20250106.json")
    assert summary.strip() != ""


def test_telegram_summary_contains_date():
    summary = generate_telegram_summary(SAMPLE_CHANGES, "2025-01-06", "reports/report_20250106.md", "reports/report_20250106.json")
    assert "2025-01-06" in summary


def test_telegram_summary_no_changes():
    summary = generate_telegram_summary([], "2025-01-06", "reports/r.md", "reports/r.json")
    assert "No changes" in summary


def test_telegram_summary_within_20_lines():
    summary = generate_telegram_summary(SAMPLE_CHANGES, "2025-01-06", "r.md", "r.json")
    assert len(summary.splitlines()) <= 20


def test_json_report_structure():
    report = generate_json_report(SAMPLE_CHANGES, "2025-01-06", "http://example.com", "tracked_only", ["8542310000"])
    assert "meta" in report
    assert "changes" in report
    assert report["meta"]["date"] == "2025-01-06"
    assert len(report["changes"]) == 2


def test_write_reports_creates_files():
    with tempfile.TemporaryDirectory() as tmpdir:
        md_path, json_path, summary = write_reports(
            changes=SAMPLE_CHANGES,
            reports_dir=tmpdir,
            source_url="http://example.com",
            mode="tracked_only",
            tracked_hts=["8542310000"],
            timezone_str="America/Los_Angeles",
        )
        assert md_path.exists()
        assert json_path.exists()
        data = json.loads(json_path.read_text())
        assert data["meta"]["total_changes"] == 2
        assert summary.strip() != ""
