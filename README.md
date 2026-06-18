# stock-analysis

基于 `AdvancingTitans/stock-analysis` 日报框架重构的全球股市证据驱动复盘引擎，整合：

- `simonlin1212/a-stock-data` 的 A股数据分层、东财独有端点与限流经验
- `simonlin1212/global-stock-data` 的新浪/腾讯/东财港美股映射
- `a-stock-daily-market-sense` 的 6 模块 Evidence Pack 方法

当前版本为 `4.2.0`。

## 已实现

- 腾讯/新浪优先的 A股、港股、美股行情链路，东财作为独有数据或末级 API fallback
- `normalize_code(symbol, source)` 统一 A股、港股、美股和基金代码
- 腾讯/新浪 GB2312 强制解码，空字段保留 `None`
- 东财 `em_get()` 统一无代理 Session、1 秒间隔、抖动和最多 3 次指数退避
- 最近交易日与 A股/港股/美股时段识别，`--format auto` 自动选择报告深度
- young profile 股票/基金持仓、汇率折算、浮盈亏、集中度、重复暴露和基准比较
- Futu 免登录新闻与社区数据，形成持仓公开信息脉冲和可审计原文链接
- Evidence Pack、6 个模块 JSON、100 分质量评分和降级报告
- Camofox 健康检测、板块榜 fallback、Hermes browser 接管说明、Playwright 可用性诊断
- 固定报告顺序、Markdown 表格、研报措辞过滤和强制免责声明
- `diagnose` 对腾讯、新浪、东财、Camofox、Hermes browser、Playwright、mootdx 的检查

## 数据源策略

| 场景 | 主路径 | 备用路径 |
|---|---|---|
| A股报价/估值 | 腾讯 → 新浪 | 东财 `stock/get` |
| A股指数 | 腾讯 → 新浪 | 东财指数接口 |
| 五档/逐笔/深度分钟 K | mootdx，默认关闭 | 腾讯/新浪基础行情 |
| A股独有信号 | 东财限流接口 | Camofox / Agent 浏览器接管 |
| 港股行情 | 腾讯/新浪互补 | 东财 `stock/get` |
| 美股行情 | 新浪/腾讯互补 | 东财 `stock/get` |
| 港股历史 K | 腾讯 K 线 | 东财可用数据 |
| 美股历史 K | 新浪日 K | 东财可用数据 |
| 基金 | 天天基金/东财基金 | 新浪基金 |

Yahoo 已从推荐路径和当前技术分析路径移除。

## 使用

```bash
~/.local/bin/uv sync

# 按当前时段自动选择深度
~/.local/bin/uv run python -m stock_analysis --market daily

# 明确要求完整复盘并保留 Evidence Pack
~/.local/bin/uv run python -m stock_analysis \
  --market global \
  --format full \
  --with-holdings \
  --emit-evidence

# 用户明确指定历史交易日
~/.local/bin/uv run python -m stock_analysis --market a --date 20260618

# 网络和数据源诊断
~/.local/bin/uv run python -m stock_analysis --market diagnose
```

`--market daily` 与 `--market a` 默认加载 young profile 持仓；港股、美股或全球模式需通过
`--with-holdings` 显式加载。

兼容入口：

```bash
~/.local/bin/uv run python skills/stock-analysis/scripts/daily_recap.py --market daily
~/.local/bin/uv run python skills/stock-analysis/scripts/aftermarket.py --market a --format full
```

## 自动时段

| 市场时段（北京时间） | 自动格式 | 内容 |
|---|---|---|
| A/H 09:00-09:30 | `summary` | 指数、持仓、开盘判断、风险 |
| A/H 09:30-11:30、13:00-15:00 | `key-points` | 指数、持仓、趋势、赚钱效应、下跌风险 |
| A/H 15:00 后 | `full` | 完整固定顺序与 6 模块 |
| 美股 21:30-次日 04:00 | `key-points` | 夜盘中量版 |

未指定日期时，程序从当前自然日开始判断；周末和内置 A股法定休市日回溯到最近交易日，并写入 `_meta.trade_date`。

## Evidence Pack

使用 `--emit-evidence` 后生成：

```text
evidence_YYYYMMDD.json
m1_YYYYMMDD.json
m2_YYYYMMDD.json
m3_YYYYMMDD.json
m4_YYYYMMDD.json
m5_YYYYMMDD.json
m6_YYYYMMDD.json
```

评分为 M1 20、M2 20、M3 20、M4 15、M5 15、M6 10。空模块不再计分，低于 60 分只输出指数、持仓和风险提示。

## 能力边界

- Futu 默认仅使用无需 OpenD、无需登录的资讯搜索、个股新闻解读和社区情绪接口。
- Futu 技术面、资金面和衍生品异动依赖 OpenD 登录，不进入开箱即用的默认日报。
- 社区接口可能返回全站流数据；程序只保留精确匹配当前标的的有效帖子，少于 3 条时标记证据不足。
- 显式历史日期报告不混入当前 Futu 新闻或社区情绪。
- Python CLI 不能直接调用 Hermes 内置浏览器，因为它属于 Agent 工具；CLI 会在 diagnose/evidence 中提示由 Hermes、Codex 或 OpenClaw 执行环境接管。
- Camofox 自动板块抓取依赖 `CAMOFOX_USER_ID` 和 `CAMOFOX_SESSION_KEY`；缺少凭据时不会伪装成功。
- `mootdx` 默认禁用且不是必装依赖；启用后仅服务五档、逐笔和深度 K 线，不进入日常行情主路径。
- 专用请求通过 `sources/mootdx_adapter.py` 路由；依赖缺失、TCP 失败或空数据时自动回普通腾讯/新浪报价并记录原因。
- 法定休市日当前使用内置日历，跨年份运行前应更新交易日表。
- 龙虎榜、解禁、两融、大宗、股东户数、研报和新闻属于可扩展独有端点，并非全部进入每日日报默认抓取。
- 项目仍复用 `young-stock-cli` 的成熟行情适配器和投资记忆；“独立引擎”指报告、证据、评分和路由编排独立，不代表已移除该运行依赖。

## 开发验证

```bash
~/.local/bin/uv run --with pytest pytest -q
~/.local/bin/uv run --with ruff ruff check
```

以上内容仅供参考，不构成任何投资建议。股市有风险，投资需谨慎。
