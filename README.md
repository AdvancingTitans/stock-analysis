# stock-analysis

<div align="center">
  <a href="./README.md">English</a> |
  <a href="./README.zh-CN.md">简体中文</a>
</div>

<p align="center">
  <img src="assets/social-preview.png" alt="stock-analysis social preview" width="860">
</p>

<p align="center">
  <strong>Turn one investment question into an institutional-style report with evidence, debate, and decision conditions.</strong>
</p>

<p align="center">
  A/HK/US stocks · ETFs / funds · Portfolios · Dynamic committee · Primary disclosures · Multi-source validation
</p>

<p align="center">
  <a href="https://github.com/thuquant/awesome-quant"><img alt="Listed in thuquant/awesome-quant" src="https://img.shields.io/badge/listed%20in-thuquant%2Fawesome--quant-2ea44f"></a>
  <a href="https://github.com/leoncuhk/awesome-quant-ai"><img alt="Listed in leoncuhk/awesome-quant-ai" src="https://img.shields.io/badge/listed%20in-leoncuhk%2Fawesome--quant--ai-2ea44f"></a>
  <a href="https://github.com/wangzhe3224/awesome-systematic-trading"><img alt="Listed in wangzhe3224/awesome-systematic-trading" src="https://img.shields.io/badge/listed%20in-wangzhe3224%2Fawesome--systematic--trading-2ea44f"></a>
  <a href="https://github.com/0xNyk/awesome-hermes-agent"><img alt="Listed in 0xNyk/awesome-hermes-agent" src="https://img.shields.io/badge/listed%20in-0xNyk%2Fawesome--hermes--agent-2ea44f"></a>
</p>

<p align="center">
  Listed in <a href="https://github.com/thuquant/awesome-quant">thuquant/awesome-quant</a> via merged PR
  <a href="https://github.com/thuquant/awesome-quant/pull/48">#48</a>.
</p>

<p align="center">
  Listed in <a href="https://github.com/leoncuhk/awesome-quant-ai">leoncuhk/awesome-quant-ai</a>
  under <em>Tools and Platforms / Data Providers</em> via merged PR
  <a href="https://github.com/leoncuhk/awesome-quant-ai/pull/39">#39</a>.
</p>

<p align="center">
  Listed in <a href="https://github.com/wangzhe3224/awesome-systematic-trading">wangzhe3224/awesome-systematic-trading</a> via merged PR
  <a href="https://github.com/wangzhe3224/awesome-systematic-trading/pull/124">#124</a>.
</p>

<p align="center">
  Listed in <a href="https://github.com/0xNyk/awesome-hermes-agent">0xNyk/awesome-hermes-agent</a> via merged PR
  <a href="https://github.com/0xNyk/awesome-hermes-agent/pull/232">#232</a>.
</p>

Investors rarely struggle because they cannot generate another paragraph of commentary. The harder questions are more concrete:

- Is a falling quality company becoming attractive, or is the business changing?
- After a semiconductor ETF rallies sharply, are you buying an industry cycle or an overcrowded valuation?
- Did the latest filing improve earnings quality, cash conversion, and shareholder returns?
- Does a ten-position portfolio actually contain ten independent risks?

`stock-analysis` handles the time-consuming first step: gather public data and primary disclosures, align dates and definitions, then assemble the six investment frameworks most relevant to the question. The output is not a one-line Buy/Sell label. It is a report covering facts, valuation, risks, disagreements, and conditional actions.

After installing the Skill, ask your Agent in plain language:

```text
Deeply research semiconductor ETF 512480. Test whether valuation already discounts the cycle,
analyze the underlying index history and drawdown, and estimate the round-trip cost of a CNY 1m order.
Select the six most relevant investment frameworks and produce the final committee report.
```

Or use the deterministic CLI directly:

```bash
uv tool install stock-analysis

stock-analysis --market daily
stock-analysis --market stock --symbol 600519
stock-analysis --market screen --fiscal-year 2025 --universe-file official_universe.json --filter roe_weighted:gt:8% --sort roe_weighted:desc
stock-analysis --market research --symbol 512480 --asset-type fund
```

> The output is for research only and does not constitute investment advice.

## 72-second demo

- [English video](promo/demo-video/out/stock-analysis-demo-en.mp4)
- [简体中文视频](promo/demo-video/out/stock-analysis-demo-zh-CN.mp4)

