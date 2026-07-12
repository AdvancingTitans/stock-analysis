# stock-analysis

<div align="center">
  <a href="./README.md">English</a> |
  <a href="./README.zh-CN.md">简体中文</a>
</div>

<p align="center">
  <img src="assets/social-preview.png" alt="stock-analysis social preview" width="860">
</p>

<p align="center">
  <strong>Evidence-first stock market analysis for AI agents, quant researchers, and investors who want auditable daily notes.</strong>
</p>

<p align="center">
  A/HK/US stocks · Funds · Portfolios · JSON Evidence Packs · Data-quality scoring · Multi-source fallback · Investor lenses
</p>

<p align="center">
  <a href="https://github.com/thuquant/awesome-quant"><img alt="Listed in thuquant/awesome-quant" src="https://img.shields.io/badge/listed%20in-thuquant%2Fawesome--quant-2ea44f"></a>
</p>

<p align="center">
  Listed in <a href="https://github.com/thuquant/awesome-quant">thuquant/awesome-quant</a> via merged PR
  <a href="https://github.com/thuquant/awesome-quant/pull/48">#48</a>.
</p>

`stock-analysis` turns public market data into deterministic Markdown reports and machine-readable evidence. It is built for repeatable market recaps, not black-box trading signals.

```bash
uv tool install stock-analysis

stock-analysis --market daily
stock-analysis --market stock --symbol 600519
stock-analysis --market screen --fiscal-year 2025 --universe-file official_universe.json --filter roe_weighted:gt:8% --sort roe_weighted:desc
stock-analysis --market global --format full --with-holdings --emit-evidence
```

> The output is for research only and does not constitute investment advice.

## Why It Exists

Most market "AI analysis" starts with a prompt and ends with a fluent paragraph. `stock-analysis` starts with evidence:

- Fetch public market data across A-shares, Hong Kong stocks, US stocks, funds, and portfolios.
- Normalize symbols, timestamps, source metadata, and missing fields before writing conclusions.
- Score report quality from six evidence modules instead of pretending every data source worked.
- Emit JSON files that AI agents, notebooks, cron jobs, or human reviewers can inspect and diff.

If a data source fails, the report records the gap. Missing metrics stay missing; they are not filled with zeroes or guessed from nearby signals.

## Start with the investor question

Choose a scenario rather than assembling low-level flags. Each scenario starts with deterministic evidence; an Agent may interpret it, but cannot bypass its source and completeness rules.

| If you need to… | Use | Deterministic entrypoint |
|---|---|---|
| Understand today's market | `/market-recap` | `--market daily` |
| Fact-check a ticker | `/stock-snapshot` | `--market stock --symbol` |
| Research a company with explicit gaps | `/stock-review` | `--market stock-review --symbol` |
| Recheck a reporting period | `/earnings-review` | `--market earnings --symbol` |
| Explain a sharp move without inventing causality | `/price-move` | `--market price-move --symbol` |
| Review saved holdings | `/portfolio-review` | `--market portfolio` |
| Run a reproducible annual-report filter | `/stock-screen` | `--market screen …` |
| Create or revisit a thesis | `/thesis-create`, `/thesis-review` | `--market thesis-create|thesis-review --symbol` |

`/command` is native in Claude Code. In Codex, install the generated Skills and use natural language such as “use stock-review for Tencent”; Custom Prompts appear as `/prompts:stock-review`. The same canonical catalog generates both forms, so their workflow contract does not drift.

## How the system works

```mermaid
flowchart TB
    U["Investor / Codex / Claude Code / Hermes"] --> S["Scenario entry\nmarket recap · snapshot · review · earnings · price move · portfolio · thesis"]
    S --> O["Research orchestration\nintent, scope, framework, counter-evidence"]
    O --> E["Evidence Engine\nMarket Pack M1–M6 · Company Pack C1–C8 · Fund · Portfolio"]
    E --> G["Data governance\nsymbols · trade dates · source routes · validation · missing-data suppression"]
    G --> D["Public sources\nTencent · Sina · Eastmoney · Tiantian Fund · filings/news · optional browser"]
    E --> R["Markdown report + JSON Evidence + local thesis state"]
    R --> O
```

The essential boundary is deliberate: **the scenario chooses the research question, code obtains and validates evidence, and a lens only interprets the available evidence.** Market M1–M6 is for market/portfolio state; the separate C1–C8 Company Evidence Pack prevents a market proxy from masquerading as a company fact.

