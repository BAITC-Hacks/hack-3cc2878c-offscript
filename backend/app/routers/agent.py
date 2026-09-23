from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, HTTPException, Request
from sse_starlette.sse import EventSourceResponse

from ..schemas import AgentRunRequest, RecalcRequest

router = APIRouter(tags=["agent"])


async def _start(request: Request, issue_date: str, mode: str, use_llm: bool, *, recalc: bool = False, reason: str | None = None) -> dict:
    run = request.app.state.runs.create(issue_date, mode)
    asyncio.create_task(request.app.state.orchestrator.run(run, use_llm=use_llm, recalc=recalc, reason=reason))
    return {"run_id": run.run_id}


@router.post("/api/agent/run")
async def run_agent(body: AgentRunRequest, request: Request) -> dict:
    return await _start(request, body.issue_date, body.mode, body.use_llm)


@router.post("/api/agent/recalc")
async def recalc(body: RecalcRequest, request: Request) -> dict:
    return await _start(request, body.issue_date, body.mode, True, recalc=True, reason=body.reason)


@router.get("/api/agent/stream/{run_id}")
async def stream(run_id: str, request: Request) -> EventSourceResponse:
    run = request.app.state.runs.get(run_id)
    if not run:
        raise HTTPException(404, "Unknown run_id")

    async def generate():
        cursor = 0
        while run.status == "running" or cursor < len(run.events):
            while cursor < len(run.events):
                yield {"event": "agent", "data": json.dumps(run.events[cursor])}
                cursor += 1
            if run.status == "running":
                await asyncio.sleep(0.05)

    return EventSourceResponse(generate())


@router.get("/api/agent/runs/{run_id}")
def get_run(run_id: str, request: Request) -> dict:
    run = request.app.state.runs.get(run_id)
    if not run:
        raise HTTPException(404, "Unknown run_id")
    return run.snapshot()


@router.get("/api/agent/runs")
def list_runs(request: Request) -> list[dict]:
    return request.app.state.runs.list()
