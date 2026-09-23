import { Bot, CheckCircle2, Circle, Database, ShieldCheck, Wrench } from 'lucide-react'
import type { AgentEvent } from '../api/types'
import { Disclosure, localTime } from './Shared'

const actorIcon = { orchestrator: Bot, critic: ShieldCheck, tool: Wrench, ledger: Database }

export function AgentTimeline({ events }: { events: AgentEvent[] }) {
  if (!events.length) return <div className="empty-state">Start an agent run to see each decision and tool result as it happens.</div>
  return <ol className="agent-timeline">{events.map(event => {
    const Icon = actorIcon[event.actor] || Circle
    const isFailure = event.type === 'error' || event.type === 'warning' || (event.type === 'critic' && event.detail.approve === false)
    return <li key={`${event.run_id}-${event.seq}`} className={isFailure ? 'event event-warning' : 'event'}><div className="event-icon"><Icon size={17} /></div><div className="event-card"><div className="event-meta"><span className="stage">{event.stage}</span><span>{localTime(event.ts)}</span>{event.llm?.cached ? <span className="tag">LLM cached</span> : null}{event.duration_ms ? <span>{event.duration_ms} ms</span> : null}</div><strong>{event.title}</strong>{event.type === 'done' ? <span className="event-done"><CheckCircle2 size={14} /> Completed</span> : null}{Object.keys(event.detail || {}).length ? <Disclosure label="Inspect decision and evidence"><pre>{JSON.stringify(event.detail, null, 2)}</pre></Disclosure> : null}</div></li>
  })}</ol>
}
