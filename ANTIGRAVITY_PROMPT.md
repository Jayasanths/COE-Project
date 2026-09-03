# CoE Project Build Prompt — Psychiatric Discharge Handover System
# Paste this entire file into the Antigravity IDE agent to build the project end-to-end.

---

## Context

You are building a consent-aware continuity summary system for counsellor and
social-worker handovers after acute psychiatric discharge. The problem: clients
repeat sensitive histories because handovers are incomplete and unfiltered.

The repo skeleton is already in place. Your job is to complete each module,
wire everything together, and ensure `make test` passes with zero consent leakage.

**Read AGENTS.md before touching any file. Follow every rule in it.**

---

## Environment

- Machine: MacBook Air M4 (arm64, fanless)
- IDE: Google Antigravity IDE
- Python: 3.12 (pinned in pyproject.toml — do not change)
- Package manager: uv (never pip, never conda)
- LLM (optional): Ollama running locally on port 11434 with `llama3.2:3b` or `qwen2.5:3b`
- Frontend: Vite + React + TypeScript + Tailwind v3
- DB: SQLite (file: data/handover.db)
- Container: OrbStack for dev, Docker Compose for final build

---

## Setup — run these once

```bash
# Install uv if not present
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install Python deps
uv sync --all-extras

# Download spaCy model
uv run python -m spacy download en_core_web_sm

# Generate synthetic data (60 clients, seed=42, deterministic)
make data

# Run baseline
make baseline

# Start API dev server
make dev-api

# Start frontend dev server (separate terminal)
make dev-ui
```

---

## What to build — in order

### Stage 1 — Data (already scaffolded)
File: `data/synthetic/generate.py`
- Already complete. Run `make data` to generate `data/synthetic/clients.json`.
- Do NOT modify seed.json or clients.json after generation.

### Stage 2 — Policy engine (HAND-WRITTEN — do not let agent modify)
Files: `src/policy/categories.py`, `src/policy/engine.py`
- Already complete. Run `make test-policy` to verify.
- Invariant: `consent_leakage_rate == 0` under all Hypothesis inputs.

### Stage 3 — Sensitivity tagger
File: `src/tagger/tagger.py`

Build a rule-based tagger using spaCy pattern matching.
It must:
- Load `en_core_web_sm`
- Define `EntityRuler` patterns for each SensitivityCategory
- Return a list of `TaggedSpan` objects with confidence scores
- Run entirely offline (no network calls)
- Be deterministic given the same input text

```python
# Interface the rest of the code expects:
def tag(text: str, session_id: str) -> list[TaggedSpan]: ...
```

### Stage 4 — Summary generator with fallback ladder
File: `src/generator/generator.py`

The fallback ladder has 4 tiers. Implement all 4:

- **Tier 1** — Ollama LLM summary (if Ollama available at localhost:11434)
  - System prompt: "You are a clinical handover assistant. Summarise only the
    provided permitted content. Do not invent, infer, or hallucinate clinical
    details. If uncertain, say so."
  - Validate output with Pydantic. On ANY exception → fall to tier 2.
  - temperature=0, seed=42

- **Tier 2** — Extractive: join permitted span texts, de-duplicate sentences.
  No generation. Prepend: "Extractive summary (AI unavailable):"

- **Tier 3** — Structured facts card: goals + open actions + consent status only.
  No free text. Returns a structured dict, not a paragraph.

- **Tier 4** — Manual handover required. Returns a printed checklist with:
  - Client ID, recipient role, date
  - List of open high-priority actions
  - "Complete paper handover form before session"

```python
def generate_brief(permitted_context: dict, tier_override: int | None = None) -> BriefOutput: ...
```

### Stage 5 — Explanation layer
File: `src/generator/explainer.py`

For every generated brief, produce:
1. **Why shown**: for each permitted category, which consent record authorised it
2. **Why withheld**: for each withheld category, whether it was (a) no record,
   (b) expired, (c) revoked, or (d) low-confidence tag
3. **Uncertainty note**: list all spans with confidence < 0.85

### Stage 6 — Action tracker with escalation
File: `src/actions/tracker.py`

State machine for `PendingAction.escalation_level`:
- Level 0 → open, within due date
- Level 1 → overdue by 1–3 days → notify owner
- Level 2 → overdue by 4–7 days → notify supervisor
- Level 3 → overdue 7+ days → appears in every brief as a red-flag

Rules:
- High-priority actions MUST appear in every brief regardless of consent filter
- Action ownership (owner_role + owner_id + due_date) must always be shown
- No unresolved high-priority action may disappear from consecutive briefs

### Stage 7 — React frontend
Directory: `ui/src/`

Build these 3 pages with Tailwind v3 (not v4):

**Page 1: Client list** (`/`)
- Table: Client ID, pseudonym, discharge date, open high-priority actions count
- Click row → go to brief page

**Page 2: Handover brief** (`/brief/:clientId`)
- Role selector dropdown (counsellor / social_worker / psychiatrist / nurse)
- Brief display with:
  - Summary text (tier badge showing which tier)
  - Yellow banner if withheld_count > 0 (shows withheld_notice)
  - Red banner if escalation_flags non-empty (shows each flag)
  - Actions table: description | owner | due date | priority | escalation badge
  - Goals list
  - Collapsible explanation section (why shown / why withheld)
  - Uncertainty note in grey italic if present

**Page 3: Consent console** (`/consent/:clientId`)
- Table of all consent records
- Show: category, role, purpose, granted, expires, revoked
- Read-only for now

Use TanStack Query for all API calls.
API base URL: `http://localhost:8000/api`

### Stage 8 — Evaluation harness completion
File: `eval/harness/run.py`

After Stage 3 and 4 are complete:
- Run the prototype against all 60 clients
- Write results to `eval/harness/prototype_results.json`
- Compute all 7 metrics against gold annotations
- Generate `eval/report/report.md` with a before/after table

Report format:
```
| Metric                | Definition | Target | Baseline | Prototype | Delta |
|---|---|---|---|---|---|
| consent_leakage_rate  | ...        | 0.0    | x.xx     | x.xx      | x.xx  |
...
```

### Stage 9 — Failure case tests
File: `tests/test_failure_cases.py`

Implement end-to-end tests for all 6 failure cases:

1. Consent revoked mid-episode → brief must not contain revoked content
2. Contradictory sessions → brief must contain a conflict notice, not pick one silently
3. Missing consent record → brief shows "consent not on file for [category]"
4. Low-confidence tag → span denied even with active consent record
5. LLM unavailable → system falls to tier 2 without raising an exception
6. Safety-critical carve-out → safety_risk content withheld but escalation_flag present

Each test:
- Builds a minimal synthetic client
- Calls the brief endpoint or generator directly
- Asserts the specific behaviour described above

### Stage 10 — Docs
Directory: `docs/`

Write these 4 markdown files:

**architecture.md** — system diagram description, design decisions, why rule-based consent
**schema.md** — all 7 tables with field names and types
**risk_register.md** — 7-row table: Risk | Likelihood | Impact | Harm to whom | Detection signal | Mitigation | Residual | Owner
**user_guide.md** — step-by-step: how to install, generate data, run the system, view a brief, run eval

---

## Invariants — check before every commit

```bash
make test         # must be 100% green
make eval         # consent_leakage_rate must be 0.0, action_retention_rate must be 1.0
make lint         # ruff + mypy must be clean on src/policy/
```

---

## Thermal management (M4 Air is fanless)

- During development: keep Ollama OFF. Use tier-2 extractive mode.
- Turn Ollama ON only when specifically testing tier-1 generation.
- Never run Ollama + Docker + long agent task simultaneously.
- `make dev-api` + `make dev-ui` together is fine.

---

## Viva questions — have answers ready

1. Why rule-based consent engine instead of LLM?
   → Auditability, determinism, no prompt injection surface, provable correctness via property tests.

2. What happens when the model is confidently wrong?
   → Provenance links + safety carve-out + fallback ladder. Never blank, never silent.

3. Why is the baseline fair?
   → It is exactly what overworked wards do today: copy-paste last 3 notes + keyword redact.

4. What is your individual contribution?
   → Policy engine (hand-written), property tests, data schema, evaluation harness.

5. How do you prove consent_leakage_rate = 0?
   → Hypothesis property test runs 200 randomised inputs. All pass.
