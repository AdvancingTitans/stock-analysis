# 选股 Phase 0 基线

执行日期：2026-07-10。

本基线只冻结数据真实性、Universe 语义、字段单位和安装可用性；不引入筛选引擎、自然语言解析或三表校验。

## 已固定的数据契约

- 东财横截面只使用 RPT_LICO_FN_CPD。
- 2025 年 A 股年报的精确过滤式为 (DATATYPE="2025年 年报")(SECURITY_TYPE="A股")。2026-07-10 实测为 5,534 条；仅按年报类型会纳入新三板，共 11,512 条，不能用于 A 股 Universe。
- WEIGHTAVG_ROE 和 YSTZ 的单位都是百分数点：8 表示 8%，不是 0.08。二者均允许负数和零；缺失才是 UNKNOWN。
- MVP 仅可将 WEIGHTAVG_ROE 映射为 roe_weighted_pct，将 YSTZ 映射为 revenue_growth_yoy_pct。
- TOTAL_OPERATE_INCOME 暂不作为跨公司统一的 revenue 字段。年报抽样显示其与披露的“营业收入”在部分公司有口径差，因此不能在未定义口径前拿来排序或比较绝对值。

对应的可执行契约位于 src/stock_analysis/screening_baseline.py，真实响应切片位于 tests/fixtures/eastmoney_2025_annual_rows.json。

## Security Master

未来筛选必须保存 universe_as_of，并把“当前可交易股票池”与“报告期时点股票池”分开。不得用今天的上市名单伪造 2025-12-31 的可交易 Universe。

权威名单入口：

- [上交所股票与存托凭证列表](https://www.sse.com.cn/assortment/stock/list/share/)
- [深交所上市公司/定期报告入口](https://www.szse.cn/disclosure/notice/company/index.html)
- [北交所股票列表](https://www.bse.cn/nq/listedcompany.html)

2026-07-10 的三所页面元数据分别为 SSE 1,604、SZSE 2,895、BSE 327，当前名单合计 4,826 条。三种官方响应都已由 normalize_sse_security_master_row()、normalize_szse_security_master_row() 和 normalize_bse_security_master_row() 固化为同一记录形状。

全量刷新仍必须留下来源 URL、抓取时间、服务端总数、抓取数、去重数和缺失字段数。若服务端总数与抓取数不一致，快照状态只能是 partial，且不得覆盖上一次完整快照。2025 年报披露集与当前名单的完整交集会在上述门禁通过后写入 Evidence；不得依据部分分页结果给出“全市场”结论。

## 独立正式年报抽样

以巨潮资讯正式年报 PDF 对东财字段做了 10 个样本的独立核对；巨潮是深交所法定信息披露平台。所有样本的 ROE 和营收同比与年报一致，差异仅来自年报展示精度。

| 代码 | 公司 | ROE：年报 / 东财 | 营收同比：年报 / 东财 | 结论 |
|---|---|---:|---:|---|
| 000001 | 平安银行 | 9.15 / 9.15 | -10.4 / -10.3978 | 通过 |
| 000333 | 美的集团 | 19.70 / 19.70 | 12.11 / 12.0802 | 通过 |
| 000858 | 五粮液 | 6.89 / 6.89 | -54.55 / -54.5518 | 通过 |
| 002594 | 比亚迪 | 15.31 / 15.31 | 3.46 / 3.4568 | 通过 |
| 300750 | 宁德时代 | 24.91 / 24.91 | 17.04 / 17.0406 | 通过 |
| 600519 | 贵州茅台 | 32.53 / 32.53 | -1.21 / -1.2001 | 通过 |
| 600900 | 长江电力 | 15.90 / 15.90 | 2.07 / 2.0713 | 通过 |
| 601318 | 中国平安 | 14.0 / 14.0 | 2.1 / 2.0974 | 通过 |
| 601899 | 紫金矿业 | 33.04 / 33.04 | 14.96 / 14.9648 | 通过 |
| 688981 | 中芯国际 | 3.4 / 3.4 | 16.5 / 16.4850 | 通过 |

可复核的原始年报包括：[平安银行](https://static.cninfo.com.cn/finalpage/2026-03-21/1225022887.PDF)、[美的集团](https://static.cninfo.com.cn/finalpage/2026-03-31/1225065145.PDF)、[贵州茅台](https://static.cninfo.com.cn/finalpage/2026-04-17/1225114741.PDF)、[宁德时代](https://static.cninfo.com.cn/finalpage/2026-03-10/1225002214.PDF)、[紫金矿业](https://static.cninfo.com.cn/finalpage/2026-03-21/1225023658.PDF)。

两处金额口径差必须保留为已知限制：美的年报“营业收入”为 456,451,731 千元，而东财 TOTAL_OPERATE_INCOME 为 458,502,407 千元；贵州茅台对应数分别为 168,838,102,514.79 和 172,054,171,890.91。二者的同比字段仍与年报一致，故 MVP 只采用同比字段，不采用该金额字段。

## 发布基线

Lens JSON 现在会随着 wheel 安装到 stock_analysis/lens_config。安装后的运行时优先读取此目录；源码开发仍保留现有 skills/stock-analysis/config/lenses 回退。Phase 0 的 clean-wheel 验收是：构建 wheel、隔离安装后运行 stock-analysis --market a --format summary 不因 Lens 配置路径缺失而失败。

## Phase 1 / 2：确定性筛选与可靠性门禁

筛选入口为：

```bash
stock-analysis --market screen \
  --fiscal-year 2025 \
  --universe-file official_universe_2026-07-10.json \
  --filter roe_weighted:gt:8% \
  --filter revenue_growth_yoy:gt:8% \
  --sort roe_weighted:desc \
  --limit 20 \
  --emit-evidence
```

- 条件只能是两个以内的 AND，且均为严格 `gt`；`8%` 与 `8` 都表示 8 个百分点。
- 每个已披露年报记录都获得 `PASS`、`FAIL` 或 `UNKNOWN`：不在当前 Universe、或筛选字段缺失时为 `UNKNOWN`。
- 结果仅称“条件命中股票”；不对现金流、盈利质量、估值或投资价值作隐含判断。
- `--emit-evidence` 只生成一个 `screen_evidence_<query_id>.json`，其中包含请求、Universe、来源事件、分页质量、结果、逐股决策和缓存元数据。

`--universe-file` 必须是来自三所官方名单的完整快照，最小形状如下。CLI 会拒绝 partial、总数/去重数不一致或证券代码异常的文件：

```json
{
  "complete": true,
  "reported_total": 4826,
  "pages_fetched": 12,
  "unique_symbols": 4826,
  "universe_as_of": "2026-07-10",
  "sources": ["官方名单 URL"],
  "records": [{"symbol": "600000"}]
}
```

东财年报横截面会按服务端 `count` / `pages` 串行拉取并核对抓取数、唯一代码数和页数；任一项不一致时只返回 partial 诊断，不写入缓存，也不能触发筛选。完整响应 warm cache 有效期为 24 小时。

常规 pytest 不联网；`.github/workflows/screening-contract.yml` 单独按周运行 `scripts/screening_contract_check.py`，仅检查在线年报横截面契约。网络或来源端异常会使该独立任务失败，而不会污染日常测试结果。
