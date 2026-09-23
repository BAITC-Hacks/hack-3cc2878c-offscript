# SAMAL — Self-Auditing Multi-model Agentic Loop
### HackAlem AI 2026 · Task: "Agentic AI for Wind Farm (ВЭС) Generation Forecasting"
*"Samal" (самал) = "breeze" in Kazakh.*

> **This is the master document.** Every teammate (and every AI coding agent — Claude Code, Codex, Cursor)
> must read this file first, then `AGENTS.md`, then the `AGENTS.md` inside their own folder.
> Detailed specs live in `docs/`. If something here conflicts with `docs/CONTRACTS.md`, **CONTRACTS.md wins**
> (it is the interface between the three of us).

---

## 0. TL;DR (30-second pitch)

SAMAL is an **autonomous AI agent that forecasts hourly wind-farm output 24–48 h ahead** for the two-turbine
wind farm in the **Shelek wind corridor (Almaty region, 43.645°N 78.536°E)**. It:

1. **Pulls archived forecasts from three weather models at once** (ECMWF, GFS and ICON, via Open-Meteo's *Previous Runs API*). "Archived" means the forecast exactly as it was published at the time. It never uses weather that became known later.
2. **Enforces a strict "time machine" (TemporalGuard):** code cannot touch any data published after the issue time.
3. **Forecasts a range, not one number.** It gives P10/P50/P90: a low case, the median and a high case, using a physics-informed model. The chance that the real value falls inside P10–P90 is calibrated to ~80% (conformal calibration).
4. **Runs as a self-auditing agent loop.** One LLM agent plans and calls tools. A second LLM agent (the "Critic") audits the result. The system recalculates when newer weather data arrives. Finally it writes a grid-dispatcher briefing in RU/KZ/EN, where every number is checked against the computed results, so no invented numbers.
5. **Seals every forecast in a hash-chained ledger ("Proof-of-No-Lookahead").** Each forecast is linked to the one before it, blockchain-style. This lets anyone *verify* that no forecast was changed after the fact and that none used future data. A "tamper" button in the UI shows the chain breaking live.

Business value: in Kazakhstan's balancing electricity market, the grid operator KEGOC must cover the gap between
forecast and actual output ("imbalance"). Better day-ahead forecasts mean smaller imbalances and lower costs, and more renewable
power can be integrated into the grid. The approach works for any wind or solar farm; only the coordinates and the farm's data change.

---

## 1. The task (what the organizers actually check)

Original text: `docs/TASK_ORIGINAL.md`. Requirement → feature mapping:

| # | Organizer requirement | SAMAL feature | Owner |
|---|---|---|---|
| R1 | Build a model of hourly WF generation from the provided history (Mar 2023 – 31 Jan 2026) | `ml/` two-stage physics-informed quantile model (MOS wind correction + empirical power curve + gradient boosting quantiles) | A |
| R2 | **Independently** fetch weather forecasts from open sources by WF coordinates, **as available at forecast time** | `ml/samal_ml/weather.py` (Open-Meteo Previous Runs API, 3+ models) + `temporal_guard.py` (lead-day selection rule, see §5.3) | A |
| R3 | Forecast next 24–48 h, hourly | Each issue produces 48 hourly values (lead 1–48 h); the official day-ahead product is lead 24–47 h | A |
| R4 | Agentic cycle: fetch weather → prepare → run model → hourly forecast → analyze → **recalculate on input update** | `backend/app/agent/` state-machine agent with LLM planner + tools + Critic + recalc policy, streamed live to the UI | B |
| R5 | Replay as if in the past: 31 Jan → forecast; 1 Feb → new forecast; … through 28 Feb | `make test-run` loops issue dates 2026-01-31 … 2026-02-27 (28 issues, covering 1–28 Feb day-ahead) and writes `data/outputs/submission/*.csv` | A (+B for agent mode) |
| R6 | Use **archived** forecasts, not actual weather | TemporalGuard + ledger records `max_nwp_init_time_used ≤ issue_time` for every block; automated test `test_no_lookahead` | A + B |
| Eval | README & reproducibility (25 pts!) | One-command run (`docker compose up`) + **offline replay** from the cached weather data included in the repo; the LLM part is optional (`LLM_PROVIDER=none` works) | C + all |

Scoring (technical round, 100): compliance/functionality 25 · technical implementation incl. agentic AI 25 · README & reproducibility 25 ·
value/applicability 15 · development potential & originality 10.
Demo Day (finals, 100): value 25 · result quality 20 · innovation 15 · scaling potential 20 · presentation & Q&A 20.

---

## 2. Why we win (differentiators — say these out loud at the demo)

| Typical team | SAMAL |
|---|---|
| One weather source, often *actual* (reanalysis) weather, so leakage | **3+ numerical weather prediction (NWP) models**, *archived* forecasts, with a formal lead-time rule and a unit test proving there is no lookahead |
| Single number forecast | **Probabilistic P10/P50/P90** with conformal calibration (guaranteed ~80% coverage on validation) |
| Plain ML on raw features | **Physics-informed**: corrects forecast wind to hub height from forecast-vs-measured history (MOS) → farm's empirical power curve (isotonic, monotone) → air-density correction → gradient boosting learns what physics misses |
| "Agent" = a chat box | **Real agent loop** with tool calling, a Critic agent (self-audit), recalculation policy and a live streamed trace |
| LLM free text with hallucinated numbers | **Numeric-grounding guardrail**: every number in the briefing must match the facts table, otherwise auto-regenerate |
| Trust us, we didn't cheat | **Proof-of-No-Lookahead ledger** (SHA-256 hash chain), verifiable in 1 click, with a live tamper demo |
| Needs their API key to run | Runs fully **offline & keyless** (cached weather data + rule-based agent fallback + cached LLM responses) |

---

## 3. Verified facts (checked 23 Sep 2026, 13:30)

- **Turbine 1**: 43.645150 N, 78.535604 E (43°38'42.5"N 78°32'08.2"E)
- **Turbine 2**: 43.643198 N, 78.538828 E (43°38'35.5"N 78°32'19.8"E), ~340 m from T1
- Farm centroid for weather queries: **lat 43.6442, lon 78.5372**. Location = Shelek/Chilik wind corridor, Almaty region
  (terrain-driven gap winds, so global models are biased; that is why the forecast-vs-measured correction (MOS) matters).
- **Open-Meteo Previous Runs API works for Feb 2026** (tested):
  `https://previous-runs-api.open-meteo.com/v1/forecast?latitude=43.6442&longitude=78.5372&hourly=wind_speed_100m_previous_day1,wind_speed_100m_previous_day2,temperature_2m_previous_day1,surface_pressure_previous_day1&start_date=2026-02-01&end_date=2026-02-01&models=ecmwf_ifs025,gfs_seamless,icon_seamless&wind_speed_unit=ms`
  - Returns columns like `wind_speed_100m_previous_day1_ecmwf_ifs025`. Times are **GMT/UTC** by default.
  - ECMWF grid snaps to (43.75, 78.5), elevation 555 m.
  - **Archive start**: GFS & ICON `previous_day1/2` from **~1 Mar 2024**; ECMWF IFS from **~mid-Mar 2024**. Before that: null.
    ⇒ **Honest training window for weather-driven models = Mar 2024 → Jan 2026 (~23 months).** The SCADA history from
    Mar 2023 is still used for the *power curve* (measured wind → power) and climatology.
  - Example of why multiple models matter: on 2026-02-01 ECMWF's day-1 forecast said ~6–8 m/s while GFS said ~10–11 m/s at 100 m.
- No API key needed; free non-commercial use; attribution **CC BY 4.0 "Weather data by Open-Meteo.com"** (put in README).
- ⚠️ The cloud sandbox couldn't reach Open-Meteo, but a normal laptop browser can. **Fetch once at the venue, then commit
  the cache (`data/cache/`)** so judges can replay offline.
- ⚠️ **Timezone trap**: Kazakhstan moved Almaty from UTC+6 to **UTC+5 on 1 Mar 2024**. SCADA "statistical time" is
  probably local. Verify with lag cross-correlation (measured wind vs NWP wind) per month (§5.2).

---

## 4. Architecture overview

```
                         ┌────────────────────────── frontend/ (React + Vite + TS + Tailwind + Recharts) ────────────────┐
                         │  Ops Forecast (fan chart)  │ Agent Console (live SSE) │ Backtest & Skill │ Ledger │ Economics   │
                         └───────────────▲──────────────────────────────────────────────────────────────────────────────┘
                                         │ REST + SSE  (docs/CONTRACTS.md)
┌────────────────────────────── backend/ (FastAPI) ─────────────────────────────────────────────────────────────────────┐
│  /api/forecast  /api/agent/run  /api/agent/stream/{id}  /api/backtest  /api/ledger  /api/ledger/verify  /api/live     │
│                                                                                                                         │
│  Agent Orchestrator (state machine)                                                                                     │
│   PLAN ─▶ FETCH_NWP ─▶ QC ─▶ FEATURES ─▶ PREDICT ─▶ ANALYZE(risk flags) ─▶ CRITIC ─┬─▶ BRIEF ─▶ PUBLISH(ledger)          │
│      ▲                                                                           │ reject (max 2)                        │
│      └──────────────────────────── RERUN with other variant / widen intervals ◀──┘                                      │
│   RECALC trigger: new NWP data for overlapping hours ─▶ diff > threshold ─▶ REVISION block                             │
│  LLM adapter: anthropic | openai | openai-compatible | none (rule-based)   + response cache (deterministic replay)       │
│  Ledger: SHA-256 hash chain, temporal invariants, verify + tamper demo                                                  │
└───────────────▲─────────────────────────────────────────────────────────────────────────────────────────────────────────┘
                │ Python import (ml is a package: `samal_ml`)
┌───────────────┴──────────────────── ml/ (pandas, numpy, scikit-learn) ─────────────────────────────────────────────────┐
│ data.py (SCADA load/clean/resample/tz) · weather.py (Open-Meteo fetch + cache) · temporal_guard.py (no-lookahead)      │
│ features.py · power_curve.py · models.py (MOS + quantile HGB + conformal) · baselines.py · backtest.py · metrics.py      │
│ cli.py:  fetch | train | validate | test-run | live                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
 data/raw (SCADA) · data/cache (NWP csv.gz, committed) · data/outputs (forecasts, metrics json, submission csv) · data/ledger
```

---

## 5. Forecasting methodology (Person A owns; everyone should understand for Q&A)

### 5.1 Data
- SCADA columns (per organizers): statistical time; average wind speed (m/s); normalized active power (line side); average ambient temperature (°C).
  Probably per turbine; maybe 10-minute resolution. **First 15 min: open the file, map columns in `ml/samal_ml/config.py`.**
- Resample to **hourly mean** (label = hour ending or hour beginning; pick one, document it and use it everywhere. Default: *hour-beginning, UTC*).
- Farm target `p` = mean normalized power of available turbines (0..1). Keep per-turbine series for diagnostics.

### 5.2 Cleaning & sanity (all flags kept as columns, never silently dropped)
- `flag_missing`, `flag_stuck` (same value ≥ 6 h), `flag_outage` (measured wind ≥ 6 m/s and p < 0.03 → down/curtailed),
  `flag_icing_suspect` (T ≤ +1 °C and p far below power curve at wind 5–15 m/s).
- Train the "available power" models on unflagged rows; report metrics on **all** rows (honest) and on available rows.
- **Timezone check**: for each month compute the lag (−3..+3 h) that maximizes correlation between measured wind and
  ECMWF `previous_day1` wind; expect a jump around 2024-03-01 if SCADA is local time. Convert everything to UTC.

### 5.3 TemporalGuard: the no-lookahead rule (core of compliance)
Issue time `t0` (UTC). Target hour `T = t0 + L`, lead `L ∈ {1..48}` h.
Open-Meteo `…_previous_dayK` at valid time `T` comes from a model run initialized ≈ `T − 24·K` h (±6 h run cycle),
published up to ~8 h later. It was therefore available at `t0` iff `T − 24K + LATENCY ≤ t0`, so:

```
K(L) = ceil((L + LATENCY_H) / 24),   LATENCY_H = 8 (config),   K ≤ 7
L = 1..16  → K=1   |   L = 17..40 → K=2   |   L = 41..48 → K=3
```
- Training rows are built **the same way**: for each historical hour T we create up to 3 samples (K=1,2,3) with features
  from `previous_dayK` and `lead_day=K` as a feature. Same distribution in training and test.
- SCADA features (e.g., last observed power, used by persistence baseline) must satisfy `ts ≤ t0`.
- `TemporalGuard.assert_ok(frame, t0)` raises if any used row violates the rule; every call logs
  `max_nwp_init_time_used` and `max_scada_time_used` → goes into the ledger block.
- Unit test `test_no_lookahead.py`: random t0/L combos, assert the invariant holds.

**Issue schedule (default):** `t0 = D 00:00 Asia/Almaty (UTC+5) = D−1 19:00 UTC`. Horizon = t0+1h … t0+48h.
Official **day-ahead product** = lead 24–47 → the whole local day D+1. Issues on D = 2026-01-31 … 2026-02-27 cover
1–28 Feb (28 issues). Lead 1–23 of the next issue = an **intraday update** of the same hours, which is our "recalculation" story.

### 5.4 Weather features (per model m ∈ {ecmwf_ifs025, gfs_seamless, icon_seamless} [+ gem_seamless, jma_seamless, ukmo_seamless if coverage OK])
`wind_speed_10m, wind_speed_100m (and 80/120 m if present), wind_direction_10m/100m, temperature_2m,
relative_humidity_2m, surface_pressure` for K ∈ {1,2,3}. Derived:
- per model: `sin/cos(direction)`, shear exponent `α = ln(v100/v10)/ln(10)`, hub-height wind `v_hub = v100·(H_hub/100)^α`
  (H_hub default 100 m; config), air density `ρ = p/(R_d·T)`, density-corrected wind `v_hub·(ρ/1.225)^(1/3)`.
- cross-model: `mean, median, std (spread), min, max` of v_hub → spread is our uncertainty signal.
- calendar: hour-of-day (local) sin/cos, day-of-year sin/cos, `lead_hours`, `lead_day K`.
- Missing models → columns NaN (HGB handles NaN natively).

### 5.5 Models (scikit-learn only: no LightGBM/libomp headaches on Mac)
- **B0 Persistence**: last observed hourly p at t0, held flat. (Standard baseline; skill scores are relative to it.)
- **B1 Climatology**: mean p by (month, local hour) from training data.
- **B2 Raw NWP → power curve**: ensemble-mean v_hub → empirical power curve. (Shows the value of ML.)
- **M1 MOS wind**: `HistGradientBoostingRegressor` predicts *measured* farm wind from NWP features (fixes corridor bias).
- **Power curve**: `IsotonicRegression(increasing=True, out_of_bounds='clip')` fit on clean SCADA (measured wind → p),
  all history since Mar 2023.
- **M2 main (hybrid quantile)**: `HistGradientBoostingRegressor(loss="quantile", quantile=q)` for q ∈ {0.1, 0.5, 0.9};
  features = all NWP features + `pc_mos = powercurve(M1 wind)` + `pc_raw = powercurve(ensemble v_hub)`.
  Post-processing: sort quantiles (no crossing), clip to [0,1].
- **Conformal calibration (CQR)**: on the last 8 weeks of the training period (held out), compute
  `E = max(p10 − y, y − p90)`; widen by the (1−α)(1+1/n) quantile of E → P10–P90 empirical coverage ≈ 80%.
- Optional **online blend**: weights of B2/M2/NWP-specific curves ∝ exp(−η·recent MAE) using only data ≤ t0 (validation mode only).

### 5.6 Evaluation protocol (Feb 2026 actuals are NOT given to us, so be explicit about this)
1. **Seasonal twin validation (primary)**: train on data ≤ 2025-01-30T19:00Z = issue time of the first replayed forecast (NWP features exist only from Mar 2024, so ~10.5 months),
   replay issues 2025-01-31 … 2025-02-27 exactly as the test → metrics. *Same month, same procedure as the hidden test.*
2. **Recent validation**: train < 2025-11-01, replay 2025-10-31 … 2026-01-30 (winter, 92 issues).
3. **Test run**: train on everything ≤ 2026-01-30T19:00Z (= issue time of the 31 Jan forecast; strictly no data after it), replay 2026-01-31 … 2026-02-27 → submission files.
   `ml/cli.py evaluate --actuals <file>` scores it instantly if the organizers release Feb actuals.

Metrics (target is normalized, so ×100 = % of capacity): **NMAE, NRMSE, bias, skill vs persistence (1 − MAE/MAE_pers),
pinball loss (mean over q), P10–P90 coverage (PICP, target 80%), MAE by lead hour, ramp hit-rate** (|Δp| ≥ 0.3 in 3 h).

### 5.7 Outputs (exact schemas in `docs/CONTRACTS.md`)
- `data/outputs/forecasts/{issue_date}.json`: one per issue (48 rows: target_time, lead_h, p10, p50, p90, v_hub_mean, spread, flags).
- `data/outputs/submission/forecast_feb2026_dayahead.csv`: one row per hour of Feb 2026 (lead 24–47).
- `data/outputs/submission/forecast_feb2026_all_issues.csv`: every issue × 48 leads.
- `data/outputs/metrics/{validation_name}.json`: all metrics + per-lead curve + per-day errors + baselines.

---

## 6. Agentic layer (Person B owns)

### 6.1 Loop (deterministic state machine, LLM makes the *decisions*, Python does the *math*)
```
PLAN      LLM → JSON plan (which NWP models, variant, whether to include optional checks). Fallback: default plan.
FETCH     tool fetch_nwp(issue_time)             → coverage per model, max_init_time_used (TemporalGuard)
QC        tool check_inputs(...)                  → missing models, stale runs, extreme values
PREDICT   tool run_forecast(issue_time, variant)  → 48×{p10,p50,p90}
ANALYZE   tool risk_scan(forecast)                → flags: ramp, icing, cut-out (>23 m/s), low-confidence (P90−P10>0.5), model disagreement (std>2.5 m/s)
          LLM → decision JSON {action: ACCEPT | RERUN(variant) | WIDEN | ESCALATE, rationale}
CRITIC    second LLM (role: independent grid-dispatch auditor) reviews forecast+facts → {approve, issues[], suggestion}
          if not approve → back to PREDICT with suggestion (max 2 loops)
BRIEF     LLM → briefing JSON {headline, summary, risks[], actions[], confidence} in ru/kk/en
          Numeric grounding check: every number in the text must be in the facts table (±rounding) → else regenerate (max 2)
PUBLISH   ledger.append(FORECAST block) + save forecast json
RECALC    on "new data" event (next issue / newer NWP / manual button): recompute overlapping hours; if
          MAE(new, published) > 0.05 or any hour leaves the published P10–P90 → REVISION block + short LLM note why
```
Every transition emits an SSE event (`docs/CONTRACTS.md §3`) → the UI shows the agent "thinking" live.

### 6.2 Tools are plain Python functions with JSON-schema signatures
Defined once in `backend/app/agent/tools.py`, exported to the LLM in the provider's tool format (Anthropic `tools` /
OpenAI `functions`). The LLM never computes numbers; it only chooses and explains.

### 6.3 LLM adapter (API key: unknown provider, so support all)
`.env`: `LLM_PROVIDER=anthropic|openai|openai_compatible|none`, `LLM_API_KEY`, `LLM_MODEL`, `LLM_BASE_URL` (for
OpenAI-compatible providers), `LLM_CACHE=1`. Temperature 0, JSON-only outputs validated by Pydantic; on invalid JSON:
one repair retry, then rule-based fallback. Cache key = sha256(provider|model|system|messages|tools) → `data/llm_cache/`.
Commit the cache for the demo runs → judges see identical agent traces **without any key**.

### 6.4 Proof-of-No-Lookahead ledger ("blockchain-lite", justified, not a gimmick)
Block = `{index, type: MODEL_TRAINED|FORECAST|REVISION, issue_time, created_at, model_version,
payload_sha256, inputs_sha256, max_nwp_init_time_used, max_scada_time_used, latency_h, prev_hash, hash}`;
`hash = sha256(canonical_json(block_without_hash))`. **Verify** = recompute all hashes + links + payload files +
temporal invariants (`max_nwp_init_time_used + latency ≤ issue_time`, `max_scada_time_used ≤ issue_time`).
**Tamper demo** = modify one p50 in a *copy* → verification fails at block N (red in UI). Why it matters: forecast
submissions to a grid operator must be provable and non-repudiable; it also proves to the jury that we did not peek at the answers.
Stretch: Ed25519 signature per block; publish the chain's head hash in the final git commit message (git timestamp = external anchor).

---

## 7. Frontend UX (Person C owns)
Dark "control-room" theme, 5 tabs:
1. **Forecast**: issue-date slider (31 Jan → 27 Feb 2026) + "Live: tomorrow" toggle; fan chart P10–P90 band + P50 line
   + dashed per-model NWP-derived curves; risk-flag chips; ledger badge "Block #12 ✓ verified"; briefing card with RU/KZ/EN switch.
2. **Agent Console**: "Run agent" button → live timeline of SSE events (tool calls with duration, LLM decisions, Critic verdict, recalc).
3. **Backtest & Skill**: KPI tiles (NMAE, skill vs persistence, coverage), model-vs-baselines bar chart, MAE-by-lead line,
   calendar heatmap of daily error, reliability plot (nominal vs observed coverage).
4. **Ledger**: block table (index, type, issue time, short hash, prev hash), "Verify chain" + "Tamper demo" buttons.
5. **Economics & Scale**: imbalance-cost calculator (capacity MW, price ₸/MWh sliders), with savings vs persistence
   computed from validation errors (all assumptions labelled), plus a "scale" map/list: same agent for any KZ wind/solar farm.
Frontend works from `shared/mocks/*.json` **before** the backend exists (env `VITE_USE_MOCKS=1`).

---

## 8. Team split: the three puzzle pieces

| Person | Folder | Mission | Hard deliverables |
|---|---|---|---|
| **A: ML** | `ml/` | Data + weather + TemporalGuard + models + validation + submission | `samal_ml` package, cached NWP in `data/cache`, metrics json, submission csv, `test_no_lookahead` |
| **B: Backend/Agent** | `backend/` | FastAPI, agent loop, LLM adapter, ledger, SSE | All endpoints from CONTRACTS, rule-based fallback, llm cache, ledger verify/tamper |
| **C: Frontend/Story** | `frontend/` + `README.md` + `docs/DEMO_SCRIPT.md` | Dashboard, demo, README, slides | 5 tabs, docker build, final README, 5–7 slide deck, rehearsed 3-min demo |

Interfaces: **A→B** Python functions in `ml/samal_ml/api.py` (signatures in CONTRACTS §1). **B→C** REST/SSE (CONTRACTS §2–3).
Until an interface is real, the consumer uses the stub/mock with the exact same shape.

---

## 9. Timeline (hackathon 13:00–18:00; commit at least every hour: rule 5.4.8 / 5.9.2 = disqualification otherwise)
Details + per-person checklists: `docs/TIMELINE.md`.

| Slot | A (ML) | B (Backend/Agent) | C (Frontend/Story) | Commit |
|---|---|---|---|---|
| 13:40–14:00 | Inspect SCADA, map columns | Repo hygiene, .env, FastAPI skeleton serving mocks | Vite scaffold, layout, tabs | **#1 docs+skeleton** |
| 14:00–15:00 | Hourly clean data, tz check, NWP fetch+cache, TemporalGuard+test | LLM adapter (3 providers + none), ledger module + tests | Forecast tab (fan chart) on mocks | **#2** |
| 15:00–16:00 | Features, power curve, MOS, quantile HGB, seasonal-twin validation | Agent state machine + tools (calling ml stubs) + SSE | Agent Console (SSE replay), Backtest tab | **#3** |
| 16:00–17:00 | Conformal, baselines, Feb-2026 test run, submission CSV | Wire real ml, Critic, briefing+grounding, recalc, verify/tamper | Ledger tab, Economics, real API switch | **#4** |
| 17:00–17:40 | Freeze model; commit outputs + cache | Record demo runs (llm cache), docker test | README final, screenshots, slides | **#5** |
| 17:40–18:00 | **Feature freeze.** Clean-clone test: `docker compose up` on another laptop. Final push ≤ 17:55 | | | **#6 FINAL** |

---

## 10. Scope tiers (protect the MVP!)
- **MUST (by 16:30)**: NWP fetch+cache, TemporalGuard, quantile model, Feb test run CSV, seasonal validation metrics,
  agent loop with fallback, SSE console, forecast chart, ledger verify, README run instructions.
- **SHOULD**: Critic agent, briefing RU/KZ/EN + grounding check, recalc/REVISION, conformal, backtest tab, tamper demo, docker compose.
- **WOW (only if ahead)**: live "tomorrow" forecast (current Open-Meteo forecast API), economics tab, extra NWP models,
  3×3 NWP neighbourhood features, Ed25519 signatures, auto-generated 1-page PDF report.
- **CUT if late (in this order)**: WOW → economics → tamper demo → Critic → conformal (keep raw quantiles).

## 11. Risks & mitigations
| Risk | Mitigation |
|---|---|
| Open-Meteo unreachable / rate-limited at venue | Fetch in 3-month chunks, retry+backoff; phone hotspot; commit cache ASAP; `WEATHER_OFFLINE=1` replay |
| SCADA format surprises (10-min, two files, tz) | Column map in config; A spends max 20 min; ask organizers early |
| LLM key limits / no key for judges | `LLM_PROVIDER=none` rule-based agent; committed llm cache; never block the pipeline on the LLM |
| Integration hell at 17:00 | Contracts + mocks from minute 0; B wires real ml by 16:15 at the latest |
| Leakage accusation | TemporalGuard + test + ledger invariants; say it proactively in the demo |
| Docker fails on judges' machine | Also document plain `python -m venv` + `npm` path; pin versions |

## 12. Rules compliance (from the Regulations PDF)
- Develop **only in the organizer-created GitHub repo** (edu.astanahub.com); commit **every hour**; final state at **18:00** is what counts.
- README must contain: description & purpose, architecture, technologies, install, run, dependencies, env params,
  **how to verify the main scenario** (5.4.15). If it can't be run from the README, the team is out (5.4.16).
- Key functionality must be checkable **without personal accounts/keys** (5.6.6): fallback + caches.
- Disclose all third-party components (libs, Open-Meteo data, AI tools used: Claude Code/Codex) in README (5.4.4).
- Never commit `.env`; ship `.env.example`. Participants must stay on site.
Full checklist: `docs/RULES_CHECKLIST.md`.

## 13. Demo Day pitch (3 min) & Q&A → `docs/DEMO_SCRIPT.md`
Story: **Problem** (wind is volatile → imbalances → costs; KZ is scaling renewables) → **Live demo** (agent runs for 14 Feb:
fetches 3 models → Critic catches wide spread → widens interval → briefing in Kazakh → ledger block sealed; tamper → red)
→ **Results** (skill vs persistence, coverage 80%) → **Scale** (any farm = coordinates + SCADA; KEGOC/Samruk-Energy; solar next).
