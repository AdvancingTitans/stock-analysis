#!/usr/bin/env python3
"""
全球股市行情一键采集脚本 v2.1.0
用法: python aftermarket.py [--market a|hk|us|global] [YYYYMMDD]

--market a      : A股复盘（默认）
--market hk     : 港股复盘
--market us     : 美股复盘
--market global : 全球市场概览（美股+港股+A股指数）

不指定日期则 A股自动取最近交易日（周末回退到周五），港美股自动取最近交易日。
输出格式化的复盘文本到 stdout，可重定向到文件。

板块榜需要 camofox-browser 支持，通过环境变量传入：
  CAMOFOX_URL=http://localhost:9377
  CAMOFOX_USER_ID=xxx
  CAMOFOX_SESSION_KEY=yyy

如果不传，跳过板块榜部分。
"""

import json
import re
import sys
import os
import urllib.request
import time
import random
from datetime import datetime, timedelta
from functools import wraps
from collections import Counter

# ------------------------------------------------------------------
# 全局配置
# ------------------------------------------------------------------

# 请求频率控制
REQUEST_INTERVAL = 0.5          # 基础请求间隔（秒）
MAX_RETRIES = 3                 # 最大重试次数
INITIAL_BACKOFF = 2             # 初始退避秒数

# 数据质量阈值
VOLUME_THRESHOLD_INDEX = 1_000_000    # 指数成交量低于此值视为异常
VOLUME_THRESHOLD_STOCK = 1_000        # 个股成交量低于此值视为异常

# 市场配置
MARKET_CONFIG = {
    "us_market": {
        "tz": "America/New_York",
        "volume_range": [1_000_000, 10_000_000_000],
        "data_sources": ["Yahoo Finance"],
        "required_fields": ["Open", "High", "Low", "Close", "Volume"],
    },
    "hk_market": {
        "tz": "Asia/Hong_Kong",
        "volume_range": [1_000_000, 5_000_000_000],
        "data_sources": ["Yahoo Finance", "East Money"],
        "required_fields": ["Open", "High", "Low", "Close", "Volume"],
    },
    "cn_market": {
        "tz": "Asia/Shanghai",
        "volume_range": [10_000_000, 10_000_000_000],
        "data_sources": ["East Money", "Yahoo Finance"],
        "required_fields": ["Open", "High", "Low", "Close", "Volume"],
    },
    "eu_market": {
        "tz": "Europe/London",
        "volume_range": [1_000_000, 5_000_000_000],
        "data_sources": ["Yahoo Finance"],
        "required_fields": ["Open", "High", "Low", "Close", "Volume"],
    },
    "jp_market": {
        "tz": "Asia/Tokyo",
        "volume_range": [1_000_000, 5_000_000_000],
        "data_sources": ["Yahoo Finance"],
        "required_fields": ["Open", "High", "Low", "Close", "Volume"],
    },
}

# A股
INDEX_SECIDS = "1.000001,0.399001,0.399006,1.000688,0.399005,0.899050"
INDEX_FIELDS = "f2,f3,f4,f5,f6,f12,f14,f15,f16,f17,f18"

ZT_URL = (
    "https://push2ex.eastmoney.com/getTopicZTPool"
    "?ut=7eea3edcaed734bea9cbfc24409ed989"
    "&dpt=wz.ztzt&Pageindex=0&pagesize=200&sort=fbt:asc&date={date}"
)
DT_URL = (
    "https://push2ex.eastmoney.com/getTopicDTPool"
    "?ut=7eea3edcaed734bea9cbfc24409ed989"
    "&dpt=wz.ztzt&Pageindex=0&pagesize=200&sort=fbt:asc&date={date}"
)
ZB_URL = (
    "https://push2ex.eastmoney.com/getTopicZBPool"
    "?ut=7eea3edcaed734bea9cbfc24409ed989"
    "&dpt=wz.ztzt&Pageindex=0&pagesize=200&sort=fbt:asc&date={date}"
)

FFLOW_URL = (
    "https://push2.eastmoney.com/api/qt/stock/fflow/kline/get"
    "?secid=1.000001&fields1=f1,f2,f3,f7"
    "&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64,f65"
    "&klt=101&lmt=1&_={ts}"
)

INDEX_URL = (
    "https://push2.eastmoney.com/api/qt/ulist.np/get"
    "?fltt=2&secids={secids}&fields={fields}&_={ts}"
)

# Yahoo Finance
YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=5d"
YAHOO_QUOTE_URL = "https://query1.finance.yahoo.com/v6/finance/quote?symbols={symbols}"

# 富途
FUTU_NEWS_URL = "https://ai-news-search.futunn.com/news_search"
FUTU_FEED_URL = "https://ai-news-search.futunn.com/stock_feed"


