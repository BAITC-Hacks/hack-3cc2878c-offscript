from fastapi import APIRouter, Request

from ..ml_bridge import USING_STUB

router = APIRouter(tags=["health"])


@router.get("/api/health")
def health(request: Request) -> dict:
    config = request.app.state.settings
    return {"status": "ok", "version": "0.1.0", "llm_provider": config.llm_provider,
            "weather_offline": config.weather_offline, "ml_stub": USING_STUB}


@router.get("/api/meta")
def meta(request: Request) -> dict:
    from ..ml_bridge import ml
    return ml.get_meta()
