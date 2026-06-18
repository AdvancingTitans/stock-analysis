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
        for module, weight in MODULE_WEIGHTS.items():
            payload = self.modules.get(module)
            if payload and payload.get("available", True):
                module_scores[module] = weight
            else:
                module_scores[module] = 0
                missing.append(module)
        quality = EvidenceQuality(module_scores=module_scores, missing_modules=missing)
        self.meta["quality_score"] = quality.total_score
        self.meta["missing_modules"] = missing
        return quality
