# stock-analysis

全球股市行情+情绪分析工具，覆盖 A股（沪深京）、港股、美股等主要市场。

## 功能

- **A股**：东财免登录 API 实时/盘后数据，涨跌停池，行业/概念板块榜（浏览器抓取）
- **港美股**：东财 clist 批量接口获取行情（免登录、不限流），富途免登录资讯搜索
- **跨市场情绪**：结构化复盘模板，板块轮动分析，社区情绪评分
- **浏览器降级**：camofox / Hermes 内置浏览器 / Playwright 页面抓取（API 失败时降级）

## 安装

### 通过 Hermes CLI

```bash
git clone https://github.com/AdvancingTitans/stock-analysis.git ~/.hermes/skills/research/stock-analysis
```

### 依赖

- Python 3.8+（运行 `scripts/aftermarket.py`）
- `curl` (所有系统通用)
- **可选** — 浏览器自动化（用于板块榜和页面抓取）：
  - [camofox-browser](https://github.com/daijro/camoufox) REST 服务，或
  - Hermes 内置浏览器工具（`browser_navigate`, `browser_console`），或
  - Playwright / Puppeteer / Selenium

## 用法

### 命令行脚本

```bash
# A股复盘（自动检测交易日）
python scripts/aftermarket.py --market a

# 美股复盘
python scripts/aftermarket.py --market us

# 港股复盘
python scripts/aftermarket.py --market hk

# 全球市场概览（美股+港股+A股指数）
python scripts/aftermarket.py --market global

# 指定日期（A股）
python scripts/aftermarket.py --market a 20260526
```

### 作为 Hermes Skill 使用

安装到 `~/.hermes/skills/research/stock-analysis` 后，Hermes 会自动加载 `SKILL.md` 上下文。

示例提示：
- "今天 A 股怎么样"
- "复盘下今日行情"
- "美股今天怎么样"
- "港股腾讯怎么样"
- "早盘怎么看"

## 目录结构

```
stock-analysis/
├── skills/
│   └── stock-analysis/
│       ├── SKILL.md                  # Hermes Agent 技能主体说明
│       ├── scripts/
│       │   └── aftermarket.py        # 一键采集脚本
│       └── references/
│           ├── eastmoney-api.md      # 东财富免登录 API 速查（A股+港美股）
│           ├── yahoo-finance-api.md  # Yahoo Finance API 速查（已废弃）
│           ├── futu-api.md           # 富途免登录搜索 API 速查
│           └── analysis-template.md  # 结构化复盘模板
├── README.md                         # 本文件
├── LICENSE                           # MIT
└── .gitignore
```

### 通过 Hermes CLI 安装

```bash
hermes skills install --repo AdvancingTitans/stock-analysis --path skills/stock-analysis
```

## 数据来源

| 来源 | 市场 | 类型 | 登录需求 | 优势 |
|---|---|---|---|---|
| push2.eastmoney.com | **A股** | 指数行情、资金流向、涨跌停数据 | **不需要** | 免登录、不限流、价格实时 |
| push2ex.eastmoney.com | **A股** | 涨跌停/炸板池 | **不需要** | 同上 |
| push2.eastmoney.com/api/qt/clist/get | **港美股** | 指数+个股实时行情 | **不需要** | **免登录、不限流、一次批量拉取**，替代 Yahoo Finance |
| quote.eastmoney.com | A股 | 行业/概念板块页面 | 不需要（浏览器抓取） | |
| query1.finance.yahoo.com | 全球 | 行情、K线、财务指标 | 不需要 | 已废弃；仅美股道指/VIX 东财暂无时备用 |
| ai-news-search.futunn.com | 全球 | 新闻、公告、研报、社区 | 不需要 | |

### 为什么用东财 clist 替代 Yahoo Finance

| 维度 | Yahoo Finance v8 | 东财 clist |
|---|---|---|
| 登录/API Key | 不需要 | **不需要** |
| 限流 | 严格（约 5 次后 429） | **未观察到限流** |
| 批量获取 | 逐个 symbol（慢） | **一次请求，最多 500 条** |
| 美股指数 | ✅ SPX、NDX、DJI、VIX | ✅ SPX、NDX；❌ DJI、VIX（暂无） |
| 美股个股 | ✅ 全部 | ✅ 主流标的（AAPL、NVDA、TSLA 等） |
| 港股指数 | ✅ HSI、HSCE、HSTECH | ✅ HSI、HSCE、HSTECH |
| 港股个股 | ✅ 全部 | ✅ 主流标的（0700、9988 等） |

> 注意：美股道指 DJI 和 VIX 东财暂不支持，需其他数据源补充。

## 市场覆盖

| 市场 | 指数 | 个股 | 新闻 | 情绪 |
|---|---|---|---|---|
| **A股（沪深京）** | ✅ 东财 | ✅ 东财 | ✅ 富途（中文名） | ✅ 富途 |
| **美股** | ✅ 东财 clist (SPX、NDX) | ✅ 东财 clist | ✅ 富途（代码） | ✅ 富途 |
| **港股** | ✅ 东财 clist (HSI、HSCE、HSTECH) | ✅ 东财 clist | ✅ 富途（代码） | ✅ 富途 |
| **日股** | ⚠️ 仅 Exa | ⚠️ 仅 Exa | ⚠️ 仅 Exa | ⚠️ 仅 Exa |

## 注意事项

- **A股**：东财 API 非官方公开接口，字段名可能调整。涨跌停池 `date` 参数只返回**当日**数据。
- **东财 clist**：使用 `fltt=2`；价格字段以 ×100 的整数返回，脚本内已自动除以 100。
- **数据质量**：所有行情返回统一的 `QuoteData` 结构。零/负价自动过滤，指数成交量为 0 降级为 warning，异常偏低成交量标记 `*`，输出末尾附数据质量报告。
- **富途搜索**：偏港美股。A股用**中文公司名**（非代码）；港美股用**代码**。
- **时区**：美股盘后复盘建议北京时间次日 05:00 后；港股 16:00 后。

## 更新日志

### v3.1.0
- **东财 clist 替代 Yahoo Finance v8 chart**获取港美股数据
  - Yahoo 429 限流问题不再存在
  - 从逐个 symbol 请求改为批量拉取
  - 不需登录、不需 API Key、不需 Cookie
- 移除港美股 3 秒请求间隔（东财不限流）；A股间隔保持
- 新增 `_normalize_diff` 辅助函数，兼容东财 `diff` 不一致格式（数组 vs 对象）
- 新增 `_em_clist_price` 辅助函数，正确处理 `fltt=2` 价格字段
- 新增 `EM_CODE_MAP` Yahoo symbol → 东财 f12 映射
- 美股道指 DJI 和 VIX 移除默认指数（东财暂不支持）
- 所有 `source` 字符串从 `yahoo_chart` 更新为 `eastmoney_clist`
- User-Agent 升级为 `stock-analysis/3.1.0`

### v3.0.0
- 技能重命名为 `stock-analysis`，仓库结构调整为 `skills/stock-analysis/`
- 废弃 Yahoo v6 批量接口，改用 v8 chart 逐个拉取（带缓存）
- 新增三层获取策略：缓存 → 稳定 API → 浏览器降级
- 新增本地缓存层 `~/.cache/stock-analysis/`
- 修复 A股指数价格格式 — 东财 `fltt=2` 已返回正常价格
- 修复富途 `publish_time` 字符串转换崩溃
- 修复 `^HSTECH` 404 — 改用 `HSTECH.HK`
- 请求间隔从 0.5s 调整为 3s；404 不重试
- 新增诊断摘要输出
- 统一数据结构 `QuoteData`，完整度评分
- 新增自动数据质量验证

### v2.1.0
- 新增 `--market global` 跨市场概览
- 新增指数退避重试机制
- 新增自动数据清洗（成交量异常检测、价格过滤）
- 新增数据完整度评分与质量报告
- 新增市场类型自动检测
- 优化错误处理 — 缺失数据静默跳过，不干扰输出

### v2.0.0
- 新增全球市场支持（港美日通过 Yahoo Finance + 富途）
- 移除硬编码代理设置，提升兼容性

## License

MIT
