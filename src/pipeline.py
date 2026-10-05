"""
Brief assembly pipeline.

Single path from raw client data to a finished handover brief:

    sessions ──► tagger ──► consent engine ──► generator ──► brief
                                │                  ▲
                                ├──► explainer ────┤
                     actions ───┴──► tracker ──────┘

Deliberately free of FastAPI, Pydantic and SQLModel imports. The eval harness
runs this over 60 clients with nothing installed but the standard library, so
the numbers in the report come from the same code path that serves the API
rather than from a reimplementation that could drift away from it.

Ordering is a safety property, not a style choice. Consent filtering happens
*before* generation, so no summariser — LLM or extractive — is ever handed
content the client did not agree to share. Filtering afterwards would mean
trusting a model to forget something it had already read.
"""

from __future__ import annotations

from datetime import datetime

from .actions.tracker import build_digest
from .generator.conflicts import detect_conflicts
from .generator.explainer import explain
from .generator.generator import generate_brief
from .policy.categories import ConsentPurpose, RecipientRole, SensitivityCategory
from .policy.engine import (
    CONFIDENCE_THRESHOLD,
    ConsentPolicyEngine,
    ConsentRecord,
    TaggedSpan,
)
from .tagger import backend_name, split_sentences, tag_session

SESSION_WINDOW = 3  # most recent N sessions feed the brief

WITHHELD_NOTICE_TEMPLATE = (
    "{n} topic(s) withheld under client consent: {cats}. "
    "Ask the client directly if clinically relevant."
)

_engine = ConsentPolicyEngine()


