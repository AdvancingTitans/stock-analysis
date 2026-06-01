---
name: stock-analysis
description: "Use when the user asks for current or after-market A股、港股、美股 or global stock-market review, single-stock/fund lookup/news, index/sector/sentiment analysis,涨跌停池,港美股重点个股, or asks to verify market data with low 429/token overhead. v3.5.1 uses Tonghuashun, Tencent, Sina, Futu, Tiantian Fund, and Eastmoney no-login quote/news/fund sources with dated staged output and same-day news-heat ranking."
version: 3.5.1
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
python scripts/aftermarket.py --market a --no-news
python scripts/aftermarket.py --market news --stock 3690.HK
python scripts/aftermarket.py --market fund --fund 161725
python scripts/aftermarket.py --market global --no-cache
```

- 默认使用缓存；只有用户要求刷新、数据明显过期或诊断提示缓存异常时才加 `--no-cache`。
- 用户问“今日全球行情”优先跑 `python scripts/aftermarket.py --market global`，再按需要补跑单市场。
- 输出已含来源提示、口径说明、日期+阶段和数据质量报告；回答时引用关键数字，不要把完整原始输出逐段复制给用户。

## 缓存防污染硬约束

v3.1.1 引入的缓存防污染机制必须保留，后续迭代不得弱化：

- 行情缓存 TTL 固定为 **5 分钟（300 秒）**，盘中实时数据过期后必须重新拉取，不能长期复用旧快照。
- 缓存路径必须按交易日隔离：`~/.cache/stock-analysis/YYYYMMDD/`；缓存 key 至少包含数据源、symbol 和日期，避免早盘未更新时把昨日数据污染到今日。
- 脚本必须继续支持 `--no-cache` 和 `--refresh`，用于用户要求刷新、早盘/午间疑似旧数据、接口诊断异常等场景。
- 缓存读取必须校验文件修改时间；超过 TTL 直接视为 miss，不应返回 stale data。
- 标题或阶段字段必须根据当前时间自动标注 `上午盘` / `午间` / `下午盘` / `盘后`，且阶段字段带数据日期，例如 `2026-06-01 下午盘`；若返回数据日期与请求日期不一致，展示返回交易日的阶段，不把请求日伪装成数据日。
- 如果未来调整缓存策略，必须同时更新 `scripts/aftermarket.py`、本文件和 README 更新日志，并明确说明如何防止缓存污染。
## 数据源优先级

| 市场 | 行情 | 新闻/情绪 | 板块 | 说明 |
|---|---|---|---|---|
| A股 | 东方财富 API + 新浪/腾讯指数兜底 | 富途 news_search + 新浪滚动新闻 + 东方财富快讯 | camofox 抓东财 | 支持 6 大指数、涨跌停池、炸板池；资金流优先用同花顺概念资金流，命中失败再降级 |
| 港股 | 腾讯指数口径 + 新浪个股 + 东财 stock/get/clist | 富途 news/feed + 新浪滚动新闻 + 东方财富快讯，按新闻热度排 Top5 | camofox 抓富途/东财 | 不适用涨跌停、连板、炸板率 |
| 美股 | 新浪财经主路径 + 腾讯指数 + 东财 stock/get/clist | 富途 news/feed + 新浪滚动新闻 + 东方财富快讯，按新闻热度排 Top5 | camofox 抓富途/财经页面 | DJI 已覆盖；VIX 若缺失，用诊断说明 |

三层获取：**缓存 → 稳定 API → 浏览器降级**。稳定 API 包括同花顺概念资金流页面、东方财富 A股接口、东财 `fflow` 最新 A股资金流、东财资金流页面指标、新浪资金流页面行业流向、腾讯港股指数收盘口径、港美股新浪财经批量行情、腾讯美股指数补充、东财 `stock/get` 单只精确兜底、东财 clist 批量补充、天天基金实时估值/持仓、富途资讯、新浪滚动新闻、东方财富快讯；浏览器降级用于东财板块榜、富途页面以及 API 连续失败、403、429 场景。

单只股票速览：脚本支持 `python scripts/aftermarket.py --market stock --stock 600519`，也支持港股 `0700.HK` 和 best-effort 美股 `AAPL`；若用户只想看消息面，使用 `python scripts/aftermarket.py --market news --stock 3690.HK`。单票输出必须标注市场、来源、数据交易日、最新价、涨跌、成交量/额和完整度；若数据源交易日与请求日不一致，必须明确提醒，不把旧数据当成当天数据。新闻逐条显示来源和链接状态，且只展示请求交易日当天发布的有效新闻，热度基于所有来源综合命中数和新鲜度，最多 Top5，不足 5 条按实际数量展示，没有则明确提示暂未获取到有效新闻信息。`--market a`、`--market hk`、`--market us`、`--market stock` 都支持 `--no-news`，用户只想看行情时不要输出新闻链接。

基金持仓速览：脚本支持 `python scripts/aftermarket.py --market fund --fund 161725` 或 `--market fund --stock 161725`。输出基金当日估算涨跌幅、上一净值日期、前十大 A股持仓行情、重仓贡献粗算和持仓股当天新闻；正式基金净值通常晚间更新，估算值必须明确标注为“天天基金盘中/收盘估算”，不能写成已确认收益率。`--no-news` 可跳过持仓股新闻。

## 分析要求

- A股最小集：6 大指数、涨跌停池、炸板池、行业/概念板块；主力资金流向展示最新可用记录并标注来源交易日，用涨停数、跌停数、炸板率、最高连板、封板时间、板块集中度判断情绪。
- 港美股最小集：大盘指数、重点个股、成交量/质量标记、多源当天新闻；重点看大盘涨跌、成交量变化、板块轮动、个股新闻，不套用 A股连板逻辑。
- 单只股票最小集：当前价、涨跌幅、昨收、开高低、成交量/额、来源、数据交易日、当天相关新闻；拿不到可核验价格时只提示缺口和建议重试，不输出空表或猜测。
- 基金最小集：基金名称/代码、上一净值日期和净值、当日估算净值/涨跌幅、估算时间、持仓截止日、前十大持仓股当日行情、按公开持仓权重粗算的贡献，以及前五大持仓股当天新闻 Top5。
- Exa 或网页搜索只做舆情交叉验证，必须带当天 `startPublishedDate`；国内财经站优先 API 或 camofox，少用 Jina Reader。
- 如果接口失败，不静默定性；说明“数据缺口 + 已用替代源/诊断摘要”。

## 省额度规则

- 先跑脚本，再分析；同一市场同一轮不要重复请求相同 symbol。
- 不把脚本代码、完整表格或长新闻列表塞进最终回答；保留指数、涨跌幅、活跃方向、异常数据和结论。
- 缓存命中时不要强刷；需要刷新时一次性跑目标市场，不逐只股票手工请求。
- 不使用境外行情接口作为默认备用源；这类接口易受地区网络和限流影响。港美股优先用腾讯/新浪/东财这些免登录国内可访问源。
- 需要更多实现细节时再读取 `references/` 和脚本帮助，主技能正文保持轻量。

## 关键坑位

- 东方财富 `fltt=2` 的 A股指数和 clist 港美股价格当前均按真实价处理，不再除以 100。
- A股资金流采用东财 `fflow` 最新上证指数口径数据；如果来源交易日与请求日不一致，仍展示数值并明确标注两个日期；实时接口临时不可用时，先尝试在线资金流页面指标接口，在线源都不可用时才展示本地最近一次可信缓存并明确标注缓存兜底。`push2his` 历史资金流当前不视为稳定兜底。
- A股资金流优先尝试同花顺概念资金流页面；该源只代表概念板块净额，必须标注“不等同于全市场主力资金净流入”。如果同花顺触发风控或不可用，再尝试东财实时资金流、东财资金流页面实时指标、新浪资金流页面行业流向、 新浪/腾讯 A股指数活跃度指标，最后才使用本地最近一次可信资金流缓存。
- 同花顺 `data.10jqka.com.cn/funds/gnzjl/` 当前适合 `young flow` 的概念板块资金流，不适合替代 A股指数、个股、港美股行情主路径；其他行情仍以新浪/腾讯/东财为主，避免降低行情覆盖和准确性。
- 每次运行都要标注日期+阶段：上午盘、午间、下午盘、盘后；如果返回数据日期与请求日期不一致，注明展示的是返回交易日数据，并在阶段字段中使用返回数据日期。
- 新闻只采用稳定免登录源。当前默认使用富途、新浪财经、东方财富快讯；雪球/同花顺若没有稳定免登录接口，不作为默认硬依赖。A股、港美股重点个股、基金持仓股和单票新闻都只展示请求交易日当天发布的有效内容，按多源新闻热度 Top5 展示；展示时尽量保留多来源，不让单一来源自动挤掉其他有效来源。新闻链接会剔除明显 404/无内容页面，网络临时校验失败时不误杀。
- 默认不要输出“数据源切换记录”等调试信息；只有设置 `YOUNG_STOCK_DEBUG=1` 时才展示接口诊断。
- 富途 `publish_time` 是字符串，脚本会先转整数。
- 指数成交量为 0 是 warning，不影响价格判断；个股成交量为 0 才影响质量评分。
- 仅对 429/403/5xx/timeout 重试；404 不重试，直接降级或诊断。
- 港股指数优先腾讯 `qt.gtimg.cn` 收盘口径；新浪 `hkHSI` 可作实时快照补充，二者盘后点位可能略有差异，回答时说明口径。
- 港美股新浪财经缺失时用东财 `stock/get` 单只兜底；clist 只作为批量补充，避免榜单分页漏掉大盘股。
