"""Physics-informed MOS and probabilistic gradient-boosting models."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

from .config import PATHS
from .power_curve import fit_power_curve, predict_power_curve


NON_FEATURES = {
    "target_time", "y", "wind_meas", "flag_missing", "flag_stuck", "flag_outage", "flag_icing_suspect"
}


@dataclass
class ModelBundle:
    power_curve: object
    mos: HistGradientBoostingRegressor
    mos_feature_list: list[str]
    quantiles: dict[float, HistGradientBoostingRegressor]
    qhat: float
    feature_list: list[str]
    train_end: str
    version: str


def _feature_list(frame: pd.DataFrame) -> list[str]:
    return [column for column in frame.columns if column not in NON_FEATURES and pd.api.types.is_numeric_dtype(frame[column])]


def _fit_hgb(**kwargs: object) -> HistGradientBoostingRegressor:
    return HistGradientBoostingRegressor(
        max_iter=300,
        learning_rate=0.05,
        max_leaf_nodes=31,
        min_samples_leaf=40,
        l2_regularization=1.0,
        random_state=42,
        **kwargs,
    )


def train_bundle(scada: pd.DataFrame, training: pd.DataFrame, train_end: object, mode: str) -> ModelBundle:
    """Fit a power curve, MOS wind correction, quantile models, and CQR margin."""
    end = pd.Timestamp(train_end)
    end = end.tz_localize("UTC") if end.tzinfo is None else end.tz_convert("UTC")
    # The caller may have loaded all SCADA history; never let later observations
    # influence either the empirical curve or the forecast model.
    scada = scada.loc[scada.index <= end]
    training = training.loc[pd.to_datetime(training["target_time"], utc=True) <= end]
    if training.empty:
        raise ValueError("no training rows: fetch the archived NWP cache before training")
    clean = training.loc[
        ~training[["flag_missing", "flag_stuck", "flag_outage"]].any(axis=1) & training["v_hub_mean"].notna()
    ].copy()
    if len(clean) < 500:
        raise ValueError(f"only {len(clean)} valid NWP/SCADA rows; at least 500 are required")
    clean["target_time"] = pd.to_datetime(clean["target_time"], utc=True)
    calibration_start = clean["target_time"].max() - pd.Timedelta(days=56)
    fit_rows = clean.loc[clean["target_time"] < calibration_start].copy()
    calibration = clean.loc[clean["target_time"] >= calibration_start].copy()
    if len(fit_rows) < 500 or len(calibration) < 100:
        cutoff = int(len(clean) * 0.8)
        fit_rows, calibration = clean.iloc[:cutoff].copy(), clean.iloc[cutoff:].copy()

    power_curve = fit_power_curve(scada)
    mos_feature_list = _feature_list(fit_rows)
    mos = _fit_hgb().fit(fit_rows[mos_feature_list], fit_rows["wind_meas"])
    for frame in (fit_rows, calibration):
        frame["pc_raw"] = predict_power_curve(power_curve, frame["v_hub_mean"])
        frame["pc_mos"] = predict_power_curve(power_curve, mos.predict(frame[mos_feature_list]))
    feature_list = _feature_list(fit_rows)
    quantiles = {
        quantile: _fit_hgb(loss="quantile", quantile=quantile).fit(fit_rows[feature_list], fit_rows["y"])
        for quantile in (0.1, 0.5, 0.9)
    }
    validation_predictions = np.column_stack([quantiles[q].predict(calibration[feature_list]) for q in (0.1, 0.9)])
    errors = np.maximum(validation_predictions[:, 0] - calibration["y"], calibration["y"] - validation_predictions[:, 1])
    qhat = float(max(0.0, np.quantile(errors, min(1.0, 0.8 * (1 + 1 / len(errors))), method="higher")))
    return ModelBundle(
        power_curve=power_curve,
        mos=mos,
        mos_feature_list=mos_feature_list,
        quantiles=quantiles,
        qhat=qhat,
        feature_list=feature_list,
        train_end=end.isoformat().replace("+00:00", "Z"),
        version=f"hybrid-qhgb-train{end.date().isoformat()}-{mode}",
    )


def predict_bundle(bundle: ModelBundle, features: pd.DataFrame, widen: float = 0.0) -> pd.DataFrame:
    """Produce ordered and clipped P10/P50/P90 forecasts from a fitted bundle."""
    result = features.copy()
    missing = set(bundle.mos_feature_list).difference(result.columns)
    if missing:
        raise ValueError(f"forecast MOS features are incompatible with model: missing {sorted(missing)}")
    base_features = result[bundle.mos_feature_list].copy()
    result["mos_wind"] = bundle.mos.predict(base_features)
    result["pc_raw"] = predict_power_curve(bundle.power_curve, result["v_hub_mean"])
    result["pc_mos"] = predict_power_curve(bundle.power_curve, result["mos_wind"])
    missing = set(bundle.feature_list).difference(result.columns)
    if missing:
        raise ValueError(f"forecast quantile features are incompatible with model: missing {sorted(missing)}")
    model_features = result[bundle.feature_list]
    predicted = np.column_stack([bundle.quantiles[q].predict(model_features) for q in (0.1, 0.5, 0.9)])
    predicted.sort(axis=1)
    predicted[:, 0] -= bundle.qhat + widen
    predicted[:, 2] += bundle.qhat + widen
    predicted = np.clip(predicted, 0.0, 1.0)
    predicted.sort(axis=1)
    result[["p10", "p50", "p90"]] = predicted
    return result


def save_bundle(bundle: ModelBundle, mode: str, path: Path | None = None) -> Path:
    destination = path or PATHS.models / f"{mode}.joblib"
    destination.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, destination)
    return destination


def load_bundle(mode: str, path: Path | None = None) -> ModelBundle:
    source = path or PATHS.models / f"{mode}.joblib"
    if not source.exists():
        raise FileNotFoundError(f"model bundle not found: {source}. Run `python -m samal_ml.cli train --mode {mode}` first.")
    return joblib.load(source)
