"""Honest benchmark forecasts used in validation and pitch metrics."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .power_curve import predict_power_curve


def persistence(scada: pd.DataFrame, issue_time: object, horizon: int = 48) -> np.ndarray:
    issue = pd.Timestamp(issue_time, tz="UTC") if pd.Timestamp(issue_time).tzinfo is None else pd.Timestamp(issue_time).tz_convert("UTC")
    prior = scada.loc[(scada.index <= issue) & scada["p"].notna(), "p"]
    if prior.empty:
        raise ValueError("persistence needs at least one SCADA value at or before issue time")
    return np.repeat(float(prior.iloc[-1]), horizon)


def climatology(scada: pd.DataFrame, issue_time: object, horizon: int = 48) -> np.ndarray:
    issue = pd.Timestamp(issue_time, tz="UTC") if pd.Timestamp(issue_time).tzinfo is None else pd.Timestamp(issue_time).tz_convert("UTC")
    history = scada.loc[(scada.index <= issue) & scada["p"].notna()].copy()
    local = history.index.tz_convert("Asia/Almaty")
    table = history.groupby([local.month, local.hour])["p"].mean()
    global_mean = float(history["p"].mean())
    targets = pd.date_range(issue + pd.Timedelta(hours=1), periods=horizon, freq="h")
    return np.asarray([table.get((target.tz_convert("Asia/Almaty").month, target.tz_convert("Asia/Almaty").hour), global_mean) for target in targets])


def raw_power_curve(curve: object, v_hub_mean: pd.Series) -> np.ndarray:
    return predict_power_curve(curve, v_hub_mean)
