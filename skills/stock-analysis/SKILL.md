---
name: stock-analysis
description: "全球股市行情+情绪分析 v3.0：三层获取（缓存→稳定API→浏览器降级），A股（东财免登录API）、港美股（Yahoo v8 chart 逐个拉取+富途资讯）、板块榜浏览器抓取、数据质量验证与诊断摘要。"
version: 3.0.0
author: Hermes Agent + yjw
tags: [stock-market, a-shares, hk-shares, us-shares, eastmoney, futu, yahoo-finance, sentiment, global-finance, data-quality, camofox]
platforms: [linux, macos, windows]
---

# 全球股市行情与情绪分析

> ⚠️ **数据质量声明**
> - Yahoo Finance v8 chart API 对不同市场支持程度不同：美股最完整，港股/欧股/日股可能缺少成交量
> - 异常数据（成交量为0、价格异常）自动检测并标记，指数成交量缺失降级为 warning 而非 error
> - 脚本内置本地缓存层，同一轮分析内重复 symbol 只请求一次
> - 三层获取策略：缓存 → 稳定 API → 浏览器降级（camofox），减少 429/404 浪费
> - 数据仅供参考，不构成投资建议

支持 A股（沪深京）、港股、美股等主要市场的行情获取与情绪分析。A股使用东财免登录 API；港美股使用 Yahoo Finance v8 chart API 逐个 symbol 拉取（废弃 v6 批量接口），结合富途免登录资讯搜索。

开箱即用脚本：`scripts/aftermarket.py`

## 脚本用法

```bash
python aftermarket.py [--market a|hk|us|global] [YYYYMMDD]
```

- `--market a` （默认）: A股复盘
- `--market hk`: 港股复盘
- `--market us`: 美股复盘
- `--market global`: 全球市场概览（美股+港股+A股指数）

## When to Use

- 用户问"今天 A 股怎么样"、"复盘下今日行情"、"分析下大盘情绪"
- 用户问"美股今天怎么样"、"拿拿 AAPL/TSLA 行情"、"纳斯达克怎么样"
- 用户问"港股怎么样"、"腾讯/9633 怎么样"、"恒指怎么样"
- 需要拿涨跌停数、连板梯队、板块涨跌（A股）
- 需要查某只标的最新新闻、公告、研报
- 需要全球市场概览（美股+港股+A股指数对比）
- 任何涉及上证/深证/创业板/科创板/北证/恒指/国指/科指/纳指/标普 500 的查询

## 三层获取策略

```
┌─────────────────────────────────────────┐
│  第一层：本地缓存（~/.cache/stock-analysis/） │
│  按 {source,symbol,date} 缓存，TTL 当日有效    │
├─────────────────────────────────────────┤
│  第二层：稳定 API                         │
│  - 东财：指数、涨跌停池、资金流向           │
│  - Yahoo v8 chart：逐个 symbol 行情        │
│  - 富途：news_search / stock_feed          │
│  请求间隔 3 秒，仅对 429/5xx/timeout 重试   │
├─────────────────────────────────────────┤
│  第三层：浏览器降级（camofox）              │
│  - 东财板块榜（行业/概念）                  │
│  - API 连续失败/403/429 时自动走页面抓取     │
└─────────────────────────────────────────┘
```

## 市场分类与数据源

| 市场 | 行情数据 | 新闻/情绪 | 板块/概念 | 复盘文章 |
|---|---|---|---|---|
| **A股** | 东财 API | 富途 news_search | 东财页面抓取 | Exa 搜"当日复盘" |
| **港股** | Yahoo v8 chart | 富途 news_search | 富途/东财页面 | Exa 搜"港股 行情" |
| **美股** | Yahoo v8 chart | 富途 news_search | Yahoo/富途页面 | Exa 搜"美股市场" |

## 核心数据源

### 稳定 API 层

1. **东方财富免登录 API** — A股指数、涨跌停池、资金流向。首选。
2. **Yahoo Finance v8 chart** — 全球行情。逐个 symbol 拉取，带缓存和限速。
3. **富途免登录 Search** — 新闻/公告/研报搜索。对港美股代码支持极好。

### 浏览器降级层

4. **camofox** — 东财板块榜（行业/概念）、富途/Yahoo 页面数据。绕开反爬。
   - 环境变量：`CAMOFOX_URL=http://localhost:9377`、`CAMOFOX_USER_ID`、`CAMOFOX_SESSION_KEY`

### 辅助

5. **Exa 搜索**（带 `startPublishedDate`）— 交叉验证舆情。

## 富途搜索市场区分

