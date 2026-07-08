# 东方财富免登录 API 速查

本文件是东财独有接口速查，不代表默认行情路由。实际优先级以
`data-source-strategy.md` 为准，所有请求必须通过 `em_get()` 限流封装。

> `fltt=2` 返回带小数的真实价格，禁止再次除以 100。东财存在网络风控，不能视为“不限流”。

---

## 1. 指数行情（`ulist.np`）

```bash
curl -s "https://push2.eastmoney.com/api/qt/ulist.np/get?fltt=2&secids=1.000001,0.399001,0.399006,1.000688,0.399005,0.899050&fields=f2,f3,f4,f5,f6,f12,f14,f15,f16,f17,f18&_=$(date +%s)000"
```

**secids 前缀含义**
| 前缀 | 市场 |
|---|---|
| `1.` | 上海 |
| `0.` | 深圳 |
| `0.899` | 北交所 |

**常用指数代码**
| 代码 | 名称 |
|---|---|
| `1.000001` | 上证指数 |
| `0.399001` | 深证成指 |
| `0.399006` | 创业板指 |
| `1.000688` | 科创50 |
| `0.399005` | 中小板指 |
| `0.899050` | 北证50 |

**字段映射（fields）**
| 字段 | 含义 | 备注 |
|---|---|---|
| `f2` | 最新价 | `fltt=2` 时为真实价 |
| `f3` | 涨跌幅 | `fltt=2` 时为真实百分比 |
| `f4` | 涨跌额 | `fltt=2` 时为真实值 |
| `f5` | 成交量 | 手 |
| `f6` | 成交额 | 元 |
| `f12` | 代码 | 如 `000001` |
| `f14` | 名称 | 如 `上证指数` |
| `f15` | 最高价 | `fltt=2` 时为真实价 |
| `f16` | 最低价 | `fltt=2` 时为真实价 |
| `f17` | 开盘价 | `fltt=2` 时为真实价 |
| `f18` | 昨收 | `fltt=2` 时为真实价 |
| `f20` | 总市值 | 元 |
| `f21` | 流通市值 | 元 |

> `fltt=2` 表示价格类字段放大了 100 倍返回整数，避免浮点。要真实值需除以 100。

---

## 2. 美股/港股/指数批量行情（`clist/get` 新）

```bash
# 美股个股
curl -s "https://push2.eastmoney.com/api/qt/clist/get?pn=1&pz=20&fid=f3&fs=m:105,m:106,m:107&fields=f12,f14,f2,f3,f4,f5,f6,f15,f16,f17,f18&fltt=2&_=$(date +%s)000"

# 美股指数（标普 500、纳斯达克）
curl -s "https://push2.eastmoney.com/api/qt/clist/get?pn=1&pz=10&fid=f3&fs=i:100.SPX,i:100.NDX&fields=f12,f14,f2,f3,f4,f5,f6,f15,f16,f17,f18&fltt=2&_=$(date +%s)000"

# 港股个股
curl -s "https://push2.eastmoney.com/api/qt/clist/get?pn=1&pz=20&fid=f3&fs=m:128&fields=f12,f14,f2,f3,f4,f5,f6,f15,f16,f17,f18&fltt=2&_=$(date +%s)000"

# 港股指数（恒指、国企、科指）
curl -s "https://push2.eastmoney.com/api/qt/clist/get?pn=1&pz=10&fid=f3&fs=i:100.HSI,i:100.HSCE,i:100.HSTECH&fields=f12,f14,f2,f3,f4,f5,f6,f15,f16,f17,f18&fltt=2&_=$(date +%s)000"
```

**市场筛选器（fs）**
| 市场 | fs 值 | 说明 |
|---|---|---|
| 美股个股 | `m:105,m:106,m:107` | 纽交所、纳斯达克、美股 OTC |
| 美股指数 | `i:100.SPX,i:100.NDX` | 标普 500、纳斯达克 |
| 港股个股 | `m:128` | 港股全市场 |
| 港股指数 | `i:100.HSI,i:100.HSCE,i:100.HSTECH` | 恒指、国企、科指 |

**返回格式**
```json
{
  "rc": 0,
  "data": {
    "total": 200,
    "diff": {
      "0": {"f12": "AAPL", "f14": "苹果", "f2": 31082, "f3": 105, ...},
      "1": {"f12": "TSLA", "f14": "特斯拉", "f2": 42550, "f3": -230, ...}
    }
  }
}
```

> 注意：`diff` 在 clist 中通常是 **对象**（键为 "0", "1"...），而非数组。解析时需兼容两种格式。

> 美股道指 DJI 和 VIX 东财暂不支持，需其他方案补充。

---

