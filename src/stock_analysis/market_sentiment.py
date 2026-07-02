from __future__ import annotations

import re
from typing import Any

from . import market_core
from .futu_public import NEGATIVE_CUES, POSITIVE_CUES

MARKET_NEWS_KEYWORDS = (
    "A股",
    "沪指",
    "大盘",
    "创业板",
    "北向资金",
    "涨停",
    "深成指",
)

MARKET_COMMUNITY_KEYWORDS = (
    "A股",
    "大盘",
    "沪指",
    "创业板",
)


def _title_sentiment(title: str) -> float:
    text = title.lower()
    positive = sum(1 for cue in POSITIVE_CUES if cue.lower() in text)
    negative = sum(1 for cue in NEGATIVE_CUES if cue.lower() in text)
    if positive == negative == 0:
        return 0.0
    return round((positive - negative) / max(positive + negative, 1), 2)


def _normalize_news_item(item: dict[str, Any], *, trade_date: str) -> dict[str, Any] | None:
    title = " ".join(str(item.get("title") or "").split())
    if len(title) <= 6:
        return None
    source = str(item.get("source") or "unknown")
    publish_date = market_core._news_date(item.get("publish_time"))
    return {
        "title": title,
        "source": source,
        "url": item.get("url") or "",
        "publish_time": item.get("publish_time") or 0,
        "publish_date": publish_date,
        "urgency": "high" if any(token in title for token in ("突发", "重磅", "预警", "暴跌", "大涨")) else "medium",
        "relevance_score": 0.85 if publish_date == trade_date else 0.65,
        "sentiment_score": _title_sentiment(title),
    }


def _dedupe_news(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unique: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in items:
        key = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", str(item.get("title") or "").lower())
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def fetch_market_news_items(trade_date: str, *, size_per_keyword: int = 5) -> list[dict[str, Any]]:
    collected: list[dict[str, Any]] = []
    for keyword in MARKET_NEWS_KEYWORDS:
        payload = market_core.combined_news_search(
            keyword,
            size=size_per_keyword,
            lang="zh-CN",
            date_str=trade_date,
        )
        for raw in payload.get("data") or []:
            normalized = _normalize_news_item(raw, trade_date=trade_date)
            if normalized:
                collected.append(normalized)

    if len(collected) < 3:
        for keyword in MARKET_NEWS_KEYWORDS[:3]:
            payload = market_core.combined_news_search(
                keyword,
                size=size_per_keyword,
                lang="zh-CN",
                date_str=None,
            )
            for raw in payload.get("data") or []:
                normalized = _normalize_news_item(raw, trade_date=trade_date)
                if normalized:
                    normalized["relevance_score"] = 0.55
                    collected.append(normalized)

    return _dedupe_news(collected)[:30]


def fetch_market_community_items(trade_date: str, *, size_per_keyword: int = 3) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for keyword in MARKET_COMMUNITY_KEYWORDS:
        feed = market_core._normalize_futu_feed(
            market_core.futu_stock_feed(keyword, size=size_per_keyword * 3),
            size=size_per_keyword,
            keyword=keyword,
            aliases=[keyword],
        )
        for raw in feed.get("data") or []:
            text = " ".join(str(raw.get("title") or raw.get("content") or "").split())
            if len(text) <= 8:
                continue
            items.append(
                {
                    "source": "Futu",
                    "text": text,
                    "url": raw.get("url") or "",
                    "sentiment_score": _title_sentiment(text),
                    "publish_date": market_core._news_date(raw.get("publish_time")),
                }
            )
    return _dedupe_news(
        [
            {**item, "title": item["text"]}
            for item in items
            if not item.get("publish_date") or item.get("publish_date") == trade_date
        ]
    )[:20]


def build_market_public_pulse(news_items: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not news_items:
        return None
    scores = [float(item.get("sentiment_score") or 0.0) for item in news_items]
    average = sum(scores) / len(scores)
    if average > 0.15:
        tone = "偏多"
    elif average < -0.15:
        tone = "偏空"
    else:
        tone = "中性"
    top = max(news_items, key=lambda item: abs(float(item.get("sentiment_score") or 0.0)))
    return {
        "symbol": "MARKET",
        "name": "A股市场",
        "news_tone": tone,
        "news_count": len(news_items),
        "community_label": "证据不足",
        "community_sample_count": 0,
        "event_title": top.get("title") or "",
        "evidence_url": top.get("url") or "",
        "generated_at": trade_date_iso(news_items),
        "scope": "market_level",
    }


def trade_date_iso(news_items: list[dict[str, Any]]) -> str:
    for item in news_items:
        publish_date = str(item.get("publish_date") or "")
        if publish_date:
            return f"{publish_date[:4]}-{publish_date[4:6]}-{publish_date[6:8]}"
    return ""


def fetch_market_sentiment(trade_date: str) -> dict[str, Any]:
    news_items = fetch_market_news_items(trade_date)
    community_items = fetch_market_community_items(trade_date)
    market_pulse = build_market_public_pulse(news_items)
    return {
        "chinese_news_items": news_items,
        "chinese_community_items": community_items,
        "market_public_pulse": market_pulse,
        "source_events": [
            {
                "module": "market_sentiment",
                "source": "combined_news_search",
                "news_count": len(news_items),
                "community_count": len(community_items),
                "trade_date": trade_date,
            }
        ],
    }