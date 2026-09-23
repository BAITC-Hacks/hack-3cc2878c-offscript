# SAMAL: Self-Auditing Multi-model Agentic Loop for wind-farm power forecasting.
**HackAlem AI 2026 · Task: Agentic AI for Wind Farm Generation Forecasting (ВЭС).**

> 🚧 Skeleton: Person C finalizes by 17:30 with real metrics & screenshots. Sections below are required by rule 5.4.15. Do not remove any.

## 1. What it is & why (description and purpose)
SAMAL is an autonomous AI agent that produces **hourly, probabilistic (P10/P50/P90) power forecasts 24–48 h ahead** for the two-turbine
wind farm in the Shelek corridor (Almaty region, 43.645°N, 78.536°E). It replays the test period **31 Jan → 28 Feb 2026** as if in real time,
using **only archived weather forecasts that existed at each issue time**, audits itself with a Critic agent, recalculates when newer
weather data arrives, writes dispatcher briefings in 🇰🇿 Kazakh / 🇷🇺 Russian / 🇬🇧 English, and seals every forecast into a hash-chained
**Proof-of-No-Lookahead ledger**.

Headline validation results (Feb 2025 "seasonal twin", day-ahead leads 24–47 h): **NMAE _X_% · skill vs persistence _+Y_% · P10–P90 coverage _Z_%**
(TODO fill from `data/outputs/metrics/val_feb2025.json`).

## 2. Architecture
(TODO insert diagram image `docs/img/architecture.png` or keep the ASCII from `PROJECT_PLAN.md` §4)
- `ml/`: `samal_ml`: SCADA cleaning, Open-Meteo archived-forecast fetcher with **TemporalGuard**, physics-informed quantile model, backtests
- `backend/`: FastAPI: agent orchestrator (planner/decider/critic LLMs + tools), SSE stream, ledger, REST API
- `frontend/`: React dashboard: forecast fan chart, live agent console, backtest skill, ledger verify/tamper, and economics
- `data/`: raw SCADA, cached weather (committed → offline replay), outputs (forecasts, metrics, **submission CSVs**), ledger, LLM cache

## 3. Technologies
Python 3.11, pandas, NumPy, scikit-learn (HistGradientBoosting quantile, Isotonic), FastAPI, sse-starlette, Pydantic, Anthropic/OpenAI SDKs
(optional), React 18 + Vite + TypeScript + Tailwind + Recharts, Docker Compose. Weather: Open-Meteo Previous Runs API (ECMWF IFS, NCEP GFS, DWD ICON).

## 4. Installation
**Option A: Docker (recommended)**
```bash
git clone <repo> && cd <repo>
cp .env.example .env          # works as is: LLM_PROVIDER=none, WEATHER_OFFLINE=1 in compose
docker compose up --build     # UI http://localhost:5173 · API http://localhost:8000/docs
```
**Option B: local**
```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt && pip install -e ml
cd frontend && npm install && cd ..
```

## 5. Running
```bash
make validate    # validation backtests → data/outputs/metrics/*.json
make test-run    # replay 31 Jan → 27 Feb 2026 issues → data/outputs/submission/*.csv
make demo        # agent over all test issues (ledger + briefings), offline
make api         # http://localhost:8000/docs
make web         # http://localhost:5173
```
(Refetch weather from the internet: `WEATHER_OFFLINE=0 make fetch`.)

## 6. Dependencies
See `ml/requirements.txt`, `backend/requirements.txt`, `frontend/package.json` (all pinned).

## 7. Environment variables
See `.env.example` (every variable documented). Key ones: `LLM_PROVIDER` (`none` works without any key), `LLM_API_KEY`, `LLM_MODEL`,
`WEATHER_OFFLINE`, `NWP_LATENCY_H`, `FARM_CAPACITY_MW` (assumption, display only).

## 8. How to verify the main scenario (for the technical commission)
1. `docker compose up --build` → open http://localhost:5173
2. **Forecast** tab: choose issue date 14 Feb 2026 → 48-h fan chart P10/P50/P90, risk flags, briefing (EN/RU/KZ), ledger badge.
3. **Agent Console**: click *Run agent* → watch the full cycle stream live: plan → fetch NWP (TemporalGuard ✓) → QC → forecast → risk scan →
   decision → Critic review (may loop) → briefing → ledger block. Click *Simulate new NWP run* → recalculation / REVISION block.
4. **Ledger**: *Verify chain* ✓ → *Tamper demo* ✗ (shows detection).
5. Submission files: `data/outputs/submission/forecast_feb2026_dayahead.csv` (672 hourly rows) and `…_all_issues.csv`.
6. Tests: `make tests` (includes `test_temporal_guard.py`: proof of no lookahead).

## Compliance with "archived forecasts only"
Lead-day rule `K = ceil((lead_h + 8)/24)` on Open-Meteo `*_previous_dayK` variables ensures every weather value was published ≥ 8 h before issue
time. See `PROJECT_PLAN.md` §5.3, `ml/samal_ml/temporal_guard.py`, and the ledger's per-block `max_nwp_init_time_used`.

## Third-party components, data & AI tools (rule 5.4.4)
- Weather data by **Open-Meteo.com** (CC BY 4.0), models ECMWF IFS, NCEP GFS, DWD ICON via Open-Meteo.
- Open-source libraries listed in §3 (their licenses apply).
- SCADA data provided by the organizers (not redistributed beyond this repo's purpose).
- AI tools used during development: Claude Code / Codex (code assistance). LLM API (optional at runtime) for planning, critique and briefings.

## Team
- Person A: ML & forecasting engine (`ml/`)
- Person B: Backend, agent & ledger (`backend/`)
- Person C: Frontend, README & demo (`frontend/`)
