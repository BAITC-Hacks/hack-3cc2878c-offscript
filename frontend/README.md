# OpenWind frontend

React 18/Vite 5 control-room dashboard for the HackAlem wind-farm forecasting task. It shows 48 hourly P10/P50/P90 forecasts, the day-ahead window (leads 24–47), archived-weather timing, operator risk flags, the autonomous agent trace and recalculation, historical backtesting, append-only ledger checks, and an illustrative balancing-cost scenario.

## Run locally

From the repository root:

```bash
cd frontend
npm ci
npm run dev
```

Open `http://localhost:5173`. Development mode defaults to the **live backend** at `http://127.0.0.1:8000`. Start the backend with `USE_ML_STUB=0`, the archived weather cache, and trained models. Keep the OpenAI key in the repository-root `.env` only; Vite must never receive it. The browser displays an error if the backend is unavailable rather than silently showing fixtures.

To configure a different backend address, create `frontend/.env.local` (do not commit it):

```dotenv
VITE_USE_MOCKS=0
VITE_API_URL=http://127.0.0.1:8000
```

For an isolated fixture demo without the backend, set `VITE_USE_MOCKS=1` and restart Vite. Fixtures are representative, not February 2026 forecasts or new validation results; demo model variants share one hourly series. The frontend consumes the routes and payloads in `docs/CONTRACTS.md`. If the backend reports `ml_stub=true`, the UI labels its data as demo data. The Dockerfile builds with `VITE_USE_MOCKS=0` and expects the repository root as Docker build context.

## Checks

```bash
npm run typecheck
npm run build
```

The mock fixtures are copied into `public/mocks/` automatically before dev/build and are ignored by Git. They are included in a local build for demo fallback, even when live mode is enabled, so production deployment should restrict access to `/mocks/` if fixture visibility matters. No weather fetch or model inference runs in the browser.

## Operator workflow

1. Choose an issue schedule and date; the Forecast tab opens the latest published agent-selected variant for that issue (or the hybrid model if none was published). Inspect the 48-hour fan chart, day-ahead table, flags, multilingual briefing, and CSV export; the variant selector remains available for comparison.
2. Run the agent to follow planning, archived-weather fetch, quality control, prediction, critic feedback, briefing, and publication. Trigger **Recalculate** for a revised weather run.
3. Inspect February 2025 or winter validation metrics, including skill against persistence, coverage, lead-hour error, reliability, and observed series.
4. Verify the ledger, then run the non-destructive tamper demo against a selected forecast block.
5. Change capacity and imbalance price assumptions to see estimated balancing cost; these figures are illustrative, not settlement prices.

All displayed timestamps use `Asia/Almaty`; API timestamps remain UTC ISO-8601. Output is normalized 0–1 until converted with the assumed farm capacity. Test-period actual generation and hidden-test accuracy are never claimed.
