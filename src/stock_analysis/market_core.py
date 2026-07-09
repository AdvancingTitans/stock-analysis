#!/usr/bin/env python3
"""Internal market data core for stock-analysis.

Keeps the proven three-layer strategy: local cache, stable public APIs,
then optional browser fallback for sources that need a rendered page.
"""

from __future__ import annotations

import html
import json
import os
import random
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path
from typing import Any

from .market_time import resolve_trade_date


class _SourceHealthBook:
    def record(self, name: str, ok: bool, latency_ms: float) -> None:
        del name, ok, latency_ms


SOURCE_HEALTH = _SourceHealthBook()


def route_board_data(
    board_type: str,
    trade_date: str,
    *,
    direct: Callable[[str, str, int], dict[str, Any]],
    browser_service: Callable[[str], dict[str, Any]],
    playwright: Callable[[str], dict[str, Any]],
    limit: int = 100,
    current_trade_date: str | None = None,
    browser_fallback: bool = False,
) -> dict[str, Any]:
    normalized_type = "concept" if board_type == "concept" else "industry"
    if current_trade_date and trade_date != current_trade_date:
        cached = cache_load("board_list", f"{trade_date}_{normalized_type}", "eastmoney_clist")
        if cached and cached.get("rows"):
            cached = dict(cached)
            cached["_source_note"] = "历史板块榜来自本地缓存"
            return cached
        requested = datetime.strptime(trade_date, "%Y%m%d")
        if (datetime.now() - requested).days > 7:
            return {
                "board_type": board_type,
                "rows": [],
                "_unavailable": "远期历史板块榜无缓存，禁止混用实时数据",
            }
    result = direct(board_type, trade_date, limit)
    if isinstance(result, dict) and result.get("rows"):
        if current_trade_date and trade_date != current_trade_date:
            result = dict(result)
            result["_stale_warning"] = "板块榜为实时接口回填，历史复盘请优先使用缓存"
        return result
    if not browser_fallback:
        return result or {"board_type": board_type, "rows": [], "_unavailable": "本模块证据暂缺"}
    for browser_source in (browser_service, playwright):
        candidate = browser_source(board_type)
        if isinstance(candidate, dict) and candidate.get("rows"):
            return candidate
    return result or {"board_type": board_type, "rows": [], "_unavailable": "本模块证据暂缺"}

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
CACHE_DIR = Path(os.environ.get("STOCK_ANALYSIS_CACHE_DIR", Path.home() / ".cache" / "stock-analysis")).expanduser()

# 全局开关：是否强制忽略缓存
NO_CACHE = False
BROWSER_FALLBACK = os.environ.get("STOCK_ANALYSIS_BROWSER_FALLBACK", "").strip().lower() in {"1", "true", "yes", "on"}

# A股配置
INDEX_SECIDS = "1.000001,0.399001,0.399006,1.000300,1.000688,0.399005,0.899050"
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
FFLOW_HIS_URL = (
    "https://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get"
    "?secid=1.000001&fields1=f1,f2,f3,f7"
    "&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64,f65"
    "&klt=101&lmt=1&_={ts}"
)
STOCK_FUND_FLOW_DAILY_URL = (
    "https://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get"
    "?secid={secid}&fields1=f1,f2,f3,f7"
    "&fields2=f51,f52,f53,f54,f55,f56,f57&klt=101&lmt={limit}&_={ts}"
)
THS_NORTHBOUND_FLOW_URL = "https://data.hexin.cn/market/hsgtApi/method/dayChart/"
EASTMONEY_DATACENTER_URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"
FUND_FLOW_COLS = "date,主力净流入,小单净流入,中单净流入,大单净流入,超大单净流入,主力净流入占比,小单净流入占比,中单净流入占比,大单净流入占比,超大单净流入占比,收盘价,涨跌幅,总成交额".split(",")
FFLOW_MARKET_FIELDS = "f62,f184,f66,f69,f72,f75,f78,f81,f84,f87,f124,f6"
FFLOW_MARKET_URL = (
    "https://push2.eastmoney.com/api/qt/ulist.np/get"
    "?fltt=2&secids=1.000001,0.399001&fields={fields}"
    "&ut=b2884a393a59ad64002292a3e90d46a5&_={ts}"
)
SINA_SECTOR_MONEY_FLOW_URL = (
    "https://money.finance.sina.com.cn/quotes_service/view/xml_money_flow_fc_hy.php"
    "?fenlei=0&format=json&callback=gotData0&_={ts}"
)
THS_CONCEPT_MONEY_FLOW_URL = "http://data.10jqka.com.cn/funds/gnzjl/"
THS_INDUSTRY_BOARD_URL = "https://q.10jqka.com.cn/thshy/"
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

# 美股 secid 映射（市场代码: 105=NASDAQ, 106=NYSE, 107=AMEX）
EM_US_SECID = {
    "AAPL": "105.AAPL", "TSLA": "105.TSLA", "NVDA": "105.NVDA",
    "MSFT": "105.MSFT", "AMZN": "105.AMZN", "GOOGL": "105.GOOGL",
    "META": "105.META", "PDD":  "105.PDD",  "NFLX": "105.NFLX",
    "AMD":  "105.AMD",  "INTC": "105.INTC", "AVGO": "105.AVGO",
    "BABA": "106.BABA", "JD":   "106.JD",   "BIDU": "105.BIDU",
    "TSM":  "106.TSM",  "ORCL": "106.ORCL", "CRM":  "106.CRM",
}

# 美股指数 secid
EM_US_INDEX_SECID = {
    "^GSPC": "100.SPX",
    "^IXIC": "100.NDX",
    "^DJI":  "100.DJIA",
}

# 港股指数 secid
EM_HK_INDEX_SECID = {
    "^HSI":      "100.HSI",
    "^HSCE":     "100.HSCE",
    "HSTECH.HK": "100.HSTECH",
}

# stock/get 字段映射: f43=最新价, f44=最高, f45=最低, f46=开盘, f47=成交量(股),
# f48=成交额(元), f57=代码, f58=名称, f60=昨收, f169=涨跌额, f170=涨跌幅
EM_STOCK_GET_FIELDS = "f43,f44,f45,f46,f47,f48,f57,f58,f60,f169,f170"
EM_SEARCH_URL = "https://searchapi.eastmoney.com/api/suggest/get"
EM_SEARCH_TOKEN = "D43BF722C8E33BDC906FB84D85E326E8"

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
SINA_ROLL_NEWS_URL = "https://feed.mix.sina.com.cn/api/roll/get"
EASTMONEY_FAST_NEWS_URL = "https://np-listapi.eastmoney.com/comm/web/getFastNewsList"
FUND_ESTIMATE_URL = "https://fundgz.1234567.com.cn/js/{code}.js?rt={ts}"
FUND_HOLDINGS_URL = (
    "https://fundf10.eastmoney.com/FundArchivesDatas.aspx"
    "?type=jjcc&code={code}&topline={topline}&year=&month=&rt={ts}"
)
FUND_NAV_HISTORY_URL = (
    "https://api.fund.eastmoney.com/f10/lsjz"
    "?fundCode={code}&pageIndex=1&pageSize=20&startDate={start}&endDate={end}&_={ts}"
)
FUND_PROFILE_URL = "https://fund.eastmoney.com/pingzhongdata/{code}.js?v={ts}"
FUND_MOB_F10_URL = "https://fundmobapi.eastmoney.com/FundMNewApi/FundMNFInfo"
EM_KLINE_URL = (
    "https://push2his.eastmoney.com/api/qt/stock/kline/get"
    "?secid={secid}&fields1=f1,f2,f3,f4,f5,f6"
    "&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61"
    "&klt=101&fqt=1&beg={beg}&end={end}&_={ts}"
)

# 新浪财经（免登录、GBK 编码、对美股/港股最稳，作为 stock/get 之外的主路径）
SINA_HQ_URL = "https://hq.sinajs.cn/list={codes}"

# 腾讯财经（免登录、GBK 编码；港股指数收盘口径更接近交易所/新闻稿）
TENCENT_QUOTE_URL = "https://qt.gtimg.cn/q={codes}"

# 诊断记录
DIAGNOSTICS: list[str] = []
NEWS_URL_VALIDATION_CACHE: dict[str, bool] = {}
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
    price: float | None = None
    prev_close: float | None = None
    change: float | None = None
    change_pct: float | None = None
    open_price: float | None = None
    high: float | None = None
    low: float | None = None
    volume: int | None = None
    turnover: float | None = None
    turnover_rate: float | None = None
    market_cap: float | None = None
    float_market_cap: float | None = None
    pe: float | None = None
    pb: float | None = None
    high_52w: float | None = None
    low_52w: float | None = None
    amplitude_pct: float | None = None
    currency: str = "USD"
    source: str = ""
    quality_flags: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    completeness: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class FundHolding:
    code: str
    name: str
    weight_pct: float | None = None
    shares_10k: float | None = None
    market_value_10k: float | None = None


# ------------------------------------------------------------------
# 缓存层
# ------------------------------------------------------------------

def _cache_key(symbol: str, date_str: str, source: str) -> str:
    safe = re.sub(r"[^\w\-\.]", "_", symbol)
    return f"{source}_{safe}_{date_str}.json"


def _cache_path(symbol: str, date_str: str, source: str) -> Path:
    return CACHE_DIR / date_str / _cache_key(symbol, date_str, source)


def _cache_write_path(symbol: str, date_str: str, source: str) -> Path:
    d = CACHE_DIR / date_str
    d.mkdir(parents=True, exist_ok=True)
    return d / _cache_key(symbol, date_str, source)


def cache_load(symbol: str, date_str: str, source: str, ttl: int = CACHE_TTL_SECONDS) -> dict[str, Any] | None:
    if NO_CACHE:
        return None
    p = _cache_path(symbol, date_str, source)
    if p.exists():
        try:
            mtime = p.stat().st_mtime
            if time.time() - mtime > ttl:
                return None  # 缓存过期
            with open(p, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return None


def cache_save(symbol: str, date_str: str, source: str, data: dict[str, Any]) -> None:
    # 空数据/错误响应不入缓存，避免污染后续读取
    if not data:
        return
    payload = data.get("data") if isinstance(data, dict) else None
    if payload is not None and not payload:  # data: [] / data: {}
        return
    p = _cache_write_path(symbol, date_str, source)
    try:
        with open(p, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, default=str)
    except Exception:
        pass


def load_latest_fund_flow_cache(date_str: str) -> dict[str, str] | None:
    """读取最近一次可信资金流缓存，用作接口临时不可用时的兜底。"""
    if not CACHE_DIR.exists():
        return None
    try:
        dirs = sorted(
            [d for d in CACHE_DIR.iterdir() if d.is_dir() and re.fullmatch(r"\d{8}", d.name)],
            key=lambda d: d.name,
            reverse=True,
        )
    except Exception:
        return None
    for d in dirs:
        p = d / _cache_key("fund_flow", d.name, "eastmoney")
        if not p.exists():
            continue
        try:
            with open(p, encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue
        if not data or data.get("_unavailable") or not data.get("主力净流入") or not data.get("date"):
            continue
        data["_requested_date"] = _display_date(date_str)
        if data.get("date", "").replace("-", "") != date_str:
            data["_date_note"] = "latest_available"
        data.setdefault("_source", "本地最近可用资金流缓存")
        data.setdefault("_scope", "A股")
        return data
    return None


def cache_clear_old(days: int = 7) -> None:
    cutoff = datetime.now() - timedelta(days=days)
    if not CACHE_DIR.exists():
        return
    try:
        dirs = list(CACHE_DIR.iterdir())
    except OSError:
        return
    for d in dirs:
        if d.is_dir():
            try:
                dt = datetime.strptime(d.name, "%Y%m%d")
                if dt < cutoff:
                    shutil.rmtree(d)
            except (ValueError, OSError):
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
        sign = "-" if v < 0 else ""
        a = abs(v)
        if a >= 1e8:
            return f"{sign}{a/1e8:.2f}亿"
        if a >= 1e4:
            return f"{sign}{a/1e4:.2f}万"
        return f"{sign}{a:.0f}"
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

def _fetch_raw(url: str, headers: dict[str, str] | None = None, timeout: int = 15) -> str:
    return _fetch_text(url, headers=headers, timeout=timeout)


def _fetch_text(
    url: str,
    headers: dict[str, str] | None = None,
    timeout: int = 15,
    encoding: str = "utf-8",
) -> str:
    default_headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json,text/html,*/*",
    }
    if headers:
        default_headers.update(headers)
    req = urllib.request.Request(url, headers=default_headers)
    # 绕过本地代理（Clash 等会拦截东财 API 返 502）
    proxy_handler = urllib.request.ProxyHandler({})
    opener = urllib.request.build_opener(proxy_handler)
    with opener.open(req, timeout=timeout) as resp:
        return resp.read().decode(encoding, errors="ignore")


def fetch_json(url: str, headers: dict[str, str] | None = None) -> dict[str, Any]:
    started = time.monotonic()
    try:
        raw = _fetch_raw(url, headers)
    except Exception as e:
        SOURCE_HEALTH.record(_source_from_url(url), ok=False, latency_ms=(time.monotonic() - started) * 1000)
        return {"_error": str(e)}
    SOURCE_HEALTH.record(_source_from_url(url), ok=True, latency_ms=(time.monotonic() - started) * 1000)
    return _parse_json_text(raw)


def _source_from_url(url: str) -> str:
    host = urllib.parse.urlparse(url).netloc.lower()
    if "eastmoney" in host:
        return "eastmoney"
    if "sina" in host:
        return "sina"
    if "gtimg" in host or "qq.com" in host:
        return "tencent"
    if "10jqka" in host:
        return "ths"
    if "futunn" in host:
        return "futu"
    return host or "unknown"


def _parse_json_text(raw: str) -> dict[str, Any]:
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


def fetch_fund_flow_json(url: str) -> dict[str, Any]:
    """资金流接口对 Python 直连较挑剔，单独放宽请求策略。"""
    headers = {"Referer": "https://quote.eastmoney.com/"}
    data = fetch_json(url, headers)
    if "_error" not in data:
        return data
    errors = [data["_error"]]

    try:
        import requests

        resp = requests.get(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": "application/json,text/plain,*/*",
                "Referer": "https://quote.eastmoney.com/",
            },
            timeout=15,
        )
        resp.raise_for_status()
        return _parse_json_text(resp.text)
    except Exception as e:
        errors.append(str(e))

    curl = shutil.which("curl")
    if curl:
        try:
            result = subprocess.run(
                [
                    curl,
                    "--noproxy", "*",
                    "-sS",
                    "--max-time", "15",
                    "-H", "Referer: https://quote.eastmoney.com/",
                    "-H", "Accept: application/json,text/plain,*/*",
                    url,
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            if result.returncode == 0 and result.stdout:
                return _parse_json_text(result.stdout)
            errors.append(result.stderr.strip() or f"curl exited {result.returncode}")
        except Exception as e:
            errors.append(str(e))

    return {"_error": " | ".join(e for e in errors if e)}


def fetch_market_fund_flow_snapshot(date_str: str) -> dict[str, str]:
    """东财资金流页面的实时资金指标。fflow 断连时作为在线替代源。"""
    url = FFLOW_MARKET_URL.format(fields=FFLOW_MARKET_FIELDS, ts=int(datetime.now().timestamp() * 1000))
    data = fetch_json(url, {"Referer": "https://data.eastmoney.com/zjlx/default.html"})
    if "_error" in data:
        diag(f"Eastmoney market fund-flow snapshot: {data['_error']}")
        return {}

    rows = _normalize_diff((data.get("data") or {}).get("diff"))
    if not rows:
        diag("Eastmoney market fund-flow snapshot: empty diff")
        return {}

    totals: dict[str, float] = defaultdict(float)
    latest_ts = 0
    for row in rows:
        for key in ("f62", "f66", "f72", "f78", "f84", "f6"):
            value = _safe_float(row.get(key))
            if value is not None:
                totals[key] += value
        ts = _safe_int(row.get("f124")) or 0
        latest_ts = max(latest_ts, ts)

    turnover = totals.get("f6") or 0

    def pct(amount: float) -> str:
        return str(amount / turnover * 100) if turnover else ""

    trade_date = _display_date(date_str)
    if latest_ts:
        trade_date = datetime.fromtimestamp(latest_ts).strftime("%Y-%m-%d")

    result = {
        "date": trade_date,
        "主力净流入": str(totals.get("f62", 0)),
        "小单净流入": str(totals.get("f84", 0)),
        "中单净流入": str(totals.get("f78", 0)),
        "大单净流入": str(totals.get("f72", 0)),
        "超大单净流入": str(totals.get("f66", 0)),
        "主力净流入占比": pct(totals.get("f62", 0)),
        "小单净流入占比": pct(totals.get("f84", 0)),
        "中单净流入占比": pct(totals.get("f78", 0)),
        "大单净流入占比": pct(totals.get("f72", 0)),
        "超大单净流入占比": pct(totals.get("f66", 0)),
        "总成交额": str(turnover),
        "_source": "东财资金流页面实时指标",
        "_scope": "A股",
    }
    if result["date"].replace("-", "") != date_str:
        result["_requested_date"] = _display_date(date_str)
        result["_date_note"] = "latest_available"
    return result


def _parse_ths_money_flow_table(raw_html: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    tbody_match = re.search(r"<tbody>(.*?)</tbody>", raw_html, re.DOTALL | re.IGNORECASE)
    tbody = tbody_match.group(1) if tbody_match else raw_html
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", tbody, re.DOTALL | re.IGNORECASE):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.DOTALL | re.IGNORECASE)
        if len(cells) < 11:
            continue
        text_cells = [_html_to_text(cell) for cell in cells]
        concept = text_cells[1]
        if not concept or concept in {"行业", "概念"}:
            continue
        rows.append(
            {
                "rank": _safe_int(text_cells[0]),
                "name": concept,
                "index": _safe_float(text_cells[2]),
                "change_pct": _safe_number(text_cells[3]),
                "buy": _safe_number(text_cells[4]),
                "sell": _safe_number(text_cells[5]),
                "net": _safe_number(text_cells[6]),
                "companies": _safe_int(text_cells[7]),
                "leader": text_cells[8],
                "leader_change_pct": _safe_number(text_cells[9]),
                "leader_price": _safe_number(text_cells[10]),
            }
        )
    return rows


def fetch_ths_concept_money_flow_snapshot(date_str: str) -> dict[str, str]:
    """同花顺概念资金流。页面可直接返回表格，作为优先在线源。"""
    cached = cache_load("fund_flow", date_str, "ths", ttl=CACHE_TTL_SECONDS)
    if cached:
        try:
            cached_in = json.loads(cached.get("_concept_in", "[]"))
            cached_out = json.loads(cached.get("_concept_out", "[]"))
        except json.JSONDecodeError:
            cached_in, cached_out = [], []
        if cached_in and cached_out:
            return cached
        diag("Ignored THS concept flow cache without two-sided net flow")
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Referer": "http://data.10jqka.com.cn/",
    }
    try:
        req = urllib.request.Request(THS_CONCEPT_MONEY_FLOW_URL, headers=headers)
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(req, timeout=12) as resp:
            raw = resp.read().decode("gbk", errors="ignore")
    except Exception as e:
        diag(f"THS concept money-flow snapshot: {e}")
        return {}

    if "Nginx forbidden" in raw or "Forbidden" in raw:
        diag("THS concept money-flow snapshot: forbidden")
        return {}
    rows = _parse_ths_money_flow_table(raw)
    if not rows:
        diag("THS concept money-flow snapshot: empty table")
        return {}
    top_in_rows = sorted([row for row in rows if float(row.get("net") or 0) > 0], key=lambda item: float(item.get("net") or 0), reverse=True)[:5]
    top_out_rows = sorted([row for row in rows if float(row.get("net") or 0) < 0], key=lambda item: float(item.get("net") or 0))[:5]
    if not top_in_rows or not top_out_rows:
        diag("THS concept money-flow snapshot: missing two-sided net flow")
        return {}
    trade_date = _display_date(nearest_trade_date())
    result = {
        "date": trade_date,
        "_source": "同花顺概念资金流",
        "_scope": "A股",
        "_fallback_indicator": "concept_money_flow",
        "_indicator_note": "以下为同花顺概念板块资金流，反映概念方向净额，不等同于全市场主力资金净流入。",
        "_concept_in": json.dumps(top_in_rows, ensure_ascii=False),
        "_concept_out": json.dumps(top_out_rows, ensure_ascii=False),
    }
    if result["date"].replace("-", "") != date_str:
        result["_requested_date"] = _display_date(date_str)
        result["_date_note"] = "latest_available"
    cache_save("fund_flow", date_str, "ths", result)
    return result


def fetch_browser_fund_flow_snapshot(date_str: str) -> dict[str, str]:
    raw = _playwright_html(THS_CONCEPT_MONEY_FLOW_URL)
    if not raw:
        return {}
    rows = _parse_ths_money_flow_table(raw)
    top_in_rows = sorted(
        [row for row in rows if float(row.get("net") or 0) > 0],
        key=lambda item: float(item.get("net") or 0),
        reverse=True,
    )[:5]
    top_out_rows = sorted(
        [row for row in rows if float(row.get("net") or 0) < 0],
        key=lambda item: float(item.get("net") or 0),
    )[:5]
    if not top_in_rows or not top_out_rows:
        return {}
    return {
        "date": _display_date(nearest_trade_date()),
        "_source": "公开财经页面概念资金流",
        "_scope": "A股",
        "_fallback_indicator": "concept_money_flow",
        "_concept_in": json.dumps(top_in_rows, ensure_ascii=False),
        "_concept_out": json.dumps(top_out_rows, ensure_ascii=False),
    }


def _market_activity_snapshot(rows: list[dict[str, Any]], source: str, date_str: str) -> dict[str, str]:
    usable = [r for r in rows if r.get("f12") in {"000001", "399001"}]
    if not usable:
        return {}
    total_turnover = sum(float(r.get("f6") or 0) for r in usable)
    source_dates = [str(r.get("_source_date") or "") for r in usable if r.get("_source_date")]
    trade_date = source_dates[0] if source_dates else _display_date(nearest_trade_date())
    result: dict[str, str] = {
        "date": trade_date,
        "_source": source,
        "_scope": "A股",
        "_fallback_indicator": "market_activity",
        "_indicator_note": "当前在线资金流接口不可用，以下为A股指数行情活跃度参考，不等同于主力资金净流入。",
        "总成交额": str(total_turnover),
    }
    for row in usable:
        name = str(row.get("f14") or row.get("f12") or "")
        code = str(row.get("f12") or "")
        prefix = "上证指数" if code == "000001" else "深证成指"
        result[f"{prefix}点位"] = str(row.get("f2") or "")
        result[f"{prefix}涨跌幅"] = str(row.get("f3") or "")
        result[f"{prefix}成交额"] = str(row.get("f6") or "")
        result[f"{prefix}名称"] = name
    if result["date"].replace("-", "") != date_str:
        result["_requested_date"] = _display_date(date_str)
        result["_date_note"] = "latest_available"
    return result


def fetch_sina_market_activity_snapshot(date_str: str) -> dict[str, str]:
    """新浪A股指数行情：仅作为资金流接口失效时的在线活跃度参考。"""
    rows = _fetch_a_indices_sina()
    if not rows:
        diag("Sina market activity: empty indices")
        return {}
    return _market_activity_snapshot(rows, "新浪财经A股指数行情", date_str)


def fetch_tencent_market_activity_snapshot(date_str: str) -> dict[str, str]:
    """腾讯A股指数行情：仅作为资金流接口失效时的在线活跃度参考。"""
    rows = _fetch_a_indices_tencent()
    if not rows:
        diag("Tencent market activity: empty indices")
        return {}
    return _market_activity_snapshot(rows, "腾讯财经A股指数行情", date_str)


def fetch_sina_sector_money_flow_snapshot(date_str: str) -> dict[str, str]:
    """新浪资金流页面行业流向：在线参考源，不等同于全市场主力净流入。"""
    url = SINA_SECTOR_MONEY_FLOW_URL.format(ts=int(time.time() * 1000))
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://money.finance.sina.com.cn/moneyflow/"})
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(req, timeout=10) as resp:
            raw = resp.read().decode("gbk", errors="ignore")
    except Exception as e:
        diag(f"Sina sector money-flow snapshot: {e}")
        return {}
    data = _parse_json_text(raw)
    if "_error" in data:
        diag(f"Sina sector money-flow snapshot: {data['_error']}")
        return {}
    xml = str(data.get("xml") or "")
    labels = re.findall(r"<category label='([^']+)'", xml)
    values = [_safe_float(v) for v in re.findall(r"<set value='([^']+)'", xml)]
    pairs = [(label, value) for label, value in zip(labels, values) if value is not None]
    if not pairs:
        diag("Sina sector money-flow snapshot: empty sector values")
        return {}
    top_in = sorted(pairs, key=lambda x: x[1], reverse=True)[:5]
    top_out = sorted(pairs, key=lambda x: x[1])[:5]
    trade_date = _display_date(nearest_trade_date())
    result = {
        "date": trade_date,
        "_source": "新浪财经资金流页面行业流向",
        "_scope": "A股",
        "_fallback_indicator": "sector_money_flow",
        "_indicator_note": "东财全市场资金流暂不可用，以下为新浪行业资金流参考，不等同于全市场主力资金净流入。",
        "_sector_in": json.dumps(top_in, ensure_ascii=False),
        "_sector_out": json.dumps(top_out, ensure_ascii=False),
    }
    if result["date"].replace("-", "") != date_str:
        result["_requested_date"] = _display_date(date_str)
        result["_date_note"] = "latest_available"
    return result


def _display_date(date_str: str) -> str:
    return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"


def _source_date(value: str | None) -> str:
    if not value:
        return ""
    value = str(value).strip().replace("/", "-")
    m = re.match(r"(\d{4}-\d{2}-\d{2})", value)
    return m.group(1) if m else value


def _tencent_source_date(value: str | None, date_str: str) -> str:
    value = str(value or "").strip()
    if not value:
        return _display_date(date_str)
    if re.match(r"\d{4}/\d{2}/\d{2}", value):
        return _source_date(value)
    if re.match(r"\d{4}-\d{2}-\d{2}", value):
        return _source_date(value)
    if re.match(r"\d{14}$", value):
        return f"{value[:4]}-{value[4:6]}-{value[6:8]}"
    return _display_date(date_str)


def session_stage_label(dt: datetime | None = None, *, data_date: str | None = None, requested_date: str | None = None) -> str:
    """返回股民更容易理解的行情阶段。历史/非请求日数据按盘后展示。"""
    if data_date and requested_date and data_date.replace("-", "") != requested_date:
        return "交易日盘后"
    if dt is None:
        dt = datetime.now()
    minutes = dt.hour * 60 + dt.minute
    if 9 * 60 + 30 <= minutes < 11 * 60 + 30:
        return "上午盘"
    if 11 * 60 + 30 <= minutes < 13 * 60:
        return "午间"
    if 13 * 60 <= minutes < 15 * 60:
        return "下午盘"
    return "盘后"


def dated_stage_label(data_date: str | None = None, requested_date: str | None = None, dt: datetime | None = None) -> str:
    stage = session_stage_label(dt, data_date=data_date, requested_date=requested_date)
    date_part = data_date or (_display_date(requested_date) if requested_date else "")
    return f"{date_part} {stage}".strip()


def print_stage_line(requested_date: str, data_date: str | None = None) -> None:
    stage = dated_stage_label(data_date=data_date, requested_date=requested_date)
    if data_date and data_date.replace("-", "") != requested_date:
        print(f"当前阶段: {stage}（展示的是 {data_date} 数据，本次请求 {_display_date(requested_date)}）\n")
    else:
        print(f"当前阶段: {stage}\n")


# ------------------------------------------------------------------
# 东财数据解析工具
# ------------------------------------------------------------------

def _normalize_diff(data_diff: Any) -> list[dict[str, Any]]:
    """东财 diff 有时是数组，有时是对象（clist 返回 {\"0\":{}, \"1\":{}}）"""
    if data_diff is None:
        return []
    if isinstance(data_diff, list):
        return data_diff
    if isinstance(data_diff, dict):
        return [data_diff[k] for k in sorted(data_diff.keys(), key=lambda x: int(x) if str(x).isdigit() else x)]
    return []


def _safe_float(v: Any) -> float | None:
    if v is None or v == "" or v == "-":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _safe_int(v: Any) -> int | None:
    if v is None or v == "" or v == "-":
        return None
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def _em_clist_price(v: Any) -> float | None:
    """clist/get?fltt=2 已直接返回真实价（带小数），无需缩放。"""
    return _safe_float(v)


def _em_item_to_quote(item: dict[str, Any], symbol: str, market_type: str, date_str: str) -> QuoteData:
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
def eastmoney_clist(fs_filter: str, fields: str = EM_CLIST_FIELDS, pz: int = 200, date_str: str = "") -> list[dict[str, Any]]:
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


def fetch_em_indices(symbols_map: dict[str, str], date_str: str, market_fs: str) -> list[QuoteData]:
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


def fetch_em_stocks(codes: list[str], date_str: str, market_fs: str) -> list[QuoteData]:
    """通过东财 clist 获取个股，批量查询后本地过滤"""
    all_data = eastmoney_clist(market_fs, pz=500, date_str=date_str)
    results = []

    # 构建查找表（支持 0700 / 00700 等变体）
    lookup: dict[str, dict[str, Any]] = {}
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
# 单只直查（stock/get）—— 大票按代码精准查询，绕开 clist 排序窗口限制
# ------------------------------------------------------------------

EM_STOCK_GET_URL = (
    "https://push2.eastmoney.com/api/qt/stock/get"
    "?fltt=2&secid={secid}&fields={fields}&_={ts}"
)


def _hk_secid(code: str) -> str:
    """港股 secid: 116.<5位补零代码>"""
    raw = code.upper().replace(".HK", "").lstrip("0") or "0"
    return f"116.{raw.zfill(5)}"


def _cn_secid(code: str) -> str:
    """A股 secid: 沪市 1.<code>，深市/北交所 0.<code>。"""
    raw = code.upper().replace(".SH", "").replace(".SZ", "").replace(".BJ", "")
    exchange = "1" if raw.startswith(("5", "6", "9")) else "0"
    return f"{exchange}.{raw}"


def _us_secid(symbol: str) -> str | None:
    """美股 secid: 优先查表，否则返回 None（让上层尝试 105/106 探测）。"""
    s = symbol.upper().lstrip("^")
    return EM_US_SECID.get(s)


def resolve_global_stock_secid(symbol: str, market_type: str) -> tuple[str, str] | None:
    """Resolve US/HK secid through Eastmoney searchapi when static maps are not enough."""
    raw = symbol.upper().replace(".HK", "")
    queries = [raw]
    if market_type == "hk_market":
        queries.extend([raw.lstrip("0") or "0", raw.zfill(5)])
        wanted_markets = {"116"}
    elif market_type == "us_market":
        wanted_markets = {"105", "106", "107"}
    else:
        return None

    for query in dict.fromkeys(queries):
        params = {
            "input": query,
            "type": 14,
            "token": EM_SEARCH_TOKEN,
            "count": 10,
        }
        url = f"{EM_SEARCH_URL}?{urllib.parse.urlencode(params)}"
        data = fetch_json(url, {"Referer": "https://quote.eastmoney.com/"})
        suggestions = ((data.get("QuotationCodeTable") or {}).get("Data") or []) if isinstance(data, dict) else []
        for item in suggestions:
            mkt = str(item.get("MktNum") or "")
            code = str(item.get("Code") or "").upper()
            if mkt not in wanted_markets or not code:
                continue
            if market_type == "hk_market" and code.lstrip("0") != raw.lstrip("0"):
                continue
            if market_type == "us_market" and code != raw:
                continue
            return f"{mkt}.{code}", str(item.get("Name") or "")
    return None


def _stock_flow_secid_candidates(symbol: str, market: str) -> list[str]:
    if market == "cn_market":
        return [_cn_secid(symbol)]
    if market == "hk_market":
        resolved = resolve_global_stock_secid(symbol, market)
        return [secid for secid in dict.fromkeys([resolved[0] if resolved else "", _hk_secid(symbol)]) if secid]
    if market == "us_market":
        mapped = _us_secid(symbol)
        raw = symbol.upper()
        resolved = resolve_global_stock_secid(symbol, market)
        candidates = [mapped] if mapped else []
        if resolved:
            candidates.append(resolved[0])
        candidates.extend([f"105.{raw}", f"106.{raw}", f"107.{raw}"])
        return [secid for secid in dict.fromkeys(candidates) if secid]
    raise ValueError(f"暂不支持该市场的资金流: {market}")


@retry_on_recoverable(max_retries=MAX_RETRIES, initial_delay=INITIAL_BACKOFF)
def fetch_em_stock_get(secid: str) -> dict[str, Any]:
    """调用 stock/get 单查接口，返回 data dict 或 {}"""
    url = EM_STOCK_GET_URL.format(
        secid=secid, fields=EM_STOCK_GET_FIELDS, ts=int(datetime.now().timestamp() * 1000)
    )
    data = fetch_json(url, {"Referer": "https://quote.eastmoney.com/"})
    if "_error" in data:
        diag(f"Eastmoney stock/get {secid}: {data['_error']}")
        return {}
    payload = data.get("data") or {}
    # 价格为 "-" 表示无效（未上市/secid 错）
    if payload.get("f43") in (None, "-"):
        return {}
    return payload


def _stock_get_to_quote(payload: dict[str, Any], symbol: str, market_type: str, date_str: str) -> QuoteData:
    """stock/get 字段 → QuoteData（fltt=2 已是真实价，不缩放）"""
    currency = "USD" if market_type == "us_market" else ("HKD" if market_type == "hk_market" else "CNY")
    qd = QuoteData(
        symbol=symbol,
        name=str(payload.get("f58") or symbol),
        market=market_type,
        date=date_str,
        price=_safe_float(payload.get("f43")),
        prev_close=_safe_float(payload.get("f60")),
        change=_safe_float(payload.get("f169")),
        change_pct=_safe_float(payload.get("f170")),
        open_price=_safe_float(payload.get("f46")),
        high=_safe_float(payload.get("f44")),
        low=_safe_float(payload.get("f45")),
        volume=_safe_int(payload.get("f47")),
        turnover=_safe_float(payload.get("f48")),
        currency=currency,
        source="eastmoney_stock_get",
    )
    return validate_quote(qd)


def fetch_us_stocks_direct(symbols: list[str], date_str: str) -> list[QuoteData]:
    """逐个用 stock/get 查美股，未知 symbol 自动尝试 105→106→107。"""
    results: list[QuoteData] = []
    for sym in symbols:
        secid = _us_secid(sym)
        resolved_name = ""
        if not secid:
            resolved = resolve_global_stock_secid(sym, "us_market")
            if resolved:
                secid, resolved_name = resolved
        payload: dict[str, Any] = {}
        if secid:
            payload = fetch_em_stock_get(secid)
        if not payload:
            # fallback: 探测三大交易所前缀
            for prefix in ("105", "106", "107"):
                payload = fetch_em_stock_get(f"{prefix}.{sym.upper()}")
                if payload:
                    break
        if not payload:
            diag(f"Eastmoney stock/get missing: {sym}")
            continue
        qd = _stock_get_to_quote(payload, sym, "us_market", date_str)
        if resolved_name:
            qd.name = resolved_name
        results.append(qd)
    return results


def fetch_hk_stocks_direct(symbols: list[str], date_str: str) -> list[QuoteData]:
    """逐个用 stock/get 查港股（secid=116.<5位补零>）。"""
    results: list[QuoteData] = []
    for sym in symbols:
        resolved = resolve_global_stock_secid(sym, "hk_market")
        secid = resolved[0] if resolved else _hk_secid(sym)
        payload = fetch_em_stock_get(secid)
        if not payload:
            diag(f"Eastmoney stock/get missing HK: {sym}")
            continue
        qd = _stock_get_to_quote(payload, sym, "hk_market", date_str)
        if resolved and resolved[1]:
            qd.name = resolved[1]
        results.append(qd)
    return results


def fetch_cn_stocks_direct(symbols: list[str], date_str: str) -> list[QuoteData]:
    """逐个用 stock/get 查 A股，作为新浪不可用时的精确兜底。"""
    results: list[QuoteData] = []
    for sym in symbols:
        payload = fetch_em_stock_get(_cn_secid(sym))
        if not payload:
            diag(f"Eastmoney stock/get missing A-share: {sym}")
            continue
        results.append(_stock_get_to_quote(payload, sym, "cn_market", date_str))
    return results


def fetch_indices_direct(symbols_map: dict[str, str], date_str: str, secid_map: dict[str, str]) -> list[QuoteData]:
    """用 stock/get 单查指数（绕开 clist 反爬/排序问题）。"""
    results: list[QuoteData] = []
    market = "us_market" if any(v.startswith("100.SPX") or v.startswith("100.NDX") or v.startswith("100.DJIA") for v in secid_map.values()) else "hk_market"
    for sym, name in symbols_map.items():
        secid = secid_map.get(sym)
        if not secid:
            diag(f"No secid for index {sym}")
            continue
        payload = fetch_em_stock_get(secid)
        if not payload:
            continue
        qd = _stock_get_to_quote(payload, sym, market, date_str)
        qd.name = name  # 用中文名覆盖
        results.append(qd)
    return results


# ------------------------------------------------------------------
# 新浪财经数据源 —— 美股/港股主路径，免登录、批量、抗风控
# ------------------------------------------------------------------

# 新浪 symbol 映射
SINA_US_INDEX = {
    "^GSPC": "gb_$inx",
    "^IXIC": "gb_$ixic",
    "^DJI":  "gb_$dji",
}


def _sina_a_code(symbol: str) -> str:
    """A股 600519 / 000001.SZ → sh600519 / sz000001。"""
    raw = symbol.upper().replace(".SH", "").replace(".SZ", "").replace(".BJ", "")
    if raw.startswith(("5", "6", "9")):
        return f"sh{raw}"
    if raw.startswith(("4", "8")):
        return f"bj{raw}"
    return f"sz{raw}"


def _sina_us_code(symbol: str) -> str:
    """美股 AAPL → gb_aapl"""
    return f"gb_{symbol.lower().lstrip('^')}"


def _sina_hk_code(symbol: str) -> str:
    """港股 0700.HK / 00700 / 700 → rt_hk00700"""
    raw = symbol.upper().replace(".HK", "").lstrip("0") or "0"
    return f"rt_hk{raw.zfill(5)}"


@retry_on_recoverable(max_retries=MAX_RETRIES, initial_delay=INITIAL_BACKOFF)
def fetch_sina_batch(codes: list[str]) -> dict[str, list[str]]:
    """批量拉新浪行情，返回 {sina_code: [field, ...]}。一次最多 ~80 个 symbol。"""
    if not codes:
        return {}
    url = SINA_HQ_URL.format(codes=",".join(codes))
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0",
            "Referer": "https://finance.sina.com.cn/",
        })
        proxy_handler = urllib.request.ProxyHandler({})
        opener = urllib.request.build_opener(proxy_handler)
        with opener.open(req, timeout=15) as resp:
            raw = resp.read().decode("gbk", errors="ignore")
    except Exception as e:
        diag(f"Sina batch: {e}")
        return {}

    out: dict[str, list[str]] = {}
    for line in raw.splitlines():
        m = re.match(r'var hq_str_([^=]+)="(.*)";?\s*$', line.strip())
        if not m:
            continue
        code, payload = m.group(1), m.group(2)
        if not payload:
            continue
        out[code] = payload.split(",")
    return out


def _sina_a_to_quote(fields: list[str], symbol: str, date_str: str) -> QuoteData | None:
    """新浪 A股字段：[名称, 开盘, 昨收, 当前价, 最高, 最低, 买一, 卖一, 成交量, 成交额, ... 日期, 时间]。"""
    if len(fields) < 32:
        return None
    price = _safe_float(fields[3])
    prev_close = _safe_float(fields[2])
    change = None
    change_pct = None
    if price is not None and prev_close not in (None, 0):
        change = price - float(prev_close)
        change_pct = change / float(prev_close) * 100
    qd = QuoteData(
        symbol=symbol,
        name=fields[0] or symbol,
        market="cn_market",
        date=_source_date(fields[30]) or _display_date(date_str),
        price=price,
        prev_close=prev_close,
        change=change,
        change_pct=change_pct,
        open_price=_safe_float(fields[1]),
        high=_safe_float(fields[4]),
        low=_safe_float(fields[5]),
        volume=_safe_int(fields[8]),
        turnover=_safe_float(fields[9]),
        currency="CNY",
        source="sina",
    )
    return validate_quote(qd)


def _sina_us_to_quote(fields: list[str], symbol: str, date_str: str, name_override: str | None = None) -> QuoteData | None:
    """新浪美股字段：[名称, 当前价, 涨跌幅%, 时间, 涨跌额, 开盘, 最高, 最低, 52周高, 52周低, 成交量, ...]"""
    if len(fields) < 11:
        return None
    qd = QuoteData(
        symbol=symbol,
        name=name_override or fields[0] or symbol,
        market="us_market",
        date=_display_date(date_str),
        price=_safe_float(fields[1]),
        change_pct=_safe_float(fields[2]),
        change=_safe_float(fields[4]),
        open_price=_safe_float(fields[5]),
        high=_safe_float(fields[6]),
        low=_safe_float(fields[7]),
        volume=_safe_int(fields[10]),
        currency="USD",
        source="sina",
    )
    # 昨收：当前价 - 涨跌额
    if qd.price is not None and qd.change is not None:
        qd.prev_close = qd.price - qd.change
    return validate_quote(qd)


def _sina_hk_to_quote(fields: list[str], symbol: str, date_str: str) -> QuoteData | None:
    """新浪港股字段：[en_name, cn_name, 开盘, 昨收, 最高, 最低, 当前价, 涨跌额, 涨跌幅%, 买一, 卖一, 成交额(港币), 成交量(股), ...]"""
    if len(fields) < 13:
        return None
    qd = QuoteData(
        symbol=symbol,
        name=fields[1] or fields[0] or symbol,
        market="hk_market",
        date=_source_date(fields[17] if len(fields) > 17 else "") or _display_date(date_str),
        price=_safe_float(fields[6]),
        prev_close=_safe_float(fields[3]),
        change=_safe_float(fields[7]),
        change_pct=_safe_float(fields[8]),
        open_price=_safe_float(fields[2]),
        high=_safe_float(fields[4]),
        low=_safe_float(fields[5]),
        volume=_safe_int(fields[12]),
        turnover=_safe_float(fields[11]),
        currency="HKD",
        source="sina",
    )
    return validate_quote(qd)


def fetch_cn_stocks_sina(symbols: list[str], date_str: str) -> list[QuoteData]:
    """新浪批量拉 A股个股。"""
    codes = [_sina_a_code(s) for s in symbols]
    raw_map = fetch_sina_batch(codes)
    results: list[QuoteData] = []
    for sym in symbols:
        fields = raw_map.get(_sina_a_code(sym))
        if not fields:
            diag(f"Sina missing A-share: {sym}")
            continue
        qd = _sina_a_to_quote(fields, sym, date_str)
        if qd:
            results.append(qd)
    return results


def fetch_us_stocks_sina(symbols: list[str], date_str: str) -> list[QuoteData]:
    """新浪批量拉美股个股。"""
    codes = [_sina_us_code(s) for s in symbols]
    raw_map = fetch_sina_batch(codes)
    results: list[QuoteData] = []
    for sym in symbols:
        fields = raw_map.get(_sina_us_code(sym))
        if not fields:
            diag(f"Sina missing US: {sym}")
            continue
        qd = _sina_us_to_quote(fields, sym, date_str)
        if qd:
            results.append(qd)
    return results


def fetch_hk_stocks_sina(symbols: list[str], date_str: str) -> list[QuoteData]:
    """新浪批量拉港股个股。"""
    codes = [_sina_hk_code(s) for s in symbols]
    raw_map = fetch_sina_batch(codes)
    results: list[QuoteData] = []
    for sym in symbols:
        fields = raw_map.get(_sina_hk_code(sym))
        if not fields:
            diag(f"Sina missing HK: {sym}")
            continue
        qd = _sina_hk_to_quote(fields, sym, date_str)
        if qd:
            results.append(qd)
    return results


def fetch_us_indices_sina(symbols_map: dict[str, str], date_str: str) -> list[QuoteData]:
    """新浪批量拉美股指数。"""
    codes = [SINA_US_INDEX[s] for s in symbols_map if s in SINA_US_INDEX]
    raw_map = fetch_sina_batch(codes)
    results: list[QuoteData] = []
    for sym, name in symbols_map.items():
        code = SINA_US_INDEX.get(sym)
        if not code:
            continue
        fields = raw_map.get(code)
        if not fields:
            diag(f"Sina missing index: {sym}")
            continue
        qd = _sina_us_to_quote(fields, sym, date_str, name_override=name)
        if qd:
            results.append(qd)
    return results


def fetch_hk_indices_sina(symbols_map: dict[str, str], date_str: str) -> list[QuoteData]:
    """新浪批量拉港股指数。
    hkHSI / hkHSCEI / hkHSTECH → 13 字段标准版（同 rt_hk 格式）。
    """
    code_map = {
        "^HSI":      "hkHSI",
        "^HSCE":     "hkHSCEI",
        "HSTECH.HK": "hkHSTECH",
    }
    codes = [code_map[s] for s in symbols_map if s in code_map]
    raw_map = fetch_sina_batch(codes)
    results: list[QuoteData] = []
    for sym, name in symbols_map.items():
        code = code_map.get(sym)
        if not code:
            continue
        fields = raw_map.get(code)
        if not fields:
            diag(f"Sina missing HK index: {sym}")
            continue
        qd = _sina_hk_to_quote(fields, sym, date_str)
        if qd:
            qd.name = name
            results.append(qd)
    return results


# ------------------------------------------------------------------
# 腾讯财经数据源 —— 港股指数收盘口径 / 美股指数 / A股指数备用
# ------------------------------------------------------------------

TENCENT_US_INDEX = {
    "^GSPC": "usINX",
    "^IXIC": "usIXIC",
    "^DJI":  "usDJI",
}

TENCENT_HK_INDEX = {
    "^HSI":      "hkHSI",
    "^HSCE":     "hkHSCEI",
    "HSTECH.HK": "hkHSTECH",
}

TENCENT_A_INDEX_MAP = {
    "sh000001": "000001",
    "sz399001": "399001",
    "sz399006": "399006",
    "sh000300": "000300",
    "sh000688": "000688",
    "sz399005": "399005",
    "bj899050": "899050",
}


@retry_on_recoverable(max_retries=MAX_RETRIES, initial_delay=INITIAL_BACKOFF)
def fetch_tencent_batch(codes: list[str]) -> str:
    """批量拉腾讯行情原文；调用方按市场解析字段。"""
    if not codes:
        return ""
    url = TENCENT_QUOTE_URL.format(codes=",".join(codes))
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0",
            "Referer": "https://gu.qq.com/",
        })
        proxy_handler = urllib.request.ProxyHandler({})
        opener = urllib.request.build_opener(proxy_handler)
        with opener.open(req, timeout=15) as resp:
            return resp.read().decode("gbk", errors="ignore")
    except Exception as e:
        diag(f"Tencent quote: {e}")
        return ""


