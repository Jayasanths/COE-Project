"""Action tracking endpoint."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..actions.tracker import (
    build_digest,
    record_action_outcome,
    verify_action_integrity,
    verify_escalation_resolution,
)
from .briefs import get_store

router = APIRouter()


class VerifyActionRequest(BaseModel):
    status: str = Field(
        default="completed",
        description="New status (e.g., in_progress, completed, cancelled)",
    )
    verified_by_role: str = Field(
        default="counsellor", description="Clinical role verifying the action"
    )
    outcome_notes: str = Field(
        default="", description="Verification outcome or handoff note"
    )
    supervisor_id: str | None = Field(
        default=None, description="Supervisor ID if resolving an escalation"
    )


@router.get("/")
def list_all_actions() -> dict:
    """List all open actions across all clients in the ward, sorted by urgency."""
    now = datetime.utcnow()
    all_tracked = []
    total_red_flags = 0
    total_verified = 0
    for client_id, client in get_store().items():
        digest = build_digest(client.get("actions", []), now)
        total_red_flags += len(digest.red_flags)
        total_verified += digest.verified_count
        for a in digest.actions:
            d = a.to_dict()
            d["client_id"] = client_id
            d["pseudonym"] = client.get("pseudonym", "")
            all_tracked.append(d)
    all_tracked.sort(
        key=lambda a: (-a["escalation_level"], a["priority"] != "HIGH", a["due_date"])
    )
    return {
        "actions": all_tracked,
        "total_count": len(all_tracked),
        "total_red_flags": total_red_flags,
        "total_verified": total_verified,
    }


@router.get("/{client_id}")
def get_actions(client_id: str) -> dict:
    """Open actions with computed escalation levels, notifications, red flags, and verification metrics."""
    client = get_store().get(client_id)
    if client is None:
        raise HTTPException(status_code=404, detail=f"Client {client_id} not found")

    digest = build_digest(client.get("actions", []), datetime.utcnow())
    return {
        "client_id": client_id,
        "actions": [a.to_dict() for a in digest.actions],
        "red_flags": digest.red_flags,
        "notifications": digest.notifications,
        "verified_count": digest.verified_count,
        "unverified_count": digest.unverified_count,
        "verification_rate": digest.verification_rate,
        "all_high_priority_have_ownership": digest.all_high_priority_have_ownership,
    }


@router.post("/{client_id}/{action_id}/verify")
def verify_action(client_id: str, action_id: str, req: VerifyActionRequest) -> dict:
    """Record outcome verification, acknowledge escalations, or update action status."""
    client = get_store().get(client_id)
    if client is None:
        raise HTTPException(status_code=404, detail=f"Client {client_id} not found")

    actions = client.get("actions", [])
    target_action = None
    target_idx = -1
    for idx, act in enumerate(actions):
        if str(act.get("action_id")) == action_id:
            target_action = act
            target_idx = idx
            break

    if target_action is None or target_idx == -1:
        raise HTTPException(
            status_code=404,
            detail=f"Action {action_id} not found for client {client_id}",
        )

    # Check if supervisor resolution requested
    if req.supervisor_id:
        updated = verify_escalation_resolution(
            target_action,
            resolution_notes=req.outcome_notes,
            supervisor_id=req.supervisor_id,
            now=datetime.utcnow(),
        )
    else:
        updated = record_action_outcome(
            target_action,
            outcome_status=req.status,
            verified_by_role=req.verified_by_role,
            outcome_notes=req.outcome_notes,
            now=datetime.utcnow(),
        )

    # Persist in memory store for the session
    actions[target_idx] = updated
    client["actions"] = actions

    integrity = verify_action_integrity(updated)

    return {
        "status": "success",
        "action_id": action_id,
        "action": updated,
        "integrity": integrity,
    }
