import { useEffect, useState } from 'react'
import { ArrowRight } from 'lucide-react'
import { getEconomics } from '../api/client'
import type { Economics } from '../api/types'
import { ErrorState, Metric, Panel, number, percent } from '../components/Shared'

export function EconomicsPage() {
  const [capacity, setCapacity] = useState(5)
  const [price, setPrice] = useState(15000)
  const [data, setData] = useState<Economics | null>(null)
  const [error, setError] = useState('')
  useEffect(() => {
    let active = true
    const timer = window.setTimeout(() => { getEconomics('val_feb2025', capacity, price).then(value => { if (active) { setData(value); setError('') } }).catch(cause => { if (active) setError(cause.message) }) }, 180)
    return () => { active = false; window.clearTimeout(timer) }
  }, [capacity, price])
  return <div className="page-stack"><div className="page-intro"><div><h1>Economics & scale</h1><p>Translate validated forecast error into an illustrative balancing cost. Capacity and price are adjustable assumptions.</p></div></div>{error ? <ErrorState message={error} /> : null}<div className="economics-grid"><Panel title="Scenario assumptions" caption="Change inputs to see the cost model update"><label className="range-label"><span>Farm capacity <strong>{number(capacity, 1)} MW</strong></span><input type="range" min="1" max="100" step="0.5" value={capacity} onChange={event => setCapacity(Number(event.target.value))} /><small>Display and cost assumption; model output remains normalized 0–1.</small></label><label className="range-label"><span>Imbalance price <strong>{number(price, 0)} ₸/MWh</strong></span><input type="range" min="1000" max="50000" step="500" value={price} onChange={event => setPrice(Number(event.target.value))} /><small>Illustrative flat price, not a market settlement quote.</small></label></Panel><Panel title="Estimated value" caption="February 2025 validation versus a persistence baseline"><div className="savings-value">{data ? `${number(data.savings_vs_persistence_kzt, 0)} ₸` : 'Loading…'}</div><p className="savings-caption">Estimated avoided balancing cost for the validation month</p><div className="metric-grid"><Metric label="Relative savings" value={data ? percent(data.savings_pct / 100, 1) : '—'} /><Metric label="Annualized illustration" value={data ? `${number(data.annualized_savings_kzt, 0)} ₸` : '—'} /></div></Panel></div>{data ? <Panel title="Cost calculation" caption="Absolute forecast error × assumed MW capacity × assumed balancing price"><div className="cost-compare"><div><span>Hybrid forecast imbalance</span><strong>{number(data.imbalance_mwh.hybrid)} MWh</strong><small>{number(data.cost_kzt.hybrid, 0)} ₸</small></div><ArrowRight size={22} /><div><span>Persistence imbalance</span><strong>{number(data.imbalance_mwh.persistence)} MWh</strong><small>{number(data.cost_kzt.persistence, 0)} ₸</small></div></div></Panel> : null}<Panel title="Scale beyond Shelek" caption="The same forecasting flow can be retrained for another site with its coordinates and SCADA history"><div className="regions"><span>Shelek corridor</span><span>Ereymentau</span><span>Zhanatas</span><span>Shokpar</span></div><p className="small-copy">Next steps: multiple wind farms, portfolio aggregation, dispatch alerts, and bidding decisions informed by P10/P50/P90 risk.</p></Panel></div>
}
