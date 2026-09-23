# ARCHITECTURE: design notes & decisions (read PROJECT_PLAN §4–6 first)

## Agent run sequence
```mermaid
sequenceDiagram
  participant UI as Frontend
  participant API as FastAPI
  participant O as Orchestrator
  participant L as LLM (planner/decider)
  participant C as Critic LLM
  participant ML as openwind_ml
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
  O->>LG: append FORECAST block (payload hash, estimated NWP time, policy version)
  O-->>UI: SSE events all along, final "done"
```

## Recalculation ("when input data is updated")
Each adjacent pair of 48-hour issues shares 24 target hours. The next issue compares those hours' selected-NWP
feature-row hashes (excluding lead hour, retaining offset K) and forecast P50 values. It records the prior issue date,
comparable old/new overlap hashes, whole-issue hashes for provenance, overlap count, MAE/max difference, materiality,
and reason in its new FORECAST payload and ledger block. Legacy payloads without stored row hashes are reported as
comparison-unavailable rather than retroactively "verified."

For a published issue, `/api/agent/recalc` with `reason:"new_nwp"` publishes no block when its selected input hash is
unchanged. Changed selected inputs publish a same-issue `REVISION`; `reason:"manual_uncertainty_review"` is a distinct,
explicitly labelled operator path that may publish a review without new weather. The opt-in `NWPWatcher` polls the selected
local archive fingerprint (default 60 s) and triggers the same-issue path once per changed version. It does not fetch
fresh provider runs or assert their publication times; cache refresh is separate.

## Decisions (mini-ADRs)
| Decision | Why |
|---|---|
| Open-Meteo Previous Runs API | Free, no key, multi-model, fixed lead-time-offset archive; it does not expose exact source release timestamps |
| Configured latency 8 h in the lead-day rule | Conservative policy margin, not measured provider delay or a guarantee of release-time availability |
| scikit-learn HistGradientBoosting (not LightGBM/XGBoost) | Native quantile loss + NaN handling, no libomp install issues on Macs, fast enough |
| Isotonic power curve + MOS + GBM hybrid | Physics prior makes the model robust with only ~2 years of NWP; GBM learns local corridor effects |
| Conformal calibration | Empirical interval adjustment; report held-out coverage rather than a universal guarantee |
| LLM for decisions/explanations only | Numbers stay deterministic and testable; LLM failure never breaks forecasting |
| Hash-chain ledger | Tamper-evidence for anchored payloads and recorded offset-policy arithmetic; no claim of provider release-time proof |
| Deterministic state machine (no LangGraph) | Fewer dependencies, full control over events and fallbacks in a 5-hour build |
| SSE (not WebSockets) | One-way stream is all we need; trivial in FastAPI & browser |
| Caches committed to git | Judges reproduce offline and without keys (rule 5.6.6) |

Every NWP CSV cache chunk has a sidecar manifest with its request URL/parameters, date range, artifact SHA-256,
policy version, and explicit `source_release_time_verified:false`. New fetches record retrieval time and response
headers; older committed chunks have `retrieved_at:null`, and their reconstructed request URL is marked as such rather
than presented as a captured original HTTP request.
Old ledger blocks remain anchored unchanged and are reported as `legacy_policy_evidence`; new blocks record
`previous-runs-offset-v1` and the estimated initialization time separately from the backward-compatible field.
New blocks also hash the full immutable forecast file in addition to the backward-compatible row hash; legacy blocks
retain row-only hash coverage.
