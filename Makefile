# SAMAL: common commands (run from repo root). Windows users: run the commands inside each target manually.
PY ?= python3
.PHONY: setup fetch train validate test-run tests api web demo docker
setup:      ## create venv + install everything
	$(PY) -m venv .venv && . .venv/bin/activate && pip install -r backend/requirements.txt && pip install -e ml && cd frontend && npm install
fetch:      ## download archived NWP forecasts into data/cache (needs internet once)
	. .venv/bin/activate && python -m samal_ml.cli fetch
train:
	. .venv/bin/activate && python -m samal_ml.cli train --mode test
validate:   ## seasonal-twin + winter validation → data/outputs/metrics/*.json
	. .venv/bin/activate && python -m samal_ml.cli validate --mode val_feb2025 && python -m samal_ml.cli validate --mode val_winter
test-run:   ## replay 31 Jan → 27 Feb 2026 issues → submission CSVs
	. .venv/bin/activate && WEATHER_OFFLINE=1 python -m samal_ml.cli test-run
tests:
	. .venv/bin/activate && pytest ml/tests backend/tests -q
api:
	. .venv/bin/activate && cd backend && PYTHONPATH=.:../ml uvicorn app.main:app --reload --port 8000
web:
	cd frontend && npm run dev -- --port 5173
demo:       ## agent over all test issues (fills ledger + briefings), offline
	. .venv/bin/activate && cd backend && PYTHONPATH=.:../ml WEATHER_OFFLINE=1 python -m app.batch --mode test
docker:
	cp -n .env.example .env || true; docker compose up --build
