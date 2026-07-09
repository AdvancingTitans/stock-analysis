# stock-analysis

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

## Report Showcase

| Committee recap | Buffett recap | Simons recap |
|---|---|---|
| [2026-07-08 投委会行情复盘](reports/20260708-投委会-行情复盘.md)<br>![Global market recap](assets/全球市场复盘_1.png) | [2026-07-08 巴菲特行情复盘](reports/20260708-巴菲特-行情复盘.md)<br>![Buffett global recap](assets/全球市场复盘（巴菲特）_1.png) | [2026-07-08 西蒙斯行情复盘](reports/20260708-西蒙斯-行情复盘.md)<br>![Simons global recap](assets/全球市场西蒙斯视角行情分析_1.png) |

| Buffett stock lens | Simons stock lens | Fund profile |
|---|---|---|
| [贵州茅台 600519](reports/20260708-巴菲特-贵州茅台600519.md)<br>![Moutai Buffett lens](assets/贵州茅台个股分析（巴菲特）_1.png) | [贵州茅台 600519](reports/20260708-西蒙斯-贵州茅台600519.md)<br>![Moutai Simons lens](assets/贵州茅台个股分析（西蒙斯）_1.png) | [512480 半导体ETF](reports/20260708-512480-半导体ETF基金分析.md)<br>![Semiconductor fund analysis](assets/半导体基金分析_1.png) |

Browse the [full report showcase](reports/README.md) for the six revised 2026-07-08 Markdown reports, the data-gap audit note, screenshots, social-share assets, and automation examples.

## What You Get

| Capability | What it means |
|---|---|
| Evidence Pack JSON | `evidence_YYYYMMDD.json` plus M1-M6 module files for audit, automation, and agent handoff. |
| A/HK/US/fund coverage | One CLI for broad market snapshots, single stocks, funds, and portfolio exposure. |
| Data-source routing | Tencent/Sina first where stable, Eastmoney for unique China-market data, browser fallback only when needed. |
| Quality scoring | Reports carry a 100-point evidence quality score and identify missing modules. |
| Investor lenses | Built-in Buffett, Munger, Graham, Simons, Dalio, Duan Yongping, Zhang Kun, and other structured lenses. |
| Portfolio memory | Optional local holdings profile with benchmark comparison, concentration risk, and FX normalization. |

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

# Deterministic fund snapshot with public profile and holdings data
stock-analysis --market fund --symbol 161725

# Diagnose Tencent, Sina, Eastmoney, browser, and optional mootdx routes
stock-analysis --market diagnose
```

## Evidence Modules

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

### 内置 lens 与 committee 边界

当前 CLI 版本为 `4.3.8`。

LensEngine 是报告生成的核心编排器。默认使用 committee 模式；committee 模式会做 m1/m6 综合深度分析。自然语言调用可以表达为“用巴菲特模式分析 贵州茅台”或“用 adversarial 模式让巴菲特和芒格辩论 腾讯”。committee 失败时降级为 single，并在 metadata 中保留 fallback 原因。

固定 committee 报告结构为：执行摘要 → 大盘指数概览 → 持仓分析（有完整持仓时）→ 六模块深度复盘 → 综合持仓建议与风险提示。结尾建议固定包含现状总结、基准跑赢/跑输、条件化仓位动作、下一交易日观察清单、风险提示。证据附录不进入早盘、盘中、午间或盘后正文；如果 M1-M6 某个模块缺失，相关章节必须标注证据暂缺。

`--market stock --symbol <代码>` 与 `--market fund --symbol <代码>` 是确定性证据视图，不要求用户安装任何外部行情 CLI。浏览器路径只作为 API 连续失败或页面独有数据的降级路径，工程细节进入 evidence/diagnose，不进入正文。

基金画像通过天天基金公开评估页 `pingzhongdata` 补充长期业绩、前端费率、规模和基金经理画像；该路径不依赖登录或 API key。基金速览应展示长期业绩、前端费率、基金经理和已披露缺口。

投资记忆默认路径为 `~/.stock_analysis/profile.json`，也可以用 `STOCK_ANALYSIS_PROFILE` 覆盖。完整持仓必须同时具备股票代码、买入日期、买入数量或买入金额。若用户新提供的信息与之前保存的投资记忆不一致，确认信息完整性后，优先以用户新提供的信息为准，覆盖写入投资记忆。

当用户明确提出想用哪位投资专家的风格时，报告必须完全以相关专家的视角输出报告；不得只在结尾追加专家点评。单专家视角和多专家综合的结构不同，但都不得模仿身份声明或虚构专家发言。

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

以上内容仅供参考，不构成任何投资建议。股市有风险，投资需谨慎。
