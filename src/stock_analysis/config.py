from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SourceConfig:
    enable_mootdx: bool = False
    eastmoney_min_interval: float = 1.0
    eastmoney_max_retries: int = 3
    camofox_health_url: str = "http://localhost:9377/json/version"
    camofox_timeout_seconds: float = 3.0
    browser_fallback_order: list[str] = field(
        default_factory=lambda: ["camofox-browser", "hermes-browser", "playwright"]
    )


TENCENT_FIELD_MAP = {
    1: "name",
    2: "code",
    3: "price",
    4: "previous_close",
    5: "open_price",
    31: "change",
    32: "change_pct",
    33: "high",
    34: "low",
    37: "turnover",
    38: "turnover_rate",
    39: "pe",
    44: "total_market_cap",
    45: "float_market_cap",
    46: "pb",
}
