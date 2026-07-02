# fix: report quality, graded evidence scoring, and classic report style

## 背景

基于 2026-07-01 实盘复盘与 Agent 集成反馈，当前 v4.3.1/v4.4.0 存在以下用户可见问题：

1. **M1「看起来缺失」**：投委会报告 M1 小节只有 committee 文案，指数表被挪到前一节；成交额/广度/港股缺失但 M1 仍满分。
2. **M2 真缺失**：板块榜空时 `missing_modules=["M2"]`，但 summary 仍像有板块数据；抗跌方向实际来自涨跌停主题 fallback。
3. **M7 误导文案**：无持仓时 pulses 为空，却统一提示「缺少 Futu pulse」。
4. **结论与证据矛盾**：经典六模块硬编码「A股整体强于港美、指数普涨」，与当日创业板/科创50 下跌不符。
5. **产品契约错位**：用户要「六模块复盘」却默认输出投委会 9 章结构。

## 本 PR 改动

### P0 正确性

| 改动 | 文件 |
|---|---|
| 删除硬编码盘面句，新增 `_market_trend_narrative()` 基于指数涨跌/炸板率生成 | `reporting.py` |
| `cross_market_comment` 在港股/美股缺失时不做虚假三地比较 | `app.py` |
| M1/M2 **分级评分** + `module_diagnostics` 写入 evidence `_meta` | `evidence.py` |
| 板块榜缺失时报告标注「集中度来自涨跌停主题统计」 | `reporting.py` |
| `sanitize_research_report` 不再把「来源：暂无」替换成「据公开市场数据」 | `research_style.py` |
| M7 空样本区分 `market_sentiment_pipeline_not_run` vs `insufficient_samples` | `lens_engine.py` |

### P1 产品化

| 改动 | 文件 |
|---|---|
| 新增 `--report-style classic\|committee`（默认 committee） | `app.py` |
| Committee 报告 `### M1` 补回指数/北向/广度表 | `reporting.py` |
| `activated_modules` 仅反映 `available=true` 模块，不再混入 lens emphasize | `lens_engine.py` |
| 缺失模块统一顶部告警 `_missing_module_notice()` | `reporting.py` |
| M2 `available` 认可 fund_flow + concentration 部分可用 | `app.py` |

### 测试

- `tests/test_evidence_quality.py` — M1/M2 分级评分
- `tests/test_market_trend_narrative.py` — 动态盘面句
- `tests/test_report_style_cli.py` — CLI 新参数

```bash
uv run --with pytest pytest -q   # 72 passed
```

## 使用方式

```bash
# 经典六模块（推荐给用户说「复盘报告」时）
uv run python -m stock_analysis --market daily --format full --report-style classic --emit-evidence

# 投委会（默认）
uv run python -m stock_analysis --market daily --format full --report-style committee --emit-evidence
```

## 已知未覆盖（建议后续 PR）

- [ ] 市场级 M7 新闻/社区抓取（财联社/东财 RSS 最小链路）
- [ ] 指数报价 merge 成交额（避免 `tencent-kline` 路径 turnover=null）
- [ ] MCP tool 暴露 `stock_daily_recap`，减少 Agent 对 shell CLI 依赖
- [ ] `STOCK_ANALYSIS_BROWSER_FALLBACK=1` 文档化 + diagnose 板块榜探测

## Checklist

- [x] 测试通过
- [x] CHANGELOG 更新（v4.3.6）
- [x] SKILL.md 补充 `--report-style`
- [ ] Reviewer 确认分级评分阈值（M2 available >= 8 分）
