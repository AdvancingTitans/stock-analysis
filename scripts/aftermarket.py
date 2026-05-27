#!/usr/bin/env python3
"""
A-share post-market data collection script
Usage: python aftermarket.py [YYYYMMDD]

Without date arg, auto-detects nearest trading day (weekend rolls back to Friday).
Outputs formatted post-market review text to stdout; redirect to file if needed.

Board ranking requires browser automation. Three options:
  1. Hermes built-in browser (recommended): set HERMES_BROWSER_URL
  2. camofox-browser REST API: set CAMOFOX_URL, CAMOFOX_USER_ID, CAMOFOX_SESSION_KEY
  3. Skip: board ranking section omitted if no browser config found.
"""

import json
import re
import sys
import os
import urllib.request
from datetime import datetime, timedelta

# ------------------------------------------------------------------
# Config
# ------------------------------------------------------------------
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

# ------------------------------------------------------------------
# Utilities
# ------------------------------------------------------------------

def fmt_price(v):
    if v is None:
        return "-"
    try:
        return f"{float(v)/100:.2f}"
    except (TypeError, ValueError):
        return str(v)


def fmt_pct(v):
    if v is None:
        return "-"
    try:
        return f"{float(v)/100:+.2f}%"
    except (TypeError, ValueError):
        return str(v)


def fmt_amount(v):
    if v is None:
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


def fmt_time(v):
    if v is None:
        return "-"
    s = str(int(v)).zfill(6)
    return f"{s[:2]}:{s[2:4]}:{s[4:6]}"


def fetch_json(url):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Referer": "https://quote.eastmoney.com/",
        },
    )
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


# ------------------------------------------------------------------
# Data Fetching
# ------------------------------------------------------------------

def get_index(date_str: str):
    url = INDEX_URL.format(secids=INDEX_SECIDS, fields=INDEX_FIELDS, ts=datetime.now().timestamp())
    data = fetch_json(url)
    if "_error" in data:
        return data
    return data.get("data", {}).get("diff", [])


def get_zt_pool(date_str: str):
    return fetch_json(ZT_URL.format(date=date_str))


def get_dt_pool(date_str: str):
    return fetch_json(DT_URL.format(date=date_str))


def get_zb_pool(date_str: str):
    return fetch_json(ZB_URL.format(date=date_str))


def get_fund_flow():
    url = FFLOW_URL.format(ts=int(datetime.now().timestamp() * 1000))
    data = fetch_json(url)
    if "_error" in data:
        return data
    d = data.get("data", {})
    klines = d.get("klines", [])
    if not klines:
        return {}
    cols = "date,主力净流入,小单净流入,中单净流入,大单净流入,超大单净流入,主力净流入占比,小单净流入占比,中单净流入占比,大单净流入占比,超大单净流入占比,收盘价,涨跌幅,总成交额".split(",")
    vals = klines[0].split(",")
    return dict(zip(cols, vals))


def _fetch_board_via_camofox(board_type: str):
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


def capture_board_list(board_type: str = "industry"):
    """
    Capture board ranking via available browser automation.
    Priority: camofox-browser REST > skip with message
    """
    if os.environ.get("CAMOFOX_URL") and os.environ.get("CAMOFOX_USER_ID"):
        return _fetch_board_via_camofox(board_type)
    return {"_skipped": "No browser automation configured. Set CAMOFOX_URL + CAMOFOX_USER_ID to enable board rankings."}


# ------------------------------------------------------------------
# Output Formatting
# ------------------------------------------------------------------

def print_index(data):
    print("## Index Performance\n")
    print(f"{'Index':<12} {'Close':>10} {'Change':>10} {'Change%':>10} {'Turnover':>12}")
    print("-" * 60)
    name_map = {
        "000001": "SSE Comp",
        "399001": "SZSE Comp",
        "399006": "ChiNext",
        "000688": "STAR50",
        "399005": "SME",
        "899050": "BSE50",
    }
    for item in data:
        code = item.get("f12", "")
        name = name_map.get(code, item.get("f14", code))
        close_p = fmt_price(item.get("f2"))
        change = fmt_price(item.get("f4"))
        pct = fmt_pct(item.get("f3"))
        amount = fmt_amount(item.get("f6"))
        print(f"{name:<12} {close_p:>10} {change:>10} {pct:>10} {amount:>12}")
    print()


