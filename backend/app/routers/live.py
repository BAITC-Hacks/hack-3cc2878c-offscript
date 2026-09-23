from fastapi import APIRouter, HTTPException

router = APIRouter(tags=["live"])


@router.get("/api/live/tomorrow")
def tomorrow() -> None:
    raise HTTPException(501, "Live forecast is intentionally disabled until fresh archived NWP retrieval is configured.")
