# stock-analysis

基于 `AdvancingTitans/stock-analysis` 日报框架重构的全球股市深度复盘技能，整合：

- `simonlin1212/a-stock-data` 的 A 股全栈数据分层与东财限流原则
- `simonlin1212/global-stock-data` 的港美股多源报价与代码映射思路
- `a-stock-daily-market-sense` 的 6 模块证据驱动复盘方法论

目标是提供一个稳定、证据化、支持持仓分析和自动时段适配的全球市场复盘引擎。

## v4 架构

```
stock-analysis/
├── src/stock_analysis/
│   ├── app.py                # 主入口
│   ├── normalize.py          # normalize_code(symbol, source)
│   ├── market_time.py        # 交易日与时段判断
│   ├── http.py               # GB2312 强制解码 + 东财 em_get
│   ├── diagnostics.py        # diagnose 命令
│   ├── evidence.py           # evidence_YYYYMMDD.json + quality_score
│   ├── portfolio.py          # 持仓完整性校验
│   ├── reporting.py          # 固定顺序 Markdown 输出
│   └── sources/router.py     # 多市场 fallback 路由
├── skills/stock-analysis/
│   ├── SKILL.md
│   ├── scripts/
│   │   ├── daily_recap.py
│   │   └── aftermarket.py
│   └── references/
│       ├── methodology/
│       ├── template/
│       └── output_discipline.md
└── tests/
```

## 数据源策略

### A股

- 默认主路径：腾讯财经 `qt.gtimg.cn` + 新浪财经 `hq.sinajs.cn`
- `mootdx` 仅按需启用：五档盘口、逐笔成交、高精度分钟/深度 K 线、扩展实时报价
- 东财仅用于独有数据：板块归属、资金流、龙虎榜、解禁、两融、大宗、股东户数、研报、新闻、全球资讯
- 优先级铁律：腾讯/新浪 > mootdx（独有能力） > 东财（独有数据且必须限流）

### 港美股

- 主路径：新浪 + 腾讯 + 东财 `push2/stock/get`

### 持仓标的

- A股：腾讯批量 > 新浪 > 东财 > 浏览器降级
- 港股：腾讯港股 > 新浪港股 > 东财港股 > 浏览器降级
- 美股：腾讯美股 > 新浪美股 > 东财美股 > 浏览器降级
- 基金：天天基金/东财基金 > 新浪基金 > 浏览器降级
- 任一标的 `price/change/change_pct` 缺失时，必须触发全链路 fallback；仍失败则在 evidence 中记录，正式报告字段留空

### 汇率与盈亏

- HKD/USD 持仓统一折算 CNY 计算组合浮盈亏
- 明细中保留原始币种

## 网络与降级

### 东财限流

- 所有东财接口统一走 `em_get()`
- 串行调用，最小间隔 `>= 1s`，带随机抖动
- `requests.Session` 复用
- 指数退避重试最多 3 次
- 文档中保留社区实测风控阈值：`>5 req/s`、`并发 >=10`、`1 分钟 >=200`、`5 分钟 >=300`

### 浏览器降级

- 降级顺序：`camofox-browser` REST > Hermes 内置浏览器 > Playwright
- Camofox 降级前先做 `http://localhost:9377/json/version` 健康检查，超时 3 秒视为不可用
- 所有浏览器工具不可用时，模块必须显式标注 `数据源不可用`

### 编码

- 腾讯/新浪响应统一强制 `response.encoding = "gb2312"`
- 禁止依赖自动编码检测

## 自动时段模式

- 早盘：轻量版
- 盘中：中量版
- 盘后：完整版，固定顺序为：
  1. 大盘指数概览
  2. 持仓分析
  3. 6 模块深度复盘
  4. 综合持仓建议与风险提示

默认日期是当前自然日；非交易日自动回溯到最近交易日，并写入 `evidence_YYYYMMDD.json` 的 `_meta.trade_date`。

## 使用

```bash
~/.local/bin/uv sync
~/.local/bin/uv run python -m stock_analysis --market diagnose
~/.local/bin/uv run python skills/stock-analysis/scripts/daily_recap.py --market daily --format summary
~/.local/bin/uv run python skills/stock-analysis/scripts/daily_recap.py --market a --format full
~/.local/bin/uv run python skills/stock-analysis/scripts/aftermarket.py --market daily
```

## 与 young-stock-cli 的关系

- 保留对 `young profile` 投资记忆的读取能力
- 不再把整个技能实现绑定为 `young-stock-cli` 的薄包装
- `aftermarket.py` 继续兼容旧调用方式，但会转发到新的证据驱动引擎

## 输出纪律优化

- 对可补齐字段优先走多源补齐，不让用户直接看到 `未知`、`数据不足`、`--`
- 仍无法稳定补齐时，正文默认隐藏该字段，不输出生硬占位词
- 例如：
  - 美股指数若缺成交额，则只写点位和涨跌
  - 个股若缺板块归属，则不写板块描述
  - 趋势不足以计算 MA 时，不输出“趋势数据不足”
- A股板块归属优先补东财 `slist`；板块榜/页面类数据优先 API，失败再走浏览器降级
- 报告形态默认向“研报分析形式”靠拢，而非命令行 checklist
- 正式报告不显示数据接口、来源站点或 fallback 技术细节
- 固定增加指数、持仓、连板梯队三类 Markdown 表格
- 持仓建议按券商研报结尾展开：
  - 现状总结
  - 基准跑赢/跑输
  - 仓位动作建议
  - 观察清单
  - 风险提示
- 仓位建议会识别直接持股与基金重仓股的重复暴露，并使用连续跑输、均线破位、炸板率和连板梯队等条件作为动作触发器
- 趋势数据优先使用：
  - A股：百度股市通 K 线与 MA
  - 美股：新浪美股日 K
  - 港股：低优先级历史 K 线备用链路

## 当前实现状态

- 已完成：项目骨架、标准化层、交易日/时段判断、诊断命令、证据包评分、持仓完整性校验、真实多源抓取适配、汇率折算、研报式报告生成、兼容入口、方法论文档
- 待继续增强：实时多源抓取器、完整指数/板块/持仓行情汇总、浏览器抓取执行层

## 风险提示

以上内容仅供参考，不构成任何投资建议。股市有风险，投资需谨慎。
