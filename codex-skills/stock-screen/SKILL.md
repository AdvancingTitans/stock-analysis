---
name: stock-screen
description: 执行有完整官方 Universe 门禁的确定性 A 股年报筛选。
---

# /stock-screen

执行有完整官方 Universe 门禁的确定性 A 股年报筛选。

Run:

```bash
stock-analysis --market screen --fiscal-year <year> --universe-file <path> --filter roe_weighted:gt:8% --sort roe_weighted:desc --emit-evidence
```

只报告 PASS/FAIL/UNKNOWN，不能把硬筛选结果说成优质公司名单。

Always preserve Evidence Pack source events and state missing evidence explicitly.
If Company Evidence marks agent_primary_evidence_reach as recommended, invoke the bundled
stock-analysis-primary-evidence-reach Skill, follow primary_evidence_requests, and rerun with
--primary-evidence-file. Agent Reach is optional because the bundled fallback can use host web/PDF tools.
