"""Snapshot persistence, retrieval and retention management."""

from __future__ import annotations

import logging
import re
from datetime import date
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

_SNAPSHOT_RE = re.compile(r"hts_snapshot_(\d{8})\.csv$")


def _snapshot_path(snapshots_dir: Path, run_date: date) -> Path:
    return snapshots_dir / f"hts_snapshot_{run_date.strftime('%Y%m%d')}.csv"


def save_snapshot(df: pd.DataFrame, snapshots_dir: str | Path, run_date: date | None = None) -> Path:
    """Persist DataFrame as a dated CSV snapshot. Returns the written path."""
    if run_date is None:
        run_date = date.today()
    snapshots_dir = Path(snapshots_dir)
    snapshots_dir.mkdir(parents=True, exist_ok=True)
    path = _snapshot_path(snapshots_dir, run_date)
    df.to_csv(path, index=False)
    logger.info("Snapshot saved: %s (%d rows)", path, len(df))
    return path


def load_snapshot(path: str | Path) -> pd.DataFrame:
    """Load a snapshot CSV as a DataFrame."""
    return pd.read_csv(Path(path), dtype=str, low_memory=False)


def list_snapshots(snapshots_dir: str | Path) -> list[Path]:
    """Return all snapshot paths sorted oldest-first."""
    snapshots_dir = Path(snapshots_dir)
    if not snapshots_dir.exists():
        return []
    paths = [p for p in snapshots_dir.iterdir() if _SNAPSHOT_RE.match(p.name)]
    return sorted(paths, key=lambda p: p.name)


def find_previous_snapshot(snapshots_dir: str | Path, current_date: date | None = None) -> Path | None:
    """
    Return the most recent snapshot that is older than current_date.
    If current_date is None, returns the second-to-last snapshot (treating the last as current).
    """
    all_snaps = list_snapshots(snapshots_dir)
    if not all_snaps:
        return None

    if current_date is None:
        # Return second-to-last if available
        return all_snaps[-2] if len(all_snaps) >= 2 else None

    target = f"hts_snapshot_{current_date.strftime('%Y%m%d')}.csv"
    before = [p for p in all_snaps if p.name < target]
    return before[-1] if before else None


def apply_retention(snapshots_dir: str | Path, retain_weeks: int = 12) -> list[Path]:
    """Delete oldest snapshots beyond retain_weeks*2 quota. Returns deleted paths."""
    max_snapshots = max(retain_weeks * 2, 2)
    all_snaps = list_snapshots(snapshots_dir)
    to_delete = all_snaps[:-max_snapshots] if len(all_snaps) > max_snapshots else []
    for p in to_delete:
        p.unlink()
        logger.info("Deleted old snapshot: %s", p)
    return to_delete
