"""Claim publication layer from plan sections 1, 2, 4, 7, and 8."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

# Plan sections 1 and 7: source sufficiency is discrete and provenance-derived.
PRIMARY_SOURCE_TYPES = frozenset(
    {
        "issuer_primary_disclosure",
        "primary_disclosure",
        "regulator_primary_xbrl",
        "market_quote",
        "market_valuation_snapshot",
    }
)
SECONDARY_SOURCE_TYPES = frozenset(
    {
        "structured_public_disclosure",
        "secondary_aggregated_financial",
        "public_announcement_index",
        "news_sample",
        "observable_moat_proxy",
    }
)
SOURCE_FINGERPRINT_RE = re.compile(r"^[0-9a-f]{64}$")


class SupportStatus(str, Enum):
    """Discrete evidence-support states for one research claim."""

    STRONGLY_SUPPORTED = "strongly_supported"
    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"
    SPECULATIVE = "speculative"
    CONFLICTED_UNRESOLVED = "conflicted_unresolved"


class MissingEvidenceEffect(str, Enum):
    """How missing evidence affects publication of one claim."""

    NO_MATERIAL_EFFECT = "no_material_effect"
    NARROWS_SCOPE = "narrows_scope"
    BLOCKS_CLAIM = "blocks_claim"
    BLOCKS_ACTION = "blocks_action"


class PublicationDecision(str, Enum):
    """Publication outcome for one research claim."""

    PUBLISH = "publish"
    PUBLISH_NARROWED = "publish_narrowed"
    AUDIT_ONLY = "audit_only"
    BLOCK_ACTION = "block_action"
    BLOCK_REPORT = "block_report"


def _tuple_of_strings(values: Iterable[str], field_name: str) -> tuple[str, ...]:
    normalized = tuple(values)
    if any(not isinstance(value, str) or not value.strip() for value in normalized):
        raise ValueError(f"{field_name} must contain non-empty strings")
    return normalized


def _source_identifier(source_type: str, fingerprint_material: str) -> str:
    fingerprint = hashlib.sha256(fingerprint_material.encode("utf-8")).hexdigest()
    return f"{source_type}@sha256:{fingerprint}"


def _parse_source_identifier(identifier: str) -> tuple[str, str]:
    source_type, separator, fingerprint = identifier.partition("@sha256:")
    if (
        not separator
        or source_type not in PRIMARY_SOURCE_TYPES | SECONDARY_SOURCE_TYPES
        or not SOURCE_FINGERPRINT_RE.fullmatch(fingerprint)
    ):
        raise ValueError(f"invalid strict source identifier: {identifier}")
    return source_type, fingerprint


def _source_identifiers_by_tier(
    identifiers: Iterable[str], *, primary: bool
) -> frozenset[str]:
    allowed = PRIMARY_SOURCE_TYPES if primary else SECONDARY_SOURCE_TYPES
    result = set()
    for identifier in identifiers:
        source_type, _ = _parse_source_identifier(identifier)
        if source_type in allowed:
            result.add(identifier)
    return frozenset(result)


def claim_source_ids(item: dict[str, Any]) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Return deduplicated strict primary and secondary IDs for one evidence item."""

    source_type = str(item.get("source_type") or "").strip().lower()
    if source_type not in PRIMARY_SOURCE_TYPES | SECONDARY_SOURCE_TYPES:
        return (), ()
    fingerprint_material = str(item.get("url") or item.get("source") or "").strip()
    if not fingerprint_material:
        return (), ()
    identifier = _source_identifier(source_type, fingerprint_material)
    if source_type in PRIMARY_SOURCE_TYPES:
        return (identifier,), ()
    return (), (identifier,)


