# CONTRACTS: the interfaces between ml/ ↔ backend/ ↔ frontend/  (SOURCE OF TRUTH)

Change policy: any change → append to `docs/CHANGELOG_CONTRACTS.md` + tell the team out loud + update `shared/mocks/`.
Conventions: timestamps UTC ISO-8601 with `Z`; `*_local` fields are `+05:00`; power normalized 0..1; quantiles `p10/p50/p90`.
Issue date `D` (local) ⇒ `issue_time = (D−1)T19:00:00Z` (= D 00:00 Asia/Almaty). Lead `lead_h` ∈ 1..48, `lead_day` K ∈ {1,2,3}.
Modes: `test` (issues 2026-01-31…2026-02-27, no actuals), `val_feb2025` (issues 2025-01-31…2025-02-27, with actuals),
`val_winter` (issues 2025-10-31…2026-01-30, with actuals).

---
## §1 Python API: `ml/samal_ml/api.py` (Person A implements, Person B imports)
All functions return **JSON-serializable dicts/lists** (no DataFrames cross the boundary).

```python
from datetime import date, datetime
from typing import Literal

Mode = Literal["test", "val_feb2025", "val_winter"]
Variant = Literal["hybrid", "mos_pc", "raw_pc", "climatology", "persistence"]

def get_meta() -> dict: ...                                   # §4.1 shape
def list_issue_dates(mode: Mode) -> list[str]: ...           # ["2026-01-31", ...]
def issue_time_for(issue_date: str) -> str: ...              # "2026-01-30T19:00:00Z"
def fetch_nwp(issue_date: str, models: list[str] | None = None) -> dict: ...
    # → {"issue_time", "models_ok": [...], "models_missing": [...], "coverage": {model: 0..1},
    #    "max_nwp_init_time_used", "latency_h", "inputs_sha256", "n_rows",
    #    "input_fingerprints_by_target": {target_time_utc: sha256_of_selected_weather_row},
    #    availability metadata listed in §4.2}   (data itself stays cached inside ml)
def check_inputs(issue_date: str) -> dict: ...
    # → {"ok": bool, "issues": [{"code","severity","message"}], "spread_mean_ms": float, "models_ok": [...]}
def run_forecast(issue_date: str, variant: Variant = "hybrid", widen: float = 0.0,
                 models: list[str] | None = None, mode: Mode = "test") -> dict: ...   # ForecastResult §4.2
def risk_scan(forecast: dict) -> list[dict]: ...             # list[RiskFlag] §4.3
def get_metrics(mode: Mode) -> dict: ...                     # Metrics §4.5 (reads data/outputs/metrics/{mode}.json)
def get_series(mode: Mode) -> list[dict]: ...                # day-ahead series (lead 24–47) [{target_time, p10,p50,p90, actual|None}]
def forecast_diff(old: dict, new: dict) -> dict: ...         # {"overlap_hours", "mae", "max_abs", "hours_outside_old_band"}
```
Until A delivers, B uses `backend/app/ml_stub.py` which returns data from `shared/mocks/` with **exactly** these shapes.

---
## §2 REST API: FastAPI on `:8000` (Person B implements, Person C consumes). CORS: allow all.