def print_zt_analysis(zt_data, dt_data, zb_data):
    zt_pool = zt_data.get("data", {}).get("pool", []) if "_error" not in zt_data else []
    dt_pool = dt_data.get("data", {}).get("pool", []) if "_error" not in dt_data else []
    zb_pool = zb_data.get("data", {}).get("pool", []) if "_error" not in zb_data else []
    zt_total = zt_data.get("data", {}).get("tc", len(zt_pool)) if "_error" not in zt_data else 0
    dt_total = dt_data.get("data", {}).get("tc", len(dt_pool)) if "_error" not in dt_data else 0
    zb_total = zb_data.get("data", {}).get("tc", len(zb_pool)) if "_error" not in zb_data else 0

    print("## Limit-up/down & Consecutive-board Ladder\n")
    print(f"Limit-up: {zt_total} | Limit-down: {dt_total} | Broken-board: {zb_total}")
    if zt_total + zb_total > 0:
        zb_rate = zb_total / (zt_total + zb_total) * 100
        print(f"Broken-board rate: {zb_rate:.1f}% {'(High)' if zb_rate > 40 else ''}")
    print()

    ladders = {}
    for s in zt_pool:
        days = s.get("zttj", {}).get("days", 1)
        if days >= 2:
            ladders.setdefault(days, []).append(s)

    if ladders:
        print("Consecutive-board ladder:")
        for d in sorted(ladders.keys(), reverse=True):
            stocks = ladders[d]
            names = ", ".join([f"{s['n']}({s['c']})" for s in stocks[:5]])
            print(f"  {d}-board ({len(stocks)}): {names}")
        max_days = max(ladders.keys())
        print(f"Highest: {max_days}-board")
    else:
        print("Consecutive-board ladder: No >=2-board stocks")

    fbt_times = [s.get("fbt", 0) for s in zt_pool if s.get("fbt")]
    early = sum(1 for t in fbt_times if t <= 100000)
    mid = sum(1 for t in fbt_times if 100000 < t <= 130000)
    late = sum(1 for t in fbt_times if t > 130000)
    print(f"\nBoard time distribution: Early({early}) / Mid({mid}) / Late({late})")

    from collections import Counter
    hy_counter = Counter([s.get("hybk", "Unknown") for s in zt_pool])
    print(f"\nLimit-up sectors TOP5:")
    for hy, cnt in hy_counter.most_common(5):
        print(f"  {hy}: {cnt}")
    print()


def print_fund_flow(flow_data):
    if not flow_data or "_error" in flow_data:
        print("## Fund Flow\nData unavailable\n")
        return
    print("## Fund Flow (SSE Composite)\n")
    print(f"  Main force: {fmt_amount(flow_data.get('主力净流入'))}")
    print(f"  Super-large: {fmt_amount(flow_data.get('超大单净流入'))}")
    print(f"  Large:       {fmt_amount(flow_data.get('大单净流入'))}")
    print(f"  Medium:      {fmt_amount(flow_data.get('中单净流入'))}")
    print(f"  Small:       {fmt_amount(flow_data.get('小单净流入'))}")
    print()


def print_boards(board_data, title):
    if "_skipped" in board_data:
        print(f"## {title}\nSkipped: {board_data['_skipped']}\n")
        return
    if "_error" in board_data:
        print(f"## {title}\nError: {board_data['_error']}\n")
        return
    rows = board_data.get("rows", [])
    if not rows:
        print(f"## {title}\nNo data captured\n")
        return
    print(f"## {title} (Top 15)\n")
    print(f"{'Rank':<4} {'Sector':<12} {'Change%':>8}")
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

    print("## Sentiment Summary\n")
    if zt_total > 80 and dt_total < 10:
        print("🔥 Strong: Limit-up>80, Limit-down<10, high sentiment")
    elif zt_total > 70 and dt_total < 15:
        print("📈 Bullish: Limit-up>70, structural hot-spot market")
    elif zt_total >= 40 and dt_total < 20:
        print("😐 Neutral: Structural, mixed or divergent")
    elif dt_total > 20 or (zt_total + zb_total > 0 and zb_total / (zt_total + zb_total) > 0.4):
        print("❄️ Weak: Limit-down>20 or high broken-board rate, pullback")
    else:
        print("⚠️ Cold: Limit-up<40, low sentiment")
    print()


# ------------------------------------------------------------------
# main
# ------------------------------------------------------------------

def main():
    if len(sys.argv) > 1:
        date_str = sys.argv[1]
        if not re.fullmatch(r"\d{8}", date_str):
            print("Invalid date format, expected YYYYMMDD", file=sys.stderr)
            sys.exit(1)
    else:
        date_str = nearest_trade_date()

    display_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
    print(f"# A-Stock Post-market Review ({display_date})\n")
    print(f"Source: Eastmoney free API | Collected: {datetime.now().strftime('%H:%M:%S')}\n")
    print("=" * 60 + "\n")

    index_data = get_index(date_str)
    if isinstance(index_data, dict) and "_error" in index_data:
        print(f"Index fetch failed: {index_data['_error']}\n")
    else:
        print_index(index_data)

    zt = get_zt_pool(date_str)
    dt = get_dt_pool(date_str)
    zb = get_zb_pool(date_str)
    print_zt_analysis(zt, dt, zb)

    flow = get_fund_flow()
    print_fund_flow(flow)

    print_sentiment_summary(zt, dt, zb, flow)

    industry = capture_board_list("industry")
    concept = capture_board_list("concept")
    print_boards(industry, "Industry Board Leaders")
    print_boards(concept, "Concept Board Leaders")

    print("=" * 60)
    print("\n*Done. For board rankings, configure browser automation (see README).")


if __name__ == "__main__":
    main()
