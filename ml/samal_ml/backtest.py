"""Leakage-safe historical replay, honest validation metrics, and submission files."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import api
from .data import load_scada
from .features import build_training_frame
from .metrics import bias, nmae, nrmse, picp, pinball, skill
from .models import save_bundle, train_bundle
from .weather import load_nwp_cache


VARIANTS = ("hybrid", "mos_pc", "raw_pc", "climatology", "persistence")
SUBMISSION_COLUMNS = (
    "target_time_local", "target_time_utc", "issue_time_utc", "lead_h", "p10", "p50", "p90", "p50_mw"
)


def train_for_mode(mode: api.Mode) -> Path:
    dates = api.list_issue_dates(mode)
    train_end = api._issue_timestamp(dates[0])
    scada = load_scada().loc[lambda frame: frame.index <= train_end]
    frame = build_training_frame(scada, load_nwp_cache(), train_end)
    bundle = train_bundle(scada, frame, train_end, mode)
    return save_bundle(bundle, mode)


def _save_forecasts(mode: api.Mode, forecasts: list[dict]) -> None:
    directory = api.PATHS.outputs / "forecasts" / mode
    directory.mkdir(parents=True, exist_ok=True)
    for forecast in forecasts:
        (directory / f"{forecast['issue_date']}.json").write_text(
            json.dumps(forecast, indent=2, ensure_ascii=False), encoding="utf-8"
        )


def _submission_row(forecast: dict, row: dict) -> dict:
    return {
        "target_time_local": row["target_time_local"],
        "target_time_utc": row["target_time"],
        "issue_time_utc": forecast["issue_time"],
        "lead_h": row["lead_h"],
        "p10": row["p10"],
        "p50": row["p50"],
        "p90": row["p90"],
        "p50_mw": round(row["p50"] * forecast["capacity_mw"], 6),
    }


def _save_submission(forecasts: list[dict]) -> dict:
    directory = api.PATHS.outputs / "submission"
    directory.mkdir(parents=True, exist_ok=True)
    all_rows = [_submission_row(forecast, row) for forecast in forecasts for row in forecast["rows"]]
    day_ahead = [row for row in all_rows if 24 <= row["lead_h"] <= 47]
    all_path = directory / "forecast_feb2026_all_issues.csv"
    day_path = directory / "forecast_feb2026_dayahead.csv"
    pd.DataFrame(all_rows, columns=SUBMISSION_COLUMNS).to_csv(all_path, index=False)
    pd.DataFrame(day_ahead, columns=SUBMISSION_COLUMNS).to_csv(day_path, index=False)
    if len(forecasts) != 28 or len(all_rows) != 28 * 48 or len(day_ahead) != 28 * 24:
        raise AssertionError("February replay has an incomplete issue or day-ahead schedule")
    return {
        "mode": "test", "n_issues": len(forecasts), "n_rows_all": len(all_rows),
        "n_rows_dayahead": len(day_ahead),
        "submission_files": [str(day_path), str(all_path)],
    }


def _rows(forecasts: list[dict], day_ahead_only: bool = False) -> pd.DataFrame:
    rows = [row for forecast in forecasts for row in forecast["rows"]
            if not day_ahead_only or 24 <= row["lead_h"] <= 47]
    return pd.DataFrame(rows).sort_values("target_time").reset_index(drop=True)


def _reliability(frame: pd.DataFrame) -> list[dict]:
    """Interpolate available P10/P50/P90 quantiles to inspect narrower bands."""
    observed = []
    for nominal in (0.2, 0.5, 0.8):
        fraction = (0.8 - nominal) / 0.8
        lower = frame["p10"] + fraction * (frame["p50"] - frame["p10"])
        upper = frame["p90"] - fraction * (frame["p90"] - frame["p50"])
        observed.append({"nominal": nominal, "observed": picp(frame["actual"], lower, upper)})
    return observed


def replay(mode: api.Mode = "val_feb2025") -> dict:
    """Train before the window and replay every historical issue without test actuals."""
    train_for_mode(mode)
    api._bundle.cache_clear()
    dates = api.list_issue_dates(mode)
    forecasts = [api.run_forecast(issue_date, mode=mode) for issue_date in dates]
    _save_forecasts(mode, forecasts)
    if mode == "test":
        return _save_submission(forecasts)

    by_variant = {"hybrid": forecasts}
    for variant in VARIANTS[1:]:
        by_variant[variant] = [api.run_forecast(issue_date, variant=variant, mode=mode) for issue_date in dates]
    all_frames = {variant: _rows(items) for variant, items in by_variant.items()}
    day_frames = {variant: _rows(items, day_ahead_only=True) for variant, items in by_variant.items()}
    targets = day_frames["hybrid"]["target_time"].tolist()
    if any(frame["target_time"].tolist() != targets for frame in day_frames.values()):
        raise AssertionError("baseline and hybrid day-ahead timestamps differ")

    actual = day_frames["hybrid"]["actual"]
    persistence = day_frames["persistence"]["p50"]
    models = {}
    for variant, frame in day_frames.items():
        predicted = frame["p50"]
        models[variant] = {
            "nmae": nmae(actual, predicted),
            "nrmse": nrmse(actual, predicted),
            "bias": bias(actual, predicted),
            "skill_vs_persistence": skill(actual, predicted, persistence),
            "pinball": float(np.mean([pinball(actual, frame[column], quantile)
                                     for column, quantile in (("p10", 0.1), ("p50", 0.5), ("p90", 0.9))])),
            "picp_80": picp(actual, frame["p10"], frame["p90"]),
        }

    mae_by_lead = []
    for lead_h in range(1, 49):
        mask = all_frames["hybrid"]["lead_h"] == lead_h
        values = all_frames["hybrid"].loc[mask, "actual"]
        mae_by_lead.append({
            "lead_h": lead_h,
            "hybrid": nmae(values, all_frames["hybrid"].loc[mask, "p50"]),
            "persistence": nmae(values, all_frames["persistence"].loc[mask, "p50"]),
            "raw_pc": nmae(values, all_frames["raw_pc"].loc[mask, "p50"]),
        })

    daily_frame = day_frames["hybrid"][["target_time", "actual", "p50"]].copy()
    daily_frame["persistence"] = persistence
    daily_frame["date"] = pd.to_datetime(daily_frame["target_time"], utc=True).dt.tz_convert("Asia/Almaty").dt.date.astype(str)
    daily = [{"date": date, "hybrid": nmae(group["actual"], group["p50"]),
              "persistence": nmae(group["actual"], group["persistence"])}
             for date, group in daily_frame.groupby("date", sort=True)]

    result = {
        "mode": mode,
        "train_end": api.issue_time_for(dates[0]),
        "n_issues": len(forecasts),
        "n_hours": int(actual.notna().sum()),
        "leads": "24-47",
        "models": models,
        "mae_by_lead": mae_by_lead,
        "daily": daily,
        "reliability": _reliability(day_frames["hybrid"]),
        "feature_importance": [],
    }
    target = api.PATHS.outputs / "metrics" / f"{mode}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
    return result
