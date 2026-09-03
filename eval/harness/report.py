"""
Report generator.

Reads `eval/report/metrics.json` and renders `eval/report/report.md`: the
before/after table, per-metric error analysis, tier distribution, and a worked
example brief.

Kept separate from `run.py` so the report can be re-rendered without re-running
the evaluation, and so a formatting change can never alter a number.

Run: uv run python -m eval.harness.report
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
METRICS_PATH = ROOT / "eval/report/metrics.json"
PROTO_PATH = ROOT / "eval/harness/prototype_results.json"
BASELINE_PATH = ROOT / "eval/baseline/results.json"
OUT_PATH = ROOT / "eval/report/report.md"

TIER_NAMES = {
    "1": "tier 1 — AI-generated",
    "2": "tier 2 — extractive",
    "3": "tier 3 — facts card",
    "4": "tier 4 — manual checklist",
    "error": "pipeline error",
}


def _direction(metric: str) -> str:
    """Which way is better for this metric."""
    return "lower" if metric in {"consent_leakage_rate", "word_reduction"} else "higher"


def _example_section(proto: list[dict], baseline: list[dict]) -> str:
    """Show the same client through both methods.

    Picks a client with both withheld content and an escalation flag, because
    that is where the two approaches actually diverge. A client with full
    consent looks similar either way and would make the comparison look like a
    formatting exercise.
    """
    chosen = next(
        (r for r in proto if r.get("withheld_count") and r.get("escalation_flags")),
        proto[0] if proto else None,
    )
    if chosen is None:
        return ""

    base = next(
        (b for b in baseline if b.get("client_id") == chosen.get("client_id")), None
    )

    lines = [
        "## Worked example",
        "",
        f"Client `{chosen['client_id']}`, recipient role "
        f"`{chosen.get('recipient_role', 'counsellor')}`.",
        "",
        "### Baseline",
        "",
        "```",
        (base or {}).get("brief", "(not available)")[:700],
        "```",
        "",
        "### Prototype",
        "",
        f"**{chosen.get('tier_label', '')}**",
        "",
        "```",
        chosen.get("summary", "")[:700],
        "```",
        "",
    ]

    if chosen.get("withheld_notice"):
        lines += ["**Withheld notice**", "", f"> {chosen['withheld_notice']}", ""]
    if chosen.get("escalation_flags"):
        lines += ["**Escalation flags**", ""]
        lines += [f"> {flag}" for flag in chosen["escalation_flags"]]
        lines += [""]
    if chosen.get("uncertainty_note"):
        lines += ["**Uncertainty**", "", f"> {chosen['uncertainty_note']}", ""]

    why_withheld = chosen.get("explanation", {}).get("why_withheld", [])
    if why_withheld:
        lines += [
            "**Why each topic was withheld**",
            "",
            "| Category | Reason | Explanation shown to the clinician |",
            "|---|---|---|",
        ]
        lines += [
            f"| `{w['category']}` | `{w['reason_code']}` | {w['detail']} |"
            for w in why_withheld
        ]
        lines += [""]

    return "\n".join(lines)


def main() -> int:
    if not METRICS_PATH.exists():
        print("❌ Run `python -m eval.harness.run` first.")
        return 1

    payload = json.loads(METRICS_PATH.read_text())
    metrics = payload["metrics"]
    proto = json.loads(PROTO_PATH.read_text()) if PROTO_PATH.exists() else []
    baseline = json.loads(BASELINE_PATH.read_text()) if BASELINE_PATH.exists() else []

    passed = sum(1 for m in metrics if m["passed"])

    lines = [
        "# Evaluation report",
        "",
        "Consent-aware continuity summary for psychiatric discharge handovers.",
        "",
        f"- Clients evaluated: **{payload['n_clients']}** (synthetic, seed 42)",
        f"- Recipient role: **{payload['role']}**, purpose **{payload['purpose']}**",
        f"- Evaluation date (fixed): **{payload['eval_date'][:10]}**",
        f"- Metrics passing target: **{passed}/{len(metrics)}**",
        f"- Report generated: {datetime.now(timezone.utc).isoformat(timespec='seconds')}Z",
        "",
        "Baseline is last-three-sessions verbatim concatenation with regex keyword",
        "redaction — what a ward under time pressure actually does today.",
        "",
        "## Results",
        "",
        "| Metric | Target | Baseline | Prototype | Delta | Better | Status |",
        "|---|---|---|---|---|---|---|",
    ]

    for m in metrics:
        status = "PASS" if m["passed"] else "**FAIL**"
        lines.append(
            f"| `{m['metric']}` | {m['target']} | {m['baseline']:.3f} | "
            f"{m['prototype']:.3f} | {m['delta']:+.3f} | {_direction(m['metric'])} | {status} |"
        )

    lines += ["", "## Metric definitions and error analysis", ""]
    for m in metrics:
        lines += [
            f"### `{m['metric']}`",
            "",
            f"{m['definition']}. Target {m['target']}.",
            "",
            f"Baseline {m['baseline']:.3f} → prototype {m['prototype']:.3f} "
            f"({m['delta']:+.3f}).",
            "",
            m["error_analysis"],
            "",
        ]

    lines += ["## Fallback tier distribution", "", "| Tier | Briefs |", "|---|---|"]
    for tier, count in sorted(payload["tier_distribution"].items()):
        lines.append(f"| {TIER_NAMES.get(tier, tier)} | {count} |")
    lines += [
        "",
        "Tier 1 is disabled by default (`PSYCH_HANDOVER_OLLAMA=0`), so a clean run",
        "sits at tier 2. That is the intended demo posture: the reported numbers",
        "come from the deterministic extractive path and do not depend on a local",
        "model being installed, warm, or reproducible across machines.",
        "",
    ]

    example = _example_section(proto, baseline)
    if example:
        lines += [example]

    lines += [
        "## Limitations",
        "",
        "Read the numbers above with these in mind.",
        "",
        "- **Synthetic data.** All 60 clients come from a template generator with a",
        "  fixed seed. Real clinical notes are messier, less grammatical, and full of",
        "  abbreviations and negation the tagger has never seen. A leakage rate of 0.0",
        "  here means the pipeline is correct on this distribution — it is not a",
        "  claim about real notes.",
        "- **The tagger bounds everything.** Consent filtering is exact, but it can",
        "  only act on spans that were tagged. An untagged sensitive sentence is",
        "  invisible to the engine and flows through as unclassified text. The",
        "  end-to-end guarantee is therefore no stronger than tagger recall, which",
        "  this harness does not measure against human annotation.",
        "- **Leakage detection is lexical.** Content-word overlap catches verbatim and",
        "  partially-redacted disclosure. It would not catch a genuine paraphrase that",
        "  reuses none of the source vocabulary.",
        "- **One role scored.** Metrics are computed for the counsellor. Other roles",
        "  see different consent sets; spot-checking suggests the same behaviour, but",
        "  it is not scored here.",
        "- **Tier 1 largely unevaluated.** With the local model off, these numbers say",
        "  almost nothing about the quality or grounding of AI-generated summaries.",
        "",
    ]

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text("\n".join(lines))
    print(f"✅ Report → {OUT_PATH}  ({passed}/{len(metrics)} metrics at target)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
