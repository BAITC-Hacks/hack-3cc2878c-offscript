# SAMAL: Self-Auditing Multi-model Agentic Loop for wind-farm power forecasting.
**HackAlem AI 2026 · Task: Agentic AI for Wind Farm Generation Forecasting (ВЭС).**

The runnable repository includes the archived weather cache, trained models, validation metrics, and the February 2026 submission CSVs. It works offline with no LLM key; an optional OpenAI key enables structured planning, risk decisions, critique, and grounded trilingual briefings.

## 1. What it is & why (description and purpose)
SAMAL is an autonomous AI agent that produces **hourly, probabilistic (P10/P50/P90) power forecasts 24–48 h ahead** for the two-turbine
wind farm in the Shelek corridor (Almaty region, 43.645°N, 78.536°E). It replays **28 daily issues, 31 Jan → 27 Feb 2026**, covering every hour of February's day-ahead product as if in real time,
using **only archived weather forecasts that existed at each issue time**, audits itself with a Critic agent, recalculates when newer
weather data arrives, writes dispatcher briefings in 🇰🇿 Kazakh / 🇷🇺 Russian / 🇬🇧 English, and seals every forecast into a hash-chained
**Proof-of-No-Lookahead ledger**.

Honest day-ahead validation (leads 24–47 h, normalized to farm capacity):

| Held-out issue period | Evaluated hours | NMAE | Skill vs persistence | P10–P90 coverage |
|---|---:|---:|---:|---:|
| February 2025 seasonal twin | 667 | 22.1% | +47.3% | 96.0% |
| Winter 2025–26 | 2,208 | 18.4% | +51.0% | 80.6% |

The first interval is conservative; coverage is measured, not claimed as a guarantee. February 2026 actual generation is unavailable, so no hidden-test accuracy is asserted.

## 2. Architecture
The flow is `archived ECMWF/GFS/ICON forecasts + organizer SCADA → TemporalGuard → MOS/power-curve/quantile ML → agent planner/decider/critic → briefing + immutable forecast payload → SHA-256 ledger → REST/SSE → control-room UI`. Numeric forecasts always come from Python, never the LLM.
- `ml/`: `samal_ml`: SCADA cleaning, Open-Meteo archived-forecast fetcher with **TemporalGuard**, physics-informed quantile model, backtests
- `backend/`: FastAPI: agent orchestrator (planner/decider/critic LLMs + tools), SSE stream, ledger, REST API
- `frontend/`: React dashboard: forecast fan chart, live agent console, backtest skill, ledger verify/tamper, economics
- `data/`: raw SCADA, cached weather (committed → offline replay), outputs (forecasts, metrics, **submission CSVs**), ledger, LLM cache

## 3. Technologies
Python 3.11, pandas, NumPy, scikit-learn (HistGradientBoosting quantile, Isotonic), FastAPI, sse-starlette, Pydantic, Anthropic/OpenAI SDKs
(optional), React 18 + Vite + TypeScript + Tailwind + Recharts, Docker Compose. Weather: Open-Meteo Previous Runs API (ECMWF IFS, NCEP GFS, DWD ICON).

## 4. Installation
**Option A: Docker (recommended)**
```bash
git clone https://github.com/BAITC-Hacks/hack-3cc2878c-offscript.git
cd hack-3cc2878c-offscript
cp .env.example .env          # real ML, offline weather, deterministic keyless agent
docker compose up --build     # UI http://localhost:5173 · API http://localhost:8000/docs
```
**Option B: local**
```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt && pip install -e ml
cd frontend && npm ci && cd ..
```

## 5. Running
```bash
make validate    # validation backtests → data/outputs/metrics/*.json
make test-run    # replay 31 Jan → 27 Feb 2026 issues → data/outputs/submission/*.csv
make demo        # agent over all test issues (ledger + briefings), offline and keyless by default
make api         # http://localhost:8000/docs
make web         # http://localhost:5173
```
(Refetch weather from the internet: `WEATHER_OFFLINE=0 make fetch`.)

## 6. Dependencies
See `ml/requirements.txt`, `backend/requirements.txt`, `frontend/package.json` (all pinned).

## 7. Environment variables
See `.env.example`. For optional OpenAI intelligence, set `LLM_PROVIDER=openai`, `LLM_MODEL=gpt-4o-mini`, and `LLM_API_KEY` in the **repository-root `.env` only**. Never place the key in `frontend/.env.local`, commit it, or paste it into browser code. `LLM_PROVIDER=none` remains a complete deterministic fallback. `WEATHER_OFFLINE=1`, `USE_ML_STUB=0`, `NWP_LATENCY_H=8`, and `FARM_CAPACITY_MW=5.0` are the reproducible defaults; capacity is an economics/display assumption, not a measured farm rating.

## 8. How to verify the main scenario (for the technical commission)
1. `docker compose up --build` → open http://localhost:5173
2. **Forecast** tab: choose issue date 14 Feb 2026 → 48-h fan chart P10/P50/P90, risk flags, briefing (EN/RU/KZ), ledger badge.
3. **Agent Console**: click *Run agent* → watch the full cycle stream live: plan → fetch NWP (TemporalGuard ✓) → QC → forecast → risk scan →
   decision → Critic review (may loop) → briefing → ledger block. Click *Review & recalculate* to compare a manual uncertainty review or newly updated cached inputs against the prior forecast; the trace labels whether inputs actually changed.
4. **Ledger**: *Verify chain* ✓ → *Tamper demo* ✗ (shows detection).
5. Submission files: `data/outputs/submission/forecast_feb2026_dayahead.csv` (672 hourly rows) and `…_all_issues.csv`.
6. Tests: `make tests` (includes `test_temporal_guard.py`: proof of no lookahead).

## Compliance with "archived forecasts only"
Lead-day rule `K = ceil((lead_h + 8)/24)` on Open-Meteo `*_previous_dayK` variables ensures every weather value was initialized early enough under the eight-hour publication-latency assumption. See `PROJECT_PLAN.md` §5.3, `ml/samal_ml/temporal_guard.py`, and the ledger's per-block `max_nwp_init_time_used`. The forecast API only displays a ledger proof when the block's payload hash matches that exact forecast; published payload files are immutable.

## Third-party components, data & AI tools (rule 5.4.4)
- Weather data by **Open-Meteo.com** (CC BY 4.0), models ECMWF IFS, NCEP GFS, DWD ICON via Open-Meteo.
- Open-source libraries listed in §3 (their licenses apply).
- SCADA data provided by the organizers. Confirm distribution rights before making any derived forecast or raw-data repository public.
- AI tools used during development: Claude Code / Codex (code assistance). OpenAI API (optional at runtime) for planning, risk decisions, critique, and briefings; only derived facts enter prompts. Pydantic validates structured responses and a deterministic fallback preserves operation on failure.

## Team
- Person A: ML & forecasting engine (`ml/`)
- Person B: Backend, agent & ledger (`backend/`)
- Person C: Frontend, README & demo (`frontend/`)
