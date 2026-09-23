from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .agent.llm import LLM
from .agent.orchestrator import Orchestrator
from .ledger import Ledger
from .runs import RunRegistry
from .settings import settings
from .watch import NWPWatcher
from .routers import agent, backtest, economics, forecast, health, ledger, live


def create_app(*, repo_root: Path | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        watcher = app.state.nwp_watcher
        if watcher is not None:
            watcher.start()
        try:
            yield
        finally:
            if watcher is not None:
                await watcher.stop()

    app = FastAPI(title="SAMAL API", version="0.1.0", description="Agentic wind-farm forecasting with a configured Previous Runs availability check and tamper-evident ledger; provider release times are not verified.", lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False, allow_methods=["*"], allow_headers=["*"])
    app.state.settings = settings
    root = repo_root or settings.repo_root
    app.state.ledger = Ledger(root / "data" / "ledger" / "ledger.jsonl")
    app.state.runs = RunRegistry(root / "data" / "outputs" / "agent_runs")
    app.state.orchestrator = Orchestrator(app.state.ledger, app.state.runs, LLM(), repo_root=root)
    app.state.nwp_watcher = (
        NWPWatcher(app.state.orchestrator, app.state.runs, mode=settings.nwp_watch_mode,
                   issue_date=settings.nwp_watch_issue_date, poll_seconds=settings.nwp_watch_poll_seconds,
                   use_llm=settings.nwp_watch_use_llm)
        if settings.nwp_watch_enabled else None
    )
    for router in (health.router, forecast.router, agent.router, ledger.router, backtest.router, economics.router, live.router):
        app.include_router(router)
    return app


app = create_app()
