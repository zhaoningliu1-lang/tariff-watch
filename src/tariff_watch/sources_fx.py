"""
Exchange rate monitoring — tracks USD vs. major trade-partner currencies.

Provides current spot rates, 30-day history with trend analysis, and
landed-cost impact calculation for cross-border sellers.

Data sources (in priority order):
  1. SQLite cache (populated by scheduler from live APIs)
  2. ECB via frankfurter.app (free, no key, 14/18 currencies)
  3. exchangerate-api.com (optional, requires EXCHANGERATE_API_KEY, all 18 currencies)
  4. Calibrated simulation fallback for ECB-gap currencies (VND, BDT, PKR, TWD)

Usage::

    from .sources_fx import get_fx_rate, get_fx_history, get_all_fx_rates
    from .sources_fx import calculate_fx_impact

    rate = get_fx_rate("CNY")          # 1 USD = X CNY
    history = get_fx_history("CNY")    # 30-day daily rates
    impact = calculate_fx_impact("CNY", cog_local=32.0, units=100)
"""

from __future__ import annotations

import logging
import os
import random
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

import requests

logger = logging.getLogger(__name__)

# ── Configuration ────────────────────────────────────────────────────────────

_PREMIUM_API_KEY: str | None = os.environ.get("EXCHANGERATE_API_KEY")

# Currencies NOT covered by ECB/frankfurter — need premium or simulation
_ECB_GAP_CURRENCIES = {"VND", "BDT", "PKR", "TWD"}

# ── Currency metadata ────────────────────────────────────────────────────────

@dataclass
class CurrencyInfo:
    code: str           # ISO 4217
    name: str
    name_zh: str
    country: str
    country_zh: str
    symbol: str
    base_rate: float    # baseline USD/X rate (how many X per 1 USD)
    volatility: float   # daily volatility factor for simulation fallback

_CURRENCIES: dict[str, CurrencyInfo] = {
    "CNY": CurrencyInfo("CNY", "Chinese Yuan", "人民币", "China", "中国", "¥", 7.35, 0.003),
    "EUR": CurrencyInfo("EUR", "Euro", "欧元", "EU", "欧盟", "€", 0.92, 0.004),
    "GBP": CurrencyInfo("GBP", "British Pound", "英镑", "UK", "英国", "£", 0.79, 0.004),
    "JPY": CurrencyInfo("JPY", "Japanese Yen", "日元", "Japan", "日本", "¥", 152.5, 0.005),
    "KRW": CurrencyInfo("KRW", "South Korean Won", "韩元", "South Korea", "韩国", "₩", 1320.0, 0.004),
    "VND": CurrencyInfo("VND", "Vietnamese Dong", "越南盾", "Vietnam", "越南", "₫", 25200.0, 0.002),
    "INR": CurrencyInfo("INR", "Indian Rupee", "印度卢比", "India", "印度", "₹", 83.5, 0.003),
    "BDT": CurrencyInfo("BDT", "Bangladeshi Taka", "孟加拉塔卡", "Bangladesh", "孟加拉", "৳", 110.0, 0.002),
    "THB": CurrencyInfo("THB", "Thai Baht", "泰铢", "Thailand", "泰国", "฿", 35.8, 0.003),
    "IDR": CurrencyInfo("IDR", "Indonesian Rupiah", "印尼盾", "Indonesia", "印尼", "Rp", 15800.0, 0.003),
    "MYR": CurrencyInfo("MYR", "Malaysian Ringgit", "马来西亚林吉特", "Malaysia", "马来西亚", "RM", 4.72, 0.003),
    "PHP": CurrencyInfo("PHP", "Philippine Peso", "菲律宾比索", "Philippines", "菲律宾", "₱", 56.5, 0.003),
    "PKR": CurrencyInfo("PKR", "Pakistani Rupee", "巴基斯坦卢比", "Pakistan", "巴基斯坦", "Rs", 280.0, 0.002),
    "TWD": CurrencyInfo("TWD", "Taiwan Dollar", "新台币", "Taiwan", "台湾", "NT$", 31.8, 0.003),
    "MXN": CurrencyInfo("MXN", "Mexican Peso", "墨西哥比索", "Mexico", "墨西哥", "$", 17.2, 0.005),
    "CAD": CurrencyInfo("CAD", "Canadian Dollar", "加拿大元", "Canada", "加拿大", "C$", 1.36, 0.003),
    "BRL": CurrencyInfo("BRL", "Brazilian Real", "巴西雷亚尔", "Brazil", "巴西", "R$", 4.95, 0.006),
    "TRY": CurrencyInfo("TRY", "Turkish Lira", "土耳其里拉", "Turkey", "土耳其", "₺", 30.5, 0.004),
}