# ------------------------------------------------------------------
# 通用工具函数
# ------------------------------------------------------------------

def retry_with_backoff(max_retries=MAX_RETRIES, initial_delay=INITIAL_BACKOFF):
    """指数退避 + 抖动重试装饰器"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            delay = initial_delay
            last_err = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_err = e
                    if attempt == max_retries - 1:
                        break
                    jitter = random.uniform(0.5, 1.5)
                    wait = delay * (2 ** attempt) * jitter
                    time.sleep(wait)
            return {"_error": f"{last_err} (retried {max_retries}x)"}
        return wrapper
    return decorator


def fmt_price(v):
    if v is None or v == "":
        return "-"
    try:
        return f"{float(v)/100:.2f}" if float(v) > 1000 else f"{float(v):.2f}"
    except (TypeError, ValueError):
        return str(v)


def fmt_pct(v):
    if v is None or v == "":
        return "-"
    try:
        return f"{float(v)/100:+.2f}%"
    except (TypeError, ValueError):
        return str(v)


def fmt_amount(v):
    if v is None or v == "":
        return "-"
    try:
        v = float(v)
        if v >= 1e8:
            return f"{v/1e8:.2f}亿"
        if v >= 1e4:
            return f"{v/1e4:.2f}万"
        return f"{v:.0f}"
    except (TypeError, ValueError):
        return str(v)


def fmt_volume(v):
    """格式化成交量，处理异常值"""
    if v is None or v == "":
        return "-"
    try:
        v = float(v)
        if v <= 0:
            return "-"
        if v >= 1e8:
            return f"{v/1e8:.2f}亿"
        if v >= 1e4:
            return f"{v/1e4:.2f}万"
        return f"{v:.0f}"
    except (TypeError, ValueError):
        return str(v)


def fmt_time(v):
    if v is None:
        return "-"
    s = str(int(v)).zfill(6)
    return f"{s[:2]}:{s[2:4]}:{s[4:6]}"


@retry_with_backoff(max_retries=MAX_RETRIES, initial_delay=INITIAL_BACKOFF)
def fetch_json(url, headers=None):
    """带重试的 JSON 获取"""
    default_headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Referer": "https://finance.yahoo.com/",
        "Accept": "application/json",
    }
    if headers:
        default_headers.update(headers)
    req = urllib.request.Request(url, headers=default_headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8", errors="ignore")
    except Exception as e:
        return {"_error": str(e)}

    raw = raw.strip()
    if raw.startswith("(") and raw.endswith(")"):
        raw = raw[1:-1]
    m = re.search(r"[({]", raw)
    if m:
        raw = raw[m.start():]
    if raw.endswith(");"):
        raw = raw[:-2] + ""
    if raw.endswith(");"):
        raw = raw[:-1]
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
        return {"_error": "JSON parse failed", "_raw": raw[:500]}


def nearest_trade_date(dt: datetime = None) -> str:
    if dt is None:
        dt = datetime.now()
    wd = dt.weekday()
    if wd == 5:
        dt -= timedelta(days=1)
    elif wd == 6:
        dt -= timedelta(days=2)
    return dt.strftime("%Y%m%d")


def detect_market_type(ticker_or_name):
    """检测市场类型"""
    t = str(ticker_or_name).upper()
    if t.endswith(".HK") or "恒生" in t or "HSI" in t or "HSCE" in t or "HSTECH" in t:
        return "hk_market"
    elif any(ex in t for ex in ["上证", "深证", "创业板", "科创板", "000001", "399001", "399006", "899050"]):
        return "cn_market"
    elif any(ex in t for ex in ["DAX", "CAC", "FTSE", "ESTX", "OMXS"]):
        return "eu_market"
    elif "NIKKEI" in t or t.endswith(".T") or t.endswith(".JP"):
        return "jp_market"
    else:
        return "us_market"


# ------------------------------------------------------------------
# 数据质量验证与清洗
# ------------------------------------------------------------------

def validate_and_clean_quote(data, ticker_type="index"):
    """验证并清洗行情数据，返回清洗后的数据 + 质量元数据"""
    cleaned = dict(data)
    notes = []
    quality_flags = []

    # 成交量验证
    volume = cleaned.get("regularMarketVolume") or cleaned.get("volume")
    if volume is not None:
        try:
            vol = float(volume)
            threshold = VOLUME_THRESHOLD_INDEX if ticker_type == "index" else VOLUME_THRESHOLD_STOCK
            if vol <= 0:
                cleaned["regularMarketVolume"] = None
                cleaned["volume"] = None
                notes.append("成交量为0，标记为缺失")
                quality_flags.append("volume_zero")
            elif vol < threshold:
                notes.append(f"成交量异常偏低({fmt_volume(vol)})，可能缺失")
                quality_flags.append("volume_anomaly")
        except (TypeError, ValueError):
            cleaned["regularMarketVolume"] = None
            cleaned["volume"] = None

    # 价格验证
    price_fields = ["regularMarketPrice", "previousClose", "open", "high", "low", "close"]
    for field in price_fields:
        val = cleaned.get(field)
        if val is not None:
            try:
                v = float(val)
                if v <= 0:
                    cleaned[field] = None
                    notes.append(f"{field}价格异常({v})已过滤")
                    quality_flags.append("price_anomaly")
            except (TypeError, ValueError):
                cleaned[field] = None

    # 数据完整性评分
    required = ["regularMarketPrice", "previousClose", "volume"]
    available = sum(1 for f in required if cleaned.get(f) is not None)
    completeness = (available / len(required)) * 100

    cleaned["_quality"] = {
        "completeness_score": round(completeness, 1),
        "notes": notes,
        "flags": quality_flags,
    }
    return cleaned


def calculate_completeness_score(data, required_fields):
    """计算数据完整性分数 0-100"""
    available = sum(1 for f in required_fields if data.get(f) is not None and data.get(f) != "-")
    return (available / len(required_fields)) * 100 if required_fields else 0


# ------------------------------------------------------------------
# A股数据获取
# ------------------------------------------------------------------

@retry_with_backoff(max_retries=MAX_RETRIES, initial_delay=INITIAL_BACKOFF)
def get_index(date_str: str):
    url = INDEX_URL.format(secids=INDEX_SECIDS, fields=INDEX_FIELDS, ts=datetime.now().timestamp())
    data = fetch_json(url, {"Referer": "https://quote.eastmoney.com/"})
    if "_error" in data:
        return data
    return data.get("data", {}).get("diff", [])


@retry_with_backoff(max_retries=MAX_RETRIES, initial_delay=INITIAL_BACKOFF)
def get_zt_pool(date_str: str):
    return fetch_json(ZT_URL.format(date=date_str), {"Referer": "https://quote.eastmoney.com/"})


@retry_with_backoff(max_retries=MAX_RETRIES, initial_delay=INITIAL_BACKOFF)
def get_dt_pool(date_str: str):
    return fetch_json(DT_URL.format(date=date_str), {"Referer": "https://quote.eastmoney.com/"})


@retry_with_backoff(max_retries=MAX_RETRIES, initial_delay=INITIAL_BACKOFF)
def get_zb_pool(date_str: str):
    return fetch_json(ZB_URL.format(date=date_str), {"Referer": "https://quote.eastmoney.com/"})


@retry_with_backoff(max_retries=MAX_RETRIES, initial_delay=INITIAL_BACKOFF)
def get_fund_flow():
    url = FFLOW_URL.format(ts=int(datetime.now().timestamp() * 1000))
    data = fetch_json(url, {"Referer": "https://quote.eastmoney.com/"})
    if "_error" in data:
        return data
    d = data.get("data", {})
    klines = d.get("klines", [])
    if not klines:
        return {}
    cols = "date,主力净流入,小单净流入,中单净流入,大单净流入,超大单净流入,主力净流入占比,小单净流入占比,中单净流入占比,大单净流入占比,超大单净流入占比,收盘价,涨跌幅,总成交额".split(",")
    vals = klines[0].split(",")
    return dict(zip(cols, vals))


# ------------------------------------------------------------------
# 港美股数据获取 (Yahoo Finance)
# ------------------------------------------------------------------

@retry_with_backoff(max_retries=MAX_RETRIES, initial_delay=INITIAL_BACKOFF)
def yahoo_quote(symbol: str):
    """获取单只股票实时行情，带数据清洗"""
    url = YAHOO_CHART_URL.format(symbol=symbol)
    data = fetch_json(url)
    if "_error" in data:
        return data

    result = data.get("chart", {}).get("result", [{}])[0]
    if not result:
        return {"_error": "No result", "symbol": symbol}

    meta = result.get("meta", {})
    timestamps = result.get("timestamp", [])
    quotes = result.get("indicators", {}).get("quote", [{}])[0]

    if not timestamps:
        return {"_error": "No data available", "symbol": symbol}

    # 取最新一条有效数据（从后往前找）
    idx = -1
    close_vals = quotes.get("close", [])
    if close_vals:
        for i in range(len(close_vals) - 1, -1, -1):
            if close_vals[i] is not None:
                idx = i
                break

    raw = {
        "symbol": symbol,
        "name": meta.get("shortName", meta.get("symbol", symbol)),
        "currency": meta.get("currency", "USD"),
        "exchange": meta.get("exchangeName", ""),
        "regularMarketPrice": meta.get("regularMarketPrice"),
        "previousClose": meta.get("previousClose"),
        "regularMarketVolume": meta.get("regularMarketVolume"),
        "fiftyTwoWeekHigh": meta.get("fiftyTwoWeekHigh"),
        "fiftyTwoWeekLow": meta.get("fiftyTwoWeekLow"),
        "open": quotes.get("open", [None])[idx] if quotes.get("open") else None,
        "high": quotes.get("high", [None])[idx] if quotes.get("high") else None,
        "low": quotes.get("low", [None])[idx] if quotes.get("low") else None,
        "close": quotes.get("close", [None])[idx] if quotes.get("close") else None,
        "volume": quotes.get("volume", [None])[idx] if quotes.get("volume") else None,
    }

    # 数据清洗
    mkt = detect_market_type(symbol)
    ticker_type = "index" if symbol.startswith("^") else "stock"
    return validate_and_clean_quote(raw, ticker_type)


@retry_with_backoff(max_retries=MAX_RETRIES, initial_delay=INITIAL_BACKOFF)
def yahoo_quotes_batch(symbols: list):
    """批量获取多只股票快照"""
    url = YAHOO_QUOTE_URL.format(symbols=",".join(symbols))
    data = fetch_json(url)
    if "_error" in data:
        return data
    results = data.get("quoteResponse", {}).get("result", [])
    cleaned = []
    for r in results:
        mkt = detect_market_type(r.get("symbol", ""))
        ticker_type = "index" if r.get("symbol", "").startswith("^") else "stock"
        cleaned.append(validate_and_clean_quote(r, ticker_type))
    return cleaned


# ------------------------------------------------------------------
# 富途数据获取
# ------------------------------------------------------------------

@retry_with_backoff(max_retries=MAX_RETRIES, initial_delay=INITIAL_BACKOFF)
def futu_news_search(keyword: str, size: int = 10, lang: str = "en", news_type: int = 1):
    params = urllib.parse.urlencode({
        "keyword": keyword,
        "size": size,
        "news_type": news_type,
        "lang": lang,
        "sort_type": 2,
    })
    url = f"{FUTU_NEWS_URL}?{params}"
    req = urllib.request.Request(url, headers={
        "User-Agent": "stock-analysis/2.1.0 (Skill)",
    })
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        return {"_error": str(e)}


@retry_with_backoff(max_retries=MAX_RETRIES, initial_delay=INITIAL_BACKOFF)
def futu_stock_feed(keyword: str, size: int = 30):
    params = urllib.parse.urlencode({
        "keyword": keyword,
        "size": size,
    })
    url = f"{FUTU_FEED_URL}?{params}"
    req = urllib.request.Request(url, headers={
        "User-Agent": "stock-analysis/2.1.0 (Skill)",
    })
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        return {"_error": str(e)}


# ------------------------------------------------------------------
# 板块榜（camofox）
# ------------------------------------------------------------------

def camofox_board_list(board_type: str = "industry"):
    base = os.environ.get("CAMOFOX_URL", "http://localhost:9377")
    user_id = os.environ.get("CAMOFOX_USER_ID", "")
    session_key = os.environ.get("CAMOFOX_SESSION_KEY", "")
    if not user_id or not session_key:
        return {"_skipped": "CAMOFOX_USER_ID / CAMOFOX_SESSION_KEY not set"}

    anchor = "industry_board" if board_type == "industry" else "concept_board"
    target_url = f"https://quote.eastmoney.com/center/gridlist.html#{anchor}"

    create_payload = json.dumps({
        "url": target_url,
        "userId": user_id,
        "sessionKey": session_key,
    }).encode()
    req = urllib.request.Request(
        f"{base}/tabs",
        data=create_payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            tab_info = json.loads(resp.read().decode())
    except Exception as e:
        return {"_error": f"create tab failed: {e}"}

    tab_id = tab_info.get("id")
    if not tab_id:
        return {"_error": "no tab id returned", "_raw": tab_info}

    wait_payload = json.dumps({"state": "networkidle", "userId": user_id, "sessionKey": session_key}).encode()
    req2 = urllib.request.Request(
        f"{base}/tabs/{tab_id}/wait",
        data=wait_payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        urllib.request.urlopen(req2, timeout=15)
    except Exception:
        pass

    snap_url = f"{base}/tabs/{tab_id}/snapshot?userId={user_id}&format=markdown"
    req3 = urllib.request.Request(snap_url, method="GET")
    try:
        with urllib.request.urlopen(req3, timeout=15) as resp:
            md = resp.read().decode("utf-8", errors="ignore")
    except Exception as e:
        return {"_error": f"snapshot failed: {e}"}

    rows = []
    for line in md.splitlines():
        line = line.strip()
        if line.startswith('row "'):
            content = line[5:].rstrip('"')
            parts = re.split(r"\s{2,}", content)
            if len(parts) >= 4:
                rows.append(parts)
    return {"board_type": board_type, "rows": rows, "count": len(rows)}


# ------------------------------------------------------------------
# 输出格式化 - A股
# ------------------------------------------------------------------

def print_index(data):
    print("## 指数表现\n")
    print(f"{'指数':<10} {'收盘':>10} {'涨跌':>10} {'涨跌幅':>10} {'成交额':>12}")
    print("-" * 60)
    name_map = {
        "000001": "上证指数",
        "399001": "深证成指",
        "399006": "创业板指",
        "000688": "科创50",
        "399005": "中小板指",
        "899050": "北证50",
    }
    for item in data:
        code = item.get("f12", "")
        name = name_map.get(code, item.get("f14", code))
        close_p = fmt_price(item.get("f2"))
        change = fmt_price(item.get("f4"))
        pct = fmt_pct(item.get("f3"))
        amount = fmt_amount(item.get("f6"))
        print(f"{name:<10} {close_p:>10} {change:>10} {pct:>10} {amount:>12}")
    print()


def print_zt_analysis(zt_data, dt_data, zb_data):
    zt_pool = zt_data.get("data", {}).get("pool", []) if "_error" not in zt_data else []
    dt_pool = dt_data.get("data", {}).get("pool", []) if "_error" not in dt_data else []
    zb_pool = zb_data.get("data", {}).get("pool", []) if "_error" not in zb_data else []
    zt_total = zt_data.get("data", {}).get("tc", len(zt_pool)) if "_error" not in zt_data else 0
    dt_total = dt_data.get("data", {}).get("tc", len(dt_pool)) if "_error" not in dt_data else 0
    zb_total = zb_data.get("data", {}).get("tc", len(zb_pool)) if "_error" not in zb_data else 0

    print("## 涨跌停与连板梯队\n")
    print(f"涨停: {zt_total} 只 | 跌停: {dt_total} 只 | 炸板: {zb_total} 只")
    if zt_total + zb_total > 0:
        zb_rate = zb_total / (zt_total + zb_total) * 100
        print(f"炸板率: {zb_rate:.1f}% {'(高)' if zb_rate > 40 else ''}")
    print()

    ladders = {}
    for s in zt_pool:
        days = s.get("zttj", {}).get("days", 1)
        if days >= 2:
            ladders.setdefault(days, []).append(s)

    if ladders:
        print("连板梯队:")
        for d in sorted(ladders.keys(), reverse=True):
            stocks = ladders[d]
            names = ", ".join([f"{s['n']}({s['c']})" for s in stocks[:5]])
            print(f"  {d}板 ({len(stocks)}只): {names}")
        max_days = max(ladders.keys())
        print(f"最高连板: {max_days}板")
    else:
        print("连板梯队: 无 ≥2 板")

    fbt_times = [s.get("fbt", 0) for s in zt_pool if s.get("fbt")]
    early = sum(1 for t in fbt_times if t <= 100000)
    mid = sum(1 for t in fbt_times if 100000 < t <= 130000)
    late = sum(1 for t in fbt_times if t > 130000)
    print(f"\n封板时间分布: 早盘(≤10:00) {early}只 / 上午 {mid}只 / 下午 {late}只")

    hy_counter = Counter([s.get("hybk", "未知") for s in zt_pool])
    print(f"\n涨停行业 TOP5:")
    for hy, cnt in hy_counter.most_common(5):
        print(f"  {hy}: {cnt}只")
    print()


def print_fund_flow(flow_data):
    if not flow_data or "_error" in flow_data:
        return
    print("## 资金流向（上证指数口径）\n")
    print(f"  主力净流入: {fmt_amount(flow_data.get('主力净流入'))}")
    print(f"  超大单:     {fmt_amount(flow_data.get('超大单净流入'))}")
    print(f"  大单:       {fmt_amount(flow_data.get('大单净流入'))}")
    print(f"  中单:       {fmt_amount(flow_data.get('中单净流入'))}")
    print(f"  小单:       {fmt_amount(flow_data.get('小单净流入'))}")
    print()


def print_boards(board_data, title):
    if "_skipped" in board_data or "_error" in board_data:
        return
    rows = board_data.get("rows", [])
    if not rows:
        return
    print(f"## {title}（前15）\n")
    print(f"{'排名':<4} {'板块':<12} {'涨跌幅':>8}")
    print("-" * 30)
    for i, r in enumerate(rows[:15], 1):
        pct_str = "-"
        for cell in reversed(r):
            if "%" in cell:
                pct_str = cell.strip()
                break
        name = r[1] if len(r) > 1 else r[0]
        print(f"{i:<4} {name:<12} {pct_str:>8}")
    print()


def print_sentiment_summary(zt_data, dt_data, zb_data, flow_data):
    zt_total = zt_data.get("data", {}).get("tc", 0) if "_error" not in zt_data else 0
    dt_total = dt_data.get("data", {}).get("tc", 0) if "_error" not in dt_data else 0
    zb_total = zb_data.get("data", {}).get("tc", 0) if "_error" not in zb_data else 0

    print("## 情绪定性\n")
    if zt_total > 80 and dt_total < 10:
        print("🔥 强势：涨停>80，跌停<10，情绪高涨")
    elif zt_total > 70 and dt_total < 15:
        print("📈 偏强：涨停>70，结构性热点行情")
    elif zt_total >= 40 and dt_total < 20:
        print("😐 中性：结构性行情，跌多涨少或分化")
    elif dt_total > 20 or (zt_total + zb_total > 0 and zb_total / (zt_total + zb_total) > 0.4):
        print("❄️ 偏弱：跌停>20 或炸板率高，退潮/调整")
    else:
        print("⚠️ 低迷：涨停<40，情绪冷淡")
    print()


# ------------------------------------------------------------------
# 输出格式化 - 港美股（含数据质量提示）
# ------------------------------------------------------------------

def print_global_indices(indices_data, market_name: str):
    print(f"## {market_name} 大盘指数\n")
    print(f"{'指数':<15} {'当前价':>12} {'涨跌幅':>10} {'成交量':>14} {'数据质量':>8}")
    print("-" * 70)
    for item in indices_data:
        if isinstance(item, dict) and "_error" in item:
            continue
        name = item.get("shortName") or item.get("name") or item.get("symbol", "")
        price = item.get("regularMarketPrice", "-")
        change = item.get("regularMarketChangePercent", "-")
        volume = item.get("regularMarketVolume") or item.get("volume")
        quality = item.get("_quality", {})
        completeness = quality.get("completeness_score", 100)

        if isinstance(change, (int, float)):
            change_str = f"{change:+.2f}%"
        else:
            change_str = "-"

        vol_str = fmt_volume(volume)
        # 如果成交量异常，标记
        vol_note = ""
        if quality.get("flags") and any(f in quality["flags"] for f in ["volume_zero", "volume_anomaly"]):
            vol_note = "*"

        quality_str = f"{completeness:.0f}%"
        print(f"{name:<15} {str(price):>12} {change_str:>10} {vol_str + vol_note:>14} {quality_str:>8}")
    print()


def print_global_stock(quote_data):
    if "_error" in quote_data:
        return
    symbol = quote_data.get("symbol", "")
    name = quote_data.get("name", symbol)
    currency = quote_data.get("currency", "USD")
    quality = quote_data.get("_quality", {})
    notes = quality.get("notes", [])

    print(f"## {name} ({symbol})\n")
    print(f"  当前价: {quote_data.get('regularMarketPrice', '-')}")
    print(f"  昨收:   {quote_data.get('previousClose', '-')}")
    print(f"  开盘:   {quote_data.get('open', '-')}")
    print(f"  最高:   {quote_data.get('high', '-')}")
    print(f"  最低:   {quote_data.get('low', '-')}")

    vol = quote_data.get("volume") or quote_data.get("regularMarketVolume")
    vol_str = fmt_volume(vol)
    if quality.get("flags") and any(f in quality["flags"] for f in ["volume_zero", "volume_anomaly"]):
        vol_str += " *"
    print(f"  成交量: {vol_str}")

    print(f"  货币:   {currency}")
    print(f"  52周高: {quote_data.get('fiftyTwoWeekHigh', '-')}")
    print(f"  52周低: {quote_data.get('fiftyTwoWeekLow', '-')}")

    prev = quote_data.get("previousClose")
    curr = quote_data.get("regularMarketPrice")
    if prev and curr:
        change = curr - prev
        pct = change / prev * 100
        print(f"  涨跌:   {change:+.2f} ({pct:+.2f}%)")

    if notes:
        print(f"  ⚠️ 数据质量: {', '.join(notes)}")
    print()


def print_futu_news(news_data, keyword: str):
    if "_error" in news_data:
        return
    data = news_data.get("data", [])
    if not data:
        return
    print(f"## {keyword} 新闻（前5条）\n")
    for i, item in enumerate(data[:5], 1):
        ts = item.get("publish_time", 0)
        dt_str = datetime.fromtimestamp(ts).strftime("%m-%d %H:%M") if ts else ""
        print(f"{i}. [{dt_str}] {item.get('title', '')}")
        print(f"   {item.get('url', '')}")
    print()


def print_global_sentiment(indices_data):
    print("## 情绪定性\n")
    bullish = 0
    bearish = 0
    valid_count = 0
    for item in indices_data:
        if isinstance(item, dict) and "_error" not in item:
            change = item.get("regularMarketChangePercent", 0)
            if isinstance(change, (int, float)):
                valid_count += 1
                if change > 1:
                    bullish += 1
                elif change < -1:
                    bearish += 1

    if valid_count > 0:
        if bullish >= valid_count * 0.6:
            print("🔥 强势：大盘指数多数大涨，情绪高涨")
        elif bearish >= valid_count * 0.6:
            print("❄️ 弱势：大盘指数多数大跌，情绪低迷")
        elif bullish > bearish:
            print("📈 偏强：大盘指数涨多跌少，情绪偏活跃")
        elif bearish > bullish:
            print("⚠️ 偏弱：大盘指数跌多涨少，情绪偏谨慎")
        else:
            print("😐 中性：大盘指数分化，情绪平衡")
    print()


def print_data_quality_report(results):
    """打印数据质量报告"""
    warnings = []
    recommendations = []
    total = len(results)
    if total == 0:
        return

    avg_score = 0
    for r in results:
        q = r.get("_quality", {})
        score = q.get("completeness_score", 100)
        avg_score += score
        if score < 80:
            name = r.get("shortName") or r.get("name") or r.get("symbol", "")
            warnings.append(f"{name}: 数据完整性较低 ({score:.0f}%)")
        for note in q.get("notes", []):
            name = r.get("shortName") or r.get("name") or r.get("symbol", "")
            if "成交量" in note:
                warnings.append(f"{name}: {note}")

    avg_score = avg_score / total

    if avg_score < 90:
        recommendations.append("数据完整性一般，建议检查网络连接或稍后重试")
    if any("异常" in str(w) for w in warnings):
        recommendations.append("部分成交量数据异常，已标记 * ，仅供参考")

    if warnings or recommendations:
        print("\n" + "=" * 60)
        print("📊 数据质量报告")
        print(f"  平均完整度: {avg_score:.0f}%")
        if warnings:
            print(f"\n  ⚠️ 警告 ({len(warnings)}条):")
            for w in warnings[:8]:
                print(f"    - {w}")
            if len(warnings) > 8:
                print(f"    ... 还有 {len(warnings) - 8} 条")
        if recommendations:
            print(f"\n  💡 建议:")
            for rec in recommendations:
                print(f"    - {rec}")
        print("=" * 60)


# ------------------------------------------------------------------
# A股复盘
# ------------------------------------------------------------------

def run_a_share(date_str: str):
    display_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
    print(f"# A 股盘后复盘（{display_date}）\n")
    print(f"数据来源: 东方财富免登录 API | 采集时间: {datetime.now().strftime('%H:%M:%S')}\n")
    print("=" * 60 + "\n")

    index_data = get_index(date_str)
    if not (isinstance(index_data, dict) and "_error" in index_data):
        print_index(index_data)

    zt = get_zt_pool(date_str)
    dt = get_dt_pool(date_str)
    zb = get_zb_pool(date_str)
    print_zt_analysis(zt, dt, zb)

    flow = get_fund_flow()
    print_fund_flow(flow)

    print_sentiment_summary(zt, dt, zb, flow)

    industry = camofox_board_list("industry")
    concept = camofox_board_list("concept")
    print_boards(industry, "行业板块涨幅")
    print_boards(concept, "概念板块涨幅")

    print("=" * 60)
    print("\n*输出结束。如需板块榜，请设置 CAMOFOX_USER_ID + CAMOFOX_SESSION_KEY 环境变量。")


# ------------------------------------------------------------------
# 美股复盘
# ------------------------------------------------------------------

def run_us_market():
    print("# 美股市场复盘\n")
    print(f"数据来源: Yahoo Finance API | 采集时间: {datetime.now().strftime('%H:%M:%S')}\n")
    print("=" * 60 + "\n")

    indices_symbols = ["^GSPC", "^IXIC", "^DJI", "^VIX"]
    indices = yahoo_quotes_batch(indices_symbols)
    if "_error" not in indices:
        print_global_indices(indices, "美股")

    hot_stocks = ["AAPL", "TSLA", "NVDA", "MSFT", "AMZN", "GOOGL", "META", "BABA", "PDD", "JD"]
    print("## 重点个股行情\n")
    for sym in hot_stocks:
        time.sleep(REQUEST_INTERVAL)
        quote = yahoo_quote(sym)
        if "_error" not in quote:
            print_global_stock(quote)

    for sym in ["AAPL", "TSLA", "NVDA"]:
        time.sleep(REQUEST_INTERVAL)
        news = futu_news_search(sym, size=5, lang="en")
        print_futu_news(news, sym)

    if "_error" not in indices:
        print_global_sentiment(indices)

    # 数据质量报告
    if "_error" not in indices:
        all_results = indices + []
        for sym in hot_stocks:
            pass  # 不重复请求，用已获取的 indices 结果
        print_data_quality_report(indices)

    print("=" * 60)
    print("\n*输出结束。")


# ------------------------------------------------------------------
# 港股复盘
# ------------------------------------------------------------------

def run_hk_market():
    print("# 港股市场复盘\n")
    print(f"数据来源: Yahoo Finance API | 采集时间: {datetime.now().strftime('%H:%M:%S')}\n")
    print("=" * 60 + "\n")

    indices_symbols = ["^HSI", "^HSCE", "^HSTECH"]
    indices = yahoo_quotes_batch(indices_symbols)
    if "_error" not in indices:
        print_global_indices(indices, "港股")

    hot_stocks = ["0700.HK", "9988.HK", "3690.HK", "9618.HK", "1299.HK", "2318.HK", "0005.HK", "0388.HK"]
    print("## 重点个股行情\n")
    for sym in hot_stocks:
        time.sleep(REQUEST_INTERVAL)
        quote = yahoo_quote(sym)
        if "_error" not in quote:
            print_global_stock(quote)

    for sym in ["0700", "9988", "3690"]:
        time.sleep(REQUEST_INTERVAL)
        news = futu_news_search(sym, size=5, lang="zh-CN")
        print_futu_news(news, sym)

    if "_error" not in indices:
        print_global_sentiment(indices)

    if "_error" not in indices:
        print_data_quality_report(indices)

    print("=" * 60)
    print("\n*输出结束。")


# ------------------------------------------------------------------
# 全球市场概览
# ------------------------------------------------------------------

def run_global_market():
    print("# 全球市场概览\n")
    print(f"数据来源: Yahoo Finance API | 采集时间: {datetime.now().strftime('%H:%M:%S')}\n")
    print("=" * 60 + "\n")

    # 美股
    us_indices = ["^GSPC", "^IXIC", "^DJI", "^VIX"]
    us_data = yahoo_quotes_batch(us_indices)
    if "_error" not in us_data:
        print_global_indices(us_data, "美股")
        time.sleep(REQUEST_INTERVAL)

    # 港股
    hk_indices = ["^HSI", "^HSCE", "^HSTECH"]
    hk_data = yahoo_quotes_batch(hk_indices)
    if "_error" not in hk_data:
        print_global_indices(hk_data, "港股")
        time.sleep(REQUEST_INTERVAL)

    # A股指数
    a_index = get_index(nearest_trade_date())
    if not (isinstance(a_index, dict) and "_error" in a_index):
        print("## A股指数表现\n")
        print(f"{'指数':<10} {'收盘':>10} {'涨跌':>10} {'涨跌幅':>10} {'成交额':>12}")
        print("-" * 60)
        name_map = {
            "000001": "上证指数",
            "399001": "深证成指",
            "399006": "创业板指",
            "000688": "科创50",
            "399005": "中小板指",
            "899050": "北证50",
        }
        for item in a_index:
            code = item.get("f12", "")
            name = name_map.get(code, item.get("f14", code))
            close_p = fmt_price(item.get("f2"))
            change = fmt_price(item.get("f4"))
            pct = fmt_pct(item.get("f3"))
            amount = fmt_amount(item.get("f6"))
            print(f"{name:<10} {close_p:>10} {change:>10} {pct:>10} {amount:>12}")
        print()

    # 数据质量报告
    all_indices = []
    if "_error" not in us_data:
        all_indices.extend(us_data)
    if "_error" not in hk_data:
        all_indices.extend(hk_data)
    if all_indices:
        print_data_quality_report(all_indices)

    print("=" * 60)
    print("\n*输出结束。")


# ------------------------------------------------------------------
# main
# ------------------------------------------------------------------

def main():
    market = "a"
    date_str = None

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--market" and i + 1 < len(args):
            market = args[i + 1].lower()
            i += 2
        elif args[i].startswith("--market="):
            market = args[i].split("=", 1)[1].lower()
            i += 1
        elif re.fullmatch(r"\d{8}", args[i]):
            date_str = args[i]
            i += 1
        else:
            i += 1

    if market not in ("a", "hk", "us", "global"):
        print("错误: --market 参数必须是 a、hk、us 或 global", file=sys.stderr)
        sys.exit(1)

    if market == "a":
        if date_str:
            run_a_share(date_str)
        else:
            run_a_share(nearest_trade_date())
    elif market == "us":
        run_us_market()
    elif market == "hk":
        run_hk_market()
    elif market == "global":
        run_global_market()


if __name__ == "__main__":
    main()
