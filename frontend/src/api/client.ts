import type { AgentEvent, AgentRun, Economics, ForecastResult, FarmMeta, Health, LedgerData, LedgerVerification, Metrics, Mode, Variant } from './types'

export const mockMode = import.meta.env.VITE_USE_MOCKS !== '0'
const baseUrl = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '')

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${baseUrl}${path}`, init)
  if (!response.ok) {
    let message = `Request failed (${response.status})`
    try { message = (await response.json()).detail || message } catch { /* Preserve status. */ }
    throw new Error(message)
  }
  return response.json() as Promise<T>
}

async function fixture<T>(name: string): Promise<T> {
  const response = await fetch(`/mocks/${name}.json`)
  if (!response.ok) throw new Error(`Missing demo fixture: ${name}`)
  return response.json() as Promise<T>
}

function shiftUtc(value: string, days: number): string {
  return new Date(new Date(value).getTime() + days * 86_400_000).toISOString().replace('.000Z', 'Z')
}

function shiftLocal(value: string, days: number): string {
  const source = new Date(value)
  const shifted = new Date(source.getTime() + days * 86_400_000 + 5 * 3_600_000)
  return shifted.toISOString().slice(0, 19) + '+05:00'
}

function adaptForecast(source: ForecastResult, issueDate: string, mode: Mode, variant: Variant): ForecastResult {
  const days = Math.round((new Date(`${issueDate}T00:00:00Z`).getTime() - new Date(`${source.issue_date}T00:00:00Z`).getTime()) / 86_400_000)
  // The shared demo fixture contains a briefing claiming 44% day-ahead output,
  // while its 48 hourly rows and summary calculate to 12%. Never present that
  // text as numerically grounded; live mode receives the backend briefing intact.
  const dayAhead = Math.round(source.summary.dayahead_mean_p50 * 100)
  const band = Math.round(source.summary.mean_band * 100)
  const demoBriefing: ForecastResult['briefing'] = source.briefing ? {
    en: { lang: 'en', headline: `${dayAhead}% expected mean output in the day-ahead window`, summary: `The hourly forecast implies ${dayAhead}% mean power at leads 24–47, with a ${band}-point average P10–P90 band. Demo figures are representative.`, risks: source.flags.length ? [{ code: 'FORECAST_RISK', text: 'Review the risk flags and uncertainty interval before dispatch.' }] : [], actions: ['Check the hourly forecast and reserve margin before scheduling.'], confidence: 'medium', grounded: true, generated_by: 'template' },
    ru: { lang: 'ru', headline: `Ожидаемая средняя выработка на сутки вперёд: ${dayAhead}%`, summary: `По часовому прогнозу средняя мощность на горизонте 24–47 ч составляет ${dayAhead}%; средняя ширина интервала P10–P90 — ${band} п.п. Данные демонстрационные.`, risks: source.flags.length ? [{ code: 'FORECAST_RISK', text: 'Проверьте флаги риска и интервал неопределённости.' }] : [], actions: ['Перед планированием проверьте почасовой прогноз и резерв.'], confidence: 'medium', grounded: true, generated_by: 'template' },
    kk: { lang: 'kk', headline: `Алдағы тәуліктегі орташа өндіріс болжамы: ${dayAhead}%`, summary: `24–47 сағаттағы орташа қуат ${dayAhead}%, ал P10–P90 аралығының орташа ені ${band} пайыздық тармақ. Бұл — демонстрациялық деректер.`, risks: source.flags.length ? [{ code: 'FORECAST_RISK', text: 'Тәуекел белгілері мен белгісіздік аралығын тексеріңіз.' }] : [], actions: ['Жоспарлау алдында сағаттық болжам мен резервті қараңыз.'], confidence: 'medium', grounded: true, generated_by: 'template' },
  } : null
  return {
    ...source, issue_date: issueDate, issue_time: shiftUtc(source.issue_time, days), mode, variant,
    briefing: demoBriefing,
    max_nwp_init_time_used: shiftUtc(source.max_nwp_init_time_used, days),
    max_scada_time_used: source.max_scada_time_used ? shiftUtc(source.max_scada_time_used, days) : null,
    rows: source.rows.map(row => ({ ...row, target_time: shiftUtc(row.target_time, days), target_time_local: shiftLocal(row.target_time_local, days), actual: mode === 'test' ? null : row.actual })),
    flags: source.flags.map(flag => ({ ...flag, start: shiftUtc(flag.start, days), end: shiftUtc(flag.end, days) })),
  }
}

export async function getHealth(): Promise<Health> { return mockMode ? fixture('health') : api('/api/health') }
export async function getMeta(): Promise<FarmMeta> { return mockMode ? fixture('meta') : api('/api/meta') }
export async function getForecast(issueDate: string, mode: Mode, variant: Variant): Promise<ForecastResult> {
  if (mockMode) return adaptForecast(await fixture<ForecastResult>('forecast'), issueDate, mode, variant)
  return api(`/api/forecast?${new URLSearchParams({ issue_date: issueDate, mode, variant })}`)
}
export async function getMetrics(mode: Mode): Promise<Metrics> {
  if (mockMode) return { ...(await fixture<Metrics>('backtest_val_feb2025')), mode }
  return api(`/api/backtest?${new URLSearchParams({ mode })}`)
}
export async function getSeries(mode: Mode): Promise<{ mode: Mode; rows: { target_time: string; p10: number; p50: number; p90: number; actual: number | null }[] }> {
  if (mockMode) return { ...(await fixture<{ mode: Mode; rows: { target_time: string; p10: number; p50: number; p90: number; actual: number | null }[] }>('series_val_feb2025')), mode }
  return api(`/api/series?${new URLSearchParams({ mode })}`)
}
export async function getLedger(): Promise<LedgerData> { return mockMode ? fixture('ledger') : api('/api/ledger') }
export async function verifyLedger(): Promise<LedgerVerification> { return mockMode ? fixture('ledger_verify') : api('/api/ledger/verify', { method: 'POST' }) }
export async function tamperLedger(blockIndex: number): Promise<LedgerVerification> {
  if (mockMode) return { ...(await fixture<LedgerVerification>('ledger_tamper')), first_bad_block: blockIndex, errors: [{ block_index: blockIndex, reason: 'payload_sha256 mismatch' }] }
  return api('/api/ledger/tamper-demo', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ block_index: blockIndex }) })
}
export async function getEconomics(mode: Mode, capacityMw: number, priceKztMwh: number): Promise<Economics> {
  if (mockMode) {
    const data = await fixture<Economics>('economics')
    const factor = capacityMw / data.capacity_mw * priceKztMwh / data.price_kzt_mwh
    return { ...data, mode, capacity_mw: capacityMw, price_kzt_mwh: priceKztMwh,
      imbalance_mwh: Object.fromEntries(Object.entries(data.imbalance_mwh).map(([key, value]) => [key, value * capacityMw / data.capacity_mw])),
      cost_kzt: Object.fromEntries(Object.entries(data.cost_kzt).map(([key, value]) => [key, Math.round(value * factor)])),
      savings_vs_persistence_kzt: Math.round(data.savings_vs_persistence_kzt * factor), annualized_savings_kzt: Math.round(data.annualized_savings_kzt * factor) }
  }
  return api(`/api/economics?${new URLSearchParams({ mode, capacity_mw: String(capacityMw), price_kzt_mwh: String(priceKztMwh) })}`)
}

const mockRuns = new Map<string, AgentRun>()
const mockRecalculations = new Set<string>()
export async function startAgent(issueDate: string, mode: Mode, recalc = false): Promise<{ run_id: string }> {
  if (mockMode) {
    const runId = `r_${issueDate.replaceAll('-', '')}_${Date.now().toString(36)}`
    mockRuns.set(runId, { run_id: runId, issue_date: issueDate, mode, status: 'running', events: [], result: null })
    if (recalc) mockRecalculations.add(runId)
    return { run_id: runId }
  }
  return api(recalc ? '/api/agent/recalc' : '/api/agent/run', { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(recalc ? { issue_date: issueDate, mode, reason: 'new_nwp' } : { issue_date: issueDate, mode, use_llm: true }) })
}
export async function getRun(runId: string): Promise<AgentRun> {
  if (mockMode) {
    const run = mockRuns.get(runId)
    if (!run) throw new Error('Demo run not found')
    return run
  }
  return api(`/api/agent/runs/${encodeURIComponent(runId)}`)
}
export async function getRuns(): Promise<Pick<AgentRun, 'run_id' | 'issue_date' | 'status' | 'decision'>[]> {
  return mockMode ? [...mockRuns.values()].reverse() : api('/api/agent/runs')
}

export function openAgentStream(runId: string, onEvent: (event: AgentEvent) => void, onError: (message: string) => void): () => void {
  if (mockMode) {
    let cancelled = false
    let timer: number | undefined
    Promise.all([fixture<AgentEvent[]>('agent_events'), fixture<ForecastResult>('forecast')]).then(([events, sampleForecast]) => {
      const run = mockRuns.get(runId)
      if (!run) throw new Error('Demo run not found')
      const previousDate = new Date(new Date(`${run.issue_date}T00:00:00Z`).getTime() - 86_400_000).toISOString().slice(0, 10)
      const sequence: AgentEvent[] = mockRecalculations.has(runId) ? [{
        run_id: runId, seq: 0, ts: new Date().toISOString(), stage: 'RECALC', type: 'recalc',
        title: `New archived weather run triggers a revised forecast for ${run.issue_date}`,
        detail: { reason: 'new_nwp', demo: true }, actor: 'orchestrator', llm: null, duration_ms: null,
      }, ...events] : events
      let index = 0
      const tick = () => {
        if (cancelled || index >= sequence.length) return
        const source = sequence[index]
        let title = source.title.replaceAll('2026-02-14', run.issue_date).replaceAll('2026-02-13', previousDate).replaceAll('44%', `${Math.round(sampleForecast.summary.dayahead_mean_p50 * 100)}%`)
        if (source.stage === 'PUBLISH' && typeof source.detail.hash === 'string') title = `Sample ledger publication · block #${source.detail.block_index} · ${source.detail.hash.slice(0, 8)}…`
        const event = { ...source, title, run_id: runId, seq: index, ts: new Date().toISOString() }
        index += 1
        mockRuns.get(runId)?.events.push(event)
        if (event.type === 'done') {
          const run = mockRuns.get(runId)
          if (run) { run.status = 'done'; run.decision = String(event.detail.decision || 'ACCEPT') }
        }
        onEvent(event)
        timer = window.setTimeout(tick, 220)
      }
      tick()
    }).catch(error => onError(String(error)))
    return () => { cancelled = true; if (timer) window.clearTimeout(timer) }
  }
  const source = new EventSource(`${baseUrl}/api/agent/stream/${encodeURIComponent(runId)}`)
  source.addEventListener('agent', message => {
    try {
      const event = JSON.parse((message as MessageEvent).data) as AgentEvent
      onEvent(event)
      if (event.type === 'done' || event.type === 'error') source.close()
    } catch { onError('Agent sent an unreadable event'); source.close() }
  })
  source.onerror = () => { onError('Agent stream disconnected'); source.close() }
  return () => source.close()
}
