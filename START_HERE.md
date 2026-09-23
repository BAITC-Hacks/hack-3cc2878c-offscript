# START HERE: team quick-start (read in 2 minutes)

**Chosen task:** Agentic AI for Wind Farm (ВЭС) generation forecasting. **Project:** SAMAL. **Deadline:** 18:00, commit every hour.

1. Clone the organizer GitHub repo; copy everything from this folder into it; commit + push (`[docs] plan & skeleton`).
2. `cp .env.example .env` (B puts the API key in `.env`, never commit it).
3. Put organizer SCADA data into `data/raw/`.
4. Each person opens their AI coding tool **in the repo root** and pastes their kickoff prompt below.
5. Follow `docs/TIMELINE.md`; log progress in `docs/PROGRESS.md`; interfaces are frozen in `docs/CONTRACTS.md`.

## Kickoff prompt: Person A (ML) → paste into Claude Code / Codex
```
Read AGENTS.md, PROJECT_PLAN.md (§3, §5), docs/CONTRACTS.md (§1, §4, §5) and ml/AGENTS.md.
Implement the samal_ml package in ml/ exactly as ml/AGENTS.md describes, in this order:
config+data inspection (the SCADA files are in data/raw/) → weather fetch+cache → temporal_guard + test → features → power curve →
MOS + quantile models → validate val_feb2025 → test-run submission → api.py. Work step by step, run each step, show me results,
keep the functions in api.py matching CONTRACTS §1 exactly. Start with `python -m samal_ml.cli inspect`.
```

## Kickoff prompt: Person B (Backend/Agent)
```
Read AGENTS.md, PROJECT_PLAN.md (§6), docs/CONTRACTS.md and backend/AGENTS.md.
Build the FastAPI backend in backend/ as described: first main.py + ml_stub.py (serving shared/mocks with CONTRACTS shapes) + health/meta/forecast
endpoints; then llm.py (anthropic/openai/openai_compatible/none + cache), ledger.py with tests, runs.py + SSE stream; then the orchestrator
state machine with tools, policy fallback, critic, grounded briefings, recalc, verify/tamper endpoints, and app/batch.py.
Everything must work with LLM_PROVIDER=none. Run tests after each module.
```

## Kickoff prompt: Person C (Frontend/Story)
```
Read AGENTS.md, PROJECT_PLAN.md (§7, §13), docs/CONTRACTS.md and frontend/AGENTS.md.
Scaffold the Vite + React + TS + Tailwind + Recharts app in frontend/ and build the 5 tabs against shared/mocks (VITE_USE_MOCKS=1):
Forecast (fan chart hero), Agent Console (SSE timeline with mock replay), Backtest & Skill, Ledger (verify/tamper), Economics.
Use the design tokens from frontend/AGENTS.md. Make it look like a professional grid control room. Then help me finalize README.md.
```

Key facts: turbines T1 43.645150,78.535604 · T2 43.643198,78.538828 · weather = Open-Meteo Previous Runs API (archive from ~Mar 2024) ·
issue date D = D 00:00 Asia/Almaty · lead 1–48 h · official day-ahead = lead 24–47 · test issues 2026-01-31…2026-02-27.
