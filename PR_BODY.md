# fix: M7 market sentiment, M2/HK evidence gaps, unified committee report (v4.3.6)

## 问题与根因

| # | 现象 | 根因 |
|---|---|---|
| 1 | M7 社区情绪无数据 | `build_evidence()` 未跑市场级新闻管线；M7 仅依赖 `--with-holdings` 持仓 Futu pulse |
| 2 | M2 板块榜暂缺 | 历史日期 `fetch_board_list()` 硬阻断 + `route_board_data` 对非当日直接返回空 |
| 3 | 港股指数暂缺 | 历史 K 线要求精确交易日匹配；腾讯港股 K 线滞后 1 日时返回空 |
| 4 | classic/committee 结构不一致 | `--report-style classic` 走独立 `render_report()` 六模块模板 |
| 5 | 成交额为空/偏小 | 历史 A 股指数走 tencent-kline，未 merge 东财 `get_index` 的 `f6` 成交额 |
| 6 | 顶部「本模块证据暂缺：。」 | `degrade_mode=degraded` 但 `missing_modules=[]` 时仍输出空列表文案 |

## 本 PR 改动

### M7 市场级情绪管线（P0）
- 新增 `market_sentiment.py`：`fetch_market_sentiment()` 聚合富途/新浪/东财市场关键词新闻
- `build_evidence()` 写入 `chinese_news_items`、`market_public_pulse`，并注入 `portfolio_public_pulse`
- Committee M7 现可输出 `status: ok`、新闻样本数、关键标题（无持仓时也可用）

### M2 板块榜（P0）
- 近 7 日历史：优先读缓存 → 允许东财/同花顺实时回填（带 `_stale_warning`）
- 远期历史（>7 日）：禁止混用实时数据，返回明确 `_unavailable`
- `STOCK_ANALYSIS_BROWSER_FALLBACK=1` 启用浏览器降级

### 港股指数（P0）
- 历史 K 线支持 `allow_nearest`（最近可用交易日，≤5 日）
- K 线全空时回退实时港股指数并标注 `nearest_available_live`

### 报告结构统一（P1）
- 移除 classic 独立输出路径；`render_report()` 统一委托 `render_report_with_metadata()`
- `--report-style classic` 保留为兼容别名，实际输出投委会结构

### 其他
- A 股历史指数成交额强制 merge 东财 `get_index.f6`
- 修复 degraded 空缺失列表顶部告警文案

## 验证

```bash
uv run --with pytest pytest -q   # 79 passed

uv run python -m stock_analysis --market daily --date 20260701 --format full --emit-evidence
# 港股 3 项、M2 板块榜、M7 新闻 16 条、统一 committee 结构
```

## 已知限制（后续 PR）

- [ ] 社区情绪（雪球/股吧）仍为 registered 无样本；需独立抓取器
- [ ] 历史板块榜依赖交易日缓存，首次远期复盘仍可能空
- [ ] 港股 `nearest_available_kline` 与请求日可能差 1 个交易日
- [ ] MCP tool 暴露 `stock_daily_recap` 减少 Agent shell 依赖

## Checklist

- [x] 79 tests passed
- [x] CHANGELOG v4.3.6
- [x] SKILL.md 更新（统一 committee 结构）