from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import SourceConfig
from .diagnostics import run_diagnostics
from .evidence import EvidenceBundle
from .integrations import (
    fetch_a_indices,
    fetch_board_list,
    fetch_fund_estimate,
    fetch_fund_flow,
    fetch_fund_holding_quotes,
    fetch_fund_holdings,
    fetch_hk_indices,
    fetch_limit_pools,
    fetch_northbound_flow,
    fetch_single_quote,
    fetch_us_indices,
)
from .market_time import detect_market_session, resolve_trade_date
from .portfolio import build_portfolio_snapshot
from .profile import load_holdings_from_profile
from .market_sentiment import fetch_market_sentiment
from .reporting import render_diagnostics, render_report_with_metadata


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evidence-driven global stock market recap")
    parser.add_argument("legacy_date", nargs="?", help=argparse.SUPPRESS)
    parser.add_argument("--date", help="Explicit trade date YYYYMMDD")
    parser.add_argument(
        "--market",
        default="daily",
        choices=["daily", "a", "hk", "us", "global", "stock", "fund", "diagnose"],
    )
    parser.add_argument(
        "--format",
        dest="report_format",
        default="auto",
        choices=["auto", "summary", "key-points", "full"],
    )
    parser.add_argument("--with-holdings", action="store_true", help="Load local stock-analysis investment memory")
    parser.add_argument("--disable-mootdx", action="store_true")
    parser.add_argument("--enable-mootdx", action="store_true")
    parser.add_argument("--emit-evidence", action="store_true")
    parser.add_argument("--lens", help="Investor lens id for single mode, e.g. buffett")
    parser.add_argument("--mode", choices=["single", "committee", "adversarial"], help="Lens analysis mode")
    parser.add_argument("--lenses", help="Comma-separated lens ids for committee or adversarial mode")
    parser.add_argument(
        "--report-style",
        default="committee",
        choices=["classic", "committee"],
        help="deprecated alias; all reports use committee structure (default)",
    )
    parser.add_argument("--symbol", help="Symbol for --market stock or --market fund")
    parser.add_argument("--stock", dest="symbol", help="Alias for --symbol with --market stock")
    parser.add_argument("--fund", dest="symbol", help="Alias for --symbol with --market fund")
    return parser


def _a_indices_payload(trade_date: str) -> list[dict[str, Any]]:
    rows = []
    for item in fetch_a_indices(trade_date):
        rows.append(
            {
                "symbol": item.get("f12"),
                "name": item.get("f14"),
                "price": item.get("f2"),
                "change": item.get("f4"),
                "change_pct": item.get("f3"),
                "turnover": item.get("f6"),
                "trade_date": _normalize_trade_date(item.get("_source_date")) or trade_date,
                "source": item.get("_source") or "",
            }
        )
    return rows


def _quote_payload(quote) -> dict[str, Any]:
    if quote is None:
        return {}
    return {
        "symbol": quote.symbol,
        "name": quote.name,
        "price": quote.price,
        "change": quote.change,
        "change_pct": quote.change_pct,
        "turnover": quote.turnover,
        "trade_date": _normalize_trade_date(quote.trade_date),
        "source": quote.source,
        "currency": quote.currency,
    }


