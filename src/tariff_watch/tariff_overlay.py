"""
Country-of-origin tariff overlay — focused on China-origin exports to the US.

Computes confirmed, currently-in-force additional duties stacked on top of
the USITC base MFN rate:

  Section 232   – steel (+25 pp, chapters 72–73) and aluminum (+10 pp, chapter 76)
                  Applied to all origins; USMCA partners CA/MX are exempt.

  Section 301   – China-specific trade-war duties (Trade Act of 1974, s. 301):
                    Chapters 61–64 (apparel/footwear) → List 4B  +7.5 pp
                    All other chapters                → Lists 1–4A +25 pp

STRUCK-DOWN / REMOVED (not included):
  IEEPA tariffs – The Supreme Court ruled on 2026-02-20 (Learning Resources v. Trump)
                  that tariffs imposed under IEEPA are unconstitutional.  CBP stopped
                  collecting all IEEPA duties as of 2026-02-24.  This includes:
                    • The fentanyl-related 10% tariff on China (EO 14195, later reduced
                      to 10% in the Nov 2025 US–China trade deal)
                    • All "reciprocal" country tariffs

ADVISORY (confirmed in effect, excluded from calculation per operator preference):
  Section 122 – Trump signed a temporary 10% global surcharge on 2026-02-20 under
                Section 122 of the Trade Act of 1974 (HTS 9903.03.01).  CBP began
                collecting this on 2026-02-24.  It expires 2026-07-24 (150-day limit)
                unless Congress extends it.  Trump has threatened to raise it to 15%;
                no official proclamation to that effect has been issued yet.
                NOT included in effective_total_pct — verify with CBP before shipment.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .antidumping import lookup_adcvd
from .trade_compliance import get_compliance_flags


# ── Section 232 ───────────────────────────────────────────────────────────────

_S232_STEEL_PCT = 25.0
_S232_STEEL_CHAPTERS = {"72", "73"}
_S232_ALUMINUM_PCT = 10.0
_S232_ALUMINUM_CHAPTER = "76"

_USMCA_COUNTRIES = {"CA", "MX", "CAN", "MEX", "CANADA", "MEXICO"}

# ── Section 301 (China only) ──────────────────────────────────────────────────

# List 4B: apparel, footwear, certain textile articles (HTS ch. 61–64)
_S301_LIST4B_PCT = 7.5
_S301_LIST4B_CHAPTERS = {"61", "62", "63", "64"}

# Lists 1–4A: all other goods
_S301_DEFAULT_PCT = 25.0

# ── Section 122 advisory text ─────────────────────────────────────────────────

_S122_ADVISORY = (
    "Section 122 (HTS 9903.03.01): temporary 10% global surcharge in effect from "
    "2026-02-24 to 2026-07-24 (150-day limit) — applies to ALL origins including China. "
    "CBP is actively collecting this duty. NOT included in effective_total_pct. "
    "Trump has signalled a possible increase to 15%; no proclamation issued yet. "
    "Verify with your customs broker before shipment."
)

# ── Country display names ─────────────────────────────────────────────────────

_CHINA_KEYS = {"CN", "CHN", "CHINA", "中国", "PRC"}

_COUNTRY_DISPLAY: dict[str, str] = {
    "CN": "China", "CHN": "China", "CHINA": "China", "中国": "China", "PRC": "China",
    "US": "USA", "USA": "USA",
    "CA": "Canada", "CAN": "Canada", "CANADA": "Canada",
    "MX": "Mexico", "MEX": "Mexico", "MEXICO": "Mexico",
    "VN": "Vietnam", "VNM": "Vietnam", "VIETNAM": "Vietnam",
    "IN": "India", "IND": "India", "INDIA": "India",
    "BD": "Bangladesh", "BGD": "Bangladesh",
    "DE": "Germany", "JP": "Japan", "KR": "South Korea",
    "TH": "Thailand", "ID": "Indonesia", "MY": "Malaysia",
    "PH": "Philippines", "PK": "Pakistan",
}


def _display(origin: str) -> str:
    return _COUNTRY_DISPLAY.get(origin.strip().upper(), origin)


# ── Core data class ───────────────────────────────────────────────────────────

@dataclass
class TariffOverlay:
    origin: str
    hts_code: str
    base_rate_pct: float
    section_232_pct: float = 0.0
    section_301_pct: float = 0.0
    adcvd_estimated_pct: float = 0.0
    adcvd_risk_level: str = "none"
    adcvd_orders_count: int = 0
    compliance_flags: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    advisory: list[str] = field(default_factory=list)

    @property
    def total_additional_pct(self) -> float:
        return self.section_232_pct + self.section_301_pct

    @property
    def effective_total_pct(self) -> float:
        return self.base_rate_pct + self.total_additional_pct

    @property
    def worst_case_total_pct(self) -> float:
        """Effective total including AD/CVD (worst-case scenario)."""
        return self.effective_total_pct + self.adcvd_estimated_pct

    def as_dict(self) -> dict:
        result = {
            "origin": self.origin,
            "origin_display": _display(self.origin),
            "hts_code": self.hts_code,
            "base_mfn_pct": round(self.base_rate_pct, 2),
            "section_232_pct": round(self.section_232_pct, 2),
            "section_301_pct": round(self.section_301_pct, 2),
            "total_additional_pct": round(self.total_additional_pct, 2),
            "effective_total_pct": round(self.effective_total_pct, 2),
            "notes": self.notes,
            "advisory": self.advisory,
        }
        # AD/CVD section (only if there are matching orders)
        if self.adcvd_orders_count > 0:
            result["adcvd"] = {
                "estimated_additional_pct": round(self.adcvd_estimated_pct, 2),
                "risk_level": self.adcvd_risk_level,
                "matching_orders_count": self.adcvd_orders_count,
                "worst_case_total_pct": round(self.worst_case_total_pct, 2),
                "warning": (
                    f"AD/CVD duties could add +{self.adcvd_estimated_pct:.1f}% "
                    f"on top of all other duties (worst case: {self.worst_case_total_pct:.1f}%). "
                    f"Actual rate is company-specific — consult a trade attorney."
                ),
            }
        # Compliance flags
        if self.compliance_flags:
            result["compliance_flags"] = self.compliance_flags
        return result


# ── Main entry point ──────────────────────────────────────────────────────────

def compute_overlay(
    hts_code: str,
    origin: str,
    base_rate_pct: float = 0.0,
) -> TariffOverlay:
    """
    Compute the confirmed, currently-in-force tariff stack for a product.

    ``effective_total_pct`` = MFN base + Section 232 + Section 301.

    The Section 122 temporary 10% global surcharge (in effect 2026-02-24) is
    NOT included in the numeric total — it appears in ``advisory`` instead.

    Args:
        hts_code:      Normalized (digits-only) HTS code, e.g. ``"7604101000"``.
        origin:        Country of origin — ISO-2, ISO-3, or common name.
        base_rate_pct: MFN base rate as a percentage (e.g. ``5.0`` for 5 %).

    Returns:
        :class:`TariffOverlay` with per-layer breakdown.
    """
    origin_key = origin.strip().upper()
    chapter = hts_code[:2] if len(hts_code) >= 2 else hts_code

    overlay = TariffOverlay(
        origin=origin,
        hts_code=hts_code,
        base_rate_pct=base_rate_pct,
    )

    is_usmca = origin_key in _USMCA_COUNTRIES

    # ── Section 232 ───────────────────────────────────────────────────────────
    if chapter in _S232_STEEL_CHAPTERS:
        if is_usmca:
            overlay.notes.append(
                f"Section 232 steel tariff waived — {_display(origin)} is a USMCA partner"
            )
        else:
            overlay.section_232_pct = _S232_STEEL_PCT
            overlay.notes.append(
                f"Section 232 (Trade Expansion Act s. 232) — steel: +{_S232_STEEL_PCT:.0f}%"
            )

    elif chapter == _S232_ALUMINUM_CHAPTER:
        if is_usmca:
            overlay.notes.append(
                f"Section 232 aluminum tariff waived — {_display(origin)} is a USMCA partner"
            )
        else:
            overlay.section_232_pct = _S232_ALUMINUM_PCT
            overlay.notes.append(
                f"Section 232 (Trade Expansion Act s. 232) — aluminum: +{_S232_ALUMINUM_PCT:.0f}%"
            )

    # ── Section 301 (China only) ──────────────────────────────────────────────
    if origin_key in _CHINA_KEYS:
        if chapter in _S301_LIST4B_CHAPTERS:
            overlay.section_301_pct = _S301_LIST4B_PCT
            overlay.notes.append(
                f"Section 301 (Trade Act of 1974) List 4B — apparel/footwear ch. {chapter}: "
                f"+{_S301_LIST4B_PCT:.1f}%"
            )
        else:
            overlay.section_301_pct = _S301_DEFAULT_PCT
            overlay.notes.append(
                f"Section 301 (Trade Act of 1974) Lists 1–4A: +{_S301_DEFAULT_PCT:.0f}%"
            )

        overlay.notes.append(
            "IEEPA tariffs (fentanyl/reciprocal) struck down by SCOTUS on 2026-02-20; "
            "CBP stopped collection 2026-02-24 — NOT applied here."
        )

    if not overlay.notes:
        overlay.notes.append(
            f"No additional Section 232 or 301 duties for origin: {_display(origin)}"
        )

    # ── AD/CVD lookup ────────────────────────────────────────────────────────
    adcvd = lookup_adcvd(hts_code, origin)
    if adcvd.matching_orders:
        overlay.adcvd_estimated_pct = adcvd.estimated_additional_pct
        overlay.adcvd_risk_level = adcvd.risk_level
        overlay.adcvd_orders_count = len(adcvd.matching_orders)
        overlay.notes.append(
            f"⚠ AD/CVD: {len(adcvd.matching_orders)} active order(s) — "
            f"'all others' rate up to +{adcvd.estimated_additional_pct:.1f}%. "
            f"Company-specific rate may differ."
        )

    # ── Compliance flags ─────────────────────────────────────────────────────
    overlay.compliance_flags = get_compliance_flags(hts_code)
    if overlay.compliance_flags:
        overlay.notes.append(
            f"Regulatory agencies: {', '.join(overlay.compliance_flags)}"
        )

    # ── Section 122 advisory (all origins) ───────────────────────────────────
    overlay.advisory.append(_S122_ADVISORY)

    return overlay
