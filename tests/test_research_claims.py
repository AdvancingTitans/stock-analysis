import pytest

from stock_analysis.research_claims import (
    MissingEvidenceEffect,
    PublicationDecision,
    ResearchClaim,
    SupportStatus,
    build_claim_audit_artifacts,
    build_evidence_integrity_audit,
    claim_source_ids,
    compile_metric_claims,
    evaluate_safety_gate,
    partition_claims,
    publication_decision,
    validate_claim_evidence_ids,
)

PRIMARY_SOURCE_ID = claim_source_ids(
    {
        "source_type": "issuer_primary_disclosure",
        "url": "https://example.test/annual-report.pdf",
    }
)[0][0]
SECONDARY_SOURCE_ID = claim_source_ids(
    {
        "source_type": "structured_public_disclosure",
        "url": "https://example.test/structured-disclosure",
    }
)[1][0]
SECONDARY_SOURCE_ID_2 = claim_source_ids(
    {
        "source_type": "news_sample",
        "url": "https://example.test/news-sample",
    }
)[1][0]


def _claim(**overrides):
    values = {
        "claim_id": "C-QUALITY-001",
        "claim": "已披露业务的现金实现质量保持稳定",
        "direction": "bullish",
        "scope": "已披露业务",
        "evidence_ids": ("EV-OCF-001", "EV-REVENUE-001"),
        "claim_status": SupportStatus.SUPPORTED,
        "applicable_period": "2026Q1",
        "conditions": ("经营现金流口径保持一致",),
        "invalidators": ("经营现金流转负",),
        "missing_evidence": (),
        "missing_evidence_effect": MissingEvidenceEffect.NO_MATERIAL_EFFECT,
        "primary_source_ids": (PRIMARY_SOURCE_ID,),
        "secondary_source_ids": (SECONDARY_SOURCE_ID,),
        "calculation_input_evidence_ids": (),
        "report_blocking_reasons": (),
    }
    values.update(overrides)
    return ResearchClaim(**values)


def test_support_status_has_exactly_five_discrete_states():
    assert {status.value for status in SupportStatus} == {
        "strongly_supported",
        "supported",
        "unsupported",
        "speculative",
        "conflicted_unresolved",
    }


def test_missing_evidence_effect_has_exactly_four_states():
    assert {effect.value for effect in MissingEvidenceEffect} == {
        "no_material_effect",
        "narrows_scope",
        "blocks_claim",
        "blocks_action",
    }


def test_publication_decision_has_exactly_five_outcomes():
    assert set(PublicationDecision.__members__) == {
        "PUBLISH",
        "PUBLISH_NARROWED",
        "AUDIT_ONLY",
        "BLOCK_ACTION",
        "BLOCK_REPORT",
    }


