from fastapi import APIRouter, Query

from ..ml_bridge import ml

router = APIRouter(tags=["economics"])


@router.get("/api/economics")
def economics(mode: str = "val_feb2025", capacity_mw: float = Query(5.0, gt=0), price_kzt_mwh: float = Query(15000, gt=0)) -> dict:
    if hasattr(ml, "get_economics"):
        return ml.get_economics(mode, capacity_mw, price_kzt_mwh)
    metrics = ml.get_metrics(mode)
    hybrid = metrics["models"]["hybrid"]["nmae"] * capacity_mw * metrics["n_hours"]
    persistence = metrics["models"]["persistence"]["nmae"] * capacity_mw * metrics["n_hours"]
    savings = (persistence - hybrid) * price_kzt_mwh
    return {"mode": mode, "capacity_mw": capacity_mw, "price_kzt_mwh": price_kzt_mwh,
            "assumption_note": "Illustrative flat imbalance price", "hours": metrics["n_hours"],
            "imbalance_mwh": {"hybrid": round(hybrid, 2), "persistence": round(persistence, 2)},
            "cost_kzt": {"hybrid": round(hybrid * price_kzt_mwh, 2), "persistence": round(persistence * price_kzt_mwh, 2)},
            "savings_vs_persistence_kzt": round(savings, 2), "savings_pct": round((1 - hybrid / persistence) * 100, 1),
            "annualized_savings_kzt": round(savings * 12, 2)}
