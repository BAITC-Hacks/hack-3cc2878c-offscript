from __future__ import annotations

import pandas as pd

from samal_ml.api import get_meta, issue_time_for, list_issue_dates
from samal_ml.features import input_fingerprints_by_target


def test_meta_matches_public_contract_basics() -> None:
    meta = get_meta()
    assert meta["farm"]["tz"] == "Asia/Almaty"
    assert meta["variants"] == ["hybrid", "mos_pc", "raw_pc", "climatology", "persistence"]
    assert meta["temporal_guard"]["latency_h"] == 8


def test_test_replay_window_and_issue_time() -> None:
    dates = list_issue_dates("test")
    assert len(dates) == 28
    assert dates[0] == "2026-01-31"
    assert issue_time_for(dates[0]) == "2026-01-30T19:00:00Z"


def test_overlap_input_fingerprint_ignores_lead_hour_but_records_new_offset() -> None:
    target = pd.Timestamp("2026-02-15T02:00:00Z")
    prior = pd.DataFrame([{"target_time": target, "lead_h": 31, "lead_day": 2, "wind_speed": 8.4}])
    same_input = pd.DataFrame([{"target_time": target, "lead_h": 7, "lead_day": 2, "wind_speed": 8.4}])
    newer_offset = pd.DataFrame([{"target_time": target, "lead_h": 7, "lead_day": 1, "wind_speed": 8.4}])
    assert input_fingerprints_by_target(prior) == input_fingerprints_by_target(same_input)
    assert input_fingerprints_by_target(prior) != input_fingerprints_by_target(newer_offset)
