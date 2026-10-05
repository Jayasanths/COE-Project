"""
Contradiction detection — failure case 2.

Sessions written by different staff on different days routinely disagree.
Week one: "Client reports being sober for 3 weeks." Week three: "Client
admitted to relapse over the weekend."

A summariser handed both will usually pick one. Which one it picks depends on
ordering, recency weighting or sampling — none of which the reader can see. If
it picks the sober line, the incoming counsellor walks in believing the client
is in recovery. That is a worse outcome than no summary, because the reader has
no signal that anything was dropped.

So contradictions are surfaced, never resolved. This module does not decide
which statement is true; it has no basis to. It detects that two permitted
statements in the same category carry opposing polarity, and hands both to the
reader with a notice attached.

Detection is lexical polarity matching within a category, deliberately narrow.
It fires on the disagreements that recur in discharge notes — abstinence vs
relapse, adherence vs non-adherence, risk present vs risk absent — and misses
subtler ones. A missed contradiction leaves the brief no worse than a system
without this module; a false one wastes thirty seconds of a clinician's time.
Both are acceptable. Silently choosing a side is not.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..policy.categories import SensitivityCategory

C = SensitivityCategory


@dataclass(frozen=True)
class PolarityRule:
    """Opposing lexical cues within one sensitivity category."""

    category: SensitivityCategory
    positive_label: str  # what the "improving" pole means clinically
    negative_label: str
    positive_cues: tuple[str, ...]
    negative_cues: tuple[str, ...]


POLARITY_RULES: tuple[PolarityRule, ...] = (
    PolarityRule(
        category=C.SUBSTANCE_USE,
        positive_label="abstinence reported",
        negative_label="ongoing use or relapse reported",
        positive_cues=("sober", "sobriety", "abstinent", "abstinence", "clean for"),
        negative_cues=(
            "relapse",
            "relapsed",
            "returned to",
            "ongoing alcohol use",
            "ongoing use",
            "using again",
            "units daily",
        ),
    ),
    PolarityRule(
        category=C.MEDICATION,
        positive_label="adherent, no adverse effects",
        negative_label="non-adherence or side effects reported",
        positive_cues=(
            "no side effects",
            "adherent",
            "compliant",
            "within therapeutic range",
        ),
        negative_cues=(
            "non-adherent",
            "not adherent",
            "missed dose",
            "missed doses",
            "declined medication",
            "side effects reported",
        ),
    ),
    PolarityRule(
        category=C.SAFETY_RISK,
        positive_label="no current risk identified",
        negative_label="active risk indicators reported",
        positive_cues=(
            "no current risk",
            "no risk identified",
            "protective factors strong",
            "denies ideation",
        ),
        negative_cues=(
            "suicidal ideation",
            "self-harm urges",
            "self harm urges",
            "risk assessment completed",
            "expressed intent",
        ),
    ),
    PolarityRule(
        category=C.FAMILY_CONFLICT,
        positive_label="family contact going well",
        negative_label="family contact causing distress or estrangement",
        positive_cues=(
            "family contact positive",
            "rebuilt contact",
            "supportive family",
        ),
        negative_cues=(
            "estranged",
            "heightened distress",
            "boundaries discussed",
            "declined contact",
        ),
    ),
)

_RULES_BY_CATEGORY = {r.category: r for r in POLARITY_RULES}


@dataclass
class Conflict:
    category: str
    positive_label: str
    negative_label: str
    positive_text: str
    negative_text: str

    @property
    def notice(self) -> str:
        return (
            f"CONFLICTING RECORDS — {self.category}: the notes contain both "
            f"'{self.positive_label}' and '{self.negative_label}'. Both statements "
            "are shown below; neither has been treated as correct. Confirm the "
            "current position with the client."
        )

    def to_dict(self) -> dict:
        return {
            "category": self.category,
            "positive_label": self.positive_label,
            "negative_label": self.negative_label,
            "positive_text": self.positive_text,
            "negative_text": self.negative_text,
            "notice": self.notice,
        }


def _matches(text: str, cues: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(re.search(rf"\b{re.escape(cue)}", lowered) for cue in cues)


def detect_conflicts(permitted_spans: list[dict]) -> list[Conflict]:
    """Find opposing-polarity statements among *permitted* spans only.

    Withheld spans are excluded by construction — the caller passes the
    post-filter set. That ordering matters: reporting a contradiction between a
    permitted statement and a withheld one would disclose the existence and
    rough content of the withheld statement, turning a transparency feature
    into a consent bypass.
    """
    by_category: dict[str, list[str]] = {}
    for span in permitted_spans:
        by_category.setdefault(span.get("category", ""), []).append(
            span.get("text", "")
        )

    conflicts: list[Conflict] = []
    for category_value, texts in sorted(by_category.items()):
        try:
            rule = _RULES_BY_CATEGORY[SensitivityCategory(category_value)]
        except (ValueError, KeyError):
            continue

        positive = next((t for t in texts if _matches(t, rule.positive_cues)), None)
        negative = next((t for t in texts if _matches(t, rule.negative_cues)), None)

        # A single sentence can legitimately carry both poles — "was sober but
        # relapsed at the weekend" is a coherent narrative, not a conflict.
        # Only flag when the two poles come from different sentences.
        if positive and negative and positive != negative:
            conflicts.append(
                Conflict(
                    category=category_value,
                    positive_label=rule.positive_label,
                    negative_label=rule.negative_label,
                    positive_text=positive,
                    negative_text=negative,
                )
            )

    return conflicts
