"""Configuration and filesystem locations for the ML package."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class ProjectPaths:
    root: Path = REPO_ROOT

    @property
    def raw(self) -> Path:
        return self.root / "data" / "raw"

    @property
    def cache(self) -> Path:
        return self.root / "data" / "cache"

    @property
    def nwp_cache(self) -> Path:
        return self.cache / "nwp"

    @property
    def models(self) -> Path:
        return self.root / "data" / "models"

    @property
    def outputs(self) -> Path:
        return self.root / "data" / "outputs"


PATHS = ProjectPaths()

LAT = 43.6442
LON = 78.5372
HUB_HEIGHT_M = 100.0
FARM_CAPACITY_MW = float(os.getenv("FARM_CAPACITY_MW", "5.0"))
LATENCY_H = int(os.getenv("NWP_LATENCY_H", os.getenv("LATENCY_H", "8")))
TZ_NAME = "Asia/Almaty"
WEATHER_OFFLINE = os.getenv("WEATHER_OFFLINE", "0") == "1"

NWP_MODELS = ("ecmwf_ifs025", "gfs_seamless", "icon_seamless")
NWP_VARIABLES = (
    "wind_speed_10m",
    "wind_speed_100m",
    "wind_direction_10m",
    "wind_direction_100m",
    "temperature_2m",
    "relative_humidity_2m",
    "surface_pressure",
)

COLUMN_MAP = {
    "time": "Статистическое время",
    "wind": "Средняя скорость ветра(m/s)",
    "power": "Нормализованная активная мощность",
    "temperature": "Средняя температура окружающей среды(°C)",
}
SCADA_FILES = {"T1": "turbine_1.csv", "T2": "turbine_2.csv"}

RISK_THRESHOLDS = {
    "ramp": 0.30,
    "cut_out_ms": 23.0,
    "wide_band": 0.50,
    "disagreement_ms": 2.5,
}
