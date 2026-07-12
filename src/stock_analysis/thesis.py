"""Portable investment-thesis state with explicit facts, risks and invalidation."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def thesis_dir() -> Path:
    return Path(os.environ.get("STOCK_ANALYSIS_THESIS_DIR", "~/.stock_analysis/theses")).expanduser()


def thesis_path(symbol: str) -> Path:
    safe = "".join(char for char in symbol.upper() if char.isalnum() or char in {".", "-"})
    return thesis_dir() / f"{safe}.json"


def create_thesis(company: dict[str, Any]) -> tuple[dict[str, Any], Path]:
    path = thesis_path(str(company["symbol"]))
    created_at = datetime.now(timezone.utc).isoformat()
    evidence = company["_meta"]
    document = {
        "schema_version": "1.0",
        "symbol": company["symbol"],
        "name": company.get("name") or company["symbol"],
        "created_at": created_at,
        "updated_at": created_at,
        "status": "evidence_insufficient" if evidence["missing_modules"] else "under_review",
        "thesis": {
            "why_watch": [],
            "core_assumptions": [],
            "supporting_facts": company.get("financial_facts") or [],
            "counter_evidence": [],
            "key_metrics": [fact["metric"] for fact in company.get("financial_facts") or []],
            "invalidation_conditions": [],
            "valuation_conditions": [],
            "next_review": None,
        },
        "evidence_snapshot": {
            "trade_date": company["trade_date"],
            "coverage": evidence["coverage"],
            "available_modules": evidence["available_modules"],
            "missing_modules": evidence["missing_modules"],
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return document, path


def review_thesis(company: dict[str, Any]) -> tuple[dict[str, Any] | None, Path, list[str]]:
    path = thesis_path(str(company["symbol"]))
    if not path.exists():
        return None, path, ["尚未创建论文；请先运行 thesis-create"]
    document = json.loads(path.read_text(encoding="utf-8"))
    previous = document.get("evidence_snapshot") or {}
    current = company.get("_meta") or {}
    changes: list[str] = []
    if previous.get("trade_date") != company.get("trade_date"):
        changes.append(f"证据日期：{previous.get('trade_date') or '无'} → {company.get('trade_date')}")
    if previous.get("coverage") != current.get("coverage"):
        changes.append(f"证据覆盖：{previous.get('coverage')}% → {current.get('coverage')}%")
    if previous.get("missing_modules") != current.get("missing_modules"):
        changes.append("证据模块可用性发生变化")
    if not changes:
        changes.append("未发现可由当前结构化 Evidence 自动判定的变化")
    document["updated_at"] = datetime.now(timezone.utc).isoformat()
    document["evidence_snapshot"] = {
        "trade_date": company["trade_date"],
        "coverage": current.get("coverage"),
        "available_modules": current.get("available_modules"),
        "missing_modules": current.get("missing_modules"),
    }
    path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return document, path, changes
