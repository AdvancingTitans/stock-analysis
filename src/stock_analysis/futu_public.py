from __future__ import annotations

import html
import re
from datetime import datetime, timezone
from typing import Any

import requests

FUTU_BASE_URL = "https://ai-news-search.futunn.com"
USER_AGENT = "stock-analysis/4.15.0 (Skill)"

POSITIVE_CUES = (
    "增长",
    "上调",
    "回购",
    "突破",
    "强劲",
    "利好",
    "合作",
    "订单",
    "扩张",
    "beat",
    "growth",
    "expand",
    "surge",
    "buyback",
    "partnership",
    "demand",
)
NEGATIVE_CUES = (
    "下调",
    "限制",
    "调查",
    "诉讼",
    "亏损",
    "下滑",
    "裁员",
    "利空",
    "miss",
    "decline",
    "restriction",
    "lawsuit",
    "cut",
    "weak",
)
BULLISH_CUES = ("看多", "看涨", "反弹", "突破", "抄底", "买入", "强势", "上涨", "bull", "long")
BEARISH_CUES = ("看空", "看跌", "回调", "下跌", "割肉", "风险", "高估", "崩", "bear", "short")


def _session() -> requests.Session:
    session = requests.Session()
    session.trust_env = False
    session.headers.update({"User-Agent": USER_AGENT})
    return session


def _clean_text(value: Any) -> str:
    text = html.unescape(str(value or ""))
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _normalize_title(value: Any) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", _clean_text(value).lower())


def _target_patterns(symbol: str, name: str) -> tuple[str, ...]:
    raw = symbol.upper()
    base = raw.replace(".HK", "")
    values = {
        raw,
        base,
        f"{base}.US",
        f"{base}.HK",
        f"{base}.SH",
        f"{base}.SZ",
        str(name or "").strip(),
    }
    return tuple(value for value in values if value)


def filter_symbol_posts(
    posts: list[dict[str, Any]],
    *,
    symbol: str,
    name: str,
) -> list[dict[str, Any]]:
    patterns = _target_patterns(symbol, name)
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for post in posts:
        raw = f"{post.get('title') or ''} {post.get('desc') or ''}"
        raw_upper = html.unescape(raw).upper()
        if not any(pattern.upper() in raw_upper for pattern in patterns):
            continue
        text = _clean_text(raw)
        content = text
        for pattern in patterns:
            content = re.sub(re.escape(pattern), " ", content, flags=re.IGNORECASE)
        content = re.sub(r"[\W_]+", "", content)
        if len(content) < 8:
            continue
        key = _normalize_title(text)
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(
            {
                "text": text,
                "publish_time": str(post.get("publish_time") or ""),
                "url": str(post.get("url") or ""),
            }
        )
    return result


def _classify_text(text: str, positive: tuple[str, ...], negative: tuple[str, ...]) -> str:
    lowered = text.lower()
    positive_score = sum(cue in lowered for cue in positive)
    negative_score = sum(cue in lowered for cue in negative)
    if positive_score > negative_score:
        return "positive"
    if negative_score > positive_score:
        return "negative"
    return "neutral"


def classify_community_posts(posts: list[dict[str, Any]]) -> dict[str, Any]:
    if len(posts) < 3:
        return {
            "status": "insufficient",
            "label": "证据不足",
            "sample_count": len(posts),
            "bull_pct": None,
            "bear_pct": None,
            "neutral_pct": None,
        }
    labels = [_classify_text(str(post.get("text") or ""), BULLISH_CUES, BEARISH_CUES) for post in posts]
    total = len(labels)
    bull = labels.count("positive")
    bear = labels.count("negative")
    neutral = total - bull - bear
    bull_pct = bull / total * 100
    bear_pct = bear / total * 100
    if abs(bull_pct - bear_pct) < 15 and bull_pct >= 25 and bear_pct >= 25:
        label = "分歧"
    elif bull > bear and bull > neutral:
        label = "偏多"
    elif bear > bull and bear > neutral:
        label = "偏空"
    else:
        label = "中性"
    return {
        "status": "ok",
        "label": label,
        "sample_count": total,
        "bull_pct": round(bull_pct, 1),
        "bear_pct": round(bear_pct, 1),
        "neutral_pct": round(neutral / total * 100, 1),
    }