@dataclass(frozen=True)
class ResearchClaim:
    """One auditable claim and the evidence rules governing its publication."""

    claim_id: str
    claim: str
    direction: str
    scope: str
    evidence_ids: tuple[str, ...]
    claim_status: SupportStatus
    applicable_period: str = ""
    conditions: tuple[str, ...] = field(default_factory=tuple)
    invalidators: tuple[str, ...] = field(default_factory=tuple)
    missing_evidence: tuple[str, ...] = field(default_factory=tuple)
    missing_evidence_effect: MissingEvidenceEffect = MissingEvidenceEffect.NO_MATERIAL_EFFECT
    primary_source_ids: tuple[str, ...] = field(default_factory=tuple)
    secondary_source_ids: tuple[str, ...] = field(default_factory=tuple)
    calculation_input_evidence_ids: tuple[str, ...] = field(default_factory=tuple)
    report_blocking_reasons: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        for field_name in ("claim_id", "claim", "direction", "scope"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} must be a non-empty string")
        if not isinstance(self.applicable_period, str):
            raise ValueError("applicable_period must be a string")
        if not isinstance(self.claim_status, SupportStatus):
            object.__setattr__(self, "claim_status", SupportStatus(self.claim_status))
        if not isinstance(self.missing_evidence_effect, MissingEvidenceEffect):
            object.__setattr__(
                self,
                "missing_evidence_effect",
                MissingEvidenceEffect(self.missing_evidence_effect),
            )
        for field_name in (
            "evidence_ids",
            "conditions",
            "invalidators",
            "missing_evidence",
            "primary_source_ids",
            "secondary_source_ids",
            "calculation_input_evidence_ids",
            "report_blocking_reasons",
        ):
            object.__setattr__(self, field_name, _tuple_of_strings(getattr(self, field_name), field_name))

    @property
    def support_status(self) -> SupportStatus:
        """Compatibility alias for consumers that use the support-status wording."""

        return self.claim_status

    @property
    def primary_source_count(self) -> int:
        """Derived count of unique, strictly allowed primary sources."""

        return len(
            {
                _parse_source_identifier(identifier)[1]
                for identifier in _source_identifiers_by_tier(
                    self.primary_source_ids, primary=True
                )
            }
        )

    @property
    def secondary_source_count(self) -> int:
        """Derived count of unique, strictly allowed secondary sources."""

        return len(
            {
                _parse_source_identifier(identifier)[1]
                for identifier in _source_identifiers_by_tier(
                    self.secondary_source_ids, primary=False
                )
            }
        )

    @property
    def has_reproducible_calculation(self) -> bool:
        """A calculation is reproducible only when its input evidence is explicit."""

        return bool(self.calculation_input_evidence_ids)

    def to_dict(self, *, include_decision: bool = True) -> dict[str, Any]:
        """Serialize the claim into a stable, JSON-compatible audit record."""

        payload: dict[str, Any] = {
            "claim_id": self.claim_id,
            "claim": self.claim,
            "direction": self.direction,
            "scope": self.scope,
            "applicable_period": self.applicable_period,
            "evidence_ids": list(self.evidence_ids),
            "claim_status": self.claim_status.value,
            "conditions": list(self.conditions),
            "invalidators": list(self.invalidators),
            "missing_evidence": list(self.missing_evidence),
            "missing_evidence_effect": self.missing_evidence_effect.value,
            "primary_source_ids": list(self.primary_source_ids),
            "secondary_source_ids": list(self.secondary_source_ids),
            "calculation_input_evidence_ids": list(self.calculation_input_evidence_ids),
            "primary_source_count": self.primary_source_count,
            "secondary_source_count": self.secondary_source_count,
            "has_reproducible_calculation": self.has_reproducible_calculation,
            "report_blocking_reasons": list(self.report_blocking_reasons),
        }
        if include_decision:
            payload["publication_decision"] = publication_decision(self).value
        return payload


