# 数据质量验证框架（v2.1.0）

本文档记录 aftermarket.py 中实现的通用数据质量验证框架，可供其他金融数据采集脚本参考。

## 1. 指数退避重试装饰器

```python
import time
import random
from functools import wraps

def retry_with_backoff(max_retries=3, initial_delay=2):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            delay = initial_delay
            last_err = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_err = e
                    if attempt == max_retries - 1:
                        break
                    jitter = random.uniform(0.5, 1.5)
                    wait = delay * (2 ** attempt) * jitter
                    time.sleep(wait)
            return {"_error": f"{last_err} (retried {max_retries}x)"}
        return wrapper
    return decorator
```

**要点**:
- 最大重试 3 次
- 退避公式: `delay × 2^attempt × random(0.5~1.5)`
- 最终失败返回 `{"_error": ...}` 而非抛异常，让调用方可以静默处理

## 2. 数据验证与清洗

```python
def validate_and_clean_quote(data, ticker_type="index"):
    cleaned = dict(data)
    notes = []
    quality_flags = []

    # 成交量验证
    volume = cleaned.get("regularMarketVolume") or cleaned.get("volume")
    if volume is not None:
        try:
            vol = float(volume)
            threshold = 1_000_000 if ticker_type == "index" else 1_000
            if vol <= 0:
                cleaned["regularMarketVolume"] = None
                notes.append("成交量为0，标记为缺失")
                quality_flags.append("volume_zero")
            elif vol < threshold:
                notes.append(f"成交量异常偏低，可能缺失")
                quality_flags.append("volume_anomaly")
        except (TypeError, ValueError):
            cleaned["regularMarketVolume"] = None

    # 价格验证
    price_fields = ["regularMarketPrice", "previousClose", "open", "high", "low", "close"]
    for field in price_fields:
        val = cleaned.get(field)
        if val is not None:
            try:
                v = float(val)
                if v <= 0:
                    cleaned[field] = None
                    notes.append(f"{field}价格异常已过滤")
                    quality_flags.append("price_anomaly")
            except (TypeError, ValueError):
                cleaned[field] = None

    # 完整性评分
    required = ["regularMarketPrice", "previousClose", "volume"]
    available = sum(1 for f in required if cleaned.get(f) is not None)
    completeness = (available / len(required)) * 100

    cleaned["_quality"] = {
        "completeness_score": round(completeness, 1),
        "notes": notes,
        "flags": quality_flags,
    }
    return cleaned
```

**阈值设置**:

| 检测项 | 指数阈值 | 个股阈值 | 处理 |
|---|---|---|---|
| 成交量为0 | <= 0 | <= 0 | 置为 None，标记 `volume_zero` |
| 成交量异常 | < 1,000,000 | < 1,000 | 保留但标记 `volume_anomaly` |
| 价格异常 | <= 0 | <= 0 | 置为 None，不输出 |

## 3. 市场类型检测

```python
def detect_market_type(ticker_or_name):
    t = str(ticker_or_name).upper()
    if t.endswith(".HK") or "恒生" in t or "HSI" in t:
        return "hk_market"
    elif any(ex in t for ex in ["上证", "深证", "399001"]):
        return "cn_market"
    elif any(ex in t for ex in ["DAX", "CAC", "FTSE"]):
        return "eu_market"
    elif "NIKKEI" in t or t.endswith(".T"):
        return "jp_market"
    else:
        return "us_market"
```

## 4. 数据质量报告生成

```python
def print_data_quality_report(results):
    warnings = []
    recommendations = []
    total = len(results)
    avg_score = 0

    for r in results:
        q = r.get("_quality", {})
        score = q.get("completeness_score", 100)
        avg_score += score
        if score < 80:
            name = r.get("name") or r.get("symbol", "")
            warnings.append(f"{name}: 完整性较低 ({score:.0f}%)")
        for note in q.get("notes", []):
            name = r.get("name") or r.get("symbol", "")
            if "成交量" in note:
                warnings.append(f"{name}: {note}")

    avg_score = avg_score / total if total else 0

    if avg_score < 90:
        recommendations.append("数据完整性一般，建议检查网络连接或稍后重试")
    if any("异常" in str(w) for w in warnings):
        recommendations.append("部分数据异常，已标记，仅供参考")

    # 输出报告
    print(f"平均完整度: {avg_score:.0f}%")
    for w in warnings[:8]:
        print(f"  - {w}")
    for rec in recommendations:
        print(f"  - {rec}")
```

## 5. 静默错误处理原则

所有数据获取失败时，不在主报告中显示错误信息：

```python
def print_global_stock(quote_data):
    if "_error" in quote_data:
        return  # 静默跳过，不输出
    # ... 正常输出
```

**原则**:
- 数据缺失 → 不输出该 section
- 数据异常 → 输出但加 `*` 或质量注释
- 所有异常汇总到报告末尾的数据质量报告

## 6. 市场配置参数

```python
MARKET_CONFIG = {
    "us_market": {
        "tz": "America/New_York",
        "volume_range": [1_000_000, 10_000_000_000],
        "required_fields": ["Open", "High", "Low", "Close", "Volume"],
    },
    "hk_market": {
        "tz": "Asia/Hong_Kong",
        "volume_range": [1_000_000, 5_000_000_000],
        "required_fields": ["Open", "High", "Low", "Close", "Volume"],
    },
    "cn_market": {
        "tz": "Asia/Shanghai",
        "volume_range": [10_000_000, 10_000_000_000],
        "required_fields": ["Open", "High", "Low", "Close", "Volume"],
    },
}
```
