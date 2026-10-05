"""
Summary generator — Stage 4.

Four-tier fallback ladder. The system degrades in quality but never in safety,
and never raises to the user:

    tier 1  local LLM summary, grounded and schema-validated
    tier 2  extractive — permitted source sentences, de-duplicated, no generation
    tier 3  structured facts card — goals, open actions, consent status only
    tier 4  manual handover checklist

Descent is one-directional and automatic: any failure at tier N falls to
tier N+1, and the tier that actually produced the text is reported on the brief
so the reader always knows how much machine involvement they are looking at.
The ladder never climbs back up.

Two invariants hold at every tier:

* The generator receives only content the consent engine already permitted.
  There is no path from a withheld span into this module — filtering happens
  first, so the model physically cannot see non-permitted text.
* Withheld content is signalled, never silently dropped. Silence implies
  completeness, and a handover that looks complete but isn't is the specific
  harm this system exists to prevent.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .llm import LLMUnavailable
from .llm import generate as llm_generate
from .llm import is_enabled as llm_enabled

TIER_LABELS: dict[int, str] = {
    1: "AI-generated summary (tier 1)",
    2: "Extractive summary — source sentences only (tier 2)",
    3: "Structured facts card (tier 3)",
    4: "Manual handover required (tier 4)",
}

EXTRACTIVE_PREFIX = "Extractive summary (AI unavailable):"
MAX_EXTRACTIVE_SENTENCES = 8

# Grounding check: words that may appear in a tier-1 summary without being
# present in the source, because they are connective rather than clinical.
_FUNCTION_WORDS = frozenset(
    """
    a an and are as at be been being but by can client could did do does for
    from had has have he her him his how i if in into is it its may might more
    most no nor not of on or our over said she should so some such than that
    the their them then there these they this those to under until up was we
    were what when where which while who whom why will with would you your
    during ongoing reported reports noted remains currently also however
    """.split()
)
_WORD = re.compile(r"[a-z][a-z'-]+")

# Fraction of a tier-1 summary's content words that must appear in the source.
GROUNDING_THRESHOLD = 0.85


def _safe_list(value: object) -> list[dict]:
    """Coerce a context field to a list of dicts, discarding anything malformed.

    Tier 4's guarantee is that it always returns a brief. That guarantee is only
    real if tier 4 cannot itself raise, which means it must not assume its input
    is well-formed — an upstream bug handing it a string instead of a list would
    otherwise put a stack trace in front of a clinician at precisely the moment
    the system is already degraded. Fails to an empty list rather than guessing.
    """
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _safe_iter(value: object) -> list[str]:
    """Coerce a context field to a list of strings. Same rationale as _safe_list."""
    if isinstance(value, (list, tuple, set)):
        return [str(v) for v in value]
    return []


@dataclass
class BriefOutput:
    """What the generator hands back, whichever tier produced it."""

    tier: int
    tier_label: str
    summary: str
    # Populated at tier 3 and 4; None at tiers 1-2 where output is prose.
    facts: dict[str, Any] | None = None
    # span_ids backing the summary. Empty at tier 1 if the model paraphrased
    # across several spans, in which case source_spans below carries the set.
    provenance: list[str] = field(default_factory=list)
    # Every failed rung, in order, so the fallback is auditable after the fact.
    degradation_reasons: list[str] = field(default_factory=list)

    @property
    def is_generated(self) -> bool:
        """True only when a language model wrote the text."""
        return self.tier == 1


# ── Grounding ──────────────────────────────────────────────────────────────


def _content_words(text: str) -> set[str]:
    return {w for w in _WORD.findall(text.lower()) if w not in _FUNCTION_WORDS}


def grounding_score(summary: str, source: str) -> float:
    """Fraction of the summary's content words that occur in the source.

    This is the anti-hallucination guard. A 3B local model asked to summarise
    three sentences will sometimes add a plausible clinical detail that was
    never in the notes — a dose, a diagnosis, a date. In a handover document
    that invented detail is indistinguishable from a real observation, and the
    reader has no way to catch it.

    So tier 1 output is only accepted if it is overwhelmingly built from words
    that were already in the permitted source. It is a blunt instrument: it
    cannot catch a model that recombines real words into a false claim
    ("denies suicidal ideation" from "reports suicidal ideation"). That is why
    the tier badge is shown on the brief and provenance links are kept — the
    guard reduces the rate of invented detail, it does not license trusting
    tier 1 output unread.
    """
    summary_words = _content_words(summary)
    if not summary_words:
        return 0.0
    source_words = _content_words(source)
    return len(summary_words & source_words) / len(summary_words)


# ── Tier 1 ─────────────────────────────────────────────────────────────────


def _tier1(context: dict) -> BriefOutput:
    spans = _safe_list(context.get("permitted_spans"))
    if not spans:
        raise LLMUnavailable("tier 1 skipped: no permitted content to summarise")

    source = " ".join(str(s.get("text", "")) for s in spans)
    prompt = (
        "Summarise the following permitted clinical handover content for a "
        f"{context.get('recipient_role', 'clinician')}. Use only what is "
        "written here.\n\n"
        f"{source}"
    )

    result = llm_generate(prompt)

    score = grounding_score(result.summary, source)
    if score < GROUNDING_THRESHOLD:
        raise LLMUnavailable(
            f"tier 1 output failed grounding check ({score:.2f} < {GROUNDING_THRESHOLD})"
        )

    return BriefOutput(
        tier=1,
        tier_label=TIER_LABELS[1],
        summary=result.summary,
        provenance=[str(s.get("span_id", "")) for s in spans],
    )


# ── Tier 2 ─────────────────────────────────────────────────────────────────


def _dedupe(sentences: list[str]) -> list[str]:
    """Drop repeats while preserving first-seen order.

    Sessions repeat near-identical lines across days ("No current risk
    identified."), so comparison is on a normalised key — casefolded, internal
    whitespace collapsed, trailing punctuation stripped — while the original
    text is what gets kept.
    """
    seen: set[str] = set()
    out: list[str] = []
    for sentence in sentences:
        key = re.sub(r"\s+", " ", sentence.strip().casefold()).rstrip(".!?;: ")
        if key and key not in seen:
            seen.add(key)
            out.append(sentence.strip())
    return out


def _tier2(context: dict) -> BriefOutput:
    spans = _safe_list(context.get("permitted_spans"))
    if not spans:
        raise ValueError("tier 2 unavailable: no permitted spans to extract")

    sentences = _dedupe([str(s.get("text", "")) for s in spans])[
        :MAX_EXTRACTIVE_SENTENCES
    ]
    kept = set(sentences)
    return BriefOutput(
        tier=2,
        tier_label=TIER_LABELS[2],
        summary=f"{EXTRACTIVE_PREFIX} " + " ".join(sentences),
        provenance=[
            str(s.get("span_id", ""))
            for s in spans
            if str(s.get("text", "")).strip() in kept
        ],
    )


# ── Tier 3 ─────────────────────────────────────────────────────────────────


def _tier3(context: dict) -> BriefOutput:
    """Structured facts only — no free text, nothing that reads as narrative.

    This is the rung for a client whose entire session content is withheld.
    The card still carries goals, open actions and consent status, because none
    of those are consent-filtered clinical disclosures: an action with an owner
    and a due date is operational information the receiving clinician needs in
    order to do their job safely.
    """
    facts = {
        "client_id": context.get("client_id", "unknown"),
        "recipient_role": context.get("recipient_role", "unknown"),
        "goals": [str(g) for g in _safe_iter(context.get("goals"))],
        "open_actions": [
            {
                "description": a.get("description", ""),
                "owner_role": a.get("owner_role", ""),
                "owner_id": a.get("owner_id", ""),
                "due_date": a.get("due_date", ""),
                "priority": a.get("priority", "MEDIUM"),
                "escalation_level": a.get("escalation_level", 0),
            }
            for a in _safe_list(context.get("actions"))
        ],
        "permitted_categories": sorted(_safe_iter(context.get("permitted_categories"))),
        "withheld_categories": sorted(_safe_iter(context.get("withheld_categories"))),
        "consent_missing": sorted(_safe_iter(context.get("consent_missing"))),
    }

    if not (facts["goals"] or facts["open_actions"] or facts["withheld_categories"]):
        raise ValueError("tier 3 unavailable: no structured facts to show")

    lines = ["Structured facts card — no disclosable session narrative for this role."]
    if facts["withheld_categories"]:
        lines.append(
            f"{len(facts['withheld_categories'])} topic(s) withheld under client consent."
        )
    if facts["open_actions"]:
        lines.append(f"{len(facts['open_actions'])} open action(s) carried forward.")
    if facts["goals"]:
        lines.append(f"{len(facts['goals'])} active goal(s) on file.")

    return BriefOutput(
        tier=3,
        tier_label=TIER_LABELS[3],
        summary=" ".join(lines),
        facts=facts,
        provenance=[],
    )


# ── Tier 4 ─────────────────────────────────────────────────────────────────


def _tier4(context: dict) -> BriefOutput:
    """The floor. Always succeeds, by construction.

    Tier 4 does not attempt to summarise anything. It tells the clinician the
    machine cannot help with this handover and hands them a checklist. Being
    told to pick up the paper form is a worse experience than a summary and a
    much better one than a confident, empty brief.
    """
    high_priority = [
        a
        for a in _safe_list(context.get("actions"))
        if str(a.get("priority", "")).upper() == "HIGH"
    ]
    facts = {
        "client_id": context.get("client_id", "unknown"),
        "recipient_role": context.get("recipient_role", "unknown"),
        "generated_at": context.get("generated_at", ""),
        "high_priority_actions": [
            {
                "description": a.get("description", ""),
                "owner_role": a.get("owner_role", ""),
                "due_date": a.get("due_date", ""),
            }
            for a in high_priority
        ],
        "instruction": "Complete paper handover form before session.",
    }

    checklist = [
        "MANUAL HANDOVER REQUIRED.",
        f"Client {facts['client_id']} — recipient role {facts['recipient_role']}"
        + (f" — {facts['generated_at']}" if facts["generated_at"] else "")
        + ".",
    ]
    if high_priority:
        checklist.append(f"{len(high_priority)} open high-priority action(s):")
        checklist.extend(
            f"- {a['description']} (owner: {a['owner_role']}, due {a['due_date']})"
            for a in facts["high_priority_actions"]
        )
    else:
        checklist.append("No open high-priority actions recorded.")
    checklist.append("Complete paper handover form before session.")

    return BriefOutput(
        tier=4,
        tier_label=TIER_LABELS[4],
        summary="\n".join(checklist),
        facts=facts,
        provenance=[],
    )


# ── Ladder ─────────────────────────────────────────────────────────────────

_LADDER = {1: _tier1, 2: _tier2, 3: _tier3, 4: _tier4}


def generate_brief(
    permitted_context: dict,
    tier_override: int | None = None,
) -> BriefOutput:
    """Walk the ladder from the highest available tier down to the first that works.

    `tier_override` pins the *starting* rung, for tests and for the UI's
    "show me what tier 3 looks like" control. It does not disable the fallback
    below that rung — pinning to 1 with no model running still lands on 2.

    This function does not raise. Tier 4 cannot fail, so there is always a
    return value. If it somehow did, the bare except below would still produce
    a brief rather than a stack trace in front of a clinician.
    """
    start = tier_override if tier_override in _LADDER else (1 if llm_enabled() else 2)
    reasons: list[str] = []

    if tier_override is None and not llm_enabled():
        reasons.append("tier 1 skipped: local LLM disabled by configuration")

    for tier in range(start, 5):
        try:
            output = _LADDER[tier](permitted_context)
        except Exception as exc:  # noqa: BLE001 - the ladder must absorb everything
            reasons.append(f"tier {tier} unavailable: {exc}")
            continue
        output.degradation_reasons = reasons
        return output

    fallback = _tier4(permitted_context)
    fallback.degradation_reasons = [
        *reasons,
        "all tiers failed; emitted manual checklist",
    ]
    return fallback