@pytest.mark.parametrize(
    ("claim_status", "expected"),
    [
        (SupportStatus.STRONGLY_SUPPORTED, PublicationDecision.PUBLISH),
        (SupportStatus.SUPPORTED, PublicationDecision.PUBLISH),
        (SupportStatus.UNSUPPORTED, PublicationDecision.AUDIT_ONLY),
        (SupportStatus.SPECULATIVE, PublicationDecision.AUDIT_ONLY),
        (SupportStatus.CONFLICTED_UNRESOLVED, PublicationDecision.AUDIT_ONLY),
    ],
)
def test_only_supported_statuses_are_publishable(claim_status, expected):
    assert publication_decision(_claim(claim_status=claim_status)) is expected


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        (
            {
                "primary_source_ids": (),
                "secondary_source_ids": (SECONDARY_SOURCE_ID, SECONDARY_SOURCE_ID_2),
            },
            PublicationDecision.PUBLISH,
        ),
        (
            {
                "evidence_ids": ("EV-OCF-001",),
                "primary_source_ids": (PRIMARY_SOURCE_ID,),
                "secondary_source_ids": (),
                "calculation_input_evidence_ids": ("EV-OCF-001",),
            },
            PublicationDecision.PUBLISH,
        ),
        (
            {
                "evidence_ids": ("EV-OCF-001",),
                "primary_source_ids": (PRIMARY_SOURCE_ID,),
                "secondary_source_ids": (),
                "calculation_input_evidence_ids": (),
            },
            PublicationDecision.AUDIT_ONLY,
        ),
    ],
)
def test_strongly_supported_requires_two_sources_or_primary_plus_calculation(overrides, expected):
    claim = _claim(claim_status=SupportStatus.STRONGLY_SUPPORTED, **overrides)

    assert publication_decision(claim) is expected


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        (
            {
                "evidence_ids": ("EV-OCF-001",),
                "primary_source_ids": (PRIMARY_SOURCE_ID,),
                "secondary_source_ids": (),
            },
            PublicationDecision.PUBLISH,
        ),
        (
            {
                "primary_source_ids": (),
                "secondary_source_ids": (SECONDARY_SOURCE_ID, SECONDARY_SOURCE_ID_2),
            },
            PublicationDecision.PUBLISH,
        ),
        (
            {
                "evidence_ids": ("EV-OCF-001",),
                "primary_source_ids": (),
                "secondary_source_ids": (),
                "calculation_input_evidence_ids": ("EV-OCF-001",),
            },
            PublicationDecision.PUBLISH,
        ),
        (
            {
                "evidence_ids": ("EV-OCF-001",),
                "primary_source_ids": (),
                "secondary_source_ids": (SECONDARY_SOURCE_ID,),
            },
            PublicationDecision.AUDIT_ONLY,
        ),
    ],
)
def test_supported_requires_primary_two_secondary_or_reproducible_calculation(overrides, expected):
    claim = _claim(**overrides)

    assert publication_decision(claim) is expected


def test_two_evidence_items_from_one_source_are_not_strongly_supported():
    claim = _claim(
        claim_status=SupportStatus.STRONGLY_SUPPORTED,
        primary_source_ids=(),
        secondary_source_ids=(SECONDARY_SOURCE_ID,),
    )

    assert len(claim.evidence_ids) == 2
    assert publication_decision(claim) is PublicationDecision.AUDIT_ONLY


def test_not_primary_source_type_does_not_count_as_primary():
    evidence = {
        "trade_date": "20260710",
        "modules": {
            "C2": {
                "available": True,
                "evidence": [
                    {
                        "evidence_id": "EV-NOT-PRIMARY",
                        "metric": "operating_cash_flow",
                        "value": 100,
                        "source": "derived-fixture",
                        "source_type": "not_primary",
                        "confidence": "not_primary",
                        "validation_status": "accepted",
                    }
                ],
                "gaps": [],
            }
        },
    }

    publishable, unpublished = compile_metric_claims(evidence, claim_prefix="company")

    assert publishable == []
    assert unpublished[0].primary_source_count == 0
    assert publication_decision(unpublished[0]) is PublicationDecision.AUDIT_ONLY


def test_reproducible_claim_requires_explicit_input_evidence_ids():
    claim = _claim(
        evidence_ids=("EV-OCF-001",),
        primary_source_ids=(),
        secondary_source_ids=(),
        calculation_input_evidence_ids=(),
    )

    assert claim.has_reproducible_calculation is False
    assert publication_decision(claim) is PublicationDecision.AUDIT_ONLY


def test_reproducible_claim_accepts_referenced_input_evidence_ids():
    claim = _claim(
        evidence_ids=("EV-OCF-001",),
        primary_source_ids=(),
        secondary_source_ids=(),
        calculation_input_evidence_ids=("EV-OCF-001",),
    )

    assert claim.has_reproducible_calculation is True
    assert publication_decision(claim) is PublicationDecision.PUBLISH


