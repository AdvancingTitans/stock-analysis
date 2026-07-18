---
name: research-workspace
description: 为股票或基金生成可恢复、可审计的机构化研究工作区。
---

# /research-workspace Claude Code command

为股票或基金生成可恢复、可审计的机构化研究工作区。

Run:

```bash
stock-analysis --market research --symbol <symbol> [--asset-type company|fund]
```

股票冻结 C1–C8 Company Evidence，基金冻结 F1–F8 Fund Evidence；lens 与 committee 消费同一 snapshot_id，并输出证据驱动的机构报告。

Always preserve Evidence Pack source events and state missing evidence explicitly.
