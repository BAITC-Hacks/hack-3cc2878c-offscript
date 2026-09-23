from __future__ import annotations

from samal_ml.api import get_meta, issue_time_for, list_issue_dates


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
