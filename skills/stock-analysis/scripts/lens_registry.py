"""Load stock-analysis skill lens definitions without external packages."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REQUIRED_FIELDS = {
    "name",
    "chinese_name",
    "core_philosophy",
    "evidence_weight_adjustments",
    "key_questions",
    "red_flags",
    "valuation_preference",
    "risk_focus",
    "analysis_modules_to_emphasize",
    "output_rules",
    "committee_role",
    "committee_synthesis_rules",
}
MODULE_KEYS = {"m1", "m2", "m3", "m4", "m5", "m6"}
DEFAULT_COMMITTEE_MEMBERS = (
    "buffett",
    "munger",
    "duan_yongping",
    "zhang_kun",
    "graham",
    "dalio",
)


def skill_root() -> Path:
    return Path(__file__).resolve().parents[1]


def default_lenses_dir() -> Path:
    return skill_root() / "config" / "lenses"


def _validate_lens(lens_id: str, payload: dict[str, Any]) -> None:
    missing = REQUIRED_FIELDS - payload.keys()
    extra = payload.keys() - REQUIRED_FIELDS
    if missing:
        raise ValueError(f"{lens_id} missing fields: {', '.join(sorted(missing))}")
    if extra:
        raise ValueError(f"{lens_id} unknown fields: {', '.join(sorted(extra))}")
    weights = payload["evidence_weight_adjustments"]
    if not isinstance(weights, dict) or set(weights) != MODULE_KEYS:
        raise ValueError(f"{lens_id} evidence_weight_adjustments must contain m1-m6")
    for key in ("key_questions", "red_flags", "analysis_modules_to_emphasize", "output_rules", "committee_synthesis_rules"):
        if not isinstance(payload[key], list) or not payload[key]:
            raise ValueError(f"{lens_id} {key} must be a non-empty list")


def load_lens_definitions(directory: str | Path | None = None) -> dict[str, dict[str, Any]]:
    lenses_dir = Path(directory) if directory is not None else default_lenses_dir()
    definitions: dict[str, dict[str, Any]] = {}
    for path in sorted(lenses_dir.glob("*.json")):
        lens_id = path.stem
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"{lens_id} definition must be a JSON object")
        _validate_lens(lens_id, payload)
        definitions[lens_id] = payload
    return definitions


def lens_ids(directory: str | Path | None = None) -> tuple[str, ...]:
    return tuple(load_lens_definitions(directory))


def get_lens_definition(lens_id: str, directory: str | Path | None = None) -> dict[str, Any]:
    normalized = lens_id.strip().lower()
    return load_lens_definitions(directory)[normalized]


def get_default_committee_members() -> tuple[str, ...]:
    return DEFAULT_COMMITTEE_MEMBERS