## 3. 涨跌停池（`push2ex.eastmoney.com`）

### 涨停池
```bash
curl -s "https://push2ex.eastmoney.com/getTopicZTPool?ut=7eea3edcaed734bea9cbfc24409ed989&dpt=wz.ztzt&Pageindex=0&pagesize=200&sort=fbt:asc&date=YYYYMMDD"
```

### 跌停池
```bash
curl -s "https://push2ex.eastmoney.com/getTopicDTPool?ut=7eea3edcaed734bea9cbfc24409ed989&dpt=wz.ztzt&Pageindex=0&pagesize=200&sort=fbt:asc&date=YYYYMMDD"
```

### 炸板池
```bash
curl -s "https://push2ex.eastmoney.com/getTopicZBPool?ut=7eea3edcaed734bea9cbfc24409ed989&dpt=wz.ztzt&Pageindex=0&pagesize=200&sort=fbt:asc&date=YYYYMMDD"
```

**公共参数说明**
| 参数 | 说明 |
|---|---|
| `date` | **必须**，格式 `YYYYMMDD`，如 `20260526`。非交易日可能返空 pool |
| `pagesize` | 最大 200 |
| `sort=fbt:asc` | 按封板时间从早到晚排 |

---

## 3b. A股单股财务快照（`datacenter-web`）

统一入口：

```text
https://datacenter-web.eastmoney.com/api/data/v1/get
```

公共参数：`reportName`、`columns=ALL`、`filter=(SECURITY_CODE="600519")`、`pageSize`、`pageNumber`、`sortColumns`、`sortTypes=-1`、`source=WEB`、`client=WEB`。

| reportName | 用途 | 关键字段 |
|---|---|---|
| `RPT_LICO_FN_CPD` | 财务摘要 | `QDATE`、`REPORTDATE`、`NOTICE_DATE`、`WEIGHTAVG_ROE`、`XSMLL`、`BASIC_EPS`、`BPS`、`TOTAL_OPERATE_INCOME`、`PARENT_NETPROFIT` |
| `RPT_DMSK_FN_BALANCE` | 资产负债表 | `REPORT_DATE`、`DEBT_ASSET_RATIO`、`TOTAL_ASSETS`、`TOTAL_LIABILITIES` |
| `RPT_DMSK_FN_CASHFLOW` | 现金流量表 | `REPORT_DATE`、`NETCASH_OPERATE`、`CONSTRUCT_LONG_ASSET`、`NETCASH_INVEST`、`NETCASH_FINANCE` |
| `RPT_PUBLIC_OP_NEWPREDICT` | 业绩预告 | 只在公司披露时返回行 |
| `RPT_PUBLIC_OP_NEWDISCOVER` | 业绩快报 | 只在公司披露时返回行 |

使用纪律：

- 财务摘要、资产负债表和现金流量表按报告期合并；合不上的字段保留空值。
- 自由现金流-lite = `NETCASH_OPERATE - CONSTRUCT_LONG_ASSET`，只能作为公开现金流代理。
- 业绩预告/快报空返回不能解释为“公司没有变化”，只能写“未取得已披露记录”。

**返回结构**
```json
{
  "data": {
    "tc": 65,           // 总条数（涨停/跌停/炸板总数）
    "pool": [
      {
        "c": "603017",       // 股票代码
        "n": "中衡设计",     // 股票名称
        "p": 1250,           // 最新价（÷100）
        "zdp": 10.01,        // 涨跌幅 %
        "zttj": {
          "days": 5,         // 连板天数
          "ct": 2            // 涨停次数（含今日）
        },
        "fbt": 92500,        // 首次封板时间（HHMMSS，如 92500=09:25:00）
        "lbt": 145600,       // 最后封板时间
        "fund": 123456789,   // 封单金额（元）
        "hybk": "建筑装饰",  // 所属行业
        "zbc": 0,            // 炸板次数（炸板池里会有值）
        "ltsz": 3500000000   // 流通市值（元）
      }
    ]
  }
}
```

**关键字段速查**
| 字段 | 含义 |
|---|---|
| `tc` | 总数（top count） |
| `c` | 代码 |
| `n` | 名称 |
| `p` | 最新价（÷100） |
| `zdp` | 涨跌幅 |
| `zttj.days` | 连板天数 |
| `zttj.ct` | 涨停次数 |
| `fbt` | 首次封板时间 |
| `lbt` | 最后封板时间 |
| `fund` | 封单金额 |
| `hybk` | 所属行业板块 |
| `zbc` | 炸板次数 |
| `ltsz` | 流通市值 |

---

## 4. 最新 A股资金流向（`fflow/kline`）

