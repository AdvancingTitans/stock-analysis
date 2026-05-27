# Futunn Free Search Skills API Quick Reference

No OpenD, no API Key, direct `curl`. Works well with Chinese company names or codes for A-share tickers.

> **A-share search recommendation**: Use **Chinese company full name** as keyword (e.g. "比亚迪" not "002594"), because Futunn is HK/US-centric and code format may hit同名 tickers.

---

## 1. News / Announcement / Research Search

```bash
curl -sG 'https://ai-news-search.futunn.com/news_search' \
  -H 'User-Agent: stock-analysis/1.2.0 (Skill)' \
  --data-urlencode 'keyword=比亚迪' \
  --data-urlencode 'size=10' \
  --data-urlencode 'news_type=1' \
  --data-urlencode 'lang=zh-CN' \
  --data-urlencode 'sort_type=2'
```

**Parameters**
| Param | Required | Description |
|---|---|---|
| `keyword` | Yes | Stock name, code, or company name |
| `size` | No | Return count, default 10, max 50 |
| `news_type` | No | `1` news, `2` announcement, `3` research |
| `lang` | No | `zh-CN` / `zh-HK` / `en` |
| `sort_type` | No | `1` hot, `2` time (recommended), `3` attention |

**Response**
```json
{
  "code": 0,
  "data": [
    {
      "news_id": "...",
      "news_type": 1,
      "title": "...",
      "publish_time": 1714102800,
      "url": "https://news.futunn.com/...",
      "img_url": "..."
    }
  ]
}
```

`publish_time` is Unix seconds. Convert to `YYYY-MM-DD HH:mm:ss` for output.

---

## 2. Community Sentiment (`stock_feed`)

```bash
curl -sG 'https://ai-news-search.futunn.com/stock_feed' \
  -H 'User-Agent: stock-analysis/1.2.0 (Skill)' \
  --data-urlencode 'keyword=比亚迪' \
  --data-urlencode 'size=30'
```

**Parameters**
| Param | Required | Description |
|---|---|---|
| `keyword` | Yes | Stock name, code, or company name |
| `size` | No | Return count, default 30, suggest 1-50 |

**Response**
```json
{
  "code": 0,
  "data": [
    {
      "id": "...",
      "title": "...",
      "desc": "...",
      "publish_time": 1714102800,
      "url": "..."
    }
  ]
}
```

**AI Processing Pipeline**:
1. Strip HTML tags, merge title + desc as analysis text
2. Sort by time desc, remove spam/empty/duplicate/pure-emoji posts
3. Classify each: `bullish` / `bearish` / `neutral`
4. Count proportions, extract Top3 representative views
5. Output sentiment snapshot

**Sentiment Classification Rules**
- **Bullish**: bullish, rebound, breakout, earnings confidence, supportive valuation, trend buy
- **Bearish**: bearish, pullback, earnings miss, competition/regulation concern, risk avoidance
- **Neutral**: factual statement without direction, wait-and-see, mixed attitude

**Mixed Aggregate**: When `abs(bull_pct - bear_pct) < 15%` and both >=25%, label as `mixed`.

---

## 3. Ticker News Digest

Call endpoint #1 (`news_search`), then do structured analysis on results.

**Workflow**:
1. Extract latest high-signal events
2. Merge duplicate/similar titles
3. Judge overall tendency: `bullish` / `bearish` / `neutral`
4. Conservative principle: default to `neutral` when evidence mixed
5. Output fixed template

**Output Template**:
```markdown
{{symbol}} News Quick Read

Conclusion: {{one-paragraph conclusion}}

Key Signals:
- {{signal_1}}
- {{signal_2}}
- {{signal_3}}

Key Evidence:
1. {{title_1}} → {{url_1}}
2. {{title_2}} → {{url_2}}
```

---

## 4. Common Pitfalls

1. **A-share code sensitivity**: Futunn is HK/US-centric; using code (e.g. 002594) for A-share may hit同名 tickers. Use Chinese company name as keyword.
2. **Community data unstable**: Small-cap A-shares may have minimal or empty community discussion. Community sentiment reflects platform users only, not entire market.
3. **Empty response handling**: If `code != 0` or `data` empty, don't fabricate results; inform user "no relevant data available".
