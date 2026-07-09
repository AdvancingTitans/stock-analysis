# stock-analysis

<div align="center">
  <a href="./README.md">English</a> |
  <a href="./README.zh-CN.md">简体中文</a>
</div>

<p align="center">
  <img src="assets/social-preview.png" alt="stock-analysis social preview" width="860">
</p>

<p align="center">
  <strong>面向 AI Agent、量化研究者和投资者的证据优先市场复盘 CLI。</strong>
</p>

<p align="center">
  A 股 / 港股 / 美股 · 基金 · 持仓 · JSON Evidence Pack · 数据质量评分 · 多源降级 · 投资者 lens
</p>

<p align="center">
  <a href="https://github.com/thuquant/awesome-quant"><img alt="Listed in thuquant/awesome-quant" src="https://img.shields.io/badge/listed%20in-thuquant%2Fawesome--quant-2ea44f"></a>
</p>

<p align="center">
  已通过 PR <a href="https://github.com/thuquant/awesome-quant/pull/48">#48</a> 收录到
  <a href="https://github.com/thuquant/awesome-quant">thuquant/awesome-quant</a>。
</p>

`stock-analysis` 把公开市场数据整理成可复查的 Markdown 报告和机器可读的证据文件。它适合做稳定、可重复的行情复盘，而不是输出黑箱交易信号。

```bash
uv tool install stock-analysis

stock-analysis --market daily
stock-analysis --market stock --symbol 600519
stock-analysis --market global --format full --with-holdings --emit-evidence
```

> 输出仅供研究参考，不构成投资建议。

## 为什么需要它

很多“AI 行情分析”是先写 prompt，再得到一段看起来流畅的文字。`stock-analysis` 的顺序相反：先有证据，再写结论。

- 抓取 A 股、港股、美股、基金和持仓相关的公开市场数据。
- 在下结论前统一处理代码、时间戳、来源元数据和缺失字段。
- 用六个证据模块给报告质量打分，而不是假装每个数据源都正常工作。
- 输出 JSON，方便 AI Agent、notebook、cron 任务或人工审阅者检查和 diff。

如果数据源失败，报告会记录缺口。缺失指标保持缺失，不会用 `0` 回填，也不会用邻近信号硬猜。

## 报告示例

| 投委会复盘 | Buffett 视角复盘 | Simons 视角复盘 |
|---|---|---|
| [2026-07-09 投委会行情复盘](reports/20260709-投委会-行情复盘.md)<br>![Global market recap](assets/全球市场复盘_1.png) | [2026-07-09 巴菲特行情复盘](reports/20260709-巴菲特-行情复盘.md)<br>![Buffett global recap](assets/全球市场复盘（巴菲特）_1.png) | [2026-07-09 西蒙斯行情复盘](reports/20260709-西蒙斯-行情复盘.md)<br>![Simons global recap](assets/全球市场西蒙斯视角行情分析_1.png) |

| Buffett 个股 lens | Simons 个股 lens | 基金画像 |
|---|---|---|
| [贵州茅台 600519](reports/20260709-巴菲特-贵州茅台600519.md)<br>![Moutai Buffett lens](assets/贵州茅台个股分析（巴菲特）_1.png) | [贵州茅台 600519](reports/20260709-西蒙斯-贵州茅台600519.md)<br>![Moutai Simons lens](assets/贵州茅台个股分析（西蒙斯）_1.png) | [512480 半导体ETF](reports/20260709-512480-半导体ETF基金分析.md)<br>![Semiconductor fund analysis](assets/半导体基金分析_1.png) |

更多报告、截图、社交分享素材和自动化示例见 [reports/](reports/)。

## 你会得到什么

