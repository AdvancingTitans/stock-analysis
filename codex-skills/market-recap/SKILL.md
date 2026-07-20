---
name: market-recap
description: 根据当前时段生成 A 股或全球市场复盘。
---

# /market-recap

根据当前时段生成 A 股或全球市场复盘。

Run:

```bash
stock-analysis --market daily --emit-evidence
```

先报告事实、质量与缺口；再给条件式观察清单。

Always preserve Evidence Pack source events and state missing evidence explicitly.
If Company Evidence marks agent_primary_evidence_reach as recommended, invoke the bundled
stock-analysis-primary-evidence-reach Skill, follow primary_evidence_requests, and rerun with
--primary-evidence-file. Agent Reach is optional because the bundled fallback can use host web/PDF tools.