@pytest.mark.parametrize(("input_period", "published"), [("2026Q1", True), ("2025Q4", False)])
def test_compiled_calculation_requires_comparable_validated_inputs(input_period, published):
    evidence = {
        "trade_date": "20260710",
        "modules": {
            "C2": {
                "available": True,
                "evidence": [
                    {
                        "evidence_id": "EV-INPUT",
                        "metric": "revenue",
                        "period": input_period,
                        "scope": "consolidated",
                        "currency": "CNY",
                        "value": 100,
                        "source": "issuer-filing",
                        "source_type": "primary_disclosure",
                        "validation_status": "accepted",
                    },
                    {
                        "evidence_id": "EV-CALC",
                        "metric": "revenue_ratio",
                        "period": "2026Q1",
                        "scope": "consolidated",
                        "currency": "CNY",
                        "value": 1.2,
                        "formula": "revenue / baseline",
                        "calculation_input_evidence_ids": ["EV-INPUT"],
                        "validation_status": "accepted",
                    },
                ],
                "gaps": [],
            }
        },
    }

    publishable, unpublished = compile_metric_claims(evidence, claim_prefix="company")
    published_metrics = {claim.claim for claim in publishable}
    unpublished_metrics = {claim.claim for claim in unpublished}

    assert ("revenue_ratio" in " ".join(published_metrics)) is published
    assert ("revenue_ratio" in " ".join(unpublished_metrics)) is (not published)


@pytest.mark.parametrize(
    ("effect", "expected"),
    [
        (MissingEvidenceEffect.NO_MATERIAL_EFFECT, PublicationDecision.PUBLISH),
        (MissingEvidenceEffect.NARROWS_SCOPE, PublicationDecision.PUBLISH_NARROWED),
        (MissingEvidenceEffect.BLOCKS_CLAIM, PublicationDecision.AUDIT_ONLY),
        (MissingEvidenceEffect.BLOCKS_ACTION, PublicationDecision.BLOCK_ACTION),
    ],
)
def test_missing_evidence_effect_controls_publication_without_scoring(effect, expected):
    claim = _claim(
        missing_evidence=("分产品季度销量",),
        missing_evidence_effect=effect,
    )

    assert publication_decision(claim) is expected


def test_identity_conflict_blocks_the_entire_report():
    claim = _claim(
        claim_status=SupportStatus.STRONGLY_SUPPORTED,
        report_blocking_reasons=("证券身份冲突",),
    )

    assert publication_decision(claim) is PublicationDecision.BLOCK_REPORT


def test_missing_evidence_never_changes_a_supported_claim_to_bearish():
    claim = _claim(
        missing_evidence=("分产品季度销量",),
        missing_evidence_effect=MissingEvidenceEffect.NARROWS_SCOPE,
    )

    assert publication_decision(claim) is PublicationDecision.PUBLISH_NARROWED
    assert claim.direction == "bullish"


def test_supported_claim_without_evidence_reference_is_audit_only():
    claim = _claim(evidence_ids=())

    assert publication_decision(claim) is PublicationDecision.AUDIT_ONLY


@pytest.mark.parametrize(
    ("field", "value"),
    [("applicable_period", ""), ("conditions", ()), ("invalidators", ())],
)
def test_supported_claim_without_verifiable_conditions_is_audit_only(field, value):
    claim = _claim(**{field: value})

    assert publication_decision(claim) is PublicationDecision.AUDIT_ONLY


def test_claim_evidence_ids_must_exist_in_the_frozen_snapshot():
    claim = _claim(evidence_ids=("EV-OCF-001", "EV-404"))

    with pytest.raises(ValueError, match="EV-404"):
        validate_claim_evidence_ids(claim, {"EV-OCF-001", "EV-REVENUE-001"})


def test_claim_evidence_id_validation_accepts_known_ids():
    claim = _claim()

    validate_claim_evidence_ids(claim, {"EV-OCF-001", "EV-REVENUE-001"})


def test_missing_company_valuation_inputs_block_action_not_report():
    evidence = {
        "symbol": "600519",
        "trade_date": "20260710",
        "modules": {"C2": {"evidence": [], "gaps": []}},
        "_meta": {},
    }

    gate = evaluate_safety_gate(evidence, [_claim().to_dict()], asset_type="company")

    assert gate["decision"] == PublicationDecision.BLOCK_ACTION.value
    assert {issue["code"] for issue in gate["issues"]} >= {
        "PRICE_UNAVAILABLE",
        "MARKET_CAP_UNAVAILABLE",
    }


