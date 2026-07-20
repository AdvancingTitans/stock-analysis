---
name: price-move
description: 把量价、新闻样本和未知部分分开，审慎解释异动。
---

# /price-move Claude Code command

把量价、新闻样本和未知部分分开，审慎解释异动。

Run:

```bash
stock-analysis --market price-move --symbol <symbol> --emit-evidence
```

不能把单条新闻或同日相关性断言为价格主因。

Always preserve Evidence Pack source events and state missing evidence explicitly.
If Company Evidence marks agent_primary_evidence_reach as recommended, invoke the bundled
stock-analysis-primary-evidence-reach Skill, follow primary_evidence_requests, and rerun with
--primary-evidence-file. Agent Reach is optional because the bundled fallback can use host web/PDF tools.
