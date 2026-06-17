# Changelog

## v4.0.0 - 2026-06-18

- 重构为独立 `stock_analysis` Python 包，不再只是 `young-stock-cli` 薄包装。
- 新增 `daily_recap.py` 主入口，`aftermarket.py` 保持兼容转发。
- 引入 `normalize_code(symbol, source)`、交易日/时段判断、证据包评分、持仓完整性校验、诊断命令。
- 新增东财统一限流 helper、浏览器健康检测与降级链路占位实现。
- 新增 `references/methodology/`、`references/template/`、`output_discipline.md` 等方法论文档。
- 报告升级为研报叙述体，并新增指数、持仓、连板梯队三类表格。
- 正式报告隐藏 API 来源和技术降级轨迹，缺失值使用空单元格。
- 持仓建议新增当日浮动盈亏、基准跑赢/跑输、风格错位和条件化操作建议。
- A股趋势新增百度 K 线 fallback，美股趋势新增新浪日 K fallback。
- 持仓建议升级为券商研报结尾结构，新增基准跑赢/跑输、仓位动作建议与观察清单。
- 新增直接持股与基金重仓股重复暴露识别，并使用条件化仓位建议替代泛化表述。
