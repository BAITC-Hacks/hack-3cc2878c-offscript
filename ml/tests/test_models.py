from __future__ import annotations

import numpy as np
import pandas as pd

from samal_ml.models import predict_bundle, train_bundle


def test_quantile_bundle_fit_and_predict_are_ordered() -> None:
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
    bundle = train_bundle(scada, training, times[-1], "unit")
    predicted = predict_bundle(bundle, training.drop(columns=["y", "wind_meas", "flag_missing", "flag_stuck", "flag_outage", "flag_icing_suspect"]).tail(48))
    assert len(predicted) == 48
    assert ((predicted["p10"] <= predicted["p50"]) & (predicted["p50"] <= predicted["p90"])).all()
    assert predicted[["p10", "p50", "p90"]].ge(0).all().all()
    assert predicted[["p10", "p50", "p90"]].le(1).all().all()
