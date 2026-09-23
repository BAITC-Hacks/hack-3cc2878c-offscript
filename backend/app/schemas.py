from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field


Mode = Literal["test", "val_feb2025", "val_winter"]
Variant = Literal["hybrid", "mos_pc", "raw_pc", "climatology", "persistence"]
Stage = Literal["PLAN", "FETCH", "QC", "PREDICT", "ANALYZE", "DECIDE", "CRITIC", "BRIEF", "PUBLISH", "RECALC", "DONE"]


class SamalModel(BaseModel):
    model_config = ConfigDict(protected_namespaces=())


class RiskFlag(SamalModel):
    code: str
    severity: Literal["info", "warn", "critical"]
    start: str
    end: str
    value: float | None = None
    message: str


class ForecastRow(SamalModel):
    target_time: str
    target_time_local: str
    lead_h: int = Field(ge=1, le=48)
    lead_day: int = Field(ge=1, le=3)
    p10: float = Field(ge=0, le=1)
    p50: float = Field(ge=0, le=1)
    p90: float = Field(ge=0, le=1)
    v_hub_mean: float | None = None
    v_hub_spread: float | None = None
    nwp_v_hub: dict[str, float] = Field(default_factory=dict)
    pc_raw: float | None = None
    temp_c: float | None = None
    actual: float | None = None


class ForecastResult(SamalModel):
    issue_date: str
    issue_time: str
    mode: Mode
    variant: Variant
    model_version: str
    nwp_models_used: list[str]
    max_nwp_init_time_used: str
    max_scada_time_used: str | None = None
    latency_h: int
    capacity_mw: float
    widen: float = 0
    rows: list[ForecastRow]
    summary: dict[str, float]
    flags: list[RiskFlag] = Field(default_factory=list)


class BriefingItem(SamalModel):
    lang: Literal["en", "ru", "kk"]
    headline: str
    summary: str
    risks: list[dict[str, str]] = Field(default_factory=list)
    actions: list[str] = Field(default_factory=list)
    confidence: Literal["low", "medium", "high"]
    grounded: bool
    generated_by: Literal["llm", "template"]


class Briefings(SamalModel):
    en: BriefingItem
    ru: BriefingItem
    kk: BriefingItem


class AgentEvent(SamalModel):
    run_id: str
    seq: int
    ts: str
    stage: Stage
    type: str
    title: str
    detail: dict[str, Any] = Field(default_factory=dict)
    actor: Literal["orchestrator", "critic", "tool", "ledger"]
    llm: dict[str, Any] | None = None
    duration_ms: int | None = None


class AgentRunRequest(SamalModel):
    issue_date: str
    mode: Mode = "test"
    use_llm: bool = True


class RecalcRequest(SamalModel):
    issue_date: str
    mode: Mode = "test"
    reason: str = "new_nwp"


class LedgerBlock(SamalModel):
    index: int
    type: str
    prev_hash: str
    hash: str
    created_at: str
    issue_date: str | None = None
    issue_time: str | None = None
    payload_sha256: str | None = None
    payload_file: str | None = None
    model_version: str | None = None
    inputs_sha256: str | None = None
    max_nwp_init_time_used: str | None = None
    max_scada_time_used: str | None = None
    latency_h: int | None = None
    note: str | None = None


class PlannerDecision(SamalModel):
    steps: list[str]
    variant: Variant = "hybrid"
    models: list[str] = Field(default_factory=list)
    reasoning: str = ""


class DeciderDecision(SamalModel):
    action: Literal["ACCEPT", "RERUN", "WIDEN", "ESCALATE"]
    variant: Variant = "hybrid"
    widen: float = Field(default=0, ge=0, le=0.3)
    rationale: str = ""


class CriticDecision(SamalModel):
    approve: bool
    issues: list[str] = Field(default_factory=list)
    suggestion: DeciderDecision = Field(default_factory=lambda: DeciderDecision(action="ACCEPT"))
