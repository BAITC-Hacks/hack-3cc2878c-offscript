from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from ..ledger import Ledger, sha
from ..ml_bridge import ml
from ..runs import Run, RunRegistry
from ..schemas import Briefings, CriticDecision
from ..settings import settings
from . import policy
from .briefing import briefings_are_grounded, template
from .llm import LLM, LLMUnavailable


class Orchestrator:
    def __init__(self, ledger: Ledger, runs: RunRegistry, llm: LLM):
        self.ledger, self.runs, self.llm = ledger, runs, llm

    async def _pace(self) -> None:
        if settings.demo_pacing:
            await asyncio.sleep(0.25)

    async def _decision(self, run: Run, stage: str, system: str, user: str, schema: Any, fallback: Any) -> tuple[Any, dict[str, Any] | None]:
        try:
            decision, metadata = await self.llm.json(system, user, schema)
            return decision, metadata
        except LLMUnavailable as exc:
            await run.emit(stage, "warning", "LLM unavailable; deterministic policy fallback engaged", "orchestrator", detail={"reason": str(exc)})
            return fallback, None

    @staticmethod
    def _facts(forecast: dict[str, Any], flags: list[dict[str, Any]], inputs: dict[str, Any]) -> dict[str, Any]:
        rows = sorted(forecast["rows"], key=lambda row: row["p50"], reverse=True)[:6]
        return {"issue_time": forecast["issue_time"], "horizon_hours": 48, "dayahead_leads": [24, 47], "summary": forecast["summary"], "flags": [{"code": flag["code"], "severity": flag["severity"], "value": flag.get("value"), "message": flag.get("message"), "start": flag.get("start"), "end": flag.get("end")} for flag in flags],
                "input_spread_ms": inputs.get("spread_mean_ms"), "top_hours": [{"target_time": row["target_time"], "p50": row["p50"]} for row in rows]}

    def _write_forecast(self, forecast: dict[str, Any], run_id: str) -> Path:
        # A ledger block must never point at a mutable "latest forecast" path.
        path = settings.outputs_dir / "ledger_payloads" / f"{run_id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(forecast, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def _latest_published(self, issue_date: str, mode: str) -> tuple[dict[str, Any], dict[str, Any]] | None:
        for block in reversed(self.ledger.blocks):
            if block.get("issue_date") != issue_date or not block.get("payload_file"):
                continue
            path = (settings.repo_root / block["payload_file"]).resolve()
            if not path.is_relative_to(settings.repo_root.resolve()) or not path.exists():
                continue
            payload = json.loads(path.read_text(encoding="utf-8"))
            if payload.get("mode") == mode and sha(payload.get("rows", [])) == block.get("payload_sha256"):
                return block, payload
        return None

    async def run(self, run: Run, *, use_llm: bool, recalc: bool = False, reason: str | None = None) -> None:
        try:
            default_plan = policy.plan()
            if use_llm:
                plan, plan_meta = await self._decision(run, "PLAN", "You are SAMAL's forecasting planner. Return JSON only.",
                                                       f"Issue date={run.issue_date}. Use archived NWP only. Available models={default_plan.models}.",
                                                       type(default_plan), default_plan)
            else:
                plan, plan_meta = default_plan, None
            if not plan.models or any(model not in default_plan.models for model in plan.models):
                await run.emit("PLAN", "warning", "Planner chose unavailable weather models; safe default plan restored", "orchestrator")
                plan, plan_meta = default_plan, None
            await run.emit("PLAN", "stage_start", f"Planning leakage-proof forecast for {run.issue_date}", "orchestrator")
            await run.emit("PLAN", "llm_decision", f"Plan selected {plan.variant} with {len(plan.models)} weather models", "orchestrator",
                           detail=plan.model_dump(), llm=plan_meta)
            await self._pace()

            await run.emit("FETCH", "tool_call", "Fetching archived NWP inputs through TemporalGuard", "tool", detail={"models": plan.models})
            inputs = ml.fetch_nwp(run.issue_date, plan.models)
            await run.emit("FETCH", "tool_result", f"Fetched {len(inputs['models_ok'])} models; TemporalGuard metadata recorded", "tool", detail=inputs)
            await self._pace()

            qc = ml.check_inputs(run.issue_date)
            await run.emit("QC", "tool_result", "Input quality check completed", "tool", detail=qc)
            await self._pace()

            previous = self._latest_published(run.issue_date, run.mode) if recalc else None
            input_changed = bool(previous and previous[0].get("inputs_sha256") != inputs["inputs_sha256"])
            if recalc:
                await run.emit("RECALC", "recalc", "Updated weather detected" if input_changed else "Manual uncertainty review; archived weather unchanged",
                               "orchestrator", detail={"reason": reason, "input_changed": input_changed,
                                                       "previous_block": previous[0]["index"] if previous else None})
            widen = 0.05 if recalc and not input_changed else 0.0
            forecast = ml.run_forecast(run.issue_date, variant=plan.variant, widen=widen, models=plan.models, mode=run.mode)
            flags = ml.risk_scan(forecast)
            await run.emit("PREDICT", "tool_result", "Probabilistic 48-hour forecast computed by ML engine", "tool",
                           detail={"variant": plan.variant, "widen": widen, "summary": forecast["summary"]})
            await run.emit("ANALYZE", "tool_result", f"Risk scan found {len(flags)} operator-relevant flags", "tool", detail={"flags": flags})
            await self._pace()

            default_decision = policy.decide(inputs | qc, flags)
            if use_llm:
                facts = self._facts(forecast, flags, qc)
                decider, decider_meta = await self._decision(run, "DECIDE", "You are SAMAL's risk decider. Use only supplied facts. Return JSON only.", json.dumps(facts), type(default_decision), default_decision)
            else:
                decider, decider_meta = default_decision, None
            if decider.action in {"WIDEN", "RERUN"} or (decider.action == "ESCALATE" and decider.widen > 0):
                widen = max(widen, decider.widen)
                forecast = ml.run_forecast(run.issue_date, variant=decider.variant, widen=widen, models=plan.models, mode=run.mode)
                flags = ml.risk_scan(forecast)
                await run.emit("PREDICT", "tool_result", "Policy reran the ML forecast with its selected safeguards", "tool", detail={"widen": widen, "variant": decider.variant})
            await run.emit("DECIDE", "llm_decision", f"Decision: {decider.action}", "orchestrator", detail=decider.model_dump(), llm=decider_meta)
            await self._pace()

            loops = 0
            while True:
                default_critique = policy.critic(forecast, flags, decider)
                if use_llm:
                    critique, critic_meta = await self._decision(run, "CRITIC", "You are SAMAL's independent grid-operator critic. Audit only supplied facts. Return JSON only.",
                                                                  json.dumps(self._facts(forecast, flags, qc)), CriticDecision, default_critique)
                else:
                    critique, critic_meta = default_critique, None
                if not default_critique.approve and critique.approve:
                    critique = default_critique
                    await run.emit("CRITIC", "warning", "Deterministic physical audit vetoed LLM approval", "critic")
                await run.emit("CRITIC", "critic", "Independent forecast audit completed", "critic", detail=critique.model_dump(), llm=critic_meta)
                if critique.approve or loops >= 2:
                    break
                loops += 1
                widen = max(widen, critique.suggestion.widen)
                forecast = ml.run_forecast(run.issue_date, variant=critique.suggestion.variant, widen=widen, models=plan.models, mode=run.mode)
                flags = ml.risk_scan(forecast)
                await run.emit("PREDICT", "tool_result", "Critic requested a safer rerun", "tool", detail={"widen": widen, "loop": loops})
            if not critique.approve:
                decider.action = "ESCALATE"
                await run.emit("CRITIC", "warning", "Critic still rejects after two reruns; dispatcher escalation required", "critic")
            if recalc and previous:
                diff = ml.forecast_diff(previous[1], forecast)
                old_rows = {row["target_time"]: row for row in previous[1]["rows"]}
                diff["quantile_changed_hours"] = sum(
                    1 for row in forecast["rows"] if row["target_time"] in old_rows and
                    (row["p10"] != old_rows[row["target_time"]]["p10"] or
                     row["p90"] != old_rows[row["target_time"]]["p90"])
                )
                diff["mean_band_delta"] = round(forecast["summary"]["mean_band"] - previous[1]["summary"]["mean_band"], 6)
                await run.emit("RECALC", "tool_result", "Revision compared with the previous published forecast", "tool",
                               detail={"input_changed": input_changed, **diff})
            await self._pace()

            fallback_briefings = template(forecast, flags)
            briefing_meta = None
            if use_llm:
                briefing_candidate, briefing_meta = await self._decision(
                    run, "BRIEF", "Write a concise trilingual grid-operator briefing using only the provided computed facts. Return JSON only.",
                    json.dumps(self._facts(forecast, flags, qc)), Briefings, fallback_briefings,
                )
                if briefings_are_grounded(briefing_candidate, self._facts(forecast, flags, qc)):
                    for item in (briefing_candidate.en, briefing_candidate.ru, briefing_candidate.kk):
                        item.grounded, item.generated_by = True, "llm"
                    briefings = briefing_candidate
                else:
                    await run.emit("BRIEF", "warning", "LLM briefing failed numeric grounding; template retained", "orchestrator")
                    briefings = fallback_briefings
            else:
                briefings = fallback_briefings
            await run.emit("BRIEF", "briefing", "Generated EN/RU/KK dispatcher briefings from computed facts", "orchestrator",
                           detail={"grounded": True, "generated_by": briefings.en.generated_by}, llm=briefing_meta)
            forecast["briefing"] = briefings.model_dump()
            payload_path = self._write_forecast(forecast, run.run_id)
            if not any(block.get("model_version") == forecast["model_version"] for block in self.ledger.blocks):
                self.ledger.append("MODEL_TRAINED", [], issue_time=forecast["issue_time"], model_version=forecast["model_version"], note="Model observed by backend")
            relative_payload = payload_path.relative_to(settings.repo_root).as_posix()
            block_type = "REVISION" if recalc and previous else "FORECAST"
            block = self.ledger.append(block_type, forecast["rows"], issue_date=run.issue_date, issue_time=forecast["issue_time"],
                                       variant=forecast["variant"],
                                       model_version=forecast["model_version"], payload_file=relative_payload,
                                       inputs_sha256=inputs["inputs_sha256"], max_nwp_init_time_used=forecast["max_nwp_init_time_used"],
                                       max_scada_time_used=forecast.get("max_scada_time_used"), latency_h=forecast["latency_h"],
                                       note=(f"{reason or 'forecast'}: {decider.action} after {loops} critic loops"
                                             + (f"; input_changed={input_changed}" if recalc else "")))
            await run.emit("PUBLISH", "ledger", f"Published {block_type.lower()} as ledger block #{block['index']}", "ledger", detail={"block_index": block["index"], "hash": block["hash"]})
            forecast["ledger"] = {"block_index": block["index"], "hash": block["hash"], "verified": self.ledger.verify()["valid"]}
            run.result, run.decision, run.status = forecast, decider.action, "done"
            await run.emit("DONE", "done", "Agent cycle complete", "orchestrator", detail={"decision": decider.action, "block_index": block["index"], "loops": loops})
        except Exception as exc:
            run.status = "error"
            await run.emit("DONE", "error", "Agent cycle failed safely", "orchestrator", detail={"error": str(exc)})
        finally:
            self.runs.persist(run)
