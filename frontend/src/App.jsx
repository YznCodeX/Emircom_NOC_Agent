import { useState, useEffect, useRef } from 'react'
import axios from 'axios'
import './App.css'

const API = 'http://localhost:8001'

if (typeof Notification !== 'undefined' && Notification.permission === 'default') {
  Notification.requestPermission()
}

const SLA_MINUTES = { Critical: 15, High: 60, Medium: 240, Low: 1440 }

const SEV_COLORS = {
  Critical: { bg: '#7f1d1d', text: '#fca5a5', dot: '#ef4444' },
  High:     { bg: '#78350f', text: '#fcd34d', dot: '#f59e0b' },
  Medium:   { bg: '#1e3a5f', text: '#93c5fd', dot: '#3b82f6' },
  Low:      { bg: '#14532d', text: '#86efac', dot: '#22c55e' },
}

const CAT_ICONS = {
  Network: '🌐', Security: '🔒', Hardware: '💾', Cloud: '☁️', Application: '📱',
}

const TEAM_NAMES = {
  Network: 'NOC Network Team', Security: 'NOC Security Team',
  Hardware: 'NOC Hardware Team', Cloud: 'NOC Cloud Team', Application: 'NOC Application Team',
}

const TEAM_EMAILS = {
  Network: 'noc-network@emircom.com', Security: 'noc-security@emircom.com',
  Hardware: 'noc-hardware@emircom.com', Cloud: 'noc-cloud@emircom.com',
  Application: 'noc-application@emircom.com',
}

function SeverityBadge({ severity }) {
  const c = SEV_COLORS[severity] || SEV_COLORS.Medium
  return (
    <span style={{
      background: c.bg, color: c.text, padding: '2px 10px', borderRadius: '999px',
      fontSize: '12px', fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: '5px',
    }}>
      <span style={{ width: 7, height: 7, borderRadius: '50%', background: c.dot, display: 'inline-block' }} />
      {severity}
    </span>
  )
}

function StatCard({ label, value, color }) {
  return (
    <div style={{ background: '#111827', border: '1px solid #1f2937', borderRadius: 12, padding: '20px 24px', flex: 1 }}>
      <div style={{ fontSize: 28, fontWeight: 700, color: color || '#fff' }}>{value}</div>
      <div style={{ fontSize: 13, color: '#6b7280', marginTop: 4 }}>{label}</div>
    </div>
  )
}