| 市场 | 代码格式 | 建议 keyword |
|---|---|---|
| **A股** | 000001、603017 | 中文公司全称（如"比亚迪"） |
| **港股** | 00700、99988 | 代码或中文名 |
| **美股** | AAPL、TSLA | 代码 |
| **中概股** | BABA、PDD | 代码 |

**港股代码**：富途用 `0700`（去前导0）或 `00700`。Yahoo 必须用 `0700.HK`。

## 数据拉取规范

**任何分析必须先拉数据，禁止裸眼定性。**接口失败时输出诊断摘要，不静默消失。

### A股最小数据集

| 必拉项 | 接口 | 备注 |
|---|---|---|
| 6 大指数 | `push2.eastmoney.com` ulist | fltt=2 已返回正常价格，不再缩放 |
| 涨跌停池 | `push2ex.eastmoney.com` ZT/DTPool | curl 稳定 |
| 炸板池 | `push2ex.eastmoney.com` ZBPool | 同上 |
| 主力资金流向 | `push2.eastmoney.com` fflow | 同上 |
| 行业/概念板块榜 | camofox 抓取 | API 裸 curl 被拦 |
| 当日复盘文章 | Exa | 必带 `startPublishedDate` |

### 港美股最小数据集

| 必拉项 | 接口 | 备注 |
|---|---|---|
| 实时行情 | Yahoo v8 chart | 逐个拉取，带缓存 |
| 当日新闻 | 富途 news_search | 精准度高 |
| 社区情绪 | 富途 stock_feed | 精准度高 |
| 市场舆情 | Exa 搜索 | 英文覆盖更好 |

**港美股特殊处理**：无涨跌停制度，不适用"连板梯队"、"炸板率"。重点看大盘指数涨跌、成交量变化、板块轮动、个股新闻。

## Yahoo Finance v8 chart 速查

```bash
# 单股行情（支持美股、港股、日股）
curl -s "https://query1.finance.yahoo.com/v8/finance/chart/AAPL?interval=1d&range=5d"
curl -s "https://query1.finance.yahoo.com/v8/finance/chart/0700.HK?interval=1d&range=5d"

# 港股指数（HSTECH.HK 优先于 ^HSTECH）
curl -s "https://query1.finance.yahoo.com/v8/finance/chart/HSTECH.HK?interval=1d&range=5d"
```

> ⚠️ v6/finance/quote 批量接口已废弃，返回 404。v3.0 已全面改用 v8 chart 逐个拉取。

## 富途免登录 Search

```bash
# 美股新闻
curl -sG 'https://ai-news-search.futunn.com/news_search' \
  --data-urlencode 'keyword=AAPL' --data-urlencode 'size=10' \
  --data-urlencode 'news_type=1' --data-urlencode 'lang=en' \
  --data-urlencode 'sort_type=2'

# 港股新闻
curl -sG 'https://ai-news-search.futunn.com/news_search' \
  --data-urlencode 'keyword=00700' --data-urlencode 'size=10' \
  --data-urlencode 'news_type=1' --data-urlencode 'lang=zh-CN' \
  --data-urlencode 'sort_type=2'
```

## 标准工作流

### A股盘后复盘（6步）

1. 东财指数接口 → SSE/SZSE/ChiNext/STAR/BSE 收盘
2. ZTPool/DTPool/ZBPool → 活跃度指标
3. camofox 抓行业/概念板块榜 → 看主线/接力
4. 富途 news_search 搜索热点新闻 → 补充资讯
5. Exa 搜 `startPublishedDate` → 主流媒体定调
6. 套用复盘模板 → 综合定性

### 美股盘后复盘（5步）

1. Yahoo v8 chart 获取标普/纳指/道指/VIX → 大盘
2. 富途 news_search 热门个股新闻 → 新闻定调
3. 富途 stock_feed 社区情绪 → 情绪温度
4. Exa 搜索美股分析文章 → 主流观点
5. 套用复盘模板 → 综合定性

### 港股盘后复盘（5步）

1. Yahoo v8 chart 获取恒指/国指/科指 → 大盘
2. Yahoo v8 chart 获取个股行情 → 详细数据
3. 富途 news_search 港股新闻 → 资讯定调
4. Exa 搜索港股市场 → 主流观点
5. 套用复盘模板 → 综合定性

## 数据质量验证（v3.0.0）

### 统一数据结构

所有数据源返回统一的 `QuoteData`：
```
symbol, name, market, date, price, prev_close, change, change_pct,
open_price, high, low, volume, currency, source, quality_flags, notes, completeness
```

### 涨跌幅计算

