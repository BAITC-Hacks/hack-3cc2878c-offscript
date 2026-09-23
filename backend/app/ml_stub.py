"""Contract-compatible offline fallback used until the ML package is available."""
from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime, timedelta
import hashlib
import json
from pathlib import Path
from typing import Any

from samal_ml.temporal_guard import availability_policy_metadata

from .settings import settings


def _load(name: str) -> Any:
    with (settings.mocks_dir / name).open(encoding="utf-8") as handle:
        return json.load(handle)


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _issue_time(issue_date: str) -> datetime:
    local_midnight = datetime.fromisoformat(issue_date).replace(tzinfo=UTC)
    return local_midnight - timedelta(hours=5)


def get_meta() -> dict[str, Any]:
    value = _load("meta.json")
    value.pop("_mock", None)
    return value


def list_issue_dates(mode: str) -> list[str]:
    return get_meta()["issue_dates"].get(mode, [])


def issue_time_for(issue_date: str) -> str:
    return _iso(_issue_time(issue_date))


def _shift_forecast(forecast: dict[str, Any], issue_date: str, mode: str) -> dict[str, Any]:
    result = deepcopy(forecast)
    source_issue = datetime.fromisoformat(result["issue_time"].replace("Z", "+00:00"))
    target_issue = _issue_time(issue_date)
    delta = target_issue - source_issue
    result.pop("_mock", None)
    result["issue_date"] = issue_date
    result["issue_time"] = _iso(target_issue)
    result["mode"] = mode
    result["max_nwp_init_time_used"] = _iso(target_issue - timedelta(hours=8))
    result["max_estimated_nwp_init_time_used"] = result["max_nwp_init_time_used"]
    result.update(availability_policy_metadata(8))
    result["max_scada_time_used"] = _iso(target_issue - timedelta(hours=1))
    for row in result["rows"]:
        utc = datetime.fromisoformat(row["target_time"].replace("Z", "+00:00")) + delta
        local = datetime.fromisoformat(row["target_time_local"]) + delta
        row["target_time"] = _iso(utc)
        row["target_time_local"] = local.isoformat()
        if mode == "test":
            row["actual"] = None
    for flag in result.get("flags", []):
        for key in ("start", "end"):
            flag[key] = _iso(datetime.fromisoformat(flag[key].replace("Z", "+00:00")) + delta)
    return result


def fetch_nwp(issue_date: str, models: list[str] | None = None) -> dict[str, Any]:
    forecast = run_forecast(issue_date, models=models)
    used = models or forecast["nwp_models_used"]
    raw = json.dumps({"issue_date": issue_date, "models": used}, sort_keys=True).encode()
    return {
        "issue_time": forecast["issue_time"], "models_ok": used, "models_missing": [],
        "coverage": {model: 1.0 for model in used},
        "max_nwp_init_time_used": forecast["max_nwp_init_time_used"], "latency_h": 8,
        **{key: forecast[key] for key in (
            "availability_basis", "availability_policy_version", "source_release_time_verified",
            "source_release_time_evidence", "max_estimated_nwp_init_time_used", "configured_latency_h",
        )},
        "inputs_sha256": hashlib.sha256(raw).hexdigest(), "n_rows": 48,
    }


def check_inputs(issue_date: str) -> dict[str, Any]:
    forecast = run_forecast(issue_date)
    spread = sum(row["v_hub_spread"] for row in forecast["rows"]) / len(forecast["rows"])
    return {"ok": True, "issues": [], "spread_mean_ms": round(spread, 3), "models_ok": forecast["nwp_models_used"]}


def run_forecast(issue_date: str, variant: str = "hybrid", widen: float = 0.0,
                 models: list[str] | None = None, mode: str = "test") -> dict[str, Any]:
    result = _shift_forecast(_load("forecast.json"), issue_date, mode)
    result["variant"] = variant
    result["widen"] = round(widen, 3)
    result["nwp_models_used"] = models or result["nwp_models_used"]
    if widen:
        for row in result["rows"]:
            row["p10"] = round(max(0, row["p10"] - widen), 4)
            row["p90"] = round(min(1, row["p90"] + widen), 4)
        result["summary"]["mean_band"] = round(result["summary"]["mean_band"] + 2 * widen, 4)
    return result


def risk_scan(forecast: dict[str, Any]) -> list[dict[str, Any]]:
    return forecast.get("flags", [])


def get_metrics(mode: str) -> dict[str, Any]:
    value = _load("backtest_val_feb2025.json")
    value.pop("_mock", None)
    value["mode"] = mode
    return value


def get_series(mode: str) -> list[dict[str, Any]]:
    value = _load("series_val_feb2025.json")
    return value.get("rows", value)


def get_economics(mode: str, capacity_mw: float, price_kzt_mwh: float) -> dict[str, Any]:
    value = _load("economics.json")
    value.pop("_mock", None)
    factor = (capacity_mw / value["capacity_mw"]) * (price_kzt_mwh / value["price_kzt_mwh"])
    value["mode"] = mode
    value["capacity_mw"] = capacity_mw
    value["price_kzt_mwh"] = price_kzt_mwh
    for key in ("cost_kzt",):
        value[key] = {name: round(amount * factor, 2) for name, amount in value[key].items()}
    for key in ("savings_vs_persistence_kzt", "annualized_savings_kzt"):
        value[key] = round(value[key] * factor, 2)
    return value


def forecast_diff(old: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    old_by_time = {row["target_time"]: row for row in old["rows"]}
    deltas = [abs(row["p50"] - old_by_time[row["target_time"]]["p50"]) for row in new["rows"] if row["target_time"] in old_by_time]
    outside = sum(1 for row in new["rows"] if row["target_time"] in old_by_time and not (old_by_time[row["target_time"]]["p10"] <= row["p50"] <= old_by_time[row["target_time"]]["p90"]))
    return {"overlap_hours": len(deltas), "mae": round(sum(deltas) / len(deltas), 4) if deltas else 0,
            "max_abs": round(max(deltas), 4) if deltas else 0, "hours_outside_old_band": outside}
