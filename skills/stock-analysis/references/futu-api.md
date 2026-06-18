# Futu 免登录 Search Skills API 速查

无需 OpenD、无需 API Key，`curl` 直调。对 A股中文名、港美股代码支持较好。

默认日报仅整合以下三项：

- `futu-news-search`
- `futu-stock-digest`
- `futu-comment-sentiment`

技术面、资金面和衍生品异动需要 OpenD 启动并登录，不属于免登录默认能力。

> **市场区分**：
> - **A股**：建议用中文公司全称（如"比亚迪"而非"002594"），因富途以港美股为主，代码形式容易命中港股/美股同名标的。
> - **港股**：用代码（如"00700"或"0700"）或中文名（如"腾讯控股"），富途对港股支持极好。
> - **美股**：用代码（如"AAPL"、"TSLA"、"NVDA"），富途对美股支持极好。
> - **中概股**：用代码（如"BABA"、"PDD"、"JD"）。

---

## 1. 新闻/公告/研报搜索

```bash
# 美股新闻搜索
curl -sG 'https://ai-news-search.futunn.com/news_search' \
  -H 'User-Agent: stock-analysis/2.0.0 (Skill)' \
  --data-urlencode 'keyword=AAPL' \
  --data-urlencode 'size=10' \
  --data-urlencode 'news_type=1' \
  --data-urlencode 'lang=en' \
  --data-urlencode 'sort_type=2'

# 港股新闻搜索
curl -sG 'https://ai-news-search.futunn.com/news_search' \
  -H 'User-Agent: stock-analysis/2.0.0 (Skill)' \
  --data-urlencode 'keyword=00700' \
  --data-urlencode 'size=10' \
  --data-urlencode 'news_type=1' \
  --data-urlencode 'lang=zh-CN' \
  --data-urlencode 'sort_type=2'

# A股新闻搜索（用中文名）
curl -sG 'https://ai-news-search.futunn.com/news_search' \
  -H 'User-Agent: stock-analysis/2.0.0 (Skill)' \
  --data-urlencode 'keyword=比亚迪' \
  --data-urlencode 'size=10' \
  --data-urlencode 'news_type=1' \
  --data-urlencode 'lang=zh-CN' \
  --data-urlencode 'sort_type=2'
```

**参数**
| 参数 | 必填 | 说明 |
|---|---|---|
| `keyword` | 是 | 股票名、代码或公司名 |
| `size` | 否 | 返回条数，默认 10，最大 50 |
| `news_type` | 否 | `1` 新闻，`2` 公告，`3` 研报 |
| `lang` | 否 | `zh-CN` / `zh-HK` / `en` |
| `sort_type` | 否 | `1` 热度，`2` 时间（推荐），`3` 关注度 |

**返回**
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

`publish_time` 为 Unix 秒级时间戳，转换为 `YYYY-MM-DD HH:mm:ss` 输出。

---

## 2. 社区情绪（stock_feed）

```bash
# 美股社区情绪
curl -sG 'https://ai-news-search.futunn.com/stock_feed' \
  -H 'User-Agent: stock-analysis/2.0.0 (Skill)' \
  --data-urlencode 'keyword=AAPL' \
  --data-urlencode 'size=30'

# 港股社区情绪
curl -sG 'https://ai-news-search.futunn.com/stock_feed' \
  -H 'User-Agent: stock-analysis/2.0.0 (Skill)' \
  --data-urlencode 'keyword=00700' \
  --data-urlencode 'size=30'
```

**参数**
| 参数 | 必填 | 说明 |
|---|---|---|
| `keyword` | 是 | 股票名、代码或公司名 |
| `size` | 否 | 返回条数，默认 30，建议 1-50 |

**返回**
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

**AI 处理流程**：
1. 清洁 HTML 标签，合并 title + desc 为分析文本
2. 按时间倒序，去除 spam/空水帖/重复/纯表情帖
3. 每条分类：`bullish` / `bearish` / `neutral`
4. 统计比例，提取 Top3 有代表性观点
5. 输出情绪快照

**情绪分类规则**
- **Bullish**: 看涨、反弹、突破、业绩信心、支撑性估值、趋势买入
- **Bearish**: 看跌、回调、业绩不及预期、竞争/监管担忧、规避风险
- **Neutral**: 仅陈述事实无方向意见、观望不明、混合态度

**Mixed Aggregate**：当 `abs(bull_pct - bear_pct) < 15%` 且双方均 >=25%时，可标为 `mixed`。

---

## 3. 个股新闻解读

调用接口 1（`news_search`），对返回结果做结构化解读。

**工作流程**：
1. 抽取最新高信号事件
2. 合并重复/相近标题
3. 判断整体倾向：`bullish` / `bearish` / `neutral`
4. 保守原则：证据混合时默认 `neutral`
5. 输出固定模板

**输出模板**：
```markdown
{{symbol}} 新闻快读

结论：{{one-paragraph conclusion}}

关键信号：
- {{signal_1}}
- {{signal_2}}
- {{signal_3}}

关键证据：
1. {{title_1}} → {{url_1}}
2. {{title_2}} → {{url_2}}
```

---

## 4. 常见坑位

1. **A股代码敏感**：富途以港/美股为主，用 A股代码（如 002594）搜索可能命中港/美股同名标的。A股建议用中文公司全称。
2. **港股代码格式**：可用 `0700`（去掉前导 0）或 `00700`。
3. **社区端点可能返回全站流**：必须根据 `stockcode`、`stocksymbol`、代码或名称精确匹配标的，禁止直接对原始批次统计。
4. **社区数据量不稳定**：过滤后少于 3 条有效帖子时只标记“证据不足”，不输出多空比例。社区情绪仅代表平台内用户，不是全市场。
5. **返回为空时的处理**：如果 `code != 0` 或 `data` 为空，不编造结果，告知用户"暂无相关数据"。
6. **英文语言匹配**：美股搜索建议用 `lang=en`，港股/A股用 `lang=zh-CN`。
