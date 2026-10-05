"""
End-to-end tests for the six documented failure cases.

`test_policy.py` proves the consent engine is correct in isolation. These tests
prove the *assembled system* is correct — that no stage downstream of the engine
reintroduces content the engine denied.

That distinction is the reason this file exists. The original brief builder
called the engine correctly and then leaked anyway: it rebuilt "general"
narrative by splitting session text on ". ", which strips the terminal period,
so those fragments never matched the stored span text that kept it, and every
withheld span was silently re-added as unclassified prose. Every unit test on
the engine still passed. Only an end-to-end assertion catches that class of bug,
so each test below goes through `build_brief` rather than calling the engine.

Each test constructs a minimal client fixture, runs the real pipeline, and
asserts the specific documented behaviour.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from src.actions.tracker import dropped_high_priority, escalation_level, track_all
from src.generator.generator import generate_brief
from src.generator.llm import LLMUnavailable
from src.pipeline import build_brief
from src.policy.categories import ConsentPurpose, RecipientRole

NOW = datetime(2025, 3, 1, 12, 0, 0)
DISCHARGE = NOW - timedelta(days=30)


# ── Fixtures ───────────────────────────────────────────────────────────────


def make_consent(
    category: str,
    role: str = "counsellor",
    granted: bool = True,
    revoked_at: datetime | None = None,
    expires_at: datetime | None = None,
    purpose: str = "handover",
) -> dict:
    return {
        "consent_id": f"cons-{category}-{role}",
        "client_id": "C001",
        "category": category,
        "recipient_role": role,
        "purpose": purpose,
        "granted": granted,
        "granted_at": (DISCHARGE - timedelta(days=2)).isoformat(),
        "expires_at": expires_at.isoformat() if expires_at else None,
        "revoked_at": revoked_at.isoformat() if revoked_at else None,
    }


def make_session(
    session_id: str, text: str, days_ago: int = 5, spans: list | None = None
) -> dict:
    return {
        "session_id": session_id,
        "client_id": "C001",
        "author_role": "nurse",
        "date": (NOW - timedelta(days=days_ago)).isoformat(),
        "text": text,
        "spans": spans if spans is not None else [],
    }


def make_action(
    action_id: str = "A1",
    priority: str = "HIGH",
    days_until_due: int = 5,
    status: str = "open",
) -> dict:
    return {
        "action_id": action_id,
        "client_id": "C001",
        "description": "Update safety plan with client",
        "owner_role": "counsellor",
        "owner_id": "STAFF_01",
        "due_date": (NOW + timedelta(days=days_until_due)).isoformat(),
        "priority": priority,
        "status": status,
        "escalation_level": 0,
    }


def make_client(
    sessions: list[dict],
    consents: list[dict] | None = None,
    actions: list[dict] | None = None,
    goals: list[dict] | None = None,
) -> dict:
    return {
        "client_id": "C001",
        "pseudonym": "Patient-001",
        "episode_id": "ep-001",
        "discharge_date": DISCHARGE.isoformat(),
        "consents": consents or [],
        "sessions": sessions,
        "goals": goals or [],
        "actions": actions or [],
        "gold": {},
    }


def brief_for(
    client: dict, role: RecipientRole = RecipientRole.COUNSELLOR, **kwargs
) -> dict:
    return build_brief(client, role, ConsentPurpose.HANDOVER, now=NOW, **kwargs)


# ── Failure case 1 — consent revoked mid-episode ───────────────────────────

SUBSTANCE_TEXT = (
    "Client admitted to relapse over the weekend — returned to cannabis use."
)


def test_case1_revoked_consent_content_absent_from_brief():
    """Revocation is retroactive for future briefs; content must disappear."""
    client = make_client(
        sessions=[make_session("s1", SUBSTANCE_TEXT)],
        consents=[make_consent("substance_use", revoked_at=NOW - timedelta(days=1))],
    )
    brief = brief_for(client)

    assert "cannabis" not in brief["summary"].lower()
    assert "relapse" not in brief["summary"].lower()
    assert "substance_use" in brief["withheld_categories"]


def test_case1_revocation_flips_a_previously_permitted_brief():
    """The same client, before and after revocation, must differ.

    Asserting only the post-revocation state would pass even if the pipeline
    withheld the content for some unrelated reason — a broken tagger, say. The
    before/after pair proves revocation is what changed the outcome.
    """
    sessions = [make_session("s1", SUBSTANCE_TEXT)]

    before = brief_for(make_client(sessions, [make_consent("substance_use")]))
    after = brief_for(
        make_client(
            sessions,
            [make_consent("substance_use", revoked_at=NOW - timedelta(days=1))],
        )
    )

    assert "cannabis" in before["summary"].lower()
    assert "cannabis" not in after["summary"].lower()
    assert any(
        w["reason_code"] == "revoked" for w in after["explanation"]["why_withheld"]
    )


# ── Failure case 2 — contradictory sessions ────────────────────────────────


def test_case2_contradiction_produces_notice_and_keeps_both_statements():
    """Conflicting notes must be surfaced, not silently resolved."""
    client = make_client(
        sessions=[
            make_session(
                "s1",
                "Client reports being sober for 3 weeks following discharge.",
                days_ago=10,
            ),
            make_session(
                "s2", "Client admitted to relapse over the weekend.", days_ago=2
            ),
        ],
        consents=[make_consent("substance_use")],
    )
    brief = brief_for(client)

    assert brief[
        "conflicts"
    ], "contradictory substance-use notes produced no conflict record"
    assert any("CONFLICTING RECORDS" in n for n in brief["conflict_notices"])

    conflict = brief["conflicts"][0]
    assert conflict["category"] == "substance_use"
    # Both sides retained — the system must not pick a winner.
    assert "sober" in conflict["positive_text"].lower()
    assert "relapse" in conflict["negative_text"].lower()

    summary = brief["summary"].lower()
    assert "sober" in summary and "relapse" in summary


def test_case2_no_false_conflict_on_consistent_notes():
    client = make_client(
        sessions=[
            make_session(
                "s1",
                "Client reports being sober for 3 weeks following discharge.",
                days_ago=10,
            ),
            make_session(
                "s2", "Client remains abstinent and engaged with support.", days_ago=2
            ),
        ],
        consents=[make_consent("substance_use")],
    )
    assert brief_for(client)["conflicts"] == []


def test_case2_conflict_detection_cannot_reveal_withheld_content():
    """A conflict must never be reported between permitted and withheld statements.

    Doing so would tell the reader that a withheld statement exists *and* what
    it roughly says — a consent bypass dressed up as transparency.
    """
    client = make_client(
        sessions=[
            make_session(
                "s1",
                "Client reports being sober for 3 weeks following discharge.",
                days_ago=10,
            ),
            make_session(
                "s2", "Client admitted to relapse over the weekend.", days_ago=2
            ),
        ],
        consents=[],  # nothing permitted at all
    )
    brief = brief_for(client)

    assert brief["conflicts"] == []
    assert "relapse" not in brief["summary"].lower()


# ── Failure case 3 — missing consent record ────────────────────────────────


def test_case3_missing_consent_is_named_not_silently_dropped():
    client = make_client(
        sessions=[
            make_session("s1", "Client has an upcoming court appearance on 14 March.")
        ],
        consents=[],
    )
    brief = brief_for(client)

    assert "forensic_legal" in brief["consent_missing"]
    assert "forensic_legal" in brief["withheld_notice"]

    reasons = {
        w["category"]: w["reason_code"] for w in brief["explanation"]["why_withheld"]
    }
    assert reasons["forensic_legal"] == "no_record"

    detail = next(
        w["detail"]
        for w in brief["explanation"]["why_withheld"]
        if w["category"] == "forensic_legal"
    )
    # The wording must not imply the client refused — nobody asked them.
    assert "not on file" in detail.lower()


def test_case3_wrong_role_is_distinguished_from_no_record():
    """Consent for another role is a different situation and must read differently."""
    client = make_client(
        sessions=[
            make_session("s1", "Client has an upcoming court appearance on 14 March.")
        ],
        consents=[make_consent("forensic_legal", role="psychiatrist")],
    )
    brief = brief_for(client, RecipientRole.COUNSELLOR)

    reasons = {
        w["category"]: w["reason_code"] for w in brief["explanation"]["why_withheld"]
    }
    assert reasons["forensic_legal"] == "wrong_role"


# ── Failure case 4 — low-confidence tag ────────────────────────────────────


def test_case4_low_confidence_denied_despite_active_consent():
    """A weak tag fails closed even when consent would otherwise permit it."""
    low_confidence_span = {
        "span_id": "sp-low",
        "text": "Client mentioned something about their situation at home.",
        "category": "family_conflict",
        "confidence": 0.42,
        "is_safety_relevant": False,
    }
    client = make_client(
        sessions=[
            make_session(
                "s1",
                "Client mentioned something about their situation at home.",
                spans=[low_confidence_span],
            )
        ],
        consents=[make_consent("family_conflict")],
    )
    brief = brief_for(client)

    assert "family_conflict" not in brief["permitted_categories"]
    assert "family_conflict" in brief["withheld_categories"]
    assert brief[
        "uncertainty_note"
    ], "low-confidence spans must be surfaced to the reader"


def test_case4_confidence_threshold_boundary_is_inclusive():
    """Exactly at the threshold permits; a hair below denies."""

    def brief_at(confidence: float) -> dict:
        span = {
            "span_id": "sp-b",
            "text": "Client has outstanding rent arrears; social worker referral made.",
            "category": "financial",
            "confidence": confidence,
            "is_safety_relevant": False,
        }
        client = make_client(
            sessions=[make_session("s1", span["text"], spans=[span])],
            consents=[make_consent("financial")],
        )
        return brief_for(client)

    assert "financial" in brief_at(0.70)["permitted_categories"]
    assert "financial" not in brief_at(0.69)["permitted_categories"]


# ── Failure case 5 — LLM unavailable ───────────────────────────────────────


def test_case5_llm_unavailable_falls_to_tier2_without_raising(monkeypatch):
    """Tier 1 failure must degrade silently to tier 2, never raise."""
    import src.generator.generator as gen

    def explode(_prompt):
        raise LLMUnavailable("connection refused")

    monkeypatch.setattr(gen, "llm_generate", explode)
    monkeypatch.setattr(gen, "llm_enabled", lambda: True)

    context = {
        "client_id": "C001",
        "recipient_role": "counsellor",
        "permitted_spans": [
            {
                "span_id": "sp1",
                "text": "Client engaged well in session.",
                "category": "unclassified",
            }
        ],
        "goals": [],
        "actions": [],
        "withheld_categories": [],
    }

    output = generate_brief(context, tier_override=1)

    assert output.tier == 2
    assert output.summary.strip()
    assert any("tier 1" in r for r in output.degradation_reasons)


def test_case5_ladder_reaches_tier4_when_nothing_else_works():
    """With no content and no facts, the floor is a manual checklist — not an error."""
    output = generate_brief(
        {
            "client_id": "C001",
            "recipient_role": "counsellor",
            "generated_at": NOW.isoformat(),
        }
    )

    assert output.tier == 4
    assert "MANUAL HANDOVER REQUIRED" in output.summary
    assert "Complete paper handover form" in output.summary


def test_case5_generate_brief_never_raises_on_malformed_input():
    """The ladder absorbs bad input rather than surfacing a stack trace to a clinician."""
    for bad in ({}, {"permitted_spans": None}, {"actions": "not-a-list"}):
        output = generate_brief(bad)
        assert output.summary.strip()
        assert output.tier in (1, 2, 3, 4)


# ── Failure case 6 — safety-critical carve-out ─────────────────────────────

SAFETY_TEXT = "Client reported self-harm urges — safety plan reviewed and updated."


def test_case6_safety_content_withheld_but_escalation_raised():
    """The content stays private; its existence does not."""
    client = make_client(
        sessions=[make_session("s1", SAFETY_TEXT)],
        consents=[],  # no consent for safety_risk
    )
    brief = brief_for(client)

    # Withheld …
    assert "safety_risk" not in brief["permitted_categories"]
    assert "self-harm" not in brief["summary"].lower()
    # … but flagged.
    assert brief["escalation_flags"], "withheld safety content raised no escalation"
    assert any("escalate" in f.lower() for f in brief["escalation_flags"])


def test_case6_escalation_flag_does_not_disclose_the_content():
    """The flag names the category and the required action, never the detail."""
    client = make_client(
        sessions=[make_session("s1", SAFETY_TEXT)],
        consents=[],
    )
    flags = " ".join(brief_for(client)["escalation_flags"]).lower()

    assert "safety_risk" in flags
    for leaked in ("self-harm", "self harm", "urges"):
        assert leaked not in flags


# ── Cross-cutting: actions survive consent filtering ───────────────────────


def test_high_priority_actions_survive_total_consent_denial():
    """Withholding every category must not delete operational continuity."""
    client = make_client(
        sessions=[make_session("s1", SAFETY_TEXT)],
        consents=[],
        actions=[make_action("A1", "HIGH"), make_action("A2", "MEDIUM")],
    )
    brief = brief_for(client)

    assert brief["permitted_categories"] == []
    carried = {a["action_id"]: a for a in brief["actions"]}
    assert "A1" in carried
    assert carried["A1"]["owner_role"] and carried["A1"]["due_date"]


@pytest.mark.parametrize(
    ("days_overdue", "expected_level"),
    [(-1, 0), (0, 0), (1, 1), (3, 1), (4, 2), (6, 2), (7, 3), (30, 3)],
)
def test_escalation_ladder_boundaries(days_overdue: int, expected_level: int):
    """Day 7 resolves to level 3, the higher of the two overlapping spec bands."""
    due = (NOW - timedelta(days=days_overdue)).isoformat()
    assert escalation_level(due, NOW) == expected_level


def test_no_unresolved_high_priority_action_disappears_between_briefs():
    overdue = make_action("A1", "HIGH", days_until_due=-10)
    upcoming = make_action("A2", "HIGH", days_until_due=3)

    previous = track_all([overdue, upcoming], NOW)
    current = track_all([overdue, upcoming], NOW + timedelta(days=1))

    assert dropped_high_priority(previous, current) == []


def test_completed_actions_are_allowed_to_disappear():
    open_action = make_action("A1", "HIGH", days_until_due=-10)
    completed = {**open_action, "status": "completed"}

    previous = track_all([open_action], NOW)
    current = track_all([completed], NOW)

    assert current == []
    assert dropped_high_priority(previous, current) == ["A1"]
