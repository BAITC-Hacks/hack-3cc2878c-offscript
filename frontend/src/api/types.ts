export type Mode = 'test' | 'val_feb2025' | 'val_winter'
export type Variant = 'hybrid' | 'mos_pc' | 'raw_pc' | 'climatology' | 'persistence'

export interface FarmMeta {
  farm: { name: string; lat: number; lon: number; turbines: { id: string; lat: number; lon: number }[]; capacity_mw: number; capacity_is_assumption: boolean; hub_height_m: number; tz: string }
  nwp_models: string[]
  variants: Variant[]
  issue_dates: Record<Mode, string[]>
  temporal_guard: { latency_h: number; rule: string }
}

export interface RiskFlag {
  code: string
  severity: 'info' | 'warn' | 'critical'
  start: string
  end: string
  value: number | null
  message: string
}

export interface ForecastRow {
  target_time: string
  target_time_local: string
  lead_h: number
  lead_day: number
  p10: number
  p50: number
  p90: number
  v_hub_mean: number | null
  v_hub_spread: number | null
  nwp_v_hub: Record<string, number>
  pc_raw: number | null
  temp_c: number | null
  actual: number | null
}

export interface Briefing {
  lang: 'en' | 'ru' | 'kk'
  headline: string
  summary: string
  risks: { code: string; text: string }[]
  actions: string[]
  confidence: 'low' | 'medium' | 'high'
  grounded: boolean
  generated_by: 'llm' | 'template'
}

export interface ForecastResult {
  issue_date: string
  issue_time: string
  mode: Mode
  variant: Variant
  model_version: string
  nwp_models_used: string[]
  max_nwp_init_time_used: string
  max_estimated_nwp_init_time_used?: string
  availability_basis?: string
  availability_policy_version?: string
  source_release_time_verified?: false
  source_release_time_evidence?: string
  configured_latency_h?: number
  availability_evidence_status?: string
  max_scada_time_used: string | null
  latency_h: number
  capacity_mw: number
  widen: number
  rows: ForecastRow[]
  summary: { mean_p50: number; energy_p50_mwh: number; max_p90: number; mean_band: number; dayahead_mean_p50: number }
  flags: RiskFlag[]
  ledger?: { block_index: number; hash: string; verified: boolean } | null
  briefing?: { en: Briefing; ru: Briefing; kk: Briefing } | null
  nwp_input_fingerprints?: Record<string, string>
  recalculation?: RecalculationEvidence | null
}

export interface RecalculationEvidence {
  path: 'historical_overlap' | 'same_issue_recalculation'
  previous_issue_date: string
  previous_block_index: number
  old_input_sha256: string | null
  new_input_sha256: string | null
  input_changed: boolean | null
  overlap_hours: number
  mae: number | null
  max_abs: number | null
  forecast_materially_changed: boolean
  reason: string
  revision_kind?: 'weather_input_update' | 'manual_uncertainty_review'
}

export interface AgentEvent {
  run_id: string
  seq: number
  ts: string
  stage: string
  type: string
  title: string
  detail: Record<string, unknown>
  actor: 'orchestrator' | 'critic' | 'tool' | 'ledger'
  llm: { provider: string; model: string; cached: boolean; latency_ms: number } | null
  duration_ms: number | null
}

export interface AgentRun {
  run_id: string
  issue_date: string
  mode: Mode
  status: 'running' | 'done' | 'error'
  events: AgentEvent[]
  result: ForecastResult | null
  decision?: string | null
}

export interface Metrics {
  mode: Mode
  train_end: string
  n_issues: number
  n_hours: number
  leads: string
  models: Record<string, { nmae: number; nrmse: number; bias: number; skill_vs_persistence: number; pinball: number | null; picp_80: number | null }>
  mae_by_lead: { lead_h: number; hybrid: number; persistence: number; raw_pc: number }[]
  daily: { date: string; hybrid: number; persistence: number }[]
  reliability: { nominal: number; observed: number }[]
  feature_importance: { feature: string; importance: number }[]
}

export interface LedgerBlock {
  index: number
  type: string
  issue_date: string | null
  issue_time: string | null
  created_at: string
  note: string | null
  prev_hash: string
  hash: string
  payload_file?: string
  max_nwp_init_time_used?: string
  max_estimated_nwp_init_time_used?: string
  availability_policy_version?: string
  source_release_time_verified?: boolean
  availability_evidence_status?: string
  latency_h?: number
  revision_kind?: 'weather_input_update' | 'manual_uncertainty_review' | 'legacy_manual_uncertainty_review'
  recalculation?: RecalculationEvidence
}

export interface LedgerData { length: number; head_hash: string; blocks: LedgerBlock[] }
export interface LedgerVerification { valid: boolean; checked?: number; head_hash?: string; first_bad_block?: number; legacy_policy_evidence_blocks?: number[]; errors: { block_index: number; reason: string }[] }
export interface Economics {
  mode: Mode
  capacity_mw: number
  price_kzt_mwh: number
  assumption_note: string
  hours: number
  imbalance_mwh: Record<string, number>
  cost_kzt: Record<string, number>
  savings_vs_persistence_kzt: number
  savings_pct: number
  annualized_savings_kzt: number
}

export interface Health { status: string; version: string; llm_provider: string; weather_offline: boolean; ml_stub?: boolean }
