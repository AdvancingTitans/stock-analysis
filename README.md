# stock-analysis

全球股市行情+情绪分析工具，覆盖 A股（沪深京）、港股、美股等主要市场。

## 功能

- **A股**：东财免登录 API 实时/盘后数据，涨跌停池，行业/概念板块榜（浏览器抓取）
- **港美股**：腾讯/新浪财经批量行情为主，东财 `stock/get` 精确兜底，clist 批量补充，富途与新浪资讯多源 fallback
- **跨市场情绪**：结构化复盘模板，板块轮动分析，社区情绪评分
- **浏览器降级**：camofox / Hermes 内置浏览器 / Playwright 页面抓取（板块榜或 API 失败时降级）

## 安装

### 通过 Hermes CLI

```bash
git clone https://github.com/AdvancingTitans/stock-analysis.git ~/.hermes/skills/research/stock-analysis
```

### 依赖

- Python 3.10+（运行 `scripts/aftermarket.py`）
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
| push2his.eastmoney.com | **A股** | 历史资金流向 | **不需要** | `fflow` 实时接口关闭连接时兜底 |
| push2ex.eastmoney.com | **A股** | 涨跌停/炸板池 | **不需要** | 同上 |
| qt.gtimg.cn | **港美股/A股指数降级** | 指数行情、港股收盘口径 | **不需要** | 港股指数收盘点位更接近交易所/新闻稿口径 |
| hq.sinajs.cn | **港美股/A股指数降级** | 指数+重点个股实时行情 | **不需要** | 批量、免登录，对港美股更稳 |
| push2.eastmoney.com/api/qt/stock/get | **港美股** | 单只指数/个股实时行情 | **不需要** | 精确查询，避开 clist 排序窗口 |
| push2.eastmoney.com/api/qt/clist/get | **港美股** | 指数+部分榜单行情 | **不需要** | 批量补充路径 |
| quote.eastmoney.com | A股 | 行业/概念板块页面 | 不需要（浏览器抓取） | |
| ai-news-search.futunn.com | 全球 | 新闻、公告、研报、社区 | 不需要 | |
| feed.mix.sina.com.cn | 全球 | 新浪财经滚动新闻 | 不需要 | 富途资讯不可用时兜底 |

### 为什么用腾讯/新浪财经 + 东财补充源

东财 clist 适合做港美股批量补充，但它按榜单返回，港股 `m:128` 可能优先返回牛熊证/衍生品，美股 `m:105,m:106,m:107` 也可能优先返回小盘或权证，导致腾讯、阿里、苹果、英伟达等重点正股不在本地过滤结果中。v3.3.0 起，港股指数优先用腾讯财经收盘口径，港美重点个股优先调用新浪财经批量行情；缺失时再用东财 `stock/get` 单只精确兜底，clist 作为批量补充。

| 维度 | 腾讯财经 | 新浪财经 | 东财 stock/get / clist |
|---|---|---|---|
| 登录/API Key | 不需要 | 不需要 | 不需要 |
| 使用时机 | 港股指数优先；指数补充 | 港美个股首选；指数补充 | 新浪/腾讯缺失时兜底/补充 |
| 批量获取 | ✅ | ✅ | `stock/get` 逐只；clist 批量 |
| 美股指数 | ✅ SPX、NDX、DJI | ✅ SPX、NDX、DJI | ✅ SPX、NDX、DJI |
| 美股重点股 | - | ✅ AAPL、NVDA、TSLA、MSFT、AMZN、GOOGL、META、BABA、PDD、JD | ✅ 常见重点股 |
| 港股指数 | ✅ HSI、HSCEI、HSTECH | ✅ HSI、HSCEI、HSTECH | ✅ HSI、HSCEI、HSTECH |
| 港股重点股 | - | ✅ 0700、9988、3690、9618、1299、2318、0005、0388 | ✅ 常见重点股 |

> 注意：DJI 已通过新浪财经覆盖；VIX 暂无稳定免登录源，若缺失，脚本输出诊断摘要，不裸眼定性。

## 市场覆盖

| 市场 | 指数 | 个股 | 新闻 | 情绪 |
|---|---|---|---|---|
| **A股（沪深京）** | ✅ 东财 | ✅ 东财 | ✅ 富途（中文名） | ✅ 富途 |
| **美股** | ✅ 新浪/腾讯/东财 (SPX、NDX、DJI) | ✅ 新浪/东财 | ✅ 富途/新浪（代码） | ✅ 富途 |
| **港股** | ✅ 腾讯/新浪/东财 (HSI、HSCEI、HSTECH) | ✅ 新浪/东财 | ✅ 富途/新浪（代码） | ✅ 富途 |
| **日股** | ⚠️ 仅 Exa | ⚠️ 仅 Exa | ⚠️ 仅 Exa | ⚠️ 仅 Exa |

## 注意事项

