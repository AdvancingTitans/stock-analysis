---
name: price-move
description: 把量价、新闻样本和未知部分分开，审慎解释异动。
---

# /prompts:price-move Codex custom prompt

把量价、新闻样本和未知部分分开，审慎解释异动。

Run:

```bash
stock-analysis --market price-move --symbol <symbol> --emit-evidence
```

不能把单条新闻或同日相关性断言为价格主因。

Always preserve Evidence Pack source events and state missing evidence explicitly.
