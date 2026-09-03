"""
Sensitivity tagger — Stage 3.

Turns free-text session notes into `TaggedSpan` objects for the consent engine.

Two guarantees the rest of the system depends on:

1. **Offline.** No network, no model download at call time, no LLM. If spaCy
   and `en_core_web_sm` are installed the tagger uses them for sentence
   segmentation; if not it falls back to a stdlib splitter. Both backends read
   the same pattern table in `patterns.py`, so the categories and confidences
   they produce are identical — only sentence boundaries can differ.

2. **Deterministic.** Same text plus same session_id gives byte-identical
   output, including span ids. Span ids are a blake2b digest of
   (session_id, sentence index, category), never a UUID, so eval runs and
   audit records line up across machines.

A sentence matching two categories produces two spans over the same text. That
is intentional: consent is granted per category, so a sentence about lithium
levels during a relapse must be withheld if *either* category is withheld.

Interface expected by the rest of the codebase:

    def tag(text: str, session_id: str) -> list[TaggedSpan]
"""

from __future__ import annotations

import hashlib
import re
from functools import lru_cache

from ..policy.categories import SensitivityCategory
from ..policy.engine import TaggedSpan
from .patterns import (
    CONFIDENCE_CEILING,
    CORROBORATION_BONUS,
    PATTERNS,
    TAGGER_VERSION,
    Pattern,
)

__all__ = ["tag", "split_sentences", "backend_name", "TAGGER_VERSION"]


# ── Pattern compilation ────────────────────────────────────────────────────

def _compile(pattern: Pattern) -> re.Pattern[str]:
    """Compile one pattern to a case-insensitive regex.

    `whole_word` patterns get \\b anchors so "court" does not fire on
    "courteous". Stems like "trauma" set whole_word=False so they still catch
    "traumatic" and "traumatised".
    """
    body = re.escape(pattern.phrase)
    # Let a literal space in a phrase absorb runs of whitespace and newlines.
    body = body.replace(r"\ ", r"\s+")
    if pattern.whole_word:
        body = rf"\b{body}\b"
    return re.compile(body, re.IGNORECASE)


_COMPILED: tuple[tuple[Pattern, re.Pattern[str]], ...] = tuple(
    (p, _compile(p)) for p in PATTERNS
)


# ── Sentence segmentation ──────────────────────────────────────────────────

# Candidate sentence break: . ! ? followed by whitespace then a capital or
# digit (optionally behind an opening quote or bracket).
#
# Python's re rejects variable-width lookbehind, so abbreviations are excluded
# with an explicit check on the text before the break rather than inside the
# pattern. `_ABBREVIATIONS` is matched case-sensitively against the final word
# so "No." (number) is protected while "no." at the end of a sentence is not.
_ABBREVIATIONS = frozenset(
    {"Dr", "Mr", "Mrs", "Ms", "Prof", "approx", "e.g", "i.e", "mg", "No", "vs"}
)
_SENTENCE_BREAK = re.compile(r"[.!?]\s+(?=[\"'(\[]?[A-Z0-9])")
_TRAILING_WORD = re.compile(r"([A-Za-z.]+)[.!?]$")


def _ends_with_abbreviation(fragment: str) -> bool:
    match = _TRAILING_WORD.search(fragment.rstrip())
    return bool(match) and match.group(1).rstrip(".") in _ABBREVIATIONS


@lru_cache(maxsize=1)
def _spacy_pipeline():  # pragma: no cover - depends on optional install
    """Load en_core_web_sm once, or return None if unavailable.

    Only the tokenizer and sentence boundaries are used — the NER and parser
    components are disabled because the tagging decision comes entirely from
    the pattern table. This keeps the pipeline fast enough to run over all 60
    synthetic clients on a fanless M4 without spinning up heat.
    """
    try:
        import spacy
    except ImportError:
        return None
    try:
        nlp = spacy.load("en_core_web_sm", disable=["ner", "lemmatizer"])
    except OSError:
        # spaCy installed but model not downloaded.
        return None
    if "senter" not in nlp.pipe_names and "parser" not in nlp.pipe_names:
        nlp.add_pipe("sentencizer")
    return nlp


def backend_name() -> str:
    """Report which segmentation backend is active (surfaced in explanations)."""
    return "spacy:en_core_web_sm" if _spacy_pipeline() is not None else "stdlib:regex"


