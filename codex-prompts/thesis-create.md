---
name: thesis-create
description: 为一个标的创建本地、可审计的投资论文骨架。
---

# /prompts:thesis-create Codex custom prompt

为一个标的创建本地、可审计的投资论文骨架。

Run:

```bash
stock-analysis --market thesis-create --symbol <symbol> --emit-evidence
```

只写入可验证事实；假设、反证与失效条件保持为空直到用户或一手资料补充。

Always preserve Evidence Pack source events and state missing evidence explicitly.
