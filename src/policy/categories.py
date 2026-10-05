"""
Sensitivity categories and role definitions.
This file is HAND-WRITTEN and must not be modified by agents.
"""

from enum import Enum


class SensitivityCategory(str, Enum):
    SUBSTANCE_USE = "substance_use"
    TRAUMA_HISTORY = "trauma_history"
    FORENSIC_LEGAL = "forensic_legal"
    SEXUAL_HEALTH = "sexual_health"
    FAMILY_CONFLICT = "family_conflict"
    MEDICATION = "medication"
    FINANCIAL = "financial"
    # Special — always shown when present, even if category withheld
    SAFETY_RISK = "safety_risk"


class RecipientRole(str, Enum):
    COUNSELLOR = "counsellor"
    SOCIAL_WORKER = "social_worker"
    PSYCHIATRIST = "psychiatrist"
    NURSE = "nurse"
    ADMIN = "admin"


class ConsentPurpose(str, Enum):
    HANDOVER = "handover"
    AUDIT = "audit"
    RESEARCH = "research"


# Safety-critical categories that ALWAYS generate an escalation flag
# even when their content is withheld from the brief.
SAFETY_CRITICAL: frozenset[SensitivityCategory] = frozenset(
    {
        SensitivityCategory.SAFETY_RISK,
    }
)

# Default deny — every category starts as withheld.
# Only explicit consent records override this.
DEFAULT_DECISION = "DENY"