Both demos are 1080p, 72 seconds, caption-led, and work without audio. The current cut shows dynamic committee selection, official filings, index history, tracking error, and execution costs. Editable Remotion source lives in [`promo/demo-video`](promo/demo-video/).

## Why It Exists

Many AI investing tools start by asking several agents to debate and end with polished prose. The hard middle is often missing: Which reporting period does a number belong to? What index does an ETF actually own? Can disclosed tracking error be recomputed? How much return might spread and market impact consume on a CNY 1m order?

`stock-analysis` follows a different order: **build the evidence, select the frameworks, then form the view.**

| Common approach | What it does well | The choice made here |
|---|---|---|
| General-purpose chatbots | Fast explanations and fluent writing | Run deterministic data workflows first; source, date, and completeness checks gate every conclusion |
| Data platforms such as [OpenBB](https://github.com/OpenBB-finance/OpenBB) | Broad financial-data integrations | Focus on investor-ready Chinese-market workflows, reports, and natural-language Agent usage |
| Multi-agent projects such as [TradingAgents](https://github.com/TauricResearch/TradingAgents) and [ai-hedge-fund](https://github.com/virattt/ai-hedge-fund) | Role-based collaboration and trading experiments | Select six frameworks from fifteen for each question, and require every selected member to consume the same structured metrics |
| Financial-model projects such as [FinGPT](https://github.com/AI4Finance-Foundation/FinGPT) | Financial language models, sentiment, and training research | No model training required; prioritize primary disclosures, market evidence, index analysis, and a recoverable workflow |

The project pays particular attention to details that generic reports often skip:

- Company research reads structured financials and official annual-report PDFs, including governance and capital allocation. Net margin and operating-cash conversion reach every committee member.
- ETF research goes beyond NAV and top holdings. It reads official constituents, weights, valuation, and index history, then recomputes correlation, beta, tracking error, drawdown, and volatility.
- Stocks and ETFs share one order-cost scenario model covering spread, commission, venue fees, transfer fees, applicable stamp duty, and market impact.
- A later review can preserve the earlier workspace and identify what changed.

If a source fails, missing metrics stay missing. They are never filled with zeroes or inferred from a one-day price move.

## Start with the investor question

Choose the investing question you have rather than assembling low-level flags. Each scenario starts with deterministic evidence (checkable prices, disclosed financial facts, or public events); an Agent may interpret it, but cannot bypass its source, trading-date, and completeness rules.

| If you need to… | Use it when… | Scenario | Deterministic entrypoint |
|---|---|---|---|
| Understand today's market | You want market context before, during, or after a trading session. | `/market-recap` | `--market daily` |
| Fact-check a ticker | You only need price, recent performance, turnover, and disclosed facts—not an opinion. | `/stock-snapshot` | `--market stock --symbol` |
| Decide whether a company merits more research | You are considering a position, a hold, or a structured fact check. | `/stock-review` | `--market stock-review --symbol` |
| See what actually changed after results | A quarterly or annual report has been released and you want disclosed financial facts. | `/earnings-review` | `--market earnings --symbol` |
| Investigate a sharp move cautiously | You want price, volume, and public events without treating a headline as proof of cause. | `/price-move` | `--market price-move --symbol` |
| Check whether holdings are too concentrated | You have already saved complete holdings information. | `/portfolio-review` | `--market portfolio` |
| Find A-shares meeting explicit financial conditions | You have hard conditions such as ROE or revenue growth and need repeatable results. | `/stock-screen` | `--market screen …` |
| Record and revisit your investment case | You have an investment hypothesis and want to check it against later facts. | `/thesis-create`, `/thesis-review` | `--market thesis-create|thesis-review --symbol` |
| Run a recoverable institutional research process | You need staged artifacts that can be resumed, audited, and compared with the prior review. | `/research-workspace` | `--market research --symbol` |

Claude Code supports native `/command` entrypoints. In Codex, Custom Prompts appear as `/prompts:stock-review`; after installing the generated Skills, an Agent can match a plain-language request such as “review Tencent” to the relevant Skill and run its deterministic command. Intent matching happens in the host Agent from the Skill description, not in the `stock-analysis` Python package. The same canonical catalog generates every entrypoint, so their workflow contract does not drift.

## How the system works

```mermaid
flowchart TB
    U["Your investment question\nasset · date · decision tension"] --> I["Intent routing\nmarket · company · ETF/fund · portfolio · earnings · price move"]
    I --> P["Research Planner\nquestions and hypotheses to test"]
    P --> C1["Market evidence\nquotes · flows · sectors · risk"]
    P --> C2["Company disclosures\nannual reports · financials · governance · capital allocation"]
    P --> C3["Fund and index\nholdings · weights · valuation · index history"]
    C1 --> V["Validation and as-of control\ndates · units · deduplication · source fallback"]
    C2 --> V
    C3 --> V
    V --> E["Structured research base\nM1–M6 · C1–C8 · F1–F8 · Portfolio"]
    E --> K["Dynamic committee\nsix relevant frameworks selected from fifteen"]
    K --> S["Committee synthesis\nconsensus · disagreement · vetoes · conditional actions"]
    S --> R["Investor report\nsummary · deep analysis · valuation · risk · watchlist"]
    S --> W["Recoverable workspace\nstage outputs · compare the next review"]
```

For an investor, this reduces to four steps:

1. State the asset and the decision question in normal language.
2. The system chooses the appropriate evidence path and blocks information published after the research date.
3. Six relevant frameworks are selected from fifteen; the committee is not a fixed cast repeating generic views.
4. The report leads with the decision, then shows supporting numbers, disagreements, invalidation conditions, and what to monitor next.

The essential boundary is deliberate: **the question selects the research path, code obtains and validates evidence, and an investment framework only interprets existing data.** M1–M6 describes markets and portfolios, C1–C8 describes companies, and F1–F8 describes fund contracts, index exposure, valuation, tracking, and implementation.

```mermaid
flowchart LR
    Q["One claim to verify"] --> P["Preferred public source"]
    P --> V{"Symbol, date, unit, and sample valid?"}
    V -- Yes --> N["Normalize + calculate"] --> A["Consumed by every selected framework"]
    V -- No --> F["Validated alternate source"] --> V2{"Cross-checkable?"}
    V2 -- Yes --> N
    V2 -- No --> G["Keep a visible research boundary\nnever fill zero or guess"]
```

## Agent installation

### No programming experience: give this to your Agent

Paste into Codex, Claude Code, or Hermes:

```text
Install https://github.com/AdvancingTitans/stock-analysis for me:
1. clone the repository;
2. install stock-analysis with uv;
3. run the repository's Agent entrypoint installer;
4. verify stock-analysis --help and the installed Skill;
5. do not modify unrelated project files, and finish by giving me three prompts I can use immediately.
```

After that, ask “deeply research 600519”, “recap today's A-share market”, or “review my portfolio”. Intent matching happens in the host Agent; `stock-analysis` retrieves and validates the evidence.

### Terminal installation

```bash
git clone https://github.com/AdvancingTitans/stock-analysis.git
cd stock-analysis
uv tool install stock-analysis
python3 scripts/sync_agent_entrypoints.py --check
scripts/install-agent-entrypoints.sh codex
scripts/install-agent-entrypoints.sh claude
```

For CLI-only use, `uv tool install stock-analysis` is enough. The Agent installer copies Codex Skills into `${CODEX_HOME:-~/.codex}/skills` and Claude commands into `${CLAUDE_CONFIG_DIR:-~/.claude}/commands`; it does not modify existing portfolio memory.

## Prompt cookbook after installation

A useful prompt only needs four things: **asset, research date, core question, and the decision you are trying to make.**

```text
Recap today's A-share close. Assess indices, breadth, sector rotation, and risk appetite,
then explain which of my holdings beat or lagged their benchmarks and build tomorrow's watchlist.
Do not turn missing data into zero and do not merely repeat headlines.
```

```text
Deeply research Kweichow Moutai 600519. Test whether the current valuation is supported by
three-year earnings, cash generation, shareholder returns, and capital allocation.
Select the six most relevant frameworks and produce an investment-committee report.
```

```text
Research semiconductor ETF 512480. Go beyond past returns and top holdings: verify the full
underlying index, weights, valuation, and daily history; recompute tracking error, drawdown,
and volatility; estimate round-trip costs for CNY 100k, 1m, and 5m orders.
```

```text
Review my holdings: 100 shares of 600519 bought on 2026-06-01 and 100,000 units of 512480
bought on 2026-05-20. Diagnose sector, style, market, and currency concentration; compare
benchmarks and state the conditions for holding, reducing risk, or waiting for more evidence.
```

```text
Use Buffett mode to analyze Tencent, focusing on business quality, capital allocation,
and long-term cash flow.
```

```text
Use adversarial mode to let Buffett and Munger debate Tencent. One side should build the
long-term case; the other should search for governance, valuation, and opportunity-cost risks.
Let the portfolio manager synthesize the decision.
```

## Report Showcase

Start with the two current deep-research reports. They show the difference between this workflow and a generic AI write-up:

| Scenario | Question answered in the report | Example |
|---|---|---|
| Kweichow Moutai company research | How annual-report facts, net margin, cash conversion, payout, capital allocation, valuation sensitivity, and implementation cost affect the thesis | [600519 dynamic committee report](reports/final-validation-v412-r2/600519/20260717/07-institutional-report.md) |
| Semiconductor ETF research | Full index composition and valuation, 146 index observations, recomputed tracking error, drawdown, volatility, and order-cost scenarios | [512480 dynamic committee report](reports/final-validation-v412-r2/512480/20260717/07-institutional-report.md) |
| Global market recap | Indices, breadth, sectors, risk, portfolio context, and next-session watchlist | [Committee market recap](reports/20260709-投委会-行情复盘.md) |

<p align="center">
  <img src="assets/全球市场复盘_1.png" alt="Global committee market recap" width="31%">
  <img src="assets/贵州茅台个股分析（巴菲特）_1.png" alt="Kweichow Moutai company research" width="31%">
  <img src="assets/半导体基金分析_1.png" alt="Semiconductor fund research" width="31%">
</p>

Browse [reports/](reports/) for more reports, screenshots, and automation examples.

## What You Get

| Capability | What it means |
|---|---|
| Investor-readable committee reports | Executive summary first, followed by business/index logic, financials or holdings, valuation, disagreements, risk, and conditional actions. |
| Dynamic six-member committee | Selects the six best-matched frameworks from fifteen instead of sending every question to a fixed cast. |
| Primary company disclosures | Extensible rules read official annual-report PDFs and route operating, governance, payout, and capital-allocation facts into every framework. |
| Deep ETF research | Studies both fund and underlying index: complete constituents, weights, valuation, index history, tracking error, premium/discount, and execution scenarios. |
| A/HK/US stocks, funds, and portfolios | One entry layer for recaps, stocks, funds, earnings, price moves, screens, portfolios, and investment theses. |
| Multi-source and as-of discipline | Stable public sources first, validated fallback when needed, and no future disclosures in historical research. |
| Recoverable research workspace | Saves the plan, research base, framework opinions, committee synthesis, and final report for later comparison. |
| Human- and machine-readable output | Markdown for investors; JSON Evidence Packs for Agent verification, automation, and reuse. |

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

# Use when you want a structured company fact check: it gives facts and gaps, not a buy score
stock-analysis --market stock-review --symbol 600519 --emit-evidence

# Use after a results release: disclosed structured financial facts only
stock-analysis --market earnings --symbol 600519 --emit-evidence

# Use after a sharp move: price, volume, and public events without asserting causality
stock-analysis --market price-move --symbol 600519 --emit-evidence

# Create and later compare a local structured thesis snapshot
stock-analysis --market thesis-create --symbol 600519
stock-analysis --market thesis-review --symbol 600519

# Build or resume a staged institutional research workspace
stock-analysis --market research --symbol 600519
stock-analysis --market research --symbol 512480 --asset-type fund

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

Think of this as a “facts to check before doing more research” list. It is neither a stock screener nor an automatic buy/sell answer.

**When does it run?** Use `/stock-review` or `stock-analysis --market stock-review --symbol <symbol>` when you want to answer “should I spend more time researching or holding this company?” Running it does not create a portfolio, save an investment case, or assign a composite score. A thesis is saved locally only when you explicitly run `thesis-create`.

**What will you get?** The report separates checked facts, missing public data, and the next evidence you would need. For example, if financial quality and valuation facts are available, it shows their period and source. If there is not enough observable material on moat, management, or capital allocation, it says the evidence is missing instead of calling the company “high quality.”

| Module | Investor question | What it checks first |
|---|---|---|
| C1 Business quality | How does the company make money? | Quote, market, and available business facts; missing business breakdowns stay gaps. |
| C2 Financial quality | Are earnings and cash flow supported by disclosed facts? | Revenue, margins, ROE, leverage, operating cash flow, and free cash flow where disclosed. |
| C3 Growth quality | Is the claimed growth visible in disclosed numbers? | Structured revenue/profit history; it does not guess the source of growth. |
| C4 Moat evidence | Is there evidence for pricing power, stickiness, or cost advantage? | Observable evidence only; absent data is explicit. |
| C5 Management and capital allocation | Can buybacks, dividends, deals, dilution, or governance events be checked? | Available public events; no management verdict where coverage is absent. |
| C6 Valuation and margin of safety | What do price and valuation-related facts say today? | Quote, disclosed financial facts, and calculable metrics; never a “buy score.” |
| C7 Risk and counter-evidence | What facts would weaken the original case? | Price/volume anomalies, disclosed risks, and evidence gaps. |
| C8 Catalysts and thesis tracking | What public events should be revisited next? | News/event samples and the local-thesis review entrypoint. |

**Simplest choice:** run `stock-review` once, then read its available and missing modules. If you only want today’s price and recent movement, use `stock-snapshot`. If results have just been released, use `earnings-review`. If the price has moved sharply, use `price-move`. These are four different questions and should not substitute for one another.

Company research has a different data boundary from daily market recap. `company_evidence_<symbol>_<date>.json` stores C1–C8 verified facts and gaps. The current structured financial adapter is A-share focused; HK/US primary-filing fields intentionally remain gaps until a verified adapter exists, so those results are not a complete fundamental-research conclusion.

### Recoverable Research Workspace

`stock-analysis --market research --symbol <symbol>` materializes an institutional workflow under `~/.stock_analysis/research/<symbol>/<trade_date>/` (override it with `STOCK_ANALYSIS_RESEARCH_DIR` or `--workspace-dir`). Company research freezes C1–C8 Company Evidence; fund research (`--asset-type fund`, or common listed-fund prefixes in auto mode) freezes a separate F1–F8 Fund Evidence model covering mandate, holdings concentration, performance, tracking/premium, underlying valuation gaps, risk, governance, and monitoring triggers. Every lens and committee consumes the same content-addressed snapshot. Re-running the same date preserves manually edited artifacts and writes refreshed output to a `.generated` sibling.

Company opinions are deterministic framework assessments, not simulated quotations: every supporting and counter-evidence reference is an `evidence_id` from the same frozen `snapshot_id`. Committee synthesis rejects mixed snapshots, preserves consensus/disagreement and risk vetoes, and returns only `observe` or `manual_review`—never an automatic position or trade. Connected inputs now include structured financial disclosures/forecasts/flashes, PE/PB/market-cap snapshots, financing cash flow, and governance/capital-allocation announcement indexes. Aggregator records remain secondary until their linked issuer/exchange originals are verified.

Every financial fact records its period, currency, accounting scope, source type, source, and confidence so that you can trace a number back to its origin. The metric registry at [`config/metric_registry.json`](config/metric_registry.json) declares how a metric is validated and which framework can use it. It never produces a composite “buy score.”

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

Current CLI version: `4.12.0`.

`research` reports retain the denser Chinese committee narrative from the 4.5 series while keeping recoverable, traceable research state inside the Workspace. Company and fund reports preserve their institutional committee spines, but user-facing Markdown no longer exposes coverage flags, missing-module diagnostics, internal actions, snapshot IDs, or audit terminology.

`LensEngine` is the report orchestration layer. For `research`, the user's question deterministically selects the six most relevant and complementary lenses from the 15 built-ins; an explicit expert selection overrides that choice. Every selected member consumes all structured metrics from the same research point before interpreting them through its own framework. Natural-language callers can still request single-lens or adversarial modes explicitly.

Company primary disclosures use an extensible official-PDF → selected-page text → JSON regex rules → C1–C8 adapter. The 600519 catalog now extracts operating, channel, dividend, repurchase, audit-opinion, and capacity facts from the annual report itself; adding another issuer requires a catalog rather than Python report logic or hard-coded values.

For 512480, official CSI files provide the complete H30184 constituent list, month-end weights, daily valuation, and index daily history. ETF/index dates are strictly aligned to recompute correlation, beta, tracking error, and active return. Stocks, funds, and portfolio holdings share a scenario cost model covering spread, commission, venue/transfer fees, applicable stamp duty, volatility impact, and 20-day ADV participation.

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
