"""Action tracking endpoint."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException

from ..actions.tracker import build_digest
from .briefs import get_store

router = APIRouter()


@router.get("/{client_id}")
def get_actions(client_id: str) -> dict:
    """Open actions with computed escalation levels, notifications and red flags."""
    client = get_store().get(client_id)
    if client is None:
        raise HTTPException(status_code=404, detail=f"Client {client_id} not found")

    digest = build_digest(client.get("actions", []), datetime.utcnow())
    return {
        "client_id": client_id,
        "actions": [a.to_dict() for a in digest.actions],
        "red_flags": digest.red_flags,
        "notifications": digest.notifications,
    }
