# ml/AGENTS.md: Person A (ML engineer): the forecasting engine `openwind_ml`

Read first: `/PROJECT_PLAN.md` §3 and §5, `/docs/CONTRACTS.md` §1, §4, §5. Your public surface is **only** `openwind_ml/api.py`.
Everything must work offline once `data/cache/` is filled (`WEATHER_OFFLINE=1`).

## Package layout (create exactly this)
```
ml/
  requirements.txt        pandas==2.2.* numpy==1.26.* scikit-learn==1.5.* requests==2.32.* joblib python-dotenv pytest pyarrow(optional)
  pyproject.toml          name = "openwind_ml" (so backend can `pip install -e ml`)
  openwind_ml/
    __init__.py
    config.py             env + constants + PATHS + COLUMN_MAP for SCADA + thresholds
    data.py               load_scada() → hourly UTC farm frame with flags; tz check
    weather.py            Open-Meteo Previous Runs fetcher + csv.gz cache
    temporal_guard.py     lead_day(L), available_at(), assert_no_lookahead()
    features.py           build_training_frame(), build_issue_frame(issue_time)
    power_curve.py        fit/predict isotonic empirical power curve (+ density correction)
    models.py             MOS wind model, quantile HGB (p10/p50/p90), conformal widen, save/load
    baselines.py          persistence, climatology, raw_pc
    backtest.py           replay(mode) → forecasts/*.json + metrics/{mode}.json
    metrics.py            nmae, nrmse, bias, skill, pinball, picp, mae_by_lead, daily
    risk.py               risk_scan(forecast) (thresholds in config)
    api.py                CONTRACTS §1 functions (thin wrappers)
    cli.py                python -m openwind_ml.cli {inspect|fetch|train|validate|test-run|evaluate|live}
  tests/
    test_temporal_guard.py   ← MUST exist (configured offset-policy boundary checks)
    test_api_shapes.py       ← outputs match CONTRACTS
```

## Step-by-step (with time boxes)

### 1. Inspect SCADA (≤ 20 min), `cli inspect`
- Print columns, dtypes, head, time step, date range, NaN %, per-turbine or not, value range of power (0..1? 0..100? negative?).
- Fill `COLUMN_MAP` in config (e.g., `{"time": "Статистическое время", "wind": "...", "power": "...", "temp": "..."}`) and
  `TURBINE_ID_COLUMN` or file-per-turbine pattern. Normalize power to 0..1 if given in %.
- Resample to hourly mean, **hour-beginning label**. Farm `p` = mean over turbines available that hour; `wind_meas` = mean wind.
- Timezone: assume local → convert with explicit offsets: before 2024-03-01 00:00 local use UTC+6, after use UTC+5
  (Almaty switched), unless the lag check says data is already UTC. **Lag check**: for each month, corr(wind_meas, nwp v100)
  for shifts −3..+3 h → print table. Document the conclusion in `docs/PROGRESS.md`.

### 2. Weather fetch + cache (≤ 40 min), `cli fetch`
Endpoint verified working (see PROJECT_PLAN §3):
```python
BASE = "https://previous-runs-api.open-meteo.com/v1/forecast"
VARS = ["wind_speed_10m","wind_speed_100m","wind_direction_10m","wind_direction_100m",
        "temperature_2m","relative_humidity_2m","surface_pressure"]   # try adding wind_speed_80m, wind_speed_120m, wind_gusts_10m
def build_url(model, start, end, days=(1,2,3)):
    hourly = [f"{v}_previous_day{k}" for v in VARS for k in days]
    return (f"{BASE}?latitude={LAT}&longitude={LON}&hourly={','.join(hourly)}&models={model}"
            f"&start_date={start}&end_date={end}&wind_speed_unit=ms&timezone=GMT")
```
- One model per request, **3-month chunks** from 2024-03-01 to 2026-03-02 (≈ 8 chunks × 3 models = 24 calls). Sleep 1 s between
  calls, retry 3× with backoff on 429/5xx. Columns come back suffixed with the model when `models=` has several; with one model they
  are not suffixed. Handle both.
- Save `data/cache/nwp/{model}_{start}_{end}.csv.gz` (time UTC + columns). Loader concatenates all chunks per model and **drops all-null
  columns** (some models lack some vars). Also try `gem_seamless`, `jma_seamless`, `ukmo_seamless`, `meteofrance_seamless`:
  keep any with ≥ 90% coverage in Feb 2026 and in Mar 2024–Jan 2026.
- ⚠️ Archive starts ~2024-03-01 (GFS/ICON) and ~2024-03-15 (ECMWF). Earlier dates return nulls; that's expected.
- If the venue network blocks it: phone hotspot. **Commit the cache immediately after the first successful fetch.**

### 3. TemporalGuard (≤ 15 min), the compliance heart
```python
import math
def lead_day(lead_h: int, latency_h: int = LATENCY_H) -> int:
    return math.ceil((lead_h + latency_h) / 24)                  # validate lead 1..48 and K 1..7; no silent capping
def est_init_time(target_time, k):                                 # offset-derived estimate, not source run metadata
    return target_time - pd.Timedelta(hours=24 * k)
def assert_no_lookahead(rows, issue_time, latency_h=LATENCY_H):
    for r in rows:                                                 # r has target_time, lead_day
        assert est_init_time(r.target_time, r.lead_day) + pd.Timedelta(hours=latency_h) <= issue_time
```
`test_temporal_guard.py`: for 1000 random (issue_time, lead) pairs assert the invariant; assert SCADA features ≤ issue_time.
Every ForecastResult must carry `max_nwp_init_time_used` (= max estimated offset time over rows),
`max_estimated_nwp_init_time_used`, `max_scada_time_used`, policy version, configured latency, and
`source_release_time_verified:false`. The provider release time is not proven.

