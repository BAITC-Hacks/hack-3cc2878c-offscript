import { useEffect, useState } from 'react'
import { Activity, BarChart3, Coins, FileClock, ShieldCheck, Wind } from 'lucide-react'
import clsx from 'clsx'
import { getHealth, getMeta, mockMode } from './api/client'
import type { FarmMeta, Health, Mode } from './api/types'
import { Status } from './components/Shared'
import { AgentPage } from './pages/AgentPage'
import { BacktestPage } from './pages/BacktestPage'
import { EconomicsPage } from './pages/EconomicsPage'
import { ForecastPage } from './pages/ForecastPage'
import { LedgerPage } from './pages/LedgerPage'

type Page = 'forecast' | 'agent' | 'backtest' | 'ledger' | 'economics'
const tabs = [
  { key: 'forecast', label: 'Forecast', icon: Activity },
  { key: 'agent', label: 'Agent console', icon: FileClock },
  { key: 'backtest', label: 'Backtest & skill', icon: BarChart3 },
  { key: 'ledger', label: 'Ledger', icon: ShieldCheck },
  { key: 'economics', label: 'Economics', icon: Coins },
] as const

export default function App() {
  const [page, setPage] = useState<Page>('forecast')
  const [mode, setMode] = useState<Mode>('test')
  const [meta, setMeta] = useState<FarmMeta | null>(null)
  const [health, setHealth] = useState<Health | null>(null)
  const [metaError, setMetaError] = useState('')
  const [bootstrapRevision, setBootstrapRevision] = useState(0)
  const [issueDate, setIssueDate] = useState('2026-02-14')
  const [ledgerRevision, setLedgerRevision] = useState(0)

  useEffect(() => { setMetaError(''); Promise.all([getMeta(), getHealth()]).then(([farm, status]) => { setMeta(farm); setHealth(status) }).catch(error => setMetaError(error.message)) }, [bootstrapRevision])
  const dates = meta?.issue_dates?.[mode] || []
  const dateIndex = Math.max(0, dates.indexOf(issueDate))
  const demo = mockMode || health?.ml_stub === true

  function chooseMode(next: Mode) {
    setMode(next)
    const options = meta?.issue_dates?.[next] || []
    setIssueDate(options.includes('2026-02-14') ? '2026-02-14' : options[Math.floor(options.length / 2)] || '')
  }

  return <div className="app-shell"><header className="app-header"><div className="brand"><div className="brand-mark"><Wind size={24} strokeWidth={2.2} /></div><div><strong>OpenWind</strong><span>Wind forecast control room</span></div></div><div className="header-right"><span className="farm-label">Shelek corridor · 2 turbines</span>{metaError ? <Status type="critical">API offline</Status> : !health ? <Status type="neutral">Connecting</Status> : demo ? <Status type="warn">Demo data</Status> : <Status type="ok">Live API</Status>}{!metaError ? <span className="header-live"><i /> SYSTEM ONLINE</span> : null}</div></header>
    <nav className="top-nav" aria-label="Main navigation">{tabs.map(tab => { const Icon = tab.icon; return <button key={tab.key} className={clsx('nav-tab', page === tab.key && 'nav-active')} aria-current={page === tab.key ? 'page' : undefined} onClick={() => setPage(tab.key)}><Icon size={17} />{tab.label}</button> })}</nav>
    <main className="main-content">{metaError ? <div className="error-state" role="alert">API metadata unavailable: {metaError}. Start the backend or set VITE_USE_MOCKS=1. <button className="button button-secondary" onClick={() => setBootstrapRevision(value => value + 1)}>Retry connection</button></div> : null}
      {meta && (page === 'forecast' || page === 'agent') ? <div className="context-bar"><div className="context-left"><label className="select-label">Issue schedule<select value={mode} onChange={event => chooseMode(event.target.value as Mode)}><option value="test">February 2026 · test</option><option value="val_feb2025">February 2025 · validation</option><option value="val_winter">Winter 2025–26 · validation</option></select></label><label className="select-label">Issue date<select value={issueDate} onChange={event => setIssueDate(event.target.value)}>{dates.map(date => <option value={date} key={date}>{date}</option>)}</select></label></div><div className="context-slider"><span>Earlier</span><input aria-label="Issue date slider" type="range" min="0" max={Math.max(dates.length - 1, 0)} value={dateIndex} onChange={event => setIssueDate(dates[Number(event.target.value)] || issueDate)} /><span>Later</span></div><span className="context-count">Issue {dateIndex + 1} of {dates.length}</span></div> : null}
      {demo ? <div className="demo-note">Representative fixture data. Dates and controls are interactive; switch VITE_USE_MOCKS=0 and USE_ML_STUB=0 for model-generated results.</div> : null}
      {page === 'forecast' && meta ? <ForecastPage issueDate={issueDate} mode={mode} /> : null}
      {page === 'agent' && meta ? <AgentPage issueDate={issueDate} mode={mode} onForecastPublished={() => setLedgerRevision(value => value + 1)} /> : null}
      {page === 'backtest' ? <BacktestPage /> : null}
      {page === 'ledger' ? <LedgerPage revision={ledgerRevision} /> : null}
      {page === 'economics' ? <EconomicsPage /> : null}
      {!meta && page !== 'backtest' && page !== 'ledger' && page !== 'economics' && !metaError ? <div className="loading">Loading farm configuration…</div> : null}
    </main><footer className="app-footer"><span>OpenWind · HackAlem AI 2026</span><span>Weather data by Open-Meteo.com · Times shown in Asia/Almaty</span></footer></div>
}
