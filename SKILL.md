---
name: a-stock-market
description: "全球股市行情+情绪分析：A股（东财免登录API）、港美股（Yahoo Finance免登录API + 富途免登录资讯）、板块榜浏览器抓取、舆情交叉验证。"
version: 2.0.0
author: Hermes Agent + yjw
tags: [stock-market, a-shares, hk-shares, us-shares, eastmoney, futu, yahoo-finance, sentiment, global-finance]
platforms: [linux, macos, windows]
---

# 全球股市行情与情绪分析

支持 A股（沪深京）、港股、美股、日股等主要市场的行情获取与情绪分析流程。A股使用东财免登录 API绕开反爬陷阱；港美股使用 Yahoo Finance 免登录 API 获取实时行情，结合富途免登录资讯搜索能力进行新闻/公告/研报/社区情绪快照。

详细 API 端点速查见 `references/` 目录，分析框架模板见 `references/analysis-template.md`，开箱即用脚本见 `scripts/aftermarket.py`。

## When to Use

- 用户问"今天 A 股怎么样"、"复盘下今日行情"、"分析下大盘情绪"
- 用户问"早盘怎么看"、"盘中什么情况"、"现在市场情绪如何"
- 用户问"美股今天怎么样"、"拿拿 AAPL/TSLA 行情"、"纳斯达克怎么样"
- 用户问"港股怎么样"、"腾讯/9633 怎么样"、"恒指怎么样"
- 需要拿涨跌停数、连板梯队、板块涨跌（A股）
- 需要查某只标的最新新闻、公告、研报（A股/港股/美股均可）
- 需要看某只标的社区/论坛情绪（富途覆盖港美股更全面）
- 任何涉及上证/深证/创业板/科创板/北证/恒指/国指/科指/纳指/标普 500 的实时或盘后查询

## 市场分类与数据源对应

| 市场 | 行情数据 | 新闻/情绪 | 板块/概念 | 复盘文章 |
|---|---|---|---|---|
| **A股** | 东财 API | 富途 news_search + stock_feed | 东财页面抓取 | Exa 搜"当日复盘" |
| **港股** | Yahoo Finance API | 富途 news_search + stock_feed | 富途/东财港股页面 | Exa 搜"港股 行情" |
| **美股** | Yahoo Finance API | 富途 news_search + stock_feed | Yahoo/富途美股页面 | Exa 搜"美股市场" |
| **日股** | Yahoo Finance API | Exa 搜日文资讯 | 东财国际页面 | Exa 搜"日股" |

## 核心数据源优先级

### 通用（全市场）
1. **Yahoo Finance 免登录 API** (`query1.finance.yahoo.com`) — 实时行情、K线、财务指标。**港美日股基础数据首选**。支持代码格式：AAPL（美股）、0700.HK（港股）、9988.T（日股）。3900.HK（港股期权）等。
2. **富途免登录 Search Skills** (`ai-news-search.futunn.com`) — 新闻/公告/研报搜索、个股解读、社区情绪。**资讯侧证首选**，对港美股代码支持极好，无需 OpenD。
3. **Exa 搜索**（**必须** 带 `startPublishedDate` 参数）— 交叉验证舆情倾向。英文索引对港美股覆盖更好。
4. **浏览器抓取**（camofox / Hermes browser / Playwright）— 富途、Yahoo、东财国际等页面数据，绕开反爬。

### A股专有（补充）
5. **东方财富免登录 API** (`push2.eastmoney.com` + `push2ex.eastmoney.com`) — 指数、涨跌停池、个股行情。**A股基础数据首选**。

## 富途搜索市场区分对照

| 市场 | 代码格式示例 | 建议 keyword |
|---|---|---|
| **A股** | 000001、603017 | 中文公司全称（如"比亚迪"），因代码可能命中港股/美股同名标的 |
| **港股** | 00700、99988 | 代码（如"00700"）或中文名（如"腾讯控股"），富途对港股支持极好 |
| **美股** | AAPL、TSLA、NVDA | 代码（如"AAPL"），富途对美股支持极好 |
| **中概股** | BABA、PDD、JD | 代码（如"BABA"），富途搜索覆盖好 |

