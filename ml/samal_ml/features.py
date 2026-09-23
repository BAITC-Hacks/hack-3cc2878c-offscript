"""Feature generation from archived NWP selections only."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping

import numpy as np
import pandas as pd

from .config import HUB_HEIGHT_M, NWP_VARIABLES, TZ_NAME
from .temporal_guard import assert_no_lookahead, lead_day


def _pick_column(frame: pd.DataFrame, variable: str, day: int) -> str | None:
    prefix = f"{variable}_previous_day{day}"
    return next((column for column in frame.columns if column == prefix or column.startswith(prefix + "_")), None)


def _single_row(
    target_time: pd.Timestamp,
    lead_h: int,
    nwp: Mapping[str, pd.DataFrame],
) -> dict:
    target = pd.Timestamp(target_time)
    if target.tzinfo is None:
        target = target.tz_localize("UTC")
    target = target.tz_convert("UTC")
    day = lead_day(lead_h)
    row: dict[str, object] = {"target_time": target, "lead_h": lead_h, "lead_day": day}
    hub_winds: list[float] = []
    temperatures: list[float] = []
    humidities: list[float] = []

    for model, frame in nwp.items():
        source = frame.loc[target] if target in frame.index else pd.Series(dtype=float)
        if isinstance(source, pd.DataFrame):
            source = source.iloc[-1]
        values: dict[str, float] = {}
        for variable in NWP_VARIABLES:
            column = _pick_column(frame, variable, day)
            value = np.nan if column is None or source.empty else source.get(column, np.nan)
            values[variable] = pd.to_numeric(value, errors="coerce")
            row[f"{model}_{variable}"] = values[variable]
        ws10 = values["wind_speed_10m"]
        ws100 = values["wind_speed_100m"]
        alpha = np.clip(np.log(np.maximum(ws100, 0.1) / np.maximum(ws10, 0.1)) / np.log(10), -0.2, 0.8)
        v_hub = ws100 * (HUB_HEIGHT_M / 100.0) ** alpha
        pressure_pa = values["surface_pressure"] * 100.0
        density = pressure_pa / (287.05 * (values["temperature_2m"] + 273.15))
        v_eq = v_hub * (density / 1.225) ** (1 / 3)
        direction = np.deg2rad(values["wind_direction_100m"])
        row.update(
            {
                f"{model}_alpha": alpha,
                f"{model}_v_hub": v_hub,
                f"{model}_v_eq": v_eq,
                f"{model}_wd100_sin": np.sin(direction),
                f"{model}_wd100_cos": np.cos(direction),
            }
        )
        if np.isfinite(v_hub):
            hub_winds.append(float(v_hub))
        if np.isfinite(values["temperature_2m"]):
            temperatures.append(float(values["temperature_2m"]))
        if np.isfinite(values["relative_humidity_2m"]):
            humidities.append(float(values["relative_humidity_2m"]))

    local = target.tz_convert(TZ_NAME)
    row.update(
        {
            "v_hub_mean": float(np.mean(hub_winds)) if hub_winds else np.nan,
            "v_hub_median": float(np.median(hub_winds)) if hub_winds else np.nan,
            "v_hub_spread": float(np.std(hub_winds)) if hub_winds else np.nan,
            "v_hub_min": float(np.min(hub_winds)) if hub_winds else np.nan,
            "v_hub_max": float(np.max(hub_winds)) if hub_winds else np.nan,
            "temp_c": float(np.mean(temperatures)) if temperatures else np.nan,
            "rh_mean": float(np.mean(humidities)) if humidities else np.nan,
            "hour_sin": np.sin(2 * np.pi * local.hour / 24),
            "hour_cos": np.cos(2 * np.pi * local.hour / 24),
            "doy_sin": np.sin(2 * np.pi * local.dayofyear / 366),
            "doy_cos": np.cos(2 * np.pi * local.dayofyear / 366),
        }
    )
    return row


def build_issue_frame(issue_time: object, nwp: Mapping[str, pd.DataFrame]) -> tuple[pd.DataFrame, dict]:
    """Build 48 rows for one issue, selecting only weather available at issue time."""
    issue = pd.Timestamp(issue_time)
    if issue.tzinfo is None:
        issue = issue.tz_localize("UTC")
    issue = issue.tz_convert("UTC")
    rows = [_single_row(issue + pd.Timedelta(hours=lead), lead, nwp) for lead in range(1, 49)]
    frame = pd.DataFrame(rows)
    audit = assert_no_lookahead(frame, issue)
    return frame, audit.__dict__


def build_training_frame(
    scada: pd.DataFrame,
    nwp: Mapping[str, pd.DataFrame],
    train_end: object | None = None,
) -> pd.DataFrame:
    """Create history with the identical lead-day distribution used at prediction time."""
    history = scada.copy()
    if train_end is not None:
        end = pd.Timestamp(train_end)
        end = end.tz_localize("UTC") if end.tzinfo is None else end.tz_convert("UTC")
        history = history.loc[history.index <= end]
    rows: list[dict] = []
    representative_leads = (12, 28, 44)
    for target, observation in history.dropna(subset=["p", "wind_meas"]).iterrows():
        for lead in representative_leads:
            item = _single_row(target, lead, nwp)
            # Training target itself can be historical, but issue-time eligibility stays identical.
            assert_no_lookahead(pd.DataFrame([item]), target - pd.Timedelta(hours=lead))
            item.update(
                {
                    "y": float(observation["p"]),
                    "wind_meas": float(observation["wind_meas"]),
                    "flag_missing": bool(observation["flag_missing"]),
                    "flag_stuck": bool(observation["flag_stuck"]),
                    "flag_outage": bool(observation["flag_outage"]),
                    "flag_icing_suspect": bool(observation["flag_icing_suspect"]),
                }
            )
            rows.append(item)
    return pd.DataFrame(rows)


def input_sha256(frame: pd.DataFrame) -> str:
    """Stable digest for the exact selected NWP inputs recorded with a forecast."""
    normalized = frame.copy()
    normalized["target_time"] = pd.to_datetime(normalized["target_time"], utc=True).astype(str)
    payload = normalized.replace({np.nan: None}).to_dict(orient="records")
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()
