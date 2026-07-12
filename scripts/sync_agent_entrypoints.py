#!/usr/bin/env python3
"""Generate Agent entrypoints from one canonical, checked-in command catalog."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "agent-workflows" / "commands.json"


def rendered(command: dict[str, str], target: str) -> str:
    title = command["id"]
    body = f"""---
name: {title}
description: {command['summary']}
---

# /{title}

{command['summary']}

Run:

```bash
{command['cli']}
```

{command['output']}

Always preserve Evidence Pack source events and state missing evidence explicitly.
"""
    if target == "claude":
        return body.replace(f"# /{title}", f"# /{title} Claude Code command")
    if target == "prompt":
        return body.replace(f"# /{title}", f"# /prompts:{title} Codex custom prompt")
    return body


def destination(command: dict[str, str], target: str) -> Path:
    if target == "skill":
        return ROOT / "codex-skills" / command["id"] / "SKILL.md"
    if target == "prompt":
        return ROOT / "codex-prompts" / f"{command['id']}.md"
    return ROOT / "claude-commands" / f"{command['id']}.md"


def sync(check: bool) -> int:
    commands = json.loads(CATALOG.read_text(encoding="utf-8"))
    stale: list[Path] = []
    for command in commands:
        for target in ("skill", "prompt", "claude"):
            path = destination(command, target)
            expected = rendered(command, target)
            if not path.exists() or path.read_text(encoding="utf-8") != expected:
                stale.append(path)
                if not check:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(expected, encoding="utf-8")
    if stale and check:
        print("Agent entrypoints are out of sync:")
        print("\n".join(str(path.relative_to(ROOT)) for path in stale))
        return 1
    print(f"Synced {len(commands)} canonical workflows.")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    raise SystemExit(sync(parser.parse_args().check))