function SLATimer({ severity, startTime }) {
  const limitSecs = (SLA_MINUTES[severity] || 240) * 60
  const [elapsed, setElapsed] = useState(() => Math.floor((Date.now() - startTime) / 1000))

  useEffect(() => {
    const iv = setInterval(() => setElapsed(Math.floor((Date.now() - startTime) / 1000)), 1000)
    return () => clearInterval(iv)
  }, [startTime])

  const remaining = Math.max(0, limitSecs - elapsed)
  const pct = Math.min(100, (elapsed / limitSecs) * 100)
  const breached = remaining === 0
  const color = pct < 50 ? '#22c55e' : pct < 80 ? '#f59e0b' : '#ef4444'
  const h = Math.floor(remaining / 3600)
  const m = Math.floor((remaining % 3600) / 60)
  const s = remaining % 60
  const slaLabel = SLA_MINUTES[severity] < 60 ? `${SLA_MINUTES[severity]}min` : `${SLA_MINUTES[severity] / 60}hr`

  return (
    <div style={{ background: '#0a0e1a', border: `1px solid ${color}44`, borderRadius: 8, padding: 14, marginBottom: 16 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
        <span style={{ fontSize: 11, color: '#4b5563', textTransform: 'uppercase', letterSpacing: 1 }}>
          ⏱ SLA Timer — {severity} ({slaLabel} window)
        </span>
        <span style={{ fontSize: 13, fontWeight: 700, color: breached ? '#ef4444' : color, fontFamily: 'monospace' }}>
          {breached ? '⚠️ SLA BREACHED' : `${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')} remaining`}
        </span>
      </div>
      <div style={{ background: '#1f2937', borderRadius: 999, height: 6 }}>
        <div style={{ height: 6, borderRadius: 999, background: color, width: `${pct}%`, transition: 'width 1s linear' }} />
      </div>
    </div>
  )
}

function generateEmailTemplate(ticket, a) {
  const severity = a.Severity || ticket.Severity || 'Medium'
  const category = ticket.Category || 'Unknown'
  const team = TEAM_NAMES[category] || 'NOC Team'
  const teamEmail = TEAM_EMAILS[category] || 'noc@emircom.com'
  const slaLabel = SLA_MINUTES[severity] < 60 ? `${SLA_MINUTES[severity]} minutes` : `${SLA_MINUTES[severity] / 60} hour(s)`

  return `To: ${teamEmail}
Subject: [NOC Alert] ${severity} Severity — ${category} Incident — ${a.Affected_Node || 'Unknown Node'}

Dear ${team},

An automated NOC AI analysis has identified the following ${severity.toLowerCase()} severity incident requiring your attention.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
INCIDENT DETAILS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Ticket ID:      ${ticket.Ticket_ID}
Severity:       ${severity}
Category:       ${category}
Affected Node:  ${a.Affected_Node || 'Unknown'}
Categorization: ${a.Categorization || 'Unknown'}

SYMPTOM
━━━━━━━━
${a.Symptom_Description || 'N/A'}

ROOT CAUSE
━━━━━━━━━━
${a.Root_Cause || 'N/A'}

BUSINESS IMPACT
━━━━━━━━━━━━━━━
${a.Business_Impact || 'N/A'}

RECOMMENDED ACTION
━━━━━━━━━━━━━━━━━━
${a.Recommended_Action || 'N/A'}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SLA Window: ${slaLabel} from ticket creation.
AI Confidence Score: ${a.Confidence_Score || 'N/A'}%${a.Confidence_Reason ? `\nReason: ${a.Confidence_Reason}` : ''}

Please acknowledge this ticket in GLPI and begin remediation immediately.

Regards,
Emircom NOC AI Agent
Generated: ${new Date().toLocaleString()}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━`
}

function TicketRow({ ticket, onSelect }) {
  const severity = ticket.Severity || 'Medium'
  return (
    <div
      onClick={() => onSelect(ticket)}
      style={{
        display: 'grid', gridTemplateColumns: '120px 100px 110px 1fr 140px',
        alignItems: 'center', gap: 16, padding: '14px 20px',
        borderBottom: '1px solid #1f2937', cursor: 'pointer', transition: 'background 0.15s',
      }}
      onMouseEnter={e => e.currentTarget.style.background = '#111827'}
      onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
    >
      <span style={{ fontFamily: 'monospace', color: '#60a5fa', fontSize: 13 }}>{ticket.Ticket_ID}</span>
      <SeverityBadge severity={severity} />
      <span style={{ fontSize: 13, color: '#9ca3af' }}>{CAT_ICONS[ticket.Category] || '📋'} {ticket.Category}</span>
      <span style={{ fontSize: 13, color: '#d1d5db', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        {ticket.Alert_Message || ticket.description || '—'}
      </span>
      <span style={{ fontSize: 12, color: '#4b5563', textAlign: 'right' }}>{ticket.Timestamp || '—'}</span>
    </div>
  )
}

function TicketDetail({ ticket, openedAt, onClose, onAction }) {
  const [loading, setLoading] = useState(false)
  const [analysis, setAnalysis] = useState(null)
  const [error, setError] = useState(null)
  const [actionDone, setActionDone] = useState(false)
  const [activeTab, setActiveTab] = useState('summary')
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    setAnalysis(null); setError(null); setActionDone(false); setActiveTab('summary')
    analyzeTicket()
  }, [ticket.Ticket_ID])

  async function analyzeTicket() {
    setLoading(true)
    try {
      const res = await axios.post(`${API}/tickets/analyze`, {
        ticket_id: ticket.Ticket_ID, category: ticket.Category,
        description: ticket.Alert_Message || '', logs: ticket.Raw_Logs || '',
      })
      setAnalysis(res.data)
    } catch { setError('Failed to analyze ticket. Is the backend running?') }
    setLoading(false)
  }

  async function handleAction(action) {
    setLoading(true)
    try {
      const severity = analysis?.analysis?.Severity || ticket.Severity || 'Medium'
      await axios.post(`${API}/tickets/approve`, {
        ticket_id: ticket.Ticket_ID, category: ticket.Category, severity, action,
      })
      setActionDone(true)
      onAction(ticket.Ticket_ID, action)
    } catch { setError('Action failed.') }
    setLoading(false)
  }

  const a = analysis?.analysis || {}
  const severity = a.Severity || ticket.Severity || 'Medium'
  const c = SEV_COLORS[severity] || SEV_COLORS.Medium

  function handleCopyEmail() {
    navigator.clipboard.writeText(generateEmailTemplate(ticket, a)).then(() => {
      setCopied(true); setTimeout(() => setCopied(false), 2000)
    })
  }

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 50, padding: 24 }}>
      <div style={{ background: '#111827', border: '1px solid #1f2937', borderRadius: 16, width: '100%', maxWidth: 720, maxHeight: '90vh', overflowY: 'auto', padding: 32 }}>

        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 20 }}>
          <div>
            <div style={{ fontSize: 13, color: '#6b7280', marginBottom: 6 }}>INCIDENT REPORT</div>
            <div style={{ fontSize: 22, fontWeight: 700, color: '#f9fafb' }}>{ticket.Ticket_ID}</div>
            <div style={{ marginTop: 8, display: 'flex', gap: 10, alignItems: 'center' }}>
              <SeverityBadge severity={severity} />
              <span style={{ fontSize: 13, color: '#9ca3af' }}>{CAT_ICONS[ticket.Category]} {ticket.Category}</span>
            </div>
          </div>
          <button onClick={onClose} style={{ background: 'none', border: '1px solid #374151', color: '#9ca3af', borderRadius: 8, padding: '6px 14px', cursor: 'pointer', fontSize: 13 }}>✕ Close</button>
        </div>

        {/* SLA Timer */}
        <SLATimer severity={severity} startTime={openedAt} />

        {loading && !analysis && (
          <div style={{ textAlign: 'center', padding: '40px 0', color: '#6b7280' }}>
            <div style={{ fontSize: 28, marginBottom: 12 }}>🤖</div>
            <div>AI Agent analyzing ticket...</div>
          </div>
        )}

        {error && <div style={{ background: '#7f1d1d', color: '#fca5a5', padding: 16, borderRadius: 8, marginBottom: 16 }}>{error}</div>}

        {analysis && (
          <>
            {/* Tabs */}
            <div style={{ display: 'flex', gap: 4, marginBottom: 20, borderBottom: '1px solid #1f2937' }}>
              {[{ id: 'summary', label: '📋 Summary' }, { id: 'email', label: '✉️ Email Template' }].map(tab => (
                <button key={tab.id} onClick={() => setActiveTab(tab.id)} style={{
                  padding: '8px 16px', background: 'none', border: 'none',
                  borderBottom: activeTab === tab.id ? '2px solid #3b82f6' : '2px solid transparent',
                  color: activeTab === tab.id ? '#60a5fa' : '#6b7280',
                  cursor: 'pointer', fontSize: 13, fontWeight: activeTab === tab.id ? 600 : 400, marginBottom: -1,
                }}>{tab.label}</button>
              ))}
            </div>

            {activeTab === 'summary' && (
              <>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 20 }}>
                  {[
                    { label: 'Affected Node', value: a.Affected_Node },
                    { label: 'Categorization', value: a.Categorization },
                    { label: 'Root Cause', value: a.Root_Cause },
                    { label: 'Business Impact', value: a.Business_Impact },
                  ].map(({ label, value }) => (
                    <div key={label} style={{ background: '#0a0e1a', border: '1px solid #1f2937', borderRadius: 8, padding: 14 }}>
                      <div style={{ fontSize: 11, color: '#4b5563', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 6 }}>{label}</div>
                      <div style={{ fontSize: 13, color: '#d1d5db' }}>{value || '—'}</div>
                    </div>
                  ))}
                </div>

                <div style={{ background: '#0a0e1a', border: '1px solid #1f2937', borderRadius: 8, padding: 14, marginBottom: 12 }}>
                  <div style={{ fontSize: 11, color: '#4b5563', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 6 }}>Symptom Description</div>
                  <div style={{ fontSize: 13, color: '#d1d5db' }}>{a.Symptom_Description || '—'}</div>
                </div>

                <div style={{ background: '#0f2027', border: `1px solid ${c.dot}33`, borderRadius: 8, padding: 14, marginBottom: 20 }}>
                  <div style={{ fontSize: 11, color: '#4b5563', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 6 }}>Recommended Action</div>
                  <div style={{ fontSize: 13, color: c.text }}>{a.Recommended_Action || '—'}</div>
                </div>

                {analysis.confidence_score != null && (
                  <div style={{ marginBottom: 20 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                      <span style={{ fontSize: 12, color: '#6b7280' }}>AI Confidence</span>
                      <span style={{ fontSize: 12, color: '#9ca3af' }}>{analysis.confidence_score}%</span>
                    </div>
                    <div style={{ background: '#1f2937', borderRadius: 999, height: 6 }}>
                      <div style={{
                        height: 6, borderRadius: 999,
                        background: analysis.confidence_score >= 80 ? '#22c55e' : analysis.confidence_score >= 60 ? '#f59e0b' : '#ef4444',
                        width: `${analysis.confidence_score}%`, transition: 'width 0.5s ease',
                      }} />
                    </div>
                    {a.Confidence_Reason && <div style={{ fontSize: 11, color: '#4b5563', marginTop: 6 }}>{a.Confidence_Reason}</div>}
                  </div>
                )}
              </>
            )}

            {activeTab === 'email' && (
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                  <span style={{ fontSize: 13, color: '#6b7280' }}>Team notification email — ready to copy</span>
                  <button onClick={handleCopyEmail} style={{
                    padding: '6px 14px', borderRadius: 6,
                    background: copied ? '#065f46' : '#1e3a5f',
                    color: copied ? '#6ee7b7' : '#93c5fd',
                    border: `1px solid ${copied ? '#047857' : '#1d4ed8'}`,
                    cursor: 'pointer', fontSize: 12, fontWeight: 600,
                  }}>{copied ? '✅ Copied!' : '📋 Copy to Clipboard'}</button>
                </div>
                <pre style={{
                  background: '#0a0e1a', border: '1px solid #1f2937', borderRadius: 8, padding: 16,
                  fontSize: 12, color: '#d1d5db', lineHeight: 1.7,
                  whiteSpace: 'pre-wrap', wordBreak: 'break-word', fontFamily: 'monospace',
                }}>{generateEmailTemplate(ticket, a)}</pre>
              </div>
            )}

            {!actionDone ? (
              <div style={{ display: 'flex', gap: 12, marginTop: 20 }}>
                <button onClick={() => handleAction('approve')} disabled={loading} style={{
                  flex: 1, padding: '12px 0', background: '#065f46', color: '#6ee7b7',
                  border: '1px solid #047857', borderRadius: 8, cursor: 'pointer', fontWeight: 600, fontSize: 14,
                }}>✅ Approve & Create GLPI Ticket</button>
                <button onClick={() => handleAction('reject')} disabled={loading} style={{
                  flex: 1, padding: '12px 0', background: '#450a0a', color: '#fca5a5',
                  border: '1px solid #7f1d1d', borderRadius: 8, cursor: 'pointer', fontWeight: 600, fontSize: 14,
                }}>❌ Reject</button>
              </div>
            ) : (
              <div style={{ textAlign: 'center', padding: 16, background: '#065f46', borderRadius: 8, color: '#6ee7b7', fontWeight: 600, marginTop: 20 }}>
                ✅ Action completed — ticket updated in GLPI
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}

function HandoffReport({ onClose }) {
  const [outgoing, setOutgoing] = useState('')
  const [incoming, setIncoming] = useState('')
  const [shiftPeriod, setShiftPeriod] = useState('08:00 - 20:00')
  const [report, setReport] = useState(null)
  const [loading, setLoading] = useState(false)

  async function generateReport() {
    setLoading(true)
    try {
      const [procRes, statsRes] = await Promise.all([
        axios.get(`${API}/tickets/processed`),
        axios.get(`${API}/stats`),
      ])
      setReport({ processed: procRes.data, stats: statsRes.data })
    } catch (e) { console.error(e) }
    setLoading(false)
  }

  const processed = report?.processed || []
  const approved = processed.filter(t => t.Status === 'Approved')
  const rejected = processed.filter(t => t.Status === 'Rejected')
  const critical = processed.filter(t => t.Severity === 'Critical')
  const byCategory = processed.reduce((acc, t) => { acc[t.Category] = (acc[t.Category] || 0) + 1; return acc }, {})

  const inputStyle = {
    background: '#0a0e1a', border: '1px solid #1f2937', borderRadius: 8,
    padding: '10px 14px', color: '#f9fafb', fontSize: 13, width: '100%', outline: 'none',
  }

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.8)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 200, padding: 24 }}>
      <div style={{ background: '#111827', border: '1px solid #1f2937', borderRadius: 16, width: '100%', maxWidth: 760, maxHeight: '90vh', overflowY: 'auto', padding: 32 }}>

        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
          <div>
            <div style={{ fontSize: 18, fontWeight: 700, color: '#f9fafb' }}>📋 Shift Handoff Report</div>
            <div style={{ fontSize: 13, color: '#6b7280', marginTop: 4 }}>Generate and export end-of-shift summary</div>
          </div>
          <button onClick={onClose} style={{ background: 'none', border: '1px solid #374151', color: '#9ca3af', borderRadius: 8, padding: '6px 14px', cursor: 'pointer', fontSize: 13 }}>✕ Close</button>
        </div>

        {/* Form */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12, marginBottom: 20 }}>
          {[
            { label: 'Outgoing Engineer', value: outgoing, set: setOutgoing, placeholder: 'e.g. Ahmed Al-Rashidi' },
            { label: 'Incoming Engineer', value: incoming, set: setIncoming, placeholder: 'e.g. Sara Al-Mutairi' },
            { label: 'Shift Period', value: shiftPeriod, set: setShiftPeriod, placeholder: '08:00 - 20:00' },
          ].map(({ label, value, set, placeholder }) => (
            <div key={label}>
              <div style={{ fontSize: 11, color: '#4b5563', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 6 }}>{label}</div>
              <input style={inputStyle} value={value} onChange={e => set(e.target.value)} placeholder={placeholder} />
            </div>
          ))}
        </div>

        {/* Buttons */}
        <div style={{ display: 'flex', gap: 10, marginBottom: 24 }}>
          <button onClick={generateReport} disabled={loading} style={{
            padding: '10px 20px', borderRadius: 8, background: '#1e3a5f', color: '#93c5fd',
            border: '1px solid #1d4ed8', cursor: 'pointer', fontWeight: 600, fontSize: 13,
          }}>{loading ? '⏳ Generating...' : '⚡ Generate Report'}</button>
          <button onClick={() => window.open(`${API}/handoff/export`, '_blank')} style={{
            padding: '10px 20px', borderRadius: 8, background: '#14532d', color: '#86efac',
            border: '1px solid #15803d', cursor: 'pointer', fontWeight: 600, fontSize: 13,
          }}>📥 Download Excel</button>
        </div>

        {/* Generated Report */}
        {report && (
          <div>
            {/* Cover */}
            <div style={{ background: '#0a0e1a', border: '1px solid #1d4ed8', borderRadius: 8, padding: 20, marginBottom: 16 }}>
              <div style={{ fontSize: 15, fontWeight: 700, color: '#60a5fa', marginBottom: 12 }}>Emircom NOC — Shift Handoff Report</div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 10 }}>
                {[
                  { label: 'Date', value: new Date().toLocaleDateString() },
                  { label: 'Shift Period', value: shiftPeriod || '—' },
                  { label: 'Outgoing Engineer', value: outgoing || '—' },
                  { label: 'Incoming Engineer', value: incoming || '—' },
                  { label: 'Generated At', value: new Date().toLocaleTimeString() },
                ].map(({ label, value }) => (
                  <div key={label}>
                    <div style={{ fontSize: 10, color: '#4b5563', textTransform: 'uppercase', letterSpacing: 1 }}>{label}</div>
                    <div style={{ fontSize: 13, color: '#d1d5db', fontWeight: 500 }}>{value}</div>
                  </div>
                ))}
              </div>
            </div>

            {/* Key Metrics */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10, marginBottom: 16 }}>
              {[
                { label: 'Total Processed', value: processed.length, color: '#a78bfa' },
                { label: 'Approved', value: approved.length, color: '#22c55e' },
                { label: 'Rejected', value: rejected.length, color: '#ef4444' },
                { label: 'Critical', value: critical.length, color: '#ef4444' },
              ].map(({ label, value, color }) => (
                <div key={label} style={{ background: '#0a0e1a', border: '1px solid #1f2937', borderRadius: 8, padding: 14, textAlign: 'center' }}>
                  <div style={{ fontSize: 24, fontWeight: 700, color }}>{value}</div>
                  <div style={{ fontSize: 11, color: '#6b7280', marginTop: 4 }}>{label}</div>
                </div>
              ))}
            </div>

            {/* By Category */}
            {Object.keys(byCategory).length > 0 && (
              <div style={{ background: '#0a0e1a', border: '1px solid #1f2937', borderRadius: 8, padding: 16, marginBottom: 16 }}>
                <div style={{ fontSize: 11, color: '#4b5563', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 10 }}>Tickets by Category</div>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  {Object.entries(byCategory).map(([cat, count]) => (
                    <span key={cat} style={{ background: '#1f2937', color: '#d1d5db', padding: '4px 12px', borderRadius: 999, fontSize: 12 }}>
                      {CAT_ICONS[cat] || '📋'} {cat}: <strong>{count}</strong>
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Critical Incidents */}
            {critical.length > 0 && (
              <div style={{ background: '#0a0e1a', border: '1px solid #7f1d1d', borderRadius: 8, padding: 16, marginBottom: 16 }}>
                <div style={{ fontSize: 11, color: '#4b5563', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 10 }}>⚠️ Critical Incidents This Shift</div>
                {critical.map((t, i) => (
                  <div key={i} style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 0', borderBottom: i < critical.length - 1 ? '1px solid #1f2937' : 'none' }}>
                    <span style={{ fontFamily: 'monospace', color: '#60a5fa', fontSize: 12 }}>{t.Ticket_ID}</span>
                    <span style={{ fontSize: 12, color: '#9ca3af' }}>{t.Category}</span>
                    <span style={{ fontSize: 12, color: t.Status === 'Approved' ? '#22c55e' : '#ef4444', fontWeight: 600 }}>{t.Status}</span>
                  </div>
                ))}
              </div>
            )}

            {/* Watch List */}
            <div style={{ background: '#0a0e1a', border: '1px solid #78350f', borderRadius: 8, padding: 16 }}>
              <div style={{ fontSize: 11, color: '#4b5563', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 8 }}>👁 Watch List for Incoming Engineer</div>
              {approved.length === 0
                ? <div style={{ fontSize: 13, color: '#6b7280' }}>No open items — all clear ✓</div>
                : <div style={{ fontSize: 13, color: '#d1d5db' }}>{approved.length} approved ticket{approved.length > 1 ? 's' : ''} escalated to GLPI teams. Monitor for resolution progress.</div>
              }
              {critical.filter(t => t.Status === 'Approved').length > 0 && (
                <div style={{ fontSize: 13, color: '#fcd34d', marginTop: 8 }}>
                  ⚡ {critical.filter(t => t.Status === 'Approved').length} critical ticket(s) pending resolution — prioritize immediately.
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

function GLPINotificationPanel({ ticket, onClose, onAction }) {
  const lines = ticket.ai_comment
    ? ticket.ai_comment.replace(/<[^>]+>/g, '').split('\n').filter(l => l.trim())
    : []
  const priorityLabels = { 6: 'Critical', 5: 'Very High', 4: 'High', 3: 'Medium', 2: 'Low' }
  const priority = priorityLabels[ticket.priority] || 'Medium'
  const c = SEV_COLORS[priority] || SEV_COLORS.Medium

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.75)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100, padding: 24 }}>
      <div style={{ background: '#111827', border: `1px solid ${c.dot}44`, borderRadius: 16, width: '100%', maxWidth: 680, maxHeight: '85vh', overflowY: 'auto', padding: 28 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 20 }}>
          <div>
            <div style={{ fontSize: 11, color: '#6b7280', letterSpacing: 1, textTransform: 'uppercase', marginBottom: 6 }}>🤖 AI Agent — Awaiting Your Review</div>
            <div style={{ fontSize: 18, fontWeight: 700, color: '#f9fafb' }}>GLPI #{ticket.glpi_id}</div>
            <div style={{ fontSize: 13, color: '#9ca3af', marginTop: 4 }}>{ticket.title}</div>
            <div style={{ marginTop: 8, display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
              <SeverityBadge severity={priority} />
              {ticket.assigned_team && (
                <span style={{ background: '#1e3a5f', color: '#93c5fd', padding: '2px 10px', borderRadius: 999, fontSize: 12, fontWeight: 500 }}>👥 {ticket.assigned_team}</span>
              )}
            </div>
          </div>
          <button onClick={onClose} style={{ background: 'none', border: '1px solid #374151', color: '#9ca3af', borderRadius: 8, padding: '6px 14px', cursor: 'pointer', fontSize: 13 }}>✕</button>
        </div>

        <div style={{ background: '#0a0e1a', border: '1px solid #1f2937', borderRadius: 8, padding: 16, marginBottom: 20, fontSize: 13, color: '#d1d5db', lineHeight: 1.8 }}>
          {lines.length > 0 ? lines.map((line, i) => (
            <div key={i} style={{ color: line.includes('=') ? '#60a5fa' : line.startsWith('✅') ? '#6ee7b7' : '#d1d5db' }}>{line}</div>
          )) : <div style={{ color: '#6b7280' }}>No AI analysis available yet.</div>}
        </div>

        <div style={{ display: 'flex', gap: 12 }}>
          <button onClick={() => onAction(ticket.glpi_id, 'approve')} style={{
            flex: 1, padding: '12px 0', background: '#065f46', color: '#6ee7b7',
            border: '1px solid #047857', borderRadius: 8, cursor: 'pointer', fontWeight: 700, fontSize: 14,
          }}>✅ Approve — Mark as Solved</button>
          <button onClick={() => onAction(ticket.glpi_id, 'reject')} style={{
            flex: 1, padding: '12px 0', background: '#450a0a', color: '#fca5a5',
            border: '1px solid #7f1d1d', borderRadius: 8, cursor: 'pointer', fontWeight: 700, fontSize: 14,
          }}>❌ Reject — Close Ticket</button>
        </div>
      </div>
    </div>
  )
}

export default function App() {
  const [tickets, setTickets] = useState([])
  const [stats, setStats] = useState({})
  const [selected, setSelected] = useState(null)
  const [selectedAt, setSelectedAt] = useState(null)
  const [loading, setLoading] = useState(true)
  const [sevFilter, setSevFilter] = useState('All')
  const [glpiPending, setGlpiPending] = useState([])
  const [glpiNotif, setGlpiNotif] = useState(null)
  const [showHandoff, setShowHandoff] = useState(false)
  const [clock, setClock] = useState(new Date())
  const seenGlpiIds = useRef(new Set())

  useEffect(() => {
    fetchData()
    const glpiIv = setInterval(pollGlpiPending, 15000)
    pollGlpiPending()
    const clockIv = setInterval(() => setClock(new Date()), 1000)
    return () => { clearInterval(glpiIv); clearInterval(clockIv) }
  }, [])

  async function pollGlpiPending() {
    try {
      const res = await axios.get(`${API}/glpi/pending-review`)
      const pending = res.data
      const newOnes = pending.filter(t => !seenGlpiIds.current.has(t.glpi_id))
      if (newOnes.length > 0) {
        newOnes.forEach(t => seenGlpiIds.current.add(t.glpi_id))
        setGlpiPending(pending)
        setGlpiNotif(newOnes[0])
        if (Notification.permission === 'granted') {
          new Notification('🤖 NOC Agent — Review Required', { body: `Ticket: ${newOnes[0].title}`, icon: '/favicon.ico' })
        }
      }
    } catch {}
  }

  async function handleGlpiAction(glpiId, action) {
    try {
      await axios.post(`${API}/glpi/action`, { glpi_id: glpiId, action })
      setGlpiNotif(null)
      setGlpiPending(prev => prev.filter(t => t.glpi_id !== glpiId))
      const remaining = glpiPending.filter(t => t.glpi_id !== glpiId)
      if (remaining.length > 0) setTimeout(() => setGlpiNotif(remaining[0]), 500)
    } catch (e) { console.error('Action failed', e) }
  }

  async function fetchData() {
    setLoading(true)
    try {
      const [t, s] = await Promise.all([axios.get(`${API}/tickets`), axios.get(`${API}/stats`)])
      setTickets(t.data); setStats(s.data)
    } catch {}
    setLoading(false)
  }

  function handleSelectTicket(ticket) { setSelected(ticket); setSelectedAt(Date.now()) }

  function handleAction(ticketId, action) {
    setTickets(prev => prev.filter(t => t.Ticket_ID !== ticketId))
    setStats(prev => ({
      ...prev, total: (prev.total || 0) + 1,
      approved: action === 'approve' ? (prev.approved || 0) + 1 : prev.approved,
      rejected: action === 'reject' ? (prev.rejected || 0) + 1 : prev.rejected,
    }))
    setSelected(null)
  }

  const filtered = sevFilter === 'All' ? tickets : tickets.filter(t => t.Severity === sevFilter)

  return (
    <div style={{ minHeight: '100vh', background: '#0a0e1a' }}>
      {/* Top Bar */}
      <div style={{ background: '#060910', borderBottom: '1px solid #1f2937', padding: '0 32px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', height: 56 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ fontSize: 20 }}>🛡️</span>
          <span style={{ fontWeight: 700, fontSize: 15, color: '#f9fafb' }}>Emircom NOC Command Center</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <button onClick={() => setShowHandoff(true)} style={{
            padding: '5px 14px', borderRadius: 8, background: '#1e3a5f', color: '#93c5fd',
            border: '1px solid #1d4ed8', cursor: 'pointer', fontSize: 12, fontWeight: 600,
          }}>📋 Handoff Report</button>
          <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#22c55e', display: 'inline-block' }} />
          <span style={{ fontSize: 12, color: '#6b7280' }}>Live</span>
          <span style={{ fontSize: 12, color: '#374151', marginLeft: 4 }}>{clock.toLocaleTimeString()}</span>
        </div>
      </div>

      <div style={{ padding: '24px 32px' }}>
        {/* Stats */}
        <div style={{ display: 'flex', gap: 16, marginBottom: 24 }}>
          <StatCard label="Pending Tickets" value={tickets.length} color="#60a5fa" />
          <StatCard label="Approved" value={stats.approved || 0} color="#22c55e" />
          <StatCard label="Rejected" value={stats.rejected || 0} color="#ef4444" />
          <StatCard label="Total Processed" value={stats.total || 0} color="#a78bfa" />
        </div>

        {/* Queue Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
          <div>
            <div style={{ fontWeight: 700, fontSize: 16, color: '#f9fafb' }}>Alert Queue</div>
            <div style={{ fontSize: 13, color: '#6b7280', marginTop: 2 }}>{filtered.length} tickets pending review</div>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            {['All', 'Critical', 'High', 'Medium', 'Low'].map(s => (
              <button key={s} onClick={() => setSevFilter(s)} style={{
                padding: '5px 14px', borderRadius: 999, border: '1px solid',
                borderColor: sevFilter === s ? '#3b82f6' : '#1f2937',
                background: sevFilter === s ? '#1e3a5f' : 'transparent',
                color: sevFilter === s ? '#93c5fd' : '#6b7280',
                cursor: 'pointer', fontSize: 12, fontWeight: 500,
              }}>{s}</button>
            ))}
            <button onClick={fetchData} style={{
              padding: '5px 14px', borderRadius: 999, border: '1px solid #1f2937',
              background: 'transparent', color: '#6b7280', cursor: 'pointer', fontSize: 12,
            }}>↻ Refresh</button>
          </div>
        </div>

        {/* Table */}
        <div style={{ background: '#0d1117', border: '1px solid #1f2937', borderRadius: 12, overflow: 'hidden' }}>
          <div style={{ display: 'grid', gridTemplateColumns: '120px 100px 110px 1fr 140px', gap: 16, padding: '10px 20px', borderBottom: '1px solid #1f2937', background: '#060910' }}>
            {['Ticket ID', 'Severity', 'Category', 'Alert', 'Time'].map(h => (
              <span key={h} style={{ fontSize: 11, color: '#4b5563', textTransform: 'uppercase', letterSpacing: 1 }}>{h}</span>
            ))}
          </div>
          {loading ? (
            <div style={{ padding: '40px 0', textAlign: 'center', color: '#4b5563' }}>Loading tickets...</div>
          ) : filtered.length === 0 ? (
            <div style={{ padding: '40px 0', textAlign: 'center', color: '#4b5563' }}>
              {tickets.length === 0 ? 'No pending tickets — all clear ✓' : 'No tickets match this filter'}
            </div>
          ) : (
            filtered.map(t => <TicketRow key={t.Ticket_ID} ticket={t} onSelect={handleSelectTicket} />)
          )}
        </div>

        {filtered.length === 0 && tickets.length === 0 && !loading && (
          <div style={{ marginTop: 16, padding: 16, background: '#0d1117', border: '1px solid #1f2937', borderRadius: 8, color: '#6b7280', fontSize: 13 }}>
            💡 Make sure the FastAPI backend is running: <code style={{ color: '#60a5fa' }}>uvicorn backend.main:app --reload</code>
          </div>
        )}
      </div>

      {selected && <TicketDetail ticket={selected} openedAt={selectedAt} onClose={() => setSelected(null)} onAction={handleAction} />}
      {glpiNotif && !selected && <GLPINotificationPanel ticket={glpiNotif} onClose={() => setGlpiNotif(null)} onAction={handleGlpiAction} />}
      {showHandoff && <HandoffReport onClose={() => setShowHandoff(false)} />}

      {glpiPending.length > 0 && !glpiNotif && !selected && (
        <div onClick={() => setGlpiNotif(glpiPending[0])} style={{
          position: 'fixed', bottom: 24, right: 24,
          background: '#7f1d1d', border: '1px solid #ef4444',
          borderRadius: 12, padding: '12px 20px',
          cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 10,
          boxShadow: '0 0 20px rgba(239,68,68,0.4)', animation: 'pulse 2s infinite',
        }}>
          <span style={{ fontSize: 18 }}>🔔</span>
          <div>
            <div style={{ fontSize: 13, fontWeight: 700, color: '#fca5a5' }}>
              {glpiPending.length} ticket{glpiPending.length > 1 ? 's' : ''} awaiting review
            </div>
            <div style={{ fontSize: 11, color: '#f87171' }}>
              {glpiPending[0]?.assigned_team ? `👥 ${glpiPending[0].assigned_team}` : 'Click to review'}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
