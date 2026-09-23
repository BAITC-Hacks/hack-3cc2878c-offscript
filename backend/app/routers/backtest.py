from fastapi import APIRouter

from ..ml_bridge import ml

router = APIRouter(tags=["backtest"])


@router.get("/api/backtest")
def backtest(mode: str = "val_feb2025") -> dict:
    return ml.get_metrics(mode)