# Map ISO-2 country codes to currency codes
_COUNTRY_TO_CURRENCY: dict[str, str] = {
    "CN": "CNY", "CHN": "CNY", "CHINA": "CNY", "中国": "CNY", "PRC": "CNY",
    "DE": "EUR", "FR": "EUR", "IT": "EUR", "ES": "EUR", "NL": "EUR", "EU": "EUR",
    "GB": "GBP", "UK": "GBP",
    "JP": "JPY",
    "KR": "KRW",
    "VN": "VND", "VNM": "VND", "VIETNAM": "VND",
    "IN": "INR", "IND": "INR", "INDIA": "INR",
    "BD": "BDT", "BGD": "BDT",
    "TH": "THB",
    "ID": "IDR",
    "MY": "MYR",
    "PH": "PHP",
    "PK": "PKR",
    "TW": "TWD",
    "MX": "MXN", "MEX": "MXN",
    "CA": "CAD", "CAN": "CAD",
    "BR": "BRL",
    "TR": "TRY",
}


def _currency_for_origin(origin: str) -> str | None:
    """Resolve an origin code to its currency code."""
    key = origin.strip().upper()
    if key in _CURRENCIES:
        return key
    return _COUNTRY_TO_CURRENCY.get(key)


# ── Live data fetching ───────────────────────────────────────────────────────

