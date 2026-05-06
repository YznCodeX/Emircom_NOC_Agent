import { useState, useEffect } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import axios from 'axios'
import { API, SEV_COLORS, CAT_ICONS } from '../constants'
import { generateEmailTemplate } from '../utils'
import SLATimer from '../components/SLATimer'
import SeverityBadge from '../components/SeverityBadge'

const TABS = ['📋 Summary', '📄 Raw Logs', '📖 Runbook', '✉️ Email Template']

export default function Operations() {
  const navigate = useNavigate()
  const { state } = useLocation()
  const ticket = state?.ticket || null
  const openedAt = state?.openedAt || Date.now()

  const [analysis, setAnalysis] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [activeTab, setActiveTab] = useState(0)
  const [actionDone, setActionDone] = useState(null)
  const [copied, setCopied] = useState(false)
  const [step2, setStep2] = useState(false)
  const [skipEmail, setSkipEmail] = useState(false)
  const [escalationShown, setEscalationShown] = useState(false)
  const [showEscBanner, setShowEscBanner] = useState(false)

  useEffect(() => {
    if (!ticket) return
    setLoading(true)
    setError(null)
    setAnalysis(null)
    setActionDone(null)
    setStep2(false)
    setSkipEmail(false)
    setEscalationShown(false)
    setShowEscBanner(false)
    axios.post(`${API}/tickets/analyze`, {
      ticket_id: ticket.Ticket_ID,
      category: ticket.Category,
      description: ticket.Alert_Message || ticket.description || '',
      logs: ticket.Raw_Logs || ticket.logs || '',
    })
      .then(r => setAnalysis(r.data))
      .catch(e => setError(e.response?.data?.detail || 'Analysis failed — backend may be unavailable.'))
      .finally(() => setLoading(false))
  }, [ticket?.Ticket_ID])

  useEffect(() => {
    if (!analysis) return
    const interval = setInterval(() => {
      if (escalationShown) return
      const elapsed = Date.now() - openedAt
      const severity = analysis.analysis?.Severity || ticket?.Severity || 'Medium'
      if (
        (severity === 'Critical' && elapsed > 300000) ||
        (severity === 'High' && elapsed > 900000)
      ) {
        setShowEscBanner(true)
        setEscalationShown(true)
      }
    }, 10000)
    return () => clearInterval(interval)
  }, [analysis, escalationShown, openedAt, ticket?.Severity])

  async function handleAction(action) {
    try {
      await axios.post(`${API}/tickets/approve`, {
        ticket_id: ticket.Ticket_ID,
        category: ticket.Category,
        severity: analysis?.Severity || ticket.Severity || 'Medium',
        action,
      })
      setActionDone(action)
    } catch (e) {
      setError(e.response?.data?.detail || 'Action failed.')
    }
  }

  function copyEmail() {
    if (!analysis) return
    navigator.clipboard.writeText(generateEmailTemplate(ticket, analysis))
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const sev = analysis?.Severity || ticket?.Severity || 'Medium'
  const c = SEV_COLORS[sev] || SEV_COLORS.Medium

  // ── Empty state ──
  if (!ticket) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '80vh', color: '#4b5563' }}>
        <div style={{ fontSize: 48, marginBottom: 16 }}>📭</div>
        <div style={{ fontSize: 18, fontWeight: 600, color: '#6b7280' }}>No ticket selected</div>
        <div style={{ fontSize: 13, color: '#374151', marginTop: 6 }}>Go back to the dashboard and select a ticket to analyse.</div>
        <button onClick={() => navigate('/')} style={{
          marginTop: 24, padding: '10px 24px', background: '#1e3a5f', color: '#93c5fd',
          border: '1px solid #3b82f6', borderRadius: 8, cursor: 'pointer', fontSize: 14,
        }}>← Back to Queue</button>
      </div>
    )
  }

  return (
    <div style={{ padding: 32, color: '#f9fafb', minHeight: '100vh' }}>
      {/* Top bar */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 20 }}>
        <div>
          <div style={{ fontSize: 11, color: '#4b5563', letterSpacing: 1, textTransform: 'uppercase', marginBottom: 4 }}>
            {CAT_ICONS[ticket.Category] || '📋'} {ticket.Category} · {ticket.Ticket_ID}
          </div>
          <div style={{ fontSize: 20, fontWeight: 700, color: '#f9fafb' }}>{ticket.Alert_Message || ticket.description || 'Untitled Alert'}</div>
          <div style={{ marginTop: 8 }}><SeverityBadge severity={sev} /></div>
        </div>
        <button onClick={() => navigate('/')} style={{
          padding: '8px 18px', background: '#111827', color: '#9ca3af',
          border: '1px solid #1f2937', borderRadius: 8, cursor: 'pointer', fontSize: 13,
        }}>← Back to Queue</button>
      </div>

      {/* SLA Timer */}
      <SLATimer severity={sev} startTime={openedAt} />

      {/* Duplicate / Correlation banners */}
      {analysis?.is_duplicate && (
        <div style={{
          background: '#450a0a', border: '1px solid #7f1d1d', borderRadius: 8,
          padding: '12px 20px', marginBottom: 12, display: 'flex', alignItems: 'center', gap: 10,
        }}>
          <span style={{ fontSize: 18 }}>🔴</span>
          <div>
            <div style={{ color: '#fca5a5', fontWeight: 700, fontSize: 14 }}>Duplicate Ticket Detected</div>
            <div style={{ color: '#f87171', fontSize: 13, marginTop: 2 }}>
              {analysis.duplicate_reason || 'This ticket is a duplicate of an existing incident.'}
            </div>
          </div>
        </div>
      )}
      {analysis?.is_correlated && !analysis?.is_duplicate && (
        <div style={{
          background: '#451a03', border: '1px solid #92400e', borderRadius: 8,
          padding: '12px 20px', marginBottom: 12, display: 'flex', alignItems: 'center', gap: 10,
        }}>
          <span style={{ fontSize: 18 }}>🟡</span>
          <div>
            <div style={{ color: '#fcd34d', fontWeight: 700, fontSize: 14 }}>Correlated Incident</div>
            <div style={{ color: '#fbbf24', fontSize: 13, marginTop: 2 }}>
              Related to: {Array.isArray(analysis.correlated_with)
                ? analysis.correlated_with.join(', ')
                : analysis.correlated_with || 'unknown ticket'}
            </div>
          </div>
        </div>
      )}

      {/* Escalation banner */}
      {showEscBanner && (
        <div style={{
          background: '#450a0a', border: '2px solid #dc2626', borderRadius: 8,
          padding: '12px 20px', marginBottom: 12, display: 'flex', alignItems: 'center', gap: 10,
          animation: 'pulse 1.5s infinite',
        }}>
          <span style={{ fontSize: 20 }}>🚨</span>
          <div style={{ color: '#fca5a5', fontWeight: 700, fontSize: 14 }}>
            SLA BREACH WARNING — This ticket requires immediate attention. Shift lead has been notified.
          </div>
        </div>
      )}

      {/* Action result */}
      {actionDone && (
        <div style={{
          background: actionDone === 'approve' ? '#065f46' : '#450a0a',
          border: `1px solid ${actionDone === 'approve' ? '#047857' : '#7f1d1d'}`,
          borderRadius: 8, padding: '14px 20px', marginBottom: 20,
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        }}>
          <span style={{ color: actionDone === 'approve' ? '#6ee7b7' : '#fca5a5', fontWeight: 600 }}>
            {actionDone === 'approve' ? '✅ Ticket approved and escalated.' : '❌ Ticket rejected and closed.'}
          </span>
          <button onClick={() => navigate('/')} style={{
            padding: '8px 18px', background: '#111827', color: '#60a5fa',
            border: '1px solid #1e3a5f', borderRadius: 8, cursor: 'pointer', fontSize: 13,
          }}>← Next Ticket</button>
        </div>
      )}

      {/* Analysis area */}
      <div style={{ background: '#111827', border: '1px solid #1f2937', borderRadius: 12, overflow: 'hidden' }}>
        {/* Tabs */}
        <div style={{ display: 'flex', borderBottom: '1px solid #1f2937' }}>
          {TABS.map((tab, i) => (
            <button key={i} onClick={() => setActiveTab(i)} style={{
              padding: '13px 22px', background: 'none', border: 'none', cursor: 'pointer',
              fontSize: 13, fontWeight: activeTab === i ? 600 : 400,
              color: activeTab === i ? '#60a5fa' : '#6b7280',
              borderBottom: activeTab === i ? '2px solid #3b82f6' : '2px solid transparent',
              transition: 'all 0.15s',
            }}>{tab}</button>
          ))}
        </div>

        <div style={{ padding: 24 }}>
          {loading && (
            <div style={{ textAlign: 'center', padding: 40, color: '#4b5563' }}>
              <div style={{ fontSize: 24, marginBottom: 12 }}>🤖</div>
              Running AI analysis pipeline…
            </div>
          )}

          {error && !loading && (
            <div style={{ background: '#450a0a', border: '1px solid #7f1d1d', borderRadius: 8, padding: 16, color: '#fca5a5', fontSize: 13 }}>
              ⚠️ {error}
            </div>
          )}

          {!loading && !error && analysis && (
            <>
              {/* Summary tab */}
              {activeTab === 0 && (
                <div>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 20 }}>
                    {[
                      ['Affected Node', analysis.Affected_Node],
                      ['Categorization', analysis.Categorization],
                      ['Confidence', `${analysis.Confidence_Score ?? '—'}%`],
                      ['Routing Team', analysis.Routing_Team || ticket.Category],
                    ].map(([label, val]) => (
                      <div key={label} style={{ background: '#0a0e1a', border: '1px solid #1f2937', borderRadius: 8, padding: '12px 16px' }}>
                        <div style={{ fontSize: 11, color: '#4b5563', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 4 }}>{label}</div>
                        <div style={{ fontSize: 14, color: '#d1d5db', fontWeight: 500 }}>{val || '—'}</div>
                      </div>
                    ))}
                  </div>

                  {/* Confidence bar */}
                  {analysis.Confidence_Score != null && (
                    <div style={{ marginBottom: 20 }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                        <span style={{ fontSize: 12, color: '#4b5563', textTransform: 'uppercase', letterSpacing: 1 }}>AI Confidence</span>
                        <span style={{ fontSize: 12, color: c.text }}>{analysis.Confidence_Score}%</span>
                      </div>
                      <div style={{ background: '#1f2937', borderRadius: 999, height: 6 }}>
                        <div style={{ height: 6, borderRadius: 999, background: c.dot, width: `${analysis.Confidence_Score}%`, transition: 'width 0.6s ease' }} />
                      </div>
                      {analysis.Confidence_Reason && (
                        <div style={{ fontSize: 12, color: '#4b5563', marginTop: 6 }}>{analysis.Confidence_Reason}</div>
                      )}
                    </div>
                  )}

                  {[
                    ['🔍 Symptom', analysis.Symptom_Description],
                    ['🌱 Root Cause', analysis.Root_Cause],
                    ['💼 Business Impact', analysis.Business_Impact],
                    ['🛠 Recommended Action', analysis.Recommended_Action],
                  ].map(([label, val]) => val ? (
                    <div key={label} style={{ marginBottom: 16 }}>
                      <div style={{ fontSize: 12, color: '#4b5563', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 6 }}>{label}</div>
                      <div style={{ background: '#0a0e1a', border: '1px solid #1f2937', borderRadius: 8, padding: '12px 16px', fontSize: 14, color: '#d1d5db', lineHeight: 1.7 }}>
                        {val}
                      </div>
                    </div>
                  ) : null)}
                </div>
              )}

              {/* Raw Logs tab */}
              {activeTab === 1 && (
                <pre style={{
                  background: '#0a0e1a', border: '1px solid #1f2937', borderRadius: 8,
                  padding: 16, fontSize: 12, color: '#6ee7b7', overflowX: 'auto',
                  lineHeight: 1.7, margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-all',
                }}>
                  {ticket.Raw_Logs || ticket.logs || 'No raw logs available for this ticket.'}
                </pre>
              )}

              {/* Runbook tab */}
              {activeTab === 2 && (
                <div>
                  {analysis.runbook_match ? (
                    <pre style={{
                      background: '#0a0e1a', border: '1px solid #1f2937', borderRadius: 8,
                      padding: 16, fontSize: 13, color: '#d1d5db', lineHeight: 1.8,
                      margin: 0, whiteSpace: 'pre-wrap',
                    }}>{analysis.runbook_match}</pre>
                  ) : (
                    <div style={{ textAlign: 'center', padding: 40, color: '#4b5563' }}>
                      <div style={{ fontSize: 32, marginBottom: 12 }}>📖</div>
                      No runbook matched for this incident type.
                    </div>
                  )}
                </div>
              )}

              {/* Email Template tab */}
              {activeTab === 3 && (
                <div>
                  <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 12 }}>
                    <button onClick={copyEmail} style={{
                      padding: '7px 16px', background: copied ? '#065f46' : '#1e3a5f',
                      color: copied ? '#6ee7b7' : '#93c5fd',
                      border: `1px solid ${copied ? '#047857' : '#3b82f6'}`,
                      borderRadius: 8, cursor: 'pointer', fontSize: 13, transition: 'all 0.2s',
                    }}>{copied ? '✅ Copied!' : '📋 Copy'}</button>
                  </div>
                  <pre style={{
                    background: '#0a0e1a', border: '1px solid #1f2937', borderRadius: 8,
                    padding: 16, fontSize: 13, color: '#d1d5db', lineHeight: 1.8,
                    margin: 0, whiteSpace: 'pre-wrap',
                  }}>{generateEmailTemplate(ticket, analysis)}</pre>
                </div>
              )}
            </>
          )}

          {!loading && !error && !analysis && (
            <div style={{ textAlign: 'center', padding: 40, color: '#4b5563' }}>Waiting for analysis…</div>
          )}
        </div>
      </div>

      {/* Approve / Reject — 2-step wizard */}
      {!actionDone && !loading && analysis && (
        <div style={{ marginTop: 20 }}>
          {/* Step 1 */}
          {!step2 && (
            <div style={{ display: 'flex', gap: 12 }}>
              <button onClick={() => setStep2(true)} style={{
                flex: 1, padding: '14px 0', background: '#065f46', color: '#6ee7b7',
                border: '1px solid #047857', borderRadius: 8, cursor: 'pointer', fontWeight: 700, fontSize: 15,
              }}>✅ Approve & Escalate</button>
              <button onClick={() => handleAction('reject')} style={{
                flex: 1, padding: '14px 0', background: '#450a0a', color: '#fca5a5',
                border: '1px solid #7f1d1d', borderRadius: 8, cursor: 'pointer', fontWeight: 700, fontSize: 15,
              }}>❌ Reject</button>
            </div>
          )}

          {/* Step 2 — email confirmation card */}
          {step2 && (
            <div style={{
              background: '#111827',
              border: `1px solid #1f2937`,
              borderLeft: `4px solid ${c.dot}`,
              borderRadius: 10,
              padding: '20px 24px',
            }}>
              <div style={{ fontSize: 13, color: '#9ca3af', marginBottom: 16, textTransform: 'uppercase', letterSpacing: 1 }}>
                ✉️ Email Notification
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 20 }}>
                {[
                  ['To', `noc-${(analysis.analysis?.Routing_Team || ticket.Category || 'team').toLowerCase().replace(/\s+/g, '-')}@emircom.ae`],
                  ['Subject', `[NOC ${sev}] ${ticket.Ticket_ID} — ${ticket.Alert_Message || 'Alert'}`],
                  ['Team', analysis.analysis?.Routing_Team || ticket.Category || '—'],
                  ['Affected Node', analysis.analysis?.Affected_Node || '—'],
                ].map(([label, val]) => (
                  <div key={label} style={{ background: '#0a0e1a', border: '1px solid #1f2937', borderRadius: 8, padding: '10px 14px' }}>
                    <div style={{ fontSize: 11, color: '#4b5563', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 3 }}>{label}</div>
                    <div style={{ fontSize: 13, color: '#d1d5db', wordBreak: 'break-all' }}>{val}</div>
                  </div>
                ))}
              </div>
              <div style={{ display: 'flex', gap: 10 }}>
                <button onClick={() => handleAction('approve')} style={{
                  flex: 2, padding: '13px 0', background: '#1e3a5f', color: '#93c5fd',
                  border: '1px solid #3b82f6', borderRadius: 8, cursor: 'pointer', fontWeight: 700, fontSize: 14,
                }}>✉️ Send Notification</button>
                <button onClick={() => { setSkipEmail(true); handleAction('approve') }} style={{
                  flex: 1, padding: '13px 0', background: '#1f2937', color: '#6b7280',
                  border: '1px solid #374151', borderRadius: 8, cursor: 'pointer', fontWeight: 600, fontSize: 14,
                }}>Skip</button>
                <button onClick={() => setStep2(false)} style={{
                  flex: 1, padding: '13px 0', background: 'none', color: '#4b5563',
                  border: '1px solid #1f2937', borderRadius: 8, cursor: 'pointer', fontSize: 13,
                }}>← Back</button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