| Method | Path | Request | Response |
|---|---|---|---|
| GET | `/api/health` | – | `{"status":"ok","version":"0.1.0","llm_provider":"none","weather_offline":true}` |
| GET | `/api/meta` | – | Meta §4.1 |
| GET | `/api/forecast` | `?issue_date=2026-02-14&variant=hybrid&mode=test` | ForecastResult §4.2 **plus** `"ledger": {"block_index":12,"hash":"…","verified":true}` only when that exact row payload was published (otherwise absent/null), and `"briefing": Briefings §4.4 or null` |
| GET | `/api/series` | `?mode=val_feb2025` | `{"mode","rows":[{"target_time","p10","p50","p90","actual"}]}` |
| POST | `/api/agent/run` | `{"issue_date":"2026-02-14","mode":"test","use_llm":true}` | `{"run_id":"r_20260214_ab12"}` |
| GET | `/api/agent/stream/{run_id}` | – | **SSE** stream of AgentEvent §3, ends with `type:"done"` |
| GET | `/api/agent/runs/{run_id}` | – | `{"run_id","status":"running|done|error","events":[AgentEvent…],"result":ForecastResult|null}` |
| GET | `/api/agent/runs` | – | `[{"run_id","issue_date","status","started_at","decision"}]` |
| POST | `/api/agent/recalc` | `{"issue_date":"2026-02-14","mode":"test","reason":"new_nwp","use_llm":true}` (`use_llm` optional, default true; explicit operator review uses `reason:"manual_uncertainty_review"`) | `{"run_id":"…"}` (stream it like a run). Unchanged inputs with `new_nwp` publish no REVISION. |
| GET | `/api/backtest` | `?mode=val_feb2025` | Metrics §4.5 |
| GET | `/api/ledger` | – | `{"length":n,"head_hash":"…","blocks":[Block §4.6…]}` |
| POST | `/api/ledger/verify` | – | `{"valid":true,"checked":n,"head_hash":"…","errors":[]}` |
| POST | `/api/ledger/tamper-demo` | `{"block_index":5}` | `{"valid":false,"first_bad_block":5,"errors":[{"block_index":5,"reason":"payload_sha256 mismatch"}]}`: works on an in-memory **copy**, never on the real ledger |
| GET | `/api/economics` | `?mode=val_feb2025&capacity_mw=5&price_kzt_mwh=15000` | Economics §4.7 |
| GET | `/api/live/tomorrow` | – | ForecastResult for the real "now" (WOW; return 501 if not done) |

Errors: `{"detail": "message"}` with proper HTTP code.

---
## §3 AgentEvent (SSE `event: agent`, `data:` = JSON)
```json
{"run_id":"r_20260214_ab12","seq":4,"ts":"2026-09-23T10:15:03Z",
 "stage":"PLAN|FETCH|QC|PREDICT|ANALYZE|DECIDE|CRITIC|BRIEF|PUBLISH|RECALC|DONE",
 "type":"stage_start|tool_call|tool_result|llm_decision|critic|recalc|ledger|briefing|warning|error|done",
 "title":"Fetched 3/3 NWP models (ECMWF, GFS, ICON)",
 "detail":{"...":"free-form but JSON"},
 "actor":"orchestrator|critic|tool|ledger",
 "llm":{"provider":"anthropic","model":"…","cached":true,"latency_ms":0} ,
 "duration_ms":412}
```
`llm` is null for non-LLM events. Final event: `{"type":"done","stage":"DONE","detail":{"decision":"ACCEPT","block_index":12,"loops":1}}`.

---
## §4 Shapes

### §4.1 Meta
```json
{"farm":{"name":"Shelek corridor WF (2 turbines)","lat":43.6442,"lon":78.5372,
  "turbines":[{"id":"T1","lat":43.645150,"lon":78.535604},{"id":"T2","lat":43.643198,"lon":78.538828}],
  "capacity_mw":5.0,"capacity_is_assumption":true,"hub_height_m":100,"tz":"Asia/Almaty"},
 "nwp_models":["ecmwf_ifs025","gfs_seamless","icon_seamless"],
 "variants":["hybrid","mos_pc","raw_pc","climatology","persistence"],
 "issue_dates":{"test":["2026-01-31","…","2026-02-27"],"val_feb2025":["2025-01-31","…"],"val_winter":["…"]},
 "temporal_guard":{"latency_h":8,"rule":"K = ceil((lead_h + latency_h)/24)"}}
```

