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