**不再依赖 Yahoo meta 的 `previousClose`**。从 K 线取最后两个有效 close 计算：
- 若 K 线不足，fallback 到 `chartPreviousClose`
- 若仍不足，标记为缺失

### 自动数据清洗

| 检测项 | 规则 | 处理方式 |
|---|---|---|
| 价格异常 | `<= 0` | 置为 `None` |
| 指数成交量为0 | 恒指/国指/VIX 等 | 降级为 warning，不影响价格判断 |
| 个股成交量为0 | `<= 0` | 标记 `volume_zero` |
| 成交量偏低 | 指数<1M，个股<1K | 标记 `volume_anomaly` |
| 完整性评分 | 必填字段 + 昨收 + 涨跌幅 | 0-100% |

### 重试策略

- 请求间隔：**3 秒**（默认）
- 仅对 **429/403/5xx/timeout** 重试，最多 2 次
- **404 不重试**，直接标记失败
- 指数退避：`delay × 2^attempt × random(0.5~1.5)`

### 诊断摘要

脚本输出末尾自动附上：
- 接口诊断（哪些 API 失败了，失败原因）
- 平均完整度百分比
- 异常数据警告列表
- 改进建议

## 情绪指标

### A股（6 指标）

| 指标 | 来源 | 解读 |
|---|---|---|
| 涨跌停数 | ZTPool/DTPool `tc` | 涨停>70 强势，<40 偏弱 |
| 炸板率 | 炸板/(涨停+炸板) | >40% 赚钱效应差 |
| 最高连板 | ZTPool.pool[].zttj.days | ≥10 板有"妖股锚" |
| 封板时间分布 | ZTPool.pool[].fbt | 早盘扎堆=共振 |
| 涨停板块集中度 | ZTPool.pool[].hybk 计数 | 集中=主线明确 |
| 概念榜接力 | 概念板块 TOP10 | 进前10=游资接力强 |

### 港美股（4 指标）

| 指标 | 来源 | 解读 |
|---|---|---|
| 大盘涨跌+成交量 | Yahoo v8 chart | 放量上涨=强势 |
| 板块轮动 | 页面抓取/富途榜单 | 轮动节奏 |
| 新闻/财报影响 | 富途 news_search | 利好密集度 |
| 社区情绪 | 富途 stock_feed | 极端情绪常是反转信号 |

## 关键坑位

### 通用

**Exa 搜索必带 `startPublishedDate`** — 否则命中历史同期文章。

**Jina Reader 国内财经站常超时** — 东财/雪球/富途直接走 API 或 camofox。

### A股

**东财板块 API 返空** → 用 camofox 抓 `gridlist.html`。
**涨跌停池 date 参数** → 只能传当日。
**东财 fltt=2 价格** → 已返回正常价格（如上证 4093.73），**不再除以 100**。

### 港美股

**Yahoo v8 chart 限速** → 3 秒间隔，带缓存避免重复请求。
**HSTECH symbol** → 用 `HSTECH.HK`，`^HSTECH` 返回 404。
**富途 publish_time** → 字符串格式（如 "1779888173"），需先 `int()` 转换。
**时区差异** → 美股盘后复盘应在北京时间第二天 05:00 后；港股 16:00 后。

## 数据源配置与降级

| 市场 | 行情数据 | 新闻/情绪 | 板块 | 降级方案 |
|---|---|---|---|---|
| **A股** | 东财 API (主) | 富途 news_search | camofox 东财页面 | Yahoo Finance |
| **港股** | Yahoo v8 chart (主) | 富途 news_search | camofox 富途/东财 | 东财 API |
| **美股** | Yahoo v8 chart (主) | 富途 news_search | camofox Yahoo/富途 | 无 |

### 市场类型自动检测

| 检测规则 | 结果 |
|---|---|
| `.HK` 后缀、`HSI`/`HSCE`/`HSTECH` | hk_market |
| `上证`、`深证`、`创业板`、`科创板` | cn_market |
| `DAX`、`CAC`、`FTSE` | eu_market |
| `Nikkei`、`.T` 后缀 | jp_market |
| 其他 | us_market (默认) |

## Limitations

- A股数据（东财）仅支持沪深京。港/美股不支持涨跌停池等 A股专属指标。
- Yahoo Finance v8 chart 免登录但有频率限制，脚本已内置 3 秒间隔 + 缓存缓解。
- 富途免登录 Search 主要覆盖港美股标的新闻，A股标的覆盖率因标的而异。
- 东财 API 是非官方公开接口，字段名可能调整。
- 真实交易日才有数据；周末/节假日返回前一交易日或空。
- 港股/欧股/日股成交量（Yahoo）可能不完整，部分指数返回 0，已做异常检测。
