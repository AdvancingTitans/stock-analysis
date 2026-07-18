"""Common evidence-consumption contract for every selected investment lens."""

from __future__ import annotations

from typing import Any

COMMON_META_EVIDENCE_KEYS = (
    "company_primary_disclosures",
    "fund_index_snapshots",
    "stock_financials",
    "stock_trading_costs",
    "market_price_volume",
    "portfolio_exposure",
)


def _flatten(value: Any, prefix: str, result: dict[str, Any]) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key in {"rows", "source_events", "depth_levels", "urls", "limitations"}:
                continue
            _flatten(child, f"{prefix}.{key}" if prefix else str(key), result)
    elif isinstance(value, list):
        if len(value) <= 10 and all(not isinstance(item, (dict, list)) for item in value):
            result[prefix] = value
        else:
            # Keep structured disclosure/financial facts consumable without copying bulky raw rows.
            for index, item in enumerate(value[:50]):
                if not isinstance(item, dict):
                    continue
                metric = item.get("metric") or item.get("name") or item.get("period_label") or index
                if item.get("value") is not None:
                    result[f"{prefix}.{metric}"] = item["value"]
                else:
                    _flatten(item, f"{prefix}.{metric}", result)
    elif isinstance(value, (int, float, str, bool)) and value not in ("", None):
        result[prefix] = value


def common_evidence_metrics(evidence: dict[str, Any]) -> dict[str, Any]:
    metrics: dict[str, Any] = {}
    for module in ("M1", "M2", "M3", "M4", "M5", "M6"):
        if isinstance(evidence.get(module), dict):
            _flatten(evidence[module], module, metrics)
    meta = evidence.get("_meta") or {}
    for key in COMMON_META_EVIDENCE_KEYS:
        if key in meta:
            _flatten(meta[key], key, metrics)
    return metrics


def build_lens_metric_analyses(evidence: dict[str, Any], lenses: tuple[str, ...]) -> dict[str, dict[str, dict[str, Any]]]:
    metrics = common_evidence_metrics(evidence)
    return {
        lens_id: {
            path: {
                "value": value,
                "interpretation": _interpret(lens_id, path, value),
            }
            for path, value in metrics.items()
        }
        for lens_id in lenses
    }


def _interpret(lens_id: str, path: str, value: Any) -> str:
    if "trading_cost" in path or "spread" in path or "turnover" in path:
        focus = "成交可实现性与成本后收益"
    elif "primary_disclosures" in path or "financial" in path:
        focus = "基本面、治理与资本配置"
    elif "index" in path or "volatility" in path or "drawdown" in path:
        focus = "趋势、因子暴露与风险预算"
    else:
        focus = "市场状态与反证"
    return f"{lens_id} 框架将 {path}={value} 用于{focus}判断"