def _parse_tencent_batch(raw: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for line in raw.splitlines():
        m = re.match(r'v_([^=]+)="(.*)";?\s*$', line.strip())
        if not m:
            continue
        code, payload = m.group(1), m.group(2)
        if payload:
            out[code] = payload.split("~")
    return out


def _tencent_index_to_quote(fields: list[str], symbol: str, name: str, market: str, date_str: str) -> QuoteData | None:
    if len(fields) < 35:
        return None
    turnover = None
    volume = _safe_int(fields[6])
    if market == "hk_market":
        # 腾讯港股指数第 6 字段是成交额，单位为万港元。
        raw_turnover = _safe_float(fields[6])
        turnover = raw_turnover * 1e4 if raw_turnover is not None else None
        volume = None
    qd = QuoteData(
        symbol=symbol,
        name=name or fields[1] or symbol,
        market=market,
        date=date_str,
        price=_safe_float(fields[3]),
        prev_close=_safe_float(fields[4]),
        change=_safe_float(fields[31]),
        change_pct=_safe_float(fields[32]),
        open_price=_safe_float(fields[5]),
        high=_safe_float(fields[33]),
        low=_safe_float(fields[34]),
        volume=volume,
        turnover=turnover,
        currency="HKD" if market == "hk_market" else "USD",
        source="tencent",
    )
    if market == "hk_market":
        qd.notes.append("港股指数采用腾讯收盘口径，和新浪盘后快照可能略有差异")
    return validate_quote(qd)


def fetch_hk_indices_tencent(symbols_map: dict[str, str], date_str: str) -> list[QuoteData]:
    codes = [TENCENT_HK_INDEX[s] for s in symbols_map if s in TENCENT_HK_INDEX]
    raw_map = _parse_tencent_batch(fetch_tencent_batch(codes))
    results: list[QuoteData] = []
    for sym, name in symbols_map.items():
        code = TENCENT_HK_INDEX.get(sym)
        if not code:
            continue
        fields = raw_map.get(code)
        if not fields:
            diag(f"Tencent missing HK index: {sym}")
            continue
        qd = _tencent_index_to_quote(fields, sym, name, "hk_market", date_str)
        if qd:
            results.append(qd)
    return results


def fetch_us_indices_tencent(symbols_map: dict[str, str], date_str: str) -> list[QuoteData]:
    codes = [TENCENT_US_INDEX[s] for s in symbols_map if s in TENCENT_US_INDEX]
    raw_map = _parse_tencent_batch(fetch_tencent_batch(codes))
    results: list[QuoteData] = []
    for sym, name in symbols_map.items():
        code = TENCENT_US_INDEX.get(sym)
        if not code:
            continue
        fields = raw_map.get(code)
        if not fields:
            diag(f"Tencent missing US index: {sym}")
            continue
        qd = _tencent_index_to_quote(fields, sym, name, "us_market", date_str)
        if qd:
            results.append(qd)
    return results


def _tencent_cn_code(symbol: str) -> str:
    raw = symbol.upper().replace(".SH", "").replace(".SZ", "").replace(".BJ", "")
    if raw.startswith(("5", "6", "9")):
        return f"sh{raw}"
    if raw.startswith(("4", "8")):
        return f"bj{raw}"
    return f"sz{raw}"


def _tencent_hk_code(symbol: str) -> str:
    raw = symbol.upper().replace(".HK", "").lstrip("0") or "0"
    return f"r_hk{raw.zfill(5)}"


def _tencent_us_code(symbol: str) -> str:
    return f"us{symbol.upper().lstrip('^')}"


def _tencent_stock_to_quote(fields: list[str], symbol: str, market: str, date_str: str) -> QuoteData | None:
    if len(fields) < 45:
        return None
    currency = {"cn_market": "CNY", "hk_market": "HKD", "us_market": "USD"}.get(market, "USD")
    turnover = _safe_float(fields[37] if len(fields) > 37 else None)
    if market == "cn_market" and turnover is not None:
        turnover *= 1e4  # A股腾讯字段为万元
    qd = QuoteData(
        symbol=symbol,
        name=str(fields[1] or symbol),
        market=market,
        date=_tencent_source_date(fields[30] if len(fields) > 30 else "", date_str),
        price=_safe_float(fields[3]),
        prev_close=_safe_float(fields[4]),
        change=_safe_float(fields[31] if len(fields) > 31 else None),
        change_pct=_safe_float(fields[32] if len(fields) > 32 else None),
        open_price=_safe_float(fields[5]),
        high=_safe_float(fields[33] if len(fields) > 33 else None),
        low=_safe_float(fields[34] if len(fields) > 34 else None),
        volume=_safe_int(fields[6]),
        turnover=turnover,
        turnover_rate=_safe_float(fields[38] if len(fields) > 38 else None),
        market_cap=_safe_float(fields[44] if len(fields) > 44 else None),
        float_market_cap=_safe_float(fields[45] if len(fields) > 45 else None),
        pe=_safe_float(fields[39] if len(fields) > 39 else None),
        high_52w=_safe_float(fields[48] if len(fields) > 48 else None),
        low_52w=_safe_float(fields[49] if len(fields) > 49 else None),
        amplitude_pct=_safe_float(fields[43] if len(fields) > 43 else None),
        currency=currency,
        source="tencent",
    )
    if market == "cn_market":
        qd.pb = _safe_float(fields[46] if len(fields) > 46 else None)
        qd.high_52w = _safe_float(fields[47] if len(fields) > 47 else None)
        qd.low_52w = _safe_float(fields[48] if len(fields) > 48 else None)
    elif market == "hk_market":
        # 港股腾讯字段 58 为 PB；56/57 可能随标的含义变化，不作为 PB。
        qd.pb = _safe_float(fields[58] if len(fields) > 58 else None)
        if qd.turnover_rate == 0:
            qd.turnover_rate = None
    return validate_quote(qd)


def fetch_cn_stocks_tencent(symbols: list[str], date_str: str) -> list[QuoteData]:
    raw_map = _parse_tencent_batch(fetch_tencent_batch([_tencent_cn_code(s) for s in symbols]))
    results: list[QuoteData] = []
    for sym in symbols:
        fields = raw_map.get(_tencent_cn_code(sym))
        if not fields:
            diag(f"Tencent missing A-share: {sym}")
            continue
        qd = _tencent_stock_to_quote(fields, sym, "cn_market", date_str)
        if qd:
            results.append(qd)
    return results


def fetch_hk_stocks_tencent(symbols: list[str], date_str: str) -> list[QuoteData]:
    raw_map = _parse_tencent_batch(fetch_tencent_batch([_tencent_hk_code(s) for s in symbols]))
    results: list[QuoteData] = []
    for sym in symbols:
        fields = raw_map.get(_tencent_hk_code(sym))
        if not fields:
            diag(f"Tencent missing HK: {sym}")
            continue
        qd = _tencent_stock_to_quote(fields, sym, "hk_market", date_str)
        if qd:
            results.append(qd)
    return results


def fetch_us_stocks_tencent(symbols: list[str], date_str: str) -> list[QuoteData]:
    raw_map = _parse_tencent_batch(fetch_tencent_batch([_tencent_us_code(s) for s in symbols]))
    results: list[QuoteData] = []
    for sym in symbols:
        fields = raw_map.get(_tencent_us_code(sym))
        if not fields:
            diag(f"Tencent missing US: {sym}")
            continue
        qd = _tencent_stock_to_quote(fields, sym, "us_market", date_str)
        if qd:
            results.append(qd)
    return results


def _fetch_a_indices_tencent() -> list[dict[str, Any]]:
    raw_map = _parse_tencent_batch(fetch_tencent_batch(list(TENCENT_A_INDEX_MAP.keys())))
    result = []
    for tencent_code, em_code in TENCENT_A_INDEX_MAP.items():
        fields = raw_map.get(tencent_code)
        if not fields or len(fields) < 38:
            continue
        raw_amount = _safe_float(fields[37])
        result.append({
            "f12": em_code,
            "f14": fields[1],
            "f2": _safe_float(fields[3]),
            "f4": _safe_float(fields[31]),
            "f3": _safe_float(fields[32]),
            "f6": raw_amount * 1e4 if raw_amount is not None else None,
            "_source_date": _source_date(fields[30] if len(fields) > 30 else "") or "",
        })
    return result


def merge_quotes_by_symbol(primary: list[QuoteData], fallback: list[QuoteData], order: list[str]) -> list[QuoteData]:
    """保留主源已有报价，仅用备用源补齐缺失 symbol。"""
    lookup: dict[str, QuoteData] = {q.symbol.upper(): q for q in fallback}
    lookup.update({q.symbol.upper(): q for q in primary})
    return [lookup[s.upper()] for s in order if s.upper() in lookup]


def enrich_quotes_by_symbol(primary: list[QuoteData], supplemental: list[QuoteData], order: list[str]) -> list[QuoteData]:
    """保留主源价格口径，用补充源填充成交额、估值、市值等扩展字段。"""
    fallback = {q.symbol.upper(): q for q in supplemental}
    primary_lookup = {q.symbol.upper(): q for q in primary}
    enriched: list[QuoteData] = []
    enrich_fields = (
        "turnover",
        "turnover_rate",
        "market_cap",
        "float_market_cap",
        "pe",
        "pb",
        "high_52w",
        "low_52w",
        "amplitude_pct",
    )
    for sym in order:
        key = sym.upper()
        qd = primary_lookup.get(key) or fallback.get(key)
        if not qd:
            continue
        extra = fallback.get(key)
        if extra and qd is not extra:
            changed = False
            for field_name in enrich_fields:
                if getattr(qd, field_name, None) is None and getattr(extra, field_name, None) is not None:
                    setattr(qd, field_name, getattr(extra, field_name))
                    changed = True
            if changed:
                qd.notes.append("腾讯财经补充成交额/估值字段")
                validate_quote(qd)
        enriched.append(qd)
    return enriched


def _has_all_quotes(quotes: list[QuoteData], order: list[str]) -> bool:
    found = {q.symbol.upper() for q in quotes}
    return all(symbol.upper() in found for symbol in order)


# ------------------------------------------------------------------
# 数据验证
# ------------------------------------------------------------------

def validate_quote(qd: QuoteData) -> QuoteData:
    notes = []
    flags = []

    # 价格验证
    for attr, val in [("price", qd.price), ("open_price", qd.open_price), ("high", qd.high), ("low", qd.low)]:
        if val is not None and val <= 0:
            setattr(qd, attr, None)
            notes.append(f"{attr}异常已过滤")
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

    # 完整性评分：指数可用成交额替代成交量。
    has_activity = qd.volume is not None or qd.turnover is not None
    available = int(qd.price is not None) + int(has_activity)
    qd.completeness = (available / 2) * 100
    # 如果昨收存在再 +20 分
    if qd.prev_close is not None:
        qd.completeness = min(100, qd.completeness + 20)
    if qd.change_pct is not None:
        qd.completeness = min(100, qd.completeness + 20)

    qd.notes = [*qd.notes, *notes]
    qd.quality_flags = flags
    return qd


# ------------------------------------------------------------------
# 市场检测
# ------------------------------------------------------------------

def detect_market_type(ticker: str) -> str:
    t = str(ticker).upper()
    if t.endswith(".HK") or any(x in t for x in ["HSI", "HSCE", "HSTECH"]):
        return "hk_market"
    elif re.fullmatch(r"\d{6}", t) or t.endswith((".SH", ".SZ", ".BJ")) or any(x in t for x in ["上证", "深证", "创业板", "科创板", "399001", "899050", "000001"]):
        return "cn_market"
    elif any(x in t for x in ["DAX", "CAC", "FTSE", "ESTX", "GDAXI", "FCHI"]):
        return "eu_market"
    elif "NIKKEI" in t or t.endswith(".T") or t.endswith(".JP") or "N225" in t:
        return "jp_market"
    else:
        return "us_market"


def normalize_stock_symbol(symbol: str) -> tuple[str, str]:
    """把用户输入规范化为内部 symbol + 市场类型。"""
    raw = str(symbol).strip().upper()
    if not raw:
        raise ValueError("股票代码不能为空")

    if raw.endswith((".SH", ".SZ", ".BJ")):
        code = raw.rsplit(".", 1)[0]
        if re.fullmatch(r"\d{6}", code):
            return code, "cn_market"
        raise ValueError(f"无法识别的 A股代码: {symbol}")

    if raw.endswith(".HK"):
        code = raw[:-3].lstrip("0") or "0"
        if code.isdigit() and len(code) <= 5:
            return f"{code.zfill(4)}.HK", "hk_market"
        raise ValueError(f"无法识别的港股代码: {symbol}")

    if raw.isdigit():
        if len(raw) == 6:
            return raw, "cn_market"
        if 1 <= len(raw) <= 5:
            return f"{raw.lstrip('0').zfill(4)}.HK", "hk_market"
        raise ValueError(f"无法识别的股票代码: {symbol}")

    if re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,9}", raw):
        return raw, "us_market"

    raise ValueError(f"无法识别的股票代码: {symbol}")


# ------------------------------------------------------------------
# A股数据获取（东财）
# ------------------------------------------------------------------

@retry_on_recoverable(max_retries=MAX_RETRIES, initial_delay=INITIAL_BACKOFF)
def get_index(date_str: str) -> list[dict[str, Any]]:
    cached = cache_load("index_all", date_str, "eastmoney")
    if cached:
        cached_rows = cached.get("data")
        if isinstance(cached_rows, list):
            cached_codes = {str(row.get("f12") or "") for row in cached_rows if isinstance(row, dict)}
            expected_codes = {secid.split(".", 1)[1] for secid in INDEX_SECIDS.split(",") if "." in secid}
            if expected_codes.issubset(cached_codes):
                return cached_rows
            diag("Ignored cached A-share index because configured index list changed")
        else:
            diag("Ignored cached A-share index because data is not a list")

    url = INDEX_URL.format(secids=INDEX_SECIDS, fields=INDEX_FIELDS, ts=datetime.now().timestamp())
    data = fetch_json(url, {"Referer": "https://quote.eastmoney.com/"})
    if "_error" in data:
        diag(f"Eastmoney index: {data['_error']}")
    diff = data.get("data", {}).get("diff", []) if "_error" not in data else []
    result = diff if isinstance(diff, list) else []
    # 东财失败时降级到新浪
    if not result:
        result = _fetch_a_indices_sina()
        if result:
            diag("A-share index fell back to sina")
    if not result:
        result = _fetch_a_indices_tencent()
        if result:
            diag("A-share index fell back to tencent")
    if result:
        cache_save("index_all", date_str, "eastmoney", {"data": result})
    return result


# 新浪 A 股指数代码 → 模拟东财 diff 字段（f12=代码,f14=名称,f2=收盘,f3=涨跌幅,f4=涨跌,f6=成交额）
_SINA_A_INDEX_MAP = {
    "s_sh000001": "000001",
    "s_sz399001": "399001",
    "s_sz399006": "399006",
    "s_sh000300": "000300",
    "s_sh000688": "000688",
    "s_sz399005": "399005",
    "s_bj899050": "899050",
}


def _a_index_source_date(raw_map: dict[str, list[str]]) -> str:
    for fields in raw_map.values():
        for value in reversed(fields):
            date = _source_date(value)
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
                return date
    return ""


def _fetch_a_indices_sina() -> list[dict[str, Any]]:
    """从新浪拉 A 股主要指数，转成东财 diff 字段以复用 print_index。
    新浪格式: [名称, 价, 涨跌额, 涨跌幅%, 成交量(手), 成交额]
    成交额单位：sh/sz 前缀为万元；bj 前缀为元。
    注意：新浪指数成交额仅覆盖成份股，会比东财全口径偏小，仅作降级显示。
    """
    raw_map = fetch_sina_batch(list(_SINA_A_INDEX_MAP.keys()))
    result = []
    for sina_code, em_code in _SINA_A_INDEX_MAP.items():
        f = raw_map.get(sina_code)
        if not f or len(f) < 6:
            continue
        try:
            raw_amount = float(f[5])
            # bj 前缀单位是元，sh/sz 前缀单位是万元
            amount_yuan = raw_amount if sina_code.startswith("s_bj") else raw_amount * 1e4
        except (TypeError, ValueError):
            amount_yuan = None
        result.append({
            "f12": em_code,
            "f14": f[0],
            "f2": _safe_float(f[1]),
            "f4": _safe_float(f[2]),
            "f3": _safe_float(f[3]),
            "f6": amount_yuan,
            "_source_date": _a_index_source_date(raw_map),
        })
    return result


@retry_on_recoverable(max_retries=MAX_RETRIES, initial_delay=INITIAL_BACKOFF)
def get_zt_pool(date_str: str) -> dict[str, Any]:
    return _get_limit_pool("zt_pool", ZT_URL, date_str, "ZT")


@retry_on_recoverable(max_retries=MAX_RETRIES, initial_delay=INITIAL_BACKOFF)
def get_dt_pool(date_str: str) -> dict[str, Any]:
    return _get_limit_pool("dt_pool", DT_URL, date_str, "DT")


@retry_on_recoverable(max_retries=MAX_RETRIES, initial_delay=INITIAL_BACKOFF)
def get_zb_pool(date_str: str) -> dict[str, Any]:
    return _get_limit_pool("zb_pool", ZB_URL, date_str, "ZB")


LIMIT_POOL_CACHE_VERSION = 2


def _valid_limit_pool_payload(payload: dict[str, Any], date_str: str) -> bool:
    if not isinstance(payload, dict) or "_error" in payload:
        return False
    data = payload.get("data") or {}
    if not isinstance(data, dict):
        return False
    qdate = str(data.get("qdate") or "")
    if qdate and qdate != date_str:
        return False
    return "tc" in data or bool(data.get("pool"))


def _get_limit_pool(cache_name: str, url_template: str, date_str: str, label: str) -> dict[str, Any]:
    cached = cache_load(cache_name, date_str, "eastmoney")
    if cached and cached.get("_cache_version") == LIMIT_POOL_CACHE_VERSION and _valid_limit_pool_payload(cached, date_str):
        return cached
    data = fetch_json(url_template.format(date=date_str), {"Referer": "https://quote.eastmoney.com/"})
    if "_error" in data:
        diag(f"Eastmoney {label} pool: {data['_error']}")
        return data
    data = dict(data)
    data["_cache_version"] = LIMIT_POOL_CACHE_VERSION
    if _valid_limit_pool_payload(data, date_str):
        cache_save(cache_name, date_str, "eastmoney", data)
    return data


@retry_on_recoverable(max_retries=MAX_RETRIES, initial_delay=INITIAL_BACKOFF)
def get_fund_flow(date_str: str, *, strict_date: bool = True) -> dict[str, str]:
    ths_snapshot = fetch_ths_concept_money_flow_snapshot(date_str)
    if ths_snapshot:
        sector_snapshot = fetch_sina_sector_money_flow_snapshot(date_str)
        if sector_snapshot:
            ths_snapshot = dict(ths_snapshot)
            for key in ("_sector_in", "_sector_out"):
                if sector_snapshot.get(key):
                    ths_snapshot[key] = sector_snapshot[key]
            ths_source = ths_snapshot.get("_source")
            sector_source = sector_snapshot.get("_source")
            if ths_source and sector_source:
                ths_snapshot["_source"] = f"{ths_source} + {sector_source}"
            if sector_snapshot.get("_indicator_note") and not ths_snapshot.get("_sector_note"):
                ths_snapshot["_sector_note"] = sector_snapshot["_indicator_note"]
        return ths_snapshot

    cached = cache_load("fund_flow", date_str, "eastmoney")
    if cached:
        if cached.get("_unavailable"):
            diag("Ignored stale unavailable fund-flow cache")
        elif cached.get("date", "").replace("-", "") == date_str:
            return cached
        elif cached.get("date"):
            cached["_requested_date"] = _display_date(date_str)
            cached["_date_note"] = "latest_available"
            return cached
        diag(
            "Ignored cached fund flow because the returned trading date "
            f"{cached.get('date')} does not match requested {date_str}"
        )

    klines = []
    last_error = ""
    flow_source = ""
    latest_result: dict[str, str] | None = None
    for source_name, url_template, display_source in (
        ("Eastmoney fflow realtime", FFLOW_URL, "东财实时资金流"),
    ):
        url = url_template.format(ts=int(datetime.now().timestamp() * 1000))
        data = fetch_fund_flow_json(url)
        if "_error" in data:
            last_error = f"{source_name}: {data['_error']}"
            continue
        klines = (data.get("data") or {}).get("klines", [])
        if klines:
            for row in klines:
                vals = row.split(",")
                result = dict(zip(FUND_FLOW_COLS, vals))
                result["_source"] = display_source
                result["_scope"] = "A股"
                if latest_result is None:
                    latest_result = result
                if result.get("date", "").replace("-", "") == date_str:
                    flow_source = display_source
                    if source_name.endswith("history"):
                        diag("Fund flow fell back to Eastmoney push2his")
                    cache_save("fund_flow", date_str, "eastmoney", result)
                    return result
                result["_requested_date"] = _display_date(date_str)
                result["_date_note"] = "latest_available"
                cache_save("fund_flow", date_str, "eastmoney", result)
                return result
            latest_date = latest_result.get("date") if latest_result else "unknown"
            last_error = f"{source_name}: latest flow date {latest_date} != requested {date_str}"
            continue
        last_error = f"{source_name}: empty klines"

    snapshot = fetch_market_fund_flow_snapshot(date_str)
    if snapshot:
        cache_save("fund_flow", date_str, "eastmoney", snapshot)
        return snapshot

    url = FFLOW_HIS_URL.format(ts=int(datetime.now().timestamp() * 1000))
    data = fetch_fund_flow_json(url)
    if "_error" in data:
        last_error = f"Eastmoney fflow history: {data['_error']}"
    else:
        klines = (data.get("data") or {}).get("klines", [])
        if klines:
            for row in klines:
                vals = row.split(",")
                result = dict(zip(FUND_FLOW_COLS, vals))
                result["_source"] = "东财历史日线资金流"
                result["_scope"] = "A股"
                if latest_result is None:
                    latest_result = result
                if result.get("date", "").replace("-", "") == date_str:
                    diag("Fund flow fell back to Eastmoney push2his")
                    cache_save("fund_flow", date_str, "eastmoney", result)
                    return result
                result["_requested_date"] = _display_date(date_str)
                result["_date_note"] = "latest_available"
                cache_save("fund_flow", date_str, "eastmoney", result)
                return result
        else:
            last_error = "Eastmoney fflow history: empty klines"

    if last_error:
        diag(last_error)
    if latest_result:
        latest_result["_requested_date"] = _display_date(date_str)
        latest_result["_date_note"] = "latest_available"
        cache_save("fund_flow", date_str, "eastmoney", latest_result)
        return latest_result
    for online_reference in (fetch_sina_sector_money_flow_snapshot,):
        activity = online_reference(date_str)
        if activity:
            return activity
    if BROWSER_FALLBACK:
        browser_flow = fetch_browser_fund_flow_snapshot(date_str)
        if browser_flow:
            return browser_flow
    for market_reference in (fetch_sina_market_activity_snapshot, fetch_tencent_market_activity_snapshot):
        activity = market_reference(date_str)
        if activity:
            return activity
    cached_latest = load_latest_fund_flow_cache(date_str)
    if cached_latest:
        cached_latest["_cache_note"] = "last_known_good"
        return cached_latest
    return {
        "_unavailable": "当前没有拿到可核验交易日的免登录资金流数据",
        "_scope": "A股",
        "_requested_date": _display_date(date_str),
        "_source": flow_source or "东财资金流",
    }


