"""Deterministic forward/reverse valuation and research-discipline helpers.

The functions in this module calculate what a set of explicit assumptions
means.  They do not source forecasts, choose a target multiple, or turn an
unverified premise into a fact.
"""

from __future__ import annotations

from typing import Any

DEFAULT_IMPLIED_MULTIPLES = (15.0, 18.0, 20.0, 22.0, 25.0, 30.0, 35.0)


def _number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a number")
    return float(value)


def _positive(value: Any, field: str) -> float:
    result = _number(value, field)
    if result <= 0:
        raise ValueError(f"{field} must be greater than zero")
    return result


def audit_premises(premises: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Classify supplied claims without pretending an unverified value is true."""

    audited = []
    for index, raw in enumerate(premises or []):
        item = dict(raw)
        claim = item.get("claim")
        asserted = item.get("asserted_value")
        verified = item.get("verified_value")
        asserted_scope = item.get("asserted_scope")
        verified_scope = item.get("verified_scope")
        if not claim:
            raise ValueError(f"premises[{index}].claim is required")
        if verified is None:
            status = "unverifiable"
            reason = "no verified comparison value"
        elif asserted_scope and verified_scope and asserted_scope != verified_scope:
            status = "ambiguous"
            reason = "accounting or reporting scope is not comparable"
        elif isinstance(asserted, (int, float)) and isinstance(verified, (int, float)):
            tolerance = abs(_number(item.get("tolerance", 0.0), f"premises[{index}].tolerance"))
            status = "verified" if abs(float(asserted) - float(verified)) <= tolerance else "incorrect"
            reason = "within tolerance" if status == "verified" else "asserted value differs from verified value"
        else:
            status = "verified" if asserted == verified else "incorrect"
            reason = "values match" if status == "verified" else "asserted value differs from verified value"
        audited.append({**item, "status": status, "reason": reason})
    return audited


def arbitrate_evidence(candidates: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Select the best comparable candidate per metric and preserve conflicts.

    Freshness only breaks ties after scope, effective period and source tier
    have been made comparable.
    """

    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for index, raw in enumerate(candidates or []):
        item = dict(raw)
        metric = str(item.get("metric") or "")
        if not metric:
            raise ValueError(f"evidence_candidates[{index}].metric is required")
        key = (metric, str(item.get("period") or "unknown"), str(item.get("scope") or "unknown"))
        groups.setdefault(key, []).append(item)

    decisions = []
    for (metric, period, scope), rows in groups.items():
        ranked = sorted(
            rows,
            key=lambda row: (
                int(row.get("source_tier", 99)),
                -int(str(row.get("published_at") or "0").replace("-", "")[:8] or 0),
            ),
        )
        selected = ranked[0]
        conflicts = [row for row in ranked[1:] if row.get("value") != selected.get("value")]
        decisions.append({
            "metric": metric,
            "period": period,
            "scope": scope,
            "selected": selected,
            "conflicts": conflicts,
            "selection_reason": "lowest source tier, then latest comparable publication",
        })
    return decisions


def _product_line_model(lines: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    result = []
    for index, raw in enumerate(lines or []):
        item = dict(raw)
        name = str(item.get("name") or "")
        if not name:
            raise ValueError(f"product_lines[{index}].name is required")
        units = _number(item.get("units"), f"product_lines[{index}].units")
        asp = _number(item.get("asp"), f"product_lines[{index}].asp")
        revenue = units * asp
        margin = _number(item.get("net_margin_pct", 0), f"product_lines[{index}].net_margin_pct")
        result.append({
            **item,
            "revenue": revenue,
            "net_profit": revenue * margin / 100,
            "formula": "units * asp; net_profit = revenue * net_margin_pct",
        })
    return result


def build_expectation_model(
    market_cap: float | int | None,
    assumptions: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a reconciled forward model and market-implied expectation bridge."""

    assumptions = dict(assumptions or {})
    if market_cap is None:
        return {
            "status": "unavailable",
            "reason": "total market capitalisation is unavailable",
            "premise_audit": audit_premises(assumptions.get("premises")),
            "evidence_arbitration": arbitrate_evidence(assumptions.get("evidence_candidates")),
        }
    equity_value = _positive(market_cap, "market_cap")
    multiples = assumptions.get("multiples") or DEFAULT_IMPLIED_MULTIPLES
    implied = []
    for index, multiple in enumerate(multiples):
        multiple_value = _positive(multiple, f"multiples[{index}]")
        implied.append({
            "multiple": multiple_value,
            "implied_net_profit": equity_value / multiple_value,
            "formula": "market_cap / multiple",
        })

    products = _product_line_model(assumptions.get("product_lines"))
    product_profit = sum(item["net_profit"] for item in products)
    segments = []
    known_value = 0.0
    forward_profit = 0.0
    included_product_lines: set[str] = set()
    for index, raw in enumerate(assumptions.get("segments") or []):
        item = dict(raw)
        name = str(item.get("name") or "")
        if not name:
            raise ValueError(f"segments[{index}].name is required")
        profit = _number(item.get("net_profit"), f"segments[{index}].net_profit")
        multiple = _positive(item.get("multiple"), f"segments[{index}].multiple")
        value = profit * multiple
        product_names = {str(value) for value in item.get("includes_product_lines") or []}
        duplicate_names = included_product_lines & product_names
        if duplicate_names:
            raise ValueError(f"product lines counted in more than one segment: {', '.join(sorted(duplicate_names))}")
        included_product_lines |= product_names
        segments.append({**item, "value": value, "formula": "net_profit * multiple"})
        known_value += value
        forward_profit += profit

    product_names = {item["name"] for item in products}
    unknown_inclusions = included_product_lines - product_names
    if unknown_inclusions:
        raise ValueError(f"segments reference unknown product lines: {', '.join(sorted(unknown_inclusions))}")
    standalone_product_profit = sum(item["net_profit"] for item in products if item["name"] not in included_product_lines)
    explicit_forward = assumptions.get("forward_net_profit")
    if explicit_forward is not None:
        forward_profit = _number(explicit_forward, "forward_net_profit")
    elif segments:
        forward_profit += standalone_product_profit
    elif products:
        forward_profit = product_profit

    residual = equity_value - known_value
    residual_status = "unallocated" if residual >= 0 else "overallocated"
    option = None
    option_input = assumptions.get("option_value") or {}
    if option_input:
        option_multiple = _positive(option_input.get("multiple"), "option_value.multiple")
        option_margin = option_input.get("net_margin_pct")
        required_profit = residual / option_multiple
        option = {
            **option_input,
            "residual_value": residual,
            "required_net_profit": required_profit,
            "required_revenue": (
                required_profit / (_positive(option_margin, "option_value.net_margin_pct") / 100)
                if option_margin is not None else None
            ),
            "status": residual_status,
            "formula": "residual_value / option_multiple; required_profit / net_margin",
        }

    expectation_gap = []
    if forward_profit:
        for row in implied:
            expectation_gap.append({
                "multiple": row["multiple"],
                "forward_net_profit": forward_profit,
                "implied_net_profit": row["implied_net_profit"],
                "gap": forward_profit - row["implied_net_profit"],
                "coverage_pct": forward_profit / row["implied_net_profit"] * 100,
            })

    monitoring = []
    for index, raw in enumerate(assumptions.get("monitoring") or []):
        item = dict(raw)
        if not item.get("metric") or not item.get("view_change_condition"):
            raise ValueError(f"monitoring[{index}] requires metric and view_change_condition")
        monitoring.append({"status": "pending", **item})

    return {
        "status": "complete" if assumptions else "market_implied_only",
        "valuation_year": assumptions.get("valuation_year"),
        "currency": assumptions.get("currency", "CNY"),
        "market_cap": equity_value,
        "premise_audit": audit_premises(assumptions.get("premises")),
        "evidence_arbitration": arbitrate_evidence(assumptions.get("evidence_candidates")),
        "market_implied": implied,
        "forward_model": {
            "product_lines": products,
            "segments": segments,
            "forward_net_profit": forward_profit or None,
            "known_segment_value": known_value or None,
        },
        "sotp_bridge": {
            "market_cap": equity_value,
            "known_segment_value": known_value,
            "residual_value": residual,
            "status": residual_status,
            "formula": "market_cap - known_segment_value",
        },
        "option_value": option,
        "expectation_gap": expectation_gap,
        "monitoring": monitoring,
        "boundaries": [
            "multiples and forward assumptions are user-supplied scenarios, not verified forecasts",
            "internally consumed product lines must be included in one segment only",
            "a negative residual is reported as overallocated and is never clamped to zero",
        ],
    }
