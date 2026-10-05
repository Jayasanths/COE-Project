"""
Tolerance tests for real failure states beyond synthetic data:
- Malformed inputs, missing dictionary keys, null values
- Corrupted text, unicode anomalies, null bytes, extreme string lengths
- Corrupted actions, unparseable dates, negative overdue days, invalid priority ratings
- Tagger input resilience, fallback tier survival
"""

from __future__ import annotations

from datetime import datetime, timedelta

from src.actions.tracker import (
    days_overdue,
    escalation_level,
    record_action_outcome,
    track,
    verify_action_integrity,
    verify_escalation_resolution,
)
from src.pipeline import build_brief
from src.policy.categories import RecipientRole
from src.tagger.tagger import split_sentences, tag


def test_tagger_none_and_corrupted_inputs():
    assert split_sentences(None) == []  # type: ignore
    assert split_sentences("") == []
    assert split_sentences("   ") == []
    assert split_sentences(12345) == []  # type: ignore

    # Null bytes inside text
    res = split_sentences("Patient presented with panic.\x00 Severe anxiety noted.")
    assert len(res) == 2
    assert "panic." in res[0]

    # Extreme length string
    huge_text = "Patient was seen. " * 5000
    spans = tag(huge_text, session_id="huge_01")
    assert isinstance(spans, list)


def test_pipeline_missing_keys_graceful():
    # Empty client dictionary
    brief = build_brief({})
    assert brief["tier"] in [3, 4]
    assert brief["withheld_count"] == 0
    assert isinstance(brief["actions"], list)
    assert isinstance(brief["goals"], list)

    # Corrupted sessions array
    corrupted_client = {
        "client_id": "ERR_01",
        "pseudonym": "Jane Doe",
        "sessions": [
            None,
            "invalid_string_instead_of_dict",
            {"date": "invalid_date", "text": None},
            {"date": "2025-01-01", "text": "Patient was seen for review."},
        ],
        "consents": [
            None,
            {"category": "invalid_cat", "recipient_role": "counsellor"},
            {"category": "medication", "recipient_role": "invalid_role"},
        ],
        "goals": [
            None,
            {"text": ""},
            {"text": "Goal 1", "status": "completed"},
            {"text": "Goal 2", "status": "open"},
        ],
        "actions": [
            None,
            {"action_id": "A1", "due_date": "not_a_date", "owner_role": ""},
        ],
    }

    brief = build_brief(corrupted_client, role=RecipientRole.COUNSELLOR)
    assert brief["client_id"] == "ERR_01"
    assert "Goal 2 (open)" in brief["goals"]
    assert len(brief["actions"]) == 1


def test_action_tracker_real_failure_states():
    now = datetime(2025, 3, 1)

    # Empty action
    act = track({}, now)
    assert act.action_id == ""
    assert act.escalation_level == 0
    assert act.days_overdue == 0
    assert act.has_full_ownership is False

    # Unparseable due dates do not crash
    assert days_overdue("invalid-iso-date", now) == 0
    assert escalation_level("not-a-date", now) == 0

    # Future date gives 0 overdue days
    future_date = (now + timedelta(days=10)).isoformat()
    assert days_overdue(future_date, now) == 0

    # Action integrity verification
    bad_act = {"action_id": "X1", "owner_role": "", "due_date": "bad_date"}
    integrity = verify_action_integrity(bad_act)
    assert integrity["is_valid"] is False
    assert integrity["has_owner"] is False
    assert integrity["has_valid_due_date"] is False

    good_act = {
        "action_id": "X2",
        "owner_role": "social_worker",
        "due_date": "2025-03-10",
        "priority": "HIGH",
    }
    good_integrity = verify_action_integrity(good_act)
    assert good_integrity["is_valid"] is True
    assert good_integrity["has_owner"] is True
    assert good_integrity["has_valid_due_date"] is True


def test_action_outcome_verification_lifecycle():
    now = datetime(2025, 3, 1)
    act = {
        "action_id": "ACT-99",
        "description": "Arrange housing assessment",
        "owner_role": "social_worker",
        "due_date": "2025-02-15",
        "priority": "HIGH",
        "status": "open",
    }

    # Verify action outcome
    updated = record_action_outcome(
        act,
        outcome_status="completed",
        verified_by_role="social_worker",
        outcome_notes="Housing secured through emergency trust fund.",
        now=now,
    )
    assert updated["status"] == "completed"
    assert updated["verified"] is True
    assert updated["verification_status"] == "outcome_confirmed"

    # Escalation resolution
    escalated_act = dict(act)
    escalated_act["status"] = "open"
    res = verify_escalation_resolution(
        escalated_act,
        resolution_notes="Supervisor approved 1-to-1 care worker assignment.",
        supervisor_id="SUP-42",
        now=now,
    )
    assert res["status"] == "completed"
    assert res["verification_status"] == "escalated_resolved"
    assert "SUP-42" in res["outcome_notes"]
