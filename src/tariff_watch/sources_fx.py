"""
Exchange rate monitoring — tracks USD vs. major trade-partner currencies.

Provides current spot rates, 30-day history with trend analysis, and
landed-cost impact calculation for cross-border sellers.

Data is currently mock (realistic ranges based on Feb 2026 market levels).
Replace with a live API (e.g. ECB, Open Exchange Rates, Frankfurter) for
production use.

Usage::

    from .sources_fx import get_fx_rate, get_fx_history, get_all_fx_rates
    from .sources_fx import calculate_fx_impact

    rate = get_fx_rate("CNY")          # 1 USD = X CNY
    history = get_fx_history("CNY")    # 30-day daily rates
    impact = calculate_fx_impact("CNY", cog_local=32.0, units=100)
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any


_TODAY = date(2026, 3, 4)

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
    volatility: float   # daily volatility factor for mock data

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
    "CA": "CAN", "CAN": "CAD",
    "BR": "BRL",
    "TR": "TRY",
}


def _currency_for_origin(origin: str) -> str | None:
    """Resolve an origin code to its currency code."""
    key = origin.strip().upper()
    if key in _CURRENCIES:
        return key
    return _COUNTRY_TO_CURRENCY.get(key)


# ── Mock rate generation ─────────────────────────────────────────────────────

def _gen_rate_history(info: CurrencyInfo, days: int = 30) -> list[dict[str, Any]]:
    """Generate realistic daily FX rate history."""
    random.seed(hash(info.code) + 42)  # deterministic per currency
    result = []
    rate = info.base_rate
    for i in range(days, -1, -1):
        delta = random.gauss(0, info.volatility)
        rate = rate * (1 + delta)
        rate = max(info.base_rate * 0.94, min(info.base_rate * 1.06, rate))
        result.append({
            "date": (_TODAY - timedelta(days=i)).isoformat(),
            "rate": round(rate, 4 if rate < 100 else 2),
        })
    return result


_HISTORY_CACHE: dict[str, list[dict[str, Any]]] = {}


def _get_cached_history(currency: str) -> list[dict[str, Any]]:
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
