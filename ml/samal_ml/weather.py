"""Archived Open-Meteo Previous Runs retrieval and offline cache loading."""

from __future__ import annotations

import time
from collections.abc import Iterable
from pathlib import Path

import pandas as pd
import requests

from .config import LAT, LON, NWP_MODELS, NWP_VARIABLES, PATHS, WEATHER_OFFLINE

BASE_URL = "https://previous-runs-api.open-meteo.com/v1/forecast"


def _iso_day(value: object) -> str:
    return pd.Timestamp(value).date().isoformat()


def build_url(model: str, start: object, end: object, days: Iterable[int] = (1, 2, 3)) -> str:
    hourly = [f"{variable}_previous_day{day}" for variable in NWP_VARIABLES for day in days]
    response = requests.Request(
        "GET",
        BASE_URL,
        params={
            "latitude": LAT,
            "longitude": LON,
            "hourly": ",".join(hourly),
            "models": model,
            "start_date": _iso_day(start),
            "end_date": _iso_day(end),
            "wind_speed_unit": "ms",
            "timezone": "GMT",
        },
    ).prepare()
    return str(response.url)


def _cache_path(model: str, start: object, end: object) -> Path:
    return PATHS.nwp_cache / f"{model}_{_iso_day(start)}_{_iso_day(end)}.csv.gz"


def fetch_chunk(model: str, start: object, end: object, retries: int = 3) -> pd.DataFrame:
    """Fetch a single cacheable date range, retrying only transient failures."""
    target = _cache_path(model, start, end)
    if target.exists():
        return pd.read_csv(target, parse_dates=["time"])
    if WEATHER_OFFLINE:
        raise FileNotFoundError(f"offline mode: missing NWP cache {target}")

    url = build_url(model, start, end)
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            response = requests.get(url, timeout=60)
            response.raise_for_status()
            payload = response.json()
            hourly = payload.get("hourly")
            if not hourly or "time" not in hourly:
                raise ValueError(f"Open-Meteo returned no hourly data for {model}: {payload}")
            frame = pd.DataFrame(hourly)
            frame["time"] = pd.to_datetime(frame["time"], utc=True)
            target.parent.mkdir(parents=True, exist_ok=True)
            frame.to_csv(target, index=False, compression="gzip")
            return frame
        except (requests.RequestException, ValueError) as error:
            last_error = error
            if attempt == retries - 1:
                break
            time.sleep(2**attempt)
    raise RuntimeError(f"could not fetch archived NWP for {model} {start}..{end}: {last_error}")


def _chunks(start: object, end: object, months: int = 3) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    cursor = pd.Timestamp(start).normalize()
    final = pd.Timestamp(end).normalize()
    result: list[tuple[pd.Timestamp, pd.Timestamp]] = []
    while cursor <= final:
        chunk_end = min(cursor + pd.DateOffset(months=months) - pd.Timedelta(days=1), final)
        result.append((cursor, chunk_end))
        cursor = chunk_end + pd.Timedelta(days=1)
    return result


def fetch_archive(
    models: Iterable[str] = NWP_MODELS,
    start: object = "2024-03-01",
    end: object = "2026-03-02",
) -> dict[str, int]:
    """Fetch all requested models in 3-month chunks and return row counts."""
    counts: dict[str, int] = {}
    for model in models:
        frames = []
        for chunk_start, chunk_end in _chunks(start, end):
            frames.append(fetch_chunk(model, chunk_start, chunk_end))
            time.sleep(1)
        counts[model] = int(sum(len(frame) for frame in frames))
    return counts


def load_nwp_cache(models: Iterable[str] = NWP_MODELS) -> dict[str, pd.DataFrame]:
    """Load cached archived forecasts, keeping only records indexed by UTC valid time."""
    loaded: dict[str, pd.DataFrame] = {}
    for model in models:
        files = sorted(PATHS.nwp_cache.glob(f"{model}_*.csv.gz"))
        if not files:
            continue
        frames = [pd.read_csv(file, compression="gzip") for file in files]
        frame = pd.concat(frames, ignore_index=True)
        if "time" not in frame:
            raise ValueError(f"NWP cache for {model} has no time column")
        frame["time"] = pd.to_datetime(frame["time"], utc=True)
        frame = frame.drop_duplicates("time", keep="last").sort_values("time")
        frame = frame.dropna(axis=1, how="all").set_index("time")
        loaded[model] = frame
    return loaded


def cache_coverage(models: Iterable[str] = NWP_MODELS) -> dict[str, float]:
    """Return fraction of non-null 100m day-1 wind values in each cache."""
    result: dict[str, float] = {}
    for model, frame in load_nwp_cache(models).items():
        column = next((col for col in frame.columns if col.startswith("wind_speed_100m_previous_day1")), None)
        result[model] = 0.0 if column is None else round(float(frame[column].notna().mean()), 4)
    return result
