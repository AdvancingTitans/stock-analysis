---
name: stock-analysis
description: "Use when the user asks for current or after-market A股、港股、美股 or global stock-market review, index/sector/sentiment analysis,涨跌停池,港美股重点个股, or asks to verify market data with low 429/token overhead."
version: 3.1.3
author: Hermes Agent + yjw
tags: [stock-market, a-shares, hk-shares, us-shares, eastmoney, futu, sentiment, global-finance, data-quality, camofox]
platforms: [linux, macos, windows]
---

# 全球股市行情与情绪分析

核心原则：**任何分析必须先拉数据，禁止裸眼定性**。优先让脚本采集和汇总，模型只做解释、归纳和风险提示，避免反复手工访问接口消耗额度。数据仅供参考，不构成投资建议。

## 快速使用

在技能目录运行：

```bash
python scripts/aftermarket.py --market global
python scripts/aftermarket.py --market a
python scripts/aftermarket.py --market hk
python scripts/aftermarket.py --market us
python scripts/aftermarket.py --market global --no-cache
```

- 默认使用缓存；只有用户要求刷新、数据明显过期或诊断提示缓存异常时才加 `--no-cache`。
- 用户问“今日全球行情”优先跑 `python scripts/aftermarket.py --market global`，再按需要补跑单市场。
- 输出已含诊断摘要和数据质量报告；回答时引用关键数字，不要把完整原始输出逐段复制给用户。

## 数据源优先级

| 市场 | 行情 | 新闻/情绪 | 板块 | 说明 |
|---|---|---|---|---|
| A股 | 东方财富 API | 富途 news_search | camofox 抓东财 | 支持 6 大指数、涨跌停池、炸板池、资金流 |
| 港股 | 东方财富 clist | 富途 news_search | camofox 抓富途/东财 | 不适用涨跌停、连板、炸板率 |
| 美股 | 东方财富 clist | 富途 news_search | camofox 抓 Yahoo/富途 | 道指/VIX 若缺失，用诊断说明 |

三层获取：**缓存 → 稳定 API → 腾讯行情备用 → 浏览器降级**。稳定 API 包括东方财富、东方财富 clist、富途；腾讯 `qt.gtimg.cn` 用于补齐东财 clist 缺失的港股/美股正股和港股指数；浏览器降级用于东财板块榜、富途页面以及 API 连续失败、403、429 场景。

## 分析要求

- A股最小集：6 大指数、涨跌停池、炸板池、主力资金流向、行业/概念板块；用涨停数、跌停数、炸板率、最高连板、封板时间、板块集中度判断情绪。
- 港美股最小集：大盘指数、重点个股、成交量/质量标记、富途新闻；重点看大盘涨跌、成交量变化、板块轮动、个股新闻，不套用 A股连板逻辑。
- Exa 或网页搜索只做舆情交叉验证，必须带当天 `startPublishedDate`；国内财经站优先 API 或 camofox，少用 Jina Reader。
- 如果接口失败，不静默定性；说明“数据缺口 + 已用替代源/诊断摘要”。

## 省额度规则

- 先跑脚本，再分析；同一市场同一轮不要重复请求相同 symbol。
- 不把脚本代码、完整表格或长新闻列表塞进最终回答；保留指数、涨跌幅、活跃方向、异常数据和结论。
- 缓存命中时不要强刷；需要刷新时一次性跑目标市场，不逐只股票手工请求。
- 不使用 Yahoo 作为默认备用源；国外接口易受地区网络和限流影响。
- 需要更多实现细节时再读取 `references/` 和脚本帮助，主技能正文保持轻量。

## 关键坑位

- 东方财富 `fltt=2` 的 A股指数价格已经是正常价格，不再除以 100；clist 港美股价格由脚本处理。
- 富途 `publish_time` 是字符串，脚本会先转整数。
- 指数成交量为 0 是 warning，不影响价格判断；个股成交量为 0 才影响质量评分。
- 仅对 429/403/5xx/timeout 重试；404 不重试，直接降级或诊断。
- 东财 clist 按榜单返回，可能漏掉港股/美股大盘股；此时用腾讯行情批量补齐。
