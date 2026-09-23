from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from samal_ml.temporal_guard import assert_no_lookahead, available_at, lead_day


def test_lead_day_is_safe_for_random_issue_leads() -> None:
    issue = pd.Timestamp("2025-02-14T19:00:00Z")
    for lead in np.random.default_rng(42).integers(1, 49, size=1000):
        target = issue + pd.Timedelta(hours=int(lead))
        assert available_at(target, lead_day(int(lead))) <= issue


def test_previous_day_zero_is_refused() -> None:
    with pytest.raises(ValueError):
        available_at("2025-02-15T00:00:00Z", 0)


def test_future_scada_is_refused() -> None:
    issue = pd.Timestamp("2025-02-14T19:00:00Z")
    rows = pd.DataFrame({"target_time": [issue + pd.Timedelta(hours=1)], "lead_day": [1], "scada_time_used": [issue + pd.Timedelta(seconds=1)]})
    with pytest.raises(AssertionError, match="SCADA"):
        assert_no_lookahead(rows, issue)