**港股代码特殊说明**：富途的 `news_search` 和 `stock_feed` 搜索港股时，可以用 `0700`（去掉前导 0）或 `00700`。Yahoo Finance 必须使用 `0700.HK` 格式。

## 数据拉取规范（强制）

**任何分析必须先拉数据，禁止裸眼定性。**如某个接口因反爬/时段限制无法获取，静默跳过该项，不在输出中体现。

**市场分类必拉清单：**

### A股最小数据集

| 必拉项 | 接口/方式 | 备注 |
|---|---|---|
| 6 大指数 | `push2.eastmoney.com` ulist | 盘中走浏览器 fetch，盘后可尝试 curl |
| 涨跌停池 | `push2ex.eastmoney.com` ZT/DTPool | curl 稳定，date 只能传当日 |
| 炸板池 | `push2ex.eastmoney.com` ZBPool | 同上 |
| 主力资金流向 | `push2.eastmoney.com` fflow | 盘中走浏览器 fetch |
| 行业/概念板块榜 | 浏览器抓取 | API 裸 curl 被拦 |
| 当日复盘文章 | Exa `web_search_exa` | 必带 `startPublishedDate` |

### 港美股最小数据集

| 必拉项 | 接口/方式 | 备注 |
|---|---|---|
| 实时行情 | Yahoo Finance `/v8/finance/chart/` | 稳定，支持全球市场 |
| 基本面/财务指标 | Yahoo Finance `/v10/finance/quoteSummary/` | 收益、PE、市值等 |
| 当日新闻/公告 | 富途 `news_search` | 代码搜索精准度高 |
| 社区情绪 | 富途 `stock_feed` | 代码搜索精准度高 |
| 市场舆情 | Exa 搜索 + Jina Reader | 英文覆盖更好 |
| 榜单/市值排名 | 富途/东财页面抓取 | 用浏览器抓取排行榜 |

**港美股分析特殊处理**：
- 港美股无涨跌停制度，不适用"连板梯队"、"炸板率"等 A股专属指标。重点看：大盘指数涨跌、成交量变化、板块轮动、个股新闻/财报影响。
- 美股盘后复盘重点：纳斯达克/标普 500 涨跌、成交量、板块轮动、重要个股动态、聘储/大众交易所交易情况（使用 browser 抓取）。
- 港股盘后复盘重点：恒指/国指/科指涨跌、南向资金流向、个股板块动态。

## Yahoo Finance API 速查（详见 references/yahoo-finance-api.md）

```bash
# 实时行情（支持美股、港股、日股、A股外资）
curl -s "https://query1.finance.yahoo.com/v8/finance/chart/AAPL?interval=1d&range=1d"
curl -s "https://query1.finance.yahoo.com/v8/finance/chart/0700.HK?interval=1d&range=1d"

# 财务摘要（收益、PE、市值等）
curl -s "https://query2.finance.yahoo.com/v10/finance/quoteSummary/AAPL?modules=summaryDetail,defaultKeyStatistics,financialData"
```

## 富途免登录 Search Skills（详见 references/futu-api.md）

```bash
# 美股新闻搜索
curl -sG 'https://ai-news-search.futunn.com/news_search' \
  --data-urlencode 'keyword=AAPL' \
  --data-urlencode 'size=10' \
  --data-urlencode 'news_type=1' \
  --data-urlencode 'lang=en' \
  --data-urlencode 'sort_type=2'

# 港股新闻搜索
curl -sG 'https://ai-news-search.futunn.com/news_search' \
  --data-urlencode 'keyword=00700' \
  --data-urlencode 'size=10' \
  --data-urlencode 'news_type=1' \
  --data-urlencode 'lang=zh-CN' \
  --data-urlencode 'sort_type=2'
```

## 标准工作流（按市场）

### A股盘后复盘（8步）

1. **`curl` 东财指数接口** → SSE/SZSE/ChiNext/STAR/BSE 收盘
2. **`curl` ZTPool/DTPool/ZBPool** → 活跃度指标
3. **浏览器抓行业/概念板块榜** → 看主线/接力
4. **富途 `news_search` 搜索当日热点新闻** → 补充资讯定调
5. **Exa 搜 `startPublishedDate`** → 主流媒体定调
6. **套用 A股复盘模板** → 给出综合定性

### 美股盘后复盘（6步）

