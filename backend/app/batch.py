from __future__ import annotations

import argparse
import asyncio

from .main import app
from .ml_bridge import ml


async def main(mode: str) -> None:
    for issue_date in ml.list_issue_dates(mode):
        run = app.state.runs.create(issue_date, mode)
        await app.state.orchestrator.run(run, use_llm=False)
        print(f"{issue_date}: {run.status} ({run.decision})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Replay SAMAL agent over an issue schedule.")
    parser.add_argument("--mode", default="test", choices=["test", "val_feb2025", "val_winter"])
    args = parser.parse_args()
    asyncio.run(main(args.mode))
