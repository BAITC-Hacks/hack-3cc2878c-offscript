from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
import json
from pathlib import Path
import secrets
from typing import Any

from .schemas import AgentEvent


def now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


@dataclass
class Run:
    run_id: str
    issue_date: str
    mode: str
    events: list[dict[str, Any]] = field(default_factory=list)
    queue: asyncio.Queue[dict[str, Any]] = field(default_factory=asyncio.Queue)
    status: str = "running"
    result: dict[str, Any] | None = None
    decision: str | None = None
    started_at: str = field(default_factory=now_iso)

    async def emit(self, stage: str, event_type: str, title: str, actor: str, *, detail: dict[str, Any] | None = None,
                   llm: dict[str, Any] | None = None, duration_ms: int | None = None) -> dict[str, Any]:
        event = AgentEvent(run_id=self.run_id, seq=len(self.events), ts=now_iso(), stage=stage, type=event_type,
                           title=title, detail=detail or {}, actor=actor, llm=llm, duration_ms=duration_ms).model_dump()
        self.events.append(event)
        await self.queue.put(event)
        return event

    def snapshot(self) -> dict[str, Any]:
        return {"run_id": self.run_id, "issue_date": self.issue_date, "mode": self.mode, "status": self.status,
                "started_at": self.started_at, "decision": self.decision, "events": self.events, "result": self.result}


class RunRegistry:
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.runs: dict[str, Run] = {}
        if output_dir.exists():
            for path in sorted(output_dir.glob("r_*.json")):
                try:
                    saved = json.loads(path.read_text(encoding="utf-8"))
                    run = Run(run_id=saved["run_id"], issue_date=saved["issue_date"], mode=saved["mode"],
                              events=saved.get("events", []), status=saved.get("status", "error"),
                              result=saved.get("result"), decision=saved.get("decision"),
                              started_at=saved.get("started_at", now_iso()))
                    if run.status == "running":
                        run.status = "error"  # A process restart cannot resume an in-flight cycle.
                    self.runs[run.run_id] = run
                except (KeyError, ValueError, TypeError):
                    continue

    def create(self, issue_date: str, mode: str) -> Run:
        run = Run(run_id=f"r_{issue_date.replace('-', '')}_{secrets.token_hex(3)}", issue_date=issue_date, mode=mode)
        self.runs[run.run_id] = run
        return run

    def get(self, run_id: str) -> Run | None:
        return self.runs.get(run_id)

    def list(self) -> list[dict[str, Any]]:
        return [{key: run.snapshot()[key] for key in ("run_id", "issue_date", "status", "started_at", "decision")}
                for run in sorted(self.runs.values(), key=lambda item: item.started_at, reverse=True)]

    def persist(self, run: Run) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        with (self.output_dir / f"{run.run_id}.json").open("w", encoding="utf-8") as handle:
            json.dump(run.snapshot(), handle, ensure_ascii=False, indent=2)
