from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field


Mode = Literal["test", "val_feb2025", "val_winter"]
Variant = Literal["hybrid", "mos_pc", "raw_pc", "climatology", "persistence"]
Stage = Literal["PLAN", "FETCH", "QC", "PREDICT", "ANALYZE", "DECIDE", "CRITIC", "BRIEF", "PUBLISH", "RECALC", "DONE"]


class OpenWindModel(BaseModel):
    model_config = ConfigDict(protected_namespaces=())


class RiskFlag(OpenWindModel):
    code: str
    severity: Literal["info", "warn", "critical"]
    start: str
    end: str
    value: float | None = None
    message: str


class ForecastRow(OpenWindModel):
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


class ForecastResult(OpenWindModel):
    issue_date: str
    issue_time: str
    mode: Mode
    variant: Variant
    model_version: str
    nwp_models_used: list[str]
    max_nwp_init_time_used: str
    max_estimated_nwp_init_time_used: str
    availability_basis: str
    availability_policy_version: str
    source_release_time_verified: Literal[False]
    source_release_time_evidence: str
    configured_latency_h: int
    max_scada_time_used: str | None = None
    latency_h: int
    capacity_mw: float
    widen: float = 0
    rows: list[ForecastRow]
    summary: dict[str, float]
    flags: list[RiskFlag] = Field(default_factory=list)
    nwp_input_fingerprints: dict[str, str] | None = None
    recalculation: dict[str, Any] | None = None


class BriefingRisk(OpenWindModel):
    code: str
    text: str


class BriefingItem(OpenWindModel):
    lang: Literal["en", "ru", "kk"]
    headline: str
    summary: str
    risks: list[BriefingRisk]
    actions: list[str]
    confidence: Literal["low", "medium", "high"]
    grounded: bool
    generated_by: Literal["llm", "template"]


class Briefings(OpenWindModel):
    en: BriefingItem
    ru: BriefingItem
    kk: BriefingItem


class AgentEvent(OpenWindModel):
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


class AgentRunRequest(OpenWindModel):
    issue_date: str
    mode: Mode = "test"
    use_llm: bool = True


class RecalcRequest(OpenWindModel):
    issue_date: str
    mode: Mode = "test"
    reason: str = "new_nwp"
    use_llm: bool = True


class LedgerBlock(OpenWindModel):
    index: int
    type: str
    prev_hash: str
    hash: str
    created_at: str
    issue_date: str | None = None
    issue_time: str | None = None
    payload_sha256: str | None = None
    payload_file_sha256: str | None = None
    payload_file: str | None = None
    model_version: str | None = None
    inputs_sha256: str | None = None
    max_nwp_init_time_used: str | None = None
    max_estimated_nwp_init_time_used: str | None = None
    availability_basis: str | None = None
    availability_policy_version: str | None = None
    source_release_time_verified: bool | None = None
    source_release_time_evidence: str | None = None
    configured_latency_h: int | None = None
    availability_evidence_status: str | None = None
    max_scada_time_used: str | None = None
    latency_h: int | None = None
    note: str | None = None
    revision_kind: Literal["weather_input_update", "manual_uncertainty_review", "legacy_manual_uncertainty_review"] | None = None
    recalculation: dict[str, Any] | None = None


class PlannerDecision(OpenWindModel):
    steps: list[str]
    variant: Variant = "hybrid"
    models: list[str] = Field(default_factory=list)
    reasoning: str = ""


class DeciderDecision(OpenWindModel):
    action: Literal["ACCEPT", "RERUN", "WIDEN", "ESCALATE"]
    variant: Variant = "hybrid"
    widen: float = Field(default=0, ge=0, le=0.3)
    rationale: str = ""


class CriticDecision(OpenWindModel):
    approve: bool
    issues: list[str] = Field(default_factory=list)
    suggestion: DeciderDecision = Field(default_factory=lambda: DeciderDecision(action="ACCEPT"))
