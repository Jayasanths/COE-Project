"""
Consent policy engine.
RULES:
  - No LLM calls, no network, no randomness.
  - Default decision is DENY.
  - Missing consent record = DENY.
  - Revoked consent = DENY (revocation is retroactive for future briefs).
  - Safety-critical content inside a withheld category → ESCALATE flag,
    never silently hidden.
  - Low-confidence tag (< threshold) → treat as sensitive, DENY.
This file is HAND-WRITTEN. Agents must not modify it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from .categories import (
    DEFAULT_DECISION,
    SAFETY_CRITICAL,
    ConsentPurpose,
    RecipientRole,
    SensitivityCategory,
)

CONFIDENCE_THRESHOLD = 0.70  # below this → treat tag as certain, fail closed


@dataclass(frozen=True)
class ConsentRecord:
    client_id: str
    category: SensitivityCategory
    recipient_role: RecipientRole
    purpose: ConsentPurpose
    granted: bool
    granted_at: datetime
    expires_at: datetime | None = None
    revoked_at: datetime | None = None

    def is_active(self, at: datetime) -> bool:
        if not self.granted:
            return False
        if self.revoked_at is not None and self.revoked_at <= at:
            return False
        if self.expires_at is not None and self.expires_at <= at:
            return False
        return True


@dataclass(frozen=True)
class TaggedSpan:
    span_id: str
    text: str
    category: SensitivityCategory
    confidence: float  # 0.0–1.0
    is_safety_relevant: bool = False


@dataclass
class PolicyDecision:
    category: SensitivityCategory
    decision: Literal["PERMIT", "DENY"]
    reason: str
    escalate: bool = False
    escalation_message: str = ""


@dataclass
class FilterResult:
    permitted_spans: list[TaggedSpan] = field(default_factory=list)
    withheld_categories: list[SensitivityCategory] = field(default_factory=list)
    escalation_flags: list[str] = field(default_factory=list)
    consent_missing: list[SensitivityCategory] = field(default_factory=list)
    decisions: list[PolicyDecision] = field(default_factory=list)

    @property
    def has_escalation(self) -> bool:
        return len(self.escalation_flags) > 0

    @property
    def withheld_count(self) -> int:
        return len(self.withheld_categories)


class ConsentPolicyEngine:
    """
    Deterministic, auditable consent filter.
    Input:  tagged spans + consent records for a client + recipient context.
    Output: FilterResult describing what is permitted, withheld, and flagged.
    """

    def __init__(self, confidence_threshold: float = CONFIDENCE_THRESHOLD) -> None:
        self.confidence_threshold = confidence_threshold

    def filter(
        self,
        spans: list[TaggedSpan],
        consent_records: list[ConsentRecord],
        recipient_role: RecipientRole,
        purpose: ConsentPurpose,
        at: datetime | None = None,
    ) -> FilterResult:
        at = at or datetime.utcnow()
        result = FilterResult()

        # Index active consent by (category, role, purpose)
        active: set[tuple[SensitivityCategory, RecipientRole, ConsentPurpose]] = set()
        for rec in consent_records:
            if (
                rec.is_active(at)
                and rec.recipient_role == recipient_role
                and rec.purpose == purpose
            ):
                active.add((rec.category, rec.recipient_role, rec.purpose))

        seen_categories: set[SensitivityCategory] = set()

        for span in spans:
            decision = self._decide(span, active, recipient_role, purpose)
            result.decisions.append(decision)

            if decision.decision == "PERMIT":
                result.permitted_spans.append(span)
            else:
                # Track withheld category once
                if span.category not in seen_categories:
                    seen_categories.add(span.category)
                    result.withheld_categories.append(span.category)

                    # Check if consent record exists at all
                    has_any_record = any(
                        r.category == span.category for r in consent_records
                    )
                    if not has_any_record:
                        result.consent_missing.append(span.category)

                # Safety-critical carve-out: even if withheld, flag escalation
                if span.category in SAFETY_CRITICAL or span.is_safety_relevant:
                    msg = (
                        f"Safety-relevant content withheld under category "
                        f"'{span.category.value}' — escalate to supervisor before session."
                    )
                    if msg not in result.escalation_flags:
                        result.escalation_flags.append(msg)

                if decision.escalate and decision.escalation_message:
                    if decision.escalation_message not in result.escalation_flags:
                        result.escalation_flags.append(decision.escalation_message)

        return result

    def _decide(
        self,
        span: TaggedSpan,
        active: set[tuple[SensitivityCategory, RecipientRole, ConsentPurpose]],
        role: RecipientRole,
        purpose: ConsentPurpose,
    ) -> PolicyDecision:
        # Low-confidence tag → fail closed (treat as sensitive)
        if span.confidence < self.confidence_threshold:
            return PolicyDecision(
                category=span.category,
                decision="DENY",
                reason=f"Tag confidence {span.confidence:.2f} below threshold {self.confidence_threshold}",
            )

        key = (span.category, role, purpose)
        if key in active:
            return PolicyDecision(
                category=span.category,
                decision="PERMIT",
                reason="Active consent record found",
            )

        # Default: DENY
        escalate = span.category in SAFETY_CRITICAL or span.is_safety_relevant
        return PolicyDecision(
            category=span.category,
            decision=DEFAULT_DECISION,  # type: ignore[arg-type]
            reason="No active consent record — default deny",
            escalate=escalate,
            escalation_message=(
                f"Safety-relevant content withheld under '{span.category.value}' "
                "— escalate to supervisor before session."
            )
            if escalate
            else "",
        )
