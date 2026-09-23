# ARCHITECTURE: design notes & decisions (read PROJECT_PLAN §4–6 first)

## Agent run sequence
```mermaid
sequenceDiagram
  participant UI as Frontend
  participant API as FastAPI
  participant O as Orchestrator
  participant L as LLM (planner/decider)
  participant C as Critic LLM
  participant ML as samal_ml
  participant LG as Ledger
  UI->>API: POST /api/agent/run {issue_date}
  API-->>UI: run_id  (then UI opens SSE /api/agent/stream/run_id)
  O->>L: plan(context)
  O->>ML: fetch_nwp(issue_date)  [TemporalGuard]
  O->>ML: check_inputs → run_forecast → risk_scan
  O->>L: decide(facts, flags)
  O->>C: review(forecast summary, flags, decision)
  alt rejected (≤2 loops)
    O->>ML: run_forecast(variant/widen from critic)
    O->>C: review again
  end
  O->>L: briefing en/ru/kk (numeric grounding check)
  O->>LG: append FORECAST block (payload hash, input times)
  O-->>UI: SSE events all along, final "done"
```

## Recalculation ("when input data is updated")
Each target hour is forecast twice in the replay: day-ahead (lead 24–47, older runs K=2/3) and intraday by the next issue (lead 1–23, K=1/2).
`/api/agent/recalc` recomputes overlapping hours with the newest available lead-days, `forecast_diff()` → if material → `REVISION` block.
In a live deployment the trigger is a scheduler polling Open-Meteo for a new model run (every 6 h).

## Decisions (mini-ADRs)
| Decision | Why |
|---|---|
| Open-Meteo Previous Runs API | Free, no key, multi-model, gives *as-issued* forecasts: exactly what the task demands |
| Conservative latency 8 h in the lead-day rule | Guarantees availability; small skill loss is worth zero leakage risk |
| scikit-learn HistGradientBoosting (not LightGBM/XGBoost) | Native quantile loss + NaN handling, no libomp install issues on Macs, fast enough |
| Isotonic power curve + MOS + GBM hybrid | Physics prior makes the model robust with only ~2 years of NWP; GBM learns local corridor effects |
| Conformal calibration | Distribution-free coverage guarantee; easy to explain |
| LLM for decisions/explanations only | Numbers stay deterministic and testable; LLM failure never breaks forecasting |
| Hash-chain ledger | Tamper-evidence + provable no-lookahead; cheap; no blockchain infrastructure needed |
| Deterministic state machine (no LangGraph) | Fewer dependencies, full control over events and fallbacks in a 5-hour build |
| SSE (not WebSockets) | One-way stream is all we need; trivial in FastAPI & browser |
| Caches committed to git | Judges reproduce offline and without keys (rule 5.6.6) |
