# 本地仓库直接调用食谱

当 `stock_analysis` 包已经以源码形式存在于用户工作目录（如 `/Users/yjw/agent/stock-analysis-v42`），且用户要求基于该本地代码生成报告时，按本食谱执行，不要重新克隆或假设必须走 `uv run python -m stock_analysis`。

## 前提检查

1. 确认仓库根目录存在 `pyproject.toml` 且 `src/stock_analysis/` 包可用。
2. 确认存在 `.venv/` 虚拟环境；如不存在，按仓库说明创建。
3. 确认存在用户投资记忆 `~/.stock_analysis/profile.json` 或 `STOCK_ANALYSIS_PROFILE` 环境变量覆盖路径。

## 激活并调用

```bash
cd /path/to/stock-analysis
source .venv/bin/activate
python -m stock_analysis.app --date YYYYMMDD --market daily --format full --with-holdings
```

- `--date YYYYMMDD`：用户明确指定日期时使用；未指定则自动解析最近交易日。
- `--market daily`：生成 A股/港股/美股/基金综合日报。
- `--format full`：输出完整 6 模块深度复盘。
- `--with-holdings`：读取本地投资记忆并输出持仓分析。
- 需要保留 evidence JSON 时追加 `--emit-evidence`。

## 证据降级模式

对于非当日的历史日期（如 2025-07-03），东财涨跌停池、板块榜等接口可能返回空或部分空数据，导致：

- M3（赚钱效应与上涨主线）缺失：涨停/跌停/炸板池为空。
- M6（抗跌方向）缺失：无法从涨跌停主题或板块榜推导 resilient 方向。
- M2（板块资金与集中度）部分缺失：行业/概念板块榜可能为空，仅保留资金流数据。

此时报告会自动降级：

- 在报告顶部添加 `> 本模块证据暂缺，报告聚焦指数、持仓和风险控制。`
- 在对应 M1-M6 章节内标注 `==本模块证据暂缺，……==`。
- 投资确信度自动评为“偏低”，推荐结论为“维持观察”。

这属于正常的数据时效性限制，不是代码缺陷。不要反复重试相同接口，也不要把缺失数据补为零值或虚构值。

## 输出验证

运行后检查：

1. stdout 是否以 `# 全球市场复盘研报（YYYY-MM-DD 盘后）` 开头。
2. 是否包含标准免责声明。
3. 若启用了 `--emit-evidence`，确认生成了 `evidence_YYYYMMDD.json` 和 `m1_YYYYMMDD.json` 至 `m6_YYYYMMDD.json`。
4. 若数据缺失，确认缺失模块已在报告顶部和对应章节明确标注。

## 何时升级数据链路

只有在同时满足以下条件时，才考虑启用浏览器或 mootdx：

- 当日或前一交易日数据仍缺失；
- 用户明确要求完整 6 模块；
- diagnose 显示浏览器/mootdx 可用。

否则，接受降级报告并在风险提示中说明证据限制。
