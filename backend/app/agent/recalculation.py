"""Comparable input and forecast evidence for same-issue and daily replay updates."""

from __future__ import annotations

from typing import Any

from ..ledger import sha

FORECAST_MAE_THRESHOLD = 0.05
FORECAST_MAX_THRESHOLD = 0.10


def comparison(
    old_block: dict[str, Any], old_forecast: dict[str, Any],
    new_inputs: dict[str, Any], new_forecast: dict[str, Any],
    diff: dict[str, Any], *, path: str, reason: str,
) -> dict[str, Any]:
    """Compare like-for-like target hours; never equate whole adjacent-issue hashes."""
    if path not in {"historical_overlap", "same_issue_recalculation"}:
        raise ValueError(f"unknown recalculation path: {path}")
    old_issue_hash = old_block.get("inputs_sha256")
    new_issue_hash = new_inputs.get("inputs_sha256")
    shared = sorted(
        {row["target_time"] for row in old_forecast["rows"]}
        & {row["target_time"] for row in new_forecast["rows"]}
    )
    if path == "same_issue_recalculation":
        old_hash, new_hash = old_issue_hash, new_issue_hash
    else:
        old_by_target = old_forecast.get("nwp_input_fingerprints") or {}
        new_by_target = new_inputs.get("input_fingerprints_by_target") or {}
        if shared and all(target in old_by_target and target in new_by_target for target in shared):
            old_hash = sha({target: old_by_target[target] for target in shared})
            new_hash = sha({target: new_by_target[target] for target in shared})
        else:
            # Legacy published payloads cannot acquire a retroactive full-input fingerprint.
            old_hash = new_hash = None
    input_changed = old_hash != new_hash if old_hash and new_hash else None
    mae = diff.get("mae")
    max_abs = diff.get("max_abs")
    material = bool(
        (mae is not None and mae >= FORECAST_MAE_THRESHOLD)
        or (max_abs is not None and max_abs >= FORECAST_MAX_THRESHOLD)
        or diff.get("hours_outside_old_band", 0) > 0
    )
    return {
        "path": path,
        "previous_issue_date": old_forecast["issue_date"],
        "previous_block_index": old_block["index"],
        "old_input_sha256": old_hash,
        "new_input_sha256": new_hash,
        "old_issue_input_sha256": old_issue_hash,
        "new_issue_input_sha256": new_issue_hash,
        "input_changed": input_changed,
        "overlap_hours": len(shared),
        "mae": mae,
        "max_abs": max_abs,
        "hours_outside_old_band": diff.get("hours_outside_old_band"),
        "forecast_materially_changed": material,
        "reason": reason,
    }
