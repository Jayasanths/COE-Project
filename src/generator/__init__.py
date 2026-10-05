"""Summary generation, fallback ladder, conflict detection and explanations."""

from .conflicts import Conflict, detect_conflicts
from .explainer import Explanation, WithholdReason, explain
from .generator import TIER_LABELS, BriefOutput, generate_brief, grounding_score

__all__ = [
    "generate_brief",
    "BriefOutput",
    "TIER_LABELS",
    "grounding_score",
    "explain",
    "Explanation",
    "WithholdReason",
    "detect_conflicts",
    "Conflict",
]
