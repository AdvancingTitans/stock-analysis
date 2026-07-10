"""Deterministic A-share annual-report screening.

This module intentionally does not infer investment quality.  It evaluates
explicit numerical conditions against a complete financial slice and a
separately-audited current security-master snapshot.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any

from .screening_baseline import FINANCIAL_FIELD_CONTRACT, normalize_annual_financial_row

FIELD_ALIASES = {
    "roe_weighted": "roe_weighted_pct",
    "roe_weighted_pct": "roe_weighted_pct",
    "total_operating_revenue_growth_yoy": "revenue_growth_yoy_pct",
    "revenue_growth_yoy": "revenue_growth_yoy_pct",
    "revenue_growth_yoy_pct": "revenue_growth_yoy_pct",
}


@dataclass(frozen=True)
class Filter:
    field: str
    operator: str
    value: float


@dataclass(frozen=True)
class Sort:
    field: str
    direction: str


def parse_filter(spec: str) -> Filter:
    """Parse ``field:gt:value`` without silently accepting another operator."""
    try:
        field, operator, raw_value = spec.split(":", 2)
    except ValueError as exc:
        raise ValueError("filter must use field:gt:value, e.g. roe_weighted:gt:8%") from exc
    normalized = _field(field)
    if operator != "gt":
        raise ValueError("only strict gt filters are supported by the MVP")
    return Filter(field=normalized, operator=operator, value=_percent_points(raw_value))


def parse_sort(spec: str) -> Sort:
    try:
        field, direction = spec.split(":", 1)
    except ValueError as exc:
        raise ValueError("sort must use field:asc or field:desc") from exc
    if direction not in {"asc", "desc"}:
        raise ValueError("sort direction must be asc or desc")
    return Sort(field=_field(field), direction=direction)


def load_security_master(path: str | Path) -> dict[str, Any]:
    """Load an official current-universe snapshot and reject incomplete input."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("universe file must contain a JSON object")
    records = payload.get("records")
    if not isinstance(records, list):
        raise ValueError("universe file must contain a records list")
    required = ("complete", "reported_total", "pages_fetched", "unique_symbols", "universe_as_of")
    missing = [key for key in required if key not in payload]
    if missing:
        raise ValueError(f"universe file is missing audit metadata: {', '.join(missing)}")
    if not payload["complete"]:
        raise ValueError("universe file is partial and cannot power a whole-market screen")
    if not all(isinstance(item, dict) for item in records):
        raise ValueError("universe file records must be JSON objects")
    try:
        reported_total = int(payload["reported_total"])
        pages_fetched = int(payload["pages_fetched"])
        unique_symbols = int(payload["unique_symbols"])
    except (TypeError, ValueError) as exc:
        raise ValueError("universe audit counts must be integers") from exc
    symbols = {str(item.get("symbol") or "") for item in records}
    if reported_total != len(records) or unique_symbols != len(symbols):
        raise ValueError("universe file failed count or uniqueness reconciliation")
    if pages_fetched < 1:
        raise ValueError("universe file has no fetched pages")
    if "" in symbols or any(len(symbol) != 6 or not symbol.isdigit() for symbol in symbols):
        raise ValueError("universe file contains an invalid security code")
    return payload


def screen(
    annual_rows: Iterable[dict[str, Any]],
    *,
    fiscal_year: int,
    universe: dict[str, Any],
    filters: Iterable[Filter],
    sort: Sort,
    limit: int,
    pagination: dict[str, Any],
) -> dict[str, Any]:
    """Evaluate the intersection of disclosed financials and current Universe."""
    filters = tuple(filters)
    if not filters:
        raise ValueError("at least one --filter is required")
    if len(filters) > 2:
        raise ValueError("the MVP supports at most two AND filters")
    if limit < 1:
        raise ValueError("limit must be positive")
    if not pagination.get("complete"):
        raise ValueError("financial pagination is partial and cannot power a whole-market screen")
    if not universe.get("complete"):
        raise ValueError("universe is partial and cannot power a whole-market screen")

    universe_symbols = {str(item["symbol"]) for item in universe["records"]}
    decisions = []
    for raw_row in annual_rows:
        record = normalize_annual_financial_row(raw_row, fiscal_year=fiscal_year)
        decision = _decide(record, filters=filters, universe_symbols=universe_symbols)
        decisions.append(decision)
    decisions.sort(key=lambda item: item["symbol"])
    passed = [item for item in decisions if item["status"] == "PASS"]
    reverse = sort.direction == "desc"
    passed.sort(key=lambda item: (item["values"][sort.field], item["symbol"]), reverse=reverse)
    results = passed[:limit]
    request = {
        "fiscal_year": fiscal_year,
        "filters": [filter.__dict__ for filter in filters],
        "sort": sort.__dict__,
        "limit": limit,
    }
    query_id = sha256(json.dumps(request, sort_keys=True).encode("utf-8")).hexdigest()[:12]
    quality = {
        "whole_market_eligible": True,
        "financial_pagination_complete": True,
        "universe_complete": True,
        "annual_rows": len(decisions),
        "universe_rows": len(universe_symbols),
        "intersection_rows": sum(item["in_universe"] for item in decisions),
        "pass": len(passed),
        "fail": sum(item["status"] == "FAIL" for item in decisions),
        "unknown": sum(item["status"] == "UNKNOWN" for item in decisions),
    }
    return {
        "query_id": query_id,
        "request": request,
        "universe": _universe_evidence(universe),
        "source_events": [
            {"source": "eastmoney:RPT_LICO_FN_CPD", "status": "ok"},
            {"source": "official-security-master", "status": "ok"},
        ],
        "pagination": dict(pagination),
        "quality": quality,
        "results": results,
        "decisions": decisions,
        "cache_metadata": {"generated_at": datetime.now(timezone.utc).isoformat()},
    }


