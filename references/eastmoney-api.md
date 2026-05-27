# Eastmoney Free API Quick Reference

All endpoints require no login, no cookie, direct `curl`. Returns JSONP-like format; strip prefix to get pure JSON.

---

## 1. Index Quotes (`ulist.np`)

```bash
curl -s "https://push2.eastmoney.com/api/qt/ulist.np/get?fltt=2&secids=1.000001,0.399001,0.399006,1.000688,0.399005,0.899050&fields=f2,f3,f4,f5,f6,f12,f14,f15,f16,f17,f18&_=$(date +%s)000"
```

**secids prefix meaning**
| Prefix | Market |
|---|---|
| `1.` | Shanghai |
| `0.` | Shenzhen |
| `0.899` | Beijing (BSE) |

**Common index codes**
| Code | Name |
|---|---|
| `1.000001` | SSE Composite |
| `0.399001` | SZSE Component |
| `0.399006` | ChiNext |
| `1.000688` | STAR 50 |
| `0.399005` | SME |
| `0.899050` | BSE 50 |

**Field mapping (fields)**
| Field | Meaning | Note |
|---|---|---|
| `f2` | Latest price | Divide by 100 (when fltt=2) |
| `f3` | Change pct | %, divide by 100 |
| `f4` | Change amount | Divide by 100 |
| `f5` | Volume | Lots (shou) |
| `f6` | Turnover | CNY |
| `f12` | Code | e.g. `000001` |
| `f14` | Name | e.g. `上证指数` |
| `f15` | High | Divide by 100 |
| `f16` | Low | Divide by 100 |
| `f17` | Open | Divide by 100 |
| `f18` | Prev close | Divide by 100 |
| `f20` | Total market cap | CNY |
| `f21` | Float market cap | CNY |

> `fltt=2` returns price fields as integers scaled by 100. Divide by 100 for true value.

---

## 2. Limit-up / Limit-down Pools (`push2ex.eastmoney.com`)

### Limit-up Pool
```bash
curl -s "https://push2ex.eastmoney.com/getTopicZTPool?ut=7eea3edcaed734bea9cbfc24409ed989&dpt=wz.ztzt&Pageindex=0&pagesize=200&sort=fbt:asc&date=YYYYMMDD"
```

### Limit-down Pool
```bash
curl -s "https://push2ex.eastmoney.com/getTopicDTPool?ut=7eea3edcaed734bea9cbfc24409ed989&dpt=wz.ztzt&Pageindex=0&pagesize=200&sort=fbt:asc&date=YYYYMMDD"
```

### Broken-board Pool
```bash
curl -s "https://push2ex.eastmoney.com/getTopicZBPool?ut=7eea3edcaed734bea9cbfc24409ed989&dpt=wz.ztzt&Pageindex=0&pagesize=200&sort=fbt:asc&date=YYYYMMDD"
```

**Common parameters**
| Param | Description |
|---|---|
| `date` | **Required**, format `YYYYMMDD`, e.g. `20260526`. Non-trading days may return empty pool |
| `pagesize` | Max 200 |
| `sort=fbt:asc` | Sort by first board time ascending |

**Response structure**
```json
{
  "data": {
    "tc": 65,
    "pool": [
      {
        "c": "603017",
        "n": "中衡设计",
        "p": 1250,
        "zdp": 10.01,
        "zttj": { "days": 5, "ct": 2 },
        "fbt": 92500,
        "lbt": 145600,
        "fund": 123456789,
        "hybk": "建筑装饰",
        "zbc": 0,
        "ltsz": 3500000000
      }
    ]
  }
}
```

**Key fields**
| Field | Meaning |
|---|---|
| `tc` | Total count |
| `c` | Code |
| `n` | Name |
| `p` | Latest price (÷100) |
| `zdp` | Change pct |
| `zttj.days` | Consecutive board days |
| `zttj.ct` | Total limit-up count |
| `fbt` | First board time |
| `lbt` | Last board time |
| `fund` | Board order amount (CNY) |
| `hybk` | Sector |
| `zbc` | Broken-board count |
| `ltsz` | Float market cap |

---

