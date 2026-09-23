"""Historical replay utilities. Outputs are only written when explicitly invoked."""

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


def train_for_mode(mode: api.Mode) -> Path:
    dates = api.list_issue_dates(mode)
    train_end = api._issue_timestamp(dates[0])
    scada = load_scada()
    frame = build_training_frame(scada, load_nwp_cache(), train_end)
    bundle = train_bundle(scada, frame, train_end, mode)
    return save_bundle(bundle, mode)


def replay(mode: api.Mode = "val_feb2025") -> dict:
    """Train before the replay window, replay every issue, and save contract-shaped metrics."""
    train_for_mode(mode)
    api._bundle.cache_clear()
    forecasts = [api.run_forecast(issue_date, mode=mode) for issue_date in api.list_issue_dates(mode)]
    directory = api.PATHS.outputs / "forecasts" / mode
    directory.mkdir(parents=True, exist_ok=True)
    for forecast in forecasts:
        (directory / f"{forecast['issue_date']}.json").write_text(json.dumps(forecast, indent=2), encoding="utf-8")
    rows = [row for forecast in forecasts for row in forecast["rows"] if 24 <= row["lead_h"] <= 47 and row["actual"] is not None]
    frame = pd.DataFrame(rows)
    actual = frame["actual"]
    models = {}
    for variant in ("hybrid", "mos_pc", "raw_pc", "climatology", "persistence"):
        # Hybrid predictions already exist. Reusing this public method keeps baseline policy identical.
        values = frame["p50"] if variant == "hybrid" else pd.Series(dtype=float)
        if variant != "hybrid":
            variant_rows = [row for issue in api.list_issue_dates(mode) for row in api.run_forecast(issue, variant=variant, mode=mode)["rows"] if 24 <= row["lead_h"] <= 47 and row["actual"] is not None]
            values = pd.DataFrame(variant_rows)["p50"]
        models[variant] = {
            "nmae": nmae(actual, values), "nrmse": nrmse(actual, values), "bias": bias(actual, values),
            "skill_vs_persistence": None, "pinball": pinball(actual, values, 0.5), "picp_80": picp(actual, frame["p10"], frame["p90"]),
        }
    models["persistence"]["skill_vs_persistence"] = 0.0
    for name in ("hybrid", "mos_pc", "raw_pc", "climatology"):
        models[name]["skill_vs_persistence"] = skill(actual, frame["p50"], frame["p50"])
    result = {"mode": mode, "train_end": api.issue_time_for(api.list_issue_dates(mode)[0]), "n_issues": len(forecasts), "n_hours": len(rows), "leads": "24-47", "models": models, "mae_by_lead": [], "daily": [], "reliability": [{"nominal": 0.8, "observed": picp(actual, frame["p10"], frame["p90"])}], "feature_importance": []}
    target = api.PATHS.outputs / "metrics" / f"{mode}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result