def render_markdown(result: dict[str, Any]) -> str:
    request = result["request"]
    universe = result["universe"]
    labels = " AND ".join(_filter_label(item) for item in request["filters"])
    lines = [
        f"# A股条件命中股票（{request['fiscal_year']} 年报）",
        "",
        f"条件：{labels}；排序：{request['sort']['field']} {request['sort']['direction']}；Top {request['limit']}。",
        f"当前 Universe：{universe['universe_as_of']}，{universe['record_count']} 只，已通过完整性对账。",
        "",
        "这是一份确定性条件命中清单，不构成优质公司认定或投资建议。",
        "",
        "| 代码 | 名称 | 加权 ROE | 营收同比 |",
        "|---|---|---:|---:|",
    ]
    for item in result["results"]:
        lines.append(
            f"| {item['symbol']} | {item['name']} | {_format_pct(item['values']['roe_weighted_pct'])} "
            f"| {_format_pct(item['values']['revenue_growth_yoy_pct'])} |"
        )
    if not result["results"]:
        lines.append("| - | 无条件命中股票 | - | - |")
    return "\n".join(lines) + "\n"


def write_evidence(result: dict[str, Any], directory: str | Path) -> Path:
    path = Path(directory) / f"screen_evidence_{result['query_id']}.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _decide(record: dict[str, Any], *, filters: tuple[Filter, ...], universe_symbols: set[str]) -> dict[str, Any]:
    values = {name: field["normalized_value"] for name, field in record["fields"].items()}
    in_universe = record["symbol"] in universe_symbols
    clauses = []
    if not in_universe:
        status, reason = "UNKNOWN", "not_in_current_universe"
    else:
        status, reason = "PASS", "all_filters_passed"
        for filter in filters:
            value = values[filter.field]
            if value is None:
                clauses.append({"filter": filter.__dict__, "status": "UNKNOWN", "actual": None})
                status, reason = "UNKNOWN", f"missing_{filter.field}"
                continue
            passed = value > filter.value
            clauses.append({"filter": filter.__dict__, "status": "PASS" if passed else "FAIL", "actual": value})
            if not passed and status != "UNKNOWN":
                status, reason = "FAIL", f"{filter.field}_not_strictly_greater"
    return {
        "symbol": record["symbol"],
        "name": record["name"],
        "in_universe": in_universe,
        "status": status,
        "reason": reason,
        "values": values,
        "clauses": clauses,
        "announcement_date": record["announcement_date"],
    }


def _field(value: str) -> str:
    normalized = FIELD_ALIASES.get(value.strip())
    if normalized is None:
        supported = ", ".join(sorted(FIELD_ALIASES))
        raise ValueError(f"unsupported screening field {value!r}; supported: {supported}")
    return normalized


def _percent_points(value: str) -> float:
    try:
        return float(value.strip().removesuffix("%"))
    except (AttributeError, ValueError) as exc:
        raise ValueError("filter value must be a numeric percent-point value, e.g. 8%") from exc


def _universe_evidence(universe: dict[str, Any]) -> dict[str, Any]:
    return {
        "universe_as_of": universe["universe_as_of"],
        "record_count": len(universe["records"]),
        "reported_total": universe["reported_total"],
        "pages_fetched": universe["pages_fetched"],
        "unique_symbols": universe["unique_symbols"],
        "complete": universe["complete"],
        "sources": universe.get("sources", []),
    }


def _filter_label(filter: dict[str, Any]) -> str:
    source = FINANCIAL_FIELD_CONTRACT[filter["field"]]["description"].split("；", 1)[0]
    return f"{source} > {filter['value']:g}%"


def _format_pct(value: float | None) -> str:
    return "-" if value is None else f"{value:.2f}%"
