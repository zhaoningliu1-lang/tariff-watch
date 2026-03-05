"""
Global container shipping rate monitoring — tracks ocean freight costs
on major trade lanes to the US.

Covers major origin ports (China, Vietnam, India, EU, etc.) to US
West Coast and East Coast, with 30-day history and trend analysis.

Data sources:
  1. SQLite cache (populated by scheduler)
  2. Freightos API (optional, requires FREIGHTOS_API_KEY)
  3. Calibrated simulation fallback (daily Gaussian walk from last known rate)

Usage::

    from .sources_shipping import get_shipping_rate, get_all_routes
    from .sources_shipping import calculate_shipping_cost

    rate = get_shipping_rate("CN", "USWC")
    routes = get_all_routes(origin="CN")
    cost = calculate_shipping_cost("CN", "USWC", cbm=2.5)
"""

from __future__ import annotations

import logging
import os
import random
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

logger = logging.getLogger(__name__)

# ── Configuration ────────────────────────────────────────────────────────────

_FREIGHTOS_API_KEY: str | None = os.environ.get("FREIGHTOS_API_KEY")

# ── Route definitions ────────────────────────────────────────────────────────

@dataclass
class ShippingRoute:
    origin_code: str          # country ISO-2
    origin_port: str          # primary port name
    origin_port_zh: str
    destination: str          # "USWC" or "USEC"
    destination_port: str
    destination_port_zh: str
    transit_days: int         # typical transit time
    base_rate_20ft: float     # baseline rate per 20ft container (TEU) in USD
    base_rate_40ft: float     # baseline rate per 40ft container (FEU)
    base_rate_cbm: float      # per-CBM LCL rate
    volatility: float         # daily price volatility factor