## 3. Fund Flow (`fflow/kline`)

```bash
curl -s "https://push2.eastmoney.com/api/qt/stock/fflow/kline/get?secid=1.000001&fields1=f1,f2,f3,f7&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64,f65&klt=101&lmt=1&_=$(date +%s)000"
```

**secid format**
- SSE Composite: `1.000001`
- SZSE Component: `0.399001`

**fields2 CSV order**
```
f51 date
f52 main force net inflow
f53 small order net inflow
f54 medium order net inflow
f55 large order net inflow
f56 super-large order net inflow
f57 main force net inflow %
f58 small order net inflow %
f59 medium order net inflow %
f60 large order net inflow %
f61 super-large order net inflow %
f62 close price
f63 change pct
f64 total turnover
f65 unknown (redundant)
```

> Unit: CNY. Positive = inflow.

---

## 4. Ticker Real-time Quote (`qt/stock/get`)

```bash
curl -s "https://push2.eastmoney.com/api/qt/stock/get?secid=0.000001&fields=f43,f44,f45,f46,f47,f48,f57,f58,f60,f170,f169,f168,f167,f162&_=$(date +%s)000"
```

**secid prefix**
- Shanghai: `1.`
- Shenzhen: `0.`
- BSE: `0.89` or `0.899`

**Common fields**
| Field | Meaning | Note |
|---|---|---|
| `f43` | Latest price | ×100 integer |
| `f44` | High | ×100 |
| `f45` | Low | ×100 |
| `f46` | Open | ×100 |
| `f47` | Volume | Lots |
| `f48` | Turnover | CNY |
| `f57` | Code | |
| `f58` | Name | |
| `f60` | Prev close | ×100 |
| `f170` | Change pct | %, ×100 |
| `f169` | Change amount | ×100 |

---

## 5. Board Rankings (`clist/get`) ⚠️ Often Empty

```bash
# Industry boards (use with caution, often empty)
curl -s "https://push2.eastmoney.com/api/qt/clist/get?pn=1&pz=100&fid=f3&fs=m:90+t:2&fields=f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f12,f13,f14,f20,f21,f23,f24,f25,f26,f27,f28,f29,f30,f31,f32,f33,f34,f35,f36,f37,f38,f39,f40,f41,f42,f43,f44,f45,f46,f47,f48,f49,f50,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64,f65,f66,f67,f68,f69,f70,f71,f72,f73,f74,f75,f76,f77,f78,f79,f80,f81,f82,f83,f84,f85,f86,f87,f88,f89,f90,f91,f92,f93,f94,f95,f96,f97,f98,f99,f100&_=$(date +%s)000"

# Concept boards (use with caution, often empty)
curl -s "...&fs=m:90+t:3&..."
```

**Alternative**: Use browser automation to capture `https://quote.eastmoney.com/center/gridlist.html#industry_board`. See SKILL.md.

---

## 6. Market-wide Up/Down Stats

Eastmoney has no standalone "up/down count" endpoint, but you can estimate via `clist` filtering or page capture. Simpler approach:

```bash
# Total A-share count (fetch 1 item to see total)
curl -s "https://push2.eastmoney.com/api/qt/clist/get?pn=1&pz=1&fid=f3&fs=m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048&fields=f3,f12,f14&_=$(date +%s)000"
```

`data.total` gives total ticker count. For precise up/down stats, iterate or capture page.

**Practical trick**: ZT pool `tc` + DT pool `tc` + ZB pool `tc` combined ≈ extreme sentiment stocks; estimate sentiment proportion against total market.

---

## 7. Date Parameter Generation

All endpoints need trading-day date (YYYYMMDD).

```bash
# Today (if non-trading day, Eastmoney may return previous trading day)
DATE=$(date +%Y%m%d)

# Nearest trading day (auto-rollback on weekend)
DOW=$(date +%u)
if [ "$DOW" -eq 6 ]; then DATE=$(date -v-1d +%Y%m%d); fi   # macOS
if [ "$DOW" -eq 7 ]; then DATE=$(date -v-2d +%Y%m%d); fi   # macOS
# Linux: use date -d "-1 day" / date -d "-2 day"
```