def _parse_stock_flow_rows(klines: list[str]) -> list[dict[str, Any]]:
    rows = []
    for line in klines:
        parts = str(line).split(",")
        if len(parts) < 6:
            continue
        rows.append({
            "date": parts[0],
            "main_net": _safe_float(parts[1]) or 0.0,
            "small_net": _safe_float(parts[2]) or 0.0,
            "mid_net": _safe_float(parts[3]) or 0.0,
            "big_net": _safe_float(parts[4]) or 0.0,
            "super_big_net": _safe_float(parts[5]) or 0.0,
            "main_pct": _safe_float(parts[6]) if len(parts) > 6 else None,
        })
    return rows


@retry_on_recoverable(max_retries=MAX_RETRIES, initial_delay=INITIAL_BACKOFF)
def fetch_stock_fund_flow_daily(symbol: str, date_str: str, limit: int = 20) -> dict[str, Any]:
    """Fetch per-stock daily fund flow for A/HK/US from Eastmoney push2his."""
    normalized, market = normalize_stock_symbol(symbol)
    limit = max(1, min(int(limit or 20), 120))
    cache_date = f"{date_str}_{normalized}_{limit}"
    cached = cache_load("stock_fund_flow", cache_date, "eastmoney_push2his")
    if cached:
        return cached

    last_error = ""
    for secid in _stock_flow_secid_candidates(normalized, market):
        url = STOCK_FUND_FLOW_DAILY_URL.format(
            secid=secid, limit=limit, ts=int(datetime.now().timestamp() * 1000)
        )
        data = fetch_json(url, {"Referer": "https://quote.eastmoney.com/"})
        if "_error" in data:
            last_error = data["_error"]
            continue
        payload = data.get("data") or {}
        rows = _parse_stock_flow_rows(payload.get("klines") or [])
        if not rows:
            last_error = f"{secid}: empty klines"
            continue
        result = {
            "symbol": normalized,
            "market": market,
            "secid": secid,
            "name": payload.get("name") or normalized,
            "rows": rows,
            "latest_date": rows[-1]["date"],
            "_requested_date": _display_date(date_str),
            "_source": "东方财富 push2his 个股日级资金流",
            "_source_note": "按单只股票查询；该接口偶发受网络/IP风控影响，失败时不会替代默认行情源。",
        }
        if not any(str(row.get("date", "")).replace("-", "") == date_str for row in rows):
            result["_date_note"] = "latest_available"
        cache_save("stock_fund_flow", cache_date, "eastmoney_push2his", result)
        return result

    return {
        "symbol": normalized,
        "market": market,
        "rows": [],
        "_error": last_error or "empty stock fund flow",
        "_source": "东方财富 push2his 个股日级资金流",
    }


@retry_on_recoverable(max_retries=MAX_RETRIES, initial_delay=INITIAL_BACKOFF)
def fetch_northbound_flow_snapshot(date_str: str) -> dict[str, Any]:
    """Fetch intraday northbound flow from THS hsgtApi, unit: 亿元."""
    cached = cache_load("northbound_flow", date_str, "ths")
    if cached:
        return cached
    try:
        raw = _fetch_raw(
            THS_NORTHBOUND_FLOW_URL,
            {
                "Host": "data.hexin.cn",
                "Referer": "https://data.hexin.cn/",
                "Accept": "application/json,text/plain,*/*",
            },
        )
        data = _parse_json_text(raw)
    except Exception as exc:
        return {"_error": str(exc), "_source": "同花顺北向资金 hsgtApi"}

    times = data.get("time") or []
    hgt = data.get("hgt") or []
    sgt = data.get("sgt") or []
    if not times or not hgt or not sgt:
        return {"_error": "empty northbound flow", "_source": "同花顺北向资金 hsgtApi"}
    idx = min(len(times), len(hgt), len(sgt)) - 1
    hgt_yi = _safe_float(hgt[idx]) or 0.0
    sgt_yi = _safe_float(sgt[idx]) or 0.0
    result = {
        "date": _display_date(date_str),
        "latest_time": str(times[idx]),
        "hgt_yi": hgt_yi,
        "sgt_yi": sgt_yi,
        "total_yi": round(hgt_yi + sgt_yi, 2),
        "points": idx + 1,
        "series": [{"time": str(times[i]), "hgt_yi": _safe_float(hgt[i]) or 0.0, "sgt_yi": _safe_float(sgt[i]) or 0.0} for i in range(idx + 1)],
        "_source": "同花顺北向资金 hsgtApi",
        "_source_note": "分钟累计流向，单位亿元；用于替代已失效的东财北向口径。",
    }
    cache_save("northbound_flow", date_str, "ths", result)
    return result


@retry_on_recoverable(max_retries=MAX_RETRIES, initial_delay=INITIAL_BACKOFF)
def fetch_eastmoney_board_list(board_type: str, date_str: str, limit: int = 100) -> dict[str, Any]:
    """Fetch A-share industry/concept board ranking via Eastmoney clist."""
    normalized_type = "concept" if board_type == "concept" else "industry"
    cached = cache_load("board_list", f"{date_str}_{normalized_type}", "eastmoney_clist")
    if cached:
        return cached
    fs = "m:90+t:3" if normalized_type == "concept" else "m:90+t:2"
    params = {
        "pn": 1,
        "pz": max(1, min(int(limit or 100), 200)),
        "po": 1,
        "np": 1,
        "fltt": 2,
        "invt": 2,
        "fid": "f3",
        "fs": fs,
        "fields": "f2,f3,f4,f12,f13,f14,f104,f105,f128,f136,f140,f141,f207",
        "_": int(datetime.now().timestamp() * 1000),
    }
    url = f"https://push2.eastmoney.com/api/qt/clist/get?{urllib.parse.urlencode(params)}"
    data = fetch_json(url, {"Referer": "https://quote.eastmoney.com/"})
    if "_error" in data:
        return {"board_type": normalized_type, "rows": [], "_error": data["_error"], "_source": "东方财富行业/概念板块"}
    diff = (data.get("data") or {}).get("diff") or []
    items = diff.values() if isinstance(diff, dict) else diff
    rows = []
    for i, item in enumerate(items, 1):
        rows.append({
            "rank": i,
            "name": item.get("f14") or "",
            "code": item.get("f12") or "",
            "change_pct": _safe_float(item.get("f3")),
            "up_count": _safe_int(item.get("f104")),
            "down_count": _safe_int(item.get("f105")),
            "leader": item.get("f140") or item.get("f128") or "",
            "leader_change_pct": _safe_float(item.get("f136")),
        })
    result = {
        "board_type": normalized_type,
        "rows": rows,
        "count": len(rows),
        "_source": "东方财富行业/概念板块",
        "_source_note": "东财 clist 板块排名；轻量单请求，失败时回退到浏览器板块页。",
    }
    if rows:
        cache_save("board_list", f"{date_str}_{normalized_type}", "eastmoney_clist", result)
    return result


def get_board_list(board_type: str, date_str: str, limit: int = 100) -> dict[str, Any]:
    """Return board rankings through the stock-analysis source order."""
    current_trade_date = nearest_trade_date()
    result = route_board_data(
        board_type,
        date_str,
        direct=fetch_eastmoney_board_list,
        browser_service=browser_board_list,
        playwright=playwright_board_list,
        limit=limit,
        current_trade_date=current_trade_date,
        browser_fallback=False,
    )
    if result.get("rows") or date_str != current_trade_date:
        return result

    ths_result = fetch_ths_board_list(board_type, limit=limit)
    if ths_result.get("rows"):
        ths_result["_fallback"] = "东财 clist 不可用，已启用同花顺板块页"
        return ths_result

    if BROWSER_FALLBACK:
        for browser_source in (browser_board_list, playwright_board_list):
            candidate = browser_source(board_type)
            if isinstance(candidate, dict) and candidate.get("rows"):
                candidate["_fallback"] = "API 失败，已启用浏览器降级抓取"
                return candidate
    return result


@retry_on_recoverable(max_retries=MAX_RETRIES, initial_delay=INITIAL_BACKOFF)
def eastmoney_datacenter(
    report_name: str,
    *,
    columns: str = "ALL",
    filter_str: str = "",
    page_size: int = 100,
    page_number: int = 1,
    sort_columns: str = "",
    sort_types: str = "-1",
) -> list[dict[str, Any]]:
    params = {
        "reportName": report_name,
        "columns": columns,
        "filter": filter_str,
        "pageSize": max(1, min(int(page_size or 100), 500)),
        "pageNumber": max(1, int(page_number or 1)),
        "sortColumns": sort_columns,
        "sortTypes": sort_types,
        "source": "WEB",
        "client": "WEB",
    }
    url = f"{EASTMONEY_DATACENTER_URL}?{urllib.parse.urlencode(params)}"
    data = fetch_json(url, {"Referer": "https://data.eastmoney.com/"})
    if "_error" in data:
        diag(f"Eastmoney datacenter {report_name}: {data['_error']}")
        return []
    return ((data.get("result") or {}).get("data") or []) if data.get("success", True) else []


def fetch_a_share_financial_snapshot(symbol: str, date_str: str, limit: int = 8) -> dict[str, Any]:
    """Fetch disclosed A-share financial evidence from Eastmoney datacenter."""
    normalized, market = normalize_stock_symbol(symbol)
    if market != "cn_market":
        return {
            "symbol": normalized,
            "available": False,
            "periods": [],
            "forecasts": {"available": False, "rows": []},
            "earnings_flash": {"available": False, "rows": []},
            "gaps": ["A股财务快照目前仅支持 A 股代码"],
            "_source": "东方财富 datacenter",
        }
    limit = max(1, min(int(limit or 8), 20))
    cache_key = f"v3_{date_str}_{normalized}_{limit}"
    cached = cache_load("a_share_financial_snapshot", cache_key, "eastmoney_datacenter", ttl=24 * 3600)
    if cached:
        return cached

    filter_str = f'(SECURITY_CODE="{normalized}")'
    summary_rows = eastmoney_datacenter(
        "RPT_LICO_FN_CPD",
        filter_str=filter_str,
        page_size=limit,
        sort_columns="REPORTDATE",
        sort_types="-1",
    )
    balance_rows = eastmoney_datacenter(
        "RPT_DMSK_FN_BALANCE",
        filter_str=filter_str,
        page_size=limit,
        sort_columns="REPORT_DATE",
        sort_types="-1",
    )
    cashflow_rows = eastmoney_datacenter(
        "RPT_DMSK_FN_CASHFLOW",
        filter_str=filter_str,
        page_size=limit,
        sort_columns="REPORT_DATE",
        sort_types="-1",
    )
    forecast_rows = eastmoney_datacenter(
        "RPT_PUBLIC_OP_NEWPREDICT",
        filter_str=filter_str,
        page_size=5,
        sort_columns="NOTICE_DATE",
        sort_types="-1",
    )
    flash_rows = eastmoney_datacenter(
        "RPT_PUBLIC_OP_NEWDISCOVER",
        filter_str=filter_str,
        page_size=5,
        sort_columns="NOTICE_DATE",
        sort_types="-1",
    )
    result = _build_a_share_financial_snapshot(
        normalized,
        summary_rows=summary_rows,
        balance_rows=balance_rows,
        cashflow_rows=cashflow_rows,
        forecast_rows=forecast_rows,
        flash_rows=flash_rows,
    )
    cache_save("a_share_financial_snapshot", cache_key, "eastmoney_datacenter", result)
    return result


