from __future__ import annotations

from dataclasses import dataclass


@dataclass
class EvidenceQuality:
    module_scores: dict[str, int]
    missing_modules: list[str]

    @property
    def total_score(self) -> int:
        return sum(self.module_scores.values())

    @property
    def degrade_mode(self) -> str:
        if self.total_score < 60:
            return "simplified"
        if self.total_score < 80:
            return "degraded"
        return "full"
