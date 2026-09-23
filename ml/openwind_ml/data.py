"""Loading, UTC normalization, hourly aggregation, and transparent SCADA flags."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import numpy as np
import pandas as pd

from .config import COLUMN_MAP, PATHS, SCADA_FILES


def _local_almaty_to_utc(local_time: pd.Series) -> pd.Series:
    """Apply the documented UTC+6 -> UTC+5 shift without ambiguous timezone inference."""
    parsed = pd.to_datetime(local_time, errors="coerce")
    cutoff = pd.Timestamp("2024-03-01 00:00:00")
    offsets = np.where(parsed < cutoff, 6, 5)
    return (parsed - pd.to_timedelta(offsets, unit="h")).dt.tz_localize("UTC")


def _stuck_flag(values: pd.Series, minimum_hours: int = 6) -> pd.Series:
    changed = values.ne(values.shift()) | values.isna()
    groups = changed.cumsum()
    lengths = values.groupby(groups).transform("size")
    return values.notna() & lengths.ge(minimum_hours)


def _read_turbine(turbine_id: str, path: Path) -> pd.DataFrame:
    raw = pd.read_csv(path)
    missing = set(COLUMN_MAP.values()).difference(raw.columns)
    if missing:
        raise ValueError(f"{path.name} is missing expected SCADA columns: {sorted(missing)}")
    frame = pd.DataFrame(
        {
            "time": _local_almaty_to_utc(raw[COLUMN_MAP["time"]]),
            "wind_meas": pd.to_numeric(raw[COLUMN_MAP["wind"]], errors="coerce"),
            "p": pd.to_numeric(raw[COLUMN_MAP["power"]], errors="coerce").clip(0, 1),
            "temp_c": pd.to_numeric(raw[COLUMN_MAP["temperature"]], errors="coerce"),
            "turbine_id": turbine_id,
        }
    ).dropna(subset=["time"])
    return frame.set_index("time").sort_index()


def load_scada(files: Mapping[str, Path] | None = None) -> pd.DataFrame:
    """Load the two source files into an hourly, UTC-indexed farm-level frame.

    Missing source intervals are retained as flagged hourly rows. Values from
    whichever turbine is available are averaged, so a single outage is not
    silently treated as a zero-power farm.
    """
    source_files = files or {key: PATHS.raw / value for key, value in SCADA_FILES.items()}
    turbine_frames = [_read_turbine(turbine_id, Path(path)) for turbine_id, path in source_files.items()]
    raw = pd.concat(turbine_frames).sort_index()
    hourly_by_turbine = raw.groupby("turbine_id").resample("h")[["wind_meas", "p", "temp_c"]].mean()
    hourly_by_turbine["flag_stuck_turbine"] = hourly_by_turbine.groupby(level=0)["p"].transform(_stuck_flag)

    farm = hourly_by_turbine.groupby(level=1)[["wind_meas", "p", "temp_c"]].mean()
    farm.index.name = "time"
    full_index = pd.date_range(farm.index.min(), farm.index.max(), freq="h", tz="UTC", name="time")
    farm = farm.reindex(full_index)
    farm["n_turbines"] = hourly_by_turbine["p"].groupby(level=1).count().reindex(full_index, fill_value=0)
    stuck = hourly_by_turbine["flag_stuck_turbine"].groupby(level=1).any().reindex(full_index, fill_value=False)
    farm["flag_missing"] = farm[["wind_meas", "p", "temp_c"]].isna().any(axis=1)
    farm["flag_stuck"] = stuck.astype(bool)
    farm["flag_outage"] = (farm["wind_meas"] >= 6.0) & (farm["p"] < 0.03)
    # A conservative diagnostic flag. The main model does not train on it.
    farm["flag_icing_suspect"] = (
        (farm["temp_c"] <= 1.0)
        & farm["wind_meas"].between(5.0, 15.0)
        & (farm["p"] < 0.10)
    )
    return farm


def inspect_scada() -> dict:
    """Return compact source-quality facts suitable for CLI output and tests."""
    frame = load_scada()
    return {
        "rows_hourly": int(len(frame)),
        "start_utc": frame.index.min().isoformat().replace("+00:00", "Z"),
        "end_utc": frame.index.max().isoformat().replace("+00:00", "Z"),
        "columns": list(frame.columns),
        "nan_percent": {key: round(float(value * 100), 3) for key, value in frame.isna().mean().items()},
        "power_range": [float(frame["p"].min()), float(frame["p"].max())],
        "wind_range_ms": [float(frame["wind_meas"].min()), float(frame["wind_meas"].max())],
    }