```bash
curl -s "https://push2.eastmoney.com/api/qt/stock/fflow/kline/get?secid=1.000001&fields1=f1,f2,f3,f7&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64,f65&klt=101&lmt=1&_=$(date +%s)000"
```

**secid 格式**
- 上证指数：`1.000001`
- 深证成指：`0.399001`

**fields2 字段（CSV 顺序）**
```
f51 日期
f52 主力净流入
f53 小单净流入
f54 中单净流入
f55 大单净流入
f56 超大单净流入
f57 主力净流入占比
f58 小单净流入占比
f59 中单净流入占比
f60 大单净流入占比
f61 超大单净流入占比
f62 收盘价
f63 涨跌幅
f64 总成交额
f65 未知（冗余）
```

> 单位：元。净流入为正表示资金流入。该接口返回最新可用交易日，使用前必须校验 `f51` 日期；`push2his` 历史资金流当前不作为稳定兜底。

---

## 5. 个股实时行情（`qt/stock/get`）

```bash
curl -s "https://push2.eastmoney.com/api/qt/stock/get?secid=0.000001&fields=f43,f44,f45,f46,f47,f48,f57,f58,f60,f170,f169,f168,f167,f162&_=$(date +%s)000"
```

**secid 前缀**
- 沪市：`1.`
- 深市：`0.`
- 北交所：`0.89` 或 `0.899`

**常用字段**
| 字段 | 含义 | 备注 |
|---|---|---|
| `f43` | 最新价 | ×100 的整数 |
| `f44` | 最高价 | ×100 |
| `f45` | 最低价 | ×100 |
| `f46` | 开盘价 | ×100 |
| `f47` | 成交量 | 手 |
| `f48` | 成交额 | 元 |
| `f57` | 股票代码 | |
| `f58` | 股票名称 | |
| `f60` | 昨收 | ×100 |
| `f170` | 涨跌幅 | %，×100 |
| `f169` | 涨跌额 | ×100 |

---

## 6. 板块榜（`clist/get`）⚠️ 经常返空

```bash
# 行业板块（慎用，经常空）
curl -s "https://push2.eastmoney.com/api/qt/clist/get?pn=1&pz=100&fid=f3&fs=m:90+t:2&fields=f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f12,f13,f14,f20,f21,f23,f24,f25,f26,f27,f28,f29,f30,f31,f32,f33,f34,f35,f36,f37,f38,f39,f40,f41,f42,f43,f44,f45,f46,f47,f48,f49,f50,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64,f65,f66,f67,f68,f69,f70,f71,f72,f73,f74,f75,f76,f77,f78,f79,f80,f81,f82,f83,f84,f85,f86,f87,f88,f89,f90,f91,f92,f93,f94,f95,f96,f97,f98,f99,f100&_=$(date +%s)000"

# 概念板块（慎用，经常空）
curl -s "...&fs=m:90+t:3&..."
```

**替代方案**：

1. 当前交易日先用同花顺公开页面作为无浏览器 fallback：
   - 行业：`https://q.10jqka.com.cn/thshy/`
   - 概念：`http://data.10jqka.com.cn/funds/gnzjl/`
2. 若公开 HTTP fallback 仍不可用，再用 camofox-browser 抓页面 `https://quote.eastmoney.com/center/gridlist.html#industry_board`，见 SKILL.md。
3. 历史日期禁止混入实时板块榜。

---

## 7. 全市场涨跌家数统计

东财没有单独的"涨跌家数"接口，但可以通过 `clist` 按条件过滤估算，或从页面抓。更简单的方式：

```bash
# 沪深京全市场总只数（取第一页1条即可看 total）
curl -s "https://push2.eastmoney.com/api/qt/clist/get?pn=1&pz=1&fid=f3&fs=m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048&fields=f3,f12,f14&_=$(date +%s)000"
```

返回里的 `data.total` 是全市场总只数。如果要精确统计涨跌家数，需遍历或抓页面。

**实用 trick**：
涨停池 `tc` + 跌停池 `tc` + 炸板池 `tc` 三者相加 ≈ 极端情绪股数量，结合全市场 total 估算情绪占比。

---

## 8. 日期参数生成

所有接口需要当日交易日日期（YYYYMMDD）。

```bash
# 今天（如果不是交易日，东财可能返前一交易日数据）
DATE=$(date +%Y%m%d)

# 最近一个交易日（周末自动回退到周五）
DOW=$(date +%u)
if [ "$DOW" -eq 6 ]; then DATE=$(date -v-1d +%Y%m%d); fi
if [ "$DOW" -eq 7 ]; then DATE=$(date -v-2d +%Y%m%d); fi
```

macOS 用 `date -v-1d`，Linux 用 `date -d "-1 day"`。
