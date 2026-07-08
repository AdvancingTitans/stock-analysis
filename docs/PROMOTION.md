# Promotion Plan

This repo should be promoted as an evidence-first market recap engine for AI agents and quant researchers, not as a trading bot.

## Positioning

Short version:

> Evidence-driven stock analysis CLI for AI agents: A/HK/US stocks, funds, portfolios, auditable JSON Evidence Packs, data-quality scoring, investor lenses, and multi-source fallback routing.

Avoid these labels:

- Trading bot
- Stock picker
- Financial advisor
- Charting app
- Generic market-data API

Use these labels:

- Evidence-first recap CLI
- Agent-readable market research tool
- Auditable stock analysis reports
- Public-data market evidence pack

## Awesome List Targets

| Priority | Repository | Suggested section | PR angle |
|---|---|---|---|
| P0 | `leoncuhk/awesome-quant-ai` | LLM-Based Trading Agents / Tools and Platforms | Agent-readable evidence and investor lenses. |
| P0 | `georgezouq/awesome-ai-in-finance` | Agents / Research Tools | Finance AI analysis with deterministic evidence before LLM synthesis. |
| P1 | `wilsonfreitas/awesome-quant` | Market Data & Data Sources | Python CLI for public market recap and evidence-pack generation. |
| P1 | `paperswithbacktest/awesome-systematic-trading` | Data Sources / Data Science | Research-oriented daily recap and portfolio exposure, not a bot. |
| P2 | `akfamily/awesome-data` | Open Data Tools | Public financial data turned into auditable reports. |
| P2 | `ashishpatel26/500-AI-Agents-Projects` | Finance | AI-agent use case once README screenshots and examples are in place. |
| P3 | `Shubhamsaboo/awesome-llm-apps` | Finance / Agents | Wait until there is a runnable agent demo or app-style example. |

## PR One-Liners

General:

```markdown
- [stock-analysis](https://github.com/AdvancingTitans/stock-analysis) - Evidence-driven market recap CLI for AI agents and quant researchers, supporting A/HK/US stocks, funds, portfolios, auditable JSON Evidence Packs, data-quality scoring, investor lenses, and multi-source fallback routing.
```

For quant lists:

```markdown
- [stock-analysis](https://github.com/AdvancingTitans/stock-analysis) - Python CLI that generates auditable A/HK/US stock, fund, and portfolio recap reports from public data, with JSON evidence packs, quality scoring, and resilient source fallback.
```

For AI-agent lists:

```markdown
- [stock-analysis](https://github.com/AdvancingTitans/stock-analysis) - Agent-friendly stock market research CLI that produces Markdown reports plus JSON Evidence Packs before any LLM synthesis, reducing black-box finance hallucinations.
```

## Share Copy

X / LinkedIn:

```text
I built stock-analysis: an evidence-first market recap CLI for AI agents.

Instead of asking an LLM to "analyze the market" from thin air, it first builds auditable JSON evidence packs from public A/HK/US stock, fund, and portfolio data, then renders deterministic Markdown reports.

MIT: https://github.com/AdvancingTitans/stock-analysis
```

Chinese technical communities:

```text
做了一个给 AI Agent 用的股市复盘 CLI：stock-analysis。

核心不是“预测涨跌”，而是先从公开数据生成可审计 Evidence Pack，再输出 Markdown 复盘：A股/港股/美股/基金/持仓，带质量评分、数据源 fallback、多投资框架 lens。

适合日常复盘、Agent 自动化、量化研究笔记，不做自动交易。
https://github.com/AdvancingTitans/stock-analysis
```

## Asset Checklist

- `assets/social-preview.png`: GitHub repository social preview.
- `assets/share-x-1.png`: X/LinkedIn launch card.
- `assets/share-x-2.png`: lens comparison card.
- `assets/share-cn-1.png`: Chinese square card.

## Launch Order

1. Make install, README, screenshots, and contribution docs consistent.
2. Submit P0 Awesome List PRs.
3. Publish the X/LinkedIn and Chinese posts with `assets/share-x-1.png` or `assets/share-cn-1.png`.
4. Add an agent automation example.
5. Submit P1 and P2 Awesome List PRs.
