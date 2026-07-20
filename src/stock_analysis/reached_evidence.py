"""Validate Agent-reached issuer-primary evidence before Company C1-C8 use."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .normalize import normalize_code


def load_reached_primary_evidence(
    path: str | Path,
    *,
    symbol: str,
    trade_date: str,
) -> dict[str, list[dict[str, Any]]]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("schema_version") != "1.0":
        raise ValueError("primary evidence file must use schema_version 1.0")
    if normalize_code(str(value.get("symbol") or "")) != normalize_code(symbol):
        raise ValueError("primary evidence symbol does not match requested symbol")
    result = {f"C{index}": [] for index in range(1, 9)}
    for index, raw in enumerate(value.get("items") or []):
        if not isinstance(raw, dict):
            raise ValueError(f"primary evidence item {index} must be an object")
        module = str(raw.get("module") or "")
        if module not in result:
            raise ValueError(f"primary evidence item {index} has invalid module")
        published_at = str(raw.get("published_at") or "").replace("-", "")
        if len(published_at) != 8 or not published_at.isdigit() or published_at > trade_date:
            raise ValueError(f"primary evidence item {index} violates publication-date cutoff")
        url = str(raw.get("url") or "")
        parsed = urlparse(url)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ValueError(f"primary evidence item {index} requires an HTTPS original-document URL")
        metric = str(raw.get("metric") or "").strip()
        period = str(raw.get("period") or "").strip()
        source = str(raw.get("source") or "").strip()
        if not metric or not period or not source or "value" not in raw:
            raise ValueError(f"primary evidence item {index} misses metric, period, value, or source")
        fingerprint = hashlib.sha256(
            json.dumps(
                {"symbol": normalize_code(symbol), "metric": metric, "period": period, "value": raw["value"], "url": url},
                ensure_ascii=False,
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()[:16]
        result[module].append(
            {
                "metric": metric,
                "period": period,
                "value": raw["value"],
                "currency": raw.get("currency"),
                "source": source,
                "source_type": "issuer_primary_disclosure",
                "url": url,
                "page": raw.get("page"),
                "published_at": published_at,
                "confidence": "primary",
                "validation_status": "conditional",
                "retrieval_method": str(value.get("retrieval_method") or "agent_primary_evidence_reach"),
                "extraction_note": raw.get("extraction_note"),
                "evidence_fingerprint": fingerprint,
            }
        )
    return result
