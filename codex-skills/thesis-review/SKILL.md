---
name: thesis-review
description: 将当前 Company Evidence 与持久化论文快照比较。
---

# /thesis-review

将当前 Company Evidence 与持久化论文快照比较。

Run:

```bash
stock-analysis --market thesis-review --symbol <symbol> --emit-evidence
```

区分事实变化、证据覆盖变化和仍需人工判断的论文变化。

Always preserve Evidence Pack source events and state missing evidence explicitly.
If Company Evidence marks agent_primary_evidence_reach as recommended, invoke the bundled
stock-analysis-primary-evidence-reach Skill, follow primary_evidence_requests, and rerun with
--primary-evidence-file. Agent Reach is optional because the bundled fallback can use host web/PDF tools.
