import { useEffect, useState } from 'react'
import { Fingerprint, RotateCcw, ShieldCheck } from 'lucide-react'
import { getLedger, tamperLedger, verifyLedger } from '../api/client'
import type { LedgerBlock, LedgerData, LedgerVerification } from '../api/types'
import { EmptyState, ErrorState, Panel, Status } from '../components/Shared'

function policyStatus(block: LedgerBlock): string {
  return block.availability_evidence_status ??
    ((block.type === 'FORECAST' || block.type === 'REVISION') && !block.availability_policy_version
      ? 'legacy_policy_evidence' : 'not_applicable')
}

export function LedgerPage({ revision }: { revision: number }) {
  const [ledger, setLedger] = useState<LedgerData | null>(null)
  const [verification, setVerification] = useState<LedgerVerification | null>(null)
  const [tamper, setTamper] = useState<LedgerVerification | null>(null)
  const [blockIndex, setBlockIndex] = useState<number | ''>('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  useEffect(() => { let active = true; getLedger().then(value => { if (active) { setLedger(value); const first = value.blocks.find(block => block.type === 'FORECAST' || block.type === 'REVISION'); setBlockIndex(first?.index ?? '') } }).catch(cause => { if (active) setError(cause.message) }); return () => { active = false } }, [revision])

  async function verify() { setLoading(true); setError(''); try { setVerification(await verifyLedger()); setTamper(null) } catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)) } finally { setLoading(false) } }
  async function simulate() { if (blockIndex === '') return; setLoading(true); setError(''); try { setTamper(await tamperLedger(blockIndex)) } catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)) } finally { setLoading(false) } }

  const legacyCount = verification?.legacy_policy_evidence_blocks?.length ?? ledger?.blocks.filter(block => policyStatus(block) === 'legacy_policy_evidence').length ?? 0
  return <div className="page-stack"><div className="page-intro"><div><h1>Forecast ledger</h1><p>Hashes check published payload integrity; weather timing follows a configured offset-and-latency policy, not verified provider release times.</p></div><Status type={verification?.valid ? 'ok' : 'neutral'}>{verification?.valid ? 'Chain integrity verified' : `${ledger?.length ?? 0} blocks`}</Status></div>
    {error ? <ErrorState message={error} /> : null}
    <div className="ledger-action-grid"><Panel title="Verify the chain" caption="Checks block hashes, links, payloads, and recorded policy arithmetic"><div className="ledger-action-icon"><ShieldCheck size={28} /></div><button className="button button-primary" onClick={verify} disabled={loading}><ShieldCheck size={16} /> Verify chain</button>{verification ? <div className={`result-banner ${verification.valid ? 'result-ok' : 'result-bad'}`}>{verification.valid ? `Integrity valid · ${verification.checked} blocks checked${legacyCount ? ` · ${legacyCount} legacy policy evidence` : ''}` : `Verification failed · ${verification.errors.map(item => item.reason).join(', ')}`}</div> : null}</Panel><Panel title="Tamper simulation" caption="Alter a copy in memory; the published ledger remains unchanged"><div className="ledger-action-icon"><Fingerprint size={28} /></div><div className="tamper-controls"><label className="select-label">Forecast block<select value={blockIndex} onChange={event => setBlockIndex(event.target.value ? Number(event.target.value) : '')}><option value="">Select a block</option>{ledger?.blocks.filter(block => block.type === 'FORECAST' || block.type === 'REVISION').map(block => <option value={block.index} key={block.index}>#{block.index} · {block.issue_date}</option>)}</select></label><button className="button button-secondary" disabled={loading || blockIndex === ''} onClick={simulate}><RotateCcw size={16} /> Tamper demo</button></div>{tamper ? <div className="result-banner result-bad">Detected at block #{tamper.first_bad_block}: {tamper.errors[0]?.reason}</div> : null}</Panel></div>
    <Panel title="Append-only block history" caption="A broken hash or recorded offset-policy violation fails verification; true source release time is not proven" action={ledger ? <span className="hash-short">Head {ledger.head_hash.slice(0, 12)}…</span> : null}>{ledger?.blocks.length ? <div className="table-scroll"><table><thead><tr><th>#</th><th>Type</th><th>Issue date</th><th>Estimated NWP init</th><th>Policy evidence</th><th>Hash</th><th>Previous</th><th>Note</th></tr></thead><tbody>{ledger.blocks.map(block => <tr key={block.index}><td>{block.index}</td><td><span className={`block-type block-${block.type.toLowerCase()}`}>{block.type.replace('_', ' ')}</span></td><td>{block.issue_date || '—'}</td><td>{(block.max_estimated_nwp_init_time_used || block.max_nwp_init_time_used)?.replace('T', ' ').slice(0, 16) || '—'}</td><td>{policyStatus(block) === 'legacy_policy_evidence' ? 'Legacy policy evidence' : policyStatus(block) === 'configured_policy_v1_source_release_unverified' ? 'Configured check · release unverified' : '—'}</td><td><code>{block.hash.slice(0, 10)}…</code></td><td><code>{block.prev_hash.slice(0, 10)}…</code></td><td>{block.note || '—'}</td></tr>)}</tbody></table></div> : <EmptyState message="No forecast blocks yet. Run the agent to publish the first forecast." />}</Panel>
  </div>
}