_ROUTES: list[ShippingRoute] = [
    # ── China ────────────────────────────────────────────────────────────────
    ShippingRoute("CN", "Shanghai/Ningbo", "上海/宁波", "USWC", "Los Angeles/Long Beach", "洛杉矶/长滩", 14, 3200, 5800, 85, 0.015),
    ShippingRoute("CN", "Shanghai/Ningbo", "上海/宁波", "USEC", "New York/Newark", "纽约/纽瓦克", 28, 4500, 8200, 110, 0.015),
    ShippingRoute("CN", "Shenzhen/Guangzhou", "深圳/广州", "USWC", "Los Angeles/Long Beach", "洛杉矶/长滩", 15, 3400, 6100, 88, 0.015),
    ShippingRoute("CN", "Shenzhen/Guangzhou", "深圳/广州", "USEC", "New York/Newark", "纽约/纽瓦克", 30, 4700, 8500, 115, 0.015),

    # ── Vietnam ──────────────────────────────────────────────────────────────
    ShippingRoute("VN", "Ho Chi Minh City", "胡志明市", "USWC", "Los Angeles/Long Beach", "洛杉矶/长滩", 18, 2800, 5100, 78, 0.012),
    ShippingRoute("VN", "Ho Chi Minh City", "胡志明市", "USEC", "New York/Newark", "纽约/纽瓦克", 32, 4200, 7600, 105, 0.012),

    # ── India ────────────────────────────────────────────────────────────────
    ShippingRoute("IN", "Nhava Sheva/Mumbai", "孟买", "USWC", "Los Angeles/Long Beach", "洛杉矶/长滩", 25, 2600, 4700, 72, 0.010),
    ShippingRoute("IN", "Nhava Sheva/Mumbai", "孟买", "USEC", "New York/Newark", "纽约/纽瓦克", 22, 3200, 5800, 88, 0.010),
    ShippingRoute("IN", "Chennai", "金奈", "USEC", "New York/Newark", "纽约/纽瓦克", 24, 3400, 6100, 92, 0.010),

    # ── Bangladesh ───────────────────────────────────────────────────────────
    ShippingRoute("BD", "Chittagong", "吉大港", "USEC", "New York/Newark", "纽约/纽瓦克", 28, 3500, 6300, 95, 0.010),

    # ── Thailand ─────────────────────────────────────────────────────────────
    ShippingRoute("TH", "Laem Chabang", "林查班", "USWC", "Los Angeles/Long Beach", "洛杉矶/长滩", 20, 2900, 5200, 80, 0.012),

    # ── Indonesia ────────────────────────────────────────────────────────────
    ShippingRoute("ID", "Jakarta/Tanjung Priok", "雅加达", "USWC", "Los Angeles/Long Beach", "洛杉矶/长滩", 22, 2700, 4900, 75, 0.012),

    # ── South Korea ──────────────────────────────────────────────────────────
    ShippingRoute("KR", "Busan", "釜山", "USWC", "Los Angeles/Long Beach", "洛杉矶/长滩", 12, 2200, 4000, 65, 0.010),
    ShippingRoute("KR", "Busan", "釜山", "USEC", "New York/Newark", "纽约/纽瓦克", 26, 3600, 6500, 95, 0.010),

    # ── Japan ────────────────────────────────────────────────────────────────
    ShippingRoute("JP", "Tokyo/Yokohama", "东京/横滨", "USWC", "Los Angeles/Long Beach", "洛杉矶/长滩", 11, 2000, 3600, 60, 0.008),

    # ── Taiwan ───────────────────────────────────────────────────────────────
    ShippingRoute("TW", "Kaohsiung", "高雄", "USWC", "Los Angeles/Long Beach", "洛杉矶/长滩", 13, 2400, 4300, 68, 0.010),

    # ── EU (Germany as representative) ───────────────────────────────────────
    ShippingRoute("DE", "Hamburg/Bremerhaven", "汉堡/不来梅", "USEC", "New York/Newark", "纽约/纽瓦克", 10, 1800, 3200, 55, 0.008),
    ShippingRoute("DE", "Hamburg/Bremerhaven", "汉堡/不来梅", "USWC", "Los Angeles/Long Beach", "洛杉矶/长滩", 24, 3000, 5400, 85, 0.008),

    # ── UK ───────────────────────────────────────────────────────────────────
    ShippingRoute("GB", "Felixstowe/Southampton", "费利克斯托/南安普顿", "USEC", "New York/Newark", "纽约/纽瓦克", 9, 1600, 2900, 50, 0.008),

    # ── Mexico ───────────────────────────────────────────────────────────────
    ShippingRoute("MX", "Manzanillo", "曼萨尼约", "USWC", "Los Angeles/Long Beach", "洛杉矶/长滩", 5, 1200, 2200, 40, 0.010),
    ShippingRoute("MX", "Veracruz", "韦拉克鲁斯", "USEC", "Houston", "休斯顿", 4, 1000, 1800, 35, 0.010),

    # ── Brazil ───────────────────────────────────────────────────────────────
    ShippingRoute("BR", "Santos", "桑托斯", "USEC", "New York/Newark", "纽约/纽瓦克", 14, 2400, 4300, 70, 0.012),

    # ── Turkey ───────────────────────────────────────────────────────────────
    ShippingRoute("TR", "Mersin/Istanbul", "梅尔辛/伊斯坦布尔", "USEC", "New York/Newark", "纽约/纽瓦克", 18, 2800, 5000, 78, 0.010),

    # ── Pakistan ─────────────────────────────────────────────────────────────
    ShippingRoute("PK", "Karachi", "卡拉奇", "USEC", "New York/Newark", "纽约/纽瓦克", 26, 3200, 5700, 88, 0.010),

    # ── Malaysia ─────────────────────────────────────────────────────────────
    ShippingRoute("MY", "Port Klang", "巴生港", "USWC", "Los Angeles/Long Beach", "洛杉矶/长滩", 20, 2500, 4500, 72, 0.010),

    # ── Philippines ──────────────────────────────────────────────────────────
    ShippingRoute("PH", "Manila", "马尼拉", "USWC", "Los Angeles/Long Beach", "洛杉矶/长滩", 18, 2600, 4700, 75, 0.010),
]


# ── Route key helper ─────────────────────────────────────────────────────────

def _route_key(route: ShippingRoute) -> str:
    return f"{route.origin_code}:{route.origin_port}:{route.destination}"


# ── Simulation helpers ───────────────────────────────────────────────────────

