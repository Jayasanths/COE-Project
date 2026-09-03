# Agent rules for Antigravity

## Never modify without explicit instruction
- `src/policy/**` — deterministic consent engine, hand-written, audited
- `eval/gold/**` — ground-truth annotations
- `data/synthetic/seed.json` — synthetic data seed, must stay fixed

## Hard constraints
- Python 3.12 only. Never bump versions in pyproject.toml.
- The consent engine must NEVER call an LLM, network, or random source.
- Default branch of every policy decision is DENY.
- Every change must keep `make test` green before marking a task done.
- Never import `random` or `os.urandom` inside `src/policy/`.
- Never add `import anthropic` or `import openai` inside `src/policy/`.

## File protection
Do not create, delete, or rename files in:
- `eval/gold/`
- `data/synthetic/seed.json`
- `src/policy/engine.py`
- `src/policy/categories.py`

## Before finishing any task
1. Run `make test`
2. Run `make eval`
3. Report the `consent_leakage_rate` metric — it must be 0.0
4. Report `action_retention_rate` — it must be 1.0

## Model selection
- Architecture / refactor tasks → Gemini 3 Pro
- Boilerplate / CRUD → fastest available model
- Policy engine, eval harness → human writes, agent reviews only
