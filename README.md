# stock-analysis

基于 `AdvancingTitans/stock-analysis` 日报框架重构的全球股市证据驱动复盘引擎，整合：

- `simonlin1212/a-stock-data` 的 A股数据分层、东财独有端点与限流经验
- `simonlin1212/global-stock-data` 的新浪/腾讯/东财港美股映射
- `a-stock-daily-market-sense` 的 6 模块 Evidence Pack 方法

当前 CLI 版本为 `4.3.1`；Skill 规则版本为 `4.3.5`。

## 已实现

- 腾讯/新浪优先的 A股、港股、美股行情链路，东财作为独有数据或末级 API fallback
- M2 行业/概念板块榜：东财 `clist` 首选，同花顺公开板块页作为无浏览器 fallback，避免空响应污染报告
- 港美股东财 fallback 会通过 `searchapi` 动态解析 secid，补足 BABA、港股五位代码等静态映射以外标的
- `normalize_code(symbol, source)` 统一 A股、港股、美股和基金代码
- 腾讯/新浪 GB2312 强制解码，空字段保留 `None`
- 东财 `em_get()` 统一无代理 Session、1 秒间隔、抖动和最多 3 次指数退避
- 最近交易日与 A股/港股/美股时段识别，`--format auto` 自动选择报告深度
- 投资记忆优先的股票/基金持仓、汇率折算、浮盈亏、集中度、重复暴露和基准比较
- 内置 15 个投资框架视角，支持用户明确指定专家风格后全篇切换视角
- Futu 免登录新闻与社区数据，形成持仓公开信息脉冲和可审计原文链接
- Evidence Pack、6 个模块 JSON、100 分质量评分和降级报告
- 确定性入口纪律：`daily`、`stock`、`fund` 默认不需要 LLM，不把浏览器或慢源伪装成主路径
- 单股/基金速览入口：先给可核验报价、估值、交易日和缺口提示，再由 Agent 决定是否升级为深度复盘
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
| 行业/概念板块榜 | 东财 `clist` | 同花顺行业/概念页 → Camofox/Playwright |
| 港股行情 | 腾讯/新浪互补 | 东财 `stock/get` |
| 美股行情 | 新浪/腾讯互补 | 东财 searchapi 解析 secid 后 `stock/get` |
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

# 确定性单股/基金速览，不触发 LLM
~/.local/bin/uv run python -m stock_analysis --market stock --symbol 600519
~/.local/bin/uv run python -m stock_analysis --market fund --symbol 161725