def _fetch_ecb_latest() -> dict[str, float]:
    """Fetch latest rates from ECB via frankfurter.app (free, no key)."""
    try:
        resp = requests.get(
            "https://api.frankfurter.app/latest",
            params={"from": "USD"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("rates", {})
    except Exception as e:
        logger.warning("ECB fetch failed: %s", e)
        return {}


def _fetch_ecb_timeseries(days: int = 30) -> dict[str, dict[str, float]]:
    """Fetch date-range time series from ECB.

    Returns {date_str: {currency: rate, ...}, ...}.
    """
    end = date.today()
    start = end - timedelta(days=days)
    try:
        resp = requests.get(
            f"https://api.frankfurter.app/{start.isoformat()}..{end.isoformat()}",
            params={"from": "USD"},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("rates", {})
    except Exception as e:
        logger.warning("ECB time series fetch failed: %s", e)
        return {}


def _fetch_premium_latest(api_key: str) -> dict[str, float]:
    """Fetch latest rates from exchangerate-api.com (covers all 18 currencies)."""
    try:
        resp = requests.get(
            f"https://v6.exchangerate-api.com/v6/{api_key}/latest/USD",
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("result") != "success":
            logger.warning("Premium FX API error: %s", data.get("error-type"))
            return {}
        return data.get("conversion_rates", {})
    except Exception as e:
        logger.warning("Premium FX API fetch failed: %s", e)
        return {}


# ── Refresh functions (called by scheduler) ──────────────────────────────────

def refresh_fx_rates() -> dict[str, float]:
    """Fetch latest FX rates from live APIs and persist to SQLite.

    Priority: premium API (if key set) > ECB > simulation for gap currencies.
    Called by the background scheduler daily.
    """
    from . import data_store

    rates: dict[str, float] = {}
    sources: dict[str, str] = {}

    # Try premium first (covers all 18)
    if _PREMIUM_API_KEY:
        premium = _fetch_premium_latest(_PREMIUM_API_KEY)
        for code in _CURRENCIES:
            if code in premium:
                rates[code] = premium[code]
                sources[code] = "exchangerate_api"

    # Fill gaps with ECB
    missing = [c for c in _CURRENCIES if c not in rates]
    if missing:
        ecb = _fetch_ecb_latest()
        for code in missing:
            if code in ecb:
                rates[code] = ecb[code]
                sources[code] = "ecb"

    # Simulate remaining gap currencies
    still_missing = [c for c in _CURRENCIES if c not in rates]
    for code in still_missing:
        info = _CURRENCIES[code]
        # Try to anchor to last known rate from SQLite
        last = data_store.query_fx_latest(code)
        base = last["rate"] if last else info.base_rate
        delta = random.gauss(0, info.volatility)
        new_rate = base * (1 + delta)
        new_rate = max(info.base_rate * 0.90, min(info.base_rate * 1.10, new_rate))
        rates[code] = round(new_rate, 4 if new_rate < 100 else 2)
        sources[code] = "simulated"

    # Persist to SQLite
    today_str = date.today().isoformat()
    rows = [
        {"currency": code, "rate": rate, "rate_date": today_str, "source": sources[code]}
        for code, rate in rates.items()
    ]
    count = data_store.upsert_fx_rates_bulk(rows)
    data_store.set_meta("fx_last_refresh", today_str)
    logger.info("FX rates refreshed: %d currencies (%s)", count,
                {s: sum(1 for v in sources.values() if v == s) for s in set(sources.values())})

    # Clear in-memory cache so next read picks up new data
    _HISTORY_CACHE.clear()
    return rates


def refresh_fx_history_backfill(days: int = 30) -> int:
    """Backfill 30 days of ECB history into SQLite. Run once on first startup."""
    from . import data_store

    timeseries = _fetch_ecb_timeseries(days)
    if not timeseries:
        logger.warning("ECB backfill failed — no data returned")
        return 0

    rows = []
    for date_str, day_rates in timeseries.items():
        for code in _CURRENCIES:
            if code in day_rates:
                rows.append({
                    "currency": code,
                    "rate": day_rates[code],
                    "rate_date": date_str,
                    "source": "ecb",
                })

    # Also simulate gap currencies for the backfill period
    for code in _ECB_GAP_CURRENCIES:
        if code not in _CURRENCIES:
            continue
        info = _CURRENCIES[code]
        random.seed(hash(code) + 99)
        rate = info.base_rate
        sorted_dates = sorted(timeseries.keys())
        for d in sorted_dates:
            delta = random.gauss(0, info.volatility)
            rate = rate * (1 + delta)
            rate = max(info.base_rate * 0.90, min(info.base_rate * 1.10, rate))
            rows.append({
                "currency": code,
                "rate": round(rate, 4 if rate < 100 else 2),
                "rate_date": d,
                "source": "simulated",
            })

    count = data_store.upsert_fx_rates_bulk(rows)
    data_store.set_meta("fx_backfilled", "true")
    data_store.set_meta("fx_last_refresh", date.today().isoformat())
    logger.info("FX history backfilled: %d rows over %d days", count, days)
    return count


# ── History cache (SQLite first, mock fallback) ──────────────────────────────

_HISTORY_CACHE: dict[str, list[dict[str, Any]]] = {}


def _gen_rate_history(info: CurrencyInfo, days: int = 30) -> list[dict[str, Any]]:
    """Generate simulated daily FX rate history (fallback only)."""
    random.seed(hash(info.code) + 42)
    result = []
    rate = info.base_rate
    today = date.today()
    for i in range(days, -1, -1):
        delta = random.gauss(0, info.volatility)
        rate = rate * (1 + delta)
        rate = max(info.base_rate * 0.94, min(info.base_rate * 1.06, rate))
        result.append({
            "date": (today - timedelta(days=i)).isoformat(),
            "rate": round(rate, 4 if rate < 100 else 2),
        })
    return result


def _get_cached_history(currency: str) -> list[dict[str, Any]]:
    """Get rate history — SQLite first, then mock fallback."""
    # Try SQLite (live/backfilled data)
    try:
        from . import data_store
        rows = data_store.query_fx_history(currency, days=30)
        if rows and len(rows) >= 5:
            return rows
    except Exception:
        pass

    # Fallback to mock
    if currency not in _HISTORY_CACHE:
        info = _CURRENCIES.get(currency)
        if not info:
            return []
        _HISTORY_CACHE[currency] = _gen_rate_history(info)
    return _HISTORY_CACHE[currency]


# ── Public API ───────────────────────────────────────────────────────────────

@dataclass
class FXRate:
    currency: str
    currency_name: str
    currency_name_zh: str
    country: str
    country_zh: str
    symbol: str
    rate: float               # 1 USD = X local currency
    rate_30d_ago: float
    change_pct: float         # % change over 30 days (positive = USD strengthened)
    trend: str                # "usd_strengthening", "usd_weakening", "stable"
    trend_zh: str
    source: str = "mock"      # "ecb", "exchangerate_api", "simulated", "mock"

    def as_dict(self) -> dict:
        return {
            "currency": self.currency,
            "currency_name": self.currency_name,
            "currency_name_zh": self.currency_name_zh,
            "country": self.country,
            "country_zh": self.country_zh,
            "symbol": self.symbol,
            "rate_usd_to_local": self.rate,
            "rate_30d_ago": self.rate_30d_ago,
            "change_30d_pct": round(self.change_pct, 2),
            "trend": self.trend,
            "trend_zh": self.trend_zh,
            "source": self.source,
        }


def get_fx_rate(currency: str) -> FXRate | None:
    """Get current FX rate and 30-day trend for a currency."""
    code = currency.strip().upper()
    if code not in _CURRENCIES:
        code = _currency_for_origin(code)
    if not code or code not in _CURRENCIES:
        return None

    info = _CURRENCIES[code]
    history = _get_cached_history(code)
    if not history:
        return None

    current = history[-1]["rate"]
    ago = history[0]["rate"]
    change_pct = ((current - ago) / ago) * 100

    if change_pct > 1.0:
        trend, trend_zh = "usd_strengthening", "美元走强"
    elif change_pct < -1.0:
        trend, trend_zh = "usd_weakening", "美元走弱"
    else:
        trend, trend_zh = "stable", "稳定"

    # Determine data source
    source = "mock"
    try:
        from . import data_store
        latest = data_store.query_fx_latest(code)
        if latest:
            source = latest["source"]
    except Exception:
        pass

    return FXRate(
        currency=code,
        currency_name=info.name,
        currency_name_zh=info.name_zh,
        country=info.country,
        country_zh=info.country_zh,
        symbol=info.symbol,
        rate=current,
        rate_30d_ago=ago,
        change_pct=change_pct,
        trend=trend,
        trend_zh=trend_zh,
        source=source,
    )


def get_fx_history(currency: str) -> list[dict[str, Any]]:
    """Get 30-day daily FX rate history."""
    code = currency.strip().upper()
    if code not in _CURRENCIES:
        code = _currency_for_origin(code) or ""
    return _get_cached_history(code)


def get_all_fx_rates() -> list[dict]:
    """Get current rates for all tracked currencies."""
    results = []
    for code in sorted(_CURRENCIES.keys()):
        rate = get_fx_rate(code)
        if rate:
            results.append(rate.as_dict())
    return results


@dataclass
class FXImpact:
    currency: str
    origin: str
    cog_local: float          # cost of goods in local currency
    cog_usd_current: float    # COG in USD at current rate
    cog_usd_30d_ago: float    # COG in USD at 30-day-ago rate
    fx_impact_per_unit_usd: float   # per-unit cost difference
    fx_impact_total_usd: float
    units: int
    change_pct: float
    assessment: str
    assessment_zh: str

    def as_dict(self) -> dict:
        return {
            "currency": self.currency,
            "origin": self.origin,
            "cog_local_currency": self.cog_local,
            "cog_usd_current": round(self.cog_usd_current, 2),
            "cog_usd_30d_ago": round(self.cog_usd_30d_ago, 2),
            "fx_impact_per_unit_usd": round(self.fx_impact_per_unit_usd, 2),
            "fx_impact_total_usd": round(self.fx_impact_total_usd, 2),
            "units": self.units,
            "fx_change_30d_pct": round(self.change_pct, 2),
            "assessment": self.assessment,
            "assessment_zh": self.assessment_zh,
        }


def calculate_fx_impact(
    origin: str,
    cog_local: float,
    units: int = 100,
) -> FXImpact | None:
    """Calculate FX impact on cost of goods over the last 30 days."""
    code = origin.strip().upper()
    currency_code = _currency_for_origin(code) or code
    rate_obj = get_fx_rate(currency_code)
    if not rate_obj:
        return None

    cog_usd_now = cog_local / rate_obj.rate
    cog_usd_ago = cog_local / rate_obj.rate_30d_ago
    impact_per_unit = cog_usd_now - cog_usd_ago
    impact_total = impact_per_unit * units

    if impact_per_unit > 0.05:
        assessment = f"FX headwind: your costs rose ${abs(impact_per_unit):.2f}/unit as {rate_obj.currency} weakened"
        assessment_zh = f"汇率逆风：{rate_obj.currency_name_zh}贬值导致每件成本上升 ${abs(impact_per_unit):.2f}"
    elif impact_per_unit < -0.05:
        assessment = f"FX tailwind: your costs fell ${abs(impact_per_unit):.2f}/unit as {rate_obj.currency} strengthened"
        assessment_zh = f"汇率顺风：{rate_obj.currency_name_zh}升值导致每件成本下降 ${abs(impact_per_unit):.2f}"
    else:
        assessment = "FX neutral: minimal cost impact from currency movement"
        assessment_zh = "汇率中性：货币波动对成本影响极小"

    return FXImpact(
        currency=currency_code,
        origin=origin,
        cog_local=cog_local,
        cog_usd_current=cog_usd_now,
        cog_usd_30d_ago=cog_usd_ago,
        fx_impact_per_unit_usd=impact_per_unit,
        fx_impact_total_usd=impact_total,
        units=units,
        change_pct=rate_obj.change_pct,
        assessment=assessment,
        assessment_zh=assessment_zh,
    )
