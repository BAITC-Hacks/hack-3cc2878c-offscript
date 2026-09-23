from __future__ import annotations

import numpy as np
import pandas as pd

from samal_ml.models import predict_bundle, train_bundle
from samal_ml.power_curve import fit_power_curve, predict_power_curve


def _sample_frames() -> tuple[pd.DataFrame, pd.DataFrame, pd.DatetimeIndex]:
    rng = np.random.default_rng(7)
    times = pd.date_range("2024-03-20", periods=900, freq="h", tz="UTC")
    wind = np.clip(8 + 4 * np.sin(np.arange(len(times)) / 20), 0.2, None)
    power = np.clip(((wind - 2) / 12) ** 2 + rng.normal(0, 0.03, len(wind)), 0, 1)
    scada = pd.DataFrame(
        {
            "wind_meas": wind,
            "p": power,
            "temp_c": 5.0,
            "flag_missing": False,
            "flag_stuck": False,
            "flag_outage": False,
        },
        index=times,
    )
    training = pd.DataFrame(
        {
            "target_time": times,
            "lead_h": 12,
            "lead_day": 1,
            "v_hub_mean": wind + rng.normal(0, 0.4, len(wind)),
            "temp_c": 5.0,
            "hour_sin": 0.0,
            "y": power,
            "wind_meas": wind,
            "flag_missing": False,
            "flag_stuck": False,
            "flag_outage": False,
            "flag_icing_suspect": False,
        }
    )
    return scada, training, times


def test_quantile_bundle_fit_and_predict_are_ordered() -> None:
    scada, training, times = _sample_frames()
    bundle = train_bundle(scada, training, times[-1], "unit")
    predicted = predict_bundle(bundle, training.drop(columns=["y", "wind_meas", "flag_missing", "flag_stuck", "flag_outage", "flag_icing_suspect"]).tail(48))
    assert len(predicted) == 48
    assert ((predicted["p10"] <= predicted["p50"]) & (predicted["p50"] <= predicted["p90"])).all()
    assert predicted[["p10", "p50", "p90"]].ge(0).all().all()
    assert predicted[["p10", "p50", "p90"]].le(1).all().all()
    raw_median = bundle.quantiles[0.5].predict(predicted[bundle.feature_list])
    expected = 0.5 * (raw_median + predicted["pc_mos"].to_numpy()) * bundle.availability_factor
    np.testing.assert_allclose(predicted["p50"], np.clip(expected, predicted["p10"], predicted["p90"]))


def test_availability_uses_flagged_calibration_hours_and_legacy_bundle_loads() -> None:
    scada, training, times = _sample_frames()
    training.loc[training.index[-50:], "flag_outage"] = True
    bundle = train_bundle(scada, training, times[-1], "unit")
    assert 0 < bundle.availability_factor < 1
    del bundle.availability_factor
    predicted = predict_bundle(bundle, training.drop(columns=[
        "y", "wind_meas", "flag_missing", "flag_stuck", "flag_outage", "flag_icing_suspect"
    ]).tail(4))
    assert predicted[["p10", "p50", "p90"]].notna().all().all()


def test_future_scada_cannot_change_fitted_power_curve() -> None:
    scada, training, times = _sample_frames()
    future = pd.DataFrame(
        {
            "wind_meas": 8.0,
            "p": 0.0,
            "temp_c": 5.0,
            "flag_missing": False,
            "flag_stuck": False,
            "flag_outage": False,
        },
        index=pd.date_range(times[-1] + pd.Timedelta(hours=1), periods=300, freq="h", tz="UTC"),
    )
    contaminated = pd.concat([scada, future])
    winds = np.array([4.0, 8.0, 12.0])
    # Ensure these future observations are strong enough that the test would
    # detect the original full-history power-curve leak.
    assert np.max(np.abs(
        predict_power_curve(fit_power_curve(scada), winds)
        - predict_power_curve(fit_power_curve(contaminated), winds)
    )) > 0.05
    clean_bundle = train_bundle(scada, training, times[-1], "unit")
    contaminated_bundle = train_bundle(contaminated, training, times[-1], "unit")
    np.testing.assert_allclose(
        predict_power_curve(clean_bundle.power_curve, winds),
        predict_power_curve(contaminated_bundle.power_curve, winds),
    )
