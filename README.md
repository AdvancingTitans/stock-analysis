# stock-analysis

全球股市行情+情绪分析工具，覆盖 A股（沪深京）、港股、美股等主要市场。

## 功能

- **A股**：东财免登录 API 实时/盘后数据，涨跌停池，行业/概念板块榜（浏览器抓取）
- **港美股**：东财 clist 批量接口优先，腾讯行情免登录接口补齐东财榜单缺口，富途免登录资讯搜索
- **跨市场情绪**：结构化复盘模板，板块轮动分析，社区情绪评分
- **浏览器降级**：camofox / Hermes 内置浏览器 / Playwright 页面抓取（板块榜或 API 失败时降级）

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
| push2.eastmoney.com/api/qt/clist/get | **港美股** | 指数+部分榜单行情 | **不需要** | **免登录、不限流、一次批量拉取**，优先使用 |
| qt.gtimg.cn | **港美股** | 指数+重点个股实时行情 | **不需要** | **东财 clist 缺失时自动补齐**，国内网络更稳定 |
| quote.eastmoney.com | A股 | 行业/概念板块页面 | 不需要（浏览器抓取） | |
| ai-news-search.futunn.com | 全球 | 新闻、公告、研报、社区 | 不需要 | |

### 为什么增加腾讯行情备用源

东财 clist 适合做港美股批量入口，但它按榜单返回，港股 `m:128` 可能优先返回牛熊证/衍生品，美股 `m:105,m:106,m:107` 也可能优先返回小盘或权证，导致腾讯、阿里、苹果、英伟达等重点正股不在本地过滤结果中。v3.1.3 起，脚本在东财 clist 缺失时自动调用腾讯行情 `qt.gtimg.cn` 批量补齐。

| 维度 | 东财 clist | 腾讯行情备用 |
|---|---|---|
| 登录/API Key | 不需要 | 不需要 |
| 使用时机 | 首选 | 仅在东财缺失时触发 |
| 批量获取 | ✅ | ✅ |
| 美股指数 | ✅ SPX、NDX | ✅ SPX、NDX |
| 美股重点股 | 可能因榜单分页缺失 | ✅ AAPL、NVDA、TSLA、MSFT、AMZN、GOOGL、META、BABA、PDD、JD |
| 港股指数 | 可能只返回部分指数 | ✅ HSI、HSCEI、HSTECH |
| 港股重点股 | 可能因衍生品榜单缺失 | ✅ 0700、9988、3690、9618、1299、2318、0005、0388 |

> 注意：美股道指 DJI 和 VIX 默认仍不强行补充；若缺失，脚本输出诊断摘要，不裸眼定性。

## 市场覆盖

| 市场 | 指数 | 个股 | 新闻 | 情绪 |
|---|---|---|---|---|
| **A股（沪深京）** | ✅ 东财 | ✅ 东财 | ✅ 富途（中文名） | ✅ 富途 |
| **美股** | ✅ 东财 clist (SPX、NDX) | ✅ 东财 clist + 腾讯 fallback | ✅ 富途（代码） | ✅ 富途 |
| **港股** | ✅ 东财 clist + 腾讯 fallback (HSI、HSCEI、HSTECH) | ✅ 东财 clist + 腾讯 fallback | ✅ 富途（代码） | ✅ 富途 |
| **日股** | ⚠️ 仅 Exa | ⚠️ 仅 Exa | ⚠️ 仅 Exa | ⚠️ 仅 Exa |

## 注意事项

- **A股**：东财 API 非官方公开接口，字段名可能调整。涨跌停池 `date` 参数只返回**当日**数据。
- **东财 clist**：使用 `fltt=2`；已验证港美股/指数价格字段为正常小数，脚本不再缩放。
- **腾讯行情 fallback**：仅在东财 clist 缺失时触发，批量拉取，响应为 GBK 编码，脚本已自动解码。
- **数据质量**：所有行情返回统一的 `QuoteData` 结构。零/负价自动过滤，指数成交量为 0 降级为 warning，异常偏低成交量标记 `*`，输出末尾附数据质量报告。
- **富途搜索**：偏港美股。A股用**中文公司名**（非代码）；港美股用**代码**。
- **时区**：美股盘后复盘建议北京时间次日 05:00 后；港股 16:00 后。

## 更新日志

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
