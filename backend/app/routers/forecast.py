from fastapi import APIRouter, HTTPException, Query, Request

from ..agent.briefing import template
from ..ml_bridge import ml

router = APIRouter(tags=["forecast"])


@router.get("/api/forecast")
def forecast(request: Request, issue_date: str = Query(...), variant: str = "hybrid", mode: str = "test") -> dict:
    if mode not in {"test", "val_feb2025", "val_winter"}:
        raise HTTPException(422, "Unknown mode")
    if variant not in {"hybrid", "mos_pc", "raw_pc", "climatology", "persistence"}:
        raise HTTPException(422, "Unknown model variant")
    result = ml.run_forecast(issue_date, variant=variant, mode=mode)
    flags = ml.risk_scan(result)
    result["flags"] = flags
    ledger = request.app.state.ledger
    latest = ledger.blocks[-1]
    result["ledger"] = {"block_index": latest["index"], "hash": latest["hash"], "verified": ledger.verify()["valid"]}
    result["briefing"] = template(result, flags).model_dump()
    return result


@router.get("/api/series")
def series(mode: str = "val_feb2025") -> dict:
    return {"mode": mode, "rows": ml.get_series(mode)}
