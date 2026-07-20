---
name: earnings-review
description: 复核已披露结构化财务事实，并明确财报研究缺口。
---

# /earnings-review Claude Code command

复核已披露结构化财务事实，并明确财报研究缺口。

Run:

```bash
stock-analysis --market earnings --symbol <symbol> --emit-evidence
```

在取得原始财报前，不推断 GAAP、指引或估值结论。

Always preserve Evidence Pack source events and state missing evidence explicitly.
If Company Evidence marks agent_primary_evidence_reach as recommended, invoke the bundled
stock-analysis-primary-evidence-reach Skill, follow primary_evidence_requests, and rerun with
--primary-evidence-file. Agent Reach is optional because the bundled fallback can use host web/PDF tools.
