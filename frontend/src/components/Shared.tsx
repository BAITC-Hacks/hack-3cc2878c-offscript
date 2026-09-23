import { useState } from 'react'
import { AlertTriangle, CheckCircle2, ChevronDown, Database, ShieldCheck } from 'lucide-react'
import type { Briefing, ForecastResult, RiskFlag } from '../api/types'

export const percent = (value: number | null | undefined, digits = 0) => value == null || !Number.isFinite(value) ? '—' : `${(value * 100).toFixed(digits)}%`
export const number = (value: number | null | undefined, digits = 1) => value == null || !Number.isFinite(value) ? '—' : value.toLocaleString('en-US', { maximumFractionDigits: digits, minimumFractionDigits: digits })
export const localTime = (value: string) => new Intl.DateTimeFormat('en-GB', { timeZone: 'Asia/Almaty', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }).format(new Date(value))

export function Panel({ title, caption, children, className = '', action }: { title: string; caption?: string; children: React.ReactNode; className?: string; action?: React.ReactNode }) {
  return <section className={`panel ${className}`}><div className="panel-heading"><div><h2>{title}</h2>{caption ? <p>{caption}</p> : null}</div>{action}</div>{children}</section>
}

export function Metric({ label, value, detail, tone = 'default' }: { label: string; value: string; detail?: string; tone?: 'default' | 'teal' | 'amber' }) {
  return <div className={`metric metric-${tone}`}><span>{label}</span><strong>{value}</strong>{detail ? <small>{detail}</small> : null}</div>
}

export function Status({ type, children }: { type: 'ok' | 'warn' | 'critical' | 'neutral'; children: React.ReactNode }) {
  return <span className={`status status-${type}`}>{type === 'ok' ? <CheckCircle2 size={14} /> : type === 'warn' || type === 'critical' ? <AlertTriangle size={14} /> : <Database size={14} />}{children}</span>
}

export function ErrorState({ message, retry }: { message: string; retry?: () => void }) {
  return <div className="error-state" role="alert"><AlertTriangle size={22} /><div><strong>Could not load this view</strong><p>{message}</p></div>{retry ? <button className="button button-secondary" onClick={retry}>Retry</button> : null}</div>
}

export function EmptyState({ message }: { message: string }) { return <div className="empty-state">{message}</div> }

export function FlagChips({ flags }: { flags: RiskFlag[] }) {
  return <div className="flag-list">{flags.length ? flags.map((flag, index) => <div className={`flag flag-${flag.severity}`} key={`${flag.code}-${index}`}><span>{flag.code.replaceAll('_', ' ')}</span><small>{flag.message}</small></div>) : <Status type="ok">No risk flags for this issue</Status>}</div>
}

export function BriefingCard({ briefing }: { briefing: ForecastResult['briefing'] }) {
  const [language, setLanguage] = useState<'en' | 'ru' | 'kk'>('en')
  if (!briefing) return <EmptyState message="Run the agent to generate an operator briefing." />
  const item: Briefing = briefing[language]
  return <div className="briefing"><div className="briefing-top"><div className="mini-tabs" role="tablist" aria-label="Briefing language">{(['en', 'ru', 'kk'] as const).map(lang => <button key={lang} role="tab" aria-selected={language === lang} className={language === lang ? 'selected' : ''} onClick={() => setLanguage(lang)}>{lang === 'kk' ? 'KZ' : lang.toUpperCase()}</button>)}</div><Status type={item.grounded ? 'ok' : 'warn'}>{item.grounded ? 'Numbers checked' : 'Review numbers'}</Status></div><h3>{item.headline}</h3><p>{item.summary}</p>{item.risks.length ? <div className="briefing-risk"><strong>Risks</strong>{item.risks.map((risk, index) => <span key={`${risk.code}-${index}`}>{risk.text}</span>)}</div> : null}<div className="briefing-actions"><strong>Operator action</strong>{item.actions.map((action, index) => <span key={index}>{action}</span>)}</div><small>Confidence: {item.confidence} · {item.generated_by === 'llm' ? 'AI drafted, checked' : 'Rule based'}</small></div>
}

export function ProofStrip({ forecast, demo = false }: { forecast: ForecastResult; demo?: boolean }) {
  return <div className="proof-strip"><ShieldCheck size={18} /><div><strong>{demo ? 'Temporal guard preview · demo data' : 'Proof of no lookahead'}</strong><span>NWP initialized by {localTime(forecast.max_nwp_init_time_used)} · issued {localTime(forecast.issue_time)} · {forecast.latency_h} h publication margin</span></div>{forecast.ledger ? <span className="proof-hash">{demo ? 'Sample block' : 'Block'} #{forecast.ledger.block_index} · {forecast.ledger.hash.slice(0, 8)}…</span> : null}</div>
}

export function Disclosure({ label, children }: { label: string; children: React.ReactNode }) {
  const [open, setOpen] = useState(false)
  return <div className="disclosure"><button aria-expanded={open} onClick={() => setOpen(value => !value)}>{label}<ChevronDown size={14} className={open ? 'rotated' : ''} /></button>{open ? <div className="disclosure-body">{children}</div> : null}</div>
}
