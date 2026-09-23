# TIMELINE: 23 Sep 2026, 13:00–18:00 (Asia/Almaty). Tick boxes as you go; commit hourly (rule 5.4.8).

Official checkpoints (each needs a visible commit): **14:00 · 15:00 · 16:00 · 17:00 · 18:00 (final, frozen by organizer)**.
Integration syncs (2-min stand-up, everyone): **14:55 · 15:55 · 16:55 · 17:35**.

## 13:40 → 14:00  Setup (commit #1 "docs+skeleton")
- [ ] (all) Clone organizer repo (edu.astanahub.com) → copy this folder's content into it → `git add . && git commit -m "[docs] plan, contracts, agent instructions, mocks"` → push
- [x] (all) `cp .env.example .env`; B adds the API key locally (never commit)
- [x] (A) Put SCADA file(s) in `data/raw/`; run a quick pandas `head()`; tell B & C the real column names/time step
- [x] (B) FastAPI skeleton: `/api/health`, `/api/meta`, `/api/forecast` returning mocks via `ml_stub.py`
- [x] (C) Vite+React+TS+Tailwind scaffold, tabs layout, mocks copied to `public/mocks`

## 14:00 → 15:00  Foundations (commit #2)
- A: [x] `data.py` hourly farm series + flags  [ ] tz lag check  [x] `weather.py` fetch all chunks → `data/cache/nwp/` **commit the cache**  [x] `temporal_guard.py` + test
- B: [x] `llm.py` (anthropic/openai/compatible/none + cache)  [x] `ledger.py` + `test_ledger.py`  [x] `runs.py` + SSE endpoint replaying mock events
- C: [x] `api/client.ts` + `types.ts` (mock mode)  [x] Forecast page: FanChart + flags + briefing card + ledger badge

## 15:00 → 16:00  Core (commit #3)
- A: [x] features (per-model, cross-model, physics)  [x] power curve (isotonic)  [x] MOS wind + quantile HGB  [x] `validate --mode val_feb2025` → metrics json (first numbers!)
- B: [x] orchestrator state machine with tools on stub  [x] policy.py fallback  [x] prompts (planner/decider/critic/briefing)  [x] `/api/agent/run` + stream end-to-end
- C: [x] Agent Console timeline (SSE, mock replay)  [x] Backtest page (KPI tiles, model bars, MAE-by-lead, heatmap)

## 16:00 → 17:00  Integration (commit #4)
- A: [x] conformal widen  [x] baselines in metrics  [x] `test-run` → submission CSVs (672 rows)  [x] `api.py` complete → tell B "real ml ready"
- B: [x] switch `USE_ML_STUB=0`  [x] critic loop + briefing grounding  [x] recalc endpoint + REVISION block  [x] verify + tamper endpoints  [ ] `app.batch` over test issues
- C: [x] Ledger page (verify/tamper)  [x] Economics page  [x] switch to real API (`VITE_USE_MOCKS=0`)  [x] start README final  [ ] screenshots

## 17:00 → 17:40  Polish & reproducibility (commit #5)
- [x] (A) freeze models, commit `data/models`, `data/outputs`, `data/cache` (availability-evidence audit; models unchanged, replay outputs and cache sidecars refreshed)
- [ ] (B) record demo runs with the real LLM (fills `data/llm_cache`) for 3 demo dates (a calm day, a ramp day, a disagreement day); commit
- [ ] (C) README final (real metrics), 3 screenshots, slides (5–7), rehearse demo twice
- [ ] (all) **Clean-clone test** on a second laptop: `git clone … && cp .env.example .env && docker compose up --build` → UI works with `LLM_PROVIDER=none`

## 17:40 → 18:00  FREEZE
- [ ] No new features. Only fixes for README/launch.
- [ ] Final commit + push **before 17:55**: `[release] v1.0 SAMAL: ledger head <hash>` (put ledger head hash in the message = external timestamp anchor)
- [ ] Confirm on GitHub web UI that the last commit is visible.

## If behind schedule (cut in this order)
1. live "tomorrow" forecast · 2. economics page · 3. extra NWP models · 4. tamper demo UI (keep verify) · 5. critic loop (keep decider) · 6. conformal (keep raw quantiles)
**Never cut**: TemporalGuard, test-run submission, agent stream, README run instructions.
