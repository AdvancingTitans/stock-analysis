---
name: stock-analysis
description: "A-share market post-market & intraday analysis: Eastmoney free API, Futu free news/sentiment, browser-based board ranking capture, cross-validation."
version: 1.2.0
author: yjw
tags: [a-shares, stock-market, eastmoney, futu, sentiment, china-finance]
platforms: [linux, macos, windows]
---

# A-Stock Market Analysis

A share (Shanghai/Shenzhen/Beijing) market data acquisition and sentiment analysis workflow, bypassing common anti-bot traps. Integrates Futunn free news search capabilities for A-share tickers.

Detailed API quick reference in `references/eastmoney-api.md`, analysis template in `references/analysis-template.md`, ready-to-use script in `scripts/aftermarket.py`.

## When to Use

- User asks "how's the A-share market today", "post-market review", "market sentiment"
- User asks "morning session outlook", "intraday status", "current market mood"
- Need limit-up / limit-down counts, consecutive-board ladders, sector leaders, north-bound flows
- Need sentiment temperature for a sector / concept
- Need latest news, announcements, research reports for an A-share ticker
- Need community / forum sentiment for an A-share ticker
- Any real-time or post-market query about SSE/SZSE/ChiNext/STAR Market/BSE

## Data Source Priority

1. **Eastmoney Free API** (`push2.eastmoney.com` + `push2ex.eastmoney.com`) — indices, limit-up/down pools, ticker quotes. **Primary for A-share base data**.
   - `push2ex.eastmoney.com` (ZT/DTPool) is stable via `curl`.
   - `push2.eastmoney.com` (indices, fund flow, up/down stats) often returns empty via bare `curl` during market hours; use **browser `fetch`** (Hermes built-in browser or Playwright).
2. **Browser page capture** (`quote.eastmoney.com/center/gridlist.html`) — sector/concept board rankings. **Primary for boards** when API returns empty.
3. **Futunn Free Search Skills** (`ai-news-search.futunn.com`) — news/announcement/research search, ticker digest, community sentiment. **Primary for news cross-check**, no OpenD required.
4. **Exa search for daily review articles** (**must** include `startPublishedDate:"YYYY-MM-DD"`) — cross-check media sentiment (Sina/NetEase/Securities Times). Without date filter hits historical same-date articles.
5. **Weibo hot search** — check if A-shares are trending. **No finance hot search itself is a "calm sentiment" signal**.

## Mandatory Data Pull Rules

**Any analysis (morning/noon/intraday/post-market) must pull data first. Blind qualitative judgment is prohibited.** If an endpoint fails due to anti-bot / time restrictions, explicitly mark "data missing" in output instead of skipping.

**Default mandatory data checklist (minimum dataset):**

| Mandatory | Endpoint/Method | Scenario | Note |
|---|---|---|---|
| 6 major indices real-time/close | `push2.eastmoney.com` ulist | All | Browser fetch during market; curl may work post-market |
| Limit-up pool | `push2ex.eastmoney.com` ZTPool | All | curl stable; date must be today |
| Limit-down pool | `push2ex.eastmoney.com` DTPool | All | Same |
| Broken-board pool | `push2ex.eastmoney.com` ZBPool | All | Same |
| Main fund flow | `push2.eastmoney.com` fflow | All | Browser fetch during market |
| Industry board ranking | Browser capture `gridlist.html#industry_board` | All | Bare curl blocked |
| Concept board ranking | Browser capture `gridlist.html#concept_board` | Post-market review | Check consecutive-board concept relay |
| Market-wide up/down counts | `push2.eastmoney.com` clist | Morning/Intraday | Browser fetch during market |
| Daily news | Futunn `news_search` | Optional | Mandatory when user mentions ticker/sector |
| Daily review articles | Exa `web_search_exa` | Post-market review | Must include `startPublishedDate` |

**Morning session special handling:**
- No "closing price" or "daily turnover"; use current price + cumulative volume.
- Consecutive-board ladder still forming; prefix conclusion with "Morning Session Snapshot".
- Broken-board rate calculated as current broken / (current limit-up + current broken), not final.

## Key API Quick Reference (see `references/eastmoney-api.md` for full details)

```bash
# Indices (SSE/SZSE/ChiNext/STAR/SME/BSE)
curl -s "https://push2.eastmoney.com/api/qt/ulist.np/get?fltt=2&secids=1.000001,0.399001,0.399006,1.000688,0.399005,0.899050&fields=f2,f3,f4,f5,f6,f12,f14,f15,f16,f17,f18"

# Limit-up pool (includes consecutive days, first board time, broken count, sector)
curl -s "https://push2ex.eastmoney.com/getTopicZTPool?ut=7eea3edcaed734bea9cbfc24409ed989&dpt=wz.ztzt&Pageindex=0&pagesize=200&sort=fbt:asc&date=YYYYMMDD"

# Limit-down / broken-board pools
curl -s "https://push2ex.eastmoney.com/getTopicDTPool?...&date=YYYYMMDD"
curl -s "https://push2ex.eastmoney.com/getTopicZBPool?...&date=YYYYMMDD"

# Fund flow
curl -s "https://push2.eastmoney.com/api/qt/stock/fflow/kline/get?secid=1.000001&fields1=f1,f2,f3,f7&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64,f65&klt=101&lmt=1"
```

