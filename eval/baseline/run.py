"""
Baseline: last-3-sessions verbatim concatenation + regex keyword redaction.
This is what a rushed ward does today. It fails in well-documented ways.
Run: uv run python -m eval.baseline.run
"""

from __future__ import annotations

import json
import re
from pathlib import Path

REDACT_PATTERNS = [
    r"\b(heroin|cocaine|crack|meth|amphetamine|MDMA|ecstasy)\b",
    r"\b(suicide|suicidal|self.harm|overdose)\b",
    r"\b(convicted|criminal|prison|probation|offence)\b",
    r"\b(HIV|STI|gonorrhoea|chlamydia|syphilis)\b",
]
COMBINED = re.compile("|".join(REDACT_PATTERNS), re.IGNORECASE)


def redact(text: str) -> str:
    return COMBINED.sub("[REDACTED]", text)


def baseline_brief(client: dict) -> dict:
    sessions = sorted(client["sessions"], key=lambda s: s["date"])
    last_3 = sessions[-3:]
    raw = " | ".join(s["text"] for s in last_3)
    brief_text = redact(raw)
    return {
        "client_id": client["client_id"],
        "method": "baseline_regex_redact",
        "brief": brief_text,
        "word_count": len(brief_text.split()),
        "actions_included": [],  # baseline carries no action tracking
        "withheld_flags": [],  # baseline never flags withheld topics
        "escalation_flags": [],
    }


def main() -> None:
    data_path = Path("data/synthetic/clients.json")
    if not data_path.exists():
        print("❌ Run `make data` first.")
        return

    with open(data_path) as f:
        payload = json.load(f)

    results = [baseline_brief(c) for c in payload["clients"]]

    out_path = Path("eval/baseline/results.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)

    print(f"✅ Baseline results → {out_path}  ({len(results)} briefs)")


if __name__ == "__main__":
    main()
