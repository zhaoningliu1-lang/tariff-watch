"""
Anti-dumping (AD) and countervailing duty (CVD) order database.

Contains curated active AD/CVD orders against China based on Commerce Dept.
ITA records.  Rates shown are the "all others" rate — the rate applied to
Chinese exporters that have not received an individual rate through an
administrative review.  Actual rates are company-specific.

Usage::

    from .antidumping import lookup_adcvd

    exposure = lookup_adcvd("7604101000", origin="CN")
    print(exposure.as_dict())
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .normalize import normalize_hts_code


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class ADCVDOrder:
    case_number: str
    order_type: str                # "AD", "CVD", or "AD+CVD"
    product_description: str
    product_description_zh: str
    country: str                   # ISO-2
    hts_prefixes: list[str]        # 4-digit HTS prefixes covered
    rate_range_low_pct: float
    rate_range_high_pct: float
    all_others_rate_pct: float
    effective_date: str
    status: str                    # "active"
    federal_register_citation: str
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "case_number": self.case_number,
            "order_type": self.order_type,
            "product_description": self.product_description,
            "product_description_zh": self.product_description_zh,
            "country": self.country,
            "hts_prefixes": self.hts_prefixes,
            "rate_range": f"{self.rate_range_low_pct:.1f}%–{self.rate_range_high_pct:.1f}%",
            "all_others_rate_pct": round(self.all_others_rate_pct, 2),
            "effective_date": self.effective_date,
            "status": self.status,
            "federal_register_citation": self.federal_register_citation,
            "notes": self.notes,
        }


@dataclass
class ADCVDExposure:
    hts_code: str
    origin: str
    matching_orders: list[ADCVDOrder]
    estimated_additional_pct: float
    risk_level: str

    def as_dict(self) -> dict:
        return {
            "hts_code": self.hts_code,
            "origin": self.origin,
            "matching_orders_count": len(self.matching_orders),
            "matching_orders": [o.as_dict() for o in self.matching_orders],
            "estimated_additional_pct": round(self.estimated_additional_pct, 2),
            "risk_level": self.risk_level,
            "warning": (
                f"AD/CVD duties could add +{self.estimated_additional_pct:.1f}% "
                f"on top of all other duties. This is the 'all others' rate — "
                f"your actual rate depends on Commerce Dept. administrative review. "
                f"Consult a trade attorney or customs broker."
            ) if self.matching_orders else None,
        }


# ── Active AD/CVD orders against China ────────────────────────────────────────

_CHINA = "CN"

_ADCVD_ORDERS: list[ADCVDOrder] = [
    # ── Aluminum ──────────────────────────────────────────────────────────────
    ADCVDOrder(
        case_number="A-570-967 / C-570-968",
        order_type="AD+CVD",
        product_description="Aluminum Extrusions",
        product_description_zh="铝型材",
        country=_CHINA,
        hts_prefixes=["7604", "7608", "7610", "7615", "7616"],
        rate_range_low_pct=32.79,
        rate_range_high_pct=374.15,
        all_others_rate_pct=32.79,
        effective_date="2011-05-26",
        status="active",
        federal_register_citation="76 FR 30650",
        notes=[
            "Covers profiles, bars, pipes, tubes, and fabricated shapes",
            "CVD rate for 'all others' is up to 374.15% for some producers",
        ],
    ),
    ADCVDOrder(
        case_number="A-570-053",
        order_type="AD",
        product_description="Common Alloy Aluminum Sheet",
        product_description_zh="普通合金铝板",
        country=_CHINA,
        hts_prefixes=["7606"],
        rate_range_low_pct=49.43,
        rate_range_high_pct=176.2,
        all_others_rate_pct=59.31,
        effective_date="2021-04-08",
        status="active",
        federal_register_citation="86 FR 18195",
    ),
    ADCVDOrder(
        case_number="A-570-116 / C-570-117",
        order_type="AD+CVD",
        product_description="Aluminum Foil",
        product_description_zh="铝箔",
        country=_CHINA,
        hts_prefixes=["7607"],
        rate_range_low_pct=19.34,
        rate_range_high_pct=106.09,
        all_others_rate_pct=48.64,
        effective_date="2018-03-15",
        status="active",
        federal_register_citation="83 FR 11647",
    ),
    ADCVDOrder(
        case_number="A-570-075 / C-570-076",
        order_type="AD+CVD",
        product_description="Aluminum Wire and Cable",
        product_description_zh="铝线缆",
        country=_CHINA,
        hts_prefixes=["7605", "7614", "8544"],
        rate_range_low_pct=58.51,
        rate_range_high_pct=188.56,
        all_others_rate_pct=58.51,
        effective_date="2019-11-01",
        status="active",
        federal_register_citation="84 FR 58460",
    ),

    # ── Steel ─────────────────────────────────────────────────────────────────
    ADCVDOrder(
        case_number="A-570-504",
        order_type="AD",
        product_description="Steel Wire Rope",
        product_description_zh="钢丝绳",
        country=_CHINA,
        hts_prefixes=["7312"],
        rate_range_low_pct=12.56,
        rate_range_high_pct=44.99,
        all_others_rate_pct=44.99,
        effective_date="1992-03-25",
        status="active",
        federal_register_citation="57 FR 10012",
    ),
    ADCVDOrder(
        case_number="A-570-900 / C-570-901",
        order_type="AD+CVD",
        product_description="Steel Nails",
        product_description_zh="钢钉",
        country=_CHINA,
        hts_prefixes=["7317"],
        rate_range_low_pct=21.24,
        rate_range_high_pct=118.04,
        all_others_rate_pct=118.04,
        effective_date="2008-07-14",
        status="active",
        federal_register_citation="73 FR 40303",
    ),
    ADCVDOrder(
        case_number="A-570-894 / C-570-895",
        order_type="AD+CVD",
        product_description="Circular Welded Steel Pipe",
        product_description_zh="焊接圆钢管",
        country=_CHINA,
        hts_prefixes=["7306"],
        rate_range_low_pct=29.57,
        rate_range_high_pct=85.55,
        all_others_rate_pct=85.55,
        effective_date="2008-06-17",
        status="active",
        federal_register_citation="73 FR 34170",
    ),

    # ── Kitchen / Hardware ────────────────────────────────────────────────────
    ADCVDOrder(
        case_number="A-570-998 / C-570-999",
        order_type="AD+CVD",
        product_description="Steel Racks / Kitchen Shelving",
        product_description_zh="钢制货架/厨房置物架",
        country=_CHINA,
        hts_prefixes=["7321", "7323", "7326"],
        rate_range_low_pct=50.09,
        rate_range_high_pct=119.63,
        all_others_rate_pct=119.63,
        effective_date="2012-05-03",
        status="active",
        federal_register_citation="77 FR 26240",
        notes=["Includes wire shelving, bakers racks, utility carts"],
    ),
    ADCVDOrder(
        case_number="A-570-890",
        order_type="AD",
        product_description="Steel Wire Garment Hangers",
        product_description_zh="钢丝衣架",
        country=_CHINA,
        hts_prefixes=["7326"],
        rate_range_low_pct=15.39,
        rate_range_high_pct=187.25,
        all_others_rate_pct=187.25,
        effective_date="2008-01-30",
        status="active",
        federal_register_citation="73 FR 5478",
    ),

    # ── Other ─────────────────────────────────────────────────────────────────
    ADCVDOrder(
        case_number="A-570-979 / C-570-980",
        order_type="AD+CVD",
        product_description="Crystalline Silicon Photovoltaic Cells",
        product_description_zh="晶硅光伏电池",
        country=_CHINA,
        hts_prefixes=["8541"],
        rate_range_low_pct=15.97,
        rate_range_high_pct=238.95,
        all_others_rate_pct=238.95,
        effective_date="2012-12-07",
        status="active",
        federal_register_citation="77 FR 73018",
    ),
    ADCVDOrder(
        case_number="A-570-601",
        order_type="AD",
        product_description="Tapered Roller Bearings",
        product_description_zh="圆锥滚子轴承",
        country=_CHINA,
        hts_prefixes=["8482"],
        rate_range_low_pct=2.71,
        rate_range_high_pct=66.00,
        all_others_rate_pct=66.00,
        effective_date="1987-06-19",
        status="active",
        federal_register_citation="52 FR 23321",
    ),
    ADCVDOrder(
        case_number="A-570-847",
        order_type="AD",
        product_description="Wooden Bedroom Furniture",
        product_description_zh="木质卧室家具",
        country=_CHINA,
        hts_prefixes=["9403"],
        rate_range_low_pct=0.0,
        rate_range_high_pct=198.08,
        all_others_rate_pct=198.08,
        effective_date="2005-01-04",
        status="active",
        federal_register_citation="70 FR 329",
    ),
    ADCVDOrder(
        case_number="A-570-082 / C-570-083",
        order_type="AD+CVD",
        product_description="Quartz Surface Products",
        product_description_zh="石英石面板",
        country=_CHINA,
        hts_prefixes=["6810"],
        rate_range_low_pct=45.32,
        rate_range_high_pct=294.57,
        all_others_rate_pct=294.57,
        effective_date="2019-04-18",
        status="active",
        federal_register_citation="84 FR 16543",
    ),
    ADCVDOrder(
        case_number="A-570-831",
        order_type="AD",
        product_description="Honey",
        product_description_zh="蜂蜜",
        country=_CHINA,
        hts_prefixes=["0409"],
        rate_range_low_pct=25.88,
        rate_range_high_pct=183.80,
        all_others_rate_pct=183.80,
        effective_date="2001-12-10",
        status="active",
        federal_register_citation="66 FR 63670",
    ),
    ADCVDOrder(
        case_number="A-570-909",
        order_type="AD",
        product_description="Laminated Woven Sacks",
        product_description_zh="复合编织袋",
        country=_CHINA,
        hts_prefixes=["6305"],
        rate_range_low_pct=64.28,
        rate_range_high_pct=91.73,
        all_others_rate_pct=91.73,
        effective_date="2008-07-11",
        status="active",
        federal_register_citation="73 FR 40117",
    ),
    ADCVDOrder(
        case_number="A-570-075",
        order_type="AD",
        product_description="Polyester Textured Yarn",
        product_description_zh="涤纶变形纱",
        country=_CHINA,
        hts_prefixes=["5402"],
        rate_range_low_pct=32.85,
        rate_range_high_pct=56.11,
        all_others_rate_pct=56.11,
        effective_date="2020-03-19",
        status="active",
        federal_register_citation="85 FR 15769",
    ),
]

# ── China alias keys (reuse from tariff_overlay) ─────────────────────────────

_CHINA_KEYS = {"CN", "CHN", "CHINA", "中国", "PRC"}


# ── Lookup functions ──────────────────────────────────────────────────────────

def _risk_level(pct: float) -> str:
    if pct == 0:
        return "none"
    if pct < 20:
        return "low"
    if pct < 50:
        return "moderate"
    if pct < 150:
        return "high"
    return "extreme"


def lookup_adcvd(hts_code: str, origin: str = "CN") -> ADCVDExposure:
    """Check if an HTS code falls under any active AD/CVD orders."""
    origin_key = origin.strip().upper()
    norm = normalize_hts_code(hts_code) or ""

    matches: list[ADCVDOrder] = []

    if origin_key in _CHINA_KEYS:
        for order in _ADCVD_ORDERS:
            if order.status != "active":
                continue
            for prefix in order.hts_prefixes:
                if norm.startswith(prefix):
                    matches.append(order)
                    break

    best_rate = max((o.all_others_rate_pct for o in matches), default=0.0)

    return ADCVDExposure(
        hts_code=hts_code,
        origin=origin,
        matching_orders=matches,
        estimated_additional_pct=best_rate,
        risk_level=_risk_level(best_rate),
    )


def get_all_orders(origin: str = "CN", status: str = "active") -> list[ADCVDOrder]:
    """Return all AD/CVD orders for a given country."""
    origin_key = origin.strip().upper()
    if origin_key not in _CHINA_KEYS:
        return []
    return [o for o in _ADCVD_ORDERS if o.status == status]


def get_orders_by_chapter(chapter: str, origin: str = "CN") -> list[ADCVDOrder]:
    """Return AD/CVD orders matching a specific HTS chapter."""
    origin_key = origin.strip().upper()
    if origin_key not in _CHINA_KEYS:
        return []
    return [
        o for o in _ADCVD_ORDERS
        if o.status == "active"
        and any(p.startswith(chapter) for p in o.hts_prefixes)
    ]
