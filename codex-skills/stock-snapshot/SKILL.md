---
name: stock-snapshot
description: 获取一个标的的确定性报价、量价和已披露财务快照。
---

# /stock-snapshot

获取一个标的的确定性报价、量价和已披露财务快照。

Run:

```bash
stock-analysis --market stock --symbol <symbol>
```

不要把快照当作完整公司研究或买卖建议。

Always preserve Evidence Pack source events and state missing evidence explicitly.
If Company Evidence marks agent_primary_evidence_reach as recommended, invoke the bundled
stock-analysis-primary-evidence-reach Skill, follow primary_evidence_requests, and rerun with
--primary-evidence-file. Agent Reach is optional because the bundled fallback can use host web/PDF tools.