### 4. Features (≤ 30 min)
For target hour `T` and lead-day `K`, per model `m`: `ws10, ws100, wd10, wd100, t2m, rh, sp` from `*_previous_dayK`. Derived:
`alpha = log(ws100/ws10)/log(10)` (clip −0.2..0.8), `v_hub = ws100*(HUB/100)**alpha`, `rho = sp*100/(287.05*(t2m+273.15))`,
`v_eq = v_hub*(rho/1.225)**(1/3)`, `sin/cos(wd100)`. Cross-model: `v_hub_mean/median/std/min/max`, `t2m_mean`, `rh_mean`.
Calendar: local hour sin/cos, doy sin/cos, `lead_h`, `lead_day`. Physics feature: `pc_raw = powercurve(v_hub_mean)`.
- **Training frame**: for every historical hour T with SCADA target, create rows for K=1,2,3 (lead_h sampled consistently:
  K=1 → lead 1..16, K=2 → 17..40, K=3 → 41..48; simplest: set `lead_h` = representative value 12/28/44, or replicate per lead if time allows).
- **Issue frame** (`build_issue_frame(issue_time)`): 48 rows, lead 1..48, K from `lead_day()`, only cache rows ≤ availability.

### 5. Models (≤ 45 min)
```python
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.isotonic import IsotonicRegression
pc = IsotonicRegression(increasing=True, out_of_bounds="clip", y_min=0, y_max=1).fit(clean.wind_meas, clean.p)
mos = HistGradientBoostingRegressor(max_iter=400, learning_rate=0.05, max_leaf_nodes=31, l2_regularization=1.0).fit(X, wind_meas)
X["pc_mos"] = pc.predict(mos.predict(X))
qm = {q: HistGradientBoostingRegressor(loss="quantile", quantile=q, max_iter=500, learning_rate=0.05,
                                        max_leaf_nodes=31, min_samples_leaf=40).fit(X, y) for q in (0.1, 0.5, 0.9)}
# predict → stack → sort along quantile axis → clip [0,1]
```
- Train on **clean** rows (`~flag_outage & ~flag_stuck & ~flag_missing`) from 2024-03-15 on (NWP-available).
- **Conformal (CQR)**: hold out the last 8 weeks before train_end: `E = max(p10−y, y−p90)`; `qhat = quantile(E, 0.8*(1+1/n))`;
  final `p10 -= qhat`, `p90 += qhat` (clip). Save `qhat` in the model bundle. `widen` arg in run_forecast adds extra margin.
- Save bundle `data/models/{mode}.joblib` = {pc, mos, qm, qhat, feature_list, train_end, version}. Version = `hybrid-qhgb-train{date}-{sha6}`.
- Baselines: persistence = last hourly p at `≤ issue_time` flat; climatology = mean p by (month, local hour) from training;
  raw_pc = pc(v_hub_mean); mos_pc = pc(mos wind).

### 6. Backtest / validation / test (≤ 45 min), `cli validate --mode val_feb2025` / `cli test-run`
- `val_feb2025`: train_end = 2025-01-30T19:00Z (issue time of 2025-01-31), issues 2025-01-31…2025-02-27. `val_winter` similar.
- `test`: train on all data ≤ 2026-01-30T19:00Z, issues 2026-01-31…2026-02-27 → forecasts/*.json + submission CSVs (CONTRACTS §5).
- Metrics on **day-ahead leads 24–47** (headline) + `mae_by_lead` over 1–48. Report on all rows and on available rows.
- Write `data/outputs/metrics/{mode}.json` exactly per CONTRACTS §4.5 (B and C depend on it).

### 7. api.py (≤ 20 min): thin wrappers, JSON-serializable, cached model bundles (load once).

## Definition of done (A)
- [ ] `python -m openwind_ml.cli fetch` fills cache; `WEATHER_OFFLINE=1 python -m openwind_ml.cli test-run` works from cache only
- [ ] `pytest ml/tests` green (temporal guard + shapes)
- [ ] `metrics/val_feb2025.json` shows hybrid beats persistence & raw_pc on day-ahead leads (if not, report honestly + explain)
- [ ] submission CSV with 672 rows (28 days × 24 h), no NaN, p10 ≤ p50 ≤ p90, all in [0,1]
- [ ] Numbers for the pitch written to `docs/PROGRESS.md` (NMAE, skill vs persistence, coverage)

## Pitfalls
- `previous_day0` = latest run: **never** use it for forecasting (it leaks up to 48 h).
- Don't use ERA5 / archive-api (reanalysis = actual weather) as forecast inputs. (OK for EDA only; don't ship it.)
- SCADA tz shift on 2024-03-01. Duplicate/missing hours around DST-like changes: dedupe with `groupby(level=0).mean()`.
- Feb 2026 SCADA is not provided → persistence for test issues uses the last available SCADA hour ≤ issue_time; for issues after
  31 Jan there is no fresh SCADA → persistence falls back to the last known value (document it) and the hybrid model does not use SCADA lags.
