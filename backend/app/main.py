from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .agent.llm import LLM
from .agent.orchestrator import Orchestrator
from .ledger import Ledger
from .runs import RunRegistry
from .settings import settings
from .routers import agent, backtest, economics, forecast, health, ledger, live


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield

    app = FastAPI(title="SAMAL API", version="0.1.0", description="Leakage-proof agentic wind-farm forecasting service.", lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False, allow_methods=["*"], allow_headers=["*"])
    app.state.settings = settings
    app.state.ledger = Ledger(settings.ledger_path)
    app.state.runs = RunRegistry(settings.outputs_dir / "agent_runs")
    app.state.orchestrator = Orchestrator(app.state.ledger, app.state.runs, LLM())
    for router in (health.router, forecast.router, agent.router, ledger.router, backtest.router, economics.router, live.router):
        app.include_router(router)
    return app


app = create_app()