1. **Yahoo Finance 获取纳斯达克/标普 500 行情** → 大盘涨跌 + 成交量
2. **Yahoo Finance 获取 VIX、十年期国债收益率** → 市场风险偏好
3. **富途 `news_search` 搜索热门个股新闻** → 新闻定调
4. **富途 `stock_feed` 社区情绪** → 情绪温度
5. **Exa 搜索美股分析文章 + startPublishedDate** → 主流观点
6. **套用港美股复盘模板** → 给出综合定性

### 港股盘后复盘（6步）

1. **Yahoo Finance 获取恒指/国指/科指行情** → 大盘涨跌 + 成交量
2. **Yahoo Finance 获取个股行情**（0700.HK、99988.HK等） → 详细数据
3. **富途 `news_search` 搜索港股新闻**→ 资讯定调
4. **Exa 搜索港股市场 + startPublishedDate** → 主流观点
5. **浏览器抓取富途/东财港股板块页面** → 板块轮动
6. **套用港美股复盘模板** → 给出综合定性

## 情绪指标（按市场）

### A股（6 指标）

| 指标 | 来源 | 解读 |
|---|---|---|
| 涨跌停数 | ZTPool / DTPool `tc` | 涨停 >70 强势，<40 偏弱 |
| 炸板率 | 炸板 / (涨停+炸板) | >40% 赚钱效应差 |
| 最高连板 | ZTPool.pool[].zttj.days | ≥10 板有"妖股锚" |
| 封板时间分布 | ZTPool.pool[].fbt | 早盘扎堆=共振 |
| 涨停板块集中度 | ZTPool.pool[].hybk 计数 | 集中=主线明确 |
| 概念榜接力 | 概念板块 TOP10 | 进前 10 = 游资接力强 |

### 港美股（4 指标）

| 指标 | 来源 | 解读 |
|---|---|---|
| 大盘涨跌 + 成交量 | Yahoo Finance | 放量上涨=强势；缩量下跌=弱势 |
| 板块轮动 | 页面抓取 / 富途榜单 | 科技、金融、能源等板块轮动节奏 |
| 新闻/财报影响 | 富途 news_search | 利好密集度、政策影响 |
| 社区情绪 | 富途 stock_feed | 极端情绪往往是反转信号 |

## 关键坑位

### 通用坑位（全市场）

**Exa 搜索必带 `startPublishedDate`**
不带此参数会命中历史同期文章。英文搜索也一样。强制加 `"startPublishedDate":"YYYY-MM-DD"`。

**Jina Reader 国内财经站常超时**
`r.jina.ai/...` 对东财、雪球、富途等经常 15s timeout。财经数据直接走 API 或浏览器抓取。

### A股专属坑位

**东财板块 API 返空** → 用浏览器抓取 `gridlist.html`。
**股叭反爬严重** → 改用富途社区情绪 + Exa 搜索。
**涨跌停池 date 参数无效** → 只能当日使用。
**指数资金接口盘中裹 curl 返空** → 走浏览器 fetch。

### 港美股专属坑位

**Yahoo Finance API 反爬**
Yahoo 对频率有限制，过快请求会被封 IP。**4-5 秒间隔一次请求**。加 `User-Agent` 和 `Referer` 可降低封险概率。

**富途搜索代码格式**
A股用中文名，港股/美股用代码。富途以港美股为主，用 A股代码搜索可能命中港美同名标的。

**时区差异**
美股盘后复盘应在美股交易日结束后（东部时间 16:00 后，北京时间第二天 05:00 后）。港股盘后复盘在港股交易日结束后（北京时间 16:00 后）。跨市场分析时注意交易时间匹配。

## Limitations

- A股数据（东财）仅支持沪深京。港/美/日股不支持涨跌停池、连板梯队等 A股专属指标。
- Yahoo Finance API 免登录但有频率限制，过快会被封 IP。建议在脚本中加 sleep(4-5)。
- 富途免登录 Search Skills 主要覆盖港美股标的新闻，A股标的覆盖率因标的而异。
- 东财 API 是非官方公开接口，字段名可能调整。
- 真实交易日才有数据；周末/节假日返回前一交易日或空。
- 富途社区情绪仅反映平台内讨论，不代表全市场。
