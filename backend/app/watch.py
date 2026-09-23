"""Opt-in polling of selected NWP inputs for an already published issue."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable

from .agent.orchestrator import Orchestrator
from .ml_bridge import ml
from .runs import RunRegistry

logger = logging.getLogger(__name__)


class NWPWatcher:
    def __init__(
        self, orchestrator: Orchestrator, runs: RunRegistry, *, mode: str = "test",
        issue_date: str | None = None, poll_seconds: int = 60, use_llm: bool = False,
        fetch_nwp: Callable[[str, list[str] | None], dict[str, Any]] | None = None,
    ) -> None:
        self.orchestrator = orchestrator
        self.runs = runs
        self.mode = mode
        self.issue_date = issue_date
        self.poll_seconds = max(5, poll_seconds)
        self.use_llm = use_llm
        self.fetch_nwp = fetch_nwp or ml.fetch_nwp
        self._task: asyncio.Task[None] | None = None
        self._active_run: asyncio.Task[None] | None = None
        self._last_triggered_hash: str | None = None

    def _target_issue(self) -> str | None:
        if self.issue_date:
            return self.issue_date
        for block in reversed(self.orchestrator.ledger.blocks):
            candidate = block.get("issue_date")
            if candidate and self.orchestrator._latest_published(candidate, self.mode):
                return candidate
        return None

    async def poll_once(self) -> dict[str, Any]:
        issue_date = self._target_issue()
        if issue_date is None:
            return {"status": "no_published_issue"}
        previous = self.orchestrator._latest_published(issue_date, self.mode)
        if previous is None or not previous[0].get("inputs_sha256"):
            return {"status": "no_comparable_published_input", "issue_date": issue_date}
        old_hash = previous[0]["inputs_sha256"]
        observed_inputs = await asyncio.to_thread(self.fetch_nwp, issue_date, previous[1].get("nwp_models_used"))
        observed = observed_inputs["inputs_sha256"]
        if observed == old_hash:
            self._last_triggered_hash = None
            return {"status": "unchanged", "issue_date": issue_date, "input_sha256": observed}
        if observed == self._last_triggered_hash:
            return {"status": "already_triggered", "issue_date": issue_date, "input_sha256": observed}
        if (self._active_run is not None and not self._active_run.done()) or any(
            run.status == "running" and run.issue_date == issue_date and run.mode == self.mode
            for run in self.runs.runs.values()
        ):
            return {"status": "run_in_progress", "issue_date": issue_date, "input_sha256": observed}
        run = self.runs.create(issue_date, self.mode)
        self._last_triggered_hash = observed
        self._active_run = asyncio.create_task(
            self.orchestrator.run(run, use_llm=self.use_llm, recalc=True, reason="nwp_poll_update")
        )
        return {"status": "triggered", "issue_date": issue_date, "run_id": run.run_id,
                "old_input_sha256": old_hash, "new_input_sha256": observed}

    async def serve(self) -> None:
        while True:
            try:
                result = await self.poll_once()
                if result["status"] == "triggered":
                    logger.info("NWP cache update triggered recalculation: %s", result)
            except Exception:
                logger.exception("NWP watcher poll failed; next poll will retry")
            await asyncio.sleep(self.poll_seconds)

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self.serve())

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
