"""Enforce a configured weather-offset policy and reject SCADA lookahead."""

from __future__ import annotations

import math
from numbers import Integral
from dataclasses import dataclass
from typing import Iterable, Mapping

import pandas as pd

from .config import LATENCY_H


AVAILABILITY_BASIS = "fixed_previous_runs_offset_plus_configured_latency"
AVAILABILITY_POLICY_VERSION = "previous-runs-offset-v1"
SOURCE_RELEASE_TIME_EVIDENCE = "not_provided_by_open_meteo_previous_runs_api"


def availability_policy_metadata(latency_h: int = LATENCY_H) -> dict[str, object]:
    """Describe the configured offset policy, not a provider release-time attestation."""
    return {
        "availability_basis": AVAILABILITY_BASIS,
        "availability_policy_version": AVAILABILITY_POLICY_VERSION,
        "source_release_time_verified": False,
        "source_release_time_evidence": SOURCE_RELEASE_TIME_EVIDENCE,
        "configured_latency_h": latency_h,
    }


def _require_integer(value: object, name: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral) or not minimum <= value <= maximum:
        raise ValueError(f"{name} must be an integer in {minimum}..{maximum}")
    return int(value)


def as_utc(value: object) -> pd.Timestamp:
    """Return a timezone-aware UTC timestamp."""
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        timestamp = timestamp.tz_localize("UTC")
    return timestamp.tz_convert("UTC")


def lead_day(lead_h: int, latency_h: int = LATENCY_H) -> int:
    """Choose the newest previous-run offset available under the latency assumption."""
    lead = _require_integer(lead_h, "lead_h", 1, 48)
    latency = _require_integer(latency_h, "latency_h", 0, 168)
    return _require_integer(math.ceil((lead + latency) / 24), "previous_day", 1, 7)


def est_init_time(target_time: object, previous_day: int) -> pd.Timestamp:
    """Offset-derived estimate; the provider does not supply a run timestamp here."""
    day = _require_integer(previous_day, "previous_day", 1, 7)
    return as_utc(target_time) - pd.Timedelta(hours=24 * day)


def available_at(target_time: object, previous_day: int, latency_h: int = LATENCY_H) -> pd.Timestamp:
    return est_init_time(target_time, previous_day) + pd.Timedelta(hours=latency_h)


@dataclass(frozen=True)
class TemporalAudit:
    max_nwp_init_time_used: str
    max_scada_time_used: str | None
    availability_basis: str
    availability_policy_version: str
    source_release_time_verified: bool
    source_release_time_evidence: str
    max_estimated_nwp_init_time_used: str
    configured_latency_h: int


def assert_no_lookahead(
    rows: pd.DataFrame | Iterable[dict], issue_time: object, latency_h: int = LATENCY_H,
    availability_metadata: Mapping[str, object] | None = None,
) -> TemporalAudit:
    """Raise when a selected offset violates the configured availability policy.

    This checks offset arithmetic, not the provider's actual publication time.
    """
    expected_metadata = availability_policy_metadata(latency_h)
    if availability_metadata is None:
        raise ValueError("availability metadata is required for the temporal audit")
    for key, expected in expected_metadata.items():
        if availability_metadata.get(key) != expected:
            raise ValueError(f"invalid or missing availability metadata: {key}")
    issue = as_utc(issue_time)
    frame = rows if isinstance(rows, pd.DataFrame) else pd.DataFrame(rows)
    if frame.empty:
        raise ValueError("cannot audit an empty weather selection")
    required = {"target_time", "lead_h", "lead_day"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"temporal audit needs columns: {sorted(missing)}")

    init_times: list[pd.Timestamp] = []
    for row in frame.loc[:, ["target_time", "lead_h", "lead_day"]].itertuples(index=False):
        target, lead, day = row
        lead = _require_integer(lead, "lead_h", 1, 48)
        day = _require_integer(day, "lead_day", 1, 7)
        if day != lead_day(lead, latency_h):
            raise ValueError(f"lead_day {day} does not match configured policy for lead_h {lead}")
        init = est_init_time(target, day)
        if init + pd.Timedelta(hours=latency_h) > issue:
            raise AssertionError(
                f"configured availability violation: target={as_utc(target).isoformat()}, previous_day={day}, "
                f"assumed_available_at={(init + pd.Timedelta(hours=latency_h)).isoformat()}, issue={issue.isoformat()}"
            )
        init_times.append(init)

    scada_max: str | None = None
    if "scada_time_used" in frame.columns:
        observed = pd.to_datetime(frame["scada_time_used"], utc=True, errors="coerce").dropna()
        if not observed.empty:
            max_scada = observed.max()
            if max_scada > issue:
                raise AssertionError(f"lookahead SCADA value: {max_scada.isoformat()} > {issue.isoformat()}")
            scada_max = max_scada.isoformat().replace("+00:00", "Z")

    estimated = max(init_times).isoformat().replace("+00:00", "Z")
    return TemporalAudit(
        max_nwp_init_time_used=estimated,
        max_scada_time_used=scada_max,
        max_estimated_nwp_init_time_used=estimated,
        **expected_metadata,
    )