def _simulate_daily_step(
    route: ShippingRoute, prev_20ft: float,
) -> tuple[float, float]:
    """Apply one day of Gaussian walk from the previous rate."""
    delta = random.gauss(0.001, route.volatility)
    new_20 = prev_20ft * (1 + delta)
    new_20 = max(route.base_rate_20ft * 0.85, min(route.base_rate_20ft * 1.20, new_20))
    new_40 = new_20 * (route.base_rate_40ft / route.base_rate_20ft)
    return round(new_20, 0), round(new_40, 0)


def _gen_shipping_history(route: ShippingRoute, days: int = 30) -> list[dict[str, Any]]:
    """Generate simulated daily shipping rate history (fallback only)."""
    seed = hash(f"{route.origin_code}-{route.destination}-{route.origin_port}") + 42
    random.seed(seed)
    result = []
    rate_20 = route.base_rate_20ft
    rate_40 = route.base_rate_40ft
    today = date.today()
    for i in range(days, -1, -1):
        delta = random.gauss(0.001, route.volatility)
        rate_20 = rate_20 * (1 + delta)
        rate_20 = max(route.base_rate_20ft * 0.85, min(route.base_rate_20ft * 1.20, rate_20))
        rate_40 = rate_20 * (route.base_rate_40ft / route.base_rate_20ft)
        result.append({
            "date": (today - timedelta(days=i)).isoformat(),
            "rate_20ft_usd": round(rate_20, 0),
            "rate_40ft_usd": round(rate_40, 0),
        })
    return result


# ── History cache (SQLite first, mock fallback) ──────────────────────────────

_SHIPPING_HISTORY_CACHE: dict[str, list[dict[str, Any]]] = {}


def _get_cached_shipping_history(route: ShippingRoute) -> list[dict[str, Any]]:
    """Get rate history — SQLite first, then mock fallback."""
    key = _route_key(route)

    # Try SQLite (persisted data from scheduler)
    try:
        from . import data_store
        rows = data_store.query_shipping_history(key, days=30)
        if rows and len(rows) >= 5:
            return rows
    except Exception:
        pass

    # Fallback to mock
    if key not in _SHIPPING_HISTORY_CACHE:
        _SHIPPING_HISTORY_CACHE[key] = _gen_shipping_history(route)
    return _SHIPPING_HISTORY_CACHE[key]


# ── Refresh function (called by scheduler) ───────────────────────────────────

def refresh_shipping_rates() -> int:
    """Persist today's shipping rates to SQLite.

    If FREIGHTOS_API_KEY is set, fetches real rates (stub — Freightos API
    requires paid registration). Otherwise, takes yesterday's rate from
    SQLite and applies one step of Gaussian walk simulation.

    Called by the background scheduler daily.
    """
    from . import data_store

    today_str = date.today().isoformat()
    rows = []

    for route in _ROUTES:
        key = _route_key(route)
        source = "simulated"
        rate_20ft = route.base_rate_20ft
        rate_40ft = route.base_rate_40ft

        # Try Freightos API if key available
        if _FREIGHTOS_API_KEY:
            # Stub: Freightos API requires paid registration
            # When implemented, fetch real rates here and set source = "freightos"
            logger.debug("Freightos API integration not yet configured for route %s", key)

        # Get previous rate from SQLite for simulation continuity
        prev = data_store.query_shipping_latest(key)
        if prev:
            rate_20ft, rate_40ft = _simulate_daily_step(route, prev["rate_20ft"])
        else:
            # First run — use base rate with small random offset
            rate_20ft, rate_40ft = _simulate_daily_step(route, route.base_rate_20ft)

        rows.append({
            "route_key": key,
            "rate_20ft": rate_20ft,
            "rate_40ft": rate_40ft,
            "rate_date": today_str,
            "source": source,
        })

    count = data_store.upsert_shipping_rates_bulk(rows)
    data_store.set_meta("shipping_last_refresh", today_str)

    # Clear in-memory cache so next read picks up new data
    _SHIPPING_HISTORY_CACHE.clear()

    logger.info("Shipping rates refreshed: %d routes", count)
    return count


