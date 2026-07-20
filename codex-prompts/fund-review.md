---
name: fund-review
description: 获取基金净值、画像、持仓和公开缺口。
---

# /prompts:fund-review Codex custom prompt

获取基金净值、画像、持仓和公开缺口。

Run:

```bash
stock-analysis --market fund --symbol <fund_code>
```

说明基金持有者关心的风格、集中度与重仓股风险；不编造未披露指标。

Always preserve Evidence Pack source events and state missing evidence explicitly.
If Company Evidence marks agent_primary_evidence_reach as recommended, invoke the bundled
stock-analysis-primary-evidence-reach Skill, follow primary_evidence_requests, and rerun with
--primary-evidence-file. Agent Reach is optional because the bundled fallback can use host web/PDF tools.
