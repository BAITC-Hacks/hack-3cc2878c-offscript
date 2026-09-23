import json

from fastapi import APIRouter, HTTPException, Query, Request

from ..agent.briefing import template
from ..ledger import sha
from ..ml_bridge import ml

router = APIRouter(tags=["forecast"])


@router.get("/api/forecast")
def forecast(request: Request, issue_date: str = Query(...), variant: str = "hybrid", mode: str = "test") -> dict:
    if mode not in {"test", "val_feb2025", "val_winter"}:
        raise HTTPException(422, "Unknown mode")
    if variant not in {"hybrid", "mos_pc", "raw_pc", "climatology", "persistence"}:
        raise HTTPException(422, "Unknown model variant")
    if issue_date not in ml.list_issue_dates(mode):
        raise HTTPException(422, "Issue date is outside the selected schedule")
    result = None
    ledger = request.app.state.ledger
    repo_root = request.app.state.orchestrator.repo_root
    for block in reversed(ledger.blocks):
        if block.get("issue_date") != issue_date or (block.get("variant") and block["variant"] != variant):
            continue
        payload_file = block.get("payload_file")
        if not payload_file:
            continue
        published = (repo_root / payload_file).resolve()
        if not published.is_relative_to(repo_root.resolve()) or not published.exists():
            continue
        stored = json.loads(published.read_text(encoding="utf-8"))
        if stored.get("variant") == variant and stored.get("mode") == mode and sha(stored.get("rows", [])) == block.get("payload_sha256"):
            result = stored
            break
    if result is None:
        result = ml.run_forecast(issue_date, variant=variant, mode=mode)
    flags = ml.risk_scan(result)
    result["flags"] = flags
    payload_hash = sha(result["rows"])
    proof = next((block for block in reversed(ledger.blocks)
                  if block.get("issue_date") == issue_date and block.get("payload_sha256") == payload_hash), None)
    if proof:
        result["ledger"] = {"block_index": proof["index"], "hash": proof["hash"], "verified": ledger.verify()["valid"]}
        result["availability_evidence_status"] = ledger.policy_evidence_status(proof)
    else:
        result.pop("ledger", None)
        result["availability_evidence_status"] = (
            "configured_policy_v1_source_release_unverified" if result.get("availability_policy_version")
            else "legacy_policy_evidence"
        )
    if result["availability_evidence_status"] == "legacy_policy_evidence":
        # Derived response annotations only: never modify an anchored payload.
        result.setdefault("max_estimated_nwp_init_time_used", result.get("max_nwp_init_time_used"))
        result["source_release_time_verified"] = False
    result["briefing"] = result.get("briefing") or template(result, flags).model_dump()
    return result


@router.get("/api/series")
def series(mode: str = "val_feb2025") -> dict:
    return {"mode": mode, "rows": ml.get_series(mode)}