def test_claim_level_blocks_action_propagates_to_the_report_gate():
    evidence = {
        "symbol": "600519",
        "trade_date": "20260710",
        "modules": {
            "C6": {
                "evidence": [
                    {"metric": "market_quote", "value": 1500},
                    {"metric": "total_market_cap", "value": 1_800_000_000_000},
                ],
                "gaps": [],
            },
            "C7": {
                "evidence": [{"metric": "execution_cost_model_status", "value": "scenario_complete"}],
                "gaps": [],
            },
        },
        "_meta": {},
    }
    claim = _claim(
        missing_evidence_effect=MissingEvidenceEffect.BLOCKS_ACTION,
        missing_evidence=("用户订单参数",),
    ).to_dict()

    gate = evaluate_safety_gate(evidence, [claim], asset_type="company")

    assert gate["decision"] == PublicationDecision.BLOCK_ACTION.value
    assert any(issue["code"] == "CLAIM_BLOCKS_ACTION" for issue in gate["issues"])


def test_claim_level_blocks_report_propagates_separately_from_publishable_claims():
    blocker = _claim(report_blocking_reasons=("证券身份冲突",))
    partitioned = partition_claims([blocker])
    evidence = {
        "symbol": "600519",
        "trade_date": "20260710",
        "modules": {
            "C6": {
                "evidence": [
                    {"metric": "market_quote", "value": 1500},
                    {"metric": "total_market_cap", "value": 1_800_000_000_000},
                ],
                "gaps": [],
            }
        },
        "execution_cost_model": {"model_status": "scenario_complete"},
        "_meta": {},
    }

    gate = evaluate_safety_gate(
        evidence,
        [_claim().to_dict()],
        asset_type="company",
        report_blockers=partitioned["report_blockers"],
    )

    assert partitioned["publishable_claims"] == []
    assert partitioned["report_blockers"][0]["claim_id"] == blocker.claim_id
    assert gate["decision"] == PublicationDecision.BLOCK_REPORT.value
    assert any(issue["code"] == "CLAIM_BLOCKS_REPORT" for issue in gate["issues"])


@pytest.mark.parametrize(
    ("metric", "value", "validation_status"),
    [
        ("market_quote", -1, "accepted"),
        ("market_quote", 1500, "expired"),
        ("total_market_cap", -1, "accepted"),
        ("total_market_cap", 1_800_000_000_000, "expired"),
    ],
)
def test_invalid_or_expired_company_price_basis_blocks_action(metric, value, validation_status):
    defaults = {
        "market_quote": {"value": 1500, "period": "20260710", "validation_status": "accepted"},
        "total_market_cap": {"value": 1_800_000_000_000, "period": "20260710", "validation_status": "accepted"},
    }
    defaults[metric].update(value=value, validation_status=validation_status)
    evidence = {
        "symbol": "600519",
        "trade_date": "20260710",
        "modules": {
            "C6": {
                "evidence": [
                    {"metric": name, **payload}
                    for name, payload in defaults.items()
                ],
                "gaps": [],
            }
        },
        "execution_cost_model": {"model_status": "scenario_complete"},
        "_meta": {},
    }

    gate = evaluate_safety_gate(evidence, [_claim().to_dict()], asset_type="company")

    assert gate["decision"] == PublicationDecision.BLOCK_ACTION.value


def test_current_positive_company_valuation_basis_does_not_block_action():
    evidence = {
        "symbol": "600519",
        "trade_date": "20260710",
        "modules": {
            "C6": {
                "evidence": [
                    {"metric": "market_quote", "value": 1500, "period": "20260710", "validation_status": "accepted"},
                    {"metric": "total_market_cap", "value": 1_800_000_000_000, "period": "20260710", "validation_status": "accepted"},
                ],
                "gaps": [],
            }
        },
        "execution_cost_model": {"model_status": "scenario_complete"},
        "_meta": {},
    }

    gate = evaluate_safety_gate(evidence, [_claim().to_dict()], asset_type="company")

    assert gate["decision"] == PublicationDecision.PUBLISH.value


