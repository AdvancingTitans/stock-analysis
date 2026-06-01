# stock-analysis

全球股市行情+情绪分析工具，覆盖 A股（沪深京）、港股、美股等主要市场。

## 功能

- **A股**：东财免登录 API 实时/盘后数据，涨跌停池，同花顺概念资金流优先源，行业/概念板块榜（浏览器抓取）
- **港美股**：腾讯/新浪财经批量行情为主，东财 `stock/get` 精确兜底，clist 批量补充，富途与新浪资讯多源 fallback
- **基金持仓**：天天基金实时估值 + 东财基金持仓，联动持仓股行情和当天新闻
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
python scripts/aftermarket.py --market a --no-news

# 美股复盘
python scripts/aftermarket.py --market us

# 港股复盘
python scripts/aftermarket.py --market hk

# 全球市场概览（美股+港股+A股指数）
python scripts/aftermarket.py --market global

# 单只股票速览（A股/港股/美股，自动标注来源交易日）
python scripts/aftermarket.py --market stock --stock 600519
python scripts/aftermarket.py --market stock --stock 0700.HK
python scripts/aftermarket.py --market stock --stock AAPL --no-news
python scripts/aftermarket.py --market news --stock 3690.HK  # 只看多源新闻、来源和链接
python scripts/aftermarket.py --market fund --fund 161725    # 基金估算收益 + 持仓股行情/新闻
python scripts/aftermarket.py --market fund --fund 161725 --no-news
python scripts/aftermarket.py --market hk --no-news

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
- "查一下 600519"
- "腾讯控股现在什么情况"
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
| push2.eastmoney.com / np-listapi.eastmoney.com | **A股/新闻** | 指数行情、最新 A股资金流、涨跌停数据、东方财富快讯 | **不需要** | 免登录，资金流输出会标注实际交易日 |
| data.10jqka.com.cn | **A股资金流** | 概念板块流入、流出、净额 | **不需要** | 页面表格较稳定，作为资金流方向优先源 |
| push2ex.eastmoney.com | **A股** | 涨跌停/炸板池 | **不需要** | 同上 |
| qt.gtimg.cn | **港美股/A股指数降级** | 指数行情、港股收盘口径 | **不需要** | 港股指数收盘点位更接近交易所/新闻稿口径 |
| hq.sinajs.cn | **A股/港美股** | 单只股票、指数、重点个股实时行情 | **不需要** | 批量、免登录，单票查询主路径 |
| push2.eastmoney.com/api/qt/stock/get | **A股/港美股** | 单只指数/个股实时行情 | **不需要** | 精确查询，避开 clist 排序窗口 |
| push2.eastmoney.com/api/qt/clist/get | **港美股** | 指数+部分榜单行情 | **不需要** | 批量补充路径 |
| quote.eastmoney.com | A股 | 行业/概念板块页面 | 不需要（浏览器抓取） | |
| ai-news-search.futunn.com | 全球 | 新闻、公告、研报、社区 | 不需要 | |
| feed.mix.sina.com.cn | 全球 | 新浪财经滚动新闻 | 不需要 | 与富途、东财快讯一起做新闻 fallback/热度参考 |
| fundgz.1234567.com.cn / fundf10.eastmoney.com | 基金 | 基金估值、净值日期、持仓明细 | 不需要 | 基金用户查看估算涨跌和重仓股表现 |

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
- **基金估算**：基金正式净值通常晚间更新；脚本里的“当日估算”来自天天基金实时估值，不作为最终净值确认。
- **新闻链接**：输出前会剔除明显 404/无内容页面；网络临时校验失败时保留链接，避免误杀正常新闻。
- **同花顺资金流**：`funds/gnzjl` 只作为概念板块资金流方向参考，不替代指数或个股行情主路径；若触发风控会继续降级到东财、新浪、腾讯和本地缓存。
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

### v3.4.0
- 新增单只股票速览：`--market stock --stock 600519`，支持 A股、港股和 best-effort 美股，输出价格、涨跌、成交量/额、来源和数据交易日。
- 同步 young-stock-cli 0.1.4：`young flow`/脚本资金流输出明确标注为 A股上证指数口径，并显示数据源实际交易日。
- 默认交易日选择在工作日 15:00 前仍使用上一交易日，避免早盘/午间把尚未结算的当天数据写入复盘。
- 东财 `push2his` 历史资金流当前不再作为稳定兜底；A股复盘仅在资金流返回日期与复盘日期一致时使用，否则给出清晰提示。

### v3.4.1
- 同步 young-stock-cli 0.1.5：资金流即使返回交易日与请求日不一致，也展示最新可用数据并明确标注来源交易日和请求日期。
- 资金流实时接口临时不可用时，先尝试在线资金流页面指标接口，再尝试新浪/腾讯 A股指数活跃度指标；这些指标会明确标注“不等同于主力资金净流入”，在线源都不可用时才降级展示本地最近一次可信资金流缓存。
- 港美股重点个股会基于富途、新浪财经、东方财富快讯等免登录来源做新闻热度 Top5 排序；雪球/同花顺若无稳定免登录接口，不作为默认硬依赖。
- 新闻输出逐条显示来源和链接状态；热度排序基于所有来源命中数和新鲜度，展示时尽量保留多来源，不让单一来源自动挤掉其他有效来源。
- 新闻只展示请求交易日当天发布的有效内容，最多 5 条；不足 5 条则按实际数量展示，没有则明确提示暂未获取到有效新闻信息。
- A股复盘默认带市场新闻，`--no-news` 可跳过。
- 所有行情命令标注当前阶段：上午盘、午间、下午盘、盘后；若展示非请求日数据，会标注为该交易日盘后数据，阶段字段包含数据日期。
- `--no-news` 可用于 `--market a`、`--market hk`、`--market us`、`--market stock`，只看行情时不会输出新闻链接。
- 默认不再输出“数据源切换记录”；如需排查接口，可设置 `YOUNG_STOCK_DEBUG=1`。

### v3.5.0
- 同步 young-stock-cli 0.1.9：新增基金查询，支持 `--market fund --fund 161725`，输出基金当日估算涨跌、上一净值日、前十大持仓股行情、重仓贡献粗算和持仓股当天新闻。
- `young flow`/脚本资金流在东财实时与页面指标不可用时，会先尝试新浪财经资金流页面行业流向，再落到新浪/腾讯指数活跃度和本地最近可信缓存；所有非主力净流入口径均明确标注。
- 新闻聚合会过滤明显无内容或 404 的链接，尽量用其他当天新闻替换。

### v3.5.1
- 同步 young-stock-cli 0.1.10：`young flow`/脚本资金流优先尝试同花顺概念资金流页面，输出概念净流入/净流出方向并标注概念板块口径。
- 若同花顺页面不可用，会继续降级到东财实时资金流、东财页面指标、新浪行业资金流、指数活跃度和本地最近可信缓存。

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
