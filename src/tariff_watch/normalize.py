"""Field cleaning and tariff rate parsing."""

from __future__ import annotations

import logging
import re

import pandas as pd

logger = logging.getLogger(__name__)

_RATE_FREE = re.compile(r"^\s*free\s*$", re.IGNORECASE)
_RATE_PERCENT = re.compile(r"^\s*([\d]+(?:\.[\d]+)?)\s*%\s*")


def normalize_hts_code(raw: str | None) -> str | None:
    """
    Normalise an HTS code string for consistent comparison and prefix matching.

    Strips all dots, spaces, and surrounding whitespace.  The resulting
    digit-only string is returned as-is (no zero-padding), so callers can use
    it both as an exact key and as a *startswith* prefix:

    - ``"0101.21.0010"`` → ``"0101210010"``  (10-digit)
    - ``"01012100"``      → ``"01012100"``    (8-digit prefix)
    - ``"0101.21"``       → ``"010121"``      (6-digit chapter/heading prefix)

    Returns:
        Cleaned digit string, or ``None`` for empty / NaN input.
    """
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return None
    cleaned = str(raw).replace(".", "").replace(" ", "").strip()
    return cleaned if cleaned else None


def parse_rate(raw: str | None) -> float | None:
    """
    Parse a tariff rate string into a float percentage value.

    Returns:
        0.0   for "Free" / "FREE"
        float for "5%" -> 5.0
        None  for unparseable strings
    """
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return None
    s = str(raw).strip()
    if not s:
        return None
    if _RATE_FREE.match(s):
        return 0.0
    m = _RATE_PERCENT.match(s)
    if m:
        return float(m.group(1))
    return None


def clean_description(raw: str | None) -> str | None:
    """Collapse multiple whitespace characters into single spaces."""
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return None
    return re.sub(r"\s+", " ", str(raw)).strip()


def normalize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Apply all normalisation transforms to a raw HTS DataFrame in-place (copy)."""
    df = df.copy()

    if "hts_code" in df.columns:
        df["hts_code"] = df["hts_code"].apply(normalize_hts_code)

    if "description" in df.columns:
        df["description"] = df["description"].apply(clean_description)

    for rate_col in ("rate_general_raw", "rate_special_raw", "rate_column2_raw"):
        parsed_col = rate_col.replace("_raw", "_value")
        if rate_col in df.columns:
            df[parsed_col] = df[rate_col].apply(parse_rate)

    # Drop rows where hts_code is None (header artefacts etc.)
    df = df.loc[df["hts_code"].notna()].reset_index(drop=True)
    return df