## Futunn Free Search Skills

Three free info capabilities from Futunn, no OpenD, no API Key, direct `curl`.

**Recommend using Chinese company full name as `keyword`** (e.g. "比亚迪" not "002594"), because Futunn is HK/US-centric and codes may hit同名 tickers.

| Capability | Endpoint | Quick Test |
|---|---|---|
| News/Announcement/Research | `GET https://ai-news-search.futunn.com/news_search` | `keyword=比亚迪&size=10&news_type=1&lang=zh-CN&sort_type=2` |
| Community sentiment | `GET https://ai-news-search.futunn.com/stock_feed` | `keyword=比亚迪&size=30` |
| Ticker digest | Structured analysis after calling `news_search` | Output conclusion+signal+evidence |

Full params, return structure, sentiment classification rules in `references/futu-api.md`.

## Board Rankings: Browser Capture Required

Eastmoney board API (`m:90+t:2` industry / `m:90+t:3` concept) often returns empty. **Use browser automation directly**:

### Option A: Hermes Built-in Browser (Recommended)
```python
# browser_navigate to the URL, then browser_console fetch
(async () => {
  const url = 'https://push2.eastmoney.com/api/qt/clist/get?pn=1&pz=20&fid=f3&fs=m:90+t:2&fields=f12,f14,f2,f3,f4,f5,f6&_=' + Date.now();
  const r = await fetch(url, { referrer: 'https://quote.eastmoney.com/' });
  return await r.json();
})()
```

### Option B: Playwright / Puppeteer / Camoufox
```python
# Navigate to quote.eastmoney.com/center/gridlist.html#industry_board
# Wait for networkidle, then capture page content or execute fetch in page context
```

### Option C: camofox-browser REST API (if available)
```python
# POST /tabs {"userId":"x","sessionKey":"s","url":"https://quote.eastmoney.com/center/gridlist.html#industry_board"}
# GET /tabs/<id>/snapshot?userId=x&format=markdown
# Extract table rows from markdown
```

Switch to concept board: navigate to `#concept_board` anchor + wait networkidle + sleep 2s before snapshot.

Full script: `scripts/aftermarket.py`.

## Sentiment Thermometer (6 Indicators)

| Indicator | Source | Interpretation |
|---|---|---|
| Limit-up / Limit-down count | ZTPool / DTPool `tc` | Limit-up >70 strong, <40 weak; Limit-down >15 caution |
| Broken-board rate | Broken / (Limit-up + Broken) | >40% poor money effect |
| Highest consecutive board | ZTPool.pool[].zttj.days | ≥10 boards = "demon stock anchor", sentiment alive |
| Board time distribution | ZTPool.pool[].fbt (HHMMSS int) | Morning cluster = resonance; even = support |
| Limit-up sector concentration | Count ZTPool.pool[].hybk | Concentrated = clear leader; scattered = pure speculation |
| "Yesterday consecutive/limit-up/first-board" concept rank | Concept board | Top 10 = strong relay |

**Futunn community sentiment as 7th auxiliary indicator**: Extreme community bull/bear ratio (>75%) often signals short-term reversal.

## Common Sentiment Combinations

- Indices flat + limit-up 40-60 + high board exists → **Structural hot-spot market** (retail-driven)
- Indices slightly down + limit-down >20 + no concept relay → **Pullback day**
- Indices slightly up + limit-up >80 + sector concentrated → **Leader sector launching**
- Indices big drop + limit-down >50 → **Panic selling**
- Indices slightly down + limit-up 50-70 + balanced community sentiment → **Divergent adjustment** (leader switching)

## Critical Pitfalls

### 🪥 Pitfall 1: Exa search hits historical same-date articles
Without `startPublishedDate`, Exa returns prior-year same-month-day articles. A-share reviews on 5/26 look identical every year.
**Fix**: Force `"startPublishedDate":"YYYY-MM-DD"`. Verify machine date with `curl -sI https://www.baidu.com | grep Date`.

### 🪥 Pitfall 2: Jina Reader times out on China finance sites
`r.jina.ai/https://finance.sina.com.cn/...` often 15s timeout. Eastmoney, 10jqka, Xueqiu have anti-bot.
**Fix**: Use Eastmoney API or browser capture; don't rely on Jina.

### 🪥 Pitfall 3: Eastmoney board API returns empty
`push2.eastmoney.com/api/qt/clist/get?fs=m:90+t:2` returns empty even with UA/Referer.
**Fix**: Use browser capture on `gridlist.html` page.

