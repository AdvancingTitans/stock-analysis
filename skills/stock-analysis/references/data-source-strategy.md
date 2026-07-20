# 数据源策略

## 行情路由

| 市场/能力 | 首选 | 第二层 | 第三层 | 浏览器 |
|---|---|---|---|---|
| A股报价/估值 | 腾讯 | 新浪 | 东财 `stock/get` | 页面接管 |
| A股基础 K | 腾讯 | 新浪可用数据 | 东财历史接口 | 页面接管 |
| A股五档/逐笔/深度 K | mootdx（按需） | 腾讯基础行情 | 新浪基础行情 | 不适用 |
| A股独有信号 | 东财限流接口 | 无同等 API | Camofox | Hermes/Playwright |
| A股单股财务 | 东财 datacenter 财务摘要/三表 | 业绩预告/快报仅披露时可用 | 保留缺口 | 不用页面猜测 |
| 行业/概念板块榜 | 东财 `clist` | 同花顺公开板块页 | Camofox | Hermes/Playwright |
| 港股行情 | 腾讯 | 新浪 | 东财 `stock/get` | 页面接管 |
| 美股行情 | 新浪 | 腾讯 | 东财 searchapi + `stock/get` | 页面接管 |
| 港股历史 K/量价 | Yahoo chart | 腾讯 `fqkline` | 东财可用数据 | - |
| 美股历史 K/量价 | Yahoo chart | 新浪日 K | 东财可用数据 | - |
| 港股财务 | Yahoo fundamentals（conditional） | HKEXnews/公司 IR 原文 | `primary-evidence-reach` | 宿主 Agent |
| 美股财务 | SEC Company Facts（primary XBRL） | 公司 IR/EDGAR 原文 | `primary-evidence-reach` | 宿主 Agent |
| 日股行情/历史 K | Yahoo chart `.T` | 最近成功缓存（仅故障恢复） | 保留单源缺口 | - |
| 韩股行情/历史 K | Naver `.KS` / `.KQ` | Yahoo 逐字段交叉验证 | 最近成功缓存 | - |
| 日韩财务摘要 | Naver/Yahoo 聚合数据（conditional） | issuer/JPX/TDnet/DART/KIND 原文 | `primary-evidence-reach` | 宿主 Agent |
| 基金画像 | 天天基金 `pingzhongdata` 公开 JS | 东财基金估值/持仓 | 新浪基金 | 页面接管 |

Yahoo 不进入 A股报价推荐路径；港美股仅用其日线计算 20 日平均本币成交额、60 日波动率和组合相关性，港股财务保持 conditional。Yahoo/Naver 聚合财务缺少公告日期时不得升级为历史 as-of 一手事实。美股 SEC Company Facts 必须用 `filed` 日期做截止，实体级标准 XBRL 不能冒充分部披露。

## 日韩边界

- 日本必须使用 `.T`，韩国必须使用 `.KS` / `.KQ`；裸 4 位/6 位数字不猜测日韩市场。
- 日股 Yahoo 是已验证的单一免登录日线源；缓存不算独立来源，失败时保留 `single_source` 缺口。
- 韩股 Naver 与 Yahoo 对共同交易日的 OHLCV 逐字段核对；冲突写入 `cross_source_conflict`。
- XTKS/XKRX 日历为版本化快照，范围外不得用周一至周五猜测。
- `primary-evidence-reach` 随 Codex Skills 安装；已有 Agent Reach 时使用其路由，否则使用宿主搜索/浏览器/PDF 能力。只有公司、交易所或监管机构原文可以导入 `--primary-evidence-file`。

## 腾讯字段

腾讯 `~` 分隔字段以当前适配器实测索引为准：

| 索引 | 字段 |
|---:|---|
| 1 | 名称 |
| 2 | 代码 |
| 3 | 当前价 |
| 4 | 昨收 |
| 5 | 今开 |
| 31 | 涨跌额 |
| 32 | 涨跌幅 |
| 37 | 成交额，单位按市场解析 |
| 38 | 换手率 |
| 39 | PE |
| 44 | 总市值 |
| 45 | 流通市值，部分市场为空 |
| 46 | PB |

不得只按一张网上流传的固定表跨市场套用。字段不足或空字符串统一写 `None`。

## 编码

腾讯和新浪优先按 `gb2312` 解码；遇到生僻字时允许严格回退 `gbk`。禁止使用自动检测或 `errors="replace"`。

## 东财限流

- 统一 `em_get()`
- `Session.trust_env = False`
- 串行、间隔至少 1 秒、随机抖动
- 最多 3 次指数退避
- 空响应和 HTTP 000 视为失败，不转换为零

## 板块榜 fallback

- M2 行业/概念榜首选东财 `clist`，但该端点在部分网络会空响应或直接断连。
- 东财失败时，当前交易日改用同花顺公开行业页与概念资金页解析 HTML 表格；历史日期仍禁止混用实时板块数据。
- 只有拿到非空 `rows` 才写缓存，避免一次空响应污染后续报告。
- 浏览器链路只在公开 HTTP fallback 仍不可用时启用。

## 港美股 secid

- 港美股东财 `stock/get` fallback 先用 searchapi `type=14` 解析 `MktNum`：`105/106/107` 为美股，`116` 为港股。
- 静态大票映射仍保留；searchapi 用于补足 BABA、五位港股代码和未内置标的。

## 基金画像

- `https://fund.eastmoney.com/pingzhongdata/{code}.js` 免登录、无需 API key，可补充长期业绩、前端费率（前端申购费）、规模、业绩评价和现任基金经理画像。
- 若字段缺失，只保留空单元格，不用同类均值或其他基金数据猜测。
- 参考 `taxueseek/fund-investment-guide` 的基金三关框架时，只采纳公开免登录字段；其 `mkapi2` + `EASTMONEY_APIKEY` 路径不作为本技能默认数据源。

## A股财务快照

- 默认只对 A股个股/持仓调用东财 datacenter：`RPT_LICO_FN_CPD` 财务摘要、`RPT_DMSK_FN_BALANCE` 资产负债表、`RPT_DMSK_FN_CASHFLOW` 现金流量表。
- 可得证据包括 ROE、毛利率、EPS、BPS、营收、归母净利润、资产负债率、总资产、总负债、经营现金流和自由现金流-lite。
- 自由现金流-lite 口径为 `NETCASH_OPERATE - CONSTRUCT_LONG_ASSET`，只是公开现金流代理，不等同于完整企业自由现金流模型。
- `RPT_PUBLIC_OP_NEWPREDICT` 业绩预告与 `RPT_PUBLIC_OP_NEWDISCOVER` 业绩快报只在上市公司披露时有行；空返回必须保留缺口，不得写成“已获取预告/快报”。

## 浏览器边界

1. Camofox REST 健康检测，超时 3 秒。
2. Camofox 有凭据时由 CLI 自动抓板块页面。
3. Hermes browser 属于 Agent 工具，由执行 skill 的 Agent 接管。
4. 本地 Playwright 可作为末级自动化环境。
5. 全部不可用时记录 `数据源不可用`。