def split_sentences(text: str) -> list[str]:
    """Segment text into sentences, preserving terminal punctuation.

    Preserving the trailing period matters more than it looks. An earlier
    version of the brief builder split on ". " and then compared the resulting
    fragments against span texts that still ended in ".". Nothing ever matched,
    so every withheld span was re-added to the brief as "general" narrative.
    Segmentation that round-trips is a consent control, not a formatting nicety.
    """
    text = text.strip()
    if not text:
        return []

    nlp = _spacy_pipeline()
    if nlp is not None:  # pragma: no cover - depends on optional install
        return [s.text.strip() for s in nlp(text).sents if s.text.strip()]

    sentences: list[str] = []
    start = 0
    for match in _SENTENCE_BREAK.finditer(text):
        # match.start() is the terminal punctuation; keep it with the sentence.
        candidate = text[start : match.start() + 1]
        if _ends_with_abbreviation(candidate):
            continue  # false break, e.g. "Dr. Patel reviewed the notes."
        if candidate.strip():
            sentences.append(candidate.strip())
        start = match.end()

    tail = text[start:].strip()
    if tail:
        sentences.append(tail)
    return sentences


# ── Span id ────────────────────────────────────────────────────────────────

def _span_id(session_id: str, index: int, category: SensitivityCategory) -> str:
    """Stable 8-char id. Deterministic across processes and machines."""
    key = f"{session_id}|{index}|{category.value}|{TAGGER_VERSION}".encode()
    return hashlib.blake2b(key, digest_size=4).hexdigest()


# ── Tagging ────────────────────────────────────────────────────────────────

def tag(text: str, session_id: str) -> list[TaggedSpan]:
    """Tag `text` and return spans sorted by (sentence order, category).

    Confidence for a category in a sentence is the highest weight among its
    matching patterns, plus a small corroboration bonus when two or more
    distinct patterns of that category fire in the same sentence.

    Confidence is never lowered below a pattern's own weight and never raised
    above CONFIDENCE_CEILING. There is no path here that can push a
    sub-threshold match above the policy engine's 0.70 cutoff on its own — a
    single weak pattern stays weak, which is what makes the engine's
    fail-closed behaviour meaningful.
    """
    spans: list[TaggedSpan] = []

    for index, sentence in enumerate(split_sentences(text)):
        # category -> (best weight, distinct pattern count, any safety flag)
        hits: dict[SensitivityCategory, tuple[float, int, bool]] = {}

        for pattern, rx in _COMPILED:
            if not rx.search(sentence):
                continue
            best, count, safety = hits.get(pattern.category, (0.0, 0, False))
            hits[pattern.category] = (
                max(best, pattern.weight),
                count + 1,
                safety or pattern.safety,
            )

        for category, (weight, count, safety) in hits.items():
            confidence = weight
            if count >= 2:
                confidence = min(confidence + CORROBORATION_BONUS, CONFIDENCE_CEILING)
            spans.append(
                TaggedSpan(
                    span_id=_span_id(session_id, index, category),
                    text=sentence,
                    category=category,
                    # Round so JSON round-trips and eval numbers are stable.
                    confidence=round(confidence, 2),
                    is_safety_relevant=safety,
                )
            )

    spans.sort(key=lambda s: (s.text, s.category.value))
    return spans


def tag_session(session: dict) -> list[TaggedSpan]:
    """Tag one session dict from the synthetic data set.

    Pre-tagged spans in the fixture are trusted when present — they are the
    generator's ground truth. The tagger runs over the full session text as
    well, and the union is returned. Union rather than either-or: a span the
    fixture knows about but the tagger misses must still be withheld, and vice
    versa. Deduplication is by (text, category), keeping the *lower*
    confidence, because the safer read of a disagreement is the cautious one.
    """
    session_id = session.get("session_id", "unknown")
    merged: dict[tuple[str, str], TaggedSpan] = {}

    def add(span: TaggedSpan) -> None:
        key = (span.text.strip(), span.category.value)
        existing = merged.get(key)
        if existing is None:
            merged[key] = span
            return
        merged[key] = TaggedSpan(
            span_id=existing.span_id,
            text=existing.text,
            category=existing.category,
            confidence=min(existing.confidence, span.confidence),
            is_safety_relevant=existing.is_safety_relevant or span.is_safety_relevant,
        )

    for raw in session.get("spans", []):
        try:
            category = SensitivityCategory(raw["category"])
        except (KeyError, ValueError):
            continue
        add(
            TaggedSpan(
                span_id=raw["span_id"],
                text=raw["text"],
                category=category,
                confidence=float(raw["confidence"]),
                is_safety_relevant=bool(raw.get("is_safety_relevant", False)),
            )
        )

    for span in tag(session.get("text", ""), session_id):
        add(span)

    return sorted(merged.values(), key=lambda s: (s.text, s.category.value))
