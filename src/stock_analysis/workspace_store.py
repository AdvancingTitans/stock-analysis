"""Shared filesystem primitives for recoverable research workspaces."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any


def research_root() -> Path:
    return Path(os.environ.get("STOCK_ANALYSIS_RESEARCH_DIR", "~/.stock_analysis/research")).expanduser()


def safe_symbol(symbol: str) -> str:
    return "".join(char for char in symbol.upper() if char.isalnum() or char in {".", "-"})


def content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write(content)
        os.replace(temporary, path)
    except Exception:
        Path(temporary).unlink(missing_ok=True)
        raise


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _generated_name(name: str) -> str:
    path = Path(name)
    return f"{path.stem}.generated{path.suffix}"


def _next_generated_path(workspace: Path, canonical_name: str, protected: Path) -> Path:
    canonical = Path(canonical_name)
    candidate = workspace / _generated_name(canonical_name)
    if candidate != protected and not candidate.exists():
        return candidate
    index = 2
    while True:
        candidate = workspace / f"{canonical.stem}.generated-{index}{canonical.suffix}"
        if candidate != protected and not candidate.exists():
            return candidate
        index += 1


def write_artifact(
    workspace: Path,
    canonical_name: str,
    content: str,
    previous: dict[str, Any] | None,
    generated_at: str,
) -> dict[str, str]:
    previous = previous or {}
    previous_name = str(previous.get("path") or canonical_name)
    target = workspace / previous_name
    previous_hash = str(previous.get("sha256") or "")
    current_hash = content_hash(target.read_text(encoding="utf-8")) if target.exists() else ""
    manually_changed = bool(target.exists() and previous_hash and current_hash != previous_hash)
    unmanaged_content = bool(target.exists() and not previous_hash and current_hash != content_hash(content))
    if manually_changed or unmanaged_content:
        # ponytail: preserve manual edits; a future UI can offer an explicit three-way merge.
        target = _next_generated_path(workspace, canonical_name, target)
    elif not previous_hash:
        target = workspace / canonical_name
    atomic_write(target, content)
    return {"path": target.name, "sha256": content_hash(content), "generated_at": generated_at}


def previous_workspace(symbol_dir: Path, trade_date: str) -> dict[str, Any]:
    candidates = (
        sorted(
            (path for path in symbol_dir.iterdir() if path.is_dir() and path.name < trade_date),
            key=lambda path: path.name,
            reverse=True,
        )
        if symbol_dir.exists()
        else []
    )
    for candidate in candidates:
        manifest = load_json(candidate / "workspace.json")
        if manifest:
            return manifest
    return {}