def _parse(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def build_consent_records(client: dict) -> list[ConsentRecord]:
    """Convert raw consent dicts into engine records, skipping malformed ones.

    A record with an unrecognised category or role is dropped rather than
    coerced. Dropping it means the category has no consent record, and the
    engine's default is DENY — so a corrupt row fails closed. Guessing what a
    malformed row meant could fail open, which is the one outcome that is not
    acceptable here.
    """
    records: list[ConsentRecord] = []
    raw_consents = client.get("consents") or []
    for raw in raw_consents:
        if not isinstance(raw, dict):
            continue
        try:
            category = SensitivityCategory(raw["category"])
            role = RecipientRole(raw["recipient_role"])
            purpose = ConsentPurpose(raw["purpose"])
        except (KeyError, ValueError, TypeError):
            continue
        granted_at = _parse(raw.get("granted_at"))
        if granted_at is None:
            continue
        records.append(
            ConsentRecord(
                client_id=raw.get("client_id", client.get("client_id", "")),
                category=category,
                recipient_role=role,
                purpose=purpose,
                granted=bool(raw.get("granted", False)),
                granted_at=granted_at,
                expires_at=_parse(raw.get("expires_at")),
                revoked_at=_parse(raw.get("revoked_at")),
            )
        )
    return records


def collect_spans(client: dict) -> tuple[list[TaggedSpan], list[str]]:
    """Tag the recent session window and separate tagged text from clean text.

    Returns (spans, unclassified_sentences).

    A sentence is "unclassified" only when the tagger found *no* category in it
    at all. That test is the load-bearing line in this module. The obvious
    alternative — collect every sentence, then subtract the ones matching a
    withheld span's text — is what the original brief builder did, and it
    leaked: session text was rebuilt by splitting on ". ", which strips the
    terminal period, so fragments never string-matched the stored span text
    that kept it. Every withheld span was silently re-added as narrative.

    Deriving both sets from one segmentation pass removes the class of bug
    rather than patching the symptom. A sentence is either tagged or it is not,
    and the two lists cannot disagree because they come from the same split.
    """
    raw_sessions = client.get("sessions") or []
    sessions = [s for s in raw_sessions if isinstance(s, dict)]
    sessions.sort(key=lambda s: str(s.get("date", "")))
    recent = sessions[-SESSION_WINDOW:] if sessions else []

    spans: list[TaggedSpan] = []
    tagged_text: set[str] = set()

    for session in recent:
        session_spans = tag_session(session)
        spans.extend(session_spans)
        tagged_text.update(s.text.strip() for s in session_spans)

    unclassified: list[str] = []
    seen: set[str] = set()
    for session in recent:
        raw_text = session.get("text", "")
        if not isinstance(raw_text, str):
            raw_text = str(raw_text or "")
        for sentence in split_sentences(raw_text):
            cleaned = sentence.strip()
            key = cleaned.casefold()
            if cleaned and cleaned not in tagged_text and key not in seen:
                seen.add(key)
                unclassified.append(cleaned)

    return spans, unclassified


def build_brief(
    client: dict,
    role: RecipientRole = RecipientRole.COUNSELLOR,
    purpose: ConsentPurpose = ConsentPurpose.HANDOVER,
    now: datetime | None = None,
    tier_override: int | None = None,
) -> dict:
    """Produce a complete handover brief for one client as a plain dict."""
    now = now or datetime.utcnow()

    spans, unclassified = collect_spans(client)
    consent_records = build_consent_records(client)
    result = _engine.filter(spans, consent_records, role, purpose, at=now)

    raw_actions = client.get("actions") or []
    actions_list = [a for a in raw_actions if isinstance(a, dict)]
    digest = build_digest(actions_list, now)

    raw_goals = client.get("goals") or []
    goals = [
        f"{g.get('text', '')} ({g.get('status', 'open')})".strip()
        for g in raw_goals
        if isinstance(g, dict) and g.get("status") != "completed" and g.get("text")
    ]

    permitted_categories = sorted({s.category.value for s in result.permitted_spans})
    withheld_categories = [c.value for c in result.withheld_categories]

    # Unclassified sentences are content the tagger found no sensitivity in.
    # They are appended after permitted spans so the consent-relevant material
    # leads, and they carry a synthetic span id prefixed "gen:" so provenance
    # stays honest about which sentences came from a policy decision.
    permitted_payload = [
        {"span_id": s.span_id, "text": s.text, "category": s.category.value}
        for s in result.permitted_spans
    ] + [
        {"span_id": f"gen:{i}", "text": text, "category": "unclassified"}
        for i, text in enumerate(unclassified)
    ]

    context = {
        "client_id": client.get("client_id", ""),
        "recipient_role": role.value,
        "generated_at": now.isoformat(),
        "permitted_spans": permitted_payload,
        "permitted_categories": permitted_categories,
        "withheld_categories": withheld_categories,
        "consent_missing": [c.value for c in result.consent_missing],
        "goals": goals,
        "actions": [a.to_dict() for a in digest.actions],
    }

    # Contradictions are detected on permitted content only, before generation,
    # so the notice can be attached regardless of which tier produced the text.
    conflicts = detect_conflicts(permitted_payload)

    output = generate_brief(context, tier_override=tier_override)

    explanation = explain(
        spans,
        consent_records,
        result,
        role,
        purpose,
        at=now,
        tagger_backend=backend_name(),
        confidence_threshold=CONFIDENCE_THRESHOLD,
    )

    withheld_notice = ""
    if withheld_categories:
        withheld_notice = WITHHELD_NOTICE_TEMPLATE.format(
            n=result.withheld_count,
            cats=", ".join(withheld_categories),
        )

    # Escalations come from two independent sources that must not mask each
    # other: the consent engine's safety carve-out, and overdue high-priority
    # actions. A client can easily have both.
    escalation_flags = list(result.escalation_flags) + digest.red_flags

    return {
        "client_id": client.get("client_id", ""),
        "pseudonym": client.get("pseudonym", ""),
        "recipient_role": role.value,
        "purpose": purpose.value,
        "generated_at": now.isoformat(),
        "tier": output.tier,
        "tier_label": output.tier_label,
        "summary": output.summary,
        "facts": output.facts,
        "brief": output.summary,  # alias consumed by the eval harness
        "word_count": len(output.summary.split()),
        "permitted_categories": permitted_categories,
        "withheld_count": result.withheld_count,
        "withheld_categories": withheld_categories,
        "withheld_flags": withheld_categories,  # alias consumed by the eval harness
        "withheld_notice": withheld_notice,
        "escalation_flags": escalation_flags,
        "notifications": digest.notifications,
        "conflicts": [c.to_dict() for c in conflicts],
        "conflict_notices": [c.notice for c in conflicts],
        "consent_missing": [c.value for c in result.consent_missing],
        "actions": [a.to_dict() for a in digest.actions],
        "actions_included": [a.action_id for a in digest.actions],
        "goals": goals,
        "provenance": output.provenance,
        "degradation_reasons": output.degradation_reasons,
        "explanation": {
            "summary": explanation.summary_sentence(
                len(result.permitted_spans), len(spans)
            ),
            "why_shown": [
                {"category": e.category, "detail": e.sentence}
                for e in explanation.why_shown
            ],
            "why_withheld": [
                {
                    "category": e.category,
                    "reason_code": e.reason_code,
                    "detail": e.detail,
                    "is_safety_relevant": e.is_safety_relevant,
                }
                for e in explanation.why_withheld
            ],
        },
        "uncertainty_note": explanation.uncertainty_note,
        "total_spans": len(spans),
        "permitted_span_count": len(result.permitted_spans),
    }