def test_missing_fund_price_blocks_action():
    evidence = {
        "symbol": "512480",
        "trade_date": "20260710",
        "price_volume": {"rows": []},
        "premium_discount": {"latest": {}},
        "execution_cost_model": {"model_status": "scenario_complete"},
        "_meta": {},
    }

    gate = evaluate_safety_gate(evidence, [_claim().to_dict()], asset_type="fund")

    assert gate["decision"] == PublicationDecision.BLOCK_ACTION.value
    assert any(issue["code"] == "PRICE_UNAVAILABLE" for issue in gate["issues"])


def test_explicit_identity_conflict_blocks_report():
    evidence = {
        "symbol": "600519",
        "trade_date": "20260710",
        "modules": {},
        "_meta": {"identity_validation": {"status": "conflict"}},
    }

    gate = evaluate_safety_gate(evidence, [_claim().to_dict()], asset_type="company")

    assert gate["decision"] == PublicationDecision.BLOCK_REPORT.value


def test_production_integrity_audit_detects_explicit_major_exceptions():
    modules = {
        "C2": {
            "evidence": [
                {
                    "evidence_id": "EV-A",
                    "metric": "revenue",
                    "period": "2025FY",
                    "value": 100,
                    "currency": "CNY",
                    "source_type": "primary_disclosure",
                    "source": "filing-a",
                    "validation_status": "accepted",
                    "published_at": "20260709",
                },
                {
                    "evidence_id": "EV-B",
                    "metric": "revenue",
                    "period": "2025FY",
                    "value": 101,
                    "currency": "USD",
                    "source_type": "primary_disclosure",
                    "source": "filing-b",
                    "validation_status": "accepted",
                    "published_at": "20260711",
                },
            ]
        }
    }

    audit = build_evidence_integrity_audit(
        modules,
        requested_symbol="600519",
        resolved_symbol="000001",
        trade_date="20260710",
    )

    assert audit["identity_validation"]["status"] == "conflict"
    assert audit["basis_conflicts"]
    assert audit["primary_conflicts"]
    assert audit["publication_cutoff_audit"]["violations"]


def test_no_publishable_claims_blocks_report():
    evidence = {"symbol": "600519", "trade_date": "20260710", "modules": {}, "_meta": {}}

    gate = evaluate_safety_gate(evidence, [], asset_type="company")

    assert gate["decision"] == PublicationDecision.BLOCK_REPORT.value
    assert any(issue["code"] == "NO_SUPPORTED_CLAIMS" for issue in gate["issues"])


def test_four_audit_artifacts_separate_published_and_unpublished_claims():
    published = _claim().to_dict()
    unpublished = {
        "question_id": "Q-MARKET-SHARE",
        "question": "市场份额是否下降？",
        "missing_evidence_effect": "blocks_claim",
    }
    snapshot = {
        "snapshot_id": "sha256:fixture",
        "evidence": {
            "symbol": "600519",
            "trade_date": "20260710",
            "modules": {
                "C2": {
                    "evidence": [
                        {
                            "evidence_id": "EV-OCF-001",
                            "metric": "operating_cash_flow",
                            "period": "2025FY",
                            "source": "annual_report",
                        }
                    ]
                }
            },
            "_meta": {
                "coverage": 50.0,
                "available_modules": ["C2"],
                "missing_modules": ["C4"],
                "source_events": [],
            },
        },
    }
    opinions = {"buffett": {"unpublished_questions": [unpublished]}}
    committee = {
        "publishable_claims": [published],
        "safety_gate": {"decision": "publish", "issues": []},
    }

    artifacts = build_claim_audit_artifacts(snapshot, opinions, committee)

    assert set(artifacts) == {
        "evidence_manifest",
        "claim_ledger",
        "coverage_report",
        "unpublished_claims",
    }
    assert artifacts["claim_ledger"]["publishable_claims"] == [published]
    assert artifacts["unpublished_claims"]["claims"] == [unpublished]