```mermaid
flowchart LR
    Q["Question"] --> P["Primary public source"]
    P --> V{"Valid fields and date?"}
    V -- Yes --> N["Normalize + calculate"] --> J["Evidence JSON"] --> A["Report / Agent reasoning"]
    V -- No --> F["Validated alternate source"] --> V2{"Verified?"}
    V2 -- Yes --> N
    V2 -- No --> G["Explicit evidence gap"] --> J
```

## Agent installation

From a checkout, generate and verify the tracked entrypoints:

```bash
python3 scripts/sync_agent_entrypoints.py --check
scripts/install-agent-entrypoints.sh codex
scripts/install-agent-entrypoints.sh claude
```

The installer copies Codex Skills into `${CODEX_HOME:-~/.codex}/skills` and Claude commands into `${CLAUDE_CONFIG_DIR:-~/.claude}/commands`. It does not install data-source dependencies or modify a portfolio profile.

## Report Showcase

| Committee recap | Buffett recap | Simons recap |
|---|---|---|
| [2026-07-09 Investment committee recap](reports/20260709-投委会-行情复盘.md)<br>![Global market recap](assets/全球市场复盘_1.png) | [2026-07-09 Buffett recap](reports/20260709-巴菲特-行情复盘.md)<br>![Buffett global recap](assets/全球市场复盘（巴菲特）_1.png) | [2026-07-09 Simons recap](reports/20260709-西蒙斯-行情复盘.md)<br>![Simons global recap](assets/全球市场西蒙斯视角行情分析_1.png) |

| Buffett stock lens | Simons stock lens | Fund profile |
|---|---|---|
| [Kweichow Moutai 600519](reports/20260709-巴菲特-贵州茅台600519.md)<br>![Moutai Buffett lens](assets/贵州茅台个股分析（巴菲特）_1.png) | [Kweichow Moutai 600519](reports/20260709-西蒙斯-贵州茅台600519.md)<br>![Moutai Simons lens](assets/贵州茅台个股分析（西蒙斯）_1.png) | [Semiconductor ETF 512480](reports/20260709-512480-半导体ETF基金分析.md)<br>![Semiconductor fund analysis](assets/半导体基金分析_1.png) |

Browse the [report directory](reports/) for the six 2026-07-09 Markdown reports, screenshots, social-share assets, and automation examples.

## What You Get

| Capability | What it means |
|---|---|
| Evidence Pack JSON | `evidence_YYYYMMDD.json` plus M1-M6 module files for audit, automation, and agent handoff. |
| A/HK/US/fund coverage | One CLI for broad market snapshots, single stocks, funds, and portfolio exposure. |
| Data-source routing | Tencent/Sina first where stable, Eastmoney for unique China-market data, browser fallback only when needed. |
| Quality scoring | Reports carry a 100-point evidence quality score and identify missing modules. |
| Investor lenses | Built-in Buffett, Munger, Graham, Simons, Dalio, Duan Yongping, Zhang Kun, and other structured lenses. |
| Portfolio memory | Optional local holdings profile with benchmark comparison, concentration risk, and FX normalization. |
| Deterministic A-share screening | Strict annual-report conditions with official-Universe gating, per-stock PASS/FAIL/UNKNOWN decisions, and one auditable Evidence JSON. |
| Guarded market-data evidence | Northbound flow requires a validated full-day sequence; fund profiles expose per-fund field coverage; listed A-shares/ETFs get 5d/20d/60d price-volume metrics and split-normalized premium/discount series when public samples are complete. |

## Quickstart

Install from PyPI:

```bash
uv tool install stock-analysis
stock-analysis --market daily
```

Run from a local checkout:

```bash
git clone https://github.com/AdvancingTitans/stock-analysis.git
cd stock-analysis
uv run stock-analysis --market daily
```

Common commands:

