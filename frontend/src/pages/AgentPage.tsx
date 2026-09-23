import { useEffect, useRef, useState } from 'react'
import { Play, RotateCcw } from 'lucide-react'
import { getRun, getRuns, openAgentStream, startAgent } from '../api/client'
import type { AgentEvent, AgentRun, Mode } from '../api/types'
import { AgentTimeline } from '../components/AgentTimeline'
import { EmptyState, ErrorState, Panel, Status } from '../components/Shared'

export function AgentPage({ issueDate, mode, onForecastPublished }: { issueDate: string; mode: Mode; onForecastPublished: () => void }) {
  const [events, setEvents] = useState<AgentEvent[]>([])
  const [run, setRun] = useState<AgentRun | null>(null)
  const [history, setHistory] = useState<Pick<AgentRun, 'run_id' | 'issue_date' | 'status' | 'decision'>[]>([])
  const [error, setError] = useState('')
  const stopRef = useRef<(() => void) | null>(null)

  useEffect(() => { getRuns().then(setHistory).catch(() => undefined); return () => stopRef.current?.() }, [])

  function streamError(message: string) {
    setError(message)
    setRun(previous => previous?.status === 'running' ? { ...previous, status: 'error' } : previous)
  }

  function streamRun(runId: string) {
    stopRef.current = openAgentStream(runId, event => {
      setEvents(previous => previous.some(item => item.seq === event.seq) ? previous : [...previous, event])
      if (event.type === 'done' || event.type === 'error') {
        setRun(previous => previous ? { ...previous, status: event.type === 'done' ? 'done' : 'error', decision: String(event.detail.decision || '') } : previous)
        getRun(runId).then(setRun).catch(() => undefined)
        getRuns().then(setHistory).catch(() => undefined)
        if (event.type === 'done' && event.detail.published !== false) onForecastPublished()
      }
    }, streamError)
  }

  async function launch(recalc = false) {
    stopRef.current?.()
    setError('')
    setEvents([])
    try {
      const { run_id } = await startAgent(issueDate, mode, recalc)
      setRun({ run_id, issue_date: issueDate, mode, status: 'running', events: [], result: null })
      streamRun(run_id)
    } catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)) }
  }

  async function inspect(runId: string) {
    stopRef.current?.()
    setError('')
    try {
      const selected = await getRun(runId)
      setRun(selected)
      setEvents(selected.events)
      if (selected.status === 'running') streamRun(runId)
    } catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)) }
  }

  return <div className="page-stack"><div className="page-intro"><div><h1>Agent console</h1><p>Each new replay issue compares overlapping hours and their selected weather-input fingerprints. The optional cache watcher recalculates only on an input update. The button below explicitly requests a manual uncertainty review; it does not simulate new weather.</p></div><div className="page-actions"><button className="button button-primary" onClick={() => launch()} disabled={run?.status === 'running'}><Play size={16} /> Run agent for {issueDate}</button><button className="button button-secondary" onClick={() => launch(true)} disabled={run?.status === 'running'}><RotateCcw size={16} /> Manual uncertainty review</button></div></div>
    {error ? <ErrorState message={error} /> : null}
    <div className="agent-layout"><Panel title="Live decision trace" caption="Every stage records tool results and configured-policy evidence" action={run ? <Status type={run.status === 'done' ? 'ok' : run.status === 'error' ? 'critical' : 'neutral'}>{run.status === 'running' ? 'Running' : run.status === 'done' ? `Done · ${run.decision || 'ACCEPT'}` : 'Error'}</Status> : null}><AgentTimeline events={events} /></Panel><div className="agent-sidebar"><Panel title="Operating sequence" caption="The Python ML engine computes all numbers"><ol className="steps-list"><li>Select archived weather offsets</li><li>Check model coverage and configured availability</li><li>Run P10/P50/P90 forecast</li><li>Scan ramps and physical risks</li><li>Critic review and possible rerun</li><li>Brief grid dispatcher</li><li>Seal result in the hash ledger</li></ol></Panel><Panel title="Recent runs" caption="Select a run to inspect its trace">{history.length ? <div className="run-list">{history.slice(0, 8).map(item => <button key={item.run_id} onClick={() => inspect(item.run_id)} className={run?.run_id === item.run_id ? 'run-selected' : ''}><span>{item.issue_date}</span><small>{item.status}{item.decision ? ` · ${item.decision}` : ''}</small></button>)}</div> : <EmptyState message="No agent runs yet. Start one for the selected issue date." />}</Panel>{run?.result?.ledger ? <Panel title="Published integrity record"><div className="key-value"><span>Ledger block</span><strong>#{run.result.ledger.block_index}</strong></div><div className="key-value"><span>Hash chain valid</span><strong>{run.result.ledger.verified ? 'Yes' : 'No'}</strong></div><code className="hash-block">{run.result.ledger.hash}</code></Panel> : null}</div></div>
  </div>
}
