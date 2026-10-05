"""Client list endpoint."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter

from ..actions.tracker import track_all
from .briefs import get_store

router = APIRouter()


@router.get("/")
def list_clients() -> dict:
    """List clients with the counts a triaging clinician sorts by.

    Open high-priority and red-flag counts are computed here rather than in the
    UI so the list and the brief cannot disagree about how many actions are
    outstanding — both read the same tracker.
    """
    now = datetime.utcnow()
    clients = []
    for client_id, client in get_store().items():
        tracked = track_all(client.get("actions", []), now)
        clients.append(
            {
                "client_id": client_id,
                "pseudonym": client.get("pseudonym", ""),
                "discharge_date": client.get("discharge_date", ""),
                "open_high_priority": sum(1 for a in tracked if a.is_high_priority),
                "red_flags": sum(1 for a in tracked if a.is_red_flag),
            }
        )
    clients.sort(
        key=lambda c: (-c["red_flags"], -c["open_high_priority"], c["client_id"])
    )
    return {"clients": clients}
