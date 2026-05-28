#!/usr/bin/env python3
"""
全球股市行情一键采集脚本 v3.1.1
用法: python aftermarket.py [--market a|hk|us|global] [YYYYMMDD] [--no-cache]

--market a      : A股复盘（默认）
--market hk     : 港股复盘
--market us     : 美股复盘
--market global : 全球市场概览（美股+港股+A股指数）
--no-cache      : 强制刷新缓存

三层获取策略：缓存 → 稳定 API → 浏览器降级
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import random
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from functools import wraps
from collections import Counter
from pathlib import Path
from typing import Optional, List, Dict, Any, Callable

# ------------------------------------------------------------------
# 配置
# ------------------------------------------------------------------

REQUEST_INTERVAL = 1.0            # 东财免登录不限流，1 秒间隔足够
MAX_RETRIES = 2                   # 最大重试次数
INITIAL_BACKOFF = 2.0             # 初始退避秒数

# 缓存有效期（秒）：盘中实时数据缓存 5 分钟，盘后数据可设更长
CACHE_TTL_SECONDS = 300

# 数据质量阈值
VOLUME_THRESHOLD_INDEX = 1_000_000
VOLUME_THRESHOLD_STOCK = 1_000

# 缓存目录
CACHE_DIR = Path.home() / ".cache" / "stock-analysis"

# 全局开关：是否强制忽略缓存
NO_CACHE = False

# A股配置
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

# 东财 clist — 美股/港股/指数统一接口（免登录、不限流）
EM_CLIST_URL = (
    "https://push2.eastmoney.com/api/qt/clist/get"
    "?pn=1&pz={pz}&fid=f3&fs={fs}&fields={fields}&fltt=2&_={ts}"
)
EM_CLIST_FIELDS = "f12,f14,f2,f3,f4,f5,f6,f15,f16,f17,f18"

# 东财市场筛选器
EM_FS = {
    "us_index":   "i:100.SPX,i:100.NDX",
    "us_stock":   "m:105,m:106,m:107",
    "hk_index":   "i:100.HSI,i:100.HSCE,i:100.HSTECH",
    "hk_stock":   "m:128",
}

# 东财代码映射（Yahoo symbol → 东财 f12）
EM_CODE_MAP = {
    "^GSPC": "SPX",
    "^IXIC": "NDX",
    "^HSI":  "HSI",
    "^HSCE": "HSCE",
    "HSTECH.HK": "HSTECH",
}

# 指数中文名
INDEX_NAME_MAP = {
    "^GSPC": "标普 500",
    "^IXIC": "纳斯达克",
    "^HSI":  "恒生指数",
    "^HSCE": "国企指数",
    "HSTECH.HK": "恒生科技指数",
}

# 富途
FUTU_NEWS_URL = "https://ai-news-search.futunn.com/news_search"
FUTU_FEED_URL = "https://ai-news-search.futunn.com/stock_feed"

# 诊断记录
DIAGNOSTICS: List[str] = []


def diag(msg: str) -> None:
    DIAGNOSTICS.append(msg)


# ------------------------------------------------------------------
# 统一数据结构
# ------------------------------------------------------------------

@dataclass
class QuoteData:
    symbol: str
    name: str = ""
    market: str = "us_market"
    date: str = ""
    price: Optional[float] = None
    prev_close: Optional[float] = None
    change: Optional[float] = None
    change_pct: Optional[float] = None
    open_price: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    volume: Optional[int] = None
    currency: str = "USD"
    source: str = ""
    quality_flags: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    completeness: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ------------------------------------------------------------------
# 缓存层
# ------------------------------------------------------------------

def _cache_key(symbol: str, date_str: str, source: str) -> str:
    safe = re.sub(r"[^\w\-\.]", "_", symbol)
    return f"{source}_{safe}_{date_str}.json"


def _cache_path(symbol: str, date_str: str, source: str) -> Path:
    d = CACHE_DIR / date_str
    d.mkdir(parents=True, exist_ok=True)
    return d / _cache_key(symbol, date_str, source)


def cache_load(symbol: str, date_str: str, source: str, ttl: int = CACHE_TTL_SECONDS) -> Optional[Dict[str, Any]]:
    if NO_CACHE:
        return None
    p = _cache_path(symbol, date_str, source)
    if p.exists():
        try:
            mtime = p.stat().st_mtime
            if time.time() - mtime > ttl:
                return None  # 缓存过期
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return None


def cache_save(symbol: str, date_str: str, source: str, data: Dict[str, Any]) -> None:
    p = _cache_path(symbol, date_str, source)
    try:
        with open(p, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, default=str)
    except Exception:
        pass


def cache_clear_old(days: int = 7) -> None:
    cutoff = datetime.now() - timedelta(days=days)
    if not CACHE_DIR.exists():
        return
    for d in CACHE_DIR.iterdir():
        if d.is_dir():
            try:
                dt = datetime.strptime(d.name, "%Y%m%d")
                if dt < cutoff:
                    import shutil
                    shutil.rmtree(d)
            except ValueError:
                pass


# ------------------------------------------------------------------
# 重试装饰器（只重试可恢复的错误）
# ------------------------------------------------------------------

def retry_on_recoverable(max_retries: int = MAX_RETRIES, initial_delay: float = INITIAL_BACKOFF):
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            delay = initial_delay
            last_err = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except urllib.error.HTTPError as e:
                    last_err = e
                    if e.code in (404, 410):
                        diag(f"{func.__name__}: HTTP {e.code}, no retry")
                        return {"_error": f"HTTP {e.code}"}
                    if e.code not in (429, 403, 500, 502, 503, 504):
                        return {"_error": f"HTTP {e.code}"}
                    if attempt == max_retries:
                        break
                except (urllib.error.URLError, TimeoutError) as e:
                    last_err = e
                    if attempt == max_retries:
                        break
                except Exception as e:
                    return {"_error": str(e)}

                jitter = random.uniform(0.5, 1.5)
                wait = delay * (2 ** attempt) * jitter
                time.sleep(wait)

            return {"_error": f"{last_err} (retried {max_retries}x)"}
        return wrapper
    return decorator


# ------------------------------------------------------------------
# 格式化工具
# ------------------------------------------------------------------

def fmt_price(v) -> str:
    if v is None or v == "":
        return "-"
    try:
        return f"{float(v):.2f}"
    except (TypeError, ValueError):
        return str(v)


def fmt_pct(v) -> str:
    if v is None or v == "":
        return "-"
    try:
        return f"{float(v):+.2f}%"
    except (TypeError, ValueError):
        return str(v)


def fmt_amount(v) -> str:
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


def fmt_volume(v) -> str:
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


# ------------------------------------------------------------------
# HTTP 工具
# ------------------------------------------------------------------

def _fetch_raw(url: str, headers: Optional[Dict[str, str]] = None, timeout: int = 15) -> str:
    default_headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json",
    }
    if headers:
        default_headers.update(headers)
    req = urllib.request.Request(url, headers=default_headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def fetch_json(url: str, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    try:
        raw = _fetch_raw(url, headers)
    except Exception as e:
        return {"_error": str(e)}

    raw = raw.strip()
    if raw.startswith("(") and raw.endswith(")"):
        raw = raw[1:-1]
    m = re.search(r"[({]", raw)
    if m:
        raw = raw[m.start():]
    if raw.endswith(");"):
        raw = raw[:-2]
    if raw.endswith(");"):
        raw = raw[:-1]
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        m2 = re.search(r"\{.*\}", raw, re.DOTALL)
        if m2:
            try:
                return json.loads(m2.group(0))
            except json.JSONDecodeError:
                pass
        return {"_error": "JSON parse failed", "_raw": raw[:500]}


# ------------------------------------------------------------------
# 东财数据解析工具
# ------------------------------------------------------------------

def _normalize_diff(data_diff: Any) -> List[Dict[str, Any]]:
    """东财 diff 有时是数组，有时是对象（clist 返回 {\"0\":{}, \"1\":{}}）"""
    if data_diff is None:
        return []
    if isinstance(data_diff, list):
        return data_diff
    if isinstance(data_diff, dict):
        return [data_diff[k] for k in sorted(data_diff.keys(), key=lambda x: int(x) if str(x).isdigit() else x)]
    return []


def _safe_float(v: Any) -> Optional[float]:
    if v is None or v == "" or v == "-":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _safe_int(v: Any) -> Optional[int]:
    if v is None or v == "" or v == "-":
        return None
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def _em_clist_price(v: Any) -> Optional[float]:
    """clist/get fltt=2 返回价格类字段 ×100 的整数，需除以 100"""
    val = _safe_float(v)
    if val is None:
        return None
    return val / 100


def _em_item_to_quote(item: Dict[str, Any], symbol: str, market_type: str, date_str: str) -> QuoteData:
    """将东财 diff 项转为 QuoteData"""
    price = _em_clist_price(item.get("f2"))
    prev_close = _em_clist_price(item.get("f18"))
    change = _em_clist_price(item.get("f4"))
    change_pct = _em_clist_price(item.get("f3"))

    # 若涨跌幅缺失但价格/昨收可用，自行计算
    if change_pct is None and price is not None and prev_close is not None and prev_close != 0:
        change_pct = (price - prev_close) / prev_close * 100

    if change is None and price is not None and prev_close is not None:
        change = price - prev_close

    currency = "USD"
    if market_type == "hk_market":
        currency = "HKD"
    elif market_type == "cn_market":
        currency = "CNY"

    qd = QuoteData(
        symbol=symbol,
        name=item.get("f14", symbol),
        market=market_type,
        date=date_str,
        price=price,
        prev_close=prev_close,
        change=change,
        change_pct=change_pct,
        open_price=_em_clist_price(item.get("f17")),
        high=_em_clist_price(item.get("f15")),
        low=_em_clist_price(item.get("f16")),
        volume=_safe_int(item.get("f5")),
        currency=currency,
        source="eastmoney_clist",
    )
    return validate_quote(qd)


# ------------------------------------------------------------------
# 东财 clist 批量获取（美股/港股/指数）
# ------------------------------------------------------------------

@retry_on_recoverable(max_retries=MAX_RETRIES, initial_delay=INITIAL_BACKOFF)
def eastmoney_clist(fs_filter: str, fields: str = EM_CLIST_FIELDS, pz: int = 200, date_str: str = "") -> List[Dict[str, Any]]:
    """东财 clist 批量接口：免登录、不限流、一次可拉多条"""
    cached = cache_load(fs_filter, date_str, "eastmoney_clist")
    if cached:
        return cached.get("data", [])

    ts = int(datetime.now().timestamp() * 1000)
    url = EM_CLIST_URL.format(fs=fs_filter, fields=fields, pz=pz, ts=ts)
    data = fetch_json(url, {"Referer": "https://quote.eastmoney.com/"})
    if "_error" in data:
        diag(f"Eastmoney clist {fs_filter}: {data['_error']}")
        return []

    diff = _normalize_diff(data.get("data", {}).get("diff"))
    cache_save(fs_filter, date_str, "eastmoney_clist", {"data": diff})
    return diff


def fetch_em_indices(symbols_map: Dict[str, str], date_str: str, market_fs: str) -> List[QuoteData]:
    """通过东财 clist 获取指数，按 symbol 过滤"""
    all_data = eastmoney_clist(market_fs, date_str=date_str)
    results = []
    lookup = {item.get("f12", "").upper(): item for item in all_data}

    for sym, name in symbols_map.items():
        em_code = EM_CODE_MAP.get(sym, sym.lstrip("^").upper())
        item = lookup.get(em_code)
        if not item:
            diag(f"Eastmoney clist missing index: {sym} (lookup {em_code})")
            continue
        market = "us_market" if market_fs.startswith("i:100.SPX") else "hk_market"
        qd = _em_item_to_quote(item, sym, market, date_str)
        qd.name = name
        results.append(qd)

    return results


def fetch_em_stocks(codes: List[str], date_str: str, market_fs: str) -> List[QuoteData]:
    """通过东财 clist 获取个股，批量查询后本地过滤"""
    all_data = eastmoney_clist(market_fs, pz=500, date_str=date_str)
    results = []

    # 构建查找表（支持 0700 / 00700 等变体）
    lookup: Dict[str, Dict[str, Any]] = {}
    for item in all_data:
        c = str(item.get("f12", "")).upper().replace(".HK", "")
        lookup[c] = item
        lookup[c.lstrip("0") or "0"] = item
        lookup[c.zfill(5)] = item

    for code in codes:
        raw = code.upper().replace(".HK", "")
        item = lookup.get(raw) or lookup.get(raw.lstrip("0") or "0") or lookup.get(raw.zfill(5))
        if not item:
            diag(f"Eastmoney clist missing stock: {code}")
            continue
        market = "us_market" if market_fs == EM_FS["us_stock"] else "hk_market"
        qd = _em_item_to_quote(item, code, market, date_str)
        results.append(qd)

    return results


# ------------------------------------------------------------------
# 数据验证
# ------------------------------------------------------------------

def validate_quote(qd: QuoteData) -> QuoteData:
    notes = []
    flags = []

    # 价格验证
    for field, val in [("price", qd.price), ("open_price", qd.open_price), ("high", qd.high), ("low", qd.low)]:
        if val is not None and val <= 0:
            setattr(qd, field, None)
            notes.append(f"{field}异常已过滤")
            flags.append("price_anomaly")

    # 成交量验证
    if qd.volume is not None:
        if qd.volume <= 0:
            if qd.symbol.startswith("^") or qd.market in ("hk_market", "eu_market", "jp_market"):
                # 指数成交量为0是正常情况，降级为 warning
                notes.append("指数成交量缺失（数据源未提供）")
                flags.append("volume_missing_index")
            else:
                notes.append("成交量为0，异常")
                flags.append("volume_zero")
        elif qd.volume < VOLUME_THRESHOLD_STOCK and not qd.symbol.startswith("^"):
            notes.append(f"成交量偏低({fmt_volume(qd.volume)})")
            flags.append("volume_anomaly")
        elif qd.volume < VOLUME_THRESHOLD_INDEX and qd.symbol.startswith("^"):
            notes.append(f"指数成交量偏低({fmt_volume(qd.volume)})")
            flags.append("volume_anomaly")

    # 完整性评分
    required = ["price", "volume"]
    available = sum(1 for f in required if getattr(qd, f) is not None)
    qd.completeness = (available / len(required)) * 100 if required else 0
    # 如果昨收存在再 +20 分
    if qd.prev_close is not None:
        qd.completeness = min(100, qd.completeness + 20)
    if qd.change_pct is not None:
        qd.completeness = min(100, qd.completeness + 20)

    qd.notes = notes
    qd.quality_flags = flags
    return qd


# ------------------------------------------------------------------
# 市场检测
# ------------------------------------------------------------------

def detect_market_type(ticker: str) -> str:
    t = str(ticker).upper()
    if t.endswith(".HK") or any(x in t for x in ["HSI", "HSCE", "HSTECH"]):
        return "hk_market"
    elif any(x in t for x in ["上证", "深证", "创业板", "科创板", "399001", "899050", "000001"]):
        return "cn_market"
    elif any(x in t for x in ["DAX", "CAC", "FTSE", "ESTX", "GDAXI", "FCHI"]):
        return "eu_market"
    elif "NIKKEI" in t or t.endswith(".T") or t.endswith(".JP") or "N225" in t:
        return "jp_market"
    else:
        return "us_market"


# ------------------------------------------------------------------
# A股数据获取（东财）
# ------------------------------------------------------------------

@retry_on_recoverable(max_retries=MAX_RETRIES, initial_delay=INITIAL_BACKOFF)
def get_index(date_str: str) -> List[Dict[str, Any]]:
    cached = cache_load("index_all", date_str, "eastmoney")
    if cached:
        return cached.get("data", [])

    url = INDEX_URL.format(secids=INDEX_SECIDS, fields=INDEX_FIELDS, ts=datetime.now().timestamp())
    data = fetch_json(url, {"Referer": "https://quote.eastmoney.com/"})
    if "_error" in data:
        diag(f"Eastmoney index: {data['_error']}")
        return []
    result = data.get("data", {}).get("diff", [])
    cache_save("index_all", date_str, "eastmoney", {"data": result})
    return result


@retry_on_recoverable(max_retries=MAX_RETRIES, initial_delay=INITIAL_BACKOFF)
def get_zt_pool(date_str: str) -> Dict[str, Any]:
    cached = cache_load("zt_pool", date_str, "eastmoney")
    if cached:
        return cached
    data = fetch_json(ZT_URL.format(date=date_str), {"Referer": "https://quote.eastmoney.com/"})
    if "_error" not in data:
        cache_save("zt_pool", date_str, "eastmoney", data)
    else:
        diag(f"Eastmoney ZT pool: {data['_error']}")
    return data


@retry_on_recoverable(max_retries=MAX_RETRIES, initial_delay=INITIAL_BACKOFF)
def get_dt_pool(date_str: str) -> Dict[str, Any]:
    cached = cache_load("dt_pool", date_str, "eastmoney")
    if cached:
        return cached
    data = fetch_json(DT_URL.format(date=date_str), {"Referer": "https://quote.eastmoney.com/"})
    if "_error" not in data:
        cache_save("dt_pool", date_str, "eastmoney", data)
    else:
        diag(f"Eastmoney DT pool: {data['_error']}")
    return data


@retry_on_recoverable(max_retries=MAX_RETRIES, initial_delay=INITIAL_BACKOFF)
def get_zb_pool(date_str: str) -> Dict[str, Any]:
    cached = cache_load("zb_pool", date_str, "eastmoney")
    if cached:
        return cached
    data = fetch_json(ZB_URL.format(date=date_str), {"Referer": "https://quote.eastmoney.com/"})
    if "_error" not in data:
        cache_save("zb_pool", date_str, "eastmoney", data)
    else:
        diag(f"Eastmoney ZB pool: {data['_error']}")
    return data


@retry_on_recoverable(max_retries=MAX_RETRIES, initial_delay=INITIAL_BACKOFF)
def get_fund_flow(date_str: str) -> Dict[str, str]:
    cached = cache_load("fund_flow", date_str, "eastmoney")
    if cached:
        return cached

    url = FFLOW_URL.format(ts=int(datetime.now().timestamp() * 1000))
    data = fetch_json(url, {"Referer": "https://quote.eastmoney.com/"})
    if "_error" in data:
        diag(f"Eastmoney fund flow: {data['_error']}")
        return {}
    d = data.get("data", {})
    klines = d.get("klines", [])
    if not klines:
        return {}
    cols = "date,主力净流入,小单净流入,中单净流入,大单净流入,超大单净流入,主力净流入占比,小单净流入占比,中单净流入占比,大单净流入占比,超大单净流入占比,收盘价,涨跌幅,总成交额".split(",")
    vals = klines[0].split(",")
    result = dict(zip(cols, vals))
    cache_save("fund_flow", date_str, "eastmoney", result)
    return result


# ------------------------------------------------------------------
# 富途数据获取
# ------------------------------------------------------------------

@retry_on_recoverable(max_retries=MAX_RETRIES, initial_delay=INITIAL_BACKOFF)
def futu_news_search(keyword: str, size: int = 10, lang: str = "en", news_type: int = 1) -> Dict[str, Any]:
    params = urllib.parse.urlencode({
        "keyword": keyword,
        "size": size,
        "news_type": news_type,
        "lang": lang,
        "sort_type": 2,
    })
    url = f"{FUTU_NEWS_URL}?{params}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "stock-analysis/3.1.1"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        diag(f"Futu news {keyword}: {e}")
        return {"_error": str(e)}


@retry_on_recoverable(max_retries=MAX_RETRIES, initial_delay=INITIAL_BACKOFF)
def futu_stock_feed(keyword: str, size: int = 30) -> Dict[str, Any]:
    params = urllib.parse.urlencode({"keyword": keyword, "size": size})
    url = f"{FUTU_FEED_URL}?{params}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "stock-analysis/3.1.1"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        diag(f"Futu feed {keyword}: {e}")
        return {"_error": str(e)}


# ------------------------------------------------------------------
# 板块榜（camofox 降级层）
# ------------------------------------------------------------------

def camofox_board_list(board_type: str = "industry") -> Dict[str, Any]:
    base = os.environ.get("CAMOFOX_URL", "http://localhost:9377")
    user_id = os.environ.get("CAMOFOX_USER_ID", "")
    session_key = os.environ.get("CAMOFOX_SESSION_KEY", "")
    if not user_id or not session_key:
        return {"_skipped": "camofox env not set"}

    anchor = "industry_board" if board_type == "industry" else "concept_board"
    target_url = f"https://quote.eastmoney.com/center/gridlist.html#{anchor}"

    try:
        create_payload = json.dumps({"url": target_url, "userId": user_id, "sessionKey": session_key}).encode()
        req = urllib.request.Request(f"{base}/tabs", data=create_payload,
                                     headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=10) as resp:
            tab_info = json.loads(resp.read().decode())
        tab_id = tab_info.get("tabId") or tab_info.get("id")
        if not tab_id:
            return {"_error": "no tab id"}

        wait_payload = json.dumps({"state": "networkidle", "userId": user_id, "sessionKey": session_key}).encode()
        req2 = urllib.request.Request(f"{base}/tabs/{tab_id}/wait", data=wait_payload,
                                      headers={"Content-Type": "application/json"}, method="POST")
        try:
            urllib.request.urlopen(req2, timeout=15)
        except Exception:
            pass

        snap_url = f"{base}/tabs/{tab_id}/snapshot?userId={user_id}&format=markdown"
        with urllib.request.urlopen(urllib.request.Request(snap_url, method="GET"), timeout=15) as resp:
            md = resp.read().decode("utf-8", errors="ignore")

        rows = []
        for line in md.splitlines():
            line = line.strip()
            if line.startswith('row "'):
                content = line[5:].rstrip('"')
                parts = re.split(r"\s{2,}", content)
                if len(parts) >= 4:
                    rows.append(parts)
        return {"board_type": board_type, "rows": rows, "count": len(rows)}
    except Exception as e:
        diag(f"camofox board {board_type}: {e}")
        return {"_error": str(e)}


# ------------------------------------------------------------------
# 输出格式化
# ------------------------------------------------------------------

def print_index(data: List[Dict[str, Any]]) -> None:
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
        # fltt=2 已返回正常价格，不再缩放
        close_p = fmt_price(item.get("f2"))
        change = fmt_price(item.get("f4"))
        pct = fmt_pct(item.get("f3"))
        amount = fmt_amount(item.get("f6"))
        print(f"{name:<10} {close_p:>10} {change:>10} {pct:>10} {amount:>12}")
    print()


def print_zt_analysis(zt_data: Dict, dt_data: Dict, zb_data: Dict) -> None:
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

    ladders: Dict[int, List] = {}
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


def print_fund_flow(flow_data: Dict[str, str]) -> None:
    if not flow_data or "_error" in flow_data:
        return
    print("## 资金流向（上证指数口径）\n")
    print(f"  主力净流入: {fmt_amount(flow_data.get('主力净流入'))}")
    print(f"  超大单:     {fmt_amount(flow_data.get('超大单净流入'))}")
    print(f"  大单:       {fmt_amount(flow_data.get('大单净流入'))}")
    print(f"  中单:       {fmt_amount(flow_data.get('中单净流入'))}")
    print(f"  小单:       {fmt_amount(flow_data.get('小单净流入'))}")
    print()


def print_boards(board_data: Dict[str, Any], title: str) -> None:
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


def print_sentiment_summary(zt_data: Dict, dt_data: Dict, zb_data: Dict, flow_data: Dict) -> None:
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


def print_global_indices(indices: List[QuoteData], market_name: str) -> None:
    print(f"## {market_name} 大盘指数\n")
    print(f"{'指数':<15} {'当前价':>12} {'涨跌幅':>10} {'成交量':>14} {'数据质量':>8}")
    print("-" * 70)
    for qd in indices:
        name = qd.name or qd.symbol
        price_str = fmt_price(qd.price)
        pct_str = fmt_pct(qd.change_pct) if qd.change_pct is not None else "-"
        vol_str = fmt_volume(qd.volume)
        if "volume_missing_index" in qd.quality_flags or "volume_zero" in qd.quality_flags:
            vol_str += " *"
        quality_str = f"{qd.completeness:.0f}%"
        print(f"{name:<15} {price_str:>12} {pct_str:>10} {vol_str:>14} {quality_str:>8}")
    print()


def print_global_stock(qd: QuoteData) -> None:
    print(f"## {qd.name} ({qd.symbol})\n")
    print(f"  当前价: {fmt_price(qd.price)}")
    print(f"  昨收:   {fmt_price(qd.prev_close)}")
    print(f"  开盘:   {fmt_price(qd.open_price)}")
    print(f"  最高:   {fmt_price(qd.high)}")
    print(f"  最低:   {fmt_price(qd.low)}")
    vol_str = fmt_volume(qd.volume)
    if any(f in qd.quality_flags for f in ["volume_zero", "volume_anomaly"]):
        vol_str += " *"
    print(f"  成交量: {vol_str}")
    print(f"  货币:   {qd.currency}")
    if qd.change is not None and qd.change_pct is not None:
        print(f"  涨跌:   {qd.change:+.2f} ({qd.change_pct:+.2f}%)")
    if qd.notes:
        print(f"  ⚠️ {', '.join(qd.notes)}")
    print()


def print_futu_news(news_data: Dict, keyword: str) -> None:
    if "_error" in news_data:
        return
    data = news_data.get("data", [])
    if not data:
        return
    print(f"## {keyword} 新闻（前5条）\n")
    for i, item in enumerate(data[:5], 1):
        ts = item.get("publish_time", 0)
        # 富途返回的 publish_time 是字符串，先转 int
        try:
            ts_int = int(ts)
            dt_str = datetime.fromtimestamp(ts_int).strftime("%m-%d %H:%M") if ts_int else ""
        except (TypeError, ValueError):
            dt_str = ""
        print(f"{i}. [{dt_str}] {item.get('title', '')}")
        print(f"   {item.get('url', '')}")
    print()


def print_global_sentiment(indices: List[QuoteData]) -> None:
    print("## 情绪定性\n")
    bullish = 0
    bearish = 0
    valid = 0
    for qd in indices:
        if qd.change_pct is not None:
            valid += 1
            if qd.change_pct > 1:
                bullish += 1
            elif qd.change_pct < -1:
                bearish += 1

    if valid > 0:
        if bullish >= valid * 0.6:
            print("🔥 强势：大盘指数多数大涨，情绪高涨")
        elif bearish >= valid * 0.6:
            print("❄️ 弱势：大盘指数多数大跌，情绪低迷")
        elif bullish > bearish:
            print("📈 偏强：大盘指数涨多跌少，情绪偏活跃")
        elif bearish > bullish:
            print("⚠️ 偏弱：大盘指数跌多涨少，情绪偏谨慎")
        else:
            print("😐 中性：大盘指数分化，情绪平衡")
    print()


def print_data_quality_report(results: List[QuoteData]) -> None:
    warnings = []
    recommendations = []
    total = len(results)
    if total == 0:
        return

    avg_score = sum(r.completeness for r in results) / total

    for r in results:
        if r.completeness < 80:
            name = r.name or r.symbol
            warnings.append(f"{name}: 数据完整性较低 ({r.completeness:.0f}%)")
        for note in r.notes:
            name = r.name or r.symbol
            warnings.append(f"{name}: {note}")

    if avg_score < 90:
        recommendations.append("数据完整性一般，建议检查网络连接或稍后重试")
    if any("异常" in w or "缺失" in w for w in warnings):
        recommendations.append("部分数据异常，已标记 * ，仅供参考")

    if warnings or recommendations or DIAGNOSTICS:
        print("\n" + "=" * 60)
        print("📊 数据质量与诊断报告")
        print(f"  平均完整度: {avg_score:.0f}%")
        if DIAGNOSTICS:
            print(f"\n  ⚙️ 接口诊断:")
            for d in DIAGNOSTICS[:6]:
                print(f"    • {d}")
            if len(DIAGNOSTICS) > 6:
                print(f"    ... 还有 {len(DIAGNOSTICS) - 6} 条")
        if warnings:
            print(f"\n  ⚠️ 数据警告 ({len(warnings)}条):")
            for w in warnings[:8]:
                print(f"    • {w}")
            if len(warnings) > 8:
                print(f"    ... 还有 {len(warnings) - 8} 条")
        if recommendations:
            print(f"\n  💡 建议:")
            for rec in recommendations:
                print(f"    • {rec}")
        print("=" * 60)


def print_diagnostic_summary() -> None:
    if DIAGNOSTICS:
        print("\n" + "=" * 60)
        print("⚙️ 接口诊断摘要")
        for d in DIAGNOSTICS:
            print(f"  • {d}")
        print("=" * 60)


# ------------------------------------------------------------------
# 复盘主体
# ------------------------------------------------------------------

def nearest_trade_date(dt: Optional[datetime] = None) -> str:
    if dt is None:
        dt = datetime.now()
    wd = dt.weekday()
    if wd == 5:
        dt -= timedelta(days=1)
    elif wd == 6:
        dt -= timedelta(days=2)
    return dt.strftime("%Y%m%d")


def _session_label() -> str:
    """根据当前时间返回场次标签"""
    now = datetime.now()
    t = now.hour * 60 + now.minute
    if 570 <= t < 690:      # 09:30 - 11:30
        return "上午盘"
    elif 690 <= t < 780:    # 11:30 - 13:00
        return "午间"
    elif 780 <= t < 900:    # 13:00 - 15:00
        return "下午盘"
    else:
        return "盘后"


def run_a_share(date_str: str) -> None:
    display_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
    session = _session_label()
    print(f"# A 股{session}复盘（{display_date}）\n")
    print(f"数据来源: 东方财富免登录 API | 采集时间: {datetime.now().strftime('%H:%M:%S')}\n")
    print("=" * 60 + "\n")

    index_data = get_index(date_str)
    if index_data:
        print_index(index_data)

    zt = get_zt_pool(date_str)
    dt = get_dt_pool(date_str)
    zb = get_zb_pool(date_str)
    print_zt_analysis(zt, dt, zb)

    flow = get_fund_flow(date_str)
    print_fund_flow(flow)

    print_sentiment_summary(zt, dt, zb, flow)

    industry = camofox_board_list("industry")
    concept = camofox_board_list("concept")
    print_boards(industry, "行业板块涨幅")
    print_boards(concept, "概念板块涨幅")

    if DIAGNOSTICS:
        print_diagnostic_summary()

    print("=" * 60)
    print("\n*输出结束。")


def run_us_market(date_str: str) -> None:
    print("# 美股市场复盘\n")
    print(f"数据来源: 东方财富免登录 API (clist) | 采集时间: {datetime.now().strftime('%H:%M:%S')}\n")
    print("=" * 60 + "\n")

    us_indices_map = {
        "^GSPC": "标普 500",
        "^IXIC": "纳斯达克",
    }
    indices = fetch_em_indices(us_indices_map, date_str, EM_FS["us_index"])
    if indices:
        print_global_indices(indices, "美股")

    hot_stocks = ["AAPL", "TSLA", "NVDA", "MSFT", "AMZN", "GOOGL", "META", "BABA", "PDD", "JD"]
    print("## 重点个股行情\n")
    stocks = fetch_em_stocks(hot_stocks, date_str, EM_FS["us_stock"])
    for qd in stocks:
        print_global_stock(qd)

    for sym in ["AAPL", "TSLA", "NVDA"]:
        news = futu_news_search(sym, size=5, lang="en")
        print_futu_news(news, sym)

    if indices:
        print_global_sentiment(indices)
        print_data_quality_report(indices + stocks)
    elif stocks:
        print_data_quality_report(stocks)

    if DIAGNOSTICS:
        print_diagnostic_summary()

    print("=" * 60)
    print("\n*输出结束。")


def run_hk_market(date_str: str) -> None:
    print("# 港股市场复盘\n")
    print(f"数据来源: 东方财富免登录 API (clist) | 采集时间: {datetime.now().strftime('%H:%M:%S')}\n")
    print("=" * 60 + "\n")

    hk_indices_map = {
        "^HSI": "恒生指数",
        "^HSCE": "国企指数",
        "HSTECH.HK": "恒生科技指数",
    }
    indices = fetch_em_indices(hk_indices_map, date_str, EM_FS["hk_index"])
    if indices:
        print_global_indices(indices, "港股")

    hot_stocks = ["0700.HK", "9988.HK", "3690.HK", "9618.HK", "1299.HK", "2318.HK", "0005.HK", "0388.HK"]
    print("## 重点个股行情\n")
    stocks = fetch_em_stocks(hot_stocks, date_str, EM_FS["hk_stock"])
    for qd in stocks:
        print_global_stock(qd)

    for sym in ["0700", "9988", "3690"]:
        news = futu_news_search(sym, size=5, lang="zh-CN")
        print_futu_news(news, sym)

    if indices:
        print_global_sentiment(indices)
        print_data_quality_report(indices + stocks)
    elif stocks:
        print_data_quality_report(stocks)

    if DIAGNOSTICS:
        print_diagnostic_summary()

    print("=" * 60)
    print("\n*输出结束。")


def run_global_market(date_str: str) -> None:
    print("# 全球市场概览\n")
    print(f"数据来源: 东方财富免登录 API | 采集时间: {datetime.now().strftime('%H:%M:%S')}\n")
    print("=" * 60 + "\n")

    # 美股
    us_indices_map = {
        "^GSPC": "标普 500",
        "^IXIC": "纳斯达克",
    }
    us_indices = fetch_em_indices(us_indices_map, date_str, EM_FS["us_index"])
    if us_indices:
        print_global_indices(us_indices, "美股")

    # 港股
    hk_indices_map = {
        "^HSI": "恒生指数",
        "^HSCE": "国企指数",
        "HSTECH.HK": "恒生科技指数",
    }
    hk_indices = fetch_em_indices(hk_indices_map, date_str, EM_FS["hk_index"])
    if hk_indices:
        print_global_indices(hk_indices, "港股")

    # A股指数
    a_index = get_index(date_str)
    if a_index:
        print("## A股指数表现\n")
        print(f"{'指数':<10} {'收盘':>10} {'涨跌':>10} {'涨跌幅':>10} {'成交额':>12}")
        print("-" * 60)
        name_map = {
            "000001": "上证指数", "399001": "深证成指",
            "399006": "创业板指", "000688": "科创50",
            "399005": "中小板指", "899050": "北证50",
        }
        for item in a_index:
            code = item.get("f12", "")
            name = name_map.get(code, item.get("f14", code))
            print(f"{name:<10} {fmt_price(item.get('f2')):>10} {fmt_price(item.get('f4')):>10} "
                  f"{fmt_pct(item.get('f3')):>10} {fmt_amount(item.get('f6')):>12}")
        print()

    all_results = []
    if us_indices:
        all_results.extend(us_indices)
    if hk_indices:
        all_results.extend(hk_indices)
    if all_results:
        print_data_quality_report(all_results)

    if DIAGNOSTICS:
        print_diagnostic_summary()

    print("=" * 60)
    print("\n*输出结束。")


# ------------------------------------------------------------------
# main
# ------------------------------------------------------------------

def main():
    global NO_CACHE
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
        elif args[i] == "--no-cache" or args[i] == "--refresh":
            NO_CACHE = True
            i += 1
        elif re.fullmatch(r"\d{8}", args[i]):
            date_str = args[i]
            i += 1
        else:
            i += 1

    if market not in ("a", "hk", "us", "global"):
        print("错误: --market 参数必须是 a、hk、us 或 global", file=sys.stderr)
        sys.exit(1)

    # 清理过期缓存
    cache_clear_old(days=7)

    if date_str is None:
        date_str = nearest_trade_date()

    if market == "a":
        run_a_share(date_str)
    elif market == "us":
        run_us_market(date_str)
    elif market == "hk":
        run_hk_market(date_str)
    elif market == "global":
        run_global_market(date_str)


if __name__ == "__main__":
    main()
