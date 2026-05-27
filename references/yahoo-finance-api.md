# Yahoo Finance 免登录 API 速查

支持全球股市实时行情、K线、财务指标。免登录、免 API Key、免 Cookie，直接 `curl` 即可。

> **频率限制警告**：Yahoo 对请求频率有限制，过快会被封 IP。建议每次请求间隔 **4-5 秒**，并添加 `User-Agent` 和 `Referer`。

---

## 1. 实时行情 / K线数据（`/v8/finance/chart/`）

```bash
# 美股
curl -s "https://query1.finance.yahoo.com/v8/finance/chart/AAPL?interval=1d&range=1d"

# 港股
curl -s "https://query1.finance.yahoo.com/v8/finance/chart/0700.HK?interval=1d&range=1d"

# 日股
curl -s "https://query1.finance.yahoo.com/v8/finance/chart/9988.T?interval=1d&range=1d"

# 中概股
curl -s "https://query1.finance.yahoo.com/v8/finance/chart/BABA?interval=1d&range=1d"

# 指数
curl -s "https://query1.finance.yahoo.com/v8/finance/chart/^GSPC?interval=1d&range=1d"  # 标普 500
curl -s "https://query1.finance.yahoo.com/v8/finance/chart/^IXIC?interval=1d&range=1d"  # 纳斯达克
curl -s "https://query1.finance.yahoo.com/v8/finance/chart/^HSI?interval=1d&range=1d"   # 恒生指数
curl -s "https://query1.finance.yahoo.com/v8/finance/chart/^DJI?interval=1d&range=1d"   # 道琼斯
```

**代码格式对照**

| 市场 | 格式示例 | 说明 |
|---|---|---|
| 美股 | `AAPL`, `TSLA`, `NVDA` | 纯代码 |
| 港股 | `0700.HK`, `9988.HK`, `9618.HK` | 代码 + `.HK` 后缀 |
| 日股 | `9988.T`, `8306.T` | 代码 + `.T` 后缀 |
| 中概股 | `BABA`, `PDD`, `JD` | 纯代码（美股上市） |
| 指数 | `^GSPC`, `^IXIC`, `^HSI`, `^DJI` | 带 `^` 前缀 |

**参数说明**

| 参数 | 说明 |
|---|---|
| `interval` | `1m` 分钟 / `15m` / `1h` / `1d` 日线 / `1wk` / `1mo` |
| `range` | `1d` / `5d` / `1mo` / `3mo` / `6mo` / `1y` / `5y` / `max` |
| `period1` + `period2` | Unix 时间戳范围（与 `range` 互斥） |

**返回结构**（简化版）

```json
{
  "chart": {
    "result": [{
      "meta": {
        "symbol": "AAPL",
        "regularMarketPrice": 189.52,
        "previousClose": 186.88,
        "regularMarketVolume": 45678900,
        "currency": "USD",
        "exchangeName": "NMS"
      },
      "timestamp": [1716816000],
      "indicators": {
        "quote": [{
          "open": [186.50],
          "high": [190.12],
          "low": [185.80],
          "close": [189.52],
          "volume": [45678900]
        }]
      }
    }]
  }
}
```

**关键字段**

| 字段 | 含义 |
|---|---|
| `regularMarketPrice` | 实时价 |
| `previousClose` | 昨收 |
| `regularMarketVolume` | 当日成交量 |
| `regularMarketChange` | 涨跌额 |
| `regularMarketChangePercent` | 涨跌幅 |
| `fiftyTwoWeekHigh` / `fiftyTwoWeekLow` | 52 周高/低 |
| `currency` | 货币 |

---

## 2. 财务指标摘要（`/v10/finance/quoteSummary/`）

```bash
curl -s "https://query2.finance.yahoo.com/v10/finance/quoteSummary/AAPL?modules=summaryDetail,defaultKeyStatistics,financialData"
```

**可用 modules**

| 模块 | 内容 |
|---|---|
| `summaryDetail` | PE、PB、市盈率、市销率、分红率、52 周高低、Beta |
| `defaultKeyStatistics` | 市值、净资产、收入、利润、员工数、第一大股东 |
| `financialData` | 营收、毛利率、营业利润率、净利率、ROE、总收入 |
| `price` | 当前价、成交量、市场状态（交易中/休市） |
| `calendarEvents` | 财报日期、分红日期 |
| `earnings` | 历史收益、未来预测 |
| `recommendationTrend` | 机构评级（强买/买入/持有/卖出/强卖） |

**常用指标对照**

| Yahoo 字段 | 含义 |
|---|---|
| `trailingPE` / `forwardPE` | 滚动 PE / 前瞻 PE |
| `priceToBook` | PB |
| `marketCap` | 总市值 |
| `dividendYield` | 分红率 |
| `beta` | Beta |
| `fiftyTwoWeekHigh` / `fiftyTwoWeekLow` | 52 周高/低 |
| `revenueGrowth` | 营收增长率 |
| `profitMargins` | 净利率 |
| `returnOnEquity` | ROE |
| `debtToEquity` | 资产负债比 |

---

## 3. 行情趋势快照（`/v6/finance/quote/`）

批量获取多只股票快照（更轻量级，适合盘面监控）：

```bash
curl -s "https://query1.finance.yahoo.com/v6/finance/quote?symbols=AAPL,TSLA,NVDA,0700.HK,9988.HK,BABA"
```

返回包含：当前价、涨跌幅、成交量、市值、市盈率、货币、交易状态。

---

## 4. Python 一次性获取示例

```python
import json, urllib.request

def yahoo_quote(symbol: str):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=1d"
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Referer": "https://finance.yahoo.com/",
    })
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        return {"_error": str(e)}

# 美股
print(yahoo_quote("AAPL"))
# 港股
print(yahoo_quote("0700.HK"))
```

---

## 5. 常见坑位

### 频率限制
过快请求会被封 IP，提示 `403 Forbidden` 或 `Too Many Requests`。
**修复**：每次请求间隔 sleep(4)，使用随机 User-Agent。

### 无法访问
某些地区或网络环境可能被阻止访问。
**修复**：使用代理或换 DNS。

### 指数代码格式
标普 500 是 `^GSPC`，纳斯达克是 `^IXIC`，道琼斯是 `^DJI`，恒生指数是 `^HSI`。必须带 `^` 前缀。

### 港股后缀
Yahoo 要求使用 `.HK` 后缀，如 `0700.HK`。不带后缀会命中美股同名标的或返空。
