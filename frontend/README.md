# SAMAL frontend

React 18/Vite 5 control-room dashboard for the HackAlem wind-farm forecasting task. It shows 48 hourly P10/P50/P90 forecasts, the day-ahead window (leads 24–47), archived-weather timing, operator risk flags, the autonomous agent trace and recalculation, historical backtesting, append-only ledger checks, and an illustrative balancing-cost scenario.

## Run locally

From the repository root:

```bash
cd frontend
npm ci
npm run dev
```

Open `http://localhost:5173`. Development mode defaults to **representative demo fixtures** copied from `shared/mocks/`; no backend or API key is needed. Dates, controls, simulated agent streaming, verification, and the tamper demonstration are interactive. The fixture is *not* a real February 2026 forecast or a new validation result. The shared fixture's original briefing disagrees with its hourly rows, so the demo adapter displays a deterministic, numerically consistent EN/RU/KZ briefing instead. Model variants in demo mode share the same hourly series; use the live API to compare real variants.

To use the backend, create `frontend/.env.local` (do not commit it):

```dotenv
VITE_USE_MOCKS=0
VITE_API_URL=http://localhost:8000
```

Start the backend separately per `backend/AGENTS.md`. The frontend consumes the routes and payloads in `docs/CONTRACTS.md` without putting an LLM key in browser code. If the backend reports `ml_stub=true`, the UI still labels its data as demo data. The Dockerfile builds with `VITE_USE_MOCKS=0` and expects the repository root as Docker build context.

## Checks

```bash
npm run typecheck
npm run build
```

The mock fixtures are copied into `public/mocks/` automatically before dev/build and are ignored by Git. They are included in a local build for demo fallback, even when live mode is enabled, so production deployment should restrict access to `/mocks/` if fixture visibility matters. No weather fetch or model inference runs in the browser.

## Operator workflow

1. Choose an issue schedule and date; inspect the 48-hour fan chart, day-ahead table, flags, multilingual briefing, and CSV export.
2. Run the agent to follow planning, archived-weather fetch, quality control, prediction, critic feedback, briefing, and publication. Trigger **Recalculate** for a revised weather run.
3. Inspect February 2025 or winter validation metrics, including skill against persistence, coverage, lead-hour error, reliability, and observed series.
4. Verify the ledger, then run the non-destructive tamper demo against a selected forecast block.
5. Change capacity and imbalance price assumptions to see estimated balancing cost; these figures are illustrative, not settlement prices.

All displayed timestamps use `Asia/Almaty`; API timestamps remain UTC ISO-8601. Output is normalized 0–1 until converted with the assumed farm capacity. Test-period actual generation and hidden-test accuracy are never claimed.
