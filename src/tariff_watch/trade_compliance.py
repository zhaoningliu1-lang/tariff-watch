"""
Trade compliance engine — customs entry, product safety, and UFLPA risk.

Covers the non-tariff concerns that Chinese exporters face when shipping to
the US:

  1. **Product safety / regulatory requirements** — which agencies (CPSC, FDA,
     FCC, EPA, DOT …) regulate a product, and what certifications or filings
     are needed, mapped by HTS chapter.

  2. **Customs entry requirements** — formal vs. informal entry, bond costs,
     broker fees, ISF (10+2) filing, and exam risk.

  3. **UFLPA (Uyghur Forced Labor Prevention Act)** risk assessment — flags
     products with high CBP detention risk based on commodity type and origin
     region.

  4. **Country-of-origin marking** — 19 USC §1304 requirements.

Usage::

    from .trade_compliance import get_compliance_report, get_entry_requirements

    report = get_compliance_report("9503000013", origin="CN")
    print(report.as_dict())

    entry = get_entry_requirements(origin="CN", estimated_value_usd=10_000)
    print(entry.as_dict())
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .normalize import normalize_hts_code


# ── Product safety / regulatory mapping ──────────────────────────────────────

@dataclass
class ComplianceRequirement:
    agency: str               # "CPSC", "FDA", "FCC", etc.
    agency_zh: str
    requirement: str           # short English description
    requirement_zh: str
    applies_to_chapters: list[str]
    mandatory: bool = True
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "agency": self.agency,
            "agency_zh": self.agency_zh,
            "requirement": self.requirement,
            "requirement_zh": self.requirement_zh,
            "mandatory": self.mandatory,
            "notes": self.notes,
        }


_COMPLIANCE_MAP: list[ComplianceRequirement] = [
    # ── Toys & children's products ───────────────────────────────────────────
    ComplianceRequirement(
        agency="CPSC",
        agency_zh="美国消费品安全委员会",
        requirement="Children's Product Certificate (CPC) + ASTM F963 testing",
        requirement_zh="儿童产品证书 (CPC) + ASTM F963 玩具安全测试",
        applies_to_chapters=["95"],
        notes=[
            "Third-party testing by CPSC-accepted lab required",
            "Lead content, phthalate, and small parts testing mandatory",
            "General Certificate of Conformity (GCC) for non-children's toys",
        ],
    ),
    ComplianceRequirement(
        agency="CPSC",
        agency_zh="美国消费品安全委员会",
        requirement="Flammability standards (16 CFR 1610/1611) for textiles",
        requirement_zh="纺织品易燃性标准 (16 CFR 1610/1611)",
        applies_to_chapters=["61", "62", "63"],
        notes=[
            "Applies to clothing, curtains, upholstery fabric",
            "Children's sleepwear has additional requirements (16 CFR 1615/1616)",
        ],
    ),

    # ── Electronics ──────────────────────────────────────────────────────────
    ComplianceRequirement(
        agency="FCC",
        agency_zh="美国联邦通信委员会",
        requirement="FCC Part 15 — Unintentional/intentional radiator testing",
        requirement_zh="FCC Part 15 — 非故意/故意辐射体测试认证",
        applies_to_chapters=["84", "85"],
        notes=[
            "All electronic devices that emit RF need FCC authorization",
            "Three paths: Certification, SDoC (Supplier's Declaration), or Verification",
            "FCC ID label required on device",
        ],
    ),
    ComplianceRequirement(
        agency="UL / NRTL",
        agency_zh="UL / 国家认可测试实验室",
        requirement="UL listing for electrical products (voluntary but expected by retailers)",
        requirement_zh="电气产品 UL 认证（自愿但零售商普遍要求）",
        applies_to_chapters=["84", "85"],
        mandatory=False,
        notes=[
            "Amazon requires UL certification for many electrical categories",
            "Not legally mandatory but practically required for US market",
        ],
    ),

    # ── Food & beverages ─────────────────────────────────────────────────────
    ComplianceRequirement(
        agency="FDA",
        agency_zh="美国食品药品监督管理局",
        requirement="FDA Prior Notice + Food Facility Registration + FSVP",
        requirement_zh="FDA 预先通知 + 食品设施注册 + 外国供应商验证计划",
        applies_to_chapters=["04", "07", "08", "09", "16", "17", "18", "19", "20", "21"],
        notes=[
            "Prior Notice must be filed before arrival at US port",
            "Foreign Supplier Verification Program (FSVP) for importer of record",
            "Acidified and low-acid canned foods need separate registration",
        ],
    ),

    # ── Cosmetics ────────────────────────────────────────────────────────────
    ComplianceRequirement(
        agency="FDA",
        agency_zh="美国食品药品监督管理局",
        requirement="MoCRA facility registration + product listing + adverse event reporting",
        requirement_zh="MoCRA 设施注册 + 产品备案 + 不良事件报告",
        applies_to_chapters=["33"],
        notes=[
            "Modernization of Cosmetics Regulation Act (MoCRA) effective 2024",
            "Facility registration and product listing now mandatory",
            "Safety substantiation required",
        ],
    ),

    # ── Pharmaceuticals / supplements ────────────────────────────────────────
    ComplianceRequirement(
        agency="FDA",
        agency_zh="美国食品药品监督管理局",
        requirement="Drug/supplement registration + NDC labeling + cGMP",
        requirement_zh="药品/保健品注册 + NDC 标签 + 现行良好生产规范",
        applies_to_chapters=["30"],
        notes=[
            "OTC drugs need NDC number",
            "Dietary supplements need structure/function claims review",
        ],
    ),

    # ── Footwear ─────────────────────────────────────────────────────────────
    ComplianceRequirement(
        agency="FTC",
        agency_zh="美国联邦贸易委员会",
        requirement="Footwear labeling (material composition)",
        requirement_zh="鞋类材料成分标签",
        applies_to_chapters=["64"],
        notes=["Upper, outsole, and lining material must be disclosed"],
    ),

    # ── Automotive parts ─────────────────────────────────────────────────────
    ComplianceRequirement(
        agency="DOT / NHTSA",
        agency_zh="美国交通部 / 国家公路交通安全管理局",
        requirement="FMVSS compliance for motor vehicle equipment",
        requirement_zh="联邦机动车安全标准 (FMVSS) 合规",
        applies_to_chapters=["87"],
        notes=[
            "Tires, lighting, braking components need DOT marking",
            "Importer must file HS-7 declaration",
        ],
    ),

    # ── Chemicals ────────────────────────────────────────────────────────────
    ComplianceRequirement(
        agency="EPA / TSCA",
        agency_zh="美国环保署 / 有毒物质控制法",
        requirement="TSCA certification — chemical substance compliance",
        requirement_zh="TSCA 认证 — 化学物质合规声明",
        applies_to_chapters=["28", "29", "38"],
        notes=[
            "All chemical imports must certify TSCA compliance at entry",
            "EPA Form 3520-21 required",
            "Positive TSCA certification for listed substances",
        ],
    ),

    # ── Solar panels / batteries ─────────────────────────────────────────────
    ComplianceRequirement(
        agency="DOE",
        agency_zh="美国能源部",
        requirement="Energy efficiency standards + DOE test procedures",
        requirement_zh="能效标准 + DOE 测试规程",
        applies_to_chapters=["85"],
        mandatory=False,
        notes=[
            "Certain appliances, motors, lighting products",
            "Energy Guide labels for covered products",
        ],
    ),

    # ── Furniture ────────────────────────────────────────────────────────────
    ComplianceRequirement(
        agency="CPSC / EPA",
        agency_zh="消费品安全委员会 / 环保署",
        requirement="CPSC furniture tip-over standards + EPA TSCA Title VI formaldehyde",
        requirement_zh="家具防倾倒标准 + EPA 甲醛排放标准 (TSCA Title VI)",
        applies_to_chapters=["94"],
        notes=[
            "Composite wood products need TSCA Title VI formaldehyde certification",
            "Clothing storage furniture needs ASTM F2057 tip-over stability",
        ],
    ),
]


# ── UFLPA risk assessment ────────────────────────────────────────────────────

@dataclass
class UFLPARisk:
    risk_level: str           # "none", "low", "medium", "high", "extreme"
    risk_level_zh: str
    commodity_flag: str       # what triggered the flag
    commodity_flag_zh: str
    cbp_action: str           # expected CBP behavior
    cbp_action_zh: str
    mitigation: list[str]     # what the exporter can do

    def as_dict(self) -> dict:
        return {
            "risk_level": self.risk_level,
            "risk_level_zh": self.risk_level_zh,
            "commodity_flag": self.commodity_flag,
            "commodity_flag_zh": self.commodity_flag_zh,
            "cbp_action": self.cbp_action,
            "cbp_action_zh": self.cbp_action_zh,
            "mitigation": self.mitigation,
        }


def _assess_uflpa(chapter: str, origin: str) -> UFLPARisk:
    """Assess UFLPA detention risk based on HTS chapter and origin."""
    origin_key = origin.strip().upper()

    # Only applies to China (PRC)
    if origin_key not in {"CN", "CHN", "CHINA", "中国", "PRC"}:
        return UFLPARisk(
            risk_level="none",
            risk_level_zh="无风险",
            commodity_flag="Non-China origin",
            commodity_flag_zh="非中国产地",
            cbp_action="UFLPA does not apply",
            cbp_action_zh="UFLPA 不适用",
            mitigation=[],
        )

    # Cotton & cotton textiles — extreme risk
    if chapter in {"52", "61", "62", "63"}:
        return UFLPARisk(
            risk_level="extreme",
            risk_level_zh="极高风险",
            commodity_flag="Cotton / cotton textile products",
            commodity_flag_zh="棉花/棉纺织品",
            cbp_action="High probability of WRO detention; CBP actively targeting cotton from Xinjiang",
            cbp_action_zh="极大概率被扣留（WRO）；CBP 正在重点排查新疆棉花",
            mitigation=[
                "Provide full supply chain traceability documentation",
                "Use isotope testing to prove non-Xinjiang origin of cotton",
                "Obtain third-party audit of ginning, spinning, and weaving facilities",
                "Consider sourcing cotton from non-China origins",
            ],
        )

    # Polysilicon / solar cells — extreme risk
    if chapter in {"28", "85"} and chapter == "85":
        return UFLPARisk(
            risk_level="extreme",
            risk_level_zh="极高风险",
            commodity_flag="Solar cells / polysilicon products",
            commodity_flag_zh="光伏电池/多晶硅产品",
            cbp_action="High probability of WRO detention; CBP actively targeting polysilicon from Xinjiang",
            cbp_action_zh="极大概率被扣留；CBP 正在重点排查新疆多晶硅",
            mitigation=[
                "Provide polysilicon supply chain mapping to ingot level",
                "Third-party audit of polysilicon sourcing (non-XUAR)",
                "Consider using non-China polysilicon wafers",
            ],
        )

    # Tomato products — high risk
    if chapter in {"20"}:
        return UFLPARisk(
            risk_level="high",
            risk_level_zh="高风险",
            commodity_flag="Tomato products",
            commodity_flag_zh="番茄制品",
            cbp_action="WRO in effect for Xinjiang tomato products; detention likely",
            cbp_action_zh="新疆番茄制品 WRO 生效中；可能被扣留",
            mitigation=[
                "Provide evidence of non-Xinjiang sourcing",
                "Third-party supply chain audit",
            ],
        )

    # Aluminum and silica — medium risk
    if chapter in {"76"}:
        return UFLPARisk(
            risk_level="medium",
            risk_level_zh="中等风险",
            commodity_flag="Aluminum products",
            commodity_flag_zh="铝制品",
            cbp_action="CBP has flagged some aluminum from XUAR; not systematic detention",
            cbp_action_zh="CBP 已标记部分来自新疆的铝制品；非系统性扣留",
            mitigation=[
                "Document smelter location and bauxite source",
                "Prepare supply chain map if CBP requests",
            ],
        )

    # PVC, chemicals — medium risk
    if chapter in {"39"}:
        return UFLPARisk(
            risk_level="medium",
            risk_level_zh="中等风险",
            commodity_flag="Plastics / PVC products",
            commodity_flag_zh="塑料/PVC 制品",
            cbp_action="Some PVC supply chains linked to XUAR; CBP may request documentation",
            cbp_action_zh="部分 PVC 供应链与新疆有关联；CBP 可能要求提供文件",
            mitigation=[
                "Prepare documentation of PVC resin sourcing",
                "Third-party audit if supply chain touches Xinjiang",
            ],
        )

    # Human hair products — high risk
    if chapter in {"67"}:
        return UFLPARisk(
            risk_level="high",
            risk_level_zh="高风险",
            commodity_flag="Human hair products",
            commodity_flag_zh="人发制品",
            cbp_action="WRO issued against specific Chinese hair product manufacturers",
            cbp_action_zh="CBP 已对特定中国人发制品制造商发布 WRO",
            mitigation=[
                "Verify manufacturer is not on WRO entity list",
                "Document sourcing of raw hair material",
            ],
        )

    # Default — low risk
    return UFLPARisk(
        risk_level="low",
        risk_level_zh="低风险",
        commodity_flag="General merchandise",
        commodity_flag_zh="一般商品",
        cbp_action="No specific UFLPA targeting; standard entry processing",
        cbp_action_zh="无特定 UFLPA 排查；标准入关流程",
        mitigation=[
            "Maintain basic supply chain records",
            "Be prepared to respond to CBP inquiries",
        ],
    )


# ── Customs entry requirements ───────────────────────────────────────────────

_INFORMAL_ENTRY_THRESHOLD_USD = 2500.0

# Typical costs (representative — actual varies by broker)
_BROKER_FEE_PER_ENTRY = 150.0
_ISF_FILING_FEE = 35.0
_SINGLE_ENTRY_BOND_COST = 12.0           # per-entry for value < $10k
_CONTINUOUS_BOND_ANNUAL = 500.0          # annual, covers unlimited entries
_EXAM_PROBABILITY_PCT = 3.0             # ~3% of entries get examined
_EXAM_COST_USD = 500.0                  # avg cost of a CBP exam (fees + delays)
_MPF_RATE_PCT = 0.3464                  # Merchandise Processing Fee
_MPF_MIN_USD = 31.67
_MPF_MAX_USD = 614.35
_HMF_RATE_PCT = 0.125                  # Harbor Maintenance Fee (ocean only)


@dataclass
class EntryRequirements:
    entry_type: str           # "informal" or "formal"
    entry_type_zh: str
    estimated_value_usd: float
    origin: str

    broker_fee_usd: float
    isf_fee_usd: float
    bond_cost_usd: float
    mpf_usd: float
    hmf_usd: float
    exam_risk_cost_usd: float
    total_entry_costs_usd: float

    notes: list[str] = field(default_factory=list)

    def per_unit(self, units: int = 100) -> dict:
        """Amortize entry costs across a shipment."""
        if units <= 0:
            units = 1
        return {
            "units_in_shipment": units,
            "broker_per_unit": round(self.broker_fee_usd / units, 2),
            "isf_per_unit": round(self.isf_fee_usd / units, 2),
            "bond_per_unit": round(self.bond_cost_usd / units, 2),
            "mpf_per_unit": round(self.mpf_usd / units, 2),
            "hmf_per_unit": round(self.hmf_usd / units, 2),
            "exam_risk_per_unit": round(self.exam_risk_cost_usd / units, 2),
            "total_per_unit": round(self.total_entry_costs_usd / units, 2),
        }

    def as_dict(self) -> dict:
        return {
            "entry_type": self.entry_type,
            "entry_type_zh": self.entry_type_zh,
            "estimated_value_usd": self.estimated_value_usd,
            "origin": self.origin,
            "costs": {
                "broker_fee_usd": self.broker_fee_usd,
                "isf_fee_usd": self.isf_fee_usd,
                "bond_cost_usd": self.bond_cost_usd,
                "mpf_usd": round(self.mpf_usd, 2),
                "hmf_usd": round(self.hmf_usd, 2),
                "exam_risk_cost_usd": round(self.exam_risk_cost_usd, 2),
                "total_entry_costs_usd": round(self.total_entry_costs_usd, 2),
            },
            "per_unit_100": self.per_unit(100),
            "notes": self.notes,
        }


def get_entry_requirements(
    origin: str = "CN",
    estimated_value_usd: float = 5000.0,
) -> EntryRequirements:
    """Calculate customs entry costs for a shipment."""
    value = max(estimated_value_usd, 0.0)
    is_formal = value > _INFORMAL_ENTRY_THRESHOLD_USD

    broker_fee = _BROKER_FEE_PER_ENTRY if is_formal else 50.0
    isf_fee = _ISF_FILING_FEE
    bond_cost = _SINGLE_ENTRY_BOND_COST if value < 10_000 else _SINGLE_ENTRY_BOND_COST * 2

    # Merchandise Processing Fee (formal entries only)
    mpf = 0.0
    if is_formal:
        mpf = value * (_MPF_RATE_PCT / 100.0)
        mpf = max(_MPF_MIN_USD, min(mpf, _MPF_MAX_USD))

    # Harbor Maintenance Fee (ocean shipments)
    hmf = value * (_HMF_RATE_PCT / 100.0)

    exam_risk = (_EXAM_PROBABILITY_PCT / 100.0) * _EXAM_COST_USD

    total = broker_fee + isf_fee + bond_cost + mpf + hmf + exam_risk

    notes = []
    if is_formal:
        notes.append(
            f"Formal entry required (value ${value:,.0f} > ${_INFORMAL_ENTRY_THRESHOLD_USD:,.0f} threshold)"
        )
        notes.append("Customs broker recommended for formal entries")
    else:
        notes.append(
            f"Informal entry eligible (value ${value:,.0f} ≤ ${_INFORMAL_ENTRY_THRESHOLD_USD:,.0f})"
        )
        notes.append("Self-filing possible but broker still recommended for first-time importers")

    notes.append(
        f"Exam risk: ~{_EXAM_PROBABILITY_PCT:.0f}% chance of CBP examination "
        f"(avg cost ${_EXAM_COST_USD:,.0f} including delays)"
    )

    origin_key = origin.strip().upper()
    if origin_key in {"CN", "CHN", "CHINA", "中国", "PRC"}:
        notes.append(
            "China-origin shipments face higher CBP scrutiny; "
            "ensure all documentation is complete before arrival"
        )

    return EntryRequirements(
        entry_type="formal" if is_formal else "informal",
        entry_type_zh="正式报关" if is_formal else "非正式报关",
        estimated_value_usd=value,
        origin=origin,
        broker_fee_usd=broker_fee,
        isf_fee_usd=isf_fee,
        bond_cost_usd=bond_cost,
        mpf_usd=mpf,
        hmf_usd=hmf,
        exam_risk_cost_usd=exam_risk,
        total_entry_costs_usd=total,
        notes=notes,
    )


# ── Country-of-origin marking ───────────────────────────────────────────────

_MARKING_RULES = {
    "default": (
        "19 USC §1304: All imported articles must be conspicuously marked with "
        "the English name of the country of origin (e.g. 'Made in China'). "
        "Marking must be legible, indelible, and in a location where it will "
        "be seen by the ultimate purchaser."
    ),
    "exceptions": [
        "Articles incapable of being marked (e.g. bulk chemicals)",
        "Articles that would be substantially damaged by marking",
        "Crude substances",
        "Articles imported for the use of the importer and not for resale",
    ],
}


# ── Compliance report ────────────────────────────────────────────────────────

@dataclass
class ComplianceReport:
    hts_code: str
    origin: str
    chapter: str
    regulatory_requirements: list[ComplianceRequirement]
    uflpa_risk: UFLPARisk
    marking_rule: str
    marking_exceptions: list[str]
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "hts_code": self.hts_code,
            "origin": self.origin,
            "chapter": self.chapter,
            "regulatory_requirements": [r.as_dict() for r in self.regulatory_requirements],
            "regulatory_agencies": list({r.agency for r in self.regulatory_requirements}),
            "uflpa_risk": self.uflpa_risk.as_dict(),
            "marking": {
                "rule": self.marking_rule,
                "exceptions": self.marking_exceptions,
            },
            "notes": self.notes,
        }


def get_compliance_report(hts_code: str, origin: str = "CN") -> ComplianceReport:
    """Generate a full compliance report for a product."""
    norm = normalize_hts_code(hts_code) or ""
    chapter = norm[:2] if len(norm) >= 2 else ""

    # Find matching regulatory requirements
    reqs = [
        r for r in _COMPLIANCE_MAP
        if any(chapter.startswith(ch) for ch in r.applies_to_chapters)
    ]

    uflpa = _assess_uflpa(chapter, origin)

    notes = []
    if not reqs:
        notes.append(
            f"No specific product safety requirements mapped for HTS chapter {chapter}. "
            "This does not mean the product is unregulated — consult a compliance specialist."
        )

    origin_key = origin.strip().upper()
    if origin_key in {"CN", "CHN", "CHINA", "中国", "PRC"}:
        notes.append(
            "China-origin products face elevated CBP scrutiny. "
            "Ensure country-of-origin marking is correct and all certifications are current."
        )

    return ComplianceReport(
        hts_code=hts_code,
        origin=origin,
        chapter=chapter,
        regulatory_requirements=reqs,
        uflpa_risk=uflpa,
        marking_rule=_MARKING_RULES["default"],
        marking_exceptions=_MARKING_RULES["exceptions"],
        notes=notes,
    )


def get_compliance_flags(hts_code: str) -> list[str]:
    """Return list of regulatory agency codes for an HTS code (for embedding in overlay)."""
    norm = normalize_hts_code(hts_code) or ""
    chapter = norm[:2] if len(norm) >= 2 else ""
    agencies = set()
    for req in _COMPLIANCE_MAP:
        if any(chapter.startswith(ch) for ch in req.applies_to_chapters):
            agencies.add(req.agency)
    return sorted(agencies)
