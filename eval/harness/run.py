"""
Evaluation harness — Stage 8.

Runs the prototype over all 60 synthetic clients, scores it and the baseline on
seven metrics, and writes `eval/report/metrics.json`.

Both arms are scored by the same functions on the same clients at the same
fixed evaluation date, so the only variable is the method under test.

Ground truth
------------
`data/synthetic/clients.json` ships a `gold` block per client, and it is
treated as read-only here. One caveat is worth stating plainly rather than
hiding inside a number: `gold.permitted_categories` is computed by the
generator across *all* roles, but consent in this system is granted per
(category, role, purpose). A category consented for the psychiatrist is
correctly withheld from the counsellor, and scoring that as a miss against a
role-blind gold would punish the system for behaving properly.

So the harness derives role-specific ground truth from the consent records
themselves — the same records the engine reads, applied by the same rules — and
uses the shipped gold for `high_priority_actions` and `has_safety_risk`, which
are role-independent and unambiguous. The derivation is deterministic and
involves no model.

Evaluation is fixed at EVAL_DATE rather than "now" so overdue-action
escalations do not drift as the report ages.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.pipeline import build_brief, build_consent_records, collect_spans  # noqa: E402
from src.policy.categories import ConsentPurpose, RecipientRole  # noqa: E402

EVAL_DATE = datetime(2025, 3, 1)
EVAL_ROLE = RecipientRole.COUNSELLOR
EVAL_PURPOSE = ConsentPurpose.HANDOVER

# ── Leakage detection ──────────────────────────────────────────────────────

_STOPWORDS = frozenset(
    """
    a an and are as at be been by client clients discussed during for from had
    has have in into is it its no not of on or over reported reports session
    sessions that the their they this to was were with
    """.split()
)
_WORD = re.compile(r"[a-z][a-z'-]+")

# A withheld span counts as leaked when this fraction of its distinctive
# content words appears in the brief.
LEAK_OVERLAP_THRESHOLD = 0.60
# Spans with fewer content words than this are too short to score reliably.
MIN_CONTENT_WORDS = 4


def _content_words(text: str) -> set[str]:
    return {w for w in _WORD.findall(text.lower()) if w not in _STOPWORDS}


def _leaks(span_text: str, brief_text: str) -> bool:
    """Does a withheld span's substance appear in the brief?

    Exact string matching is not sufficient. The baseline redacts individual
    keywords in place — "passive [REDACTED] ideation" — so the sentence is no
    longer identical to the source but its clinical content survives intact and
    is trivially re-identifiable by a reader. Scoring only exact matches would
    hand the baseline a perfect leakage score for a technique that plainly
    leaks, and make the whole comparison meaningless.

    Content-word overlap catches partial redaction while ignoring the shared
    scaffolding of clinical prose ("client", "session", "reported"), which is
    what the stoplist is for. Very short spans are skipped rather than guessed
    at, since a three-word overlap is as likely to be coincidence as disclosure.
    """
    span_words = _content_words(span_text)
    if len(span_words) < MIN_CONTENT_WORDS:
        return False
    brief_words = _content_words(brief_text)
    return len(span_words & brief_words) / len(span_words) >= LEAK_OVERLAP_THRESHOLD


# ── Role-specific ground truth ─────────────────────────────────────────────


def role_ground_truth(client: dict) -> dict:
    """Derive what *should* be disclosable to EVAL_ROLE, from consent records."""
    records = build_consent_records(client)
    permitted = {
        r.category.value
        for r in records
        if r.recipient_role == EVAL_ROLE
        and r.purpose == EVAL_PURPOSE
        and r.is_active(EVAL_DATE)
    }
    spans, _ = collect_spans(client)
    present = {s.category.value for s in spans}
    return {
        "permitted_categories": sorted(permitted & present),
        "withheld_categories": sorted(present - permitted),
        "withheld_spans": [
            {
                "text": s.text,
                "category": s.category.value,
                "safety": s.is_safety_relevant,
            }
            for s in spans
            if s.category.value not in permitted
        ],
        "has_safety_risk": any(s.is_safety_relevant for s in spans),
    }


# ── Metrics ────────────────────────────────────────────────────────────────


def consent_leakage_rate(results: list[dict], truths: list[dict]) -> float:
    """Fraction of briefs containing content from a non-permitted category.

    Counted per brief, not per span: one leak ruins one handover. The target is
    0.0 and nothing above it is acceptable, because the failure is unbounded —
    a disclosed forensic history cannot be un-disclosed.
    """
    if not results:
        return 0.0
    leaked = 0
    for res, truth in zip(results, truths):
        brief = res.get("brief", "")
        if any(_leaks(s["text"], brief) for s in truth["withheld_spans"]):
            leaked += 1
    return leaked / len(results)


def action_retention_rate(results: list[dict], clients: list[dict]) -> float:
    """Fraction of open high-priority actions carried forward with owner and due date.

    An action listed without an owner is not counted as retained. The point of
    carrying it forward is that somebody knows it is theirs.
    """
    retained = total = 0
    for res, client in zip(results, clients):
        expected = [
            a
            for a in client["actions"]
            if a["priority"] == "HIGH" and a["status"] not in ("completed", "cancelled")
        ]
        total += len(expected)
        by_id = {a["action_id"]: a for a in res.get("actions", [])}
        for action in expected:
            carried = by_id.get(action["action_id"])
            if carried and carried.get("owner_role") and carried.get("due_date"):
                retained += 1
    return retained / total if total else 1.0


def withheld_flag_recall(results: list[dict], truths: list[dict]) -> float:
    """Fraction of withheld categories the brief openly signals as withheld.

    This is the metric that separates a filtered brief from a censored one. A
    brief that quietly omits a topic reads as complete, and the receiving
    clinician never learns to ask. Flagging costs nothing and converts a hidden
    gap into a visible one.
    """
    flagged = total = 0
    for res, truth in zip(results, truths):
        flags = " ".join(str(f) for f in res.get("withheld_flags", []))
        for category in truth["withheld_categories"]:
            total += 1
            if category in flags:
                flagged += 1
    return flagged / total if total else 1.0


def word_reduction(results: list[dict], baseline: list[dict]) -> float:
    """Prototype word count as a fraction of baseline word count.

    A proxy for reading time under pressure, not a goal in itself. It is
    reported next to action_retention_rate on purpose: shortening the brief by
    dropping actions would show up there as a regression.
    """
    if not results or not baseline:
        return 1.0
    avg_proto = sum(r.get("word_count", 0) for r in results) / len(results)
    avg_base = sum(r.get("word_count", 0) for r in baseline) / len(baseline)
    return avg_proto / avg_base if avg_base else 1.0


def safety_escalation_recall(results: list[dict], truths: list[dict]) -> float:
    """Of clients with withheld safety-relevant content, how many briefs raise a flag.

    The safety carve-out is the system's sharpest ethical edge: risk-of-harm
    content is still withheld when consent says so, but its *existence* is
    always escalated. Silence here is the one failure mode that could put
    somebody in front of an unprepared clinician.
    """
    flagged = total = 0
    for res, truth in zip(results, truths):
        if not any(s["safety"] for s in truth["withheld_spans"]):
            continue
        total += 1
        if res.get("escalation_flags"):
            flagged += 1
    return flagged / total if total else 1.0


def provenance_coverage(results: list[dict]) -> float:
    """Fraction of briefs whose disclosed content is traceable to source span ids.

    Tier 3 and 4 briefs disclose no session narrative, so they satisfy this
    trivially and are counted as covered. The metric asks whether a clinician
    can point at a sentence and get an answer to "where did this come from".
    """
    if not results:
        return 1.0
    covered = 0
    for res in results:
        if res.get("tier", 2) >= 3 or res.get("permitted_span_count", 0) == 0:
            covered += 1
        elif res.get("provenance"):
            covered += 1
    return covered / len(results)


def fallback_availability(results: list[dict], expected: int) -> float:
    """Fraction of clients receiving a usable, non-empty brief.

    The ladder's promise is that the system is never blank and never raises to
    the user. This measures that promise directly: a brief that is missing,
    empty or whitespace is a failure regardless of how good the other six
    numbers look.

    Reads `summary` or `brief` so both arms are scored on the same question.
    The baseline should and does score 1.0 here — it is always available, just
    never filtered. Marking it down on a key-name mismatch would flatter the
    prototype on the one axis where the baseline is genuinely competitive, and
    a comparison that only shows favourable numbers is not worth running.
    """
    if not expected:
        return 1.0
    usable = sum(
        1 for r in results if (r.get("summary") or r.get("brief") or "").strip()
    )
    return usable / expected


# ── Runner ─────────────────────────────────────────────────────────────────


@dataclass
class MetricResult:
    metric: str
    definition: str
    target: str
    baseline: float
    prototype: float
    delta: float
    passed: bool
    error_analysis: str


def run_prototype(clients: list[dict]) -> list[dict]:
    """Build a brief for every client. Failures are recorded, never raised.

    If the pipeline itself throws, that client still gets a result row with an
    empty summary so fallback_availability registers the loss. Crashing the
    harness would hide the failure behind a stack trace.
    """
    results = []
    for client in clients:
        try:
            results.append(build_brief(client, EVAL_ROLE, EVAL_PURPOSE, now=EVAL_DATE))
        except Exception as exc:  # noqa: BLE001
            results.append(
                {
                    "client_id": client.get("client_id", "?"),
                    "brief": "",
                    "summary": "",
                    "word_count": 0,
                    "actions": [],
                    "withheld_flags": [],
                    "escalation_flags": [],
                    "error": repr(exc),
                }
            )
    return results


THRESHOLDS = {
    "consent_leakage_rate": lambda v: v == 0.0,
    "action_retention_rate": lambda v: v >= 1.0,
    "withheld_flag_recall": lambda v: v >= 0.95,
    "word_reduction": lambda v: v <= 0.40,
    "safety_escalation_recall": lambda v: v >= 1.0,
    "provenance_coverage": lambda v: v >= 1.0,
    "fallback_availability": lambda v: v >= 1.0,
}


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    data_path = root / "data/synthetic/clients.json"
    baseline_path = root / "eval/baseline/results.json"

    if not data_path.exists():
        print("❌ Run `make data` first.")
        return 1
    if not baseline_path.exists():
        print("❌ Run `make baseline` first.")
        return 1

    clients = json.loads(data_path.read_text())["clients"]
    baseline = json.loads(baseline_path.read_text())

    truths = [role_ground_truth(c) for c in clients]
    proto = run_prototype(clients)

    proto_path = root / "eval/harness/prototype_results.json"
    proto_path.write_text(json.dumps(proto, indent=2))

    metrics = [
        MetricResult(
            "consent_leakage_rate",
            "Fraction of briefs containing content from a non-permitted category",
            "0.0",
            round(consent_leakage_rate(baseline, truths), 4),
            round(consent_leakage_rate(proto, truths), 4),
            0.0,
            False,
            "Keyword redaction removes the word but leaves the sentence, so the "
            "disclosure survives and is trivially re-identifiable. Category-level "
            "filtering removes the whole span before generation.",
        ),
        MetricResult(
            "action_retention_rate",
            "Open high-priority actions carried forward with owner and due date",
            "1.0",
            round(action_retention_rate(baseline, clients), 4),
            round(action_retention_rate(proto, clients), 4),
            0.0,
            False,
            "Baseline copies prose and has no action model at all. Actions travel "
            "on a separate track that consent filtering never touches.",
        ),
        MetricResult(
            "withheld_flag_recall",
            "Withheld topics openly signalled rather than silently dropped",
            ">=0.95",
            round(withheld_flag_recall(baseline, truths), 4),
            round(withheld_flag_recall(proto, truths), 4),
            0.0,
            False,
            "Baseline cannot flag what it does not model. Every withheld category "
            "is named in the notice so the clinician knows a gap exists.",
        ),
        MetricResult(
            "word_reduction",
            "Prototype word count as a fraction of baseline word count",
            "<=0.40",
            1.0,
            round(word_reduction(proto, baseline), 4),
            0.0,
            False,
            "Baseline concatenates three full sessions verbatim. Tier 2 keeps only "
            "permitted sentences and de-duplicates repeats across sessions.",
        ),
        MetricResult(
            "safety_escalation_recall",
            "Clients with withheld safety content whose brief raises an escalation flag",
            "1.0",
            round(safety_escalation_recall(baseline, truths), 4),
            round(safety_escalation_recall(proto, truths), 4),
            0.0,
            False,
            "Baseline redacts risk wording and signals nothing, so withheld risk "
            "becomes invisible. The carve-out flags existence without disclosing content.",
        ),
        MetricResult(
            "provenance_coverage",
            "Briefs whose disclosed content is traceable to source span ids",
            "1.0",
            0.0,
            round(provenance_coverage(proto), 4),
            0.0,
            False,
            "Baseline output is an undifferentiated blob with no span links. Every "
            "prototype sentence carries the span id it came from.",
        ),
        MetricResult(
            "fallback_availability",
            "Clients receiving a usable non-empty brief without an unhandled error",
            "1.0",
            round(fallback_availability(baseline, len(clients)), 4),
            round(fallback_availability(proto, len(clients)), 4),
            0.0,
            False,
            "Baseline is always available but always unfiltered. The ladder keeps "
            "availability without giving up the consent guarantee.",
        ),
    ]

    for m in metrics:
        m.delta = round(m.prototype - m.baseline, 4)
        m.passed = THRESHOLDS[m.metric](m.prototype)

    tier_counts: dict[str, int] = {}
    for r in proto:
        key = str(r.get("tier", "error"))
        tier_counts[key] = tier_counts.get(key, 0) + 1

    payload = {
        "eval_date": EVAL_DATE.isoformat(),
        "role": EVAL_ROLE.value,
        "purpose": EVAL_PURPOSE.value,
        "n_clients": len(clients),
        "tier_distribution": tier_counts,
        "metrics": [asdict(m) for m in metrics],
        "all_passed": all(m.passed for m in metrics),
    }

    out_path = root / "eval/report/metrics.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2))

    print(
        f"\n── Evaluation ({len(clients)} clients, role={EVAL_ROLE.value}) ──────────"
    )
    for m in metrics:
        mark = "PASS" if m.passed else "FAIL"
        print(
            f"  [{mark}] {m.metric:<26} baseline={m.baseline:<8.3f}"
            f"prototype={m.prototype:<8.3f}target={m.target}"
        )
    print(f"\n  tier distribution: {tier_counts}")
    print(f"✅ Metrics → {out_path}")
    return 0 if payload["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