def validate_claim_evidence_ids(
    claim: ResearchClaim,
    known_evidence_ids: Iterable[str] | None = None,
) -> None:
    """Reject missing, duplicate, or out-of-snapshot evidence references."""

    evidence_ids = claim.evidence_ids
    if len(evidence_ids) != len(set(evidence_ids)):
        raise ValueError(f"{claim.claim_id} contains duplicate evidence_ids")
    if claim.claim_status in {SupportStatus.STRONGLY_SUPPORTED, SupportStatus.SUPPORTED} and not evidence_ids:
        raise ValueError(f"{claim.claim_id} requires evidence_ids for a supported claim")
    if len(claim.primary_source_ids) != len(set(claim.primary_source_ids)):
        raise ValueError(f"{claim.claim_id} contains duplicate primary_source_ids")
    if len(claim.secondary_source_ids) != len(set(claim.secondary_source_ids)):
        raise ValueError(f"{claim.claim_id} contains duplicate secondary_source_ids")
    primary_fingerprints = {_parse_source_identifier(identifier)[1] for identifier in claim.primary_source_ids}
    secondary_fingerprints = {
        _parse_source_identifier(identifier)[1] for identifier in claim.secondary_source_ids
    }
    if primary_fingerprints & secondary_fingerprints:
        raise ValueError(f"{claim.claim_id} source fingerprints cannot occupy both tiers")
    for identifier in claim.primary_source_ids:
        source_type, _ = _parse_source_identifier(identifier)
        if source_type not in PRIMARY_SOURCE_TYPES:
            raise ValueError(f"{claim.claim_id} has a non-primary primary_source_id")
    for identifier in claim.secondary_source_ids:
        source_type, _ = _parse_source_identifier(identifier)
        if source_type not in SECONDARY_SOURCE_TYPES:
            raise ValueError(f"{claim.claim_id} has a non-secondary secondary_source_id")
    calculation_inputs = set(claim.calculation_input_evidence_ids)
    if len(calculation_inputs) != len(claim.calculation_input_evidence_ids):
        raise ValueError(f"{claim.claim_id} contains duplicate calculation_input_evidence_ids")
    unknown_inputs = calculation_inputs - set(evidence_ids)
    if unknown_inputs:
        rendered = ", ".join(sorted(unknown_inputs))
        raise ValueError(f"{claim.claim_id} calculation inputs are not evidence_ids: {rendered}")
    if known_evidence_ids is not None:
        known = set(known_evidence_ids)
        unknown = [evidence_id for evidence_id in evidence_ids if evidence_id not in known]
        if unknown:
            raise ValueError(f"{claim.claim_id} references unknown evidence_ids: {', '.join(unknown)}")


def _meets_support_rule(claim: ResearchClaim) -> bool:
    primary_fingerprints = {
        _parse_source_identifier(identifier)[1] for identifier in claim.primary_source_ids
    }
    secondary_fingerprints = {
        _parse_source_identifier(identifier)[1] for identifier in claim.secondary_source_ids
    }
    if claim.claim_status is SupportStatus.STRONGLY_SUPPORTED:
        independent_sources = len(primary_fingerprints | secondary_fingerprints)
        return independent_sources >= 2 or (
            bool(primary_fingerprints) and claim.has_reproducible_calculation
        )
    if claim.claim_status is SupportStatus.SUPPORTED:
        return (
            bool(primary_fingerprints)
            or len(secondary_fingerprints) >= 2
            or claim.has_reproducible_calculation
        )
    return False


def publication_decision(claim: ResearchClaim) -> PublicationDecision:
    """Apply the rule-based supported-claim publication policy."""

    if claim.report_blocking_reasons:
        return PublicationDecision.BLOCK_REPORT
    try:
        validate_claim_evidence_ids(claim)
    except ValueError:
        return PublicationDecision.AUDIT_ONLY
    if not _meets_support_rule(claim):
        return PublicationDecision.AUDIT_ONLY
    if not claim.applicable_period.strip() or not claim.conditions or not claim.invalidators:
        return PublicationDecision.AUDIT_ONLY
    if claim.missing_evidence_effect is MissingEvidenceEffect.BLOCKS_CLAIM:
        return PublicationDecision.AUDIT_ONLY
    if claim.missing_evidence_effect is MissingEvidenceEffect.BLOCKS_ACTION:
        return PublicationDecision.BLOCK_ACTION
    if claim.missing_evidence_effect is MissingEvidenceEffect.NARROWS_SCOPE:
        return PublicationDecision.PUBLISH_NARROWED
    return PublicationDecision.PUBLISH


