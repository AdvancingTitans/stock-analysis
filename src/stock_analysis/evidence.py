from __future__ import annotations

from dataclasses import dataclass, field

from .quality import EvidenceQuality

MODULE_WEIGHTS = {"M1": 20, "M2": 20, "M3": 20, "M4": 15, "M5": 15, "M6": 10}


@dataclass
class EvidenceBundle:
    trade_date: str
    modules: dict[str, dict] = field(default_factory=dict)
    meta: dict[str, object] = field(default_factory=dict)

    def quality(self) -> EvidenceQuality:
        self.meta["style"] = "research-report"
        self.meta["style_filter"] = "research-report-sanitized"
        module_scores: dict[str, int] = {}
        missing: list[str] = []
        diagnostics: dict[str, dict[str, object]] = {}

        for module, weight in MODULE_WEIGHTS.items():
            payload = self.modules.get(module) or {}
            if module == "M1":
                score, gaps, available = _score_m1(payload, weight)
            elif module == "M2":
                score, gaps, available = _score_m2(payload, weight)
            else:
                score, gaps, available = _score_simple(payload, weight)

            module_scores[module] = score
            diagnostics[module] = {"score": score, "max": weight, "gaps": gaps, "available": available}
            if not available:
                missing.append(module)

        quality = EvidenceQuality(module_scores=module_scores, missing_modules=missing)
        self.meta["quality_score"] = quality.total_score
        self.meta["missing_modules"] = missing
        self.meta["module_diagnostics"] = diagnostics
        return quality


def _score_simple(payload: dict, weight: int) -> tuple[int, list[str], bool]:
    available = bool(payload) and payload.get("available", True)
    if available:
        return weight, [], True
    return 0, ["unavailable"], False


def _score_m1(payload: dict, weight: int) -> tuple[int, list[str], bool]:
    gaps: list[str] = []
    score = 0
    a_indices = payload.get("a_indices") or []
    hk_indices = payload.get("hk_indices") or []
    us_indices = payload.get("us_indices") or []
    breadth = payload.get("breadth") or {}

    if a_indices:
        score += 8
    else:
        gaps.append("a_indices")

    if any(row.get("turnover") for row in a_indices + hk_indices + us_indices):
        score += 4
    else:
        gaps.append("turnover")

    if hk_indices:
        score += 4
    else:
        gaps.append("hk_indices")

    if breadth.get("available"):
        score += 4
    else:
        gaps.append("breadth")

    available = bool(a_indices or hk_indices or us_indices) and score >= 8
    return min(score, weight), gaps, available


def _score_m2(payload: dict, weight: int) -> tuple[int, list[str], bool]:
    gaps: list[str] = []
    score = 0
    industry_rows = payload.get("industry_top20") or []
    concept_rows = payload.get("concept_top20") or []
    fund_flow = payload.get("fund_flow") or {}
    concentration = payload.get("concentration") or {}

    if industry_rows or concept_rows:
        score += 12
    else:
        gaps.append("board_rankings")

    if fund_flow.get("_concept_in") or fund_flow.get("_concept_out") or fund_flow.get("rows"):
        score += 4
    else:
        gaps.append("fund_flow")

    if concentration.get("top1_ratio") is not None or concentration.get("top3_ratio") is not None:
        score += 4
    else:
        gaps.append("concentration")

    available = score >= 8
    if not available and score > 0:
        gaps.append("partial_only")
    return min(score, weight), gaps, available
