"""Stable JSON-only ML interface used by the backend."""

from __future__ import annotations

import functools
import json
from datetime import date
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd

from .baselines import climatology, persistence, raw_power_curve
from .config import FARM_CAPACITY_MW, HUB_HEIGHT_M, LAT, LATENCY_H, LON, NWP_MODELS, PATHS, TZ_NAME
from .data import load_scada
from .features import build_issue_frame, input_sha256
from .models import load_bundle, predict_bundle
from .risk import risk_scan as _risk_scan
from .weather import cache_coverage, load_nwp_cache

Mode = Literal["test", "val_feb2025", "val_winter"]
Variant = Literal["hybrid", "mos_pc", "raw_pc", "climatology", "persistence"]


def _stamp(value: object) -> str:
    timestamp = pd.Timestamp(value)
    timestamp = timestamp.tz_localize("UTC") if timestamp.tzinfo is None else timestamp.tz_convert("UTC")
    return timestamp.isoformat().replace("+00:00", "Z")


def _issue_timestamp(issue_date: str) -> pd.Timestamp:
    local_midnight = pd.Timestamp(issue_date).tz_localize(TZ_NAME)
    return local_midnight.tz_convert("UTC")


def _mode_dates(mode: Mode) -> pd.DatetimeIndex:
    if mode == "test":
        return pd.date_range("2026-01-31", "2026-02-27", freq="D")
    if mode == "val_feb2025":
        return pd.date_range("2025-01-31", "2025-02-27", freq="D")
    if mode == "val_winter":
        return pd.date_range("2025-10-31", "2026-01-30", freq="D")
    raise ValueError(f"unsupported mode: {mode}")


def get_meta() -> dict:
    return {
        "farm": {
            "name": "Shelek corridor WF (2 turbines)",
            "lat": LAT,
            "lon": LON,
            "turbines": [
                {"id": "T1", "lat": 43.645150, "lon": 78.535604},
                {"id": "T2", "lat": 43.643198, "lon": 78.538828},
            ],
            "capacity_mw": FARM_CAPACITY_MW,
            "capacity_is_assumption": True,
            "hub_height_m": HUB_HEIGHT_M,
            "tz": TZ_NAME,
        },
        "nwp_models": list(NWP_MODELS),
        "variants": ["hybrid", "mos_pc", "raw_pc", "climatology", "persistence"],
        "issue_dates": {mode: list_issue_dates(mode) for mode in ("test", "val_feb2025", "val_winter")},
        "temporal_guard": {"latency_h": LATENCY_H, "rule": "K = ceil((lead_h + latency_h)/24)"},
    }


def list_issue_dates(mode: Mode) -> list[str]:
    return [stamp.date().isoformat() for stamp in _mode_dates(mode)]


def issue_time_for(issue_date: str) -> str:
    return _stamp(_issue_timestamp(issue_date))


def fetch_nwp(issue_date: str, models: list[str] | None = None) -> dict:
    issue = _issue_timestamp(issue_date)
    selected = load_nwp_cache(models or NWP_MODELS)
    frame, audit = build_issue_frame(issue, selected)
    coverage = cache_coverage(selected.keys())
    return {
        "issue_time": _stamp(issue),
        "models_ok": list(selected),
        "models_missing": [model for model in (models or list(NWP_MODELS)) if model not in selected],
        "coverage": coverage,
        "max_nwp_init_time_used": audit["max_nwp_init_time_used"],
        "latency_h": LATENCY_H,
        "inputs_sha256": input_sha256(frame),
        "n_rows": int(len(frame)),
    }


def check_inputs(issue_date: str) -> dict:
    result = fetch_nwp(issue_date)
    rows, _ = build_issue_frame(_issue_timestamp(issue_date), load_nwp_cache())
    issues = []
    if result["models_missing"]:
        issues.append({"code": "DATA_GAP", "severity": "warn", "message": "Some requested NWP caches are unavailable"})
    if rows["v_hub_mean"].isna().any():
        issues.append({"code": "DATA_GAP", "severity": "warn", "message": "Some target hours have no usable 100m NWP wind"})
    return {
        "ok": not any(issue["severity"] == "critical" for issue in issues) and bool(result["models_ok"]),
        "issues": issues,
        "spread_mean_ms": round(float(rows["v_hub_spread"].mean()), 4) if rows["v_hub_spread"].notna().any() else float("nan"),
        "models_ok": result["models_ok"],
    }


@functools.lru_cache(maxsize=8)
def _bundle(mode: str):
    return load_bundle(mode)


def _optional_float(value: object) -> float | None:
    return None if value is None or not np.isfinite(value) else round(float(value), 6)


def _apply_variant(frame: pd.DataFrame, variant: Variant, scada: pd.DataFrame, issue: pd.Timestamp, bundle: object) -> pd.DataFrame:
    result = frame.copy()
    if variant == "hybrid":
        return result
    if variant == "mos_pc":
        result["p50"] = result["pc_mos"]
    elif variant == "raw_pc":
        result["p50"] = raw_power_curve(bundle.power_curve, result["v_hub_mean"])
    elif variant == "climatology":
        result["p50"] = climatology(scada, issue, len(result))
    elif variant == "persistence":
        result["p50"] = persistence(scada, issue, len(result))
    else:
        raise ValueError(f"unsupported variant: {variant}")
    margin = bundle.qhat if variant in {"mos_pc", "raw_pc"} else 0.15
    result["p10"] = np.clip(result["p50"] - margin, 0, 1)
    result["p90"] = np.clip(result["p50"] + margin, 0, 1)
    return result