def build_evidence(trade_date: str, market: str, session_label: str, include_holdings: bool) -> tuple[EvidenceBundle, dict[str, Any]]:
    holdings = load_holdings_from_profile() if include_holdings else []
    portfolio_snapshot = build_portfolio_snapshot(holdings, trade_date) if holdings else {"details": []}

    a_indices = _a_indices_payload(trade_date)
    hk_indices = [_quote_payload(q) for q in fetch_hk_indices(trade_date)]
    us_indices = [_quote_payload(q) for q in fetch_us_indices(trade_date)]
    northbound = fetch_northbound_flow(trade_date)
    fund_flow = fetch_fund_flow(trade_date)
    industry = fetch_board_list("industry", trade_date, limit=200)
    concept = fetch_board_list("concept", trade_date, limit=20)
    pools = fetch_limit_pools(trade_date) if market in {"daily", "a", "global"} else {"zt": {}, "dt": {}, "zb": {}}
    pool_stats = _pool_statistics(pools)
    feature_groups = _feature_groups(pools)
    concentration = _concentration_snapshot(pools, industry, concept)
    breadth = _market_breadth(industry)

    m1 = {
        "available": bool(a_indices or hk_indices or us_indices),
        "a_indices": a_indices,
        "hk_indices": hk_indices,
        "us_indices": us_indices,
        "northbound": northbound,
        "breadth": breadth,
        "cross_market_comment": _cross_market_comment(a_indices, hk_indices, us_indices),
    }
    _enrich_portfolio_benchmarks(portfolio_snapshot, m1)
    has_board_rows = bool(industry.get("rows") or concept.get("rows"))
    has_fund_flow = bool(
        fund_flow.get("_concept_in")
        or fund_flow.get("_concept_out")
        or fund_flow.get("rows")
    )
    has_concentration = concentration.get("top1_ratio") is not None or concentration.get("top3_ratio") is not None
    m2 = {
        "available": has_board_rows or (has_fund_flow and has_concentration),
        "industry_top20": industry.get("rows", [])[:20],
        "concept_top20": concept.get("rows", [])[:20],
        "fund_flow": fund_flow,
        "concentration": concentration,
        "summary": _module2_summary(industry, concept, fund_flow, concentration),
        "fallback": industry.get("_fallback") or concept.get("_fallback"),
        "board_rankings_available": has_board_rows,
        "fund_flow_available": has_fund_flow,
    }
    m3 = {
        "available": bool((pools.get("zt", {}).get("data") or {}).get("pool")),
        "zt_count": (pools.get("zt", {}).get("data") or {}).get("tc", 0),
        "zb_count": (pools.get("zb", {}).get("data") or {}).get("tc", 0),
        "pool_stats": pool_stats,
        "summary": _module3_summary(pool_stats),
    }
    m4 = {
        "available": bool((pools.get("dt", {}).get("data") or {}).get("pool")) or bool((pools.get("zb", {}).get("data") or {}).get("pool")),
        "dt_count": (pools.get("dt", {}).get("data") or {}).get("tc", 0),
        "pool_stats": pool_stats,
        "summary": _module4_summary(pool_stats),
    }
    m5 = {
        "available": any(feature_groups.values()) or bool(portfolio_snapshot.get("details")),
        "styles": _style_distribution(portfolio_snapshot.get("details", [])),
        "feature_groups": feature_groups,
        "summary": _module5_summary(portfolio_snapshot, feature_groups),
    }
    m6 = {
        "available": bool(_resilient_directions(industry, concept, pool_stats)),
        "resilient": _resilient_directions(industry, concept, pool_stats),
        "summary": _module6_summary(industry, concept, pool_stats, m1),
    }
    public_pulses = [
        detail["public_pulse"]
        for detail in portfolio_snapshot.get("details", [])
        if detail.get("public_pulse")
    ]
    market_sentiment = fetch_market_sentiment(trade_date)
    chinese_news_items = market_sentiment.get("chinese_news_items") or []
    chinese_community_items = market_sentiment.get("chinese_community_items") or []
    market_pulse = market_sentiment.get("market_public_pulse")
    if market_pulse:
        public_pulses = [market_pulse, *public_pulses]
    source_events = _source_events(a_indices, hk_indices, us_indices, industry, concept)
    source_events.extend(market_sentiment.get("source_events") or [])
    if public_pulses:
        source_events.append(
            {
                "module": "portfolio_public_pulse",
                "source": "Futu public gateway",
                "symbols": [pulse.get("symbol") for pulse in public_pulses],
                "generated_at": max(str(pulse.get("generated_at") or "") for pulse in public_pulses),
            }
        )
    evidence = EvidenceBundle(
        trade_date=trade_date,
        modules={"M1": m1, "M2": m2, "M3": m3, "M4": m4, "M5": m5, "M6": m6},
        meta={
            "trade_date": trade_date,
            "session": session_label,
            "source_events": source_events,
            "portfolio_public_pulse": public_pulses,
            "chinese_news_items": chinese_news_items,
            "chinese_community_items": chinese_community_items,
            "market_public_pulse": market_pulse,
            "portfolio_advice_sections": _portfolio_advice_sections(portfolio_snapshot, m1, m2, m3, m4),
        },
    )
    return evidence, portfolio_snapshot


def _normalize_trade_date(value: Any) -> str:
    digits = "".join(character for character in str(value or "") if character.isdigit())
    return digits[:8] if len(digits) >= 8 else ""


