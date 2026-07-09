# Report Showcase

This directory contains the revised release showcase reports for 2026-07-08 plus the data-gap audit note. They are generated Markdown examples, not investment advice.

## 2026-07-08 Reports

| Report | Lens / scope |
|---|---|
| [西蒙斯 · 7.8 行情](20260708-西蒙斯-行情复盘.md) | Quant-style global market recap. |
| [巴菲特 · 7.8 行情](20260708-巴菲特-行情复盘.md) | Value-investing global market recap. |
| [投委会 · 7.8 行情](20260708-投委会-行情复盘.md) | Committee-mode global market recap. |
| [512480 基金分析](20260708-512480-半导体ETF基金分析.md) | Semiconductor ETF fund analysis. |
| [巴菲特 · 茅台 600519](20260708-巴菲特-贵州茅台600519.md) | Kweichow Moutai single-stock analysis, Buffett lens. |
| [西蒙斯 · 茅台 600519](20260708-西蒙斯-贵州茅台600519.md) | Kweichow Moutai single-stock analysis, Simons lens. |

## Data-Gap Audit

- [2026-07-08 数据缺口审计与补全说明](20260708-数据缺口审计与补全说明.md): documents which fields were repaired and which gaps remain intentionally unfilled.

## Screenshot Gallery

| Use case | Screenshots |
|---|---|
| Global market recap | [1](../assets/全球市场复盘_1.png) · [2](../assets/全球市场复盘_2.png) · [3](../assets/全球市场复盘_3.png) |
| Global recap, Buffett lens | [1](../assets/全球市场复盘（巴菲特）_1.png) · [2](../assets/全球市场复盘（巴菲特）_2.png) · [3](../assets/全球市场复盘（巴菲特）_3.png) |
| Global recap, Simons lens | [1](../assets/全球市场西蒙斯视角行情分析_1.png) · [2](../assets/全球市场西蒙斯视角行情分析_2.png) · [3](../assets/全球市场西蒙斯视角行情分析_3.png) · [4](../assets/全球市场西蒙斯视角行情分析_4.png) · [5](../assets/全球市场西蒙斯视角行情分析_5.png) |
| Moutai, Buffett lens | [1](../assets/贵州茅台个股分析（巴菲特）_1.png) · [2](../assets/贵州茅台个股分析（巴菲特）_2.png) · [3](../assets/贵州茅台个股分析（巴菲特）_3.png) · [4](../assets/贵州茅台个股分析（巴菲特）_4.png) |
| Moutai, Simons lens | [1](../assets/贵州茅台个股分析（西蒙斯）_1.png) · [2](../assets/贵州茅台个股分析（西蒙斯）_2.png) · [3](../assets/贵州茅台个股分析（西蒙斯）_3.png) · [4](../assets/贵州茅台个股分析（西蒙斯）_4.png) |
| Semiconductor fund profile | [1](../assets/半导体基金分析_1.png) · [2](../assets/半导体基金分析_2.png) · [3](../assets/半导体基金分析_3.png) |
| Social-share cards | [Chinese share card](../assets/share-cn-1.png) · [X card 1](../assets/share-x-1.png) · [X card 2](../assets/share-x-2.png) · [GitHub social preview](../assets/social-preview.png) |

## Automation Examples

- [Agent workflow](../examples/agent.md): run the CLI, inspect Markdown, and audit strong claims against the Evidence Pack.
- [GitHub Actions daily recap](../examples/github-actions-daily-recap.yml): scheduled report generation with uploaded Markdown and JSON evidence artifacts.
