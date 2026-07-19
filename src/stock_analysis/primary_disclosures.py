"""Rule-driven extraction of issuer facts from official PDF disclosures."""

from __future__ import annotations

import io
import json
import re
from pathlib import Path
from typing import Any

import requests
from pypdf import PdfReader


def _catalog_dir() -> Path:
    return Path(__file__).with_name("primary_catalog")


def _number(value: str) -> float:
    return float(value.replace(",", ""))


def _extract_document_pages(url: str, pages: set[int]) -> dict[int, str]:
    response = requests.get(url, timeout=30, headers={"User-Agent": "stock-analysis/4.13.0"})
    response.raise_for_status()
    reader = PdfReader(io.BytesIO(response.content))
    return {
        page: re.sub(r"\s+", " ", reader.pages[page - 1].extract_text() or "").strip()
        for page in pages
        if 0 < page <= len(reader.pages)
    }


def extract_catalog_facts(catalog: dict[str, Any], pages_by_document: dict[str, dict[int, str]]) -> dict[str, list[dict[str, Any]]]:
    """Extract configured facts from already decoded pages; useful for deterministic tests."""

    result = {f"C{index}": [] for index in range(1, 9)}
    extracted: dict[str, float] = {}
    for rule in catalog.get("facts") or []:
        text = (pages_by_document.get(rule["document"]) or {}).get(int(rule["page"]), "")
        match = re.search(rule["pattern"], text, flags=re.S)
        if not match:
            continue
        if "constant_on_match" in rule:
            value: Any = rule["constant_on_match"]
        else:
            value = _number(match.group(int(rule.get("group", 1)))) * float(rule.get("multiplier", 1))
        extracted[rule["metric"]] = value if isinstance(value, (int, float)) else 0.0
        document = catalog["documents"][rule["document"]]
        item = {
            "metric": rule["metric"],
            "value": value,
            "period": catalog["period"],
            "published_at": catalog["published_at"],
            "source": catalog["source"],
            "source_type": "issuer_primary_disclosure",
            "confidence": "primary",
            "url": document["url"],
            "page": int(rule["page"]),
            "extraction_method": "official_pdf_regex",
            **(rule.get("extra") or {}),
        }
        result[rule["module"]].append(item)
    for rule in catalog.get("derived_facts") or []:
        numerator = extracted.get(rule["numerator_metric"])
        denominator = extracted.get(rule["denominator_metric"])
        if numerator is None or denominator in (None, 0):
            continue
        if rule["operation"] != "divide_percent":
            continue
        source_fact = next(
            item for items in result.values() for item in items if item["metric"] == rule["numerator_metric"]
        )
        result[rule["module"]].append({
            **source_fact,
            "metric": rule["metric"],
            "value": numerator / denominator * 100,
            "formula": f"{rule['numerator_metric']} / {rule['denominator_metric']} * 100",
            "extraction_method": "derived_from_official_pdf_facts",
        })
    return result


def load_issuer_primary_facts(
    symbol: str,
    trade_date: str,
    *,
    catalog_dir: Path | None = None,
    page_loader: Any = _extract_document_pages,
) -> dict[str, list[dict[str, Any]]]:
    """Load all applicable issuer catalogs; adding an issuer requires no Python change."""

    result = {f"C{index}": [] for index in range(1, 9)}
    root = catalog_dir or _catalog_dir()
    for path in sorted(root.glob(f"{symbol}-*.json")):
        catalog = json.loads(path.read_text(encoding="utf-8"))
        if catalog.get("published_at", "").replace("-", "") > trade_date.replace("-", ""):
            continue
        pages_by_document = {}
        try:
            for document_id, document in catalog["documents"].items():
                pages = {int(rule["page"]) for rule in catalog.get("facts") or [] if rule["document"] == document_id}
                pages_by_document[document_id] = page_loader(document["url"], pages)
        except Exception:
            continue
        extracted = extract_catalog_facts(catalog, pages_by_document)
        for module, facts in extracted.items():
            result[module].extend(facts)
    return result