def _deduplicate_news(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in items:
        title = _clean_text(item.get("title"))
        key = _normalize_title(title)
        if not key or key in seen:
            continue
        seen.add(key)
        result.append({**item, "title": title})
    return result


def _filter_relevant_news(
    items: list[dict[str, Any]],
    *,
    symbol: str,
    name: str,
    market: str,
) -> list[dict[str, Any]]:
    targets = _target_patterns(symbol, name)
    relevant: list[dict[str, Any]] = []
    for item in items:
        raw_title = str(item.get("title") or "")
        title = _clean_text(raw_title)
        lowered = title.lower()
        matched = next((target for target in targets if target.lower() in lowered), "")
        if not matched:
            highlighted = re.search(r"<em>(.*?)</em>", raw_title, flags=re.IGNORECASE)
            matched = _clean_text(highlighted.group(1)) if highlighted else ""
        if not matched:
            continue
        target_index = lowered.find(matched.lower())
        if market == "a" and target_index > 8:
            continue
        prefix = lowered[max(0, target_index - 12) : target_index]
        if any(
            word in prefix
            for word in (
                "超过",
                "超越",
                "赶超",
                "反超",
                "取代",
                "逼近",
                "对标",
                "不及",
                "supplier to",
            )
        ):
            continue
        relevant.append(item)
    return relevant


def build_public_pulse(
    *,
    symbol: str,
    name: str,
    market: str,
    news_items: list[dict[str, Any]],
    feed_items: list[dict[str, Any]],
    news_status: str = "ok",
    feed_status: str = "ok",
) -> dict[str, Any]:
    news = _deduplicate_news(
        _filter_relevant_news(news_items, symbol=symbol, name=name, market=market)
    )
    news_labels = [_classify_text(item["title"], POSITIVE_CUES, NEGATIVE_CUES) for item in news]
    positive = news_labels.count("positive")
    negative = news_labels.count("negative")
    news_tone = "偏正面" if positive > negative else "偏负面" if negative > positive else "中性"
    event = news[0] if news else {}
    filtered_posts = filter_symbol_posts(feed_items, symbol=symbol, name=name)
    community = classify_community_posts(filtered_posts)
    return {
        "symbol": symbol,
        "name": name,
        "market": market,
        "news_tone": "数据暂不可用" if news_status != "ok" else news_tone if news else "暂无相关新闻",
        "news_count": len(news),
        "event_title": event.get("title") or "",
        "event_publish_time": _format_timestamp(event.get("publish_time")),
        "evidence_url": event.get("url") or "",
        "community_label": "数据暂不可用" if feed_status != "ok" else community["label"],
        "community_sample_count": community["sample_count"],
        "community_bull_pct": community.get("bull_pct"),
        "community_bear_pct": community.get("bear_pct"),
        "community_neutral_pct": community.get("neutral_pct"),
        "source": "Futu public gateway",
        "news_status": news_status,
        "community_status": feed_status,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def fetch_futu_public_pulse(symbol: str, name: str, market: str) -> dict[str, Any]:
    keyword = name if market == "a" and name else symbol
    lang = "en" if market == "us" else "zh-CN"
    session = _session()
    news_items: list[dict[str, Any]] = []
    feed_items: list[dict[str, Any]] = []
    news_status = "error"
    feed_status = "error"
    try:
        response = session.get(
            f"{FUTU_BASE_URL}/news_search",
            params={
                "keyword": keyword,
                "size": 10,
                "news_type": 1,
                "lang": lang,
                "sort_type": 2,
            },
            timeout=8,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("code") == 0:
            news_items = list(payload.get("data") or [])
            news_status = "ok"
    except Exception:
        pass
    try:
        response = session.get(
            f"{FUTU_BASE_URL}/stock_feed",
            params={"keyword": keyword, "size": 50},
            timeout=8,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("code") == 0:
            feed_items = list(payload.get("data") or [])
            feed_status = "ok"
    except Exception:
        pass
    return build_public_pulse(
        symbol=symbol,
        name=name,
        market=market,
        news_items=news_items,
        feed_items=feed_items,
        news_status=news_status,
        feed_status=feed_status,
    )


def _format_timestamp(value: Any) -> str:
    try:
        timestamp = float(value)
    except (TypeError, ValueError):
        return ""
    if timestamp > 1e12:
        timestamp /= 1000
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()
