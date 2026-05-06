import { useState, useEffect } from 'react'
import axios from 'axios'
import { API, SEV_COLORS, CAT_ICONS } from '../constants'

const input = (extra = {}) => ({
  width: '100%', padding: '10px 14px', background: '#0a0e1a',
  border: '1px solid #1f2937', borderRadius: 8, color: '#d1d5db',
  fontSize: 14, outline: 'none', boxSizing: 'border-box', ...extra,
})

export default function Reports() {
  const [form, setForm] = useState({ outgoing: '', incoming: '', period: '' })
  const [report, setReport] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [pirList, setPirList] = useState([])

  useEffect(() => {
    axios.get(`${API}/pir/list`).then(r => setPirList(r.data || [])).catch(() => {})
  }, [])

  function set(field) {
    return e => setForm(f => ({ ...f, [field]: e.target.value }))
  }

  async function generate() {
    if (!form.outgoing || !form.incoming || !form.period) {
      setError('Please fill in all three fields before generating.')
      return
    }
    setError(null)
    setLoading(true)
    try {
      const [ticketsRes, statsRes] = await Promise.all([
        axios.get(`${API}/tickets/processed`),
        axios.get(`${API}/stats`),
      ])
      const tickets = ticketsRes.data || []
      const stats = statsRes.data || {}
      setReport({ tickets, stats, ...form, generatedAt: new Date().toLocaleString() })
    } catch (e) {
      setError(e.response?.data?.detail || 'Failed to fetch data — backend may be unavailable.')
    } finally {
      setLoading(false)
    }
  }

  // derived report data
  const byCat = {}
  const critical = []
  if (report) {
    report.tickets.forEach(t => {
      const cat = t.category || t.Category || 'Unknown'
      byCat[cat] = (byCat[cat] || 0) + 1
      if ((t.severity || t.Severity || '').toLowerCase() === 'critical') critical.push(t)
    })
  }

  const metricCard = (label, value, color) => (
    <div key={label} style={{
      background: '#0a0e1a', border: '1px solid #1f2937', borderRadius: 10,
      padding: '18px 22px', flex: 1,
    }}>
      <div style={{ fontSize: 26, fontWeight: 700, color: color || '#f9fafb' }}>{value ?? '—'}</div>
      <div style={{ fontSize: 12, color: '#4b5563', marginTop: 4 }}>{label}</div>
    </div>
  )

  return (
    <div style={{ padding: 32, color: '#f9fafb', minHeight: '100vh', maxWidth: 900 }}>
      <div style={{ fontSize: 22, fontWeight: 700, marginBottom: 4 }}>Shift Handoff Report</div>
      <div style={{ fontSize: 13, color: '#4b5563', marginBottom: 28 }}>
        Generate an end-of-shift summary for outgoing and incoming engineers.
      </div>

      {/* Form */}
      <div style={{ background: '#111827', border: '1px solid #1f2937', borderRadius: 12, padding: 24, marginBottom: 24 }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 16, marginBottom: 18 }}>
          <div>
            <label style={{ fontSize: 12, color: '#4b5563', textTransform: 'uppercase', letterSpacing: 1, display: 'block', marginBottom: 6 }}>
              Outgoing Engineer
            </label>
            <input style={input()} placeholder="e.g. John Smith" value={form.outgoing} onChange={set('outgoing')} />
          </div>
          <div>
            <label style={{ fontSize: 12, color: '#4b5563', textTransform: 'uppercase', letterSpacing: 1, display: 'block', marginBottom: 6 }}>
              Incoming Engineer
            </label>
            <input style={input()} placeholder="e.g. Sara Ali" value={form.incoming} onChange={set('incoming')} />
          </div>
          <div>
            <label style={{ fontSize: 12, color: '#4b5563', textTransform: 'uppercase', letterSpacing: 1, display: 'block', marginBottom: 6 }}>
              Shift Period
            </label>
            <input style={input()} placeholder="e.g. 08:00 – 16:00" value={form.period} onChange={set('period')} />
          </div>
        </div>

        {error && (
          <div style={{ background: '#450a0a', border: '1px solid #7f1d1d', borderRadius: 8, padding: '10px 14px', color: '#fca5a5', fontSize: 13, marginBottom: 14 }}>
            ⚠️ {error}
          </div>
        )}

        <button onClick={generate} disabled={loading} style={{
          padding: '11px 28px', background: loading ? '#1f2937' : '#1e3a5f',
          color: loading ? '#4b5563' : '#93c5fd',
          border: '1px solid #3b82f6', borderRadius: 8, cursor: loading ? 'not-allowed' : 'pointer',
          fontSize: 14, fontWeight: 600,
        }}>
          {loading ? 'Generating…' : '📄 Generate Report'}
        </button>
      </div>

      {/* Generated report */}
      {report && (
        <div style={{ background: '#111827', border: '1px solid #1f2937', borderRadius: 12, overflow: 'hidden', marginBottom: 24 }}>
          {/* Cover */}
          <div style={{ background: '#0a0e1a', borderBottom: '1px solid #1f2937', padding: '24px 28px' }}>
            <div style={{ fontSize: 11, color: '#4b5563', letterSpacing: 1, textTransform: 'uppercase', marginBottom: 6 }}>
              Emircom NOC — AI-Generated Shift Report
            </div>
            <div style={{ fontSize: 20, fontWeight: 700, color: '#f9fafb' }}>Shift Handoff Summary</div>
            <div style={{ display: 'flex', gap: 32, marginTop: 12, flexWrap: 'wrap' }}>
              {[
                ['Outgoing', report.outgoing],
                ['Incoming', report.incoming],
                ['Shift Period', report.period],
                ['Generated', report.generatedAt],
              ].map(([k, v]) => (
                <div key={k}>
                  <div style={{ fontSize: 11, color: '#4b5563', textTransform: 'uppercase', letterSpacing: 1 }}>{k}</div>
                  <div style={{ fontSize: 13, color: '#d1d5db', marginTop: 2 }}>{v}</div>
                </div>
              ))}
            </div>
          </div>

          <div style={{ padding: 24 }}>
            {/* Metric cards */}
            <div style={{ display: 'flex', gap: 12, marginBottom: 24, flexWrap: 'wrap' }}>
              {metricCard('Total Processed', report.stats.total, '#60a5fa')}
              {metricCard('Approved', report.stats.approved, '#22c55e')}
              {metricCard('Rejected', report.stats.rejected, '#ef4444')}
              {metricCard('Still Pending', report.stats.pending, '#f59e0b')}
            </div>

            {/* By category */}
            <div style={{ marginBottom: 24 }}>
              <div style={{ fontSize: 12, color: '#4b5563', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 12 }}>
                Tickets by Category
              </div>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                {Object.keys(byCat).length === 0
                  ? <span style={{ color: '#374151', fontSize: 13 }}>No data</span>
                  : Object.entries(byCat).map(([cat, count]) => (
                    <span key={cat} style={{
                      padding: '5px 14px', borderRadius: 999, background: '#1e3a5f',
                      color: '#93c5fd', fontSize: 13, fontWeight: 500,
                    }}>
                      {CAT_ICONS[cat] || '📋'} {cat} ({count})
                    </span>
                  ))
                }
              </div>
            </div>

            {/* Critical incidents */}
            <div style={{ marginBottom: 24 }}>
              <div style={{ fontSize: 12, color: '#4b5563', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 12 }}>
                Critical Incidents This Shift
              </div>
              {critical.length === 0
                ? <div style={{ color: '#374151', fontSize: 13 }}>No critical incidents recorded.</div>
                : critical.map((t, i) => (
                  <div key={i} style={{
                    background: '#0a0e1a', border: '1px solid #7f1d1d', borderRadius: 8,
                    padding: '10px 14px', marginBottom: 8, display: 'flex', gap: 16, alignItems: 'center',
                  }}>
                    <span style={{ fontFamily: 'monospace', color: '#fca5a5', fontSize: 13 }}>
                      {t.ticket_id || t.Ticket_ID}
                    </span>
                    <span style={{ fontSize: 13, color: '#d1d5db', flex: 1 }}>
                      {t.alert_message || t.Alert_Message || t.description || '—'}
                    </span>
                    <span style={{ fontSize: 12, color: '#4b5563' }}>{t.category || t.Category}</span>
                  </div>
                ))
              }
            </div>

            {/* Watch list */}
            <div style={{ marginBottom: 24 }}>
              <div style={{ fontSize: 12, color: '#4b5563', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 12 }}>
                Watch List — High Severity
              </div>
              {report.tickets.filter(t => (t.severity || t.Severity || '').toLowerCase() === 'high').length === 0
                ? <div style={{ color: '#374151', fontSize: 13 }}>No high-severity tickets pending.</div>
                : report.tickets
                    .filter(t => (t.severity || t.Severity || '').toLowerCase() === 'high')
                    .slice(0, 5)
                    .map((t, i) => (
                      <div key={i} style={{
                        background: '#0a0e1a', border: '1px solid #78350f', borderRadius: 8,
                        padding: '10px 14px', marginBottom: 8, display: 'flex', gap: 16, alignItems: 'center',
                      }}>
                        <span style={{ fontFamily: 'monospace', color: '#fcd34d', fontSize: 13 }}>
                          {t.ticket_id || t.Ticket_ID}
                        </span>
                        <span style={{ fontSize: 13, color: '#d1d5db', flex: 1 }}>
                          {t.alert_message || t.Alert_Message || t.description || '—'}
                        </span>
                      </div>
                    ))
              }
            </div>

            {/* Download */}
            <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
              <button
                onClick={() => window.open(`${API}/handoff/export`, '_blank')}
                style={{
                  padding: '11px 24px', background: '#065f46', color: '#6ee7b7',
                  border: '1px solid #047857', borderRadius: 8, cursor: 'pointer',
                  fontSize: 14, fontWeight: 600,
                }}
              >
                ⬇️ Download Excel
              </button>
            </div>
          </div>

        </div>
      )}

      {/* PIR Downloads */}
      <div style={{ background: '#111827', border: '1px solid #1f2937', borderRadius: 12, overflow: 'hidden', marginBottom: 24 }}>
        <div style={{ background: '#0a0e1a', borderBottom: '1px solid #1f2937', padding: '16px 24px' }}>
          <div style={{ fontSize: 12, color: '#4b5563', textTransform: 'uppercase', letterSpacing: 1 }}>
            Post-Incident Reviews (PIR)
          </div>
        </div>
        <div style={{ padding: 24 }}>
          {pirList.length === 0 ? (
            <div style={{ fontSize: 13, color: '#374151' }}>
              No PIR files generated yet — PIRs are created automatically when tickets are approved
            </div>
          ) : (
            pirList.map(({ filename, ticket_id }) => (
              <div key={ticket_id} style={{
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                padding: '10px 14px', background: '#0a0e1a', border: '1px solid #1f2937',
                borderRadius: 8, marginBottom: 8,
              }}>
                <span style={{ fontFamily: 'monospace', color: '#93c5fd', fontSize: 13 }}>{ticket_id}</span>
                <button
                  onClick={() => window.open(`${API}/pir/download/${ticket_id}`, '_blank')}
                  style={{
                    padding: '6px 16px', background: '#1e3a5f', color: '#93c5fd',
                    border: '1px solid #3b82f6', borderRadius: 6, cursor: 'pointer',
                    fontSize: 13, fontWeight: 600,
                  }}
                >
                  📥 Download
                </button>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  )
}
