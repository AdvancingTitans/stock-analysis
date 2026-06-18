---
name: stock-analysis
description: 全球股市深度复盘技能。用于 A股、港股、美股、基金的当前行情、盘中/盘后复盘、6 模块证据驱动分析、young profile 持仓分析、单股速览与数据源诊断；执行腾讯/新浪优先、东财独有数据限流、证据质量评分和浏览器接管策略。
metadata:
  version: "4.1.0"
  author: "Hermes Agent + yjw"
  platforms: "linux, macos, windows"
---

# 全球股市深度复盘

先取数、校验交易日和字段完整性，再形成判断。所有强弱结论必须能回到成交额、放量倍数、资金流、涨跌家数或指数比较。

## 执行入口

```bash
uv run python -m stock_analysis --market daily
uv run python -m stock_analysis --market a --format full --emit-evidence
uv run python -m stock_analysis --market diagnose
```

- 默认 `--format auto`：根据当前北京时间自动选择 `summary`、`key-points` 或 `full`。
- `--date YYYYMMDD` 仅在用户明确指定日期时使用；未指定时自动解析最近 A股交易日。
- `--emit-evidence` 保留 `evidence_YYYYMMDD.json` 与 6 个模块 JSON。
- `mootdx` 默认关闭；只有明确需要五档、逐笔或深度分钟 K 时才使用 `--enable-mootdx`。
- 专用能力由 `sources/mootdx_adapter.py` 执行；依赖缺失、TCP 失败或返回空数据时自动回普通腾讯/新浪报价并记录原因。

## 数据路由

### A股

1. 实时报价、估值、指数、基础 K 线：腾讯 → 新浪。
2. 五档、逐笔、高精度分钟/深度 K：按需 mootdx；失败后回腾讯/新浪并记录原因。
3. 板块归属、资金流、涨跌停池、龙虎榜、解禁、两融、大宗、股东户数、研报和新闻：东财独有接口。
4. 东财失败或页面数据不完整：Camofox → Hermes browser 由 Agent 接管 → Playwright。

### 港美股

- 行情：新浪/腾讯互补 → 东财 `stock/get`。
- 港股历史 K 线：腾讯 K 线；美股历史 K 线：新浪。
- Yahoo 不属于推荐路径，不在报告或示例中使用。

### 基金

- 天天基金/东财基金估值 → 新浪基金备用。
- 基金重仓股统一走股票行情路由，并参与重复暴露分析。

详细字段与路由见 `references/data-source-strategy.md`。

## 强制规则

### 代码与字段

- 缓存、合并、持仓匹配前执行 `normalize_code(symbol, source)`。
- 腾讯/新浪响应强制按 GB2312 解码，必要时允许 GBK 兼容，禁止依赖自动编码检测。
- 价格 `<= 0` 自动过滤；字段空值保留 `None`，报告中留空，不显示误导性的 `0.00`。
- 指数涨跌额和涨跌幅同时为零或空时，必须切换来源重取；仍失败则不展示该行，并在 evidence 记录失败。
- 异常成交量写入 `quality_flags`；来源、交易日、来源链和失败原因写入 evidence。

### 东财

- 本包内东财请求统一走 `em_get()`：无代理、Session 复用、串行、最小间隔 1 秒、随机抖动、指数退避、最多 3 次。
- 风控经验阈值：`>5 次/秒`、并发 `>=10`、1 分钟 `>=200`、5 分钟 `>=300`。
- 部分大陆住宅 IP 可能出现 HTTP 000/空响应；先重试，再换网络或代理，不得把空响应当成零值。

### 浏览器

- Camofox 使用前检查 `http://localhost:9377/json/version`，3 秒无响应即不可用。
- Python CLI 当前自动调用 Camofox；Hermes browser 和本地 Playwright 由执行本 skill 的 Agent 接管，diagnose 负责暴露可用性。
- 全部浏览器路径不可用时，在 evidence/diagnose 标记 `数据源不可用`，不得静默跳过。

## 时段与报告

北京时间：

- A股/港股 09:00-09:30：早盘，轻量版。
- 09:30-11:30、13:00-15:00：盘中，中量版。
- 11:30-13:00：午间，中量版。
- 15:00 后：盘后，完整版。
- 美股 21:30-次日 04:00：夜盘，中量版；其他时段为盘后版。

用户明确要求“复盘、深度复盘、6 模块、证据驱动复盘”时，优先输出 `full`。

完整版固定顺序：

1. 大盘指数概览
2. 持仓分析
3. 6 模块深度复盘
4. 综合持仓建议与风险提示

无持仓时给出通用市场建议，并提示可通过 `young-stock-cli` 投资记忆或提供代码、数量、买入日期。

## Evidence Pack

生成：

- `evidence_YYYYMMDD.json`
- `m1_YYYYMMDD.json` 至 `m6_YYYYMMDD.json`

评分权重：M1 20、M2 20、M3 20、M4 15、M5 15、M6 10。

- `>=80`：完整报告。
- `60-79`：完整报告，并列出缺失模块。
- `<60`：仅指数、持仓和风险提示。

`_meta` 至少包含 `trade_date`、`session`、`quality_score`、`missing_modules`、`source_events`。

6 模块方法见 `references/methodology/`，报告模板见 `references/template/`，输出纪律见 `references/output_discipline.md`。

## 持仓

- 自动读取 `~/.young_stock/profile.json` 或 `YOUNG_STOCK_PROFILE`。
- 支持股票、基金、买入日期、数量和买入参考价。
- HKD/USD 按当前汇率折算 CNY，明细保留原始币种。
- 前三大持仓占比 `>70%` 标记集中度风险；单一市场 `>80%` 标记市场暴露风险。
- A股对比沪指/创业板，港股对比恒指/恒生科技，美股对比纳指/道指。
- 建议必须使用条件化触发器，不得给出无条件买卖指令。

## 输出纪律

- 研报正文不展示 API、抓取工具或 fallback 工程细节；这些只进入 evidence 和 diagnose。
- 每个模块使用 `==关键判断==`，并包含判断、证据、风险或确认条件。
- 指数、持仓、连板梯队使用 Markdown 表格。
- 结尾必须原样包含：

`以上内容仅供参考，不构成任何投资建议。股市有风险，投资需谨慎。`

## 示例

- “复盘今日行情，分析我的持仓”
- “今天全球市场怎么样，给我 summary”
- “盘后给我完整 6 模块证据驱动复盘”
- “帮我跑 diagnose，检查腾讯、新浪、东财、mootdx 和浏览器链路”
