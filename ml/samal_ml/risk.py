"""Rule-based forecast risk flags consumed by the agent and frontend."""

from __future__ import annotations

import pandas as pd

from .config import RISK_THRESHOLDS


def _stamp(value: object) -> str:
    return pd.Timestamp(value).tz_convert("UTC").isoformat().replace("+00:00", "Z")


def risk_scan(forecast: dict) -> list[dict]:
    rows = pd.DataFrame(forecast.get("rows", []))
    if rows.empty:
        return []
    rows["target_time"] = pd.to_datetime(rows["target_time"], utc=True)
    flags: list[dict] = []
    changes = rows["p50"].diff(3)
    for index, change in changes.items():
        if pd.notna(change) and abs(change) >= RISK_THRESHOLDS["ramp"]:
            code = "RAMP_UP" if change > 0 else "RAMP_DOWN"
            flags.append({"code": code, "severity": "warn", "start": _stamp(rows.loc[index, "target_time"]), "end": _stamp(rows.loc[index, "target_time"]), "value": round(float(change), 4), "message": f"{code.replace('_', '-').title()} of {abs(change):.0%} capacity within 3 h"})
    for _, row in rows.iterrows():
        time = _stamp(row["target_time"])
        band = row["p90"] - row["p10"]
        if pd.notna(band) and band >= RISK_THRESHOLDS["wide_band"]:
            flags.append({"code": "LOW_CONFIDENCE", "severity": "warn", "start": time, "end": time, "value": round(float(band), 4), "message": "Prediction interval is wider than 50% of capacity"})
        if pd.notna(row.get("v_hub_spread")) and row["v_hub_spread"] >= RISK_THRESHOLDS["disagreement_ms"]:
            flags.append({"code": "MODEL_DISAGREEMENT", "severity": "warn", "start": time, "end": time, "value": round(float(row["v_hub_spread"]), 3), "message": "Weather models disagree on hub-height wind"})
        if pd.notna(row.get("v_hub_mean")) and row["v_hub_mean"] >= RISK_THRESHOLDS["cut_out_ms"]:
            flags.append({"code": "CUT_OUT", "severity": "critical", "start": time, "end": time, "value": round(float(row["v_hub_mean"]), 3), "message": "Hub-height wind is at or above the cut-out threshold"})
        if pd.notna(row.get("temp_c")) and pd.notna(row.get("rh_mean")) and row["temp_c"] <= 1 and row["rh_mean"] >= 90 and row.get("v_hub_mean", 0) >= 3:
            flags.append({"code": "ICING", "severity": "warn", "start": time, "end": time, "value": round(float(row["temp_c"]), 2), "message": "Cold, humid wind conditions may increase icing risk"})
    return flags
