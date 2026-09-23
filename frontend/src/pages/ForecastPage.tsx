import { useEffect, useState } from 'react'
import { Download, RefreshCw } from 'lucide-react'
import { getForecast, getRun, getRuns, mockMode } from '../api/client'
import type { ForecastResult, Mode, Variant } from '../api/types'
import { FanChart } from '../components/FanChart'
import { BriefingCard, EmptyState, ErrorState, FlagChips, Metric, Panel, ProofStrip, Status, localTime, number, percent } from '../components/Shared'

function downloadRows(forecast: ForecastResult) {
  const columns = ['target_time_local', 'target_time', 'lead_h', 'p10', 'p50', 'p90', 'actual'] as const
  const csv = [columns.join(','), ...forecast.rows.map(row => columns.map(column => row[column] ?? '').join(','))].join('\n')
  const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }))
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = `samal_${forecast.issue_date}_${forecast.variant}_48h.csv`
  anchor.click()
  URL.revokeObjectURL(url)
}

export function ForecastPage({ issueDate, mode }: { issueDate: string; mode: Mode }) {
  const [variant, setVariant] = useState<Variant>('hybrid')
  const [variantReady, setVariantReady] = useState(mockMode)
  const [forecast, setForecast] = useState<ForecastResult | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [showModels, setShowModels] = useState(false)
  const [showAllRows, setShowAllRows] = useState(false)
  const [revision, setRevision] = useState(0)

  useEffect(() => {
    let active = true
    setVariantReady(false)
    setForecast(null)
    if (mockMode) { setVariant('hybrid'); setVariantReady(true); return () => { active = false } }
    getRuns().then(async runs => {
      const published = runs.find(run => run.issue_date === issueDate && run.status === 'done')
      if (!published) return null
      return getRun(published.run_id)
    }).then(run => {
      if (active) setVariant(run?.mode === mode && run.result?.ledger?.verified ? run.result.variant : 'hybrid')
    }).catch(() => { if (active) setVariant('hybrid') }).finally(() => { if (active) setVariantReady(true) })
    return () => { active = false }
  }, [issueDate, mode])

  useEffect(() => {
    if (!variantReady) return
    let active = true
    setLoading(true)
    setError('')
    setForecast(null)
    getForecast(issueDate, mode, variant).then(value => { if (active) setForecast(value) }).catch(cause => { if (active) setError(cause.message) }).finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [issueDate, mode, variant, revision, variantReady])

  if (error) return <ErrorState message={error} retry={() => setRevision(value => value + 1)} />
  if ((!variantReady || loading) && !forecast) return <div className="loading">Loading 48 hourly forecasts…</div>
  if (!forecast) return <EmptyState message="No forecast is available for this issue date." />
  return <div className="page-stack">
    <div className="page-intro"><div><h1>Forecast operations</h1><p>Hourly generation forecast for the two turbine Shelek wind farm. Power is normalized to farm capacity.</p></div><div className="page-actions"><label className="select-label">Model variant<select value={variant} onChange={event => setVariant(event.target.value as Variant)}><option value="hybrid">Hybrid quantile</option><option value="mos_pc">MOS + power curve</option><option value="raw_pc">Raw weather + curve</option><option value="climatology">Climatology</option><option value="persistence">Persistence</option></select></label><button className="button button-secondary" onClick={() => setRevision(value => value + 1)} aria-label="Refresh forecast"><RefreshCw size={16} /> Refresh</button></div></div>
    <ProofStrip forecast={forecast} demo={mockMode} />
    <div className="forecast-grid"><Panel title="48 hour power outlook" caption="Median output, calibrated uncertainty, and the day-ahead delivery window" className="forecast-chart-panel" action={<label className="switch"><input type="checkbox" checked={showModels} onChange={event => setShowModels(event.target.checked)} /> Show NWP wind</label>}><FanChart forecast={forecast} showModels={showModels} showActual={mode !== 'test'} /><div className="chart-legend-note">The shaded P10–P90 interval shows plausible output. Dashed model lines use the right wind-speed axis when enabled.</div></Panel><div className="forecast-side"><div className="metric-grid"><Metric label="48 h energy · P50" value={`${number(forecast.summary.energy_p50_mwh)} MWh`} detail="Capacity based on configured assumption" tone="teal" /><Metric label="Day-ahead mean" value={percent(forecast.summary.dayahead_mean_p50)} detail="Leads 24–47" /><Metric label="Mean interval width" value={percent(forecast.summary.mean_band)} detail="P90 minus P10" /><Metric label="Peak upper bound" value={percent(forecast.summary.max_p90)} detail="Maximum P90 across horizon" /></div><Panel title="Operator risk scan" caption="Flags from forecast analysis"><FlagChips flags={forecast.flags} /></Panel><Panel title="Dispatcher briefing" caption="EN · RU · KZ, based on computed facts"><BriefingCard briefing={forecast.briefing} /></Panel></div></div>
    <Panel title="Hourly forecast" caption="All 48 issued hours, including the 24–47 day-ahead delivery window" action={<button className="button button-secondary" onClick={() => downloadRows(forecast)}><Download size={16} /> Export CSV</button>}><div className="table-toolbar"><button className="text-button" onClick={() => setShowAllRows(value => !value)}>{showAllRows ? 'Show first 12 hours' : 'Show all 48 hours'}</button><Status type={!mockMode && forecast.ledger?.verified ? 'ok' : 'neutral'}>{mockMode ? `Sample block #${forecast.ledger?.block_index ?? '—'}` : forecast.ledger?.verified ? `Sealed in block #${forecast.ledger.block_index}` : 'Awaiting ledger verification'}</Status></div><div className="table-scroll"><table><thead><tr><th>Local time</th><th>Lead</th><th>Product</th><th>P10</th><th>P50</th><th>P90</th><th>Wind</th><th>Actual</th></tr></thead><tbody>{forecast.rows.slice(0, showAllRows ? 48 : 12).map(row => <tr key={row.lead_h} className={row.lead_h >= 24 && row.lead_h <= 47 ? 'dayahead-row' : ''}><td>{localTime(row.target_time)}</td><td>+{row.lead_h} h</td><td>{row.lead_h >= 24 && row.lead_h <= 47 ? 'Day-ahead' : 'Intraday'}</td><td>{percent(row.p10)}</td><td className="value-primary">{percent(row.p50)}</td><td>{percent(row.p90)}</td><td>{row.v_hub_mean == null ? '—' : `${number(row.v_hub_mean)} m/s`}</td><td>{row.actual == null ? '—' : percent(row.actual)}</td></tr>)}</tbody></table></div></Panel>
  </div>
}
