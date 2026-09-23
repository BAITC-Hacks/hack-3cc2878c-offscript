from __future__ import annotations

from typing import Any

from ..schemas import CriticDecision, DeciderDecision, PlannerDecision


DEFAULT_MODELS = ["ecmwf_ifs025", "gfs_seamless", "icon_seamless"]


def plan() -> PlannerDecision:
    return PlannerDecision(steps=["fetch_nwp", "check_inputs", "run_forecast", "risk_scan"], variant="hybrid",
                           models=DEFAULT_MODELS, reasoning="Use the full archived NWP ensemble and calibrated hybrid quantiles.")


def decide(inputs: dict[str, Any], flags: list[dict[str, Any]]) -> DeciderDecision:
    missing = inputs.get("models_missing", [])
    has_cutout = any(flag.get("code") == "CUT_OUT" for flag in flags)
    high_spread = inputs.get("spread_mean_ms", 0) >= 2.5
    if has_cutout:
        return DeciderDecision(action="ESCALATE", widen=0.1, rationale="Potential turbine cut-out requires dispatch review.")
    if missing:
        return DeciderDecision(action="WIDEN", widen=0.08, rationale="A weather model is unavailable; widen uncertainty.")
    if high_spread:
        return DeciderDecision(action="WIDEN", widen=0.05, rationale="NWP disagreement exceeds the uncertainty threshold.")
    return DeciderDecision(action="ACCEPT", rationale="Inputs pass temporal and coverage checks.")


def critic(forecast: dict[str, Any], flags: list[dict[str, Any]], decision: DeciderDecision) -> CriticDecision:
    rows = forecast["rows"]
    crossing = any(not (row["p10"] <= row["p50"] <= row["p90"]) for row in rows)
    invalid_power = any(not (0 <= row["p10"] <= 1 and 0 <= row["p90"] <= 1) for row in rows)
    too_narrow = any(row["v_hub_spread"] and row["v_hub_spread"] >= 2.5 and row["p90"] - row["p10"] < 0.25 for row in rows)
    issues: list[str] = []
    if crossing:
        issues.append("Quantile crossing detected.")
    if invalid_power:
        issues.append("Power bounds violated.")
    if too_narrow:
        issues.append("Band is too narrow for the observed model spread.")
    if issues:
        return CriticDecision(approve=False, issues=issues,
                              suggestion=DeciderDecision(action="WIDEN", widen=min(0.3, decision.widen + 0.05), rationale="Correct deterministic audit finding."))
    return CriticDecision(approve=True, issues=[], suggestion=DeciderDecision(action="ACCEPT", rationale="Quantiles and physical bounds pass audit."))