# 网络和数据源诊断
~/.local/bin/uv run python -m stock_analysis --market diagnose
```

持仓绩效分析只在用户明确要求持仓分析，或 CLI 显式传入 `--with-holdings` 时读取投资记忆。持仓相关请求优先读取本技能自己的 `~/.stock_analysis/profile.json` 或 `STOCK_ANALYSIS_PROFILE`，不会读取或写入其他工具的 profile，也不会因为本机存在其他工具的 profile 而自动触发持仓分析。

投资记忆不存在、投资记忆有但信息不完整，或用户主动提供的持仓信息不完整时，等待用户交互输入并进入一次确认流程。只有股票代码、买入日期、买入数量或买入金额三项完整，才输出收益、浮盈亏、年化表现和组合绩效；缺少任意一项时，默认生成普通市场复盘报告，不包含持仓绩效内容，并只提问一次精准提示补齐缺失项。

如果买入日期没有年份，按当前年份计算；如果用户只给出数字，必须确认这是买入数量还是买入金额，并确认币种是人民币、港币还是美元。用户补齐或修改后的持仓信息完整时，保存到本地投资记忆，并明确告知：“投资记忆已保存本地。下次将默认按这份投资记忆分析持仓；如需清空投资记忆请反馈。”

如果用户新提供的信息与之前保存的投资记忆不一致，先确认信息完整性；确认信息完整性后，优先以用户新提供的信息为准，覆盖写入投资记忆。不完整的新信息不得覆盖已有完整投资记忆。

`--market stock --symbol <代码>` 与 `--market fund --symbol <代码>` 是确定性证据视图：
只输出当前价/估值、涨跌、交易日、关键交易字段和基金重仓股报价；字段缺失时保留空单元格并提示缺口。
如果用户需要研报式判断，再运行 `daily`、`a`、`global --format full --emit-evidence`，或由任意 Agent 基于 evidence pack 生成观点层报告。

兼容入口：

```bash
~/.local/bin/uv run python skills/stock-analysis/scripts/daily_recap.py --market daily
~/.local/bin/uv run python skills/stock-analysis/scripts/aftermarket.py --market a --format full
```

## 自动时段

| 市场时段（北京时间） | 自动格式 | 内容 |
|---|---|---|
| A/H 09:00-09:30 | `summary` | 指数、开盘判断、风险 |
| A/H 09:30-11:30、13:00-15:00 | `key-points` | 指数、趋势、赚钱效应、下跌风险 |
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

### 模块边界

`stock-analysis` 固定负责 M1-M6 的证据包、评分和研报正文；聊天、发送、外部发布和真实交易都属于集成方的上层产品工作流。需要多专家综合时，应先用本包产出可审计 evidence，再由 Agent 或宿主应用基于内置投资框架做综合判断；不要在本包里新增交易、发送或聊天外壳。

### 内置投资框架

当用户明确提出想用哪位投资专家的风格生成报告时，必须完全以相关专家的视角输出报告：整篇报告的证据优先级、判断顺序、风险表达、持仓建议和观察清单都服从该专家框架，不得只在结尾追加专家点评。

支持 `buffett`、`munger`、`graham`、`klarman`、`lynch`、`o_neil`、`wood`、`dalio`、`soros`、`livermore`、`minervini`、`simons`、`duan_yongping`、`zhang_kun`、`feng_liu`。可识别专家名称、英文名、中文名、别名或框架 id。

单专家视角不输出多专家委员会小节，也不输出交易计划草案、风险管理意见、组合经理最终意见等委员会内容；最后章节使用 `## {专家中文名}持仓建议与风险提示`。报告不得模仿身份声明或虚构专家发言，所有结论仍必须回到 evidence 和公开市场数据。

## 能力边界

- Futu 默认仅使用无需 OpenD、无需登录的资讯搜索、个股新闻解读和社区情绪接口。
- Futu 技术面、资金面和衍生品异动依赖 OpenD 登录，不进入开箱即用的默认日报。
- 社区接口可能返回全站流数据；程序只保留精确匹配当前标的的有效帖子，少于 3 条时标记证据不足。
- 显式历史日期报告不混入当前 Futu 新闻或社区情绪。
- Python CLI 不能直接调用 Hermes 内置浏览器，因为它属于 Agent 工具；CLI 会在 diagnose/evidence 中提示由 Hermes、Codex 或 OpenClaw 执行环境接管。
- 浏览器路径只作为 API 连续失败或页面独有数据的降级路径；正文不展示浏览器、API 或 fallback 工程细节，相关信息留在 diagnose/evidence。
- Camofox 自动板块抓取依赖 `CAMOFOX_USER_ID` 和 `CAMOFOX_SESSION_KEY`；缺少凭据时不会伪装成功。
- `mootdx` 默认禁用且不是必装依赖；启用后仅服务五档、逐笔和深度 K 线，不进入日常行情主路径。
- 专用请求通过 `sources/mootdx_adapter.py` 路由；依赖缺失、TCP 失败或空数据时自动回普通腾讯/新浪报价并记录原因。
- 法定休市日当前使用内置日历，跨年份运行前应更新交易日表。
- 龙虎榜、解禁、两融、大宗、股东户数、研报和新闻属于可扩展独有端点，并非全部进入每日日报默认抓取。
- 项目内置行情适配器、缓存、投资记忆、证据评分和路由编排；不要求用户安装任何外部行情 CLI。

## 开发验证

```bash
~/.local/bin/uv run --with pytest pytest -q
~/.local/bin/uv run --with ruff ruff check
```

以上内容仅供参考，不构成任何投资建议。股市有风险，投资需谨慎。
