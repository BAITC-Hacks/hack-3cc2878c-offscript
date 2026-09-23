"""Monotonic empirical wind-to-power curve."""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression


def fit_power_curve(scada: pd.DataFrame) -> IsotonicRegression:
    clean = scada.loc[
        ~scada[["flag_missing", "flag_stuck", "flag_outage"]].any(axis=1), ["wind_meas", "p"]
    ].dropna()
    if len(clean) < 100:
        raise ValueError("at least 100 clean SCADA hours are required for a power curve")
    return IsotonicRegression(increasing=True, out_of_bounds="clip", y_min=0.0, y_max=1.0).fit(
        clean["wind_meas"], clean["p"]
    )


def predict_power_curve(curve: IsotonicRegression, wind_ms: pd.Series | np.ndarray) -> np.ndarray:
    values = np.asarray(wind_ms, dtype=float)
    result = np.full(values.shape, np.nan, dtype=float)
    valid = np.isfinite(values)
    result[valid] = curve.predict(values[valid])
    return np.clip(result, 0.0, 1.0)
