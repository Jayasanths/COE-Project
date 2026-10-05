"""Consent console endpoint (read-only)."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException

from ..pipeline import build_consent_records
from .briefs import get_store

router = APIRouter()


@router.get("/{client_id}")
def get_consent(client_id: str) -> dict:
    """Return every consent record with its current active/inactive status.

    Status is computed with the same `is_active` check the policy engine uses,
    rather than re-derived from the raw dates here. A consent console that
    disagreed with the engine about whether a record is live would be worse
    than no console at all.
    """
    client = get_store().get(client_id)
    if client is None:
        raise HTTPException(status_code=404, detail=f"Client {client_id} not found")

    now = datetime.utcnow()
    records = build_consent_records(client)

    return {
        "client_id": client_id,
        "pseudonym": client.get("pseudonym", ""),
        "evaluated_at": now.isoformat(),
        "consents": [
            {
                "category": r.category.value,
                "recipient_role": r.recipient_role.value,
                "purpose": r.purpose.value,
                "granted": r.granted,
                "granted_at": r.granted_at.isoformat(),
                "expires_at": r.expires_at.isoformat() if r.expires_at else None,
                "revoked_at": r.revoked_at.isoformat() if r.revoked_at else None,
                "active": r.is_active(now),
            }
            for r in records
        ],
    }