### §4.2 ForecastResult
```json
{"issue_date":"2026-02-14","issue_time":"2026-02-13T19:00:00Z","mode":"test","variant":"hybrid",
 "model_version":"hybrid-qhgb-train2026-01-31-3f2a9c",
 "nwp_models_used":["ecmwf_ifs025","gfs_seamless","icon_seamless"],
 "max_nwp_init_time_used":"2026-02-13T11:00:00Z","max_scada_time_used":"2026-02-13T18:00:00Z","latency_h":8,
 "availability_basis":"fixed_previous_runs_offset_plus_configured_latency",
 "availability_policy_version":"previous-runs-offset-v1","source_release_time_verified":false,
 "source_release_time_evidence":"not_provided_by_open_meteo_previous_runs_api",
 "max_estimated_nwp_init_time_used":"2026-02-13T11:00:00Z","configured_latency_h":8,
 "capacity_mw":5.0,"widen":0.0,
 "rows":[{"target_time":"2026-02-13T20:00:00Z","target_time_local":"2026-02-14T01:00:00+05:00",
          "lead_h":1,"lead_day":1,"p10":0.12,"p50":0.31,"p90":0.55,
          "v_hub_mean":7.8,"v_hub_spread":1.4,"nwp_v_hub":{"ecmwf_ifs025":7.1,"gfs_seamless":9.0,"icon_seamless":7.3},
          "pc_raw":0.35,"temp_c":-3.2,"actual":null}],
 "summary":{"mean_p50":0.46,"energy_p50_mwh":55.2,"max_p90":0.93,"mean_band":0.38,"dayahead_mean_p50":0.44},
 "flags":[RiskFlag…]}
```
`rows` has 48 items (lead 1..48). `actual` filled only in validation modes.
Agent-published payloads additionally carry optional `nwp_input_fingerprints` (target-time → selected NWP feature-row SHA-256)
and `recalculation` evidence. Replaying the next issue compares only its 24 shared target hours with the prior issue;
whole-issue input hashes are recorded for provenance but are **not** compared across different horizons.
`forecast_materially_changed` uses a fixed rule: overlap P50 MAE ≥ 0.05, max absolute P50 shift ≥ 0.10, or any
new P50 outside the old P10–P90 band. An input-version change can be true while forecast materiality is false.
`max_nwp_init_time_used` is retained for compatibility but is an **offset-derived estimate**, not a provider-supplied run timestamp.
The configured 8-hour latency is an assumption; this policy does not independently verify the source publication time.

### §4.3 RiskFlag
`{"code":"RAMP_UP|RAMP_DOWN|ICING|CUT_OUT|LOW_CONFIDENCE|MODEL_DISAGREEMENT|DATA_GAP","severity":"info|warn|critical",
  "start":"…Z","end":"…Z","value":0.42,"message":"Ramp-up of +42% capacity within 3 h expected around 06:00 local"}`
Thresholds (config): ramp |Δp50| ≥ 0.30 in ≤ 3 h; icing T ≤ +1 °C & RH ≥ 90% & v_hub ≥ 3; cut-out v_hub ≥ 23 m/s;
low confidence p90−p10 ≥ 0.50; disagreement std(v_hub across models) ≥ 2.5 m/s; data gap = any model missing.

### §4.4 Briefings
```json
{"en":{"lang":"en","headline":"…","summary":"…","risks":[{"code":"RAMP_UP","text":"…"}],
       "actions":["…"],"confidence":"low|medium|high","grounded":true,"generated_by":"llm|template"},
 "ru":{…},"kk":{…}}
```

### §4.5 Metrics (`data/outputs/metrics/{mode}.json`)
```json
{"mode":"val_feb2025","train_end":"2025-01-30T19:00:00Z","n_issues":28,"n_hours":672,"leads":"24-47",
 "models":{"hybrid":{"nmae":0.121,"nrmse":0.172,"bias":-0.01,"skill_vs_persistence":0.41,"pinball":0.048,"picp_80":0.79},
           "mos_pc":{…},"raw_pc":{…},"climatology":{…},"persistence":{…}},
 "mae_by_lead":[{"lead_h":1,"hybrid":0.08,"persistence":0.06,"raw_pc":0.12}],
 "daily":[{"date":"2025-02-01","hybrid":0.10,"persistence":0.21}],
 "reliability":[{"nominal":0.8,"observed":0.79},{"nominal":0.5,"observed":0.47}],
 "feature_importance":[{"feature":"pc_mos","importance":0.31}]}
```

