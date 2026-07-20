---
name: portfolio-review
description: 读取已明确授权的本地持仓记忆，复核集中度、暴露和相对表现。
---

# /prompts:portfolio-review Codex custom prompt

读取已明确授权的本地持仓记忆，复核集中度、暴露和相对表现。

Run:

```bash
stock-analysis --market portfolio --emit-evidence
```

没有完整持仓时，只报告市场，不能虚构组合收益。

Always preserve Evidence Pack source events and state missing evidence explicitly.
If Company Evidence marks agent_primary_evidence_reach as recommended, invoke the bundled
stock-analysis-primary-evidence-reach Skill, follow primary_evidence_requests, and rerun with
--primary-evidence-file. Agent Reach is optional because the bundled fallback can use host web/PDF tools.
