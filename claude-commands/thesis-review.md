---
name: thesis-review
description: 将当前 Company Evidence 与持久化论文快照比较。
---

# /thesis-review Claude Code command

将当前 Company Evidence 与持久化论文快照比较。

Run:

```bash
stock-analysis --market thesis-review --symbol <symbol> --emit-evidence
```

区分事实变化、证据覆盖变化和仍需人工判断的论文变化。

Always preserve Evidence Pack source events and state missing evidence explicitly.