### §4.6 Ledger Block (`data/ledger/ledger.jsonl`, one JSON per line)
```json
{"index":12,"type":"GENESIS|MODEL_TRAINED|FORECAST|REVISION","issue_date":"2026-02-14","issue_time":"2026-02-13T19:00:00Z",
 "created_at":"2026-09-23T10:15:09Z","model_version":"…","payload_file":"data/outputs/forecasts/test/2026-02-14.json",
 "payload_sha256":"…","payload_file_sha256":"…","inputs_sha256":"…","max_nwp_init_time_used":"…","max_scada_time_used":"…","latency_h":8,
 "availability_basis":"fixed_previous_runs_offset_plus_configured_latency",
 "availability_policy_version":"previous-runs-offset-v1","source_release_time_verified":false,
 "source_release_time_evidence":"not_provided_by_open_meteo_previous_runs_api",
 "max_estimated_nwp_init_time_used":"…","configured_latency_h":8,
 "note":"ACCEPT after 1 critic loop","prev_hash":"…","hash":"…"}
```
New daily FORECAST blocks can include `recalculation:{path:"historical_overlap",previous_issue_date,
old_input_sha256,new_input_sha256,old_issue_input_sha256,new_issue_input_sha256,input_changed,
overlap_hours,mae,max_abs,hours_outside_old_band,forecast_materially_changed,reason}`.
Same-issue REVISION blocks carry the same evidence with `path:"same_issue_recalculation"` and
`revision_kind:"weather_input_update"|"manual_uncertainty_review"`. An automatic unchanged-input check writes a trace
and DONE event with `published:false`, **not** a new block. A manual uncertainty review is explicitly labelled even when
the selected weather inputs are unchanged. Historical anchored blocks are not retroactively given these fields; `/api/ledger`
may derive `revision_kind:"legacy_manual_uncertainty_review"` from an old `input_changed=False` note for display only.
`hash = sha256(canonical_json(block minus "hash"))`, canonical = `json.dumps(obj, sort_keys=True, separators=(",",":"), ensure_ascii=False)`.
`payload_sha256` = sha256 of canonical JSON of the ForecastResult **rows** only (so adding the ledger/briefing fields doesn't change it).
New blocks also store `payload_file_sha256` over the full immutable saved forecast file; legacy blocks predate this field and
retain their original row-only hash coverage. Neither hash attests the provider's publication time.
Existing anchored blocks are never rewritten. `/api/ledger` adds a derived `availability_evidence_status` per block;
`/api/ledger/verify` lists `legacy_policy_evidence_blocks` separately from integrity errors. Legacy blocks remain hash-valid
but do not claim the new policy metadata. Neither status proves the provider's actual release time.

### §4.7 Economics
```json
{"mode":"val_feb2025","capacity_mw":5,"price_kzt_mwh":15000,"assumption_note":"Illustrative flat imbalance price",
 "hours":672,"imbalance_mwh":{"hybrid":210.4,"persistence":355.9,"climatology":301.2},
 "cost_kzt":{"hybrid":3156000,"persistence":5338500},"savings_vs_persistence_kzt":2182500,"savings_pct":40.9,
 "annualized_savings_kzt":28400000}
```

---
## §5 Files
| Path | Writer | Content |
|---|---|---|
| `data/raw/*` | organizers | SCADA, never modified |
| `data/cache/nwp/{model}_{YYYYMMDD}_{YYYYMMDD}.csv.gz` | A | `time` (UTC) + `{var}_previous_day{K}` columns |
| `data/cache/nwp/{model}_{YYYY-MM-DD}_{YYYY-MM-DD}.csv.gz.manifest.json` | A | request URL/parameters plus capture-vs-reconstruction status, retrieval timestamp if captured, cache SHA-256, policy version, explicit unavailable release-time evidence; legacy chunks have `retrieved_at:null` |
| `data/cache/scada_hourly.csv.gz` | A | cleaned hourly farm series + flags |
| `data/outputs/forecasts/{mode}/{issue_date}.json` | A (batch) / B (agent) | ForecastResult |
| `data/outputs/metrics/{mode}.json` | A | Metrics |
| `data/outputs/submission/forecast_feb2026_dayahead.csv` | A | `target_time_local,target_time_utc,issue_time_utc,lead_h,p10,p50,p90,p50_mw` (672 rows) |
| `data/outputs/submission/forecast_feb2026_all_issues.csv` | A | same columns, all issues × 48 leads |
| `data/outputs/briefings/{mode}/{issue_date}.json` | B | Briefings |
| `data/outputs/agent_runs/{run_id}.json` | B | run record (events + result) |
| `data/ledger/ledger.jsonl` | B | blocks |
| `data/llm_cache/{sha256}.json` | B | cached LLM responses |
| `data/models/*.joblib` | A | trained models (commit if < 50 MB) |
