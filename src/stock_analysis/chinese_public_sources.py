from __future__ import annotations

from typing import Any

FINANCIAL_NEWS_SOURCES = (
    {"id": "cailianshe", "name": "财联社", "kind": "news", "status": "registered"},
    {"id": "eastmoney", "name": "东方财富", "kind": "news", "status": "registered"},
    {"id": "sina_finance", "name": "新浪财经", "kind": "news", "status": "registered"},
    {"id": "tencent_finance", "name": "腾讯财经", "kind": "news", "status": "registered"},
    {"id": "futu", "name": "Futu", "kind": "news", "status": "registered"},
)

COMMUNITY_DISCUSSION_SOURCES = (
    {"id": "xueqiu", "name": "雪球", "kind": "community", "status": "registered"},
    {"id": "eastmoney_guba", "name": "东方财富股吧", "kind": "community", "status": "registered"},
    {"id": "weibo", "name": "微博", "kind": "community", "status": "registered"},
)

_SOURCE_ALIASES = {
    "财联社": "财联社",
    "cailianshe": "财联社",
    "cls": "财联社",
    "东方财富": "东方财富",
    "eastmoney": "东方财富",
    "东财": "东方财富",
    "新浪财经": "新浪财经",
    "sina_finance": "新浪财经",
    "sina": "新浪财经",
    "腾讯财经": "腾讯财经",
    "tencent_finance": "腾讯财经",
    "tencent": "腾讯财经",
    "futu": "Futu",
    "富途": "Futu",
    "Futu": "Futu",
    "雪球": "雪球",
    "xueqiu": "雪球",
    "东方财富股吧": "东方财富股吧",
    "股吧": "东方财富股吧",
    "eastmoney_guba": "东方财富股吧",
    "weibo": "微博",
    "微博": "微博",
}


def build_chinese_public_signal_summary(
    *,
    news_items: list[dict[str, Any]] | None = None,
    community_items: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    news = _normalize_items(news_items or [])
    community = _normalize_items(community_items or [])
    registered_news = [source["name"] for source in FINANCIAL_NEWS_SOURCES]
    registered_community = [source["name"] for source in COMMUNITY_DISCUSSION_SOURCES]
    source_status = {name: "registered_no_samples" for name in registered_news + registered_community}
    for item in news + community:
        source_status[item["source"]] = "available"
    return {
        "registered_news_sources": registered_news,
        "registered_community_sources": registered_community,
        "source_status": source_status,
        "news": _channel_summary(news),
        "community": _channel_summary(community),
    }


def _normalize_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized = []
    seen: set[tuple[str, str]] = set()
    for item in items:
        source = _normalize_source_name(item.get("source"))
        text = " ".join(str(item.get("title") or item.get("text") or item.get("content") or "").split())
        if not source or len(text) <= 4:
            continue
        key = (source, text.lower())
        if key in seen:
            continue
        seen.add(key)
        normalized.append({**item, "source": source, "text": text})
    return normalized


def _normalize_source_name(value: Any) -> str:
    raw = str(value or "").strip()
    return _SOURCE_ALIASES.get(raw, raw)


def _channel_summary(items: list[dict[str, Any]]) -> dict[str, Any]:
    source_distribution: dict[str, int] = {}
    sentiment_scores = []
    for item in items:
        source = str(item.get("source") or "unknown")
        source_distribution[source] = source_distribution.get(source, 0) + 1
        score = _safe_float(item.get("sentiment_score"))
        if score is not None:
            sentiment_scores.append(score)
    return {
        "sample_count": len(items),
        "source_distribution": source_distribution,
        "average_sentiment_score": round(sum(sentiment_scores) / len(sentiment_scores), 2)
        if sentiment_scores
        else 0.0,
    }


def _safe_float(value: Any) -> float | None:
    try:
        return None if value in (None, "") else float(value)
    except (TypeError, ValueError):
        return None
