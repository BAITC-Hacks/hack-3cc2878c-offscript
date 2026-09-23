from __future__ import annotations

import asyncio
from types import SimpleNamespace

import app.agent.orchestrator as orchestrator_module
import app.batch as batch_module
from app import ml_stub
from app.agent.llm import LLM
from app.agent.orchestrator import Orchestrator
from app.ledger import Ledger, sha
from app.runs import RunRegistry
from app.watch import NWPWatcher


def _system(tmp_path, monkeypatch):
    version = {"value": "a"}
    original_fetch = ml_stub.fetch_nwp

    def fetch(issue_date, models=None):
        result = original_fetch(issue_date, models)
        result["inputs_sha256"] = sha([result["inputs_sha256"], version["value"]])
        result["input_fingerprints_by_target"] = {
            target: sha([fingerprint, version["value"]])
            for target, fingerprint in result["input_fingerprints_by_target"].items()
        }
        return result

    monkeypatch.setattr(ml_stub, "fetch_nwp", fetch)
    monkeypatch.setattr(orchestrator_module, "ml", ml_stub)
    ledger = Ledger(tmp_path / "data" / "ledger" / "ledger.jsonl")
    runs = RunRegistry(tmp_path / "data" / "outputs" / "agent_runs")
    orchestrator = Orchestrator(ledger, runs, LLM(provider="none"), repo_root=tmp_path)
    return version, fetch, ledger, runs, orchestrator


async def _run(orchestrator, runs, issue_date, *, recalc=False, reason=None):
    run = runs.create(issue_date, "test")
    await orchestrator.run(run, use_llm=False, recalc=recalc, reason=reason)
    assert run.status == "done", run.events[-1]
    return run


def test_unchanged_weather_does_not_publish_revision_but_changed_inputs_do(tmp_path, monkeypatch):
    version, _, ledger, runs, orchestrator = _system(tmp_path, monkeypatch)

    async def scenario():
        await _run(orchestrator, runs, "2026-02-14")
        count = len(ledger.blocks)
        unchanged = await _run(orchestrator, runs, "2026-02-14", recalc=True, reason="new_nwp")
        assert unchanged.decision == "NO_CHANGE"
        assert unchanged.events[-1]["detail"]["published"] is False
        assert len(ledger.blocks) == count

        version["value"] = "b"
        changed = await _run(orchestrator, runs, "2026-02-14", recalc=True, reason="new_nwp")
        block = ledger.blocks[-1]
        assert block["type"] == "REVISION"
        assert block["revision_kind"] == "weather_input_update"
        assert block["recalculation"]["input_changed"] is True
        assert block["recalculation"]["previous_issue_date"] == "2026-02-14"
        assert block["recalculation"]["old_input_sha256"] != block["recalculation"]["new_input_sha256"]
        assert block["recalculation"]["overlap_hours"] == 48
        assert block["recalculation"]["mae"] is not None
        assert block["recalculation"]["max_abs"] is not None
        assert block["recalculation"]["forecast_materially_changed"] is False
        assert changed.events[-1]["detail"]["published"] is True
        assert ledger.verify()["valid"]

        manual = await _run(orchestrator, runs, "2026-02-14", recalc=True,
                            reason="manual_uncertainty_review")
        assert manual.status == "done"
        assert ledger.blocks[-1]["type"] == "REVISION"
        assert ledger.blocks[-1]["revision_kind"] == "manual_uncertainty_review"
        assert ledger.blocks[-1]["recalculation"]["input_changed"] is False
        assert "manual uncertainty review" in ledger.blocks[-1]["note"]

    asyncio.run(scenario())


def test_next_issue_compares_only_overlapping_target_input_hashes(tmp_path, monkeypatch):
    version, _, ledger, runs, orchestrator = _system(tmp_path, monkeypatch)

    async def scenario():
        await _run(orchestrator, runs, "2026-02-14")
        version["value"] = "b"
        next_issue = await _run(orchestrator, runs, "2026-02-15")
        block = ledger.blocks[-1]
        comparison = block["recalculation"]
        assert block["type"] == "FORECAST"
        assert comparison["path"] == "historical_overlap"
        assert comparison["previous_issue_date"] == "2026-02-14"
        assert comparison["overlap_hours"] == 24
        assert comparison["input_changed"] is True
        assert comparison["old_input_sha256"] != comparison["new_input_sha256"]
        assert comparison["mae"] is not None and comparison["max_abs"] is not None
        assert next_issue.result["recalculation"] == comparison
        assert any(event["stage"] == "RECALC" and event["detail"].get("path") == "historical_overlap"
                   for event in next_issue.events)
        assert ledger.verify()["valid"]

    asyncio.run(scenario())


def test_watcher_triggers_once_per_changed_input_version(tmp_path, monkeypatch):
    version, fetch, ledger, runs, orchestrator = _system(tmp_path, monkeypatch)

    async def scenario():
        await _run(orchestrator, runs, "2026-02-14")
        watcher = NWPWatcher(orchestrator, runs, issue_date="2026-02-14", fetch_nwp=fetch)
        assert (await watcher.poll_once())["status"] == "unchanged"
        version["value"] = "b"
        triggered = await watcher.poll_once()
        assert triggered["status"] == "triggered"
        assert (await watcher.poll_once())["status"] in {"already_triggered", "run_in_progress"}
        assert watcher._active_run is not None
        await watcher._active_run
        assert (await watcher.poll_once())["status"] == "unchanged"
        assert sum(block["type"] == "REVISION" for block in ledger.blocks) == 1
        watcher.start()
        await asyncio.sleep(0)
        assert watcher._task is not None and not watcher._task.done()
        await watcher.stop()
        assert watcher._task.done()

    asyncio.run(scenario())


def test_batch_explicitly_uses_historical_overlap_path(monkeypatch):
    calls = []

    class FakeOrchestrator:
        async def run(self, run, **kwargs):
            calls.append((run.issue_date, kwargs))
            run.status, run.decision = "done", "ACCEPT"

    class FakeRuns:
        def create(self, issue_date, mode):
            return SimpleNamespace(issue_date=issue_date, status="running", decision=None)

    monkeypatch.setattr(batch_module, "app", SimpleNamespace(state=SimpleNamespace(
        runs=FakeRuns(), orchestrator=FakeOrchestrator())))
    monkeypatch.setattr(batch_module, "ml", SimpleNamespace(
        list_issue_dates=lambda mode: ["2026-02-14", "2026-02-15"]))
    asyncio.run(batch_module.main("test"))
    assert len(calls) == 2
    assert all(options["compare_previous_issue"] is True and options["use_llm"] is False
               for _, options in calls)