```bash
# Auto-select summary/key-points/full by Beijing market session
stock-analysis --market daily

# Full global recap with auditable JSON evidence
stock-analysis --market global --format full --emit-evidence

# Deterministic single-stock snapshot, no LLM required
stock-analysis --market stock --symbol 600519

# Company Evidence Pack: C1 business through C8 catalyst/thesis, with explicit gaps
stock-analysis --market stock-review --symbol 600519 --emit-evidence

# Financial facts only; it will not infer missing original-report data
stock-analysis --market earnings --symbol 600519 --emit-evidence

# Price, volume and public-event samples without claiming a causal explanation
stock-analysis --market price-move --symbol 600519 --emit-evidence

# Create and later compare a local structured thesis snapshot
stock-analysis --market thesis-create --symbol 600519
stock-analysis --market thesis-review --symbol 600519

# Deterministic fund snapshot with public profile and holdings data
stock-analysis --market fund --symbol 161725

# Deterministic A-share annual-report screen; requires a complete official Security Master snapshot
stock-analysis --market screen --fiscal-year 2025 --universe-file official_universe.json \
  --filter roe_weighted:gt:8% --filter revenue_growth_yoy:gt:8% \
  --sort roe_weighted:desc --limit 20 --emit-evidence

# Diagnose Tencent, Sina, Eastmoney, browser, and optional mootdx routes
stock-analysis --market diagnose
```

## Evidence Modules

### Company Evidence Pack (C1–C8)

Company research has a different contract from daily market recap. `company_evidence_<symbol>_<date>.json` groups verified facts and gaps into business quality, financial quality, growth, moat evidence, management/capital allocation, valuation, risk/counter-evidence, and catalysts/thesis tracking. The current structured financial adapter is A-share focused; HK/US primary-filing fields intentionally remain gaps until a verified adapter exists.

Every financial fact includes period, currency, accounting scope, source type, source, and confidence. The metric registry at [`config/metric_registry.json`](config/metric_registry.json) declares how a metric is validated and which framework can use it. It never produces a composite “buy score.”

When `--emit-evidence` is enabled, the CLI writes:

```text
evidence_YYYYMMDD.json
m1_YYYYMMDD.json
m2_YYYYMMDD.json
m3_YYYYMMDD.json
m4_YYYYMMDD.json
m5_YYYYMMDD.json
m6_YYYYMMDD.json
```

The six-module score is designed for report trust, not performance marketing:

| Module | Focus | Weight |
|---|---:|---:|
| M1 | Cross-market index state, breadth, liquidity, benchmark context | 20 |
| M2 | Sector and concept rotation | 20 |
| M3 | Short-term sentiment and limit-up structure | 20 |
| M4 | Risk, failed breakouts, downside pressure | 15 |
| M5 | Portfolio exposure, style, concentration, holdings pulse | 15 |
| M6 | Resilient directions and next-session watchlist | 10 |

Full reports keep the same structure even when quality is low, but missing modules are called out naturally in the relevant section.

For current-day A-share reports, whole-market breadth is counted only after every Eastmoney `clist` page reconciles; a Sina `hs_a` fallback must paginate to EOF with unique valid codes. Historical reports keep strict breadth unavailable rather than relabeling industry-board components as all-market breadth. Tencent daily K lines add 5d/20d/60d returns, volume z-score, and ATR only when the sample is complete.

## Built For Agents

`stock-analysis` is intentionally agent-friendly:

- Deterministic CLI first; LLM layers can consume evidence later.
- Markdown for human review, JSON for machine workflows.
- Explicit source events and fallback reasons.
- Stable command surface for cron jobs, notebooks, Hermes, Codex, Claude Code, and other tool-calling agents.

Example agent prompt:

```text
Run stock-analysis --market global --format full --emit-evidence.
Use the Markdown report for the user-facing recap.
Use evidence_YYYYMMDD.json to verify every strong conclusion before summarizing.
If a module is missing, say which evidence was unavailable instead of guessing.
```

See [examples/agent.md](examples/agent.md) for a daily agent workflow and [examples/github-actions-daily-recap.yml](examples/github-actions-daily-recap.yml) for a scheduled GitHub Actions recap that uploads the report plus Evidence Pack.

## What It Is Not

- Not a trading bot.
- Not a broker integration.
- Not a promise of complete market data.
- Not a replacement for professional financial advice.
- Not a black-box LLM report generator.

## Data Source Strategy

| Scenario | Primary route | Fallback route |
|---|---|---|
| A-share quotes and valuation | Tencent → Sina | Eastmoney `stock/get` |
| A-share indices | Tencent → Sina | Eastmoney index endpoints |
| Board rankings | Eastmoney `clist` | Tonghuashun public pages → browser fallback |
| HK quotes | Tencent/Sina | Eastmoney `stock/get` |
| US quotes | Sina/Tencent | Eastmoney `searchapi` → `stock/get` |
| Funds | Eastmoney/Tiantian fund pages | Sina fund fallback |
| Deep tick/order-book data | Optional `mootdx` | Basic Tencent/Sina quotes |