| 能力 | 含义 |
|---|---|
| Evidence Pack JSON | 生成 `evidence_YYYYMMDD.json` 和 M1-M6 模块文件，便于审计、自动化和 Agent 交接。 |
| A 股 / 港股 / 美股 / 基金覆盖 | 一个 CLI 同时覆盖全市场快照、单股、基金和持仓暴露。 |
| 数据源路由 | 稳定场景优先 Tencent / Sina，中国市场特有数据走 Eastmoney，只有必要时才用浏览器降级。 |
| 质量评分 | 报告带 100 分证据质量评分，并明确标出缺失模块。 |
| 投资者 lens | 内置 Buffett、Munger、Graham、Simons、Dalio、Duan Yongping、Zhang Kun 等结构化 lens。 |
| 本地持仓记忆 | 可选的本地持仓 profile，支持基准对比、集中度风险和汇率归一。 |

## 快速开始

从 PyPI 安装：

```bash
uv tool install stock-analysis
stock-analysis --market daily
```

从本地仓库运行：

```bash
git clone https://github.com/AdvancingTitans/stock-analysis.git
cd stock-analysis
uv run stock-analysis --market daily
```

常用命令：

```bash
# 按北京时间市场阶段自动选择 summary/key-points/full
stock-analysis --market daily

# 带 JSON 证据的完整全球市场复盘
stock-analysis --market global --format full --emit-evidence

# 确定性的单股快照，不依赖 LLM
stock-analysis --market stock --symbol 600519

# 带公开画像和持仓数据的基金快照
stock-analysis --market fund --symbol 161725

# 诊断 Tencent、Sina、Eastmoney、browser 和可选 mootdx 路由
stock-analysis --market diagnose
```

## 证据模块

启用 `--emit-evidence` 后，CLI 会写出：

```text
evidence_YYYYMMDD.json
m1_YYYYMMDD.json
m2_YYYYMMDD.json
m3_YYYYMMDD.json
m4_YYYYMMDD.json
m5_YYYYMMDD.json
m6_YYYYMMDD.json
```

六模块评分关注的是报告可信度，不是收益宣传：

| 模块 | 关注点 | 权重 |
|---|---:|---:|
| M1 | 跨市场指数状态、广度、流动性、基准背景 | 20 |
| M2 | 行业和概念轮动 | 20 |
| M3 | 短线情绪和涨停结构 | 20 |
| M4 | 风险、突破失败、下行压力 | 15 |
| M5 | 持仓暴露、风格、集中度、持仓脉冲 | 15 |
| M6 | 韧性方向和下一交易日观察清单 | 10 |

即使质量评分偏低，完整报告也会保持相同结构；缺失模块会在相关章节自然说明。

## 为 Agent 而设计

`stock-analysis` 对工具调用友好：

- 先有确定性 CLI，LLM 层可以后续消费 evidence。
- Markdown 给人看，JSON 给机器工作流用。
- 明确记录来源事件和 fallback 原因。
- 命令界面稳定，适合 cron、notebook、Hermes、Codex、Claude Code 和其他工具调用型 Agent。

示例 Agent prompt：

```text
Run stock-analysis --market global --format full --emit-evidence.
Use the Markdown report for the user-facing recap.
Use evidence_YYYYMMDD.json to verify every strong conclusion before summarizing.
If a module is missing, say which evidence was unavailable instead of guessing.
```

日常 Agent 工作流见 [examples/agent.md](examples/agent.md)，定时生成报告并上传 Evidence Pack 的 GitHub Actions 示例见 [examples/github-actions-daily-recap.yml](examples/github-actions-daily-recap.yml)。

## 它不是什么

- 不是交易机器人。
- 不是券商接口。
- 不承诺覆盖所有市场数据。
- 不能替代专业投资建议。
- 不是黑箱 LLM 报告生成器。

## 数据源策略

| 场景 | 主路径 | 降级路径 |
|---|---|---|
| A 股行情和估值 | Tencent → Sina | Eastmoney `stock/get` |
| A 股指数 | Tencent → Sina | Eastmoney index endpoints |
| 板块排行 | Eastmoney `clist` | Tonghuashun public pages → browser fallback |
| 港股行情 | Tencent/Sina | Eastmoney `stock/get` |
| 美股行情 | Sina/Tencent | Eastmoney `searchapi` → `stock/get` |
| 基金 | Eastmoney/Tiantian fund pages | Sina fund fallback |
| 深度 tick / order-book 数据 | Optional `mootdx` | Basic Tencent/Sina quotes |

