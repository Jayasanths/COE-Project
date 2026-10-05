"""
Explanation layer — Stage 5.

Every brief carries its own reasoning. Three questions get answered:

1. Why is this shown?     Which consent record authorised each permitted category.
2. Why is this missing?   Whether the category had no record, an expired one,
                          a revoked one, one belonging to a different role or
                          purpose, or a tag the system was not confident about.
3. What is uncertain?     Every span below the reporting confidence bar.

The distinction in (2) is the whole point of this module. "Withheld" is a
single decision to the policy engine but four very different situations to a
clinician: *the client said no* is a boundary to respect, whereas *nobody ever
asked* is an administrative gap someone should close, and *this was tagged and
we weren't sure* means the content may not even be sensitive. Collapsing them
into one grey box would make the consent process look like the client's fault.

This module reads consent records; it never decides anything. The engine has
already made every call by the time an explanation is produced, so nothing here
can widen disclosure. It is a mirror held up to a decision already taken.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from ..policy.categories import ConsentPurpose, RecipientRole, SensitivityCategory
from ..policy.engine import ConsentRecord, FilterResult, TaggedSpan

# Spans at or above the policy threshold but below this are permitted, and
# still worth flagging to the reader as "believed, not certain".
UNCERTAINTY_REPORTING_THRESHOLD = 0.85


class WithholdReason:
    """Why a category did not make it into the brief."""

    NO_RECORD = "no_record"
    REVOKED = "revoked"
    EXPIRED = "expired"
    NOT_GRANTED = "not_granted"
    WRONG_ROLE = "wrong_role"
    WRONG_PURPOSE = "wrong_purpose"
    LOW_CONFIDENCE = "low_confidence"


WITHHOLD_PHRASING: dict[str, str] = {
    WithholdReason.NO_RECORD: (
        "Consent not on file for this category. Nobody has asked the client — "
        "this is an administrative gap, not a refusal."
    ),
    WithholdReason.REVOKED: (
        "The client revoked consent for this category. Respect the decision; "
        "do not seek the content through another route."
    ),
    WithholdReason.EXPIRED: (
        "Consent for this category has expired and needs renewing with the client."
    ),
    WithholdReason.NOT_GRANTED: (
        "The client was asked and declined consent for this category."
    ),
    WithholdReason.WRONG_ROLE: (
        "The client consented to share this with a different role, not yours."
    ),
    WithholdReason.WRONG_PURPOSE: (
        "Consent exists for a different purpose than this handover."
    ),
    WithholdReason.LOW_CONFIDENCE: (
        "Content was tagged as possibly sensitive but below the confidence "
        "threshold, so it was withheld by default. It may not be sensitive at all."
    ),
}


@dataclass
class PermittedExplanation:
    category: str
    consent_id: str
    granted_at: str
    expires_at: str | None
    recipient_role: str
    purpose: str

    @property
    def sentence(self) -> str:
        window = f", expires {self.expires_at[:10]}" if self.expires_at else ""
        return (
            f"{self.category}: shown under consent granted "
            f"{self.granted_at[:10]} for role '{self.recipient_role}' "
            f"and purpose '{self.purpose}'{window}."
        )


@dataclass
class WithheldExplanation:
    category: str
    reason_code: str
    detail: str
    is_safety_relevant: bool = False

    @property
    def sentence(self) -> str:
        return f"{self.category}: {self.detail}"


@dataclass
class Explanation:
    why_shown: list[PermittedExplanation] = field(default_factory=list)
    why_withheld: list[WithheldExplanation] = field(default_factory=list)
    uncertainty_spans: list[tuple[str, float]] = field(default_factory=list)
    policy_version: str = "engine-1.0"
    tagger_backend: str = ""
    confidence_threshold: float = 0.70

    @property
    def uncertainty_note(self) -> str:
        if not self.uncertainty_spans:
            return ""
        return (
            f"{len(self.uncertainty_spans)} span(s) carried confidence below "
            f"{UNCERTAINTY_REPORTING_THRESHOLD:.2f}. Verify sensitive history "
            "directly with the client if clinically indicated."
        )

    def summary_sentence(self, permitted_count: int, total_count: int) -> str:
        return (
            f"{permitted_count} of {total_count} tagged span(s) were permitted. "
            f"{len(self.why_withheld)} category/categories withheld. "
            f"Policy {self.policy_version}, confidence threshold "
            f"{self.confidence_threshold:.2f}"
            + (f", tagger {self.tagger_backend}" if self.tagger_backend else "")
            + "."
        )


def _classify_withhold(
    category: SensitivityCategory,
    records: list[ConsentRecord],
    role: RecipientRole,
    purpose: ConsentPurpose,
    at: datetime,
    low_confidence: bool,
) -> str:
    """Pick the most informative reason for a withheld category.

    Ordering matters. A category can fail several checks at once — an expired
    record for the wrong role, say — and the reason shown drives what the
    clinician does next. So the order runs from *most actionable* to least:
    revoked (stop) before expired (renew it) before wrong role (ask the right
    person) before no record (start the conversation). Low confidence is
    checked first only when no consent record exists to discuss at all,
    because in that case the tag itself is the thing in doubt.
    """
    for_category = [r for r in records if r.category == category]

    if not for_category:
        return (
            WithholdReason.LOW_CONFIDENCE
            if low_confidence
            else WithholdReason.NO_RECORD
        )

    matching = [
        r for r in for_category if r.recipient_role == role and r.purpose == purpose
    ]

    if matching:
        if any(r.revoked_at is not None and r.revoked_at <= at for r in matching):
            return WithholdReason.REVOKED
        if any(r.expires_at is not None and r.expires_at <= at for r in matching):
            return WithholdReason.EXPIRED
        if any(not r.granted for r in matching):
            return WithholdReason.NOT_GRANTED
        # A live, matching, granted record that still produced a denial can
        # only mean the tag failed the confidence bar.
        return WithholdReason.LOW_CONFIDENCE

    if any(r.recipient_role != role for r in for_category):
        return WithholdReason.WRONG_ROLE
    return WithholdReason.WRONG_PURPOSE


def explain(
    spans: list[TaggedSpan],
    consent_records: list[ConsentRecord],
    result: FilterResult,
    role: RecipientRole,
    purpose: ConsentPurpose,
    at: datetime,
    tagger_backend: str = "",
    confidence_threshold: float = 0.70,
) -> Explanation:
    """Build the full explanation for one filtered brief."""
    explanation = Explanation(
        tagger_backend=tagger_backend,
        confidence_threshold=confidence_threshold,
    )

    # ── Why shown ──────────────────────────────────────────────────────────
    permitted_categories = {s.category for s in result.permitted_spans}
    for category in sorted(permitted_categories, key=lambda c: c.value):
        authorising = next(
            (
                r
                for r in consent_records
                if r.category == category
                and r.recipient_role == role
                and r.purpose == purpose
                and r.is_active(at)
            ),
            None,
        )
        if authorising is None:
            # Unreachable via the engine: a permitted span always has an active
            # record. Recorded rather than skipped so that if the invariant
            # ever breaks, it shows up on the brief instead of hiding.
            explanation.why_shown.append(
                PermittedExplanation(
                    category=category.value,
                    consent_id="UNKNOWN",
                    granted_at="",
                    expires_at=None,
                    recipient_role=role.value,
                    purpose=purpose.value,
                )
            )
            continue
        explanation.why_shown.append(
            PermittedExplanation(
                category=category.value,
                consent_id=f"{authorising.client_id}:{category.value}:{role.value}",
                granted_at=authorising.granted_at.isoformat(),
                expires_at=authorising.expires_at.isoformat()
                if authorising.expires_at
                else None,
                recipient_role=authorising.recipient_role.value,
                purpose=authorising.purpose.value,
            )
        )

    # ── Why withheld ───────────────────────────────────────────────────────
    low_confidence_categories = {
        s.category for s in spans if s.confidence < confidence_threshold
    }
    safety_categories = {s.category for s in spans if s.is_safety_relevant}

    for category in result.withheld_categories:
        reason = _classify_withhold(
            category,
            consent_records,
            role,
            purpose,
            at,
            low_confidence=category in low_confidence_categories,
        )
        explanation.why_withheld.append(
            WithheldExplanation(
                category=category.value,
                reason_code=reason,
                detail=WITHHOLD_PHRASING[reason],
                is_safety_relevant=category in safety_categories,
            )
        )

    # ── Uncertainty ────────────────────────────────────────────────────────
    explanation.uncertainty_spans = sorted(
        (
            (s.span_id, s.confidence)
            for s in spans
            if s.confidence < UNCERTAINTY_REPORTING_THRESHOLD
        ),
        key=lambda pair: pair[1],
    )

    return explanation
