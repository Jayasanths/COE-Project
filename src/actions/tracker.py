"""
Action tracker with escalation — Stage 6.

Pending actions are the part of a handover that consent filtering must not
touch. "Refer to housing support, owner social_worker, due 14 March" contains
no clinical disclosure; it is operational continuity. If it were routed through
the consent filter, a client withholding their financial history would also
silently lose their housing referral — the exact failure this system exists to
prevent, reintroduced through a side door.

So actions travel on a parallel track: filtered for status only, never for
category, and always carrying owner and due date.

Escalation ladder
-----------------
    level 0   open, on or before the due date
    level 1   1-3 days overdue      notify owner
    level 2   4-6 days overdue      notify supervisor
    level 3   7+ days overdue       red flag in every brief until resolved

The build spec writes the bands as "4-7" and "7+", which overlap at day
seven. Resolved in favour of the higher level: a week overdue is a week
overdue, and when a boundary is ambiguous the safe reading is the one that
escalates sooner rather than later.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

# Lower bound in whole days overdue for each level.
LEVEL_1_DAYS = 1
LEVEL_2_DAYS = 4
LEVEL_3_DAYS = 7

LEVEL_ACTIONS: dict[int, str] = {
    0: "On track — no escalation.",
    1: "Overdue — notify the owner.",
    2: "Overdue 4+ days — notify the supervisor.",
    3: "Overdue 7+ days — red flag, appears in every brief until resolved.",
}

CLOSED_STATUSES = frozenset({"completed", "cancelled"})
HIGH = "HIGH"


@dataclass
class TrackedAction:
    """One pending action with its computed escalation state."""

    action_id: str
    description: str
    owner_role: str
    owner_id: str
    due_date: str
    priority: str
    status: str
    escalation_level: int
    days_overdue: int
    escalation_note: str

    @property
    def is_high_priority(self) -> bool:
        return self.priority.upper() == HIGH

    @property
    def is_red_flag(self) -> bool:
        return self.escalation_level >= 3

    @property
    def has_full_ownership(self) -> bool:
        """Owner and due date must both be present for the action to be actionable.

        An action with no owner is a wish. The eval harness scores this
        directly as action_retention_rate, so it is a property rather than a
        rendering concern.
        """
        return bool(self.owner_role and self.due_date)

    def to_dict(self) -> dict:
        return {
            "action_id": self.action_id,
            "description": self.description,
            "owner_role": self.owner_role,
            "owner_id": self.owner_id,
            "due_date": self.due_date,
            "priority": self.priority,
            "status": self.status,
            "escalation_level": self.escalation_level,
            "days_overdue": self.days_overdue,
            "escalation_note": self.escalation_note,
        }


def _parse_date(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def days_overdue(due_date: str, now: datetime) -> int:
    """Whole days past due. Zero if not yet due, or if the date is unparseable.

    An unparseable due date returns 0 rather than raising. The action still
    appears in the brief with its description and owner intact — a malformed
    date must not be able to delete a pending task from a handover.
    """
    due = _parse_date(due_date)
    if due is None:
        return 0
    delta = (now - due).days
    return max(delta, 0)


def escalation_level(due_date: str, now: datetime, status: str = "open") -> int:
    """Map a due date to an escalation level. Closed actions never escalate."""
    if status.lower() in CLOSED_STATUSES:
        return 0
    overdue = days_overdue(due_date, now)
    if overdue >= LEVEL_3_DAYS:
        return 3
    if overdue >= LEVEL_2_DAYS:
        return 2
    if overdue >= LEVEL_1_DAYS:
        return 1
    return 0


def track(action: dict, now: datetime) -> TrackedAction:
    """Compute escalation state for one raw action dict."""
    status = str(action.get("status", "open"))
    due_date = str(action.get("due_date", ""))
    level = escalation_level(due_date, now, status)
    return TrackedAction(
        action_id=str(action.get("action_id", "")),
        description=str(action.get("description", "")),
        owner_role=str(action.get("owner_role", "")),
        owner_id=str(action.get("owner_id", "")),
        due_date=due_date,
        priority=str(action.get("priority", "MEDIUM")),
        status=status,
        escalation_level=level,
        days_overdue=days_overdue(due_date, now),
        escalation_note=LEVEL_ACTIONS[level],
    )


def track_all(actions: list[dict], now: datetime) -> list[TrackedAction]:
    """Track every open action, most urgent first.

    Sort order is escalation level desc, then high priority, then days overdue
    desc, then due date. The reader's eye lands on the thing that will hurt
    someone first.
    """
    tracked = [track(a, now) for a in actions if str(a.get("status", "open")).lower() not in CLOSED_STATUSES]
    tracked.sort(
        key=lambda a: (
            -a.escalation_level,
            not a.is_high_priority,
            -a.days_overdue,
            a.due_date,
        )
    )
    return tracked


@dataclass
class ActionDigest:
    """Everything a brief needs to say about actions."""

    actions: list[TrackedAction] = field(default_factory=list)
    red_flags: list[str] = field(default_factory=list)
    notifications: list[str] = field(default_factory=list)

    @property
    def high_priority(self) -> list[TrackedAction]:
        return [a for a in self.actions if a.is_high_priority]

    @property
    def all_high_priority_have_ownership(self) -> bool:
        return all(a.has_full_ownership for a in self.high_priority)


def build_digest(actions: list[dict], now: datetime) -> ActionDigest:
    """Track actions and derive the notifications and red flags for a brief."""
    tracked = track_all(actions, now)
    digest = ActionDigest(actions=tracked)

    for action in tracked:
        if action.escalation_level >= 3:
            digest.red_flags.append(
                f"RED FLAG — '{action.description}' is {action.days_overdue} days "
                f"overdue (owner: {action.owner_role}, due {action.due_date[:10]}). "
                "Resolve or reassign before the session."
            )
        elif action.escalation_level == 2:
            digest.notifications.append(
                f"Notify supervisor — '{action.description}' is "
                f"{action.days_overdue} days overdue (owner: {action.owner_role})."
            )
        elif action.escalation_level == 1:
            digest.notifications.append(
                f"Notify owner ({action.owner_role}) — '{action.description}' is "
                f"{action.days_overdue} day(s) overdue."
            )

    return digest


def dropped_high_priority(
    previous: list[TrackedAction],
    current: list[TrackedAction],
) -> list[str]:
    """Return high-priority action ids that vanished between two briefs.

    The invariant is that no unresolved high-priority action may disappear from
    consecutive briefs. Resolving one is fine — that is a status change, and
    closed actions are filtered out upstream. Vanishing without being resolved
    is a continuity bug, and this is what `test_failure_cases.py` asserts on.

    Returning ids rather than raising keeps the check usable both as a test
    assertion and as a runtime audit signal.
    """
    previous_ids = {a.action_id for a in previous if a.is_high_priority}
    current_ids = {a.action_id for a in current if a.is_high_priority}
    return sorted(previous_ids - current_ids)
