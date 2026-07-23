---
name: research-workspace
description: 为股票或基金生成可恢复、可审计的机构化研究工作区。
---

# /research-workspace Claude Code command

为股票或基金生成可恢复、可审计的机构化研究工作区。

Run:

```bash
stock-analysis --market research --symbol <symbol> [--asset-type company|fund]
```

股票冻结 C1–C8 Company Evidence，基金冻结 F1–F8 Fund Evidence；lens 与 committee 消费同一 snapshot_id，最终报告只发布通过离散证据规则的 publishable_claims，普通缺口与未发布命题保留在四类审计 JSON。

For research-workspace investor reports, use only publishable_claims. Keep ordinary missing evidence and unpublished questions in evidence_manifest.json, claim_ledger.json, coverage_report.json, and unpublished_claims.json; never turn absence of evidence into a bearish, neutral, conservative, or wait-and-see conclusion.
If Company Evidence marks agent_primary_evidence_reach as recommended, invoke the bundled
stock-analysis-primary-evidence-reach Skill, follow primary_evidence_requests, and rerun with
--primary-evidence-file. Agent Reach is optional because the bundled fallback can use host web/PDF tools.
