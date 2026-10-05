"""SQLModel database models — mirrors the 7-table schema."""

from __future__ import annotations

from datetime import datetime

from sqlmodel import Field, SQLModel


class Client(SQLModel, table=True):
    client_id: str = Field(primary_key=True)
    pseudonym: str
    episode_id: str
    discharge_date: datetime


class SessionSummary(SQLModel, table=True):
    session_id: str = Field(primary_key=True)
    client_id: str = Field(foreign_key="client.client_id")
    author_role: str
    date: datetime
    text: str
    source_span_ids: str = ""  # JSON list


class SensitivityTag(SQLModel, table=True):
    span_id: str = Field(primary_key=True)
    session_id: str = Field(foreign_key="sessionsummary.session_id")
    category: str
    confidence: float
    is_safety_relevant: bool = False
    tagger_version: str = "1.0"


class ConsentRecord(SQLModel, table=True):
    consent_id: str = Field(primary_key=True)
    client_id: str = Field(foreign_key="client.client_id")
    category: str
    recipient_role: str
    purpose: str
    granted: bool
    granted_at: datetime
    expires_at: datetime | None = None
    revoked_at: datetime | None = None


class ClientGoal(SQLModel, table=True):
    goal_id: str = Field(primary_key=True)
    client_id: str = Field(foreign_key="client.client_id")
    text: str
    status: str
    priority: str
    review_date: datetime


class PendingAction(SQLModel, table=True):
    action_id: str = Field(primary_key=True)
    client_id: str = Field(foreign_key="client.client_id")
    description: str
    owner_role: str
    owner_id: str
    due_date: datetime
    priority: str
    status: str
    escalation_level: int = 0


class DisclosureAudit(SQLModel, table=True):
    event_id: str = Field(primary_key=True)
    brief_id: str
    recipient_role: str
    categories_shown: str  # JSON list
    categories_withheld: str  # JSON list
    override_flag: bool = False
    justification: str = ""
    timestamp: datetime = Field(default_factory=datetime.utcnow)
