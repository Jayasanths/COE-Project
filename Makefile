.PHONY: setup data test eval run baseline report clean

# ── Setup ──────────────────────────────────────────────────────────────────
setup:
	uv sync --all-extras
	uv pip install https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl
	cd ui && npm install

# ── Data ───────────────────────────────────────────────────────────────────
data:
	uv run python -m data.synthetic.generate --seed 42 --clients 60

# ── Tests ──────────────────────────────────────────────────────────────────
test:
	uv run pytest tests/ -v --tb=short

test-policy:
	uv run pytest tests/test_policy.py -v --hypothesis-seed=42

test-failures:
	uv run pytest tests/test_failure_cases.py -v

# ── Eval ───────────────────────────────────────────────────────────────────
baseline:
	uv run python -m eval.baseline.run

eval:
	uv run python -m eval.harness.run
	uv run python -m eval.harness.report

# Full reproducible pipeline: data → baseline → prototype → report
reproduce:
	$(MAKE) data
	$(MAKE) baseline
	$(MAKE) eval
	@echo "\n✅ eval/report/report.md generated"

# ── Run ────────────────────────────────────────────────────────────────────
run:
	docker compose up

dev-api:
	uv run uvicorn src.main:app --reload --port 8000

dev-ui:
	cd ui && npm run dev

# ── Lint ───────────────────────────────────────────────────────────────────
lint:
	uv run ruff check src/ tests/
	uv run mypy src/policy/

fmt:
	uv run ruff format src/ tests/

# ── Clean ──────────────────────────────────────────────────────────────────
clean:
	rm -rf .pytest_cache __pycache__ dist
	find . -name "*.pyc" -delete
	find . -name "__pycache__" -delete
