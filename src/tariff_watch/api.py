"""FastAPI Web API for Tariff Watch V2."""

from __future__ import annotations

import logging
import os
from datetime import date, timedelta
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .db import (
    apply_schema,
    init_pool,
    query_current_rates,
    query_rate_history,
    query_recent_changes,
    query_recent_notices,
)
from .normalize import normalize_hts_code
from .sources_usitc import fetch_live_rates

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Tariff Watch API",
    description=(
        "Query current US HTS tariff rates, rate change history, "
        "and Federal Register tariff notices."
    ),
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    init_pool()
    apply_schema()
    logger.info("Tariff Watch API started.")


@app.on_event("shutdown")
def shutdown() -> None:
    from .db import close_pool
    close_pool()


# ── Health ───────────────────────────────────────────────────────────────────

@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    """Returns 200 OK when the API and database are reachable."""
    return {"status": "ok", "version": "2.0.0"}


# ── Tariff lookup ─────────────────────────────────────────────────────────────

@app.get("/tariff/{hts_code}", tags=["tariff"])
def get_tariff(hts_code: str) -> list[dict[str, Any]]:
    """
    Return current tariff rates for an HTS code or prefix.

    - Dots and spaces are stripped automatically.
    - A 6/8-digit code acts as a prefix and returns all matching rows.
    - The most recent database snapshot is used; if the database has not yet
      been populated by the weekly scheduler, data is fetched live from USITC.

    **Example:** `/tariff/0101.21.0010` or `/tariff/6111`
    """
    prefix = normalize_hts_code(hts_code)
    if not prefix:
        raise HTTPException(status_code=422, detail=f"Invalid HTS code: {hts_code!r}")

    rows = query_current_rates(prefix)
    if rows:
        return rows

    # DB is empty (scheduler has not run yet) — fall back to live USITC query.
    logger.info("DB has no data for prefix %s — trying live USITC lookup.", prefix)
    live_rows = fetch_live_rates(prefix)
    if live_rows:
        return live_rows

    raise HTTPException(
        status_code=404,
        detail=(
            f"No tariff data found for HTS prefix '{prefix}'. "
            "The database has not been populated yet and the live USITC lookup also "
            "returned no results. Try /live/tariff/{hts_code} for a direct query."
        ),
    )


# ── Live tariff lookup (always fresh from USITC) ──────────────────────────────

@app.get("/live/tariff/{hts_code}", tags=["tariff"])
def get_tariff_live(hts_code: str) -> list[dict[str, Any]]:
    """
    Return **live** tariff rates fetched directly from USITC (no database needed).

    The full HTS CSV is downloaded from USITC and cached in memory for up to
    1 hour. This endpoint always returns the most current published data and
    works even before the scheduler has run for the first time.

    - Dots and spaces are stripped automatically.
    - A 4/6/8-digit prefix returns all matching rows.

    **Example:** `/live/tariff/6111` or `/live/tariff/6111.20`
    """
    prefix = normalize_hts_code(hts_code)
    if not prefix:
        raise HTTPException(status_code=422, detail=f"Invalid HTS code: {hts_code!r}")

    rows = fetch_live_rates(prefix)
    if not rows:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No tariff data found for HTS prefix '{prefix}' in the live USITC "
                "table. Check that the HTS code prefix is valid."
            ),
        )
    return rows


@app.get("/tariff/{hts_code}/history", tags=["tariff"])
def get_tariff_history(
    hts_code: str,
    limit: int = Query(default=52, ge=1, le=200, description="Max snapshots to return"),
) -> list[dict[str, Any]]:
    """
    Return weekly rate history for an exact 10-digit HTS code.

    **Example:** `/tariff/0101210010/history?limit=12`
    """
    code = normalize_hts_code(hts_code)
    if not code:
        raise HTTPException(status_code=422, detail=f"Invalid HTS code: {hts_code!r}")

    rows = query_rate_history(code, limit=limit)
    if not rows:
        raise HTTPException(
            status_code=404,
            detail=f"No history found for HTS code '{code}'.",
        )
    return rows


# ── Changes ───────────────────────────────────────────────────────────────────

@app.get("/changes", tags=["changes"])
def get_changes(
    since: date = Query(
        default=date.today() - timedelta(days=30),
        description="Return changes on or after this date (YYYY-MM-DD)",
    ),
    hts: str | None = Query(default=None, description="Filter by HTS code prefix"),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[dict[str, Any]]:
    """
    Return detected tariff rate changes since a given date.

    **Example:** `/changes?since=2026-01-01&hts=6111`
    """
    prefix = normalize_hts_code(hts) if hts else None
    return query_recent_changes(since.isoformat(), hts_prefix=prefix, limit=limit)


# ── Federal Register ──────────────────────────────────────────────────────────

@app.get("/notices", tags=["notices"])
def get_notices(
    limit: int = Query(default=20, ge=1, le=100),
    agency: str | None = Query(default=None, description="Filter by agency name (partial match)"),
) -> list[dict[str, Any]]:
    """
    Return recent Federal Register tariff-related notices.

    **Example:** `/notices?limit=10&agency=USTR`
    """
    return query_recent_notices(limit=limit, agency=agency)
