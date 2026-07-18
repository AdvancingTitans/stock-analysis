"""Shared OHLCV analytics for stocks, funds, and tracked indices."""

from __future__ import annotations

import math
from typing import Any


def build_price_series_pack(samples: list[dict[str, Any]]) -> dict[str, Any]:
    ordered = sorted(samples, key=lambda row: str(row["date"]))
    metrics: dict[str, float] = {}
    for days in (5, 20, 60):
        if len(ordered) > days and ordered[-days - 1]["close"] > 0:
            metrics[f"returns_{days}d"] = (ordered[-1]["close"] / ordered[-days - 1]["close"] - 1) * 100
    if len(ordered) >= 61:
        closes = [item["close"] for item in ordered[-61:]]
        peak = closes[0]
        max_drawdown = 0.0
        for close in closes[1:]:
            peak = max(peak, close)
            max_drawdown = min(max_drawdown, close / peak - 1)
        daily_returns = [closes[index] / closes[index - 1] - 1 for index in range(1, len(closes))]
        average_return = sum(daily_returns) / len(daily_returns)
        variance = sum((value - average_return) ** 2 for value in daily_returns) / (len(daily_returns) - 1)
        metrics["max_drawdown_60d_pct"] = max_drawdown * 100
        metrics["annualized_volatility_60d_pct"] = math.sqrt(variance) * math.sqrt(252) * 100
    if len(ordered) >= 21 and all(item.get("volume") is not None for item in ordered[-21:]):
        history = [item["volume"] for item in ordered[-21:-1]]
        average = sum(history) / len(history)
        variance = sum((value - average) ** 2 for value in history) / len(history)
        if variance > 0:
            metrics["volume_zscore"] = (ordered[-1]["volume"] - average) / math.sqrt(variance)
    if len(ordered) >= 15:
        ranges = []
        for index in range(len(ordered) - 14, len(ordered)):
            current, previous = ordered[index], ordered[index - 1]
            ranges.append(max(current["high"] - current["low"], abs(current["high"] - previous["close"]), abs(current["low"] - previous["close"])))
        metrics["atr_14_pct"] = sum(ranges) / len(ranges) / ordered[-1]["close"] * 100
    turnovers = [float(item["turnover_cny"]) for item in ordered[-20:] if item.get("turnover_cny") is not None]
    liquidity = {
        "average_turnover_20d_cny": sum(turnovers) / len(turnovers) if turnovers else None,
        "turnover_sample_size": len(turnovers),
    }
    return {
        "available": bool(metrics),
        "sample_size": len(ordered),
        "metrics": metrics,
        "liquidity": liquidity,
        "rows": ordered[-90:],
    }


def compare_price_series(asset_rows: list[dict[str, Any]], benchmark_rows: list[dict[str, Any]]) -> dict[str, Any]:
    asset = {str(row["date"]).replace("-", ""): float(row["close"]) for row in asset_rows if row.get("close")}
    benchmark = {str(row["date"]).replace("-", ""): float(row["close"]) for row in benchmark_rows if row.get("close")}
    dates = sorted(set(asset) & set(benchmark))
    pairs = []
    for previous, current in zip(dates, dates[1:]):
        if asset[previous] <= 0 or benchmark[previous] <= 0:
            continue
        pairs.append((asset[current] / asset[previous] - 1, benchmark[current] / benchmark[previous] - 1))
    if len(pairs) < 20:
        return {"available": False, "aligned_days": len(pairs), "reason": "aligned daily returns fewer than 20"}
    asset_returns = [pair[0] for pair in pairs]
    benchmark_returns = [pair[1] for pair in pairs]
    asset_mean = sum(asset_returns) / len(asset_returns)
    benchmark_mean = sum(benchmark_returns) / len(benchmark_returns)
    covariance = sum(
        (asset_return - asset_mean) * (benchmark_return - benchmark_mean)
        for asset_return, benchmark_return in pairs
    ) / (len(pairs) - 1)
    asset_variance = sum((value - asset_mean) ** 2 for value in asset_returns) / (len(pairs) - 1)
    benchmark_variance = sum((value - benchmark_mean) ** 2 for value in benchmark_returns) / (len(pairs) - 1)
    active_returns = [asset_return - benchmark_return for asset_return, benchmark_return in pairs]
    active_mean = sum(active_returns) / len(active_returns)
    active_variance = sum((value - active_mean) ** 2 for value in active_returns) / (len(active_returns) - 1)
    correlation = covariance / math.sqrt(asset_variance * benchmark_variance) if asset_variance > 0 and benchmark_variance > 0 else None
    return {
        "available": True,
        "aligned_days": len(pairs),
        "correlation": correlation,
        "beta": covariance / benchmark_variance if benchmark_variance > 0 else None,
        "annualized_tracking_error_pct": math.sqrt(active_variance) * math.sqrt(252) * 100,
        "annualized_active_return_pct": active_mean * 252 * 100,
    }
