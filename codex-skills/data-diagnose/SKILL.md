---
name: data-diagnose
description: 检查当前数据源、浏览器接管边界和缺失字段。
---

# /data-diagnose

检查当前数据源、浏览器接管边界和缺失字段。

Run:

```bash
stock-analysis --market diagnose
```

把不可用数据源、fallback 与下一步补数路径明确告知用户。

Always preserve Evidence Pack source events and state missing evidence explicitly.
If Company Evidence marks agent_primary_evidence_reach as recommended, invoke the bundled
stock-analysis-primary-evidence-reach Skill, follow primary_evidence_requests, and rerun with
--primary-evidence-file. Agent Reach is optional because the bundled fallback can use host web/PDF tools.
