from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from openwind_ml.temporal_guard import (
    AVAILABILITY_POLICY_VERSION, assert_no_lookahead, availability_policy_metadata,
    available_at, lead_day,
)


def test_lead_day_is_safe_for_random_issue_leads() -> None:
    issue = pd.Timestamp("2025-02-14T19:00:00Z")
    for lead in np.random.default_rng(42).integers(1, 49, size=1000):
        target = issue + pd.Timedelta(hours=int(lead))
        assert available_at(target, lead_day(int(lead))) <= issue


def test_previous_day_zero_is_refused() -> None:
    with pytest.raises(ValueError):
        available_at("2025-02-15T00:00:00Z", 0)


@pytest.mark.parametrize(("lead", "expected_day"), [(1, 1), (16, 1), (17, 2), (40, 2), (41, 3), (48, 3)])
def test_boundary_leads_record_offset_policy(lead: int, expected_day: int) -> None:
    issue = pd.Timestamp("2025-02-14T19:00:00Z")
    target = issue + pd.Timedelta(hours=lead)
    assert lead_day(lead) == expected_day
    audit = assert_no_lookahead(
        [{"target_time": target, "lead_h": lead, "lead_day": expected_day}], issue,
        availability_metadata=availability_policy_metadata(),
    )
    assert audit.availability_policy_version == AVAILABILITY_POLICY_VERSION
    assert audit.source_release_time_verified is False
    assert audit.max_estimated_nwp_init_time_used == audit.max_nwp_init_time_used


@pytest.mark.parametrize("lead", [0, 49, 1.5, "17", True])
def test_invalid_lead_hour_is_rejected(lead: object) -> None:
    with pytest.raises(ValueError, match="lead_h"):
        lead_day(lead)


@pytest.mark.parametrize("day", [0, 8, 1.5, "2", True])
def test_invalid_previous_day_is_rejected(day: object) -> None:
    with pytest.raises(ValueError, match="previous_day"):
        available_at("2025-02-15T00:00:00Z", day)


def test_missing_or_unverified_source_evidence_is_rejected() -> None:
    issue = pd.Timestamp("2025-02-14T19:00:00Z")
    rows = [{"target_time": issue + pd.Timedelta(hours=1), "lead_h": 1, "lead_day": 1}]
    with pytest.raises(ValueError, match="availability metadata"):
        assert_no_lookahead(rows, issue)
    claimed = availability_policy_metadata()
    claimed["source_release_time_verified"] = True
    with pytest.raises(ValueError, match="source_release_time_verified"):
        assert_no_lookahead(rows, issue, availability_metadata=claimed)
    with pytest.raises(ValueError, match="lead_day"):
        assert_no_lookahead([rows[0] | {"lead_day": 1.0}], issue,
                            availability_metadata=availability_policy_metadata())


def test_future_scada_is_refused() -> None:
    issue = pd.Timestamp("2025-02-14T19:00:00Z")
    rows = pd.DataFrame({"target_time": [issue + pd.Timedelta(hours=1)], "lead_h": [1],
                         "lead_day": [1], "scada_time_used": [issue + pd.Timedelta(seconds=1)]})
    with pytest.raises(AssertionError, match="SCADA"):
        assert_no_lookahead(rows, issue, availability_metadata=availability_policy_metadata())