def refresh_shipping_history_backfill(days: int = 30) -> int:
    """Backfill 30 days of simulated shipping history into SQLite."""
    from . import data_store

    today = date.today()
    rows = []

    for route in _ROUTES:
        key = _route_key(route)
        seed = hash(f"{route.origin_code}-{route.destination}-{route.origin_port}") + 99
        random.seed(seed)
        rate_20 = route.base_rate_20ft

        for i in range(days, -1, -1):
            delta = random.gauss(0.001, route.volatility)
            rate_20 = rate_20 * (1 + delta)
            rate_20 = max(route.base_rate_20ft * 0.85, min(route.base_rate_20ft * 1.20, rate_20))
            rate_40 = rate_20 * (route.base_rate_40ft / route.base_rate_20ft)
            rows.append({
                "route_key": key,
                "rate_20ft": round(rate_20, 0),
                "rate_40ft": round(rate_40, 0),
                "rate_date": (today - timedelta(days=i)).isoformat(),
                "source": "simulated",
            })

    count = data_store.upsert_shipping_rates_bulk(rows)
    data_store.set_meta("shipping_backfilled", "true")
    logger.info("Shipping history backfilled: %d rows over %d days", count, days)
    return count


# ── Route finder ─────────────────────────────────────────────────────────────

def _find_routes(origin: str, destination: str | None = None) -> list[ShippingRoute]:
    """Find matching routes for an origin and optional destination."""
    origin_key = origin.strip().upper()
    results = [r for r in _ROUTES if r.origin_code == origin_key]
    if destination:
        dest_key = destination.strip().upper()
        results = [r for r in results if r.destination == dest_key]
    return results


# ── Public API ───────────────────────────────────────────────────────────────

@dataclass
class ShippingRate:
    origin_code: str
    origin_port: str
    origin_port_zh: str
    destination: str
    destination_port: str
    destination_port_zh: str
    transit_days: int
    rate_20ft_usd: float      # current rate per 20ft container
    rate_40ft_usd: float      # current rate per 40ft container
    rate_cbm_usd: float       # current per-CBM LCL rate
    rate_20ft_30d_ago: float
    change_pct: float
    trend: str
    trend_zh: str

    def as_dict(self) -> dict:
        return {
            "origin_code": self.origin_code,
            "origin_port": self.origin_port,
            "origin_port_zh": self.origin_port_zh,
            "destination": self.destination,
            "destination_port": self.destination_port,
            "destination_port_zh": self.destination_port_zh,
            "transit_days": self.transit_days,
            "current_rates": {
                "rate_20ft_usd": round(self.rate_20ft_usd),
                "rate_40ft_usd": round(self.rate_40ft_usd),
                "rate_cbm_lcl_usd": round(self.rate_cbm_usd),
            },
            "rate_20ft_30d_ago": round(self.rate_20ft_30d_ago),
            "change_30d_pct": round(self.change_pct, 1),
            "trend": self.trend,
            "trend_zh": self.trend_zh,
        }


def get_shipping_rate(origin: str, destination: str = "USWC") -> list[dict]:
    """Get current shipping rates for an origin-destination pair."""
    routes = _find_routes(origin, destination)
    results = []
    for route in routes:
        history = _get_cached_shipping_history(route)
        current_20 = history[-1]["rate_20ft_usd"]
        current_40 = history[-1]["rate_40ft_usd"]
        ago_20 = history[0]["rate_20ft_usd"]
        change = ((current_20 - ago_20) / ago_20) * 100

        if change > 5:
            trend, trend_zh = "rising", "上涨"
        elif change < -5:
            trend, trend_zh = "falling", "下降"
        else:
            trend, trend_zh = "stable", "稳定"

        sr = ShippingRate(
            origin_code=route.origin_code,
            origin_port=route.origin_port,
            origin_port_zh=route.origin_port_zh,
            destination=route.destination,
            destination_port=route.destination_port,
            destination_port_zh=route.destination_port_zh,
            transit_days=route.transit_days,
            rate_20ft_usd=current_20,
            rate_40ft_usd=current_40,
            rate_cbm_usd=route.base_rate_cbm,
            rate_20ft_30d_ago=ago_20,
            change_pct=change,
            trend=trend,
            trend_zh=trend_zh,
        )
        results.append(sr.as_dict())
    return results


def get_shipping_history(origin: str, destination: str = "USWC") -> list[dict]:
    """Get 30-day rate history for a shipping route."""
    routes = _find_routes(origin, destination)
    if not routes:
        return []
    route = routes[0]
    history = _get_cached_shipping_history(route)
    return [{**h, "origin": route.origin_port, "destination": route.destination_port} for h in history]


