"""
Sensitivity pattern table.

Single source of truth for both tagger backends (spaCy EntityRuler and the
stdlib regex matcher). Keeping one table means the two backends cannot drift
apart and produce different consent decisions on the same text.

Confidence semantics
--------------------
`weight` is the confidence a *single* match of this pattern earns. It encodes
how specific the phrase is to the category, not how bad the content is:

    0.90-0.97   unambiguous clinical marker ("clozapine", "self-harm urges")
    0.78-0.89   strong but context-dependent ("relapse", "court appearance")
    0.60-0.77   suggestive only ("family", "money")

The policy engine's CONFIDENCE_THRESHOLD is 0.70, so anything in the bottom
band is denied by default. That is deliberate: a weak signal must fail closed,
never open. Do not raise a weight to "fix" a span being withheld.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..policy.categories import SensitivityCategory


@dataclass(frozen=True)
class Pattern:
    """One lexical rule mapping a phrase to a sensitivity category."""

    phrase: str
    category: SensitivityCategory
    weight: float
    safety: bool = False
    # If True the phrase is matched as a whole word sequence only.
    # If False it may match inside a longer word (used for stems like "alcohol").
    whole_word: bool = True


C = SensitivityCategory

PATTERNS: tuple[Pattern, ...] = (
    # ── Substance use ──────────────────────────────────────────────────────
    Pattern("alcohol", C.SUBSTANCE_USE, 0.93),
    Pattern("units daily", C.SUBSTANCE_USE, 0.88),
    Pattern("cannabis", C.SUBSTANCE_USE, 0.95),
    Pattern("heroin", C.SUBSTANCE_USE, 0.97),
    Pattern("cocaine", C.SUBSTANCE_USE, 0.97),
    Pattern("methadone", C.SUBSTANCE_USE, 0.95),
    Pattern("substance use", C.SUBSTANCE_USE, 0.96),
    Pattern("drug use", C.SUBSTANCE_USE, 0.94),
    Pattern("sober", C.SUBSTANCE_USE, 0.90),
    Pattern("sobriety", C.SUBSTANCE_USE, 0.90),
    Pattern("relapse", C.SUBSTANCE_USE, 0.86),
    Pattern("harm reduction", C.SUBSTANCE_USE, 0.91),
    Pattern("detox", C.SUBSTANCE_USE, 0.92),
    Pattern("AA meeting", C.SUBSTANCE_USE, 0.89),
    # Overdose is substance-adjacent AND safety-relevant.
    Pattern("overdose", C.SUBSTANCE_USE, 0.96, safety=True),
    Pattern("drinking", C.SUBSTANCE_USE, 0.74),

    # ── Trauma history ─────────────────────────────────────────────────────
    Pattern("childhood abuse", C.TRAUMA_HISTORY, 0.97),
    Pattern("abuse", C.TRAUMA_HISTORY, 0.88),
    Pattern("trauma", C.TRAUMA_HISTORY, 0.94, whole_word=False),
    Pattern("PTSD", C.TRAUMA_HISTORY, 0.96),
    Pattern("flashback", C.TRAUMA_HISTORY, 0.92, whole_word=False),
    Pattern("early life", C.TRAUMA_HISTORY, 0.79),
    Pattern("past experiences", C.TRAUMA_HISTORY, 0.72),
    Pattern("difficulty trusting", C.TRAUMA_HISTORY, 0.78),
    Pattern("distress when discussing", C.TRAUMA_HISTORY, 0.80),

    # ── Forensic / legal ───────────────────────────────────────────────────
    Pattern("court appearance", C.FORENSIC_LEGAL, 0.95),
    Pattern("court", C.FORENSIC_LEGAL, 0.84),
    Pattern("probation", C.FORENSIC_LEGAL, 0.95, whole_word=False),
    Pattern("criminal conviction", C.FORENSIC_LEGAL, 0.97),
    Pattern("conviction", C.FORENSIC_LEGAL, 0.92),
    Pattern("convicted", C.FORENSIC_LEGAL, 0.93),
    Pattern("offence", C.FORENSIC_LEGAL, 0.88),
    Pattern("prison", C.FORENSIC_LEGAL, 0.93),
    Pattern("custody", C.FORENSIC_LEGAL, 0.80),
    Pattern("solicitor", C.FORENSIC_LEGAL, 0.86),

    # ── Sexual health ──────────────────────────────────────────────────────
    Pattern("sexual health", C.SEXUAL_HEALTH, 0.96),
    Pattern("GUM clinic", C.SEXUAL_HEALTH, 0.95),
    Pattern("STI", C.SEXUAL_HEALTH, 0.94),
    Pattern("HIV", C.SEXUAL_HEALTH, 0.96),
    Pattern("chlamydia", C.SEXUAL_HEALTH, 0.97),
    Pattern("gonorrhoea", C.SEXUAL_HEALTH, 0.97),
    Pattern("syphilis", C.SEXUAL_HEALTH, 0.97),
    Pattern("screening discussed", C.SEXUAL_HEALTH, 0.76),
    Pattern("contraception", C.SEXUAL_HEALTH, 0.93),

    # ── Family conflict ────────────────────────────────────────────────────
    Pattern("family visit", C.FAMILY_CONFLICT, 0.89),
    Pattern("estranged", C.FAMILY_CONFLICT, 0.94),
    Pattern("sibling", C.FAMILY_CONFLICT, 0.79),
    Pattern("emergency contacts", C.FAMILY_CONFLICT, 0.75),
    Pattern("primary family", C.FAMILY_CONFLICT, 0.84),
    Pattern("boundaries discussed", C.FAMILY_CONFLICT, 0.78),
    Pattern("family", C.FAMILY_CONFLICT, 0.66),  # below threshold on its own

    # ── Medication ─────────────────────────────────────────────────────────
    Pattern("clozapine", C.MEDICATION, 0.97),
    Pattern("risperidone", C.MEDICATION, 0.97),
    Pattern("lithium", C.MEDICATION, 0.97),
    Pattern("olanzapine", C.MEDICATION, 0.97),
    Pattern("quetiapine", C.MEDICATION, 0.97),
    Pattern("sertraline", C.MEDICATION, 0.97),
    Pattern("depot", C.MEDICATION, 0.90),
    Pattern("nocte", C.MEDICATION, 0.91),
    Pattern("mmol/L", C.MEDICATION, 0.88),
    Pattern("dose reviewed", C.MEDICATION, 0.92),
    Pattern("non-adherent", C.MEDICATION, 0.89),
    Pattern("medication compliance", C.MEDICATION, 0.93),
    Pattern("therapeutic range", C.MEDICATION, 0.90),
    Pattern("side effects", C.MEDICATION, 0.83),

    # ── Financial ──────────────────────────────────────────────────────────
    Pattern("rent arrears", C.FINANCIAL, 0.96),
    Pattern("arrears", C.FINANCIAL, 0.94),
    Pattern("benefits claim", C.FINANCIAL, 0.93),
    Pattern("Universal Credit", C.FINANCIAL, 0.96),
    Pattern("benefits application", C.FINANCIAL, 0.92),
    Pattern("debt", C.FINANCIAL, 0.91),
    Pattern("financial", C.FINANCIAL, 0.85, whole_word=False),
    Pattern("money", C.FINANCIAL, 0.68),  # below threshold on its own

    # ── Safety risk (always safety-relevant) ───────────────────────────────
    Pattern("suicidal ideation", C.SAFETY_RISK, 0.98, safety=True),
    Pattern("suicidal", C.SAFETY_RISK, 0.96, safety=True),
    Pattern("suicide", C.SAFETY_RISK, 0.96, safety=True),
    Pattern("self-harm", C.SAFETY_RISK, 0.97, safety=True),
    Pattern("self harm", C.SAFETY_RISK, 0.97, safety=True),
    Pattern("risk assessment", C.SAFETY_RISK, 0.90, safety=True),
    Pattern("safety plan", C.SAFETY_RISK, 0.91, safety=True),
    Pattern("protective factors", C.SAFETY_RISK, 0.86, safety=True),
    Pattern("harm to others", C.SAFETY_RISK, 0.95, safety=True),
    Pattern("absconding", C.SAFETY_RISK, 0.93, safety=True),
    Pattern("no current risk", C.SAFETY_RISK, 0.88, safety=True),
)

# Matching two or more distinct patterns in one sentence is corroborating
# evidence, so confidence gets this bump (capped at CONFIDENCE_CEILING).
CORROBORATION_BONUS = 0.03
CONFIDENCE_CEILING = 0.99

TAGGER_VERSION = "1.0"
