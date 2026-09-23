# SAMAL ML.

This folder contains the leakage-safe probabilistic forecasting engine for the two-turbine Shelek wind farm.

## What it does.

- Loads the two raw SCADA CSV files from `data/raw/`, converts their local statistical time to UTC, and aggregates them to hourly farm power.
- Retains missing, stuck, outage, and potential-icing flags. It does not silently fill or discard bad intervals.
- Uses only Open-Meteo **Previous Runs** weather products. A lead-time rule rejects any NWP product that could have become available after the forecast issue time.
- Fits a measured-wind correction, monotonic empirical power curve, and P10/P50/P90 gradient-boosting forecasts. The P10-P90 interval is widened with held-out conformal calibration.

## Install and check

From this directory:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pytest tests -q
.\.venv\Scripts\python.exe -m samal_ml.cli inspect
```

The inspection output should show normalized power in `[0, 1]`, UTC timestamps, and explicit flags.

## Weather and forecast workflow

`fetch` is the one networked command. It caches archived NWP files outside this folder under `data/cache/nwp/`; after the cache is populated, set `WEATHER_OFFLINE=1` for reproducible replay.

```powershell
.\.venv\Scripts\python.exe -m samal_ml.cli fetch
.\.venv\Scripts\python.exe -m samal_ml.cli train --mode val_feb2025
.\.venv\Scripts\python.exe -m samal_ml.cli validate --mode val_feb2025
.\.venv\Scripts\python.exe -m samal_ml.cli test-run
```

The public integration surface is `samal_ml/api.py`. Its forecast responses use UTC JSON timestamps, normalized power, and ordered `p10`, `p50`, `p90` quantiles.