Yahoo 不是推荐默认路径的一部分，这是有意为之。

## 投资者 Lens

Lens engine 可以把同一份 evidence 按不同投资框架组织成报告。当前支持：

`buffett`, `munger`, `graham`, `klarman`, `lynch`, `o_neil`, `wood`, `dalio`, `soros`, `livermore`, `minervini`, `simons`, `duan_yongping`, `zhang_kun`, `feng_liu`.

Lens 会改变证据优先级和叙事结构，但不会绕过数据质量规则，也不会编造缺失数字。

### 内置 lens 与 committee 边界

当前 CLI 版本为 `4.3.9`。

LensEngine 是报告生成的核心编排器。默认使用 committee 模式；该模式会综合 M1-M6 证据做跨模块深度分析，也就是原来的 m1/m6 综合深度分析边界。自然语言调用可以表达为“用巴菲特模式分析贵州茅台”或“用 adversarial 模式让巴菲特和芒格辩论腾讯”。如果 `committee` 失败，会降级为 `single`，也就是 committee 失败时降级为 single，并在 metadata 中保留 fallback 原因。

`committee` 报告有固定骨架：执行摘要 → 大盘指数概览 → 持仓分析（有完整持仓时）→ 六模块深度复盘 → 综合持仓建议与风险提示。结尾建议需要覆盖现状总结、基准跑赢/跑输、条件化仓位动作、下一交易日观察清单和风险提示。证据附录不进入早盘、盘中、午间或盘后正文；如果 M1-M6 某个模块缺失，相关章节必须说明证据暂缺。

`--market stock --symbol <code>` 和 `--market fund --symbol <code>` 是确定性证据视图，不要求用户安装任何外部行情 CLI。浏览器路径只作为 API 连续失败或页面独有数据的降级路径；工程细节进入 evidence/diagnose，不进入正文。

基金画像通过天天基金公开评估页 `pingzhongdata` 补充长期业绩、前端费率、规模和基金经理画像；该路径不依赖登录或 API key。基金速览应展示长期业绩、前端费率、基金经理信息和已披露缺口。

投资记忆默认路径为 `~/.stock_analysis/profile.json`，也可以用 `STOCK_ANALYSIS_PROFILE` 覆盖。完整持仓必须同时具备股票代码、买入日期、买入数量或买入金额。若用户新提供的信息与之前保存的投资记忆不一致，确认信息完整性后，优先以用户新提供的信息为准，并覆盖写入投资记忆。

当用户明确提出想用哪位投资专家的风格时，整篇报告都必须完全以相关专家的视角输出报告，不得只在结尾追加专家点评。单专家视角和多专家综合的结构不同，但都不得模仿身份声明或虚构专家发言。

## 贡献

适合上手的贡献方向：

- 新增或加固公开数据源 adapter。
- 改进报告模板或投资者 lens。
- 为新的地区、标的类型或 Agent 工作流补充示例。
- 带着 `--market diagnose` 输出报告数据源失效。
- 把项目提交到匹配度高的 Awesome List 或 Agent 工具目录。

请先阅读 [CONTRIBUTING.md](CONTRIBUTING.md) 和 [ROADMAP.md](ROADMAP.md)。

## Awesome List 简介

提交到精选列表时，可以使用这句简介：

> [stock-analysis](https://github.com/AdvancingTitans/stock-analysis) - Evidence-driven market recap CLI for AI agents and quant researchers, supporting A/HK/US stocks, funds, portfolios, auditable JSON Evidence Packs, data-quality scoring, investor lenses, and multi-source fallback routing.

适合目标包括 `awesome-quant-ai`、`awesome-ai-in-finance`、`awesome-quant` 和 `awesome-systematic-trading`。

## 开发

```bash
uv sync
uv run --with pytest pytest -q
uv run --with ruff ruff check
```

## License

MIT

以上内容仅供研究参考，不构成任何投资建议。股市有风险，投资需谨慎。