- **A股**：东财 API 非官方公开接口，字段名可能调整。涨跌停池 `date` 参数只返回**当日**数据。
- **港美股行情**：港股指数优先腾讯收盘口径；港美重点个股优先新浪财经；缺失时用东财 `stock/get` 兜底，clist 作为补充。东财 `fltt=2` 当前返回真实价，不再除以 100。
- **新浪财经**：批量拉取，响应为 GBK 编码，脚本已自动解码。
- **新闻 fallback**：富途 `news_search` 不可用时会尝试富途 feed，再尝试新浪财经滚动新闻。
- **数据质量**：所有行情返回统一的 `QuoteData` 结构。零/负价自动过滤，指数成交量为 0 降级为 warning，异常偏低成交量标记 `*`，输出末尾附数据质量报告。
- **富途搜索**：偏港美股。A股用**中文公司名**（非代码）；港美股用**代码**。
- **时区**：美股盘后复盘建议北京时间次日 05:00 后；港股 16:00 后。

## 更新日志

### v3.3.0
- 同步 young-stock-cli 多源增强：新增腾讯财经 `qt.gtimg.cn`，港股指数优先使用腾讯收盘口径，并在输出中提示和新浪盘后快照可能存在口径差异。
- 新闻增加 fallback 链路：富途 news_search → 富途 feed → 新浪财经滚动新闻。
- A股指数在东财失败、再到新浪失败时可继续降级到腾讯指数。
- 输出风格改为“数据质量与来源提示 / 口径说明 / 复盘仅供参考”，移除“输出结束”等偏技术化文案。
- 港股指数表将成交额和成交量区分展示，并显示当前命中的数据源。

### v3.2.0
- **同步 young-stock-cli 核心实现**：港美股主路径改为新浪财经批量行情，东财 `stock/get` 单只精确兜底，clist 作为补充。
- 美股默认指数恢复道指 DJI（走新浪财经）；VIX 仍暂不默认纳入。
- A股资金流在东财实时 `fflow` 接口关闭 Python 直连时，降级到 `push2his` 历史资金流接口并放宽请求策略。
- 恒生指数改用新浪 `hkHSI` 完整行情，补齐成交量字段。
- A股指数在东财接口失败时降级到新浪指数。
- HTTP 请求绕过本地代理，避免 Clash 等代理导致东财/新浪接口 502。
- 空数据/错误响应不再写入缓存，减少缓存污染。
- 修正东财 `fltt=2` 价格处理：按真实价处理，不再除以 100。

### v3.1.4
- 恢复并前置缓存防污染约束到 `SKILL.md` 主上下文：5 分钟 TTL、按交易日隔离缓存、`--no-cache` / `--refresh` 强制刷新、过期缓存直接 miss、盘中/盘后标题自动切换
- 明确后续迭代如果调整缓存策略，必须同步更新脚本、技能说明和 README，防止 v3.1.1 的缓存污染修复被文档压缩遗漏
### v3.1.3
- 新增腾讯行情 `qt.gtimg.cn` 作为港股/美股免登录备用源
  - 东财 clist 缺失港股正股、美股大盘股或部分港股指数时自动补齐
  - 已验证补齐港股：恒指、国企指数、恒生科技，以及 0700、9988、3690、9618、1299、2318、0005、0388
  - 已验证补齐美股：AAPL、TSLA、NVDA、MSFT、AMZN、GOOGL、META、BABA、PDD、JD
- 修复腾讯行情 GBK 解码，中文名称正常显示
- 修复东财 clist 港美股/指数价格误除以 100 的问题
- 全球概览可完整输出港股三大指数；诊断摘要会标注腾讯 fallback 命中项
- 默认备用源不使用境外行情接口，降低地区网络和限流风险

### v3.1.2
- 压缩 `SKILL.md` 主上下文，降低模型 token 消耗
- 保留数据源优先级、三层获取、缓存、诊断摘要和“禁止裸眼定性”等关键约束
- 明确最终回答只引用关键数字和结论，不复制完整原始输出

### v3.1.1
- **修复缓存污染问题**：早盘数据未更新时缓存了昨日数据，导致后续运行始终输出旧数据
  - 新增 `--no-cache` / `--refresh` 参数，强制刷新缓存
  - 缓存增加 5 分钟 TTL 过期机制，盘中实时数据不再长期污染
  - 标题根据当前时间自动切换：上午盘/午间/下午盘/盘后

### v3.1.0
- **东财 clist 替代境外逐只行情接口**获取港美股数据
  - 降低境外接口限流影响
  - 从逐个 symbol 请求改为批量拉取
  - 不需登录、不需 API Key、不需 Cookie
- 移除港美股 3 秒请求间隔（东财不限流）；A股间隔保持
- 新增 `_normalize_diff` 辅助函数，兼容东财 `diff` 不一致格式（数组 vs 对象）
- 新增 `_em_clist_price` 辅助函数，正确处理 `fltt=2` 价格字段
- 新增 `EM_CODE_MAP` 外部 symbol → 东财 f12 映射
- 美股道指 DJI 和 VIX 移除默认指数（东财暂不支持）
- 所有行情 `source` 字符串统一为稳定数据源标识
- User-Agent 升级为 `stock-analysis/3.1.0`

### v3.0.0
- 技能重命名为 `stock-analysis`，仓库结构调整为 `skills/stock-analysis/`
- 废弃不稳定的批量行情接口，改用逐标的行情接口（带缓存）
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
- 新增全球市场支持（港美日行情 + 富途资讯）
- 移除硬编码代理设置，提升兼容性

## License

MIT
