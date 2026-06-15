PY := .venv/bin/python
PIP := .venv/bin/pip

.PHONY: install doctor api ui ui-install ui-build dev demo restart test lint eval fixture-check docker-up

install:
	python3 -m venv .venv
	$(PIP) install --upgrade pip
	$(PIP) install setuptools wheel
	$(PIP) install -e ".[dev,langfuse]" --no-build-isolation
	$(MAKE) ui-install

doctor:
	$(PY) scripts/doctor.py

api:
	$(PY) -m uvicorn app.main:app --port 8000 --reload

ui-install:
	cd frontend && npm install

ui-build:
	cd frontend && npm run build

# Vite dev server (proxies /api + /health to the API on :8000).
ui:
	cd frontend && npm run dev

# Live mode: requires LLM_API_KEY in .env
dev:
	bash scripts/run_stack.sh live

# Replay mode: deterministic demo, no API key required
demo:
	bash scripts/run_stack.sh replay

# Stop :8000 + :5173, then start the stack again (default: replay)
restart:
	bash scripts/restart_stack.sh replay

test:
	$(PY) -m pytest

lint:
	.venv/bin/ruff check .

eval:
	$(PY) -m app.evals.runner

fixture-check:
	$(PY) scripts/fixture_check.py

docker-up:
	docker compose up --build