def partition_claims(claims: Sequence[ResearchClaim]) -> dict[str, list[dict[str, Any]]]:
    """Split claims into investor-facing and audit-only serialized records."""

    # Plan section 4: report blockers are isolated from ordinary unpublished claims.
    publishable: list[dict[str, Any]] = []
    unpublished: list[dict[str, Any]] = []
    report_blockers: list[dict[str, Any]] = []
    for claim in claims:
        serialized = claim.to_dict()
        decision = publication_decision(claim)
        if decision is PublicationDecision.BLOCK_REPORT:
            report_blockers.append(serialized)
        elif decision in {
            PublicationDecision.PUBLISH,
            PublicationDecision.PUBLISH_NARROWED,
            PublicationDecision.BLOCK_ACTION,
        }:
            publishable.append(serialized)
        else:
            unpublished.append(serialized)
    return {
        "publishable_claims": publishable,
        "unpublished_claims": unpublished,
        "report_blockers": report_blockers,
    }


def _stable_claim_id(prefix: str, payload: Any) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return f"{prefix}:{hashlib.sha256(encoded).hexdigest()[:16]}"


def _render_value(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.4f}".rstrip("0").rstrip(".")
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return str(value)


def _group_support(
    items: Sequence[dict[str, Any]],
) -> tuple[SupportStatus, tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    validations = {
        str(item.get("validation_status") or "").lower()
        for item in items
    }
    if validations & {"conflicted_unresolved", "conflict", "ambiguous"}:
        return SupportStatus.CONFLICTED_UNRESOLVED, (), (), ()
    if validations & {"rejected", "invalid"}:
        return SupportStatus.UNSUPPORTED, (), (), ()

    accepted = [
        item
        for item in items
        if str(item.get("validation_status") or "").lower() == "accepted"
    ]
    primary_ids: list[str] = []
    secondary_ids: list[str] = []
    calculation_inputs: list[str] = []
    for item in accepted:
        primary, secondary = claim_source_ids(item)
        primary_ids.extend(primary)
        secondary_ids.extend(secondary)
        calculation_inputs.extend(
            str(evidence_id)
            for evidence_id in item.get("calculation_input_evidence_ids") or []
            if str(evidence_id).strip()
        )
    primary = tuple(dict.fromkeys(primary_ids))
    secondary = tuple(dict.fromkeys(secondary_ids))
    inputs = tuple(dict.fromkeys(calculation_inputs))
    primary_fingerprints = {_parse_source_identifier(identifier)[1] for identifier in primary}
    secondary_fingerprints = {_parse_source_identifier(identifier)[1] for identifier in secondary}
    if len(primary_fingerprints | secondary_fingerprints) >= 2 or (
        primary_fingerprints and inputs
    ):
        return SupportStatus.STRONGLY_SUPPORTED, primary, secondary, inputs
    if primary_fingerprints or len(secondary_fingerprints) >= 2 or inputs:
        return SupportStatus.SUPPORTED, primary, secondary, inputs
    if accepted:
        return SupportStatus.UNSUPPORTED, primary, secondary, inputs
    return SupportStatus.SPECULATIVE, primary, secondary, inputs


def validated_calculation_inputs(
    item: dict[str, Any],
    evidence_by_id: dict[str, dict[str, Any]],
) -> tuple[str, ...]:
    """Return calculation inputs only when the frozen inputs are comparable."""

    input_ids = tuple(
        dict.fromkeys(
            str(evidence_id)
            for evidence_id in item.get("calculation_input_evidence_ids") or []
            if str(evidence_id).strip()
        )
    )
    if not input_ids:
        return ()
    inputs = [evidence_by_id.get(evidence_id) for evidence_id in input_ids]
    if any(
        row is None
        or str(row.get("validation_status") or "").lower() != "accepted"
        for row in inputs
    ):
        return ()
    rows = [row for row in inputs if row is not None]

    def compatible(field: str) -> bool:
        values = {str(row.get(field)) for row in rows if row.get(field) not in (None, "")}
        output = item.get(field)
        if output not in (None, ""):
            values.add(str(output))
        return len(values) <= 1

    units = {
        (str(row.get("unit") or ""), str(row.get("currency") or ""))
        for row in rows
    }
    output_unit = (str(item.get("unit") or ""), str(item.get("currency") or ""))
    if output_unit != ("", ""):
        units.add(output_unit)
    if not compatible("period") or not compatible("scope") or len(units) > 1:
        return ()
    return input_ids


def compile_metric_claims(
    evidence: dict[str, Any],
    *,
    claim_prefix: str,
) -> tuple[list[ResearchClaim], list[ResearchClaim]]:
    """Compile frozen metric evidence into publishable facts and audit-only gaps."""

    # Plan sections 1, 2, and 7: consistent facts merge before discrete publication.
    publishable: list[ResearchClaim] = []
    unpublished: list[ResearchClaim] = []
    trade_date = str(evidence.get("trade_date") or "unknown")
    modules = evidence.get("modules") or {}
    known_evidence_ids = {
        str(item["evidence_id"])
        for section in modules.values()
        for item in section.get("evidence") or []
        if item.get("evidence_id")
    }
    evidence_by_id = {
        str(item["evidence_id"]): item
        for section in modules.values()
        for item in section.get("evidence") or []
        if item.get("evidence_id")
    }
    grouped: dict[tuple[str, str, str, str, str, str], list[dict[str, Any]]] = {}
    for module, section in modules.items():
        for item in section.get("evidence") or []:
            metric = item.get("metric")
            evidence_id = item.get("evidence_id")
            value = item.get("value")
            if not metric or not evidence_id or value is None:
                continue
            period = str(
                item.get("period")
                or item.get("asof")
                or item.get("published_at")
                or trade_date
            )
            scope = str(item.get("scope") or module)
            unit = str(item.get("unit") or item.get("currency") or "")
            canonical_value = json.dumps(
                value,
                ensure_ascii=False,
                sort_keys=True,
                default=str,
            )
            normalized_item = dict(item)
            normalized_item["calculation_input_evidence_ids"] = list(
                validated_calculation_inputs(item, evidence_by_id)
            )
            key = (str(module), str(metric), period, scope, unit, canonical_value)
            grouped.setdefault(key, []).append(normalized_item)

    for key, items in grouped.items():
        module, metric, period, scope, _, _ = key
        section = modules[module]
        gaps = tuple(str(gap) for gap in section.get("gaps") or [] if str(gap).strip())
        value = items[0]["value"]
        status, primary_ids, secondary_ids, calculation_inputs = _group_support(items)
        evidence_ids = tuple(
            dict.fromkeys(
                [
                    *(str(item["evidence_id"]) for item in items),
                    *calculation_inputs,
                ]
            )
        )
        effect = (
            MissingEvidenceEffect.NARROWS_SCOPE
            if gaps
            else MissingEvidenceEffect.NO_MATERIAL_EFFECT
        )
        claim = ResearchClaim(
            claim_id=_stable_claim_id(claim_prefix, list(key)),
            claim=f"在{period}的已披露口径内，{metric}为{_render_value(value)}。",
            direction="neutral",
            scope=scope,
            evidence_ids=evidence_ids,
            claim_status=status,
            applicable_period=period,
            conditions=("证据对象、期间、单位与计算口径保持一致",),
            invalidators=(f"后续同口径披露修订{metric}",),
            missing_evidence=gaps,
            missing_evidence_effect=effect,
            primary_source_ids=primary_ids,
            secondary_source_ids=secondary_ids,
            calculation_input_evidence_ids=calculation_inputs,
        )
        try:
            validate_claim_evidence_ids(claim, known_evidence_ids)
        except ValueError:
            unpublished.append(claim)
            continue
        decision = publication_decision(claim)
        if decision in {
            PublicationDecision.PUBLISH,
            PublicationDecision.PUBLISH_NARROWED,
            PublicationDecision.BLOCK_ACTION,
        }:
            publishable.append(claim)
        else:
            unpublished.append(claim)

    for module, section in modules.items():
        if section.get("evidence"):
            continue
        gaps = tuple(str(gap) for gap in section.get("gaps") or [] if str(gap).strip())
        for gap in gaps:
            unpublished.append(
                ResearchClaim(
                    claim_id=_stable_claim_id(claim_prefix, [module, gap]),
                    claim=f"{module}相关判断",
                    direction="neutral",
                    scope=str(module),
                    evidence_ids=(),
                    claim_status=SupportStatus.UNSUPPORTED,
                    applicable_period=trade_date,
                    conditions=("取得与研究对象及截止日一致的可核验证据",),
                    invalidators=("相关证据完成验证并达到发布门槛",),
                    missing_evidence=(gap,),
                    missing_evidence_effect=MissingEvidenceEffect.BLOCKS_CLAIM,
                )
            )
    return publishable, unpublished


def _normalized_period(value: Any) -> str:
    return "".join(character for character in str(value or "") if character.isdigit())[:8]


def _is_positive_number(value: Any) -> bool:
    try:
        return float(value) > 0
    except (TypeError, ValueError):
        return False


def build_evidence_integrity_audit(
    modules: dict[str, dict[str, Any]],
    *,
    requested_symbol: str,
    resolved_symbol: str | None,
    trade_date: str,
) -> dict[str, Any]:
    """Build production safety metadata for the plan-section-8 exceptions."""

    requested = requested_symbol.strip().upper()
    resolved = str(resolved_symbol or "").strip().upper()
    identity_status = (
        "unverified"
        if not resolved
        else "matched"
        if resolved == requested
        else "conflict"
    )
    cutoff = _normalized_period(trade_date)
    violations: list[dict[str, Any]] = []
    basis_conflicts: list[dict[str, Any]] = []
    primary_conflicts: list[dict[str, Any]] = []
    grouped: dict[tuple[str, str, str, str], list[dict[str, Any]]] = {}

    for module, section in modules.items():
        for item in section.get("evidence") or []:
            evidence_id = str(item.get("evidence_id") or "")
            published = _normalized_period(item.get("published_at") or item.get("notice_date"))
            if cutoff and published and published > cutoff:
                violations.append(
                    {"evidence_id": evidence_id, "field": "published_at", "value": published}
                )
            metric = str(item.get("metric") or "")
            asof_value = _normalized_period(item.get("asof"))
            if cutoff and metric.endswith("_asof"):
                asof_value = _normalized_period(item.get("value")) or asof_value
            if cutoff and asof_value and asof_value > cutoff:
                violations.append(
                    {"evidence_id": evidence_id, "field": "effective_period", "value": asof_value}
                )
            if str(item.get("validation_status") or "").lower() != "accepted":
                continue
            key = (
                str(module),
                metric,
                str(item.get("period") or item.get("asof") or ""),
                str(item.get("scope") or module),
            )
            grouped.setdefault(key, []).append(item)

    for key, items in grouped.items():
        currencies = {str(item.get("currency")) for item in items if item.get("currency")}
        units = {str(item.get("unit")) for item in items if item.get("unit")}
        if len(currencies) > 1 or len(units) > 1:
            basis_conflicts.append(
                {
                    "module": key[0],
                    "metric": key[1],
                    "period": key[2],
                    "currencies": sorted(currencies),
                    "units": sorted(units),
                    "evidence_ids": [str(item.get("evidence_id") or "") for item in items],
                }
            )
        primary_items = [item for item in items if claim_source_ids(item)[0]]
        values = {
            json.dumps(item.get("value"), ensure_ascii=False, sort_keys=True, default=str)
            for item in primary_items
        }
        if len(primary_items) >= 2 and len(values) > 1:
            primary_conflicts.append(
                {
                    "module": key[0],
                    "metric": key[1],
                    "period": key[2],
                    "evidence_ids": [
                        str(item.get("evidence_id") or "") for item in primary_items
                    ],
                }
            )

    return {
        "identity_validation": {
            "status": identity_status,
            "requested_symbol": requested,
            "resolved_symbol": resolved or None,
        },
        "basis_conflicts": basis_conflicts,
        "primary_conflicts": primary_conflicts,
        "publication_cutoff_audit": {
            "trade_date": trade_date,
            "violations": violations,
        },
    }


def evaluate_safety_gate(
    evidence: dict[str, Any],
    publishable_claims: Sequence[dict[str, Any]],
    *,
    asset_type: str,
    report_blockers: Sequence[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Evaluate only explicit research-integrity and action-feasibility failures."""

    # Plan section 8: explicit report blockers outrank action-level limitations.
    issues: list[dict[str, str]] = []
    meta = evidence.get("_meta") or {}

    def add(code: str, decision: PublicationDecision, reason: str) -> None:
        issues.append({"code": code, "decision": decision.value, "reason": reason})

    identity_status = (meta.get("identity_validation") or {}).get("status")
    if not str(evidence.get("symbol") or "").strip() or identity_status in {
        "conflict",
        "unverified",
    }:
        add("IDENTITY_CONFLICT", PublicationDecision.BLOCK_REPORT, "研究对象身份无法确认。")
    if meta.get("basis_conflicts"):
        add("BASIS_CONFLICT", PublicationDecision.BLOCK_REPORT, "报告期、币种或单位存在未解决冲突。")
    if meta.get("primary_conflicts"):
        add("PRIMARY_CONFLICT", PublicationDecision.BLOCK_REPORT, "关键一手披露存在未解决冲突。")
    if (meta.get("publication_cutoff_audit") or {}).get("violations"):
        add("LOOKAHEAD_BIAS", PublicationDecision.BLOCK_REPORT, "发布命题引用了研究截止日后的证据。")
    if report_blockers:
        add("CLAIM_BLOCKS_REPORT", PublicationDecision.BLOCK_REPORT, "命题层存在重大安全阻断。")
    if not publishable_claims:
        add("NO_SUPPORTED_CLAIMS", PublicationDecision.BLOCK_REPORT, "当前问题没有可发布命题。")
    if any(
        claim.get("publication_decision") == PublicationDecision.BLOCK_ACTION.value
        for claim in publishable_claims
    ):
        add("CLAIM_BLOCKS_ACTION", PublicationDecision.BLOCK_ACTION, "可发布研究结论不具备交易行动条件。")

    metric_items = [
        item
        for section in (evidence.get("modules") or {}).values()
        for item in section.get("evidence") or []
        if item.get("metric")
    ]
    metrics = {
        str(item.get("metric")): item.get("value")
        for item in metric_items
    }
    trade_period = _normalized_period(evidence.get("trade_date"))
    current_metrics = {
        str(item.get("metric")): item.get("value")
        for item in metric_items
        if str(item.get("validation_status") or "").lower() == "accepted"
        and _normalized_period(
            item.get("period") or item.get("asof") or item.get("trade_date")
        )
        == trade_period
    }
    if asset_type == "company":
        if not _is_positive_number(current_metrics.get("market_quote")):
            add("PRICE_UNAVAILABLE", PublicationDecision.BLOCK_ACTION, "当前价格不可得，估值与行动输出被阻断。")
        if not _is_positive_number(current_metrics.get("total_market_cap")):
            add("MARKET_CAP_UNAVAILABLE", PublicationDecision.BLOCK_ACTION, "总市值不可得，反向估值与行动输出被阻断。")
    else:
        price_rows = (evidence.get("price_volume") or {}).get("rows") or []
        latest_market = (evidence.get("premium_discount") or {}).get("latest") or {}
        latest_price = next(
            (
                row.get("close")
                for row in reversed(price_rows)
                if _normalized_period(row.get("date") or row.get("trade_date")) == trade_period
                and _is_positive_number(row.get("close"))
            ),
            None,
        )
        if latest_price is None and _normalized_period(
            latest_market.get("date") or latest_market.get("trade_date") or latest_market.get("asof")
        ) == trade_period:
            latest_price = latest_market.get("close") or latest_market.get("price")
        if not _is_positive_number(latest_price):
            add("PRICE_UNAVAILABLE", PublicationDecision.BLOCK_ACTION, "场内价格不可得，估值与行动输出被阻断。")

    execution = evidence.get("execution_cost_model") or {}
    execution_status = execution.get("model_status") or metrics.get("execution_cost_model_status")
    if execution_status != "scenario_complete":
        add("EXECUTION_UNAVAILABLE", PublicationDecision.BLOCK_ACTION, "流动性或交易成本输入不完整，交易行动被阻断。")

    decisions = {item["decision"] for item in issues}
    if PublicationDecision.BLOCK_REPORT.value in decisions:
        decision = PublicationDecision.BLOCK_REPORT
    elif PublicationDecision.BLOCK_ACTION.value in decisions:
        decision = PublicationDecision.BLOCK_ACTION
    else:
        decision = PublicationDecision.PUBLISH
    return {"decision": decision.value, "issues": issues}


def build_claim_audit_artifacts(
    snapshot: dict[str, Any],
    opinions: dict[str, dict[str, Any]],
    committee: dict[str, Any],
) -> dict[str, Any]:
    """Build the four fixed audit artifacts required by plan section 4."""

    evidence = snapshot["evidence"]
    evidence_rows = []
    for module, section in (evidence.get("modules") or {}).items():
        for item in section.get("evidence") or []:
            if not item.get("evidence_id"):
                continue
            evidence_rows.append(
                {
                    "evidence_id": item["evidence_id"],
                    "module": module,
                    "metric": item.get("metric"),
                    "period": item.get("period") or item.get("asof") or evidence.get("trade_date"),
                    "source": item.get("source"),
                    "source_type": item.get("source_type"),
                    "validation_status": item.get("validation_status") or item.get("confidence"),
                }
            )
    publishable = list(committee.get("publishable_claims") or [])
    report_blockers = list(committee.get("report_blockers") or [])
    unpublished_by_id: dict[str, dict[str, Any]] = {}
    for opinion in opinions.values():
        for item in opinion.get("unpublished_questions") or []:
            item_id = str(item.get("claim_id") or item.get("question_id"))
            unpublished_by_id.setdefault(item_id, item)
    unpublished = list(unpublished_by_id.values())
    safety_gate = committee.get("safety_gate") or {}
    return {
        "evidence_manifest": {
            "schema_version": "1.0",
            "evidence_snapshot_id": snapshot["snapshot_id"],
            "symbol": evidence.get("symbol"),
            "trade_date": evidence.get("trade_date"),
            "evidence": evidence_rows,
        },
        "claim_ledger": {
            "schema_version": "1.0",
            "evidence_snapshot_id": snapshot["snapshot_id"],
            "publishable_claims": publishable,
            "report_blockers": report_blockers,
            "unpublished_claims": unpublished,
            "safety_gate": safety_gate,
        },
        "coverage_report": {
            "schema_version": "1.0",
            "coverage": (evidence.get("_meta") or {}).get("coverage"),
            "available_modules": (evidence.get("_meta") or {}).get("available_modules") or [],
            "missing_modules": (evidence.get("_meta") or {}).get("missing_modules") or [],
            "source_events": (evidence.get("_meta") or {}).get("source_events") or [],
            "identity_validation": (evidence.get("_meta") or {}).get("identity_validation"),
            "basis_conflicts": (evidence.get("_meta") or {}).get("basis_conflicts") or [],
            "primary_conflicts": (evidence.get("_meta") or {}).get("primary_conflicts") or [],
            "publication_cutoff_audit": (
                (evidence.get("_meta") or {}).get("publication_cutoff_audit") or {}
            ),
            "narrowed_claim_ids": [
                claim["claim_id"]
                for claim in publishable
                if claim.get("missing_evidence_effect") == MissingEvidenceEffect.NARROWS_SCOPE.value
            ],
        },
        "unpublished_claims": {
            "schema_version": "1.0",
            "evidence_snapshot_id": snapshot["snapshot_id"],
            "claims": unpublished,
        },
    }
