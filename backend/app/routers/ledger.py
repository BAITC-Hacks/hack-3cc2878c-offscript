from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

router = APIRouter(tags=["ledger"])


class TamperRequest(BaseModel):
    block_index: int = Field(ge=0)


@router.get("/api/ledger")
def get_ledger(request: Request) -> dict:
    ledger = request.app.state.ledger
    return {"length": len(ledger.blocks), "head_hash": ledger.blocks[-1]["hash"], "blocks": ledger.blocks}


@router.post("/api/ledger/verify")
def verify(request: Request) -> dict:
    return request.app.state.ledger.verify()


@router.post("/api/ledger/tamper-demo")
def tamper(body: TamperRequest, request: Request) -> dict:
    try:
        return request.app.state.ledger.tamper_demo(body.block_index)
    except IndexError as exc:
        raise HTTPException(404, str(exc)) from exc
