"""
Tests for SQLModel schema models in `src/models.py`.
"""

from __future__ import annotations

from datetime import datetime

from src.models import (
    Client,
    ClientGoal,
    ConsentRecord,
    DisclosureAudit,
    PendingAction,
    SensitivityTag,
    SessionSummary,
)


def test_client_model():
    client = Client(
        client_id="C001",
        pseudonym="Patient Alpha",
        episode_id="EP-101",
        discharge_date=datetime(2025, 3, 15),
    )
    assert client.client_id == "C001"
    assert client.pseudonym == "Patient Alpha"
    assert client.episode_id == "EP-101"
    assert client.discharge_date.year == 2025


def test_session_summary_model():
    session = SessionSummary(
        session_id="S001",
        client_id="C001",
        author_role="psychiatrist",
        date=datetime(2025, 3, 10),
        text="Review of medication compliance.",
        source_span_ids="[]",
    )
    assert session.session_id == "S001"
    assert session.author_role == "psychiatrist"


def test_sensitivity_tag_model():
    tag = SensitivityTag(
        span_id="sp01",
        session_id="S001",
        category="medication",
        confidence=0.95,
        is_safety_relevant=False,
    )
    assert tag.span_id == "sp01"
    assert tag.confidence == 0.95
    assert tag.tagger_version == "1.0"


def test_consent_record_model():
    consent = ConsentRecord(
        consent_id="CR-01",
        client_id="C001",
        category="medication",
        recipient_role="counsellor",
        purpose="handover",
        granted=True,
        granted_at=datetime(2025, 1, 1),
    )
    assert consent.granted is True
    assert consent.expires_at is None
    assert consent.revoked_at is None


def test_client_goal_model():
    goal = ClientGoal(
        goal_id="G01",
        client_id="C001",
        text="Maintain stable mood",
        status="in_progress",
        priority="HIGH",
        review_date=datetime(2025, 4, 1),
    )
    assert goal.status == "in_progress"
    assert goal.priority == "HIGH"


def test_pending_action_model():
    action = PendingAction(
        action_id="ACT-01",
        client_id="C001",
        description="Schedule outpatient psychiatric review",
        owner_role="psychiatrist",
        owner_id="DR-09",
        due_date=datetime(2025, 3, 20),
        priority="HIGH",
        status="open",
        escalation_level=0,
    )
    assert action.action_id == "ACT-01"
    assert action.escalation_level == 0


def test_disclosure_audit_model():
    audit = DisclosureAudit(
        event_id="AUD-01",
        brief_id="BR-01",
        recipient_role="counsellor",
        categories_shown='["trauma_history"]',
        categories_withheld='["financial"]',
        override_flag=False,
    )
    assert audit.event_id == "AUD-01"
    assert audit.override_flag is False
    assert isinstance(audit.timestamp, datetime)
