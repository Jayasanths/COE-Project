"""
Property and unit tests for the consent policy engine.
The single most important invariant: consent_leakage_rate == 0.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from hypothesis import given, settings
from hypothesis import strategies as st

from src.policy.categories import (
    ConsentPurpose,
    RecipientRole,
    SensitivityCategory,
)
from src.policy.engine import (
    CONFIDENCE_THRESHOLD,
    ConsentPolicyEngine,
    ConsentRecord,
    TaggedSpan,
)

engine = ConsentPolicyEngine()
NOW = datetime(2025, 1, 1, 12, 0, 0)
FUTURE = NOW + timedelta(days=365)


# ── Helpers ────────────────────────────────────────────────────────────────


def make_span(
    category: SensitivityCategory = SensitivityCategory.SUBSTANCE_USE,
    confidence: float = 0.95,
    safety: bool = False,
) -> TaggedSpan:
    return TaggedSpan(
        span_id="s1",
        text="test span",
        category=category,
        confidence=confidence,
        is_safety_relevant=safety,
    )


def make_consent(
    category: SensitivityCategory = SensitivityCategory.SUBSTANCE_USE,
    role: RecipientRole = RecipientRole.COUNSELLOR,
    purpose: ConsentPurpose = ConsentPurpose.HANDOVER,
    granted: bool = True,
    revoked_at: datetime | None = None,
    expires_at: datetime | None = None,
) -> ConsentRecord:
    return ConsentRecord(
        client_id="c1",
        category=category,
        recipient_role=role,
        purpose=purpose,
        granted=granted,
        granted_at=NOW - timedelta(days=1),
        expires_at=expires_at,
        revoked_at=revoked_at,
    )


# ── Unit tests ─────────────────────────────────────────────────────────────


def test_permit_with_active_consent():
    span = make_span()
    consent = make_consent()
    result = engine.filter(
        [span], [consent], RecipientRole.COUNSELLOR, ConsentPurpose.HANDOVER, at=NOW
    )
    assert span in result.permitted_spans


def test_deny_with_no_consent():
    span = make_span()
    result = engine.filter(
        [span], [], RecipientRole.COUNSELLOR, ConsentPurpose.HANDOVER, at=NOW
    )
    assert span not in result.permitted_spans
    assert SensitivityCategory.SUBSTANCE_USE in result.withheld_categories
    assert SensitivityCategory.SUBSTANCE_USE in result.consent_missing


def test_deny_after_revocation():
    span = make_span()
    consent = make_consent(revoked_at=NOW - timedelta(seconds=1))
    result = engine.filter(
        [span], [consent], RecipientRole.COUNSELLOR, ConsentPurpose.HANDOVER, at=NOW
    )
    assert span not in result.permitted_spans


def test_deny_after_expiry():
    span = make_span()
    consent = make_consent(expires_at=NOW - timedelta(seconds=1))
    result = engine.filter(
        [span], [consent], RecipientRole.COUNSELLOR, ConsentPurpose.HANDOVER, at=NOW
    )
    assert span not in result.permitted_spans


def test_deny_wrong_role():
    span = make_span()
    consent = make_consent(role=RecipientRole.PSYCHIATRIST)
    result = engine.filter(
        [span], [consent], RecipientRole.COUNSELLOR, ConsentPurpose.HANDOVER, at=NOW
    )
    assert span not in result.permitted_spans


def test_low_confidence_denied():
    span = make_span(confidence=CONFIDENCE_THRESHOLD - 0.01)
    consent = make_consent()
    result = engine.filter(
        [span], [consent], RecipientRole.COUNSELLOR, ConsentPurpose.HANDOVER, at=NOW
    )
    assert span not in result.permitted_spans


def test_safety_relevant_withheld_triggers_escalation():
    span = make_span(safety=True)
    result = engine.filter(
        [span], [], RecipientRole.COUNSELLOR, ConsentPurpose.HANDOVER, at=NOW
    )
    assert result.has_escalation
    assert any("escalate" in msg.lower() for msg in result.escalation_flags)


def test_safety_category_withheld_triggers_escalation():
    span = make_span(category=SensitivityCategory.SAFETY_RISK, confidence=0.99)
    result = engine.filter(
        [span], [], RecipientRole.COUNSELLOR, ConsentPurpose.HANDOVER, at=NOW
    )
    assert result.has_escalation


def test_withheld_count_does_not_double_count():
    spans = [
        make_span(category=SensitivityCategory.SUBSTANCE_USE),
        TaggedSpan("s2", "another span", SensitivityCategory.SUBSTANCE_USE, 0.95),
    ]
    result = engine.filter(
        spans, [], RecipientRole.COUNSELLOR, ConsentPurpose.HANDOVER, at=NOW
    )
    assert result.withheld_categories.count(SensitivityCategory.SUBSTANCE_USE) == 1


# ── Failure cases ──────────────────────────────────────────────────────────


def test_failure_consent_revoked_mid_episode():
    """Failure case 1: consent revoked mid-episode."""
    span = make_span()
    revoked_consent = make_consent(revoked_at=NOW)
    result = engine.filter(
        [span],
        [revoked_consent],
        RecipientRole.COUNSELLOR,
        ConsentPurpose.HANDOVER,
        at=NOW,
    )
    assert span not in result.permitted_spans


def test_failure_missing_consent_record():
    """Failure case 3: no consent record at all → deny + flag missing."""
    span = make_span(category=SensitivityCategory.TRAUMA_HISTORY)
    result = engine.filter(
        [span], [], RecipientRole.SOCIAL_WORKER, ConsentPurpose.HANDOVER, at=NOW
    )
    assert SensitivityCategory.TRAUMA_HISTORY in result.consent_missing


def test_failure_low_confidence_tag():
    """Failure case 4: low-confidence tag → fail closed."""
    span = make_span(confidence=0.50)
    consent = make_consent()
    result = engine.filter(
        [span], [consent], RecipientRole.COUNSELLOR, ConsentPurpose.HANDOVER, at=NOW
    )
    assert span not in result.permitted_spans


def test_failure_safety_critical_carveout():
    """Failure case 6: safety-critical content inside withheld category."""
    span = make_span(category=SensitivityCategory.SAFETY_RISK, confidence=0.98)
    result = engine.filter(
        [span], [], RecipientRole.COUNSELLOR, ConsentPurpose.HANDOVER, at=NOW
    )
    assert span not in result.permitted_spans
    assert result.has_escalation


# ── Property tests (Hypothesis) ───────────────────────────────────────────

category_st = st.sampled_from(SensitivityCategory)
role_st = st.sampled_from(RecipientRole)
purpose_st = st.sampled_from(ConsentPurpose)
confidence_st = st.floats(min_value=0.0, max_value=1.0, allow_nan=False)


@given(
    categories=st.lists(category_st, min_size=1, max_size=5),
    role=role_st,
    purpose=purpose_st,
)
@settings(max_examples=200, deadline=2000)
def test_property_no_consent_always_denies(
    categories: list[SensitivityCategory],
    role: RecipientRole,
    purpose: ConsentPurpose,
) -> None:
    """With zero consent records, every span must be denied."""
    spans = [TaggedSpan(f"s{i}", "text", cat, 0.99) for i, cat in enumerate(categories)]
    result = engine.filter(spans, [], role, purpose, at=NOW)
    assert (
        len(result.permitted_spans) == 0
    ), f"Consent leakage! {len(result.permitted_spans)} spans leaked with no consent records."


@given(
    categories=st.lists(category_st, min_size=1, max_size=5),
    confidence=st.floats(
        min_value=0.0, max_value=CONFIDENCE_THRESHOLD - 0.001, allow_nan=False
    ),
    role=role_st,
    purpose=purpose_st,
)
@settings(max_examples=200, deadline=2000)
def test_property_low_confidence_always_denies(
    categories: list[SensitivityCategory],
    confidence: float,
    role: RecipientRole,
    purpose: ConsentPurpose,
) -> None:
    """Low-confidence tags must never be permitted regardless of consent."""
    spans = [
        TaggedSpan(f"s{i}", "text", cat, confidence) for i, cat in enumerate(categories)
    ]
    consents = [
        make_consent(category=cat, role=role, purpose=purpose) for cat in categories
    ]
    result = engine.filter(spans, consents, role, purpose, at=NOW)
    assert (
        len(result.permitted_spans) == 0
    ), f"Low-confidence leak! confidence={confidence:.3f}"


@given(
    categories=st.lists(category_st, min_size=1, max_size=4),
    role=role_st,
    purpose=purpose_st,
)
@settings(max_examples=200, deadline=2000)
def test_property_revoked_consent_always_denies(
    categories: list[SensitivityCategory],
    role: RecipientRole,
    purpose: ConsentPurpose,
) -> None:
    """Revoked consent must always deny, even if revoked 1 second ago."""
    spans = [TaggedSpan(f"s{i}", "text", cat, 0.99) for i, cat in enumerate(categories)]
    consents = [
        make_consent(
            category=cat,
            role=role,
            purpose=purpose,
            revoked_at=NOW - timedelta(seconds=1),
        )
        for cat in categories
    ]
    result = engine.filter(spans, consents, role, purpose, at=NOW)
    assert len(result.permitted_spans) == 0