Yahoo is intentionally not part of the recommended default path.

## Investor Lenses

The lens engine can render the same evidence through different investment frameworks. Supported lenses include:

`buffett`, `munger`, `graham`, `klarman`, `lynch`, `o_neil`, `wood`, `dalio`, `soros`, `livermore`, `minervini`, `simons`, `duan_yongping`, `zhang_kun`, and `feng_liu`.

Lenses change evidence priority and narrative structure. They do not override data quality rules or invent missing numbers.

### Built-in Lens and Committee Boundaries

Current CLI version: `4.5.0`.

`LensEngine` is the report orchestration layer. The default mode is `committee`, which combines M1-M6 evidence into a deeper cross-module analysis. Natural-language callers can ask for requests such as "analyze Kweichow Moutai in Buffett mode" or "run an adversarial debate between Buffett and Munger on Tencent." If `committee` mode fails, the engine falls back to `single` mode and preserves the fallback reason in metadata.

Committee reports use a fixed spine: executive summary → market index overview → portfolio analysis when complete holdings are available → six-module deep recap → integrated portfolio guidance and risk notes. The closing guidance should cover the current state, benchmark outperformance or underperformance, conditional position actions, the next-session watchlist, and key risks. Evidence appendices stay outside the morning, intraday, midday, and after-close narrative body. If any M1-M6 module is missing, the relevant section must say that the evidence is unavailable.

`--market stock --symbol <code>` and `--market fund --symbol <code>` are deterministic evidence views. They do not require users to install any external quote CLI. Browser routes are fallback-only paths for repeated API failures or page-only data. Engineering details belong in evidence and diagnose output, not in the user-facing report body.

Northbound flow is shown only after a current-day full-session validation (coverage through 14:50, sufficient minute samples, and a sane opening baseline). Historical or incomplete streams remain unavailable. Fund-profile completeness is evaluated for every fund and every field, so an ETF with no published fee values cannot be compared as if fees were known. Board rankings carry their source taxonomy, and classifications from different providers are not comparable without normalization.

Listed-fund premium/discount uses Tencent forward-adjusted daily closes against paginated official NAV. Public share-split events are normalized before the two series are compared; any unparseable corporate action suppresses the series. A fund-page annualized tracking-error value is labeled as disclosed metadata, never as a locally recomputed daily tracking error.

Fund profiles use Tiantian Fund's public `pingzhongdata` page to supplement long-term performance, front-end fees, fund size, and fund manager context. This path does not require login or an API key. Fund snapshots should show long-term performance, front-end fees, fund manager information, and any disclosed gaps.

Investment memory defaults to `~/.stock_analysis/profile.json` and can be overridden with `STOCK_ANALYSIS_PROFILE`. A complete holding must include the symbol, buy date, and either share quantity or purchase amount. If newly supplied user information conflicts with saved investment memory, confirm that the new information is complete, then prefer the user's latest input and overwrite the saved memory.

When a user explicitly asks for a specific investor style, the whole report must be written from that lens. Do not merely append an expert comment at the end. Single-expert and multi-expert reports have different structures, but neither should impersonate an investor or fabricate expert quotes.

## Contributing

Good first contributions:

- Add or harden a public data-source adapter.
- Improve a report template or investor lens.
- Add examples for a new region, symbol type, or agent workflow.
- Report a source failure with `--market diagnose` output.
- Submit this project to a high-fit Awesome List or agent tool directory.

Start with [CONTRIBUTING.md](CONTRIBUTING.md) and [ROADMAP.md](ROADMAP.md).

## Awesome List Blurb

Use this one-liner when submitting the project to curated lists:

> [stock-analysis](https://github.com/AdvancingTitans/stock-analysis) - Evidence-driven market recap CLI for AI agents and quant researchers, supporting A/HK/US stocks, funds, portfolios, auditable JSON Evidence Packs, data-quality scoring, investor lenses, and multi-source fallback routing.

High-fit targets include `awesome-quant-ai`, `awesome-ai-in-finance`, `awesome-quant`, and `awesome-systematic-trading`.

## Development

```bash
uv sync
uv run --with pytest pytest -q
uv run --with ruff ruff check
```

## License

MIT

This project is for research only and does not constitute investment advice. Markets involve risk.