def _build_a_share_financial_snapshot(
    symbol: str,
    *,
    summary_rows: list[dict[str, Any]],
    balance_rows: list[dict[str, Any]],
    cashflow_rows: list[dict[str, Any]],
    forecast_rows: list[dict[str, Any]],
    flash_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    balance_by_period = {_financial_period_key(row): row for row in balance_rows if _financial_period_key(row)}
    cashflow_by_period = {_financial_period_key(row): row for row in cashflow_rows if _financial_period_key(row)}
    periods: list[dict[str, Any]] = []
    name = symbol
    for row in summary_rows:
        period = _financial_period_key(row)
        if not period:
            continue
        name = str(row.get("SECURITY_NAME_ABBR") or row.get("SECURITY_NAME") or name)
        balance = balance_by_period.get(period) or {}
        cashflow = cashflow_by_period.get(period) or {}
        operating_cash_flow = _safe_float(cashflow.get("NETCASH_OPERATE"))
        capex_cash_paid = _safe_float(cashflow.get("CONSTRUCT_LONG_ASSET"))
        fcf_lite = (
            operating_cash_flow - capex_cash_paid
            if operating_cash_flow is not None and capex_cash_paid is not None
            else None
        )
        periods.append(
            {
                "report_date": period,
                "period_label": _financial_period_label(period),
                "notice_date": _date_only(row.get("NOTICE_DATE") or row.get("REPORTDATE")),
                "roe_weighted": _safe_float(row.get("WEIGHTAVG_ROE")),
                "gross_margin": _safe_float(row.get("XSMLL")),
                "basic_eps": _safe_float(row.get("BASIC_EPS")),
                "bps": _safe_float(row.get("BPS")),
                "revenue": _safe_float(row.get("TOTAL_OPERATE_INCOME")),
                "parent_net_profit": _safe_float(row.get("PARENT_NETPROFIT")),
                "debt_asset_ratio": _safe_float(balance.get("DEBT_ASSET_RATIO")),
                "total_assets": _safe_float(balance.get("TOTAL_ASSETS")),
                "total_liabilities": _safe_float(balance.get("TOTAL_LIABILITIES")),
                "operating_cash_flow": operating_cash_flow,
                "capex_cash_paid": capex_cash_paid,
                "free_cash_flow_lite": fcf_lite,
                "net_cash_invest": _safe_float(cashflow.get("NETCASH_INVEST")),
                "net_cash_finance": _safe_float(cashflow.get("NETCASH_FINANCE")),
            }
        )
    periods.sort(key=lambda item: str(item.get("report_date") or ""), reverse=True)
    latest_period = str(periods[0].get("report_date") or "") if periods else ""
    forecasts = _financial_disclosure_rows(forecast_rows, min_report_date=latest_period)
    flashes = _financial_disclosure_rows(flash_rows, min_report_date=latest_period)
    availability = {
        "roe": any(row.get("roe_weighted") is not None for row in periods),
        "gross_margin": any(row.get("gross_margin") is not None for row in periods),
        "debt_asset_ratio": any(row.get("debt_asset_ratio") is not None for row in periods),
        "operating_cash_flow": any(row.get("operating_cash_flow") is not None for row in periods),
        "free_cash_flow_lite": any(row.get("free_cash_flow_lite") is not None for row in periods),
        "forecast": bool(forecasts),
        "earnings_flash": bool(flashes),
    }
    gaps = [label for key, label in (
        ("roe", "ROE"),
        ("debt_asset_ratio", "资产负债率"),
        ("operating_cash_flow", "经营现金流"),
        ("free_cash_flow_lite", "自由现金流-lite"),
    ) if not availability[key]]
    if not forecasts and not flashes:
        gaps.append("业绩预告/快报仅在公司披露时存在")
    return {
        "symbol": symbol,
        "name": name,
        "available": bool(periods),
        "periods": periods,
        "availability": availability,
        "forecasts": {"available": bool(forecasts), "rows": forecasts},
        "earnings_flash": {"available": bool(flashes), "rows": flashes},
        "gaps": gaps,
        "limitations": [
            "业绩预告/快报仅在公司披露时存在；无返回不代表公司没有业绩变化。",
            "free_cash_flow_lite=经营现金流净额-购建固定资产等长期资产支付现金，仅作公开现金流代理。",
        ],
        "_source": "东方财富 datacenter 财务摘要/资产负债表/现金流量表/业绩预告/业绩快报",
    }


def _financial_period_key(row: dict[str, Any]) -> str:
    return _date_only(
        row.get("REPORT_DATE")
        or row.get("REPORTDATE")
        or row.get("END_DATE")
        or row.get("REPORT_PERIOD")
        or row.get("QDATE")
    )


def _financial_period_label(period: str) -> str:
    if len(period) != 10:
        return period
    month_day = period[5:]
    return {
        "03-31": f"{period[:4]}Q1",
        "06-30": f"{period[:4]}H1",
        "09-30": f"{period[:4]}Q3",
        "12-31": f"{period[:4]}FY",
    }.get(month_day, period)


def _date_only(value: Any) -> str:
    text = str(value or "").strip()
    match = re.search(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", text)
    if match:
        year, month, day = match.groups()
        return f"{year}-{int(month):02d}-{int(day):02d}"
    digits = re.sub(r"\D", "", text)
    if len(digits) >= 8:
        return f"{digits[:4]}-{digits[4:6]}-{digits[6:8]}"
    return ""


def _financial_disclosure_rows(rows: list[dict[str, Any]], *, min_report_date: str = "") -> list[dict[str, Any]]:
    result = []
    for row in rows:
        report_date = _date_only(row.get("REPORT_DATE") or row.get("REPORTDATE") or row.get("QDATE"))
        if min_report_date and (not report_date or report_date < min_report_date):
            continue
        result.append(
            {
                "notice_date": _date_only(row.get("NOTICE_DATE") or row.get("DISCLOSE_DATE")),
                "report_date": report_date,
                "title": row.get("TITLE") or row.get("NOTICE_TITLE") or row.get("PREDICT_CONTENT") or "",
                "type": row.get("PREDICT_TYPE") or row.get("REPORT_TYPE") or row.get("FORECAST_TYPE") or "",
                "summary": row.get("CHANGE_REASON") or row.get("PREDICT_REASON") or row.get("CONTENT") or "",
                "lower": _safe_float(row.get("ADD_AMP_LOWER") or row.get("PREDICT_AMT_LOWER")),
                "upper": _safe_float(row.get("ADD_AMP_UPPER") or row.get("PREDICT_AMT_UPPER")),
            }
        )
    return result


@retry_on_recoverable(max_retries=MAX_RETRIES, initial_delay=INITIAL_BACKOFF)
def fetch_block_trades(symbol: str, date_str: str, limit: int = 10) -> dict[str, Any]:
    normalized, market = normalize_stock_symbol(symbol)
    if market != "cn_market":
        return {"symbol": normalized, "rows": [], "_error": "大宗交易目前仅支持 A 股", "_source": "东方财富 datacenter"}
    limit = max(1, min(int(limit or 10), 100))
    cached = cache_load("block_trades", f"{date_str}_{normalized}_{limit}", "eastmoney_datacenter")
    if cached:
        return cached

    data = eastmoney_datacenter(
        "RPT_DATA_BLOCKTRADE",
        filter_str=f'(SECURITY_CODE="{normalized}")',
        page_size=limit,
        sort_columns="TRADE_DATE",
        sort_types="-1",
    )
    rows = []
    name = normalized
    for row in data:
        close = _safe_float(row.get("CLOSE_PRICE")) or 0.0
        price = _safe_float(row.get("DEAL_PRICE")) or 0.0
        premium = ((price / close - 1) * 100) if close else 0.0
        name = str(row.get("SECURITY_NAME_ABBR") or name)
        rows.append({
            "date": str(row.get("TRADE_DATE", ""))[:10],
            "price": price,
            "close": close,
            "premium_pct": round(premium, 2),
            "vol": _safe_float(row.get("DEAL_VOLUME")) or 0.0,
            "amount": _safe_float(row.get("DEAL_AMT")) or 0.0,
            "buyer": row.get("BUYER_NAME") or "",
            "seller": row.get("SELLER_NAME") or "",
        })
    result = {
        "symbol": normalized,
        "market": market,
        "name": name,
        "rows": rows,
        "latest_date": rows[0]["date"] if rows else "",
        "_requested_date": _display_date(date_str),
        "_source": "东方财富 datacenter 大宗交易",
        "_source_note": "交易所披露类低频数据，经东财 datacenter 聚合。",
    }
    cache_save("block_trades", f"{date_str}_{normalized}_{limit}", "eastmoney_datacenter", result)
    return result


def _first_present(row: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return value
    return None


LHB_CACHE_VERSION = 2
LHB_REPORT_NAMES = (
    ("RPT_DAILYBILLBOARD_DETAILS", "BILLBOARD_NET_AMT"),
    ("RPT_DAILYBILLBOARD_DETAILSNEW", "NET_BS_AMT"),
    ("RPT_BILLBOARD_DAILYDETAILS", "TOTAL_NET"),
)


def _recent_iso_dates(date_str: str, days: int = 5) -> list[str]:
    start = datetime.strptime(_display_date(date_str), "%Y-%m-%d")
    return [(start - timedelta(days=offset)).strftime("%Y-%m-%d") for offset in range(max(1, days))]


def _amount_wan(value: Any) -> float | None:
    amount = _safe_float(value)
    if amount is None:
        return None
    return amount / 10000 if abs(amount) > 100000 else amount


def _lhb_row(row: dict[str, Any]) -> dict[str, Any]:
    buy_amount = _first_present(row, "BILLBOARD_BUY_AMT", "SUM_BUY_AMT", "TOTAL_BUY", "BUY_AMT", "BUY_AMOUNT")
    sell_amount = _first_present(row, "BILLBOARD_SELL_AMT", "SUM_SELL_AMT", "TOTAL_SELL", "SELL_AMT", "SELL_AMOUNT")
    net_amount = _first_present(row, "BILLBOARD_NET_AMT", "NET_BS_AMT", "TOTAL_NET", "NET_BUY_AMT", "NET_AMT")
    return {
        "symbol": str(_first_present(row, "SECURITY_CODE", "SECUCODE", "CODE") or ""),
        "name": str(_first_present(row, "SECURITY_NAME_ABBR", "SECURITY_NAME", "NAME") or ""),
        "close_price": _safe_float(_first_present(row, "CLOSE_PRICE", "CLOSE", "NEW_PRICE")),
        "change_pct": _safe_float(_first_present(row, "CHANGE_RATE", "CHANGE_RATE_1D", "ZDF")),
        "buy_amount_wan": _amount_wan(buy_amount),
        "sell_amount_wan": _amount_wan(sell_amount),
        "net_amount_wan": _amount_wan(net_amount),
        "reason": str(_first_present(row, "EXPLANATION", "REASON", "BILLBOARD_REASON") or ""),
    }


def _fetch_lhb_rows_for_date(iso_date: str, limit: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for report_name, sort_column in LHB_REPORT_NAMES:
        data = eastmoney_datacenter(
            report_name,
            filter_str=f"(TRADE_DATE='{iso_date}')",
            page_size=max(1, min(int(limit or 5), 50)),
            sort_columns=sort_column,
            sort_types="-1",
        )
        for row in data:
            row_date = str(_first_present(row, "TRADE_DATE", "TDATE", "STATISTIC_DATE") or "")[:10]
            if row_date and row_date != iso_date:
                continue
            parsed = _lhb_row(row)
            key = (parsed["symbol"], parsed["name"])
            if key in seen or not any(key):
                continue
            seen.add(key)
            rows.append(parsed)
            if len(rows) >= limit:
                return rows
    return rows


@retry_on_recoverable(max_retries=MAX_RETRIES, initial_delay=INITIAL_BACKOFF)
def fetch_lhb_aftermarket(date_str: str, limit: int = 5) -> dict[str, Any]:
    """Fetch after-market Longhu list rows from Eastmoney datacenter."""
    cache_key = f"{date_str}_{limit}_v{LHB_CACHE_VERSION}"
    cached = cache_load("lhb_aftermarket", cache_key, "eastmoney_datacenter")
    if cached and cached.get("_cache_version") == LHB_CACHE_VERSION and cached.get("available"):
        return cached

    requested_iso = _display_date(date_str)
    rows: list[dict[str, Any]] = []
    actual_iso = requested_iso
    for iso_date in _recent_iso_dates(date_str, days=5):
        rows = _fetch_lhb_rows_for_date(iso_date, limit)
        if rows:
            actual_iso = iso_date
            break

    result = {
        "available": bool(rows),
        "date": actual_iso,
        "requested_date": requested_iso,
        "rows": rows,
        "_cache_version": LHB_CACHE_VERSION,
        "_source": "东方财富数据中心龙虎榜",
        "_source_note": "盘后交易所公开龙虎榜聚合；若请求日无披露，回看最近可用交易日。",
    }
    if actual_iso != requested_iso:
        result["fallback_reason"] = f"requested={requested_iso}; lhb_date={actual_iso}"
    cache_save("lhb_aftermarket", cache_key, "eastmoney_datacenter", result)
    return result


IMPORTANT_ANNOUNCEMENT_TERMS = (
    "中标",
    "重大合同",
    "回购",
    "增持",
    "减持",
    "并购",
    "重组",
    "业绩预告",
    "业绩快报",
    "风险提示",
    "停牌",
    "复牌",
    "控制权",
)

ANNOUNCEMENT_FALLBACK_QUERIES = (
    "重大合同",
    "中标",
    "业绩预告",
    "回购",
    "并购重组",
    "停复牌",
)


@retry_on_recoverable(max_retries=MAX_RETRIES, initial_delay=INITIAL_BACKOFF)
def fetch_important_announcements(
    date_str: str,
    *,
    candidates: list[dict[str, Any]] | None = None,
    limit: int = 8,
) -> dict[str, Any]:
    """Fetch important A/H/US announcements for visible market leaders/holdings."""
    limit = max(1, min(int(limit or 8), 20))
    candidates = candidates or []
    rows: list[dict[str, Any]] = []
    seen_titles: set[str] = set()
    query_items = list(candidates[: max(limit, 4)])
    query_items.extend({"name": keyword, "symbol": ""} for keyword in ANNOUNCEMENT_FALLBACK_QUERIES)
    for candidate in query_items:
        keyword = str(candidate.get("name") or candidate.get("symbol") or "").strip()
        if not keyword:
            continue
        payload = futu_news_search(keyword, size=10, lang="zh-CN", news_type=2)
        for item in payload.get("data") or []:
            title = _clean_news_title(str(item.get("title") or ""))
            if not title or title in seen_titles:
                continue
            publish_date = _news_date(item.get("publish_time"))
            if publish_date and publish_date != date_str:
                continue
            if not any(term in title for term in IMPORTANT_ANNOUNCEMENT_TERMS):
                continue
            seen_titles.add(title)
            rows.append(
                {
                    "symbol": str(candidate.get("symbol") or ""),
                    "name": str(candidate.get("name") or keyword),
                    "title": title,
                    "url": _normalize_news_url(item),
                    "publish_date": publish_date,
                }
            )
            if len(rows) >= limit:
                break
        if len(rows) >= limit:
            break
    return {
        "available": bool(rows),
        "date": _display_date(date_str),
        "rows": rows,
        "_source": "Futu 免登录公告搜索",
        "_source_note": "按盘面领涨/持仓候选查询公告，标题命中重大事项关键词后展示。",
    }


# ------------------------------------------------------------------
# 富途数据获取
# ------------------------------------------------------------------

@retry_on_recoverable(max_retries=MAX_RETRIES, initial_delay=INITIAL_BACKOFF)
def futu_news_search(keyword: str, size: int = 10, lang: str = "en", news_type: int = 1) -> dict[str, Any]:
    params = urllib.parse.urlencode({
        "keyword": keyword,
        "size": size,
        "news_type": news_type,
        "lang": lang,
        "sort_type": 2,
    })
    url = f"{FUTU_NEWS_URL}?{params}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "stock-analysis/0.3.13"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        diag(f"Futu news {keyword}: {e}")
        return {"_error": str(e)}


@retry_on_recoverable(max_retries=MAX_RETRIES, initial_delay=INITIAL_BACKOFF)
def futu_stock_feed(keyword: str, size: int = 30) -> dict[str, Any]:
    params = urllib.parse.urlencode({"keyword": keyword, "size": size})
    url = f"{FUTU_FEED_URL}?{params}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "stock-analysis/0.3.13"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        diag(f"Futu feed {keyword}: {e}")
        return {"_error": str(e)}


SINA_NEWS_ALIASES = {
    "AAPL": ["AAPL", "Apple", "苹果"],
    "TSLA": ["TSLA", "Tesla", "特斯拉"],
    "NVDA": ["NVDA", "NVIDIA", "英伟达"],
    "0700": ["0700", "00700", "腾讯", "腾讯控股"],
    "9988": ["9988", "09988", "阿里", "阿里巴巴"],
    "3690": ["3690", "03690", "美团"],
}


def _clean_news_title(title: str) -> str:
    title = re.sub(r"<[^>]+>", "", title or "")
    return html.unescape(title).strip()


def _news_aliases(symbol: str, name: str = "") -> list[str]:
    aliases = [symbol]
    if symbol.upper().endswith(".HK"):
        raw = symbol.upper().replace(".HK", "")
        aliases.extend([raw, raw.lstrip("0"), raw.zfill(5)])
    if name:
        aliases.append(name)
        aliases.append(re.split(r"[-－—（(]", name, maxsplit=1)[0].strip())
    return [alias for alias in dict.fromkeys(a for a in aliases if a)]


def _normalize_futu_feed(
    feed_data: dict[str, Any],
    size: int = 5,
    *,
    keyword: str | None = None,
    aliases: list[str] | None = None,
) -> dict[str, Any]:
    if "_error" in feed_data:
        return feed_data
    raw_items = feed_data.get("data", [])
    if isinstance(raw_items, dict):
        raw_items = raw_items.get("list") or raw_items.get("items") or []
    candidates = [keyword or "", *(aliases or SINA_NEWS_ALIASES.get((keyword or "").upper(), []))]
    candidates = [c.lower() for c in candidates if c]
    items = []
    for item in raw_items:
        title = _clean_news_title(str(item.get("title") or item.get("content") or ""))
        if not title:
            continue
        if candidates and not any(alias in title.lower() for alias in candidates):
            continue
        items.append({
            "title": title,
            "url": item.get("url") or item.get("jump_url") or "",
            "publish_time": item.get("publish_time") or item.get("time") or 0,
            "source": "futu_feed",
        })
        if len(items) >= size:
            break
    return {"source": "futu_feed", "data": items}


@retry_on_recoverable(max_retries=MAX_RETRIES, initial_delay=INITIAL_BACKOFF)
def sina_roll_news(keyword: str, size: int = 5, aliases: list[str] | None = None) -> dict[str, Any]:
    """新浪财经滚动新闻 fallback。按别名过滤，避免给个股塞无关新闻。"""
    params = urllib.parse.urlencode({
        "pageid": 153,
        "lid": 2509,
        "num": 60,
        "page": 1,
    })
    url = f"{SINA_ROLL_NEWS_URL}?{params}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            payload = json.loads(resp.read().decode("utf-8", errors="ignore"))
    except Exception as e:
        diag(f"Sina roll news {keyword}: {e}")
        return {"_error": str(e)}

    candidates = [keyword, *(aliases or SINA_NEWS_ALIASES.get(keyword.upper(), []))]
    candidates = [c.lower() for c in candidates if c]
    raw_items = payload.get("result", {}).get("data", [])
    items = []
    for item in raw_items:
        title = _clean_news_title(str(item.get("title", "")))
        intro = _clean_news_title(str(item.get("intro", "")))
        text = f"{title} {intro}".lower()
        if candidates and not any(alias in text for alias in candidates):
            continue
        items.append({
            "title": title,
            "url": item.get("url") or item.get("wapurl") or "",
            "publish_time": item.get("ctime") or item.get("intime") or 0,
            "source": item.get("media_name") or "新浪财经",
        })
        if len(items) >= size:
            break
    return {"source": "sina_roll", "data": items}


@retry_on_recoverable(max_retries=MAX_RETRIES, initial_delay=INITIAL_BACKOFF)
def eastmoney_fast_news(keyword: str, size: int = 5, aliases: list[str] | None = None) -> dict[str, Any]:
    """东方财富7x24快讯。免登录，按关键词/别名做本地过滤。"""
    params = urllib.parse.urlencode({
        "client": "web",
        "biz": "web_724",
        "fastColumn": "102",
        "sortEnd": "",
        "req_trace": str(int(time.time() * 1000)),
        "pageSize": 80,
    })
    url = f"{EASTMONEY_FAST_NEWS_URL}?{params}"
    data = fetch_json(url, {"Referer": "https://kuaixun.eastmoney.com/"})
    if "_error" in data:
        diag(f"Eastmoney fast news {keyword}: {data['_error']}")
        return data

    candidates = [keyword, *(aliases or SINA_NEWS_ALIASES.get(keyword.upper(), []))]
    candidates = [c.lower() for c in candidates if c]
    raw_items = ((data.get("data") or {}).get("fastNewsList") or [])
    items = []
    for item in raw_items:
        title = _clean_news_title(str(item.get("title", "")))
        summary = _clean_news_title(str(item.get("summary", "")))
        text = f"{title} {summary}".lower()
        if candidates and not any(alias in text for alias in candidates):
            continue
        items.append({
            "title": title,
            "url": f"https://kuaixun.eastmoney.com/detail.html?newsid={item.get('code', '')}",
            "publish_time": _parse_news_time(item.get("showTime")),
            "source": "东方财富",
        })
        if len(items) >= size:
            break
    return {"source": "eastmoney_fast", "data": items}


def _parse_news_time(value: Any) -> int:
    if not value:
        return 0
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value).strip()
    if text.isdigit():
        return int(text)
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d"):
        try:
            return int(datetime.strptime(text, fmt).timestamp())
        except ValueError:
            continue
    return 0


def _news_date(value: Any) -> str:
    ts = _parse_news_time(value)
    if not ts:
        return ""
    return datetime.fromtimestamp(ts).strftime("%Y%m%d")


def _news_source_label(source: str) -> str:
    return {
        "futu_news": "富途资讯",
        "futu_feed": "富途社区/资讯",
        "sina_roll": "新浪财经",
        "eastmoney_fast": "东方财富快讯",
        "东方财富": "东方财富",
        "新浪财经": "新浪财经",
    }.get(source, source or "未知来源")


def _normalize_news_url(item: dict[str, Any]) -> str:
    for key in ("url", "jump_url", "link", "news_url", "article_url", "wapurl"):
        value = item.get(key)
        if value:
            return str(value)
    return ""


def _news_url_has_readable_content(url: str) -> bool:
    """剔除明显无内容的新闻页；网络临时失败时不误杀。"""
    if not url:
        return False
    if url in NEWS_URL_VALIDATION_CACHE:
        return NEWS_URL_VALIDATION_CACHE[url]
    parsed = urllib.parse.urlparse(url)
    host = parsed.netloc.lower()
    if host.endswith(".example") or host == "example.com":
        NEWS_URL_VALIDATION_CACHE[url] = True
        return True
    if parsed.scheme not in {"http", "https"}:
        NEWS_URL_VALIDATION_CACHE[url] = False
        return False

    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
        )
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(req, timeout=5) as resp:
            status = getattr(resp, "status", 200)
            content_type = resp.headers.get("Content-Type", "")
            raw = resp.read(65536)
    except urllib.error.HTTPError as e:
        NEWS_URL_VALIDATION_CACHE[url] = e.code not in (404, 410)
        return NEWS_URL_VALIDATION_CACHE[url]
    except Exception as e:
        diag(f"News URL validation skipped {url}: {e}")
        return True

    if status in (404, 410):
        NEWS_URL_VALIDATION_CACHE[url] = False
        return False
    if content_type and "html" not in content_type and "text" not in content_type:
        NEWS_URL_VALIDATION_CACHE[url] = True
        return True

    text = raw.decode("utf-8", errors="ignore")
    compact = re.sub(r"\s+", "", re.sub(r"<[^>]+>", "", text)).lower()
    invalid_markers = (
        "页面不存在",
        "内容不存在",
        "暂无内容",
        "新闻不存在",
        "文章不存在",
        "404notfound",
        "notfound",
    )
    valid = bool(len(compact) >= 80 and not any(marker in compact for marker in invalid_markers))
    NEWS_URL_VALIDATION_CACHE[url] = valid
    return valid


def _filter_readable_news(items: list[dict[str, Any]], size: int) -> list[dict[str, Any]]:
    if not items:
        return []
    selected: list[dict[str, Any]] = []
    pending_without_url: list[dict[str, Any]] = []
    max_checks = max(size * 4, size)
    checked = 0
    for item in items:
        url = _normalize_news_url(item)
        if not url:
            pending_without_url.append(item)
            continue
        if checked >= max_checks:
            selected.append(item)
        elif _news_url_has_readable_content(url):
            selected.append(item)
        checked += 1
        if len(selected) >= size:
            break
    if len(selected) < size:
        selected.extend(pending_without_url[: size - len(selected)])
    return selected[:size]


def _select_diverse_news(items: list[dict[str, Any]], size: int) -> list[dict[str, Any]]:
    """展示时尽量保留多来源；热度计算仍基于所有命中。"""
    if len(items) <= size:
        return items
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in items:
        buckets[str(item.get("source", "news"))].append(item)
    for bucket in buckets.values():
        bucket.sort(key=lambda item: _parse_news_time(item.get("publish_time")), reverse=True)

    selected: list[dict[str, Any]] = []
    seen_titles: set[str] = set()
    source_order = sorted(
        buckets,
        key=lambda source: (
            -len(buckets[source]),
            -max((_parse_news_time(item.get("publish_time")) for item in buckets[source]), default=0),
        ),
    )
    while len(selected) < size and source_order:
        progressed = False
        for source in list(source_order):
            bucket = buckets[source]
            while bucket:
                item = bucket.pop(0)
                title = str(item.get("title", ""))
                if title in seen_titles:
                    continue
                selected.append(item)
                seen_titles.add(title)
                progressed = True
                break
            if not bucket:
                source_order.remove(source)
            if len(selected) >= size:
                break
        if not progressed:
            break
    selected.sort(key=lambda item: _parse_news_time(item.get("publish_time")), reverse=True)
    return selected[:size]


def _news_matches_date(item: dict[str, Any], date_str: str | None) -> bool:
    if not date_str:
        return True
    return _news_date(item.get("publish_time")) == date_str


def news_search_chain(keyword: str, size: int = 5, lang: str = "en", aliases: list[str] | None = None) -> dict[str, Any]:
    """资讯四段式：Futu 新闻 → Futu feed → 新浪财经 → 东方财富。"""
    news = futu_news_search(keyword, size=size, lang=lang)
    if news.get("data"):
        news.setdefault("source", "futu_news")
        return news

    feed = _normalize_futu_feed(futu_stock_feed(keyword, size=size * 2), size=size, keyword=keyword, aliases=aliases)
    if feed.get("data"):
        return feed

    fallback = sina_roll_news(keyword, size=size, aliases=aliases)
    if fallback.get("data"):
        return fallback

    em_news = eastmoney_fast_news(keyword, size=size, aliases=aliases)
    if em_news.get("data"):
        return em_news

    return news if "_error" in news else {"source": "none", "data": []}


def combined_news_search(
    keyword: str,
    size: int = 5,
    lang: str = "zh-CN",
    aliases: list[str] | None = None,
    date_str: str | None = None,
) -> dict[str, Any]:
    """聚合稳定免登录新闻源，用于热度排序和展示。"""
    per_source_size = max(size, 5)
    sources = [
        futu_news_search(keyword, size=per_source_size, lang=lang),
        _normalize_futu_feed(
            futu_stock_feed(keyword, size=per_source_size * 2),
            size=per_source_size,
            keyword=keyword,
            aliases=aliases,
        ),
        sina_roll_news(keyword, size=per_source_size, aliases=aliases),
        eastmoney_fast_news(keyword, size=per_source_size, aliases=aliases),
    ]
    seen: set[str] = set()
    items: list[dict[str, Any]] = []
    used_sources: list[str] = []
    source_counts: Counter[str] = Counter()
    for idx, source in enumerate(sources):
        if not source.get("data"):
            continue
        fallback_name = ("futu_news", "futu_feed", "sina_roll", "eastmoney_fast")[idx]
        source_name = str(source.get("source") or fallback_name)
        used_sources.append(source_name)
        for item in source.get("data", []):
            title = _clean_news_title(str(item.get("title", "")))
            if not title or title in seen:
                continue
            seen.add(title)
            normalized = dict(item)
            normalized["title"] = title
            normalized["url"] = _normalize_news_url(normalized)
            normalized.setdefault("source", source_name)
            if not _news_matches_date(normalized, date_str):
                continue
            items.append(normalized)
            source_counts[source_name] += 1
    items.sort(key=lambda item: _parse_news_time(item.get("publish_time")), reverse=True)
    linked_items = [item for item in items if item.get("url")]
    display_items = _filter_readable_news(linked_items, size) if linked_items else []
    if len(display_items) < size:
        seen_titles = {str(item.get("title", "")) for item in display_items}
        display_items.extend([
            item for item in items
            if not item.get("url") and str(item.get("title", "")) not in seen_titles
        ][: size - len(display_items)])
    return {
        "source": "+".join(s for s in used_sources if s) or "none",
        "data": _select_diverse_news(display_items, size),
        "all_count": len(items),
        "source_counts": dict(source_counts),
    }


def rank_symbols_by_news_heat(
    symbols: list[str],
    *,
    names: dict[str, str] | None = None,
    lang: str = "zh-CN",
    top_n: int = 5,
    date_str: str | None = None,
) -> tuple[list[str], dict[str, dict[str, Any]]]:
    """按多源新闻命中数和新鲜度给股票排序，保持无新闻标的的原始顺序。"""
    heat: dict[str, dict[str, Any]] = {}
    names = names or {}
    now_ts = int(time.time())
    for symbol in symbols:
        aliases = [symbol]
        if names.get(symbol):
            aliases.append(names[symbol])
        keyword = names.get(symbol) or symbol
        news = combined_news_search(keyword, size=5, lang=lang, aliases=aliases, date_str=date_str)
        score = float(news.get("all_count", 0))
        source_counts = news.get("source_counts") or {}
        score += max(0, len(source_counts) - 1) * 0.8
        for item in news.get("data", []):
            ts = _parse_news_time(item.get("publish_time"))
            if ts and now_ts - ts < 24 * 3600:
                score += 0.5
        heat[symbol] = {"score": score, "news": news}
    ranked = sorted(symbols, key=lambda s: (-heat.get(s, {}).get("score", 0), symbols.index(s)))
    ranked = [symbol for symbol in ranked if heat.get(symbol, {}).get("score", 0) > 0]
    return ranked[:top_n], heat


# ------------------------------------------------------------------
# 板块榜（可选浏览器服务降级层）
# ------------------------------------------------------------------

def _strip_pct(value: Any) -> float | None:
    return _safe_float(str(value or "").replace("%", "").strip())


def _html_cells(row_html: str) -> list[str]:
    return [_html_to_text(cell) for cell in re.findall(r"<td[^>]*>(.*?)</td>", row_html, re.DOTALL | re.IGNORECASE)]


def _first_board_code(row_html: str) -> str:
    match = re.search(r"/detail/code/(\d+)/", row_html)
    return match.group(1) if match else ""


def _parse_ths_board_rows(html_text: str, board_type: str, limit: int) -> list[dict[str, Any]]:
    tbody_match = re.search(r"<tbody[^>]*>(.*?)</tbody>", html_text, re.DOTALL | re.IGNORECASE)
    if not tbody_match:
        return []
    rows: list[dict[str, Any]] = []
    for row_html in re.findall(r"<tr[^>]*>(.*?)</tr>", tbody_match.group(1), re.DOTALL | re.IGNORECASE):
        cells = _html_cells(row_html)
        if board_type == "industry":
            if len(cells) < 12:
                continue
            rank = _safe_int(cells[0])
            name = cells[1]
            change_pct = _strip_pct(cells[2])
            up_count = _safe_int(cells[6])
            down_count = _safe_int(cells[7])
            leader = cells[9]
            leader_change_pct = _strip_pct(cells[11])
        else:
            if len(cells) < 10:
                continue
            rank = _safe_int(cells[0])
            name = cells[1]
            change_pct = _strip_pct(cells[3])
            up_count = None
            down_count = None
            leader = cells[8]
            leader_change_pct = _strip_pct(cells[9])
        if rank is None or not name:
            continue
        rows.append(
            {
                "rank": rank,
                "name": name,
                "code": _first_board_code(row_html),
                "change_pct": change_pct,
                "up_count": up_count,
                "down_count": down_count,
                "leader": leader,
                "leader_change_pct": leader_change_pct,
            }
        )
        if len(rows) >= limit:
            break
    return rows


def fetch_ths_board_list(board_type: str, limit: int = 100) -> dict[str, Any]:
    normalized_type = "concept" if board_type == "concept" else "industry"
    url = THS_CONCEPT_MONEY_FLOW_URL if normalized_type == "concept" else THS_INDUSTRY_BOARD_URL
    try:
        html_text = _fetch_text(
            url,
            headers={
                "Referer": "https://q.10jqka.com.cn/",
                "User-Agent": "Mozilla/5.0",
            },
            timeout=15,
            encoding="gbk",
        )
    except Exception as exc:
        return {"board_type": normalized_type, "rows": [], "_error": str(exc), "_source": "同花顺板块页"}
    rows = _parse_ths_board_rows(html_text, normalized_type, max(1, min(int(limit or 100), 200)))
    return {
        "board_type": normalized_type,
        "rows": rows,
        "count": len(rows),
        "_source": "同花顺板块页",
        "_source_note": "东财 clist 不可用时的 HTML 表格 fallback；字段来自公开板块行情页。",
    }


def _parse_browser_board_snapshot(markdown: str) -> list[dict[str, Any]]:
    rows = []
    for line in markdown.splitlines():
        line = line.strip()
        if not line.startswith('row "'):
            continue
        content = line[5:].rstrip('"')
        parts = re.split(r"\s{2,}", content)
        if len(parts) < 4:
            parts = content.split()
        if len(parts) < 3:
            continue
        rank = _safe_int(parts[0])
        if rank is None:
            continue
        rows.append(
            {
                "rank": rank,
                "name": parts[1],
                "change_pct": _safe_float(str(parts[2]).rstrip("%")),
                "up_count": _safe_int(parts[3]) if len(parts) > 3 else None,
                "down_count": _safe_int(parts[4]) if len(parts) > 4 else None,
                "leader": parts[5] if len(parts) > 5 else "",
                "leader_change_pct": (
                    _safe_float(str(parts[6]).rstrip("%")) if len(parts) > 6 else None
                ),
            }
        )
    return rows


def _playwright_html(url: str) -> str:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return ""
    try:
        with sync_playwright() as runtime:
            browser = runtime.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, wait_until="networkidle", timeout=20_000)
            content = page.content()
            browser.close()
            return content
    except Exception as exc:
        diag(f"Browser page unavailable: {exc}")
        return ""


def playwright_board_list(board_type: str = "industry") -> dict[str, Any]:
    anchor = "industry_board" if board_type == "industry" else "concept_board"
    html_text = _playwright_html(f"https://quote.eastmoney.com/center/gridlist.html#{anchor}")
    if not html_text:
        return {"board_type": board_type, "rows": [], "_unavailable": "browser unavailable"}
    text = re.sub(r"<[^>]+>", "  ", html.unescape(html_text))
    rows = _parse_browser_board_snapshot(
        "\n".join(f'row "{line.strip()}"' for line in text.splitlines() if re.match(r"^\s*\d+\s+", line))
    )
    return {"board_type": board_type, "rows": rows, "count": len(rows), "_source": "公开财经页面"}


def browser_board_list(board_type: str = "industry") -> dict[str, Any]:
    base = os.environ.get("STOCK_ANALYSIS_BROWSER_URL", "http://localhost:9377")
    user_id = os.environ.get("STOCK_ANALYSIS_BROWSER_USER_ID", "")
    session_key = os.environ.get("STOCK_ANALYSIS_BROWSER_SESSION_KEY", "")
    if not user_id or not session_key:
        return {"_skipped": "browser service env not set"}

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

        rows = _parse_browser_board_snapshot(md)
        return {"board_type": board_type, "rows": rows, "count": len(rows)}
    except Exception as e:
        diag(f"browser service board {board_type}: {e}")
        return {"_error": str(e)}


# ------------------------------------------------------------------
# 输出格式化
# ------------------------------------------------------------------

def print_index(data: list[dict[str, Any]]) -> None:
    print("## A股指数表现\n")
    print(f"{'指数':<10} {'收盘':>10} {'涨跌':>10} {'涨跌幅':>10} {'成交额':>12}")
    print("-" * 60)
    if not data:
        print("  数据暂不可用（接口可能被风控，请稍后重试或加 --refresh）")
        print()
        return
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


def print_zt_analysis(zt_data: dict, dt_data: dict, zb_data: dict) -> None:
    zt_pool = zt_data.get("data", {}).get("pool", []) if "_error" not in zt_data else []
    dt_pool = dt_data.get("data", {}).get("pool", []) if "_error" not in dt_data else []
    zb_pool = zb_data.get("data", {}).get("pool", []) if "_error" not in zb_data else []
    zt_total = zt_data.get("data", {}).get("tc", len(zt_pool)) if "_error" not in zt_data else 0
    dt_total = dt_data.get("data", {}).get("tc", len(dt_pool)) if "_error" not in dt_data else 0
    zb_total = zb_data.get("data", {}).get("tc", len(zb_pool)) if "_error" not in zb_data else 0

    print("## A股涨跌停与连板梯队\n")
    print(f"涨停: {zt_total} 只 | 跌停: {dt_total} 只 | 炸板: {zb_total} 只")
    if zt_total + zb_total > 0:
        zb_rate = zb_total / (zt_total + zb_total) * 100
        print(f"炸板率: {zb_rate:.1f}% {'(高)' if zb_rate > 40 else ''}")
    print()

    ladders: dict[int, list] = {}
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
    print("\n涨停行业 TOP5:")
    for hy, cnt in hy_counter.most_common(5):
        print(f"  {hy}: {cnt}只")
    print()


def print_fund_flow(flow_data: dict[str, str]) -> None:
    scope_title = "A股资金流向（上证指数口径）"
    if flow_data.get("_fallback_indicator") == "concept_money_flow":
        scope_title = "A股资金流向（概念板块口径）"
    elif flow_data.get("_fallback_indicator") == "sector_money_flow":
        scope_title = "A股资金流向（行业板块口径）"
    elif flow_data.get("_fallback_indicator") == "market_activity":
        scope_title = "A股资金流向（指数活跃度参考）"
    print(f"## {scope_title}\n")
    if not flow_data or "_error" in flow_data:
        print("  暂不展示：当前没有拿到可核验交易日的免登录资金流数据。")
        print()
        return
    if flow_data.get("_unavailable"):
        print("  当前没有拿到可核验交易日的免登录资金流数据。")
        if flow_data.get("_requested_date"):
            print(f"  本次复盘: {flow_data['_requested_date']}")
        if flow_data.get("_latest_date"):
            print(f"  来源最新: {flow_data['_latest_date']}")
        if flow_data.get("_source"):
            print(f"  来源: {flow_data['_source']}")
        print()
        return
    if flow_data.get("date"):
        print(f"  交易日: {flow_data['date']}")
        requested = str(flow_data.get("_requested_date", "")).replace("-", "") or flow_data.get("date", "").replace("-", "")
        if requested:
            print(f"  阶段: {dated_stage_label(data_date=flow_data['date'], requested_date=requested)}")
    if flow_data.get("_date_note") == "latest_available" and flow_data.get("_requested_date"):
        print(f"  提醒: 当前展示来源最新可用数据，本次请求日期为 {flow_data['_requested_date']}")
    if flow_data.get("_cache_note") == "last_known_good":
        print("  提醒: 实时接口暂不可用，当前为本地最近一次可信数据")
    if flow_data.get("_source"):
        print(f"  来源: {flow_data['_source']}")
    if flow_data.get("_fallback_indicator") == "concept_money_flow":
        print(f"  说明: {flow_data.get('_indicator_note', '当前展示概念板块资金流参考，不等同于全市场主力资金净流入。')}")
        try:
            top_in = json.loads(flow_data.get("_concept_in", "[]"))
            top_out = json.loads(flow_data.get("_concept_out", "[]"))
        except json.JSONDecodeError:
            top_in, top_out = [], []
        if top_in:
            print("  概念净流入靠前:")
            for item in top_in[:5]:
                name = item.get("name", "-")
                net = float(item.get("net") or 0)
                leader = item.get("leader") or "-"
                leader_pct = fmt_pct(item.get("leader_change_pct"))
                print(f"    {name}: {net:+.2f}亿，领涨股 {leader}（{leader_pct}）")
        if top_out:
            print("  概念净流出靠前:")
            for item in top_out[:5]:
                name = item.get("name", "-")
                net = float(item.get("net") or 0)
                leader = item.get("leader") or "-"
                leader_pct = fmt_pct(item.get("leader_change_pct"))
                print(f"    {name}: {net:+.2f}亿，领涨股 {leader}（{leader_pct}）")
        else:
            print("  概念净流出靠前: 当前页未返回净流出概念")
        print()
        return
    if flow_data.get("_fallback_indicator") == "sector_money_flow":
        print(f"  说明: {flow_data.get('_indicator_note', '当前展示行业资金流参考，不等同于全市场主力资金净流入。')}")
        try:
            top_in = json.loads(flow_data.get("_sector_in", "[]"))
            top_out = json.loads(flow_data.get("_sector_out", "[]"))
        except json.JSONDecodeError:
            top_in, top_out = [], []
        if top_in:
            print("  行业净流入靠前:")
            for name, value in top_in[:5]:
                print(f"    {name}: {value:+.2f}亿")
        if top_out:
            print("  行业净流出靠前:")
            for name, value in top_out[:5]:
                print(f"    {name}: {value:+.2f}亿")
        print()
        return
    if flow_data.get("_fallback_indicator") == "market_activity":
        print(f"  说明: {flow_data.get('_indicator_note', '当前展示行情活跃度参考，不等同于主力资金净流入。')}")
        print(f"  合计成交额: {fmt_amount(flow_data.get('总成交额'))}")
        for name in ("上证指数", "深证成指"):
            if flow_data.get(f"{name}点位"):
                print(
                    f"  {name}: {fmt_price(flow_data.get(f'{name}点位'))} "
                    f"({fmt_pct(flow_data.get(f'{name}涨跌幅'))})，成交额 {fmt_amount(flow_data.get(f'{name}成交额'))}"
                )
        print()
        return
    print(f"  主力净流入: {fmt_amount(flow_data.get('主力净流入'))}")
    print(f"  超大单:     {fmt_amount(flow_data.get('超大单净流入'))}")
    print(f"  大单:       {fmt_amount(flow_data.get('大单净流入'))}")
    print(f"  中单:       {fmt_amount(flow_data.get('中单净流入'))}")
    print(f"  小单:       {fmt_amount(flow_data.get('小单净流入'))}")
    print()


def fmt_signed_amount(v) -> str:
    try:
        value = float(v)
    except (TypeError, ValueError):
        return "-"
    sign = "+" if value > 0 else ""
    abs_value = abs(value)
    if abs_value >= 1e8:
        return f"{sign}{value / 1e8:.2f}亿"
    if abs_value >= 1e4:
        return f"{sign}{value / 1e4:.2f}万"
    return f"{sign}{value:.0f}"


def print_stock_fund_flow_report(data: dict[str, Any]) -> None:
    title = f"{data.get('name') or data.get('symbol')}({data.get('symbol', '-')})"
    print(f"## 个股资金流向：{title}\n")
    if not data or data.get("_error") or not data.get("rows"):
        print(f"  暂未获取到个股资金流：{data.get('_error', 'empty data') if data else 'empty data'}")
        print()
        return
    print(f"  来源: {data.get('_source', '-')}")
    if data.get("_source_note"):
        print(f"  说明: {data['_source_note']}")
    if data.get("_date_note") == "latest_available":
        print(f"  提醒: 当前展示来源最新可用数据，本次请求日期为 {data.get('_requested_date', '-')}")
    latest = data["rows"][-1]
    print(f"  最新交易日: {latest.get('date', '-')}")
    print(
        "  最新主力: "
        f"{fmt_signed_amount(latest.get('main_net'))} "
        f"({fmt_pct(latest.get('main_pct'))})，"
        f"超大单 {fmt_signed_amount(latest.get('super_big_net'))}，"
        f"大单 {fmt_signed_amount(latest.get('big_net'))}"
    )
    recent = data["rows"][-5:]
    total_main = sum(float(row.get("main_net") or 0) for row in recent)
    print(f"  近{len(recent)}日主力合计: {fmt_signed_amount(total_main)}")
    print()
    print("  最近记录:")
    for row in reversed(recent):
        print(
            f"    {row.get('date', '-')}: 主力 {fmt_signed_amount(row.get('main_net')):>10} "
            f"超大 {fmt_signed_amount(row.get('super_big_net')):>10} "
            f"大单 {fmt_signed_amount(row.get('big_net')):>10} "
            f"小单 {fmt_signed_amount(row.get('small_net')):>10}"
        )
    print()


def print_northbound_flow_report(data: dict[str, Any]) -> None:
    print("## 北向资金流向\n")
    if not data or data.get("_error"):
        print(f"  暂未获取到北向资金流：{data.get('_error', 'empty data') if data else 'empty data'}")
        print()
        return
    print(f"  日期: {data.get('date', '-')}")
    print(f"  时间: {data.get('latest_time', '-')}")
    print(f"  来源: {data.get('_source', '-')}")
    if data.get("_source_note"):
        print(f"  说明: {data['_source_note']}")
    print(f"  沪股通: {data.get('hgt_yi', 0):+.2f}亿")
    print(f"  深股通: {data.get('sgt_yi', 0):+.2f}亿")
    print(f"  合计:   {data.get('total_yi', 0):+.2f}亿")
    print()


def print_block_trades_report(data: dict[str, Any]) -> None:
    title = f"{data.get('name') or data.get('symbol')}({data.get('symbol', '-')})"
    print(f"## A股大宗交易：{title}\n")
    if not data or data.get("_error"):
        print(f"  暂未获取到大宗交易：{data.get('_error', 'empty data') if data else 'empty data'}")
        print()
        return
    if not data.get("rows"):
        print("  近期未查询到大宗交易记录。")
        print()
        return
    print(f"  来源: {data.get('_source', '-')}")
    if data.get("_source_note"):
        print(f"  说明: {data['_source_note']}")
    print()
    for row in data.get("rows", [])[:10]:
        print(
            f"  {row.get('date', '-')}: 价 {fmt_price(row.get('price'))} "
            f"折溢价 {fmt_pct(row.get('premium_pct'))} "
            f"成交 {fmt_amount(row.get('amount'))}"
        )
        buyer = row.get("buyer") or "-"
        seller = row.get("seller") or "-"
        print(f"    买方: {buyer}")
        print(f"    卖方: {seller}")
    print()


def print_boards(board_data: dict[str, Any], title: str) -> None:
    if "_skipped" in board_data or "_error" in board_data:
        return
    rows = board_data.get("rows", [])
    if not rows:
        return
    print(f"## {title}（前15）\n")
    if isinstance(rows[0], dict):
        print(f"{'排名':<4} {'板块':<12} {'涨跌幅':>8} {'涨/跌':>10} {'领涨股':>12}")
        print("-" * 58)
        for i, row in enumerate(rows[:15], 1):
            name = str(row.get("name") or "-")
            breadth = "-"
            if row.get("up_count") is not None and row.get("down_count") is not None:
                breadth = f"{row.get('up_count')}/{row.get('down_count')}"
            leader = str(row.get("leader") or "-")
            print(f"{i:<4} {name:<12} {fmt_pct(row.get('change_pct')):>8} {breadth:>10} {leader:>12}")
        print()
        return
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


def print_sentiment_summary(zt_data: dict, dt_data: dict, zb_data: dict, flow_data: dict) -> None:
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


def print_global_indices(indices: list[QuoteData], market_name: str) -> None:
    print(f"## {market_name} 大盘指数\n")
    activity_label = "成交额" if any(q.turnover is not None for q in indices) else "成交量"
    print(f"{'指数':<15} {'点位':>12} {'涨跌幅':>10} {activity_label:>14} {'来源':>8}")
    print("-" * 72)
    for qd in indices:
        name = qd.name or qd.symbol
        price_str = fmt_price(qd.price)
        pct_str = fmt_pct(qd.change_pct) if qd.change_pct is not None else "-"
        vol_str = fmt_amount(qd.turnover) if qd.turnover is not None else fmt_volume(qd.volume)
        if "volume_missing_index" in qd.quality_flags or "volume_zero" in qd.quality_flags:
            vol_str += " *"
        source_str = {
            "sina": "新浪",
            "tencent": "腾讯",
            "eastmoney_stock_get": "东财",
            "eastmoney_clist": "东财",
        }.get(qd.source, qd.source or "-")
        print(f"{name:<15} {price_str:>12} {pct_str:>10} {vol_str:>14} {source_str:>8}")
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
    if qd.turnover is not None:
        print(f"  成交额: {fmt_amount(qd.turnover)}")
    if qd.turnover_rate is not None and qd.turnover_rate > 0:
        print(f"  换手率: {fmt_pct(qd.turnover_rate)}")
    if qd.market_cap is not None:
        print(f"  总市值: {fmt_amount(qd.market_cap * 1e8)}")
    valuation = []
    if qd.pe is not None and qd.pe > 0:
        valuation.append(f"PE {qd.pe:.2f}")
    if qd.pb is not None and qd.pb > 0:
        valuation.append(f"PB {qd.pb:.2f}")
    if valuation:
        print(f"  估值:   {' | '.join(valuation)}")
    if qd.high_52w is not None or qd.low_52w is not None:
        print(f"  52周:   {fmt_price(qd.low_52w)} - {fmt_price(qd.high_52w)}")
    print(f"  货币:   {qd.currency}")
    if qd.change is not None and qd.change_pct is not None:
        print(f"  涨跌:   {qd.change:+.2f} ({qd.change_pct:+.2f}%)")
    if qd.notes:
        print(f"  ⚠️ {', '.join(qd.notes)}")
    print()


def _source_label(source: str) -> str:
    return {
        "sina": "新浪财经",
        "tencent": "腾讯财经",
        "eastmoney_stock_get": "东方财富",
        "eastmoney_clist": "东方财富",
    }.get(source, source or "-")


def _market_label(market: str) -> str:
    return {
        "cn_market": "A股",
        "hk_market": "港股",
        "us_market": "美股",
    }.get(market, market)


def _is_usable_quote(qd: QuoteData | None) -> bool:
    return bool(qd and qd.price is not None and qd.completeness >= 50)


def _quote_from_cache(data: dict[str, Any] | None) -> QuoteData | None:
    if not data:
        return None
    try:
        return QuoteData(**data)
    except TypeError:
        return None


def normalize_fund_code(code: str) -> str:
    code = str(code).strip()
    if not re.fullmatch(r"\d{6}", code):
        raise ValueError("基金代码应为 6 位数字，例如 161725")
    return code


def _compact_date(value: str) -> str:
    return re.sub(r"\D", "", str(value or ""))[:8]


def _date_plus_days(date_str: str, days: int) -> str:
    return (datetime.strptime(_compact_date(date_str), "%Y%m%d") + timedelta(days=days)).strftime("%Y%m%d")


def _stock_secid_for_history(symbol: str) -> tuple[str, str, str]:
    normalized, market = normalize_stock_symbol(symbol)
    if market == "cn_market":
        return normalized, market, _cn_secid(normalized)
    if market == "hk_market":
        return normalized, market, _hk_secid(normalized)
    secid = _us_secid(normalized)
    if not secid:
        raise ValueError(f"暂不支持自动回溯该美股历史价格: {symbol}")
    return normalized, market, secid


def fetch_stock_close_on_or_after(symbol: str, buy_date: str) -> dict[str, Any]:
    """Fetch first available split-adjusted daily close on/after buy_date."""
    compact = _compact_date(buy_date)
    if not re.fullmatch(r"\d{8}", compact):
        return {"_error": "买入日期应为 YYYYMMDD 或 YYYY-MM-DD"}
    try:
        normalized, market, secid = _stock_secid_for_history(symbol)
    except ValueError as e:
        return {"_error": str(e)}
    end = _date_plus_days(compact, 10)
    cached = cache_load(f"stock_buy_{normalized}", compact, "eastmoney_kline", ttl=86400)
    if cached:
        return cached
    url = EM_KLINE_URL.format(secid=secid, beg=compact, end=end, ts=int(time.time() * 1000))
    data = fetch_json(url, {"Referer": "https://quote.eastmoney.com/"})
    if "_error" in data:
        return data
    klines = (data.get("data") or {}).get("klines") or []
    for row in klines:
        parts = str(row).split(",")
        if len(parts) >= 3:
            result = {
                "symbol": normalized,
                "market": market,
                "date": parts[0],
                "close": _safe_float(parts[2]),
                "_source": "东方财富历史K线",
            }
            if result["close"] is not None:
                cache_save(f"stock_buy_{normalized}", compact, "eastmoney_kline", result)
                return result
    return {"_error": "买入日附近未获取到可用股票收盘价"}


def fetch_stock_history_quote(symbol: str, trade_date: str) -> QuoteData | None:
    """Fetch exact-date historical quote fields from Eastmoney kline."""
    compact = _compact_date(trade_date)
    if not re.fullmatch(r"\d{8}", compact):
        return None
    try:
        normalized, market, secid = _stock_secid_for_history(symbol)
    except ValueError:
        return None
    cached = _quote_from_cache(cache_load(f"stock_history_{normalized}", compact, "eastmoney_kline", ttl=86400))
    if _is_usable_quote(cached):
        return cached
    url = EM_KLINE_URL.format(secid=secid, beg=compact, end=compact, ts=int(time.time() * 1000))
    data = fetch_json(url, {"Referer": "https://quote.eastmoney.com/"})
    if "_error" in data:
        return None
    payload = data.get("data") or {}
    rows = payload.get("klines") or []
    if not rows:
        return None
    parts = str(rows[-1]).split(",")
    if len(parts) < 11 or parts[0].replace("-", "") != compact:
        return None
    currency = "USD" if market == "us_market" else ("HKD" if market == "hk_market" else "CNY")
    qd = QuoteData(
        symbol=normalized,
        name=str(payload.get("name") or normalized),
        market=market,
        date=parts[0].replace("-", ""),
        open_price=_safe_float(parts[1]),
        price=_safe_float(parts[2]),
        high=_safe_float(parts[3]),
        low=_safe_float(parts[4]),
        volume=_safe_int(parts[5]),
        turnover=_safe_float(parts[6]),
        amplitude_pct=_safe_float(parts[7]),
        change_pct=_safe_float(parts[8]),
        change=_safe_float(parts[9]),
        turnover_rate=_safe_float(parts[10]),
        currency=currency,
        source="eastmoney-kline",
    )
    quote = validate_quote(qd)
    cache_save(f"stock_history_{normalized}", compact, "eastmoney_kline", quote.to_dict())
    return quote


def fetch_fund_nav_on_or_after(fund_code: str, buy_date: str) -> dict[str, Any]:
    """Fetch first available fund NAV on/after buy_date."""
    fund_code = normalize_fund_code(fund_code)
    compact = _compact_date(buy_date)
    if not re.fullmatch(r"\d{8}", compact):
        return {"_error": "买入日期应为 YYYYMMDD 或 YYYY-MM-DD"}
    start = datetime.strptime(compact, "%Y%m%d").strftime("%Y-%m-%d")
    end = datetime.strptime(_date_plus_days(compact, 20), "%Y%m%d").strftime("%Y-%m-%d")
    cached = cache_load(f"fund_buy_{fund_code}", compact, "eastmoney_fund_nav", ttl=86400)
    if cached:
        return cached
    url = FUND_NAV_HISTORY_URL.format(code=fund_code, start=start, end=end, ts=int(time.time() * 1000))
    data = fetch_json(url, {"Referer": f"https://fundf10.eastmoney.com/jjjz_{fund_code}.html"})
    if "_error" in data:
        return data
    rows = ((data.get("Data") or {}).get("LSJZList") or [])
    rows = sorted(rows, key=lambda row: str(row.get("FSRQ") or ""))
    for row in rows:
        nav = _safe_float(row.get("DWJZ"))
        if nav is not None:
            result = {
                "fundcode": fund_code,
                "date": row.get("FSRQ") or "",
                "nav": nav,
                "_source": "东方财富历史净值",
            }
            cache_save(f"fund_buy_{fund_code}", compact, "eastmoney_fund_nav", result)
            return result
    return {"_error": "买入日附近未获取到可用基金净值"}


def fetch_fund_nav_quote(fund_code: str, trade_date: str) -> dict[str, Any]:
    """Fetch fund NAV and one-day change for a historical report date."""
    fund_code = normalize_fund_code(fund_code)
    compact = _compact_date(trade_date)
    if not re.fullmatch(r"\d{8}", compact):
        return {"_error": "交易日期应为 YYYYMMDD 或 YYYY-MM-DD"}
    cached = cache_load(f"fund_nav_quote_{fund_code}", compact, "eastmoney_fund_nav", ttl=86400)
    if cached and cached.get("_nav_quote_version") == 2:
        return cached
    target_date = datetime.strptime(compact, "%Y%m%d")
    start = (target_date - timedelta(days=14)).strftime("%Y-%m-%d")
    end = target_date.strftime("%Y-%m-%d")
    url = FUND_NAV_HISTORY_URL.format(code=fund_code, start=start, end=end, ts=int(time.time() * 1000))
    data = fetch_json(url, {"Referer": f"https://fundf10.eastmoney.com/jjjz_{fund_code}.html"})
    if "_error" in data:
        return data
    rows = sorted(((data.get("Data") or {}).get("LSJZList") or []), key=lambda row: str(row.get("FSRQ") or ""))
    usable = [
        row
        for row in rows
        if row.get("FSRQ") and str(row.get("FSRQ")) <= target_date.strftime("%Y-%m-%d") and _safe_float(row.get("DWJZ")) is not None
    ]
    if not usable:
        return {"_error": "交易日前未获取到可用基金净值"}
    current = usable[-1]
    previous = usable[-2] if len(usable) >= 2 else {}
    nav = _safe_float(current.get("DWJZ"))
    previous_nav = _safe_float(previous.get("DWJZ"))
    official_change_pct = _safe_float(current.get("JZZZL"))
    if official_change_pct is not None and nav is not None and official_change_pct > -100:
        adjusted_previous = nav / (1 + official_change_pct / 100)
        change = nav - adjusted_previous
        change_pct = official_change_pct
    else:
        change = nav - previous_nav if nav is not None and previous_nav not in (None, 0) else None
        change_pct = change / previous_nav * 100 if change is not None and previous_nav else None
    result = {
        "fundcode": fund_code,
        "date": current.get("FSRQ") or "",
        "nav": nav,
        "previous_nav": previous_nav,
        "change": change,
        "change_pct": change_pct,
        "_source": "东方财富历史净值",
        "_nav_quote_version": 2,
    }
    if current.get("FHSP"):
        result["split_note"] = current.get("FHSP")
    if str(current.get("FSRQ") or "").replace("-", "") != compact:
        result["_date_note"] = "nearest_available_nav"
        result["_requested_date"] = compact
    cache_save(f"fund_nav_quote_{fund_code}", compact, "eastmoney_fund_nav", result)
    return result


def fetch_fund_estimate(fund_code: str, date_str: str) -> dict[str, Any]:
    fund_code = normalize_fund_code(fund_code)
    cached = cache_load(f"fund_estimate_{fund_code}", date_str, "eastmoney_fund")
    if cached:
        return cached

    url = FUND_ESTIMATE_URL.format(code=fund_code, ts=int(time.time() * 1000))
    data = fetch_json(url, {"Referer": f"https://fund.eastmoney.com/{fund_code}.html"})
    if "_error" in data:
        diag(f"Fund estimate {fund_code}: {data['_error']}")
        return data

    gztime = str(data.get("gztime") or "")
    estimate_date = _source_date(gztime) or _source_date(str(data.get("jzrq") or ""))
    result = {
        "fundcode": fund_code,
        "name": data.get("name") or fund_code,
        "nav_date": data.get("jzrq") or "",
        "nav": data.get("dwjz") or "",
        "estimate_nav": data.get("gsz") or "",
        "estimate_change_pct": data.get("gszzl") or "",
        "estimate_time": gztime,
        "date": estimate_date,
        "_source": "天天基金实时估值",
    }
    if estimate_date and estimate_date.replace("-", "") != date_str:
        result["_requested_date"] = _display_date(date_str)
        result["_date_note"] = "latest_available"
    cache_save(f"fund_estimate_{fund_code}", date_str, "eastmoney_fund", result)
    return result


def parse_fund_profile_js(fund_code: str, raw: str) -> dict[str, Any]:
    fund_code = normalize_fund_code(fund_code)
    text = raw.lstrip("\ufeff")
    returns = {
        label: value
        for label, var_name in (("近1月", "syl_1y"), ("近3月", "syl_3y"), ("近6月", "syl_6y"), ("近1年", "syl_1n"))
        if (value := _safe_number(_js_string_var(text, var_name))) is not None
    }
    performance_raw = _js_json_var(text, "Data_performanceEvaluation") or {}
    categories = performance_raw.get("categories") or []
    scores = performance_raw.get("data") or []
    performance = {
        "average_score": _safe_number(performance_raw.get("avr")),
        "metrics": {
            str(name): _safe_number(score)
            for name, score in zip(categories, scores)
            if name and _safe_number(score) is not None
        },
    }
    scale_raw = _js_json_var(text, "Data_fluctuationScale") or {}
    scale = _latest_fund_scale(scale_raw)
    managers = [
        _normalize_fund_manager(row)
        for row in (_js_json_var(text, "Data_currentFundManager") or [])
        if isinstance(row, dict)
    ]
    managers = [row for row in managers if row.get("name")]
    return {
        "fundcode": fund_code,
        "name": _js_string_var(text, "fS_name") or fund_code,
        "returns": returns,
        "fees": {
            "front_end_source_rate_pct": _safe_number(_js_string_var(text, "fund_sourceRate")),
            "front_end_rate_pct": _safe_number(_js_string_var(text, "fund_Rate")),
            "min_purchase_cny": _safe_number(_js_string_var(text, "fund_minsg")),
        },
        "scale": scale,
        "performance_evaluation": performance,
        "managers": managers,
        "_source": "天天基金公开评估页",
    }


def fetch_fund_profile(fund_code: str, date_str: str) -> dict[str, Any]:
    fund_code = normalize_fund_code(fund_code)
    cached = cache_load(f"fund_profile_{fund_code}", date_str, "eastmoney_pingzhongdata", ttl=24 * 3600)
    if cached:
        return cached
    url = FUND_PROFILE_URL.format(code=fund_code, ts=int(time.time() * 1000))
    try:
        raw = _fetch_raw(url, {"Referer": f"https://fund.eastmoney.com/{fund_code}.html"}, timeout=15)
    except Exception as e:
        diag(f"Fund profile {fund_code}: {e}")
        result = {"fundcode": fund_code, "name": fund_code, "_error": str(e), "_source": "天天基金公开评估页"}
    else:
        result = parse_fund_profile_js(fund_code, raw)
    result = _merge_fund_profile(result, fetch_fundmob_f10_profile(fund_code))
    cache_save(f"fund_profile_{fund_code}", date_str, "eastmoney_pingzhongdata", result)
    return result


def fetch_fundmob_f10_profile(fund_code: str) -> dict[str, Any]:
    fund_code = normalize_fund_code(fund_code)
    params = {
        "FCODE": fund_code,
        "deviceid": "stock-analysis",
        "plat": "Android",
        "product": "EFund",
        "version": "6.5.8",
    }
    url = f"{FUND_MOB_F10_URL}?{urllib.parse.urlencode(params)}"
    data = fetch_json(url, {"Referer": f"https://fundf10.eastmoney.com/jbgk_{fund_code}.html"})
    if "_error" in data:
        return data
    payload = data.get("Datas") or data.get("data") or {}
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            payload = {}
    if isinstance(payload, list):
        payload = payload[0] if payload and isinstance(payload[0], dict) else {}
    if not isinstance(payload, dict) or not payload:
        return {}
    scale_value = _first_number(
        payload,
        "ENDNAV",
        "FUNDSCALE",
        "JJGM",
        "NETASSET",
        "NETASSETVALUE",
    )
    scale_date = _first_text(payload, "FSRQ", "PDATE", "ENDDATE", "JZDATE")
    scale_mom = _format_percent_text(_first_text(payload, "RZDF", "SCALECHG", "MOM"))
    result = {
        "fundcode": _first_text(payload, "FCODE") or fund_code,
        "name": _first_text(payload, "SHORTNAME", "NAME", "FUNDSNAME") or fund_code,
        "returns": _fundmob_returns(payload),
        "fees": {
            "front_end_source_rate_pct": _first_number(payload, "SOURCE_RATE", "ORIGINALRATE", "fund_sourceRate"),
            "front_end_rate_pct": _first_number(payload, "RATE", "DISCOUNTRATE", "fund_Rate"),
            "min_purchase_cny": _first_number(payload, "MINSGBL", "MINSG", "fund_minsg"),
        },
        "scale": {
            "latest_size_yi": scale_value,
            "asof": scale_date,
            "mom": scale_mom,
        },
        "performance_evaluation": {"average_score": _first_number(payload, "AVR", "SCORE"), "metrics": {}},
        "managers": _fundmob_managers(payload),
        "purchase_status": {
            "subscribe": _first_text(payload, "SGZT", "SUBSCRIBESTATUS"),
            "redeem": _first_text(payload, "SHZT", "REDEEMSTATUS"),
        },
        "_source": "eastmoney_fundmob_f10",
    }
    if not any(result["purchase_status"].values()):
        result.pop("purchase_status")
    return result


def _merge_fund_profile(primary: dict[str, Any], supplemental: dict[str, Any]) -> dict[str, Any]:
    if not supplemental or supplemental.get("_error"):
        return primary
    result = dict(primary or {})
    for key in ("fundcode", "name"):
        if not result.get(key) and supplemental.get(key):
            result[key] = supplemental[key]
    for key in ("returns", "fees", "scale", "performance_evaluation"):
        result[key] = _merge_missing_dict(result.get(key), supplemental.get(key))
    if not result.get("managers") and supplemental.get("managers"):
        result["managers"] = supplemental["managers"]
    if supplemental.get("purchase_status"):
        result["purchase_status"] = _merge_missing_dict(result.get("purchase_status"), supplemental.get("purchase_status"))
    sources = [
        str(source)
        for source in (result.get("_source"), supplemental.get("_source"))
        if source and str(source) not in {"{}", "[]"}
    ]
    if sources:
        result["_source"] = " + ".join(dict.fromkeys(sources))
    return result


def _merge_missing_dict(primary: Any, supplemental: Any) -> dict[str, Any]:
    result = dict(primary or {}) if isinstance(primary, dict) else {}
    extra = supplemental if isinstance(supplemental, dict) else {}
    for key, value in extra.items():
        if isinstance(value, dict):
            result[key] = _merge_missing_dict(result.get(key), value)
        elif result.get(key) in (None, "", {}, []):
            result[key] = value
    return result


def _fundmob_returns(payload: dict[str, Any]) -> dict[str, float]:
    mapping = (
        ("近1月", ("SYL_1Y", "RZDF1M", "MONTH1")),
        ("近3月", ("SYL_3Y", "RZDF3M", "MONTH3")),
        ("近6月", ("SYL_6Y", "RZDF6M", "MONTH6")),
        ("近1年", ("SYL_1N", "RZDF1Y", "YEAR1")),
    )
    result: dict[str, float] = {}
    for label, keys in mapping:
        value = _first_number(payload, *keys)
        if value is not None:
            result[label] = value
    return result


def _fundmob_managers(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("JJJL") or payload.get("MANAGERS") or payload.get("FundManagers") or []
    if isinstance(rows, dict):
        rows = [rows]
    managers: list[dict[str, Any]] = []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        name = _first_text(row, "MGR", "NAME", "JJJL")
        if not name:
            continue
        managers.append(
            {
                "name": name,
                "star": row.get("STAR"),
                "work_time": _first_text(row, "TOTALDAYS", "WORKTIME", "WORKDAYS"),
                "fund_size": _first_text(row, "NETNAV", "FUNDSIZE", "INMANAGESCALE"),
                "score": _first_number(row, "SCORE", "AVR"),
                "tenure_return_pct": _first_number(row, "PENAVGROWTH", "TENURERETURN", "PROFIT"),
                "same_type_avg_pct": _first_number(row, "PENAVRRETURN", "SAMEAVG"),
                "benchmark_return_pct": _first_number(row, "BENCHMARKRETURN", "BENCHMARK"),
            }
        )
    return managers


def _first_text(payload: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = payload.get(key)
        if value not in (None, "", "--", "-"):
            return str(value).strip()
    return ""


def _first_number(payload: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = _safe_number(payload.get(key))
        if value is not None:
            return value
    return None


def _format_percent_text(value: str) -> str:
    value = str(value or "").strip()
    if not value or value in {"-", "--"}:
        return ""
    return value if value.endswith("%") else f"{value}%"


def _js_string_var(text: str, name: str) -> str:
    match = re.search(rf"var\s+{re.escape(name)}\s*=\s*\"(.*?)\"\s*;", text, re.DOTALL)
    return html.unescape(match.group(1)) if match else ""


def _js_json_var(text: str, name: str) -> Any:
    match = re.search(rf"var\s+{re.escape(name)}\s*=\s*(.*?)\s*;", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return None


def _latest_fund_scale(raw: dict[str, Any]) -> dict[str, Any]:
    categories = raw.get("categories") or []
    series = raw.get("series") or []
    if not categories or not series:
        return {}
    latest = series[-1] or {}
    return {
        "asof": categories[-1],
        "latest_size_yi": _safe_number(latest.get("y")),
        "mom": latest.get("mom") or "",
    }


def _normalize_fund_manager(row: dict[str, Any]) -> dict[str, Any]:
    profit_rows = (((row.get("profit") or {}).get("series") or [{}])[0].get("data") or [])
    return {
        "name": row.get("name") or "",
        "star": row.get("star"),
        "work_time": row.get("workTime") or "",
        "fund_size": row.get("fundSize") or "",
        "score": _safe_number((row.get("power") or {}).get("avr")),
        "tenure_return_pct": _safe_number((profit_rows[0] if len(profit_rows) > 0 else {}).get("y")),
        "same_type_avg_pct": _safe_number((profit_rows[1] if len(profit_rows) > 1 else {}).get("y")),
        "benchmark_return_pct": _safe_number((profit_rows[2] if len(profit_rows) > 2 else {}).get("y")),
    }


def _html_to_text(value: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", value or "")).strip()


def _safe_number(value: str) -> float | None:
    value = str(value or "").replace(",", "").replace("%", "").strip()
    if not value or value in {"-", "--"}:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def fetch_fund_holdings(fund_code: str, date_str: str, limit: int = 10) -> dict[str, Any]:
    fund_code = normalize_fund_code(fund_code)
    cached = cache_load(f"fund_holdings_{fund_code}", date_str, "eastmoney_fund", ttl=24 * 3600)
    if cached:
        return cached

    url = FUND_HOLDINGS_URL.format(code=fund_code, topline=limit, ts=f"{time.time():.3f}")
    try:
        raw = _fetch_raw(url, {"Referer": f"https://fundf10.eastmoney.com/ccmx_{fund_code}.html"}, timeout=15)
    except Exception as e:
        diag(f"Fund holdings {fund_code}: {e}")
        return {"_error": str(e)}

    title_match = re.search(r"<h4[^>]*class='t'.*?<label[^>]*class='left'>(.*?)</label>", raw, re.DOTALL)
    title = _html_to_text(title_match.group(1)) if title_match else ""
    asof_match = re.search(r"截止至：<font[^>]*>(.*?)</font>", raw)
    asof = _html_to_text(asof_match.group(1)) if asof_match else ""
    row_matches = re.findall(r"<tr>(.*?)</tr>", raw, re.DOTALL)
    holdings: list[dict[str, Any]] = []
    for row in row_matches:
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.DOTALL)
        if len(cells) < 9:
            continue
        code = _html_to_text(cells[1])
        name = _html_to_text(cells[2])
        if not re.fullmatch(r"\d{6}", code) or not name:
            continue
        holdings.append(
            asdict(
                FundHolding(
                    code=code,
                    name=name,
                    weight_pct=_safe_number(_html_to_text(cells[6])),
                    shares_10k=_safe_number(_html_to_text(cells[7])),
                    market_value_10k=_safe_number(_html_to_text(cells[8])),
                )
            )
        )
        if len(holdings) >= limit:
            break

    result = {
        "fundcode": fund_code,
        "title": title,
        "asof": asof,
        "holdings": holdings,
        "_source": "天天基金持仓明细",
    }
    cache_save(f"fund_holdings_{fund_code}", date_str, "eastmoney_fund", result)
    return result


def fetch_fund_holding_quotes(holdings: list[dict[str, Any]], date_str: str) -> dict[str, QuoteData]:
    codes = [str(item.get("code") or "") for item in holdings if item.get("code")]
    if not codes:
        return {}
    if _compact_date(date_str) < datetime.now().strftime("%Y%m%d"):
        return {
            q.symbol: q
            for q in (fetch_stock_history_quote(code, date_str) for code in codes)
            if _is_usable_quote(q)
        }
    quotes = fetch_cn_stocks_sina(codes, date_str)
    tencent_quotes = fetch_cn_stocks_tencent(codes, date_str)
    if not _has_all_quotes(quotes, codes):
        quotes = merge_quotes_by_symbol(quotes, tencent_quotes, codes)
    quotes = enrich_quotes_by_symbol(quotes, tencent_quotes, codes)
    if not _has_all_quotes(quotes, codes):
        quotes = merge_quotes_by_symbol(quotes, fetch_cn_stocks_direct(codes, date_str), codes)
    return {q.symbol: q for q in quotes if _is_usable_quote(q)}


def get_single_stock_quote(symbol: str, date_str: str) -> QuoteData | None:
    normalized, market = normalize_stock_symbol(symbol)
    cached = _quote_from_cache(cache_load(normalized, date_str, "single_stock"))
    if _is_usable_quote(cached):
        return cached

    quotes: list[QuoteData] = []
    if market == "cn_market":
        quotes = fetch_cn_stocks_sina([normalized], date_str)
        tencent_quotes = fetch_cn_stocks_tencent([normalized], date_str)
        if not _has_all_quotes(quotes, [normalized]):
            quotes = merge_quotes_by_symbol(quotes, tencent_quotes, [normalized])
        quotes = enrich_quotes_by_symbol(quotes, tencent_quotes, [normalized])
        if not _has_all_quotes(quotes, [normalized]):
            quotes = merge_quotes_by_symbol(quotes, fetch_cn_stocks_direct([normalized], date_str), [normalized])
    elif market == "hk_market":
        quotes = fetch_hk_stocks_sina([normalized], date_str)
        tencent_quotes = fetch_hk_stocks_tencent([normalized], date_str)
        if not _has_all_quotes(quotes, [normalized]):
            quotes = merge_quotes_by_symbol(quotes, tencent_quotes, [normalized])
        quotes = enrich_quotes_by_symbol(quotes, tencent_quotes, [normalized])
        if not _has_all_quotes(quotes, [normalized]):
            quotes = merge_quotes_by_symbol(quotes, fetch_hk_stocks_direct([normalized], date_str), [normalized])
        if not _has_all_quotes(quotes, [normalized]):
            quotes = merge_quotes_by_symbol(quotes, fetch_em_stocks([normalized], date_str, EM_FS["hk_stock"]), [normalized])
    elif market == "us_market":
        quotes = fetch_us_stocks_sina([normalized], date_str)
        tencent_quotes = fetch_us_stocks_tencent([normalized], date_str)
        if not _has_all_quotes(quotes, [normalized]):
            quotes = merge_quotes_by_symbol(quotes, tencent_quotes, [normalized])
        quotes = enrich_quotes_by_symbol(quotes, tencent_quotes, [normalized])
        if not _has_all_quotes(quotes, [normalized]):
            quotes = merge_quotes_by_symbol(quotes, fetch_us_stocks_direct([normalized], date_str), [normalized])
        if not _has_all_quotes(quotes, [normalized]):
            quotes = merge_quotes_by_symbol(quotes, fetch_em_stocks([normalized], date_str, EM_FS["us_stock"]), [normalized])

    qd = quotes[0] if quotes else None
    if not _is_usable_quote(qd):
        diag(f"No verified single-stock quote for {normalized}")
        return None

    cache_save(normalized, date_str, "single_stock", qd.to_dict())
    return qd


def print_single_stock_unavailable(symbol: str, reason: str) -> None:
    print(f"# 个股速览：{symbol}\n")
    print(f"暂未拿到可核验行情：{reason}")
    print("可以稍后加 --refresh 重试，或确认代码格式，例如 A股 600519、港股 0700.HK、美股 AAPL。")


def print_single_stock_report(qd: QuoteData, requested_date: str) -> None:
    print(f"# 个股速览：{qd.name or qd.symbol} ({qd.symbol})\n")
    print(f"市场: {_market_label(qd.market)} | 来源: {_source_label(qd.source)} | 数据日期: {qd.date or '-'}")
    print(f"当前阶段: {dated_stage_label(data_date=qd.date, requested_date=requested_date)}")
    if qd.date and qd.date.replace("-", "") != requested_date:
        print(f"提醒: 当前展示数据源最新可用交易日，本次请求日期为 {_display_date(requested_date)}")
    print()
    print(f"  最新价: {fmt_price(qd.price)} {qd.currency}")
    if qd.change is not None or qd.change_pct is not None:
        change_str = f"{qd.change:+.2f}" if qd.change is not None else "-"
        print(f"  涨跌:   {change_str} ({fmt_pct(qd.change_pct)})")
    print(f"  昨收:   {fmt_price(qd.prev_close)}")
    print(f"  开盘:   {fmt_price(qd.open_price)}")
    print(f"  最高:   {fmt_price(qd.high)}")
    print(f"  最低:   {fmt_price(qd.low)}")
    if qd.turnover is not None:
        print(f"  成交额: {fmt_amount(qd.turnover)}")
    print(f"  成交量: {fmt_volume(qd.volume)}")
    if qd.turnover_rate is not None and qd.turnover_rate > 0:
        print(f"  换手率: {fmt_pct(qd.turnover_rate)}")
    if qd.market_cap is not None:
        print(f"  总市值: {fmt_amount(qd.market_cap * 1e8)}")
    valuation = []
    if qd.pe is not None and qd.pe > 0:
        valuation.append(f"PE {qd.pe:.2f}")
    if qd.pb is not None and qd.pb > 0:
        valuation.append(f"PB {qd.pb:.2f}")
    if valuation:
        print(f"  估值:   {' | '.join(valuation)}")
    if qd.high_52w is not None or qd.low_52w is not None:
        print(f"  52周:   {fmt_price(qd.low_52w)} - {fmt_price(qd.high_52w)}")
    if qd.notes:
        print(f"  提醒:   {'；'.join(qd.notes)}")
    print()


def print_fund_report(
    fund: dict[str, Any],
    holdings_data: dict[str, Any],
    quotes_by_code: dict[str, QuoteData],
    requested_date: str,
) -> None:
    fund_code = str(fund.get("fundcode") or holdings_data.get("fundcode") or "")
    fund_name = str(fund.get("name") or holdings_data.get("title") or fund_code)
    print(f"# 基金持仓速览：{fund_name} ({fund_code})\n")
    print("市场: A股基金持仓")
    if fund.get("date"):
        print(f"当前阶段: {dated_stage_label(data_date=str(fund.get('date')), requested_date=requested_date)}")
    else:
        print_stage_line(requested_date)
    if fund.get("_date_note") == "latest_available" and fund.get("_requested_date"):
        print(f"提醒: 当前展示来源最新可用估值，本次请求日期为 {fund['_requested_date']}")
    print(f"基金数据源: {fund.get('_source', '-')}")
    if fund.get("nav_date") or fund.get("nav"):
        print(f"上一净值: {fund.get('nav', '-')}（{fund.get('nav_date', '-')}）")
    if fund.get("estimate_change_pct") or fund.get("estimate_nav"):
        print(
            "当日估算: "
            f"{fund.get('estimate_nav', '-')}（{fmt_pct(fund.get('estimate_change_pct'))}，{fund.get('estimate_time', '-')}）"
        )
        print("说明: 基金正式净值通常晚间更新，此处为天天基金盘中/收盘估算。")
    print()

    holdings = holdings_data.get("holdings", [])
    if not holdings:
        print("## 持仓股行情\n")
        print("  暂未获取到该基金的公开持仓明细。")
        print()
        return

    asof = holdings_data.get("asof") or "-"
    print(f"## 持仓股行情（前{min(len(holdings), 10)}，持仓截止 {asof}）\n")
    stale_note = _fund_holding_staleness_note(asof, requested_date)
    if stale_note:
        print(stale_note)
        print()
    print(f"{'股票':<14} {'占净值':>8} {'最新价':>10} {'涨跌幅':>10} {'估算贡献':>10} {'来源':>8}")
    print("-" * 72)
    contribution = 0.0
    contribution_count = 0
    for item in holdings[:10]:
        code = str(item.get("code") or "")
        qd = quotes_by_code.get(code)
        weight = item.get("weight_pct")
        pct = qd.change_pct if qd else None
        contrib = None
        if weight is not None and pct is not None:
            contrib = float(weight) * float(pct) / 100
            contribution += contrib
            contribution_count += 1
        name = str(item.get("name") or code)
        stock_label = f"{name}({code})"
        print(
            f"{stock_label:<14} "
            f"{fmt_pct(weight).replace('+', ''):>8} "
            f"{fmt_price(qd.price if qd else None):>10} "
            f"{fmt_pct(pct):>10} "
            f"{fmt_pct(contrib):>10} "
            f"{_source_label(qd.source) if qd else '-':>8}"
        )
    print()
    if contribution_count:
        print(f"前{contribution_count}只可取行情持仓股对净值的估算贡献: {contribution:+.2f}%")
        print("说明: 该贡献只按公开季报持仓和当日股价粗略估算，未包含调仓、仓位变化、现金、债券等影响。")
        print()


def _fund_holding_staleness_note(asof: str, requested_date: str) -> str:
    try:
        asof_dt = datetime.strptime(str(asof), "%Y-%m-%d")
        req_dt = datetime.strptime(requested_date, "%Y%m%d")
    except (TypeError, ValueError):
        return ""
    days = max(0, (req_dt - asof_dt).days)
    if days < 30:
        return f"持仓时效: {asof}（距请求日 {days} 天）。"
    return f"持仓时效: {asof}（距请求日 {days} 天，季报持仓可能已调仓；建议结合基金公告和实时估值变化。）"


def print_fund_holding_news(
    holdings: list[dict[str, Any]],
    heat: dict[str, dict[str, Any]],
    ranked_symbols: list[str],
    limit: int = 5,
) -> None:
    print(f"## 持仓股相关新闻（当天多源热度 Top{limit}）\n")
    if not ranked_symbols:
        print("  目前暂未获取到有效新闻信息。")
        print()
        return

    name_map = {str(item.get("code")): str(item.get("name") or item.get("code")) for item in holdings}
    shown = 0
    seen_titles: set[str] = set()
    for code in ranked_symbols:
        news = heat.get(code, {}).get("news") or {}
        for item in news.get("data", []):
            title = _clean_news_title(str(item.get("title") or ""))
            if not title or title in seen_titles:
                continue
            seen_titles.add(title)
            ts = _parse_news_time(item.get("publish_time"))
            dt_str = datetime.fromtimestamp(ts).strftime("%m-%d %H:%M") if ts else ""
            source = _news_source_label(str(item.get("source") or news.get("source") or ""))
            url = _normalize_news_url(item)
            shown += 1
            print(f"{shown}. {name_map.get(code, code)}({code}) [{dt_str}] {title}")
            print(f"   来源: {source} | 链接: {url or '暂无公开链接'}")
            break
        if shown >= limit:
            break
    if shown == 0:
        print("  目前暂未获取到有效新闻信息。")
    print()


def run_stock_fund_flow_report(symbol: str, date_str: str, limit: int = 20) -> None:
    DIAGNOSTICS.clear()
    try:
        data = fetch_stock_fund_flow_daily(symbol, date_str, limit=limit)
    except ValueError as exc:
        data = {"symbol": symbol, "rows": [], "_error": str(exc)}
    print_stock_fund_flow_report(data)
    if DIAGNOSTICS:
        print_diagnostic_summary()
    print_report_footer()


def run_northbound_flow_report(date_str: str) -> None:
    DIAGNOSTICS.clear()
    data = fetch_northbound_flow_snapshot(date_str)
    print_northbound_flow_report(data)
    if DIAGNOSTICS:
        print_diagnostic_summary()
    print_report_footer()


def run_block_trades_report(symbol: str, date_str: str, limit: int = 10) -> None:
    DIAGNOSTICS.clear()
    try:
        data = fetch_block_trades(symbol, date_str, limit=limit)
    except ValueError as exc:
        data = {"symbol": symbol, "rows": [], "_error": str(exc)}
    print_block_trades_report(data)
    if DIAGNOSTICS:
        print_diagnostic_summary()
    print_report_footer()


def run_fund_report(fund_code: str, date_str: str, include_news: bool = True) -> None:
    DIAGNOSTICS.clear()
    try:
        fund_code = normalize_fund_code(fund_code)
    except ValueError as e:
        print(f"# 基金持仓速览：{fund_code}\n")
        print(f"暂未拿到可核验基金数据：{e}")
        print_report_footer()
        return

    fund = fetch_fund_estimate(fund_code, date_str)
    holdings_data = fetch_fund_holdings(fund_code, date_str, limit=10)
    if "_error" in fund and "_error" in holdings_data:
        print(f"# 基金持仓速览：{fund_code}\n")
        print("暂未拿到可核验基金数据，可以稍后加 --refresh 重试。")
        print_report_footer()
        return

    holdings = holdings_data.get("holdings", []) if "_error" not in holdings_data else []
    quotes_by_code = fetch_fund_holding_quotes(holdings, date_str)
    print_fund_report(fund if "_error" not in fund else {"fundcode": fund_code}, holdings_data, quotes_by_code, date_str)

    if include_news and holdings:
        news_holdings = holdings[:5]
        names = {str(item.get("code")): str(item.get("name") or item.get("code")) for item in news_holdings}
        ranked, heat = rank_symbols_by_news_heat(list(names.keys()), names=names, lang="zh-CN", top_n=5, date_str=date_str)
        print_fund_holding_news(holdings, heat, ranked, limit=5)

    if DIAGNOSTICS:
        print_diagnostic_summary()
    print_report_footer()


def run_stock_quote(symbol: str, date_str: str, include_news: bool = True) -> None:
    DIAGNOSTICS.clear()
    try:
        qd = get_single_stock_quote(symbol, date_str)
    except ValueError as e:
        print_single_stock_unavailable(symbol, str(e))
        print_report_footer()
        return

    if not qd:
        print_single_stock_unavailable(symbol, "当前数据源没有返回有效价格或成交数据")
        if DIAGNOSTICS:
            print_diagnostic_summary()
        print_report_footer()
        return

    print_single_stock_report(qd, date_str)

    if include_news:
        keyword = qd.name if qd.market in ("cn_market", "hk_market") and qd.name else qd.symbol
        lang = "zh-CN" if qd.market in ("cn_market", "hk_market") else "en"
        aliases = _news_aliases(qd.symbol, qd.name)
        print_futu_news(combined_news_search(keyword, size=5, lang=lang, aliases=aliases, date_str=date_str), keyword)

    if DIAGNOSTICS:
        print_diagnostic_summary()
    print_report_footer()


def run_stock_news(symbol: str, date_str: str, size: int = 8) -> None:
    DIAGNOSTICS.clear()
    size = min(size, 5)
    normalized = symbol
    market = detect_market_type(symbol)
    name = ""
    try:
        normalized, market = normalize_stock_symbol(symbol)
        qd = get_single_stock_quote(normalized, date_str)
        if qd:
            name = qd.name
            market = qd.market
    except ValueError:
        pass

    keyword = name if market in ("cn_market", "hk_market") and name else normalized
    lang = "zh-CN" if market in ("cn_market", "hk_market") else "en"
    aliases = _news_aliases(normalized, name)
    print(f"# 消息面速览：{name or normalized} ({normalized})\n")
    print(f"市场: {_market_label(market)}")
    print_stage_line(date_str)
    news = combined_news_search(keyword, size=size, lang=lang, aliases=aliases, date_str=date_str)
    print_futu_news(news, keyword, limit=size)
    print_report_footer()


def print_daily_watchlist(watchlist: dict[str, list[str]] | None, date_str: str, include_news: bool = True) -> None:
    from .reports import print_daily_watchlist as _print_daily_watchlist

    _print_daily_watchlist(sys.modules[__name__], watchlist, date_str, include_news=include_news)


def run_daily_report(
    date_str: str,
    watchlist: dict[str, list[str]] | None = None,
    include_news: bool = True,
    report_format: str = "full",
    order: str | None = None,
) -> None:
    from .reports import run_daily_report as _run_daily_report

    _run_daily_report(
        sys.modules[__name__],
        date_str,
        watchlist,
        include_news=include_news,
        report_format=report_format,
        order=order,
    )


def print_futu_news(news_data: dict, keyword: str, limit: int = 5) -> None:
    if "_error" in news_data:
        return
    data = news_data.get("data", [])
    source = news_data.get("source", "futu_news")
    source_label = "多源聚合" if "+" in str(source) else _news_source_label(str(source))
    if not data:
        print(f"## {keyword} 相关新闻（{source_label}）\n")
        print("  目前暂未获取到有效新闻信息。")
        print()
        return
    shown = min(limit, len(data))
    print(f"## {keyword} 相关新闻（{source_label}，前{shown}条）\n")
    source_counts = news_data.get("source_counts") or {}
    if source_counts:
        parts = [f"{_news_source_label(str(k))} {v}条" for k, v in source_counts.items()]
        print("  来源覆盖: " + " / ".join(parts))
        print()
    for i, item in enumerate(data[:limit], 1):
        ts = item.get("publish_time", 0)
        # 富途返回的 publish_time 是字符串，先转 int
        try:
            ts_int = int(ts)
            dt_str = datetime.fromtimestamp(ts_int).strftime("%m-%d %H:%M") if ts_int else ""
        except (TypeError, ValueError):
            dt_str = ""
        item_source = _news_source_label(str(item.get("source") or source))
        url = _normalize_news_url(item)
        print(f"{i}. [{dt_str}] {_clean_news_title(item.get('title', ''))}")
        print(f"   来源: {item_source} | 链接: {url or '暂无公开链接'}")
    print()


def print_global_sentiment(indices: list[QuoteData]) -> None:
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


def print_data_quality_report(results: list[QuoteData]) -> None:
    if os.environ.get("STOCK_ANALYSIS_DEBUG") != "1":
        return
    warnings = []
    source_notes = []
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
            if "口径" in note:
                source_notes.append(f"{name}: {note}")
            else:
                warnings.append(f"{name}: {note}")

    if avg_score < 90:
        recommendations.append("数据完整性一般，建议检查网络连接或稍后重试")
    if any("异常" in w or "缺失" in w for w in warnings):
        recommendations.append("部分数据异常，已标记 * ，仅供参考")

    if warnings or source_notes or recommendations or DIAGNOSTICS:
        print("\n" + "=" * 60)
        print("📊 数据质量与来源提示")
        print(f"  平均完整度: {avg_score:.0f}%")
        if DIAGNOSTICS:
            print("\n  数据源切换:")
            for d in DIAGNOSTICS[:6]:
                print(f"    • {d}")
            if len(DIAGNOSTICS) > 6:
                print(f"    ... 还有 {len(DIAGNOSTICS) - 6} 条")
        if source_notes:
            print(f"\n  口径说明 ({len(source_notes)}条):")
            for note in source_notes[:8]:
                print(f"    • {note}")
        if warnings:
            print(f"\n  ⚠️ 数据警告 ({len(warnings)}条):")
            for w in warnings[:8]:
                print(f"    • {w}")
            if len(warnings) > 8:
                print(f"    ... 还有 {len(warnings) - 8} 条")
        if recommendations:
            print("\n  💡 建议:")
            for rec in recommendations:
                print(f"    • {rec}")
        print("=" * 60)


def print_diagnostic_summary() -> None:
    if os.environ.get("STOCK_ANALYSIS_DEBUG") != "1":
        return
    if DIAGNOSTICS:
        print("\n" + "=" * 60)
        print("数据源切换记录")
        for d in DIAGNOSTICS:
            print(f"  • {d}")
        print("=" * 60)


def print_report_footer() -> None:
    print("\n复盘仅供参考，请结合公告、交易所披露和自身风险承受能力判断。")


def print_a_share_news(date_str: str, zt_data: dict | None = None) -> None:
    keywords = ["A股", "上证指数", "涨停"]
    zt_pool = ((zt_data or {}).get("data", {}) or {}).get("pool", []) if zt_data and "_error" not in zt_data else []
    for item in zt_pool[:2]:
        name = item.get("n")
        if name:
            keywords.append(str(name))

    seen_titles: set[str] = set()
    all_items: list[dict[str, Any]] = []
    source_counts: Counter[str] = Counter()
    for keyword in dict.fromkeys(keywords):
        news = combined_news_search(str(keyword), size=5, lang="zh-CN", aliases=[str(keyword)], date_str=date_str)
        for source, count in (news.get("source_counts") or {}).items():
            source_counts[str(source)] += int(count)
        for item in news.get("data", []):
            title = str(item.get("title", ""))
            if not title or title in seen_titles:
                continue
            seen_titles.add(title)
            all_items.append(item)

    all_items.sort(key=lambda item: _parse_news_time(item.get("publish_time")), reverse=True)
    print_futu_news(
        {
            "source": "+".join(source_counts.keys()) or "none",
            "source_counts": dict(source_counts),
            "data": _select_diverse_news(all_items, 5),
        },
        "A股市场",
        limit=5,
    )


# ------------------------------------------------------------------
# 复盘主体
# ------------------------------------------------------------------

def nearest_trade_date(dt: datetime | None = None) -> str:
    return resolve_trade_date(dt or datetime.now(), market="a")


def _session_label() -> str:
    """根据当前时间返回场次标签"""
    return session_stage_label()


def run_a_share(date_str: str, include_news: bool = True) -> None:
    DIAGNOSTICS.clear()
    display_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
    session = _session_label()
    print(f"# A 股{session}复盘（{display_date}）\n")
    print(f"数据来源: 新浪/腾讯/同花顺优先，A股专项能力按需调用公开接口 | 采集时间: {datetime.now().strftime('%H:%M:%S')}\n")
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

    northbound = fetch_northbound_flow_snapshot(date_str)
    print_northbound_flow_report(northbound)

    print_sentiment_summary(zt, dt, zb, flow)

    if include_news:
        print_a_share_news(date_str, zt)

    industry = get_board_list("industry", date_str)
    concept = get_board_list("concept", date_str)
    print_boards(industry, "行业板块涨幅")
    print_boards(concept, "概念板块涨幅")

    if DIAGNOSTICS:
        print_diagnostic_summary()

    print_report_footer()


def run_us_market(date_str: str, include_news: bool = True) -> None:
    DIAGNOSTICS.clear()
    print("# 美股市场复盘\n")
    print_stage_line(date_str)
    print(f"数据来源: 新浪财经 + 腾讯财经，资讯优先富途/新浪 | 采集时间: {datetime.now().strftime('%H:%M:%S')}\n")
    print("=" * 60 + "\n")

    us_indices_map = {
        "^GSPC": "标普 500",
        "^IXIC": "纳斯达克",
        "^DJI":  "道琼斯",
    }
    us_index_order = list(us_indices_map)
    indices = fetch_us_indices_sina(us_indices_map, date_str)
    if not _has_all_quotes(indices, us_index_order):
        indices = merge_quotes_by_symbol(indices, fetch_us_indices_tencent(us_indices_map, date_str), us_index_order)
    if not _has_all_quotes(indices, us_index_order):
        indices = merge_quotes_by_symbol(indices, fetch_indices_direct(us_indices_map, date_str, EM_US_INDEX_SECID), us_index_order)
    if indices:
        print_global_indices(indices, "美股")

    default_hot_stocks = ["AAPL", "TSLA", "NVDA", "MSFT", "AMZN", "GOOGL", "META", "BABA", "PDD", "JD"]
    hot_stocks = default_hot_stocks
    heat: dict[str, dict[str, Any]] = {}
    if include_news:
        ranked_news, heat = rank_symbols_by_news_heat(default_hot_stocks, lang="en", top_n=5, date_str=date_str)
        print("## 新闻热度 Top5\n")
        if ranked_news:
            for i, sym in enumerate(ranked_news, 1):
                print(f"{i}. {sym}（新闻热度 {heat.get(sym, {}).get('score', 0):.1f}）")
        else:
            print("  目前暂未获取到有效新闻信息。")
        print()
        hot_stocks = list(dict.fromkeys([*ranked_news, *default_hot_stocks]))[:5]
    print("## 重点个股行情\n")
    stocks = fetch_us_stocks_sina(hot_stocks, date_str)
    tencent_stocks = fetch_us_stocks_tencent(hot_stocks, date_str)
    if not _has_all_quotes(stocks, hot_stocks):
        stocks = merge_quotes_by_symbol(stocks, tencent_stocks, hot_stocks)
    stocks = enrich_quotes_by_symbol(stocks, tencent_stocks, hot_stocks)
    if not _has_all_quotes(stocks, hot_stocks):
        stocks = merge_quotes_by_symbol(stocks, fetch_us_stocks_direct(hot_stocks, date_str), hot_stocks)
    if not _has_all_quotes(stocks, hot_stocks):
        stocks = merge_quotes_by_symbol(stocks, fetch_em_stocks(hot_stocks, date_str, EM_FS["us_stock"]), hot_stocks)
    for qd in stocks:
        print_global_stock(qd)

    if include_news:
        news_symbols = [s for s in hot_stocks[:3] if heat.get(s, {}).get("score", 0) > 0]
        if news_symbols:
            print("## 相关新闻\n")
        for sym in news_symbols:
            news = heat.get(sym, {}).get("news") or combined_news_search(sym, size=5, lang="en", date_str=date_str)
            print_futu_news(news, sym)

    printed_quality = False
    if indices:
        print_global_sentiment(indices)
        print_data_quality_report(indices + stocks)
        printed_quality = True
    elif stocks:
        print_data_quality_report(stocks)
        printed_quality = True

    if DIAGNOSTICS and not printed_quality:
        print_diagnostic_summary()

    print_report_footer()


def run_hk_market(date_str: str, include_news: bool = True) -> None:
    DIAGNOSTICS.clear()
    print("# 港股市场复盘\n")
    print_stage_line(date_str)
    print(f"数据来源: 腾讯财经 + 新浪财经，资讯优先富途/新浪 | 采集时间: {datetime.now().strftime('%H:%M:%S')}\n")
    print("=" * 60 + "\n")

    hk_indices_map = {
        "^HSI": "恒生指数",
        "^HSCE": "国企指数",
        "HSTECH.HK": "恒生科技指数",
    }
    hk_index_order = list(hk_indices_map)
    indices = fetch_hk_indices_tencent(hk_indices_map, date_str)
    if not _has_all_quotes(indices, hk_index_order):
        indices = merge_quotes_by_symbol(indices, fetch_hk_indices_sina(hk_indices_map, date_str), hk_index_order)
    if not _has_all_quotes(indices, hk_index_order):
        indices = merge_quotes_by_symbol(indices, fetch_indices_direct(hk_indices_map, date_str, EM_HK_INDEX_SECID), hk_index_order)
    if indices:
        print_global_indices(indices, "港股")

    default_hot_stocks = ["0700.HK", "9988.HK", "3690.HK", "9618.HK", "1299.HK", "2318.HK", "0005.HK", "0388.HK"]
    hot_stocks = default_hot_stocks
    hk_names = {
        "0700.HK": "腾讯控股",
        "9988.HK": "阿里巴巴",
        "3690.HK": "美团",
        "9618.HK": "京东集团",
        "1299.HK": "友邦保险",
        "2318.HK": "中国平安",
        "0005.HK": "汇丰控股",
        "0388.HK": "香港交易所",
    }
    heat: dict[str, dict[str, Any]] = {}
    if include_news:
        ranked_news, heat = rank_symbols_by_news_heat(default_hot_stocks, names=hk_names, lang="zh-CN", top_n=5, date_str=date_str)
        print("## 新闻热度 Top5\n")
        if ranked_news:
            for i, sym in enumerate(ranked_news, 1):
                print(f"{i}. {hk_names.get(sym, sym)}（{sym}，新闻热度 {heat.get(sym, {}).get('score', 0):.1f}）")
        else:
            print("  目前暂未获取到有效新闻信息。")
        print()
        hot_stocks = list(dict.fromkeys([*ranked_news, *default_hot_stocks]))[:5]
    print("## 重点个股行情\n")
    stocks = fetch_hk_stocks_sina(hot_stocks, date_str)
    tencent_stocks = fetch_hk_stocks_tencent(hot_stocks, date_str)
    if not _has_all_quotes(stocks, hot_stocks):
        stocks = merge_quotes_by_symbol(stocks, tencent_stocks, hot_stocks)
    stocks = enrich_quotes_by_symbol(stocks, tencent_stocks, hot_stocks)
    if not _has_all_quotes(stocks, hot_stocks):
        stocks = merge_quotes_by_symbol(stocks, fetch_hk_stocks_direct(hot_stocks, date_str), hot_stocks)
    if not _has_all_quotes(stocks, hot_stocks):
        stocks = merge_quotes_by_symbol(stocks, fetch_em_stocks(hot_stocks, date_str, EM_FS["hk_stock"]), hot_stocks)
    for qd in stocks:
        print_global_stock(qd)

    if include_news:
        news_symbols = [s for s in hot_stocks[:3] if heat.get(s, {}).get("score", 0) > 0]
        if news_symbols:
            print("## 相关新闻\n")
        for sym in news_symbols:
            news = heat.get(sym, {}).get("news") or combined_news_search(hk_names.get(sym, sym), size=5, lang="zh-CN", date_str=date_str)
            print_futu_news(news, hk_names.get(sym, sym))

    printed_quality = False
    if indices:
        print_global_sentiment(indices)
        print_data_quality_report(indices + stocks)
        printed_quality = True
    elif stocks:
        print_data_quality_report(stocks)
        printed_quality = True

    if DIAGNOSTICS and not printed_quality:
        print_diagnostic_summary()

    print_report_footer()


def run_global_market(date_str: str) -> None:
    DIAGNOSTICS.clear()
    print("# 全球市场概览\n")
    print_stage_line(date_str)
    print(f"数据来源: 腾讯财经 + 新浪财经，多源自动切换 | 采集时间: {datetime.now().strftime('%H:%M:%S')}\n")
    print("=" * 60 + "\n")

    # 美股
    us_indices_map = {
        "^GSPC": "标普 500",
        "^IXIC": "纳斯达克",
    }
    us_indices = fetch_us_indices_sina(us_indices_map, date_str)
    us_index_order = list(us_indices_map)
    if not _has_all_quotes(us_indices, us_index_order):
        us_indices = merge_quotes_by_symbol(us_indices, fetch_us_indices_tencent(us_indices_map, date_str), us_index_order)
    if not _has_all_quotes(us_indices, us_index_order):
        us_indices = merge_quotes_by_symbol(us_indices, fetch_indices_direct(us_indices_map, date_str, EM_US_INDEX_SECID), us_index_order)
    if us_indices:
        print_global_indices(us_indices, "美股")

    # 港股
    hk_indices_map = {
        "^HSI": "恒生指数",
        "^HSCE": "国企指数",
        "HSTECH.HK": "恒生科技指数",
    }
    hk_indices = fetch_hk_indices_tencent(hk_indices_map, date_str)
    hk_index_order = list(hk_indices_map)
    if not _has_all_quotes(hk_indices, hk_index_order):
        hk_indices = merge_quotes_by_symbol(hk_indices, fetch_hk_indices_sina(hk_indices_map, date_str), hk_index_order)
    if not _has_all_quotes(hk_indices, hk_index_order):
        hk_indices = merge_quotes_by_symbol(hk_indices, fetch_indices_direct(hk_indices_map, date_str, EM_HK_INDEX_SECID), hk_index_order)
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

    if DIAGNOSTICS and not all_results:
        print_diagnostic_summary()

    print_report_footer()


# ------------------------------------------------------------------
# main
# ------------------------------------------------------------------

def main():
    global NO_CACHE
    market = "a"
    date_str = None
    stock_symbol = None
    include_news = True

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
        elif args[i] == "--no-news":
            include_news = False
            i += 1
        elif args[i] in ("--stock", "--symbol", "--fund") and i + 1 < len(args):
            stock_symbol = args[i + 1]
            if args[i] == "--fund":
                market = "fund"
            elif market not in ("news", "fund"):
                market = "stock"
            i += 2
        elif re.fullmatch(r"\d{8}", args[i]):
            date_str = args[i]
            i += 1
        else:
            i += 1

    if market not in ("a", "hk", "us", "global", "stock", "news", "fund"):
        print("错误: --market 参数必须是 a、hk、us、global、stock、news 或 fund", file=sys.stderr)
        sys.exit(1)
    if market in ("stock", "news", "fund") and not stock_symbol:
        example = "--fund 161725" if market == "fund" else "--stock 600519"
        print(f"错误: --market {market} 需要配合 {example} 使用", file=sys.stderr)
        sys.exit(1)

    # 清理过期缓存
    cache_clear_old(days=7)

    if date_str is None:
        date_str = nearest_trade_date()

    if market == "a":
        run_a_share(date_str, include_news=include_news)
    elif market == "us":
        run_us_market(date_str, include_news=include_news)
    elif market == "hk":
        run_hk_market(date_str, include_news=include_news)
    elif market == "global":
        run_global_market(date_str)
    elif market == "stock" and stock_symbol:
        run_stock_quote(stock_symbol, date_str, include_news=include_news)
    elif market == "news" and stock_symbol:
        run_stock_news(stock_symbol, date_str)
    elif market == "fund" and stock_symbol:
        run_fund_report(stock_symbol, date_str, include_news=include_news)


if __name__ == "__main__":
    main()
