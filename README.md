# stock-analysis

Hermes Agent Skill for global stock market analysis, covering A-shares (Shanghai/Shenzhen/Beijing), Hong Kong stocks, US stocks, and Japan stocks.

## What It Does

- **A-shares**: Real-time and post-market data from Eastmoney free APIs, limit-up/down pools, sector/concept board rankings via browser automation
- **US/HK stocks**: Real-time quotes from **Eastmoney clist free API** (no login, no rate limit), news/sentiment from Futunn free search
- **Cross-market sentiment**: Structured review templates, sector rotation analysis, community sentiment scoring
- **Browser automation**: camofox / Hermes built-in browser / Playwright for page capture when APIs fail

## Install

### Via Hermes CLI

```bash
git clone https://github.com/AdvancingTitans/stock-analysis.git ~/.hermes/skills/research/stock-analysis
```

### Requirements

- Python 3.8+ (for `scripts/aftermarket.py`)
- `curl` (available on all major OS)
- **Optional** — Browser automation for board rankings and page capture:
  - [camofox-browser](https://github.com/daijro/camoufox) REST server, OR
  - Hermes built-in browser tools (`browser_navigate`, `browser_console`), OR
  - Playwright / Puppeteer / Selenium

## Usage

### Quick Script

```bash
# A-shares review (auto-detects trading day)
python scripts/aftermarket.py --market a

# US market review
python scripts/aftermarket.py --market us

# HK market review
python scripts/aftermarket.py --market hk

# Global market overview (US + HK + A-share indices)
python scripts/aftermarket.py --market global

# Specific date (A-shares only)
python scripts/aftermarket.py --market a 20260526
```

### As Hermes Skill

Once installed in `~/.hermes/skills/research/stock-analysis`, Hermes will auto-load `SKILL.md` context when you ask about stock market analysis.

Example prompts:
- "今天A股怎么样" / "How's the A-share market today"
- "复盘下今日行情" / "Post-market review"
- "美股今天怎么样" / "How's the US market"
- "港股腾讯怎么样" / "How's Tencent (0700.HK)"
- "早盘怎么看" / "Morning session outlook"

## Structure

```
stock-analysis/
├── skills/
│   └── stock-analysis/
│       ├── SKILL.md                  # Main skill instructions for Hermes Agent
│       ├── scripts/
│       │   └── aftermarket.py        # Standalone Python script for data collection
│       └── references/
│           ├── eastmoney-api.md      # Eastmoney free API reference (A-shares + US/HK)
│           ├── yahoo-finance-api.md  # Yahoo Finance API reference (legacy/deprecated)
│           ├── futu-api.md           # Futunn free search API reference
│           └── analysis-template.md  # Structured review templates (A-shares + global)
├── README.md                         # This file
├── LICENSE                           # MIT
└── .gitignore
```

### Install via Hermes CLI

```bash
hermes skills install --repo AdvancingTitans/stock-analysis --path skills/stock-analysis
```

## Data Sources

| Source | Market | Type | Auth Required | Advantages |
|---|---|---|---|---|
| push2.eastmoney.com | **A-shares** | Index quotes, fund flow, ticker data | **No** | 免登录、不限流、价格实时 |
| push2ex.eastmoney.com | **A-shares** | Limit-up/down/broken-board pools | **No** | 同上 |
| push2.eastmoney.com/api/qt/clist/get | **US/HK** | Index + stock real-time quotes | **No** | **免登录、不限流、一次请求批量拉取**，替代 Yahoo Finance |
| quote.eastmoney.com | A-shares | Sector/concept board pages | No (browser capture) |  |
| query1.finance.yahoo.com | Global | Real-time quotes, K-lines, financials | No |  legacy only; 美股道指/VIX 东财暂无时备用 |
| ai-news-search.futunn.com | Global | News, announcements, research, community | No |  |

### Why Eastmoney clist replaces Yahoo Finance

| Aspect | Yahoo Finance v8 | Eastmoney clist |
|---|---|---|
| **Login / API Key** | Not required | **Not required** |
| **Rate limit** | Strict (429 after ~5 req) | **None observed** |
| **Batch fetch** | Per-symbol (slow) | **One request, up to 500 items** |
| **US indices** | ✅ SPX, NDX, DJI, VIX | ✅ SPX, NDX; ❌ DJI, VIX (暂无) |
| **US stocks** | ✅ All | ✅ Major ones (AAPL, NVDA, TSLA, etc.) |
| **HK indices** | ✅ HSI, HSCE, HSTECH | ✅ HSI, HSCE, HSTECH |
| **HK stocks** | ✅ All | ✅ Major ones (0700, 9988, etc.) |

> **Note**: DJI and VIX are not available on Eastmoney yet; fallback to Yahoo Finance or other sources if needed.

## Market Coverage

| Market | Indices | Tickers | News | Sentiment |
|---|---|---|---|---|
| **A-shares (沪深京)** | ✅ Eastmoney | ✅ Eastmoney | ✅ Futunn (中文名) | ✅ Futunn |
| **US stocks** | ✅ Eastmoney clist (SPX, NDX) | ✅ Eastmoney clist | ✅ Futunn (代码) | ✅ Futunn |
| **HK stocks** | ✅ Eastmoney clist (HSI, HSCE, HSTECH) | ✅ Eastmoney clist | ✅ Futunn (代码) | ✅ Futunn |
| **Japan stocks** | ⚠️ Exa only | ⚠️ Exa only | ⚠️ Exa only | ⚠️ Exa only |

## Notes

- **A-shares**: Eastmoney APIs are unofficial; field names may change. Limit-up/down pool `date` param only returns **today's** data.
- **Eastmoney clist**: Uses `fltt=2`; price fields are returned ×100 as integers and are divided by 100 in the script.
- **Data Quality**: All quotes return a unified `QuoteData` structure. Zero/negative prices are filtered, index volume=0 is downgraded to warning, suspiciously low volume is flagged with `*`, and a diagnostic summary + quality report is appended to the output.
- **Futunn search**: HK/US-centric. Use **Chinese company names** (not codes) for A-share queries; use **codes** for HK/US queries.
- **Time zones**: US market reviews should be done after US market close (ET 16:00). HK market reviews after HK close (HKT 16:00).

## Changelog

### v3.1.0
- **Replaced Yahoo Finance v8 chart with Eastmoney clist API** for US/HK market data
  - Yahoo's 429 rate limiting is no longer an issue
  - Batch fetch in one request instead of per-symbol polling
  - No login, no API key, no cookie required
- Removed 3-second request interval for US/HK (Eastmoney is rate-limit-free); A-share interval unchanged
- Added `_normalize_diff` helper to handle Eastmoney's inconsistent `diff` format (array vs object)
- Added `_em_clist_price` helper to properly scale `fltt=2` price fields
- Added `EM_CODE_MAP` for Yahoo symbol → Eastmoney f12 mapping
- Removed DJI and VIX from default US indices (not available on Eastmoney yet)
- Updated all `source` strings from `yahoo_chart` to `eastmoney_clist`
- Bumped script User-Agent to `stock-analysis/3.1.0`

### v3.0.0
- **Breaking**: Renamed skill from `a-stock-market` to `stock-analysis`
- **Breaking**: Repository restructured to `skills/stock-analysis/` subdir for proper Hermes CLI install
- **Breaking**: Yahoo v6/finance/quote batch API removed; all quotes now use v8 chart per-symbol with caching
- Added three-tier fetch strategy: cache → stable API → browser fallback (camofox)
- Added local cache layer at `~/.cache/stock-analysis/` to avoid duplicate requests
- Fixed A-share index price formatting — Eastmoney `fltt=2` returns normal prices, no longer divide by 100
- Fixed Futunn `publish_time` string crash (now casts to int before datetime)
- Fixed `^HSTECH` 404 — now uses `HSTECH.HK`
- Changed default request interval from 0.5s to 3s; only retry on 429/5xx/timeout (not 404)
- Added diagnostic summary output when APIs fail (no more silent missing blocks)
- Unified all data sources to `QuoteData` structure with completeness scoring
- Added automated data quality validation with quality report at end of output

### v2.1.0
- Added `--market global` for cross-market overview
- Added exponential backoff retry for all API requests
- Added automatic data validation and cleaning (volume anomaly detection, price filtering)
- Added data completeness scoring and quality report
- Added market type auto-detection
- Improved error handling — missing data is silently skipped without cluttering output

### v2.0.0
- Added global market support (US/HK/JP via Yahoo Finance + Futunn)
- Removed hardcoded proxy settings for broader compatibility

## License

MIT
