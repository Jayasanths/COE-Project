"""
Handover brief endpoint.

    GET /api/briefs/{client_id}?role=counsellor&purpose=handover&tier=

A thin shell over `src.pipeline.build_brief`. All consent logic, tagging,
generation and explanation live in the pipeline; this module's only jobs are
HTTP concerns and response typing.

That split is deliberate. The evaluation harness calls the pipeline directly, so
the numbers in the report describe the same code path that serves this endpoint.
If brief assembly lived in the router, the eval would have to reimplement it and
the two could drift — with the report claiming a leakage rate the API no longer
achieves.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ..pipeline import build_brief
from ..policy.categories import ConsentPurpose, RecipientRole

router = APIRouter()

DATA_PATH = Path("data/synthetic/clients.json")

# In-memory store. Swap for the SQLModel session in production; the pipeline
# takes plain dicts, so nothing below the router changes when that happens.
_CLIENT_STORE: dict[str, dict] = {}


def load_clients() -> None:
    """Load synthetic clients from disk. Safe to call repeatedly."""
    if not DATA_PATH.exists():
        return
    payload = json.loads(DATA_PATH.read_text())
    for client in payload.get("clients", []):
        _CLIENT_STORE[client["client_id"]] = client


def get_store() -> dict[str, dict]:
    """Return the client store, loading it on first access."""
    if not _CLIENT_STORE:
        load_clients()
    return _CLIENT_STORE


# ── Response models ────────────────────────────────────────────────────────


class ActionItem(BaseModel):
    action_id: str
    description: str
    owner_role: str
    owner_id: str = ""
    due_date: str
    priority: str
    status: str = "open"
    escalation_level: int = 0
    days_overdue: int = 0
    escalation_note: str = ""
    verified: bool = False
    verified_by_role: str = ""
    verified_at: str = ""
    verification_status: str = "unverified"
    outcome_notes: str = ""


class WithheldReasonItem(BaseModel):
    category: str
    reason_code: str
    detail: str
    is_safety_relevant: bool = False


class ShownReasonItem(BaseModel):
    category: str
    detail: str


class ExplanationBlock(BaseModel):
    summary: str
    why_shown: list[ShownReasonItem] = []
    why_withheld: list[WithheldReasonItem] = []


class ConflictItem(BaseModel):
    category: str
    positive_label: str
    negative_label: str
    positive_text: str
    negative_text: str
    notice: str


class HandoverBrief(BaseModel):
    client_id: str
    pseudonym: str = ""
    recipient_role: str
    purpose: str
    generated_at: str

    tier: int
    tier_label: str
    summary: str
    facts: dict[str, Any] | None = None
    word_count: int

    permitted_categories: list[str]
    withheld_count: int
    withheld_categories: list[str]
    withheld_notice: str

    escalation_flags: list[str]
    notifications: list[str]
    conflicts: list[ConflictItem] = []
    conflict_notices: list[str] = []
    consent_missing: list[str]

    actions: list[ActionItem]
    goals: list[str]

    explanation: ExplanationBlock
    uncertainty_note: str
    provenance: list[str] = []
    degradation_reasons: list[str] = []
    total_spans: int = 0
    permitted_span_count: int = 0


# ── Endpoints ──────────────────────────────────────────────────────────────


@router.get("/{client_id}", response_model=HandoverBrief)
def get_brief(
    client_id: str,
    role: RecipientRole = Query(default=RecipientRole.COUNSELLOR),
    purpose: ConsentPurpose = Query(default=ConsentPurpose.HANDOVER),
    tier: int | None = Query(
        default=None,
        ge=1,
        le=4,
        description=(
            "Pin the starting fallback tier, for demonstrating degraded modes. "
            "Fallback below the pinned tier still applies."
        ),
    ),
) -> HandoverBrief:
    client = get_store().get(client_id)
    if client is None:
        raise HTTPException(status_code=404, detail=f"Client {client_id} not found")

    return HandoverBrief(**build_brief(client, role, purpose, tier_override=tier))