def run_forecast(
    issue_date: str,
    variant: Variant = "hybrid",
    widen: float = 0.0,
    models: list[str] | None = None,
    mode: Mode = "test",
) -> dict:
    """Run one 48-hour forecast without permitting future weather or SCADA data."""
    issue = _issue_timestamp(issue_date)
    nwp = load_nwp_cache(models or NWP_MODELS)
    if not nwp:
        raise FileNotFoundError("no archived NWP cache found; run `python -m samal_ml.cli fetch` on a networked machine")
    inputs, audit = build_issue_frame(issue, nwp)
    bundle = _bundle(mode)
    predicted = predict_bundle(bundle, inputs, widen=widen)
    scada = load_scada()
    predicted = _apply_variant(predicted, variant, scada, issue, bundle)
    actual = scada["p"].reindex(pd.DatetimeIndex(predicted["target_time"])).to_numpy()
    rows: list[dict] = []
    for index, row in predicted.iterrows():
        target = pd.Timestamp(row["target_time"]).tz_convert("UTC")
        local = target.tz_convert(TZ_NAME)
        model_wind = {model: _optional_float(row.get(f"{model}_v_hub")) for model in nwp}
        rows.append(
            {
                "target_time": _stamp(target),
                "target_time_local": local.isoformat(),
                "lead_h": int(row["lead_h"]),
                "lead_day": int(row["lead_day"]),
                "p10": _optional_float(row["p10"]),
                "p50": _optional_float(row["p50"]),
                "p90": _optional_float(row["p90"]),
                "v_hub_mean": _optional_float(row.get("v_hub_mean")),
                "v_hub_spread": _optional_float(row.get("v_hub_spread")),
                "nwp_v_hub": model_wind,
                "pc_raw": _optional_float(row.get("pc_raw")),
                "temp_c": _optional_float(row.get("temp_c")),
                "actual": _optional_float(actual[index]) if mode != "test" else None,
            }
        )
    p50 = np.asarray([row["p50"] for row in rows], dtype=float)
    bands = np.asarray([row["p90"] - row["p10"] for row in rows], dtype=float)
    result = {
        "issue_date": issue_date,
        "issue_time": _stamp(issue),
        "mode": mode,
        "variant": variant,
        "model_version": bundle.version,
        "nwp_models_used": list(nwp),
        "max_nwp_init_time_used": audit["max_nwp_init_time_used"],
        "max_scada_time_used": _stamp(scada.loc[scada.index <= issue].index.max()),
        "latency_h": LATENCY_H,
        "capacity_mw": FARM_CAPACITY_MW,
        "widen": widen,
        "rows": rows,
        "summary": {
            "mean_p50": _optional_float(np.nanmean(p50)),
            "energy_p50_mwh": _optional_float(np.nansum(p50) * FARM_CAPACITY_MW),
            "max_p90": _optional_float(max(row["p90"] for row in rows)),
            "mean_band": _optional_float(np.nanmean(bands)),
            "dayahead_mean_p50": _optional_float(np.nanmean(p50[23:47])),
        },
        "flags": [],
    }
    result["flags"] = _risk_scan(result)
    return result


def risk_scan(forecast: dict) -> list[dict]:
    return _risk_scan(forecast)


def get_metrics(mode: Mode) -> dict:
    source = PATHS.outputs / "metrics" / f"{mode}.json"
    if not source.exists():
        raise FileNotFoundError(f"metrics not found: {source}. Run the relevant backtest first.")
    return json.loads(source.read_text(encoding="utf-8"))


def get_series(mode: Mode) -> list[dict]:
    directory = PATHS.outputs / "forecasts" / mode
    if not directory.exists():
        raise FileNotFoundError(f"forecast directory not found: {directory}")
    rows: list[dict] = []
    for source in sorted(directory.glob("*.json")):
        forecast = json.loads(source.read_text(encoding="utf-8"))
        rows.extend(row for row in forecast["rows"] if 24 <= row["lead_h"] <= 47)
    return rows


def forecast_diff(old: dict, new: dict) -> dict:
    old_rows = {row["target_time"]: row for row in old.get("rows", [])}
    new_rows = {row["target_time"]: row for row in new.get("rows", [])}
    shared = sorted(old_rows.keys() & new_rows.keys())
    differences = [abs(old_rows[key]["p50"] - new_rows[key]["p50"]) for key in shared]
    outside = sum(
        int(new_rows[key]["p50"] < old_rows[key]["p10"] or new_rows[key]["p50"] > old_rows[key]["p90"])
        for key in shared
    )
    return {
        "overlap_hours": len(shared),
        "mae": _optional_float(np.mean(differences)) if differences else None,
        "max_abs": _optional_float(max(differences)) if differences else None,
        "hours_outside_old_band": outside,
    }
