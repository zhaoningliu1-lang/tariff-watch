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
from .normalize import normalize_hts_code, parse_rate
from .sources_usitc import fetch_live_rates
from .tariff_overlay import compute_overlay

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
    try:
        init_pool()
        apply_schema()
        logger.info("Tariff Watch API started (PostgreSQL connected).")
    except Exception as e:
        logger.warning("PostgreSQL not available, running in live-only mode: %s", e)


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

@app.get("/tariff/news", tags=["tariff"])
def tariff_news(
    limit: int = Query(default=20, ge=1, le=100, description="Max number of news items to return"),
) -> list[dict[str, Any]]:
    """Return recent tariff and trade policy news items."""
    return get_tariff_news(limit=limit)


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

    try:
        rows = query_current_rates(prefix)
    except Exception:
        rows = []
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


# ── Effective tariff (MFN + all overlays by origin) ───────────────────────────

def _lookup_base_rate(hts: str) -> tuple[float, str]:
    """Return (base_rate_pct, source) for a normalized HTS code.

    Walks from the full code toward a 5-digit prefix until a rate is found
    in the live USITC table.  Returns (0.0, "not_found") if nothing matches.
    """
    import re as _re
    try:
        rows = fetch_live_rates(hts[:4])
        rate_map: dict[str, str] = {}
        for r in rows:
            raw_code = normalize_hts_code(str(r.get("hts_code") or ""))
            raw = str(r.get("rate_general_raw") or "").strip()
            if raw_code and raw and raw.lower() not in ("none", ""):
                rate_map[raw_code] = raw
        for length in range(len(hts), 4, -1):
            candidate = hts[:length]
            if candidate in rate_map:
                raw = rate_map[candidate]
                if raw.strip().lower() == "free":
                    return 0.0, "usitc_live"
                m = _re.search(r"(\d+\.?\d*)%", raw)
                if m:
                    return float(m.group(1)), "usitc_live"
    except Exception:
        pass
    return 0.0, "not_found"


@app.get("/tariff/{hts_code}/effective", tags=["tariff"])
def get_tariff_effective(
    hts_code: str,
    origin: str = Query(
        default="CN",
        description="Country of origin — ISO-2 or ISO-3 code, e.g. 'CN', 'VN', 'MX', 'IN'",
    ),
) -> dict:
    """
    Return the **confirmed, in-force effective tariff rate** for an HTS code and origin.

    Stacks confirmed additional duties on top of the USITC base MFN rate:
    - **Section 232** — steel (+25%) and aluminum (+10%), all origins except USMCA partners
    - **Section 301** — China-specific duties (+25% most goods; +7.5% apparel/footwear ch. 61–64)

    IEEPA tariffs (fentanyl/reciprocal) were struck down by SCOTUS on 2026-02-20 and are NOT included.

    The Section 122 temporary 10% global surcharge (in effect from 2026-02-24) is noted in
    the `advisory` field but excluded from `effective_total_pct` — verify before shipment.

    **Example:** `/tariff/7604101000/effective?origin=CN`
    """
    code = normalize_hts_code(hts_code)
    if not code:
        raise HTTPException(status_code=422, detail=f"Invalid HTS code: {hts_code!r}")

    base_pct, source = _lookup_base_rate(code)
    overlay = compute_overlay(hts_code=code, origin=origin, base_rate_pct=base_pct)
    result = overlay.as_dict()
    result["base_rate_source"] = source
    return result


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
    if not code:  # type: ignore[truthy-bool]
        raise HTTPException(status_code=422, detail=f"Invalid HTS code: {hts_code!r}")

    rows = []
    try:
        rows = query_rate_history(code, limit=limit)
    except Exception:
        pass
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
    try:
        return query_recent_changes(since.isoformat(), hts_prefix=prefix, limit=limit)
    except Exception:
        return []


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
    try:
        return query_recent_notices(limit=limit, agency=agency)
    except Exception:
        return []


# ── Amazon Product Analytics ──────────────────────────────────────────────────

from .sources_amazon import (  # noqa: E402
    calculate_profit,
    get_category_stats,
    get_competitor_data,
    get_product,
    get_tariff_news,
    get_trending_products,
    search_products,
)


@app.get("/amazon/search", tags=["amazon"])
def amazon_search(
    q: str = Query(description="Keyword to search (e.g. 'yoga mat', 'electronics')"),
) -> list[dict[str, Any]]:
    """Search Amazon product catalogue. Returns matching products with BSR, rating, HTS code."""
    return search_products(q)


@app.get("/amazon/product/{asin}", tags=["amazon"])
def amazon_product(asin: str) -> dict[str, Any]:
    """Return full product details including 30-day price and BSR history."""
    p = get_product(asin.upper())
    if not p:
        raise HTTPException(status_code=404, detail=f"ASIN '{asin}' not found.")
    return p


@app.get("/amazon/profit/{asin}", tags=["amazon"])
def amazon_profit(
    asin: str,
    origin: str = Query(
        default="CN",
        description="Country of origin — ISO-2 or ISO-3 code, e.g. 'CN', 'VN', 'MX', 'IN'",
    ),
) -> dict[str, Any]:
    """
    Calculate profit breakdown for a product with full tariff stack by origin country.

    Tariff = MFN base rate (live USITC) + Section 232 + Section 301 + 2025 exec. order.
    Pass `?origin=VN` for Vietnam, `?origin=MX` for Mexico, etc.  Default: China (CN).
    """
    p = get_product(asin.upper())
    if not p:
        raise HTTPException(status_code=404, detail=f"ASIN '{asin}' not found.")

    hts: str | None = normalize_hts_code(p["hts_code"])
    base_pct, source = _lookup_base_rate(hts) if hts else (0.0, "no_hts")
    overlay = compute_overlay(hts_code=hts or "", origin=origin, base_rate_pct=base_pct)
    tariff_rate = overlay.effective_total_pct / 100.0

    result = calculate_profit(asin.upper(), tariff_rate=tariff_rate)
    if result:
        result["tariff_source"] = source
        result["tariff_breakdown"] = overlay.as_dict()
        result["breakdown"]["tariff_rate_pct"] = round(overlay.effective_total_pct, 2)
    return result or {}


@app.get("/amazon/competitor/{asin}", tags=["amazon"])
def amazon_competitor(asin: str) -> dict[str, Any]:
    """Return 30-day price and BSR trend for competitor monitoring."""
    data = get_competitor_data(asin.upper())
    if not data:
        raise HTTPException(status_code=404, detail=f"ASIN '{asin}' not found.")
    return data


@app.get("/amazon/trending", tags=["amazon"])
def amazon_trending(
    category: str = Query(default="All", description="Category filter, or 'All'"),
    limit: int = Query(default=15, ge=1, le=50),
) -> list[dict[str, Any]]:
    """Return trending products ranked by review velocity, BSR, and rating."""
    return get_trending_products(category=category if category != "All" else None, limit=limit)


@app.get("/amazon/categories", tags=["amazon"])
def amazon_categories() -> list[dict[str, Any]]:
    """Return category-level market stats: avg price, margin, competition, opportunity score."""
    return get_category_stats()



