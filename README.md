# stock-analysis

Hermes Agent Skill for A-share (Shanghai/Shenzhen/Beijing) market analysis.

## What It Does

- Pulls real-time and post-market data from Eastmoney free APIs
- Captures sector/concept board rankings via browser automation
- Cross-checks news and community sentiment via Futunn free search
- Provides structured post-market review templates and sentiment scoring

## Install

### Via Hermes CLI

```bash
# Clone into your Hermes skills directory
git clone https://github.com/YOUR_USERNAME/stock-analysis.git ~/.hermes/skills/research/stock-analysis
```

### Requirements

- Python 3.8+ (for `scripts/aftermarket.py`)
- `curl` (available on all major OS)
- **Optional** — Browser automation for board rankings:
  - [camofox-browser](https://github.com/daijro/camoufox) REST server, OR
  - Hermes built-in browser tools (`browser_navigate`, `browser_console`), OR
  - Playwright / Puppeteer / Selenium

### Optional: Board Ranking Setup

The script can run without browser automation (board ranking section will be skipped). To enable it:

**Option A: camofox-browser**
```bash
export CAMOFOX_URL=http://localhost:9377
export CAMOFOX_USER_ID=your_user_id
export CAMOFOX_SESSION_KEY=your_session_key
python scripts/aftermarket.py
```

**Option B: Hermes built-in browser**
Use the SKILL.md workflows directly; the skill instructions reference Hermes `browser_navigate` and `browser_console` for in-page `fetch`.

## Usage

### Quick Script

```bash
# Today's review (auto-detects trading day)
python scripts/aftermarket.py

# Specific date
python scripts/aftermarket.py 20260526
```

### As Hermes Skill

Once installed in `~/.hermes/skills/research/stock-analysis`, Hermes will auto-load `SKILL.md` context when you ask about A-share market analysis.

Example prompts:
- "今天A股怎么样" / "How's the A-share market today"
- "复盘下今天行情" / "Post-market review"
- "早盘怎么看" / "Morning session outlook"

## Structure

```
stock-analysis/
├── SKILL.md                          # Main skill instructions for Hermes Agent
├── scripts/
│   └── aftermarket.py                 # Standalone Python script for data collection
└── references/
    ├── eastmoney-api.md               # Eastmoney free API reference
    ├── futu-api.md                    # Futunn free search API reference
    └── analysis-template.md           # Structured review output template
```

## Data Sources

| Source | Type | Auth Required |
|---|---|---|
| push2.eastmoney.com | Index quotes, fund flow, ticker data | No |
| push2ex.eastmoney.com | Limit-up/down/broken-board pools | No |
| quote.eastmoney.com | Sector/concept board pages | No (browser capture) |
| ai-news-search.futunn.com | News, announcements, research, community | No |

## Notes

- All Eastmoney APIs are unofficial public endpoints; field names may change.
- Limit-up/down pool `date` parameter only returns **today's** data regardless of input.
- Some endpoints (`push2.eastmoney.com` indices/fund-flow) may return empty via bare `curl` during market hours; use browser `fetch` instead.
- Futunn search is HK/US-centric; use **Chinese company names** (not codes) for A-share queries.

## License

MIT
