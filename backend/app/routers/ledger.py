from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

router = APIRouter(tags=["ledger"])


class TamperRequest(BaseModel):
    block_index: int = Field(ge=0)


@router.get("/api/ledger")
def get_ledger(request: Request) -> dict:
    ledger = request.app.state.ledger
    blocks = []
    for block in ledger.blocks:
        presented = {**block, "availability_evidence_status": ledger.policy_evidence_status(block)}
        if (block.get("type") == "REVISION" and "revision_kind" not in block
                and "input_changed=False" in str(block.get("note", ""))):
            # Derived label only: historical anchored block bytes are unchanged.
            presented["revision_kind"] = "legacy_manual_uncertainty_review"
        blocks.append(presented)
    return {"length": len(blocks), "head_hash": ledger.blocks[-1]["hash"], "blocks": blocks}


@router.post("/api/ledger/verify")
def verify(request: Request) -> dict:
    return request.app.state.ledger.verify()


@router.post("/api/ledger/tamper-demo")
def tamper(body: TamperRequest, request: Request) -> dict:
    try:
        return request.app.state.ledger.tamper_demo(body.block_index)
    except IndexError as exc:
        raise HTTPException(404, str(exc)) from exc
