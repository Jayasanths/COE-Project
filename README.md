# Psychiatric Discharge Handover System
### CoE Project — Consent-aware continuity summary

> Clients repeat sensitive histories because handovers are incomplete.
> This system fixes that — without leaking consent-protected content.

---

## Quick start (M4 Air + Antigravity)

```bash
# 1. Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Install all deps (arm64 native wheels)
make setup

# 3. Generate 60 synthetic clients (seed=42, deterministic)
make data

# 4. Run baseline
make baseline

# 5. Run all tests (must be 100% green before any demo)
make test

# 6. Start API + UI
make dev-api      # terminal 1 → http://localhost:8000
make dev-ui       # terminal 2 → http://localhost:5173
```

## Full reproducible pipeline

```bash
make reproduce    # data → baseline → eval → report.md
```

## Project structure

```
psych_handover/
├── AGENTS.md                  ← Antigravity agent rules (read this first)
├── ANTIGRAVITY_PROMPT.md      ← Full build prompt for Antigravity IDE
├── Makefile
├── pyproject.toml             ← Python 3.12, pinned deps
├── docker-compose.yml
├── src/
│   ├── policy/
│   │   ├── categories.py      ← Sensitivity categories (HAND-WRITTEN)
│   │   └── engine.py          ← Consent engine (HAND-WRITTEN, never agent-modified)
│   ├── tagger/
│   │   ├── patterns.py        ← Pattern table shared by both backends
│   │   └── tagger.py          ← Deterministic tagger (spaCy or stdlib)
│   ├── generator/
│   │   ├── llm.py             ← Ollama client (tier 1, opt-in)
│   │   ├── generator.py       ← 4-tier fallback ladder + grounding check
│   │   ├── conflicts.py       ← Contradiction detector
│   │   └── explainer.py       ← Why shown / why withheld / uncertainty
│   ├── actions/tracker.py     ← Escalation state machine
│   ├── pipeline.py            ← Brief assembly (API + eval share this)
│   ├── routers/               ← FastAPI endpoints
│   └── main.py
├── data/synthetic/            ← Synthetic clients (60, seed=42)
├── eval/
│   ├── baseline/              ← Regex-redact baseline
│   ├── harness/               ← 7-metric evaluation harness + report generator
│   ├── gold/                  ← Ground-truth annotations
│   └── report/                ← Generated before/after report
├── tests/
│   ├── test_policy.py         ← Property tests (Hypothesis, 200 examples)
│   └── test_failure_cases.py  ← End-to-end tests for the 6 failure cases
├── ui/                        ← React + Vite + Tailwind v3 frontend
└── docs/                      ← architecture, schema, risk register, user guide
```

## Key design decisions

| Decision | Rationale |
|---|---|
| Rule-based consent engine, not LLM | Deterministic, auditable, property-testable, no prompt injection surface |
| Consent filtering before generation | LLM never sees non-permitted content |
| Withheld content flagged, not silently dropped | Silence implies completeness — that's the harm vector |
| 4-tier fallback ladder | System is never blank, never raises to the user |
| Safety-critical carve-out | Risk-of-harm content withheld → escalation flag, not silence |
| Fixed seed (42) everywhere | Eval numbers are reproducible across machines |

## Metrics

Measured over 60 synthetic clients at role=counsellor, evaluation date pinned to
2025-03-01. Baseline is last-3-sessions verbatim concatenation with regex keyword
redaction.

| Metric | Target | Baseline | Prototype |
|---|---|---|---|
| consent_leakage_rate | 0.0 | 1.000 | **0.000** |
| action_retention_rate | 1.0 | 0.000 | **1.000** |
| withheld_flag_recall | ≥0.95 | 0.000 | **1.000** |
| word_reduction | ≤0.40 | 1.000 | **0.343** |
| safety_escalation_recall | 1.0 | 0.000 | **1.000** |
| provenance_coverage | 1.0 | 0.000 | **1.000** |
| fallback_availability | 1.0 | 1.000 | 1.000 |

Regenerate with `make reproduce`. Read the limitations section of
`eval/report/report.md` before quoting these: they describe one synthetic
distribution, and end-to-end safety is bounded by tagger recall, which is not
measured here against human annotation.

## Documentation

| Doc | What's in it |
|---|---|
| `docs/architecture.md` | System diagram, design decisions, where the guarantees stop |
| `docs/schema.md` | All 7 tables, field by field |
| `docs/risk_register.md` | 7 risks with likelihood, impact, detection and residual |
| `docs/user_guide.md` | Install → data → run → read a brief → evaluate |
