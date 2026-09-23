"""Formal availability checks that prevent weather and SCADA lookahead."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable

import pandas as pd

from .config import LATENCY_H


def as_utc(value: object) -> pd.Timestamp:
    """Return a timezone-aware UTC timestamp."""
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        timestamp = timestamp.tz_localize("UTC")
    return timestamp.tz_convert("UTC")


def lead_day(lead_h: int, latency_h: int = LATENCY_H) -> int:
    """Choose the newest previous-run product provably available at issue time."""
    if lead_h < 1:
        raise ValueError("lead_h must be at least 1")
    return min(7, math.ceil((lead_h + latency_h) / 24))


def est_init_time(target_time: object, previous_day: int) -> pd.Timestamp:
    """Conservative upper bound of the NWP initialization time."""
    if previous_day < 1:
        raise ValueError("previous_day must be at least 1; previous_day0 is prohibited")
    return as_utc(target_time) - pd.Timedelta(hours=24 * previous_day)


def available_at(target_time: object, previous_day: int, latency_h: int = LATENCY_H) -> pd.Timestamp:
    return est_init_time(target_time, previous_day) + pd.Timedelta(hours=latency_h)


@dataclass(frozen=True)
class TemporalAudit:
    max_nwp_init_time_used: str
    max_scada_time_used: str | None


def assert_no_lookahead(
    rows: pd.DataFrame | Iterable[dict], issue_time: object, latency_h: int = LATENCY_H
) -> TemporalAudit:
    """Raise when a selected previous-run forecast was unavailable at ``issue_time``.

    Rows must contain ``target_time`` and ``lead_day``. This deliberately never
    accepts day 0 products, which can contain future information at short leads.
    """
    issue = as_utc(issue_time)
    frame = rows if isinstance(rows, pd.DataFrame) else pd.DataFrame(rows)
    if frame.empty:
        raise ValueError("cannot audit an empty weather selection")
    required = {"target_time", "lead_day"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"temporal audit needs columns: {sorted(missing)}")

    init_times: list[pd.Timestamp] = []
    for row in frame.loc[:, ["target_time", "lead_day"]].itertuples(index=False):
        target, day = row
        init = est_init_time(target, int(day))
        if init + pd.Timedelta(hours=latency_h) > issue:
            raise AssertionError(
                f"lookahead: target={as_utc(target).isoformat()}, previous_day={day}, "
                f"available_at={(init + pd.Timedelta(hours=latency_h)).isoformat()}, issue={issue.isoformat()}"
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

    return TemporalAudit(
        max_nwp_init_time_used=max(init_times).isoformat().replace("+00:00", "Z"),
        max_scada_time_used=scada_max,
    )