### 🪥 Pitfall 4: Guba anti-bot is strictest
`guba.eastmoney.com` often returns 0 bytes even with browser automation.
**Fix**: Use Futunn community sentiment + Exa daily review articles.

### 🪥 Pitfall 5: `push2.eastmoney.com` indices/fund-flow empty via bare curl during market hours
Indices (`ulist.np/get`), fund flow (`fflow/kline/get`), market-wide stats (`clist/get`) often return empty via `curl` during morning/intraday. `push2ex.eastmoney.com` (ZT/DTPool) curl is stable.
**Fix**: Use **browser `fetch`** (Hermes `browser_console`, Playwright page.evaluate, or camofox evaluate) during market hours.

### 🪥 Pitfall 6: Futunn news search is code-format sensitive for A-shares
Futunn is HK/US-centric. Using A-share code (e.g. 002594) may hit HK/US同名 tickers.
**Fix**: Use Chinese company name; resolve name via Eastmoney API first if precise targeting needed.

### 🪥 Pitfall 7: Futunn `stock_feed` community data unstable
Small-cap A-shares may have minimal or empty community discussion.
**Fix**: Use only as auxiliary reference; don't force sentiment output when empty.

### 🪥 Pitfall 8: Eastmoney limit-up/down pool `date` param is non-functional for history
`getTopicZTPool`/`DTPool`/`ZBPool` `date` param always returns **today's** data regardless of input. Tested: calling `date=20260526` on 2026-05-27 still returns 5/27 data.
**Fix**: Only usable same-day post-market; historical ladders need manual logging or other sources.

### 🪥 Pitfall 9: Board ranking API requires browser context
`push2.eastmoney.com/api/qt/clist/get?fs=m:90+t:2` works in browser `fetch()` but fails via bare `curl` (even with UA/Referer) due to cookie/TLS fingerprint/render-chain validation.
**Fix**: Always use browser automation for board rankings.

### 🪥 Pitfall 10: Futunn `stock_feed` returns generalized content for A-share Chinese names
Using Chinese name (e.g. "比亚迪") on `stock_feed` often returns HK/US同名 ticker or related content; A-share precision is low.
**Fix**: Use `news_search` (news_type 1/2/3) for news cross-check, or resolve ticker code via Eastmoney first.

### 🪥 Pitfall 11: Morning vs Post-market data needs differ
Morning analysis has no "closing price" or "daily turnover"; focus on real-time index moves, early board time distribution (`fbt`), broken-board rate, sector concentration, real-time fund outflow. Consecutive-board ladder is still dynamic.
**Fix**: Use simplified 5-step morning workflow below, not the full 8-step post-market template.

## Intraday / Morning Snapshot Workflow (5 Steps)

1. **Browser `fetch` indices** → SSE/SZSE/ChiNext/STAR/BSE real-time change + volume
2. **`curl` ZTPool + DTPool + ZBPool** → Stats: limit-up/down/broken counts, ladder, early board times, sector concentration
3. **Browser `fetch` fund flow + market-wide up/down** → Main outflow + up/down ratio
4. **Futunn `news_search` hot news** → Quick news context (optional)
5. **Apply 6 indicators for morning sentiment** (prefix "Morning Session Snapshot")

## Standard Post-market Review Workflow (8 Steps)

1. **`curl` Eastmoney indices** → SSE/SZSE/ChiNext/STAR/BSE close + fund flow
2. **`curl` ZTPool/DTPool/ZBPool (date=today)** → Calculate limit-up/down/broken/highest board
3. **Browser capture industry board ranking** → Identify leader sector
4. **Browser capture concept board ranking** → Check if "yesterday consecutive/limit-up" in top 10 (relay strength)
5. **Futunn `news_search` hot ticker news** → Quick news context (optional, when user mentions ticker)
6. **Futunn `stock_feed` community sentiment** → Market temperature (optional)
7. **Exa search `daily review capital main force` + startPublishedDate** → Mainstream media tone
8. **Apply "6 indicators + 4 combinations" for comprehensive sentiment**

Ready-to-run script: `scripts/aftermarket.py YYYYMMDD`

## Limitations

- A-share data (Eastmoney) covers Shanghai/Shenzhen/Beijing only. HK/US/Japan stocks need Futunn OpenAPI (requires OpenD).
- Futunn free Search Skills mainly cover HK/US ticker news; A-share coverage varies by ticker. Chinese name as keyword works best.
- Eastmoney API is unofficial; field names (`f2/f3/...`) may change. Use `curl ... | jq` to inspect raw structure when fields missing.
- `push2.eastmoney.com` endpoints (indices, fund flow, up/down) may return empty via bare `curl` during market hours; use browser `fetch`. `push2ex.eastmoney.com` limit pools are curl-stable.
- Limit pool `date` param **only works for today**; historical queries return today's data. Post-market limit analysis must be done same day.
- Real trading days only; weekends/holidays return previous trading day or empty.
- Futunn community sentiment reflects platform users only, not entire market.
