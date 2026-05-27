# stock-analysis

Hermes Agent Skill for global stock market analysis, covering A-shares (Shanghai/Shenzhen/Beijing), Hong Kong stocks, US stocks, and Japan stocks.

## What It Does

- **A-shares**: Real-time and post-market data from Eastmoney free APIs, limit-up/down pools, sector/concept board rankings via browser automation
- **US/HK/JP stocks**: Real-time quotes from Yahoo Finance free API, news/sentiment from Futunn free search
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
├── SKILL.md                          # Main skill instructions for Hermes Agent
├── README.md                         # This file
├── LICENSE                           # MIT
├── .gitignore
├── scripts/
│   └── aftermarket.py                # Standalone Python script for data collection
└── references/
    ├── eastmoney-api.md              # Eastmoney free API reference (A-shares)
    ├── yahoo-finance-api.md          # Yahoo Finance free API reference (global)
    ├── futu-api.md                   # Futunn free search API reference
    └── analysis-template.md          # Structured review templates (A-shares + global)
```

## Data Sources

| Source | Market | Type | Auth Required |
|---|---|---|---|
| push2.eastmoney.com | A-shares | Index quotes, fund flow, ticker data | No |
| push2ex.eastmoney.com | A-shares | Limit-up/down/broken-board pools | No |
| quote.eastmoney.com | A-shares | Sector/concept board pages | No (browser capture) |
| query1.finance.yahoo.com | Global | Real-time quotes, K-lines, financials | No |
| ai-news-search.futunn.com | Global | News, announcements, research, community | No |

## Market Coverage

| Market | Indices | Tickers | News | Sentiment |
|---|---|---|---|---|
| **A-shares (沪深京)** | ✅ Eastmoney | ✅ Eastmoney | ✅ Futunn (中文名) | ✅ Futunn |
| **US stocks** | ✅ Yahoo (^GSPC, ^IXIC, ^DJI) | ✅ Yahoo | ✅ Futunn (代码) | ✅ Futunn |
| **HK stocks** | ✅ Yahoo (^HSI, ^HSCE) | ✅ Yahoo | ✅ Futunn (代码) | ✅ Futunn |
| **Japan stocks** | ✅ Yahoo | ✅ Yahoo | ⚠️ Exa only | ⚠️ Exa only |

## Notes

- **A-shares**: Eastmoney APIs are unofficial; field names may change. Limit-up/down pool `date` param only returns **today's** data.
- **Yahoo Finance**: Has rate limits (429 Too Many Requests). The script now includes **exponential backoff retry** (max 3 retries with jitter) to mitigate this. Still, avoid extremely rapid requests.
- **Data Quality**: All quotes are automatically validated — zero/negative prices are filtered, suspiciously low volume is flagged with `*`, and a data quality report is appended to the output.
- **Futunn search**: HK/US-centric. Use **Chinese company names** (not codes) for A-share queries; use **codes** for HK/US queries.
- **Time zones**: US market reviews should be done after US market close (ET 16:00). HK market reviews after HK close (HKT 16:00).

## Changelog

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