def get_all_routes(origin: str | None = None) -> list[dict]:
    """Get current rates for all routes, optionally filtered by origin."""
    results = []
    for route in _ROUTES:
        if origin and route.origin_code != origin.strip().upper():
            continue
        history = _get_cached_shipping_history(route)
        current_20 = history[-1]["rate_20ft_usd"]
        ago_20 = history[0]["rate_20ft_usd"]
        change = ((current_20 - ago_20) / ago_20) * 100
        results.append({
            "origin_code": route.origin_code,
            "origin_port": route.origin_port,
            "origin_port_zh": route.origin_port_zh,
            "destination": route.destination,
            "destination_port": route.destination_port,
            "transit_days": route.transit_days,
            "rate_20ft_usd": round(current_20),
            "rate_40ft_usd": round(history[-1]["rate_40ft_usd"]),
            "change_30d_pct": round(change, 1),
        })
    return results


@dataclass
class ShippingCostEstimate:
    origin: str
    destination: str
    method: str               # "FCL_20", "FCL_40", "LCL"
    container_rate_usd: float
    cbm: float
    units: int
    cost_per_unit_usd: float
    total_shipping_usd: float
    transit_days: int

    def as_dict(self) -> dict:
        return {
            "origin": self.origin,
            "destination": self.destination,
            "method": self.method,
            "container_rate_usd": round(self.container_rate_usd),
            "cbm": self.cbm,
            "units": self.units,
            "cost_per_unit_usd": round(self.cost_per_unit_usd, 2),
            "total_shipping_usd": round(self.total_shipping_usd, 2),
            "transit_days": self.transit_days,
        }


def calculate_shipping_cost(
    origin: str,
    destination: str = "USWC",
    cbm: float = 1.0,
    units: int = 100,
) -> list[dict]:
    """
    Calculate shipping cost per unit for different methods (FCL 20ft, FCL 40ft, LCL).

    Args:
        origin: Country code (e.g. "CN", "VN")
        destination: "USWC" or "USEC"
        cbm: Total cubic meters of the shipment
        units: Number of product units in the shipment
    """
    routes = _find_routes(origin, destination)
    if not routes:
        return []

    route = routes[0]
    history = _get_cached_shipping_history(route)
    current_20 = history[-1]["rate_20ft_usd"]
    current_40 = current_20 * (route.base_rate_40ft / route.base_rate_20ft)
    cbm_rate = route.base_rate_cbm

    results = []
    units = max(1, units)

    # LCL
    lcl_total = cbm * cbm_rate
    results.append(ShippingCostEstimate(
        origin=route.origin_code,
        destination=route.destination,
        method="LCL",
        container_rate_usd=cbm_rate,
        cbm=cbm,
        units=units,
        cost_per_unit_usd=lcl_total / units,
        total_shipping_usd=lcl_total,
        transit_days=route.transit_days + 5,  # LCL adds consolidation time
    ).as_dict())

    # FCL 20ft (capacity ~28 CBM)
    containers_20 = max(1, int(cbm / 28) + (1 if cbm % 28 > 0 else 0))
    fcl20_total = containers_20 * current_20
    results.append(ShippingCostEstimate(
        origin=route.origin_code,
        destination=route.destination,
        method="FCL_20ft",
        container_rate_usd=current_20,
        cbm=cbm,
        units=units,
        cost_per_unit_usd=fcl20_total / units,
        total_shipping_usd=fcl20_total,
        transit_days=route.transit_days,
    ).as_dict())

    # FCL 40ft (capacity ~58 CBM)
    containers_40 = max(1, int(cbm / 58) + (1 if cbm % 58 > 0 else 0))
    fcl40_total = containers_40 * current_40
    results.append(ShippingCostEstimate(
        origin=route.origin_code,
        destination=route.destination,
        method="FCL_40ft",
        container_rate_usd=current_40,
        cbm=cbm,
        units=units,
        cost_per_unit_usd=fcl40_total / units,
        total_shipping_usd=fcl40_total,
        transit_days=route.transit_days,
    ).as_dict())

    return results