def _market_breadth(industry: dict[str, Any]) -> dict[str, Any]:
    rows = industry.get("rows") or []
    up = sum(int(row.get("up_count") or 0) for row in rows)
    down = sum(int(row.get("down_count") or 0) for row in rows)
    return {
        "available": (up + down) > 0,
        "up": up,
        "down": down,
        "ratio": (up / down) if down else None,
        "scope": "行业板块成分汇总",
    }


def run(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    now = datetime.now()
    market = "a" if args.market in {"daily", "a", "global"} else args.market
    explicit_date = args.date or args.legacy_date
    if explicit_date and (len(explicit_date) != 8 or not explicit_date.isdigit()):
        parser.error("--date must use YYYYMMDD")
    if explicit_date and explicit_date > now.strftime("%Y%m%d"):
        parser.error("--date cannot be in the future")
    trade_date = explicit_date or resolve_trade_date(now, market=market)
    session = detect_market_session(now, market=market)
    if explicit_date and trade_date < now.strftime("%Y%m%d"):
        session.label = "盘后"
        session.depth = "full"
    config = SourceConfig(enable_mootdx=args.enable_mootdx and not args.disable_mootdx)
    if args.market == "diagnose":
        print(render_diagnostics(run_diagnostics(config)))
        return 0
    if args.market == "stock":
        if not args.symbol:
            parser.error("--symbol or --stock is required when --market stock")
        print(_render_stock_snapshot(args.symbol, trade_date))
        return 0
    if args.market == "fund":
        if not args.symbol:
            parser.error("--symbol or --fund is required when --market fund")
        print(_render_fund_snapshot(args.symbol, trade_date))
        return 0

    evidence, portfolio_snapshot = build_evidence(
        trade_date=trade_date,
        market=args.market,
        session_label=session.label,
        include_holdings=_should_include_holdings(args.market, args.with_holdings),
    )
    quality = evidence.quality()
    report_format = args.report_format
    if report_format == "auto":
        report_format = {"light": "summary", "medium": "key-points", "full": "full"}[session.depth]
    lenses = tuple(item.strip() for item in (args.lenses or "").split(",") if item.strip()) or None
    result = render_report_with_metadata(
        trade_date=trade_date,
        session_label=session.label,
        evidence=evidence,
        quality=quality,
        portfolio_snapshot=portfolio_snapshot,
        report_format=report_format,
        lens=args.lens,
        lenses=lenses,
        mode=args.mode,
    )
    print(result.markdown)
    if args.emit_evidence:
        base = Path.cwd()
        (base / f"evidence_{trade_date}.json").write_text(
            json.dumps({"modules": evidence.modules, "_meta": evidence.meta}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        for key, payload in evidence.modules.items():
            (base / f"{key.lower()}_{trade_date}.json").write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
    return 0


def _should_include_holdings(market: str, explicitly_requested: bool) -> bool:
    del market
    return explicitly_requested


def _render_stock_snapshot(symbol: str, trade_date: str) -> str:
    quote = fetch_single_quote(symbol, trade_date)
    lines = [f"# 单股速览（{trade_date}）", ""]
    lines.extend(
        [
            "| 代码 | 名称 | 市场 | 最新价 | 涨跌幅 | 交易日 |",
            "|---|---|---|---:|---:|---|",
        ]
    )
    if quote is None or quote.price is None:
        lines.append(f"| {symbol} |  |  |  |  |  |")
        lines.extend(["", "关键报价暂不可用；已保留缺口，不用零值替代。"])
    else:
        price = f"{float(quote.price):,.2f} {quote.currency}".strip()
        quote_trade_date = _normalize_trade_date(quote.trade_date) or trade_date
        lines.append(
            f"| {quote.symbol} | {quote.name or quote.symbol} | {_market_label(quote.market)} | "
            f"{price} | {_format_pct(quote.change_pct)} | {quote_trade_date} |"
        )
        previous_close = _format_number(quote.previous_close)
        open_price = _format_number(quote.open_price)
        high = _format_number(quote.high)
        low = _format_number(quote.low)
        volume = _format_number(quote.volume, digits=0)
        turnover = _format_amount_yi(quote.turnover)
        lines.extend(
            [
                "",
                "| 昨收 | 开盘 | 最高 | 最低 | 成交量 | 成交额 |",
                "|---:|---:|---:|---:|---:|---:|",
                f"| {previous_close} | {open_price} | {high} | {low} | {volume} | {turnover} |",
            ]
        )
        if quote.quality_flags:
            lines.extend(["", "数据质量提示："] + [f"- {flag}" for flag in quote.quality_flags])
    lines.extend(["", "以上内容仅供参考，不构成任何投资建议。股市有风险，投资需谨慎。"])
    return "\n".join(lines)


def _render_fund_snapshot(code: str, trade_date: str) -> str:
    estimate = fetch_fund_estimate(code, trade_date)
    holdings = fetch_fund_holdings(code, trade_date, limit=5).get("holdings") or []
    quotes = fetch_fund_holding_quotes(holdings, trade_date)
    normalized_date = _normalize_trade_date(estimate.get("date")) or trade_date
    price = _safe_float(estimate.get("estimate_nav")) or _safe_float(estimate.get("nav"))
    change_pct = _safe_float(estimate.get("estimate_change_pct"))
    lines = [f"# 基金速览（{trade_date}）", ""]
    lines.extend(
        [
            "| 代码 | 名称 | 估值/净值 | 涨跌幅 | 交易日 |",
            "|---|---|---:|---:|---|",
            "| {code} | {name} | {price} CNY | {change_pct} | {trade_date} |".format(
                code=code,
                name=estimate.get("name") or code,
                price=_format_number(price),
                change_pct=_format_pct(change_pct),
                trade_date=normalized_date,
            ),
        ]
    )
    if holdings:
        lines.extend(
            [
                "",
                "## 重仓股",
                "| 代码 | 名称 | 权重 | 最新价 | 涨跌幅 |",
                "|---|---|---:|---:|---:|",
            ]
        )
        for item in holdings:
            symbol = str(item.get("code") or "")
            quote = quotes.get(symbol)
            lines.append(
                "| {symbol} | {name} | {weight} | {price} | {change_pct} |".format(
                    symbol=symbol,
                    name=item.get("name") or "",
                    weight=_format_pct(item.get("weight_pct"), signed=False),
                    price=_format_number(quote.price if quote else None),
                    change_pct=_format_pct(quote.change_pct if quote else None),
                )
            )
    else:
        lines.extend(["", "重仓股暂不可用；已保留缺口，不用零值替代。"])
    lines.extend(["", "以上内容仅供参考，不构成任何投资建议。股市有风险，投资需谨慎。"])
    return "\n".join(lines)


def _market_label(value: str) -> str:
    return {"a": "A股", "hk": "港股", "us": "美股", "fund": "基金"}.get(value, value)


def _format_pct(value: Any, *, signed: bool = True) -> str:
    number = _safe_float(value)
    if number is None:
        return ""
    prefix = "+" if signed and number > 0 else ""
    return f"{prefix}{number:.2f}%"


def _format_number(value: Any, digits: int = 2) -> str:
    number = _safe_float(value)
    if number is None:
        return ""
    return f"{number:,.{digits}f}"


def _format_amount_yi(value: Any) -> str:
    number = _safe_float(value)
    if number is None:
        return ""
    return f"{number / 1e8:,.2f}亿"


def _safe_float(value: Any) -> float | None:
    try:
        return None if value in (None, "") else float(value)
    except (TypeError, ValueError):
        return None


def _source_events(
    a_indices: list[dict[str, Any]],
    hk_indices: list[dict[str, Any]],
    us_indices: list[dict[str, Any]],
    industry: dict[str, Any],
    concept: dict[str, Any],
) -> list[dict[str, Any]]:
    events = []
    for market, rows in (("a", a_indices), ("hk", hk_indices), ("us", us_indices)):
        sources = sorted({str(row.get("source") or "") for row in rows if row.get("source")})
        dates = sorted({str(row.get("trade_date") or "") for row in rows if row.get("trade_date")})
        events.append({"market": market, "sources": sources, "trade_dates": dates})
    for board_type, payload in (("industry", industry), ("concept", concept)):
        if payload.get("_fallback"):
            events.append({"module": board_type, "fallback": payload["_fallback"]})
        elif not payload.get("rows"):
            events.append({"module": board_type, "status": "数据源不可用"})
    return events


def _cross_market_comment(a_indices: list[dict[str, Any]], hk_indices: list[dict[str, Any]], us_indices: list[dict[str, Any]]) -> str:
    markets: list[tuple[str, float]] = []
    if a_indices:
        markets.append(("A股", _avg_pct(a_indices)))
    if hk_indices:
        markets.append(("港股", _avg_pct(hk_indices)))
    if us_indices:
        markets.append(("美股", _avg_pct(us_indices)))
    if not markets:
        return "主要市场指数暂不可用，建议先核验数据源后再做跨市场比较。"
    if len(markets) < 3:
        missing = sorted({"A股", "港股", "美股"} - {name for name, _ in markets})
        leader = max(markets, key=lambda item: item[1])
        return (
            f"{'/'.join(missing)}指数暂缺；当前可得样本内{leader[0]}相对更强，跨市场结论仅供参考。"
        )
    ordered = sorted(markets, key=lambda item: item[1], reverse=True)
    if ordered[0][0] == "美股" and ordered[1][0] == "港股" and ordered[2][0] == "A股":
        return "美股强于港股，港股强于A股，风险偏好更多集中在海外成长资产。"
    if ordered[0][0] == "A股":
        return "A股相对最强，若成交额配合，说明内资主线更清晰。"
    return "三地市场强弱分化，建议结合成交额和持仓暴露控制节奏。"


def _avg_pct(rows: list[dict[str, Any]]) -> float:
    values = [float(row.get("change_pct")) for row in rows if row.get("change_pct") is not None]
    return sum(values) / len(values) if values else 0.0


def _module2_summary(industry: dict[str, Any], concept: dict[str, Any], fund_flow: dict[str, Any], concentration: dict[str, Any]) -> str:
    industry_rows = industry.get("rows") or []
    concept_rows = concept.get("rows") or []
    industry_name = industry_rows[0].get("name") if industry_rows else "暂无"
    concept_name = concept_rows[0].get("name") if concept_rows else "暂无"
    fragments = []
    if industry_name != "暂无":
        fragments.append(f"行业强势方向以 {industry_name} 为首")
    if concept_name != "暂无":
        fragments.append(f"概念方向以 {concept_name} 领涨")
    if not fragments:
        fragments.append("板块强弱更多体现为资金在若干高景气方向之间轮动")
    fragments.append(
        f"涨停板块集中度 TOP1/3 分别为 {concentration.get('top1_ratio', 0):.1%}/{concentration.get('top3_ratio', 0):.1%}"
    )
    return "；".join(fragments) + "。"


def _module3_summary(pool_stats: dict[str, Any]) -> str:
    return (
        f"涨停池 {pool_stats.get('zt_count', 0)} 家，首板 {pool_stats.get('first_board_count', 0)} 家，"
        f"连板 {pool_stats.get('multi_board_count', 0)} 家，封单金额合计约 {pool_stats.get('zt_fund_total_yi', 0):.2f} 亿元；"
        f"前 3 主线板块 {pool_stats.get('top_themes_text', '暂无')}。"
    )


def _module4_summary(pool_stats: dict[str, Any]) -> str:
    return (
        f"跌停池 {pool_stats.get('dt_count', 0)} 家，炸板池 {pool_stats.get('zb_count', 0)} 家，"
        f"炸板率约 {pool_stats.get('blowup_ratio', 0):.1%}；"
        f"若炸板率高于 25% 且连板占比回落，说明风险更偏向高位分歧。"
    )


def _style_distribution(details: list[dict[str, Any]]) -> dict[str, float]:
    result: dict[str, float] = {}
    for detail in details:
        style = str(detail.get("style") or "未知")
        weight = float(detail.get("market_value_cny") or 0)
        result[style] = result.get(style, 0.0) + weight
    return result


def _module5_summary(portfolio_snapshot: dict[str, Any], feature_groups: dict[str, Any]) -> str:
    details = portfolio_snapshot.get("details", [])
    styles = _style_distribution(details)
    if not styles:
        return "未提供持仓，模块按市场风格做通用观察。"
    top_style = max(styles.items(), key=lambda item: item[1])[0]
    return (
        f"当前持仓风格暴露以 {top_style} 为主；"
        f"盘面特征上，10:30 前涨停 {feature_groups.get('early_limit_up_count', 0)} 家，"
        f"低位异动 {feature_groups.get('low_position_active_count', 0)} 家，"
        f"科创/创业板活跃样本 {feature_groups.get('growth_board_count', 0)} 家。"
    )


def _resilient_directions(
    industry: dict[str, Any],
    concept: dict[str, Any],
    pool_stats: dict[str, Any],
) -> list[str]:
    candidates = []
    for row in (industry.get("rows") or [])[:5]:
        if (row.get("change_pct") or 0) >= 0:
            candidates.append(str(row.get("name")))
    for row in (concept.get("rows") or [])[:5]:
        if (row.get("change_pct") or 0) >= 0:
            candidates.append(str(row.get("name")))
    if not candidates:
        ordered_themes = sorted(
            (pool_stats.get("theme_counter") or {}).items(),
            key=lambda item: item[1],
            reverse=True,
        )
        candidates.extend(str(name) for name, _ in ordered_themes[:5])
    return candidates[:5]


def _module6_summary(
    industry: dict[str, Any],
    concept: dict[str, Any],
    pool_stats: dict[str, Any],
    m1: dict[str, Any],
) -> str:
    resilient = _resilient_directions(industry, concept, pool_stats)
    a_avg = _avg_pct(m1.get("a_indices", []))
    if resilient:
        prefix = "弱指数环境下仍有承接" if a_avg < 0.3 else "相对抗跌方向"
        return f"{prefix}主要集中在：{'、'.join(resilient)}。"
    return "当前未识别出明确抗跌方向。"


def _pool_items(pools: dict[str, Any], key: str) -> list[dict[str, Any]]:
    return ((pools.get(key, {}).get("data") or {}).get("pool") or [])


def _pool_statistics(pools: dict[str, Any]) -> dict[str, Any]:
    zt_pool = _pool_items(pools, "zt")
    dt_pool = _pool_items(pools, "dt")
    zb_pool = _pool_items(pools, "zb")
    zt_count = int(((pools.get("zt", {}).get("data") or {}).get("tc")) or len(zt_pool))
    dt_count = int(((pools.get("dt", {}).get("data") or {}).get("tc")) or len(dt_pool))
    zb_count = int(((pools.get("zb", {}).get("data") or {}).get("tc")) or len(zb_pool))
    first_board = 0
    multi_board = 0
    theme_counter: dict[str, int] = {}
    theme_fund: dict[str, float] = {}
    total_fund = 0.0
    for row in zt_pool:
        zttj = row.get("zttj") or {}
        board_count = int(zttj.get("ct") or 1)
        if board_count <= 1:
            first_board += 1
        else:
            multi_board += 1
        theme = str(row.get("hybk") or "未分类")
        theme_counter[theme] = theme_counter.get(theme, 0) + 1
        fund = float(row.get("fund") or 0.0)
        total_fund += fund
        theme_fund[theme] = theme_fund.get(theme, 0.0) + fund
    sorted_themes = sorted(theme_counter.items(), key=lambda item: item[1], reverse=True)
    top_text = "、".join(f"{name}{count}家" for name, count in sorted_themes[:3]) if sorted_themes else "暂无"
    leaders = sorted(
        (
            {
                "name": str(row.get("n") or row.get("c") or ""),
                "code": str(row.get("c") or ""),
                "board_days": int((row.get("zttj") or {}).get("ct") or 1),
                "seal_fund_yi": float(row.get("fund") or 0.0) / 1e8,
                "theme": str(row.get("hybk") or ""),
            }
            for row in zt_pool
        ),
        key=lambda row: (row["board_days"], row["seal_fund_yi"]),
        reverse=True,
    )[:10]
    return {
        "zt_count": zt_count,
        "dt_count": dt_count,
        "zb_count": zb_count,
        "first_board_count": first_board,
        "multi_board_count": multi_board,
        "zt_fund_total_yi": total_fund / 1e8,
        "blowup_ratio": (zb_count / (zt_count + zb_count)) if zt_count or zb_count else 0.0,
        "theme_counter": theme_counter,
        "theme_fund_yi": {key: value / 1e8 for key, value in theme_fund.items()},
        "top_themes_text": top_text,
        "leaders": leaders,
    }


def _feature_groups(pools: dict[str, Any]) -> dict[str, Any]:
    zt_pool = _pool_items(pools, "zt")
    early_limit = 0
    growth_board = 0
    low_position_active = 0
    for row in zt_pool:
        first_seal = int(row.get("fbt") or 0)
        code = str(row.get("c") or "")
        change_pct = float(row.get("zdp") or 0.0)
        if first_seal and first_seal <= 103000:
            early_limit += 1
        if code.startswith(("300", "688")):
            growth_board += 1
        if change_pct >= 9.9 and (float(row.get("ltsz") or 0.0) / 1e8) < 80:
            low_position_active += 1
    return {
        "early_limit_up_count": early_limit,
        "growth_board_count": growth_board,
        "low_position_active_count": low_position_active,
    }


def _concentration_snapshot(pools: dict[str, Any], industry: dict[str, Any], concept: dict[str, Any]) -> dict[str, Any]:
    zt_pool = _pool_items(pools, "zt")
    theme_counter: dict[str, int] = {}
    for row in zt_pool:
        theme = str(row.get("hybk") or "未分类")
        theme_counter[theme] = theme_counter.get(theme, 0) + 1
    ordered = sorted(theme_counter.values(), reverse=True)
    total = sum(ordered)
    top1 = (ordered[0] / total) if total and ordered else 0.0
    top3 = (sum(ordered[:3]) / total) if total else 0.0
    return {
        "top1_ratio": top1,
        "top3_ratio": top3,
        "industry_leader": ((industry.get("rows") or [{}])[0]).get("name") or None,
        "concept_leader": ((concept.get("rows") or [{}])[0]).get("name") or None,
    }


def _index_lookup(m1: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = m1.get("a_indices", []) + m1.get("hk_indices", []) + m1.get("us_indices", [])
    return {str(row.get("name") or ""): row for row in rows}


def _enrich_portfolio_benchmarks(portfolio_snapshot: dict[str, Any], m1: dict[str, Any]) -> None:
    indices = _index_lookup(m1)
    for detail in portfolio_snapshot.get("details", []):
        market = detail.get("market")
        style = str(detail.get("style") or "")
        symbol = str(detail.get("symbol") or "")
        if market == "us":
            benchmark = "纳斯达克" if style == "成长型" else "道琼斯"
        elif market == "hk":
            benchmark = "恒生科技指数" if style == "成长型" else "恒生指数"
        elif market == "fund":
            benchmark = "创业板指" if style == "成长型" else "上证指数"
        elif symbol.startswith(("300", "688")) or style == "成长型":
            benchmark = "创业板指"
        else:
            benchmark = "上证指数"
        benchmark_row = indices.get(benchmark)
        if not benchmark_row or benchmark_row.get("change_pct") is None or detail.get("change_pct") is None:
            continue
        relative = float(detail["change_pct"]) - float(benchmark_row["change_pct"])
        detail["benchmark_name"] = benchmark
        detail["benchmark_change_pct"] = benchmark_row["change_pct"]
        detail["relative_pct"] = relative
        detail["relative_label"] = "跑赢" if relative >= 0 else "跑输"


def _portfolio_advice_sections(
    portfolio_snapshot: dict[str, Any],
    m1: dict[str, Any],
    m2: dict[str, Any],
    m3: dict[str, Any],
    m4: dict[str, Any],
) -> dict[str, list[str]]:
    details = portfolio_snapshot.get("details", [])
    current: list[str] = []
    benchmark: list[str] = []
    position_actions: list[str] = []
    watchlist: list[str] = []
    risks: list[str] = []
    stats = m3.get("pool_stats", {})
    themes = [name for name, _ in sorted((stats.get("theme_counter") or {}).items(), key=lambda item: item[1], reverse=True)[:3]]
    direct_symbols = {str(detail.get("symbol") or "") for detail in details if detail.get("market") != "fund"}

    for detail in details:
        pct = detail.get("change_pct")
        daily_pnl = detail.get("daily_pnl_original")
        if pct is None:
            continue
        direction = "涨" if float(pct) >= 0 else "跌"
        sentence = f"{detail.get('name')}{direction}{abs(float(pct)):.2f}%"
        if daily_pnl is not None:
            pnl_direction = "浮盈" if float(daily_pnl) >= 0 else "浮亏"
            sentence += (
                f"（当日{pnl_direction}{abs(float(daily_pnl)):,.0f}"
                f"{_currency_name(str(detail.get('currency') or ''))}）"
            )
        if detail.get("relative_label"):
            sentence += (
                f"，{detail.get('relative_label')}{detail.get('benchmark_name')}"
                f"{abs(float(detail.get('relative_pct', 0))):.2f}个百分点"
            )
            benchmark.append(
                f"{detail.get('name')}{detail.get('relative_label')}{detail.get('benchmark_name')}"
                f"{abs(float(detail.get('relative_pct', 0))):.2f}个百分点；"
                f"{'相对收益为正，可继续检验强势持续性' if detail.get('relative_label') == '跑赢' else '相对收益为负，需关注弱势是否延续'}。"
            )
        current.append(sentence)

        if detail.get("relative_label") == "跑输":
            position_actions.append(
                f"{detail.get('name')}若连续两日跑输{detail.get('benchmark_name')}，"
                "且自身板块未进入成交额主线，应优先降低其对组合波动的贡献。"
            )
        elif detail.get("relative_label") == "跑赢" and float(detail.get("relative_pct", 0)) >= 0.5:
            position_actions.append(
                f"{detail.get('name')}当前具备相对收益，可继续保留观察；"
                f"若后续转为跑输{detail.get('benchmark_name')}，应把它视为强势逻辑减弱的信号。"
            )
        elif detail.get("relative_label") and abs(float(detail.get("relative_pct", 0))) < 0.2:
            position_actions.append(
                f"{detail.get('name')}当天基本跟随{detail.get('benchmark_name')}，"
                "暂不属于个股独立转弱，后续重点观察能否形成持续超额收益。"
            )
        if detail.get("trend") == "空头":
            position_actions.append(f"{detail.get('name')}均线结构偏弱，反弹时重点观察能否重新站上 MA10。")
        elif detail.get("trend") == "多头":
            position_actions.append(f"{detail.get('name')}均线保持多头排列，策略上以持有观察为主，不宜在指数情绪极端时追高。")

    held_styles = {str(detail.get("style") or "") for detail in details}
    for detail in details:
        overlaps = [
            str(item.get("name") or item.get("code"))
            for item in detail.get("fund_holdings", [])
            if str(item.get("code") or "") in direct_symbols
        ]
        if overlaps:
            position_actions.append(
                f"组合直接持有{'、'.join(overlaps)}，同时又通过{detail.get('name')}间接持有，"
                "形成重复暴露；调仓时应把两部分视为同一风险因子统一管理。"
            )
    if themes and any(style in held_styles for style in ("消费/防御型", "价值型")):
        position_actions.append(
            f"组合仍有较高消费/价值暴露，而当日涨停主线集中在{'、'.join(themes)}，持仓风格与活跃资金方向存在错位。"
        )
    if portfolio_snapshot.get("top3_ratio", 0) > 0.7:
        position_actions.append(
            f"前三大持仓占比达到{portfolio_snapshot.get('top3_ratio', 0):.1%}，"
            "新增仓位应优先用于降低相关性，而不是继续强化同一风格。"
        )
    if portfolio_snapshot.get("dominant_ratio", 0) > 0.8:
        position_actions.append(
            f"单一市场暴露达到{portfolio_snapshot.get('dominant_ratio', 0):.1%}，"
            "需把该市场指数转弱视为组合级风险信号。"
        )

    index_rows = m1.get("a_indices", [])
    extreme = [row for row in index_rows if row.get("change_pct") is not None and abs(float(row["change_pct"])) >= 3]
    for row in extreme:
        risks.append(f"{row.get('name')}单日涨幅达到{float(row['change_pct']):.2f}%，情绪偏极端，需警惕次日分化。")
        watchlist.append(
            f"观察{row.get('name')}次日能否在高位维持成交承接；若冲高回落并放量，成长风格可能进入分化。"
        )
    blowup_ratio = float((m4.get("pool_stats") or {}).get("blowup_ratio") or 0)
    if blowup_ratio >= 0.25:
        risks.append(f"炸板率达到{blowup_ratio:.1%}，高位接力容错率下降，追涨风险明显高于指数表面表现。")
        watchlist.append(
            f"观察炸板率能否由{blowup_ratio:.1%}回落至25%以下；若继续上升，应降低高位题材参与度。"
        )
    if stats.get("multi_board_count", 0) > 0:
        risks.append("若连板梯队次日出现断层，当前主线可能从加速转为快速轮动。")
        leaders = stats.get("leaders") or []
        leader_names = "、".join(str(row.get("name")) for row in leaders[:3] if row.get("name"))
        watchlist.append(
            f"观察连板梯队是否保持晋级"
            f"{f'，重点看{leader_names}' if leader_names else ''}；高标断层将削弱短线赚钱效应。"
        )
    if themes:
        watchlist.append(f"观察{'、'.join(themes)}能否继续获得成交额和首板数量支持，确认主线持续性。")

    return {
        "current": current,
        "benchmark": benchmark,
        "position_actions": position_actions,
        "watchlist": watchlist,
        "risks": risks,
    }


def _currency_name(currency: str) -> str:
    return {"CNY": "元", "USD": "美元", "HKD": "港元"}.get(currency, currency)
