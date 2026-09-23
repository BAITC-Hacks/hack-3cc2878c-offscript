# AGENTS.md: instructions for AI coding agents (Claude Code, Codex, Cursor, …)

You are helping a 3-person team at **HackAlem AI 2026** (5-hour hackathon, hard deadline **18:00 Asia/Almaty**).
Project: **SAMAL**, an agentic, probabilistic wind-farm power forecaster with a configured NWP availability policy. The Previous Runs API does not verify source release timestamps. Read in this order:

0. `START_HERE.md`: 2-minute quick start + kickoff prompts
1. `PROJECT_PLAN.md`: what we build and why (the master plan)
2. `docs/CONTRACTS.md`: **the interfaces between folders. Never break them silently.**
3. `<your folder>/AGENTS.md`: role-specific instructions (`ml/`, `backend/`, `frontend/`)
4. `docs/TIMELINE.md`: what must be done by which hour

## Repository map
```
PROJECT_PLAN.md       master plan            docs/ARCHITECTURE.md   deeper design notes
AGENTS.md / CLAUDE.md this file              docs/CONTRACTS.md      Python API, REST, SSE, file schemas (SOURCE OF TRUTH)
README.md             judge-facing README    docs/TIMELINE.md       hour-by-hour plan + checklists
ml/                   Person A (samal_ml)    docs/RULES_CHECKLIST.md  hackathon rules → actions
backend/              Person B (FastAPI+agent) docs/DEMO_SCRIPT.md  pitch, demo flow, Q&A
frontend/             Person C (React)       docs/TASK_ORIGINAL.md  organizer task text
shared/mocks/         JSON fixtures matching CONTRACTS (frontend uses them before backend is ready)
data/raw/             organizer SCADA data (do not modify)   data/cache/  NWP cache (commit it!)
data/outputs/         forecasts, metrics, submission CSVs     data/ledger/ hash-chain ledger
```

## Golden rules (all agents)
1. **Stay in your folder.** Only touch another folder if the human explicitly asks. Shared files
   (`docs/CONTRACTS.md`, `shared/mocks/`, `docker-compose.yml`, `README.md`) may be edited only with a note in
   `docs/CHANGELOG_CONTRACTS.md` (append: time, who, what changed, why).
2. **No lookahead, ever.** Any code that touches weather or SCADA data for a forecast issued at `t0` must go through
   `samal_ml.temporal_guard`. If you are unsure whether data was available at `t0`, it wasn't.
3. **LLM never computes numbers.** Python computes; the LLM plans, decides, critiques, explains. All LLM outputs are JSON
   validated with Pydantic, with a rule-based fallback. The whole system must run with `LLM_PROVIDER=none`.
4. **Offline reproducibility.** Anything fetched from the internet is cached under `data/cache/` (weather) or
   `data/llm_cache/` (LLM) and committed. `WEATHER_OFFLINE=1` must work.
5. **Time-box.** Prefer the simplest thing that works and demo-ready over perfect. MUST > SHOULD > WOW (PROJECT_PLAN §10).
6. **Small commits, often.** At least one commit per hour per person (hackathon rule, disqualification otherwise).
   Commit message format: `[ml|backend|frontend|docs] short description`.
7. **Secrets**: never commit `.env` or keys. Use `.env.example`.
8. **Python 3.11**, type hints, `ruff`-clean if time. Node 20 for frontend.
9. **Pin versions** in `requirements.txt` / `package.json` (judges must reproduce).
10. When you finish a task, tick it in `docs/TIMELINE.md` and add a one-line entry to `docs/PROGRESS.md`
    (`HH:MM [who] what`). This is also our evidence of hourly progress.

## Coding conventions
- Timestamps: **UTC internally**, ISO-8601 with `Z` in JSON. Local display = Asia/Almaty (UTC+5).
- Power is **normalized 0..1** everywhere in code; UI may show % or MW (capacity from config `FARM_CAPACITY_MW`).
- Quantile columns are named exactly `p10`, `p50`, `p90`.
- Issue date `D` means issue time `t0 = D 00:00 Asia/Almaty = (D−1) 19:00Z`; lead `L` = hours after t0 (1..48).
- Paths are built from `samal_ml.config.PATHS` (never hard-code absolute paths).
