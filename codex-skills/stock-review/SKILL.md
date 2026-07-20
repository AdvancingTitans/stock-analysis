---
name: stock-review
description: 生成独立于 M1-M6 的 C1-C8 Company Evidence Pack。
---

# /stock-review

生成独立于 M1-M6 的 C1-C8 Company Evidence Pack。

Run:

```bash
stock-analysis --market stock-review --symbol <symbol> --emit-evidence
```

严格区分可验证事实、证据缺口与需要补充的一手资料。

Always preserve Evidence Pack source events and state missing evidence explicitly.
If Company Evidence marks agent_primary_evidence_reach as recommended, invoke the bundled
stock-analysis-primary-evidence-reach Skill, follow primary_evidence_requests, and rerun with
--primary-evidence-file. Agent Reach is optional because the bundled fallback can use host web/PDF tools.
