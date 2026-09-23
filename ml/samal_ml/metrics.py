"""Metrics for bounded normalized power forecasts."""

from __future__ import annotations

import numpy as np
import pandas as pd


def _arrays(actual: object, predicted: object) -> tuple[np.ndarray, np.ndarray]:
    y = np.asarray(actual, dtype=float)
    p = np.asarray(predicted, dtype=float)
    valid = np.isfinite(y) & np.isfinite(p)
    return y[valid], p[valid]


def nmae(actual: object, predicted: object) -> float:
    y, p = _arrays(actual, predicted)
    return float(np.mean(np.abs(y - p))) if len(y) else float("nan")


def nrmse(actual: object, predicted: object) -> float:
    y, p = _arrays(actual, predicted)
    return float(np.sqrt(np.mean((y - p) ** 2))) if len(y) else float("nan")


def bias(actual: object, predicted: object) -> float:
    y, p = _arrays(actual, predicted)
    return float(np.mean(p - y)) if len(y) else float("nan")


def skill(actual: object, predicted: object, baseline: object) -> float:
    base = nmae(actual, baseline)
    return float("nan") if not np.isfinite(base) or base == 0 else float(1 - nmae(actual, predicted) / base)


def pinball(actual: object, predicted: object, quantile: float) -> float:
    y, p = _arrays(actual, predicted)
    error = y - p
    return float(np.mean(np.maximum(quantile * error, (quantile - 1) * error))) if len(y) else float("nan")


def picp(actual: object, p10: object, p90: object) -> float:
    y = np.asarray(actual, dtype=float)
    low, high = np.asarray(p10, dtype=float), np.asarray(p90, dtype=float)
    valid = np.isfinite(y) & np.isfinite(low) & np.isfinite(high)
    return float(np.mean((y[valid] >= low[valid]) & (y[valid] <= high[valid]))) if valid.any() else float("nan")


def daily(frame: pd.DataFrame, actual: str = "actual", predicted: str = "p50") -> list[dict]:
    copied = frame.copy()
    copied["date"] = pd.to_datetime(copied["target_time"], utc=True).dt.date.astype(str)
    return [{"date": date, "hybrid": nmae(group[actual], group[predicted])} for date, group in copied.groupby("date")]
