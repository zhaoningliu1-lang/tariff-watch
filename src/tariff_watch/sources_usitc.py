"""Download and parse USITC HTS export data (CSV)."""

from __future__ import annotations

import io
import logging
from typing import TYPE_CHECKING

import pandas as pd

from .config import AppConfig, ConfigError
from .http import NetworkError, ParseError, download_text, get as http_get
from .normalize import normalize_dataframe, normalize_hts_code

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Canonical output columns. Sources may not supply all of them.
OUTPUT_COLUMNS = [
    "hts_code",
    "description",
    "rate_general_raw",
    "rate_special_raw",
    "rate_column2_raw",
]

# Common column name variants found in USITC exports → mapped to canonical names.
_COLUMN_ALIASES: dict[str, str] = {
    # hts_code
    "hts_number": "hts_code",
    "htsno": "hts_code",
    "hts": "hts_code",
    "hts_code": "hts_code",
    # description
    "brief_description": "description",
    "description": "description",
    "article_description": "description",
    # general rate
    "rate_of_duty_general": "rate_general_raw",
    "general_rate_of_duty": "rate_general_raw",
    "general": "rate_general_raw",
    "rate_general_raw": "rate_general_raw",
    # special rate
    "rate_of_duty_special": "rate_special_raw",
    "special": "rate_special_raw",
    "rate_special_raw": "rate_special_raw",
    # column 2
    "rate_of_duty_col2": "rate_column2_raw",
    "column_2": "rate_column2_raw",
    "col2": "rate_column2_raw",
    "rate_column2_raw": "rate_column2_raw",
}


def _rename_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Normalise column names using known aliases (case-insensitive)."""
    mapping = {
        col: _COLUMN_ALIASES[col.strip().lower().replace(" ", "_")]
        for col in df.columns
        if col.strip().lower().replace(" ", "_") in _COLUMN_ALIASES
    }
    df = df.rename(columns=mapping)
    # Ensure all OUTPUT_COLUMNS exist (fill with None if absent)
    for col in OUTPUT_COLUMNS:
        if col not in df.columns:
            logger.debug("Column '%s' not found in source — filling with None", col)
            df[col] = None
    return df[OUTPUT_COLUMNS]


def filter_tracked_hts(df: pd.DataFrame, tracked_codes: list[str]) -> pd.DataFrame:
    """
    Filter *df* to rows whose normalised HTS code starts with any of the
    normalised *tracked_codes* prefixes (supports 8- or 10-digit codes,
    with or without dots).

    A temporary column ``hts_code_norm`` is added then removed so the
    returned DataFrame keeps the same schema as the input.

    Args:
        df: Normalised HTS DataFrame (must contain an ``hts_code`` column).
        tracked_codes: Raw HTS code strings from config; may use dot notation.

    Returns:
        Filtered DataFrame (new object, original index reset).
    """
    norm_prefixes: list[str] = [
        n for c in tracked_codes
        if (n := normalize_hts_code(c)) is not None
    ]
    # Deduplicate while preserving determinism
    norm_prefixes = list(dict.fromkeys(norm_prefixes))

    if not norm_prefixes:
        logger.warning("filter_tracked_hts: no valid tracked codes supplied — returning empty DataFrame.")
        return df.iloc[0:0].copy()

    df = df.copy()
    df["_hts_norm"] = df["hts_code"].map(normalize_hts_code)

    mask = pd.Series(False, index=df.index)
    for prefix in norm_prefixes:
        mask |= df["_hts_norm"].str.startswith(prefix, na=False)

    filtered = df.loc[mask].drop(columns=["_hts_norm"]).reset_index(drop=True)

    matched_prefixes: list[str] = sorted(
        p for p in norm_prefixes
        if df["_hts_norm"].str.startswith(p, na=False).any()
    )
    unmatched_prefixes: list[str] = sorted(set(norm_prefixes) - set(matched_prefixes))

    if filtered.empty:
        logger.warning(
            "filter_tracked_hts: no rows matched any of %d tracked prefix(es): %s",
            len(norm_prefixes),
            norm_prefixes,
        )
    else:
        logger.info(
            "filter_tracked_hts: %d row(s) matched across %d/%d prefix(es): %s",
            len(filtered),
            len(matched_prefixes),
            len(norm_prefixes),
            matched_prefixes,
        )
        if unmatched_prefixes:
            logger.warning(
                "filter_tracked_hts: %d prefix(es) had NO matches: %s",
                len(unmatched_prefixes),
                unmatched_prefixes,
            )

    return filtered


def fetch_hts_dataframe(cfg: AppConfig) -> pd.DataFrame:
    """
    Download USITC HTS CSV export and return a normalised DataFrame.

    When ``cfg.mode == "tracked_only"`` the result is filtered via
    :func:`filter_tracked_hts` before returning.

    Raises:
        ConfigError: export URL is not configured.
        NetworkError: download failure.
        ParseError: CSV cannot be parsed.
    """
    url = cfg.sources.usitc_hts_export_url.strip()
    if not url or "PLACEHOLDER" in url:
        raise ConfigError(
            "sources.usitc_hts_export_url is not configured. "
            "Please obtain the CSV export URL from https://hts.usitc.gov/ "
            "and set it in config.yaml. See README.md for instructions."
        )

    logger.info("Downloading HTS export from %s", url)
    try:
        resp = http_get(url)
        # Decode with utf-8-sig so the UTF-8 BOM (if present) is stripped cleanly.
        # Using resp.text risks requests mis-detecting latin-1 and mangling the BOM.
        text = resp.content.decode("utf-8-sig")
    except NetworkError:
        raise
    except Exception as exc:
        raise ParseError(f"Failed to download CSV from {url}: {exc}") from exc

    try:
        df = pd.read_csv(io.StringIO(text), dtype=str, low_memory=False)
    except Exception as exc:
        raise ParseError(f"Failed to parse CSV from {url}: {exc}") from exc

    logger.info("Downloaded %d rows, %d columns", len(df), len(df.columns))

    df = _rename_columns(df)
    df = normalize_dataframe(df)

    if cfg.mode == "tracked_only" and cfg.tracked_hts:
        df = filter_tracked_hts(df, cfg.tracked_hts)

    return df