# User guide

Install, generate data, run the system, read a brief, run the evaluation.

Written for a MacBook Air M4 (arm64). Nothing here is Apple-specific except the
thermal note at the end.

---

## 1. Install

Python 3.12 and Node 18+ are prerequisites. The Python version is pinned in
`pyproject.toml` and should not be changed.

```bash
# uv, if you don't have it
curl -LsSf https://astral.sh/uv/install.sh | sh

# everything else
make setup
```

`make setup` runs three things: `uv sync --all-extras`, the spaCy model
download, and `npm install` in `ui/`.

**If the spaCy model fails to download**, the system still works. The tagger
falls back to a stdlib sentence splitter that reads the same pattern table, so
categories and confidences are identical — only sentence boundaries can differ.
Check which backend is live:

```bash
uv run python -c "from src.tagger import backend_name; print(backend_name())"
```

---

## 2. Generate the synthetic data

```bash
make data
```

Writes `data/synthetic/clients.json`: 60 clients with sessions, goals, consent
records, pending actions and gold annotations. Seed is fixed at 42, so the
output is byte-identical on every machine.

Do not edit `clients.json` or `seed.json` by hand. The eval numbers assume this
exact data set.

---

## 3. Run the system

Two terminals.

```bash
make dev-api     # terminal 1 → http://localhost:8000
make dev-ui      # terminal 2 → http://localhost:5173
```

Check the API first:

```bash
curl http://localhost:8000/health
# {"status":"ok","version":"0.1.0"}
```

Interactive API docs are at `http://localhost:8000/docs`.

---

## 4. Read a brief

Open `http://localhost:5173`.

**Client list.** Sorted by red flags, then open high-priority actions — most
urgent first, not alphabetical. Click a client id.

**Brief page.** Read it in the order it is laid out; the order is the design.

1. **Escalation banner** (red, if present). Safety-relevant content was withheld
   or an action is 7+ days overdue. Act on this before the session.
2. **Conflict banner** (red, if present). The notes contradict each other. Both
   statements are shown. The system has not picked a winner and neither should
   you without checking.
3. **Withheld banner** (amber, if present). Topics the client has not consented
   to share with your role, each with a reason.
4. **Disclosure ledger.** Every sensitivity category found in the notes, with
   its state: ● disclosed, ○ withheld, ▲ withheld but safety-relevant. This is
   the fastest way to see the *shape* of what you have and have not been told.
5. **Summary**, with a tier badge showing how it was produced.
6. **Open actions**, with owner, due date and escalation level.
7. **Goals.**
8. **"Why this brief looks like this"** — expand for the consent record behind
   each disclosure and the specific reason behind each withholding.

**Change the role dropdown.** This is the demo. The same client produces a
materially different brief for a counsellor and a psychiatrist, because consent
is granted per role. It is not a filter over one brief — it is a separate
disclosure decision, recomputed.

**Consent console** (`/consent/:clientId`) lists every record with its live
status. Read-only: consent is captured and withdrawn with the client, not in
this interface.

---

## 5. Understand the tier badge

| Badge | Meaning |
|---|---|
| **T1** | A local language model wrote this. Grounded and validated, still verify. |
| **T2** | Extractive. Sentences copied verbatim from permitted notes. Nothing generated. |
| **T3** | Facts card. No narrative was disclosable; goals, actions and consent status only. |
| **T4** | Manual handover required. Complete the paper form before the session. |

A clean run sits at **T2**, because tier 1 is off by default. That is intended:
the system's guarantees should not depend on a model being installed or warm.

To try tier 1:

```bash
ollama serve                                   # separate terminal
ollama pull llama3.2:3b
PSYCH_HANDOVER_OLLAMA=1 make dev-api
```

Tier 1 output is rejected and dropped to tier 2 if it fails the grounding check,
so a badge reading T2 with Ollama running means the model produced something
unsupported by the source. That is the guard working.

---

## 6. Run the tests

```bash
make test              # everything
make test-policy       # property tests, 200 Hypothesis examples each
make test-failures     # the six documented failure cases
```

All tests must be green before any demo. `test_policy.py` proves the consent
engine correct in isolation; `test_failure_cases.py` proves the assembled system
does not reintroduce content the engine denied — a distinction that matters,
because a leak once existed downstream of a correct engine while every engine
unit test still passed.

---

## 7. Run the evaluation

```bash
make reproduce         # data → baseline → eval → report
```

Or step by step:

```bash
make data
make baseline          # regex-redaction baseline over the same 60 clients
make eval              # 7 metrics + eval/report/report.md
```

Read `eval/report/report.md`. Expected on a clean run:

| Metric | Baseline | Prototype | Target |
|---|---|---|---|
| `consent_leakage_rate` | 1.000 | 0.000 | 0.0 |
| `action_retention_rate` | 0.000 | 1.000 | 1.0 |
| `withheld_flag_recall` | 0.000 | 1.000 | ≥0.95 |
| `word_reduction` | 1.000 | 0.343 | ≤0.40 |
| `safety_escalation_recall` | 0.000 | 1.000 | 1.0 |
| `provenance_coverage` | 0.000 | 1.000 | 1.0 |
| `fallback_availability` | 1.000 | 1.000 | 1.0 |

The evaluation date is pinned to 2025-03-01 so overdue-action escalations do not
drift as the report ages.

**Read the limitations section at the bottom of the report before quoting any of
these numbers.** They describe one synthetic distribution. `consent_leakage_rate
= 0.0` means the pipeline is correct on this data — it is not a claim about real
clinical notes.

---

## 8. Lint

```bash
make lint              # ruff on src/ and tests/, mypy --strict on src/policy/
make fmt               # ruff format
```

`src/policy/` is type-checked strictly because it is the component whose
correctness the whole system rests on.

---

## Troubleshooting

**`❌ Run make data first.`** — the eval needs `data/synthetic/clients.json`.

**Client list is empty** — the API loads clients at startup. Generate the data,
then restart `make dev-api`.

**UI shows "Could not load the client list"** — the API is not running on port
8000, or it started before the data existed.

**Every brief shows T4** — the client has no permitted content, no goals and no
actions. Check the consent console; a client with no records has everything
withheld by default, which is correct behaviour.

**Briefs look identical across roles** — that client's consent records probably
cover all four roles. Try another; the generator varies this.

---

## Thermal note (fanless M4)

- Keep Ollama **off** during development. Tier 2 is the default path.
- Turn it on only when specifically demonstrating tier 1.
- Do not run Ollama, Docker and a long agent task at once.
- `make dev-api` and `make dev-ui` together is fine.
