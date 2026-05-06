import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'
import { API } from '../constants'
import StatCard from '../components/StatCard'
import TicketRow from '../components/TicketRow'
import GLPINotificationPanel from '../components/GLPINotificationPanel'

const SEVERITIES = ['All', 'Critical', 'High', 'Medium', 'Low']

export default function Dashboard() {
  const navigate = useNavigate()
  const [tickets, setTickets] = useState([])
  const [stats, setStats] = useState({ pending: 0, approved: 0, rejected: 0, total: 0 })
  const [filter, setFilter] = useState('All')
  const [glpiTickets, setGlpiTickets] = useState([])
  const [glpiPanel, setGlpiPanel] = useState(null)
  const [bellVisible, setBellVisible] = useState(false)
  const [loading, setLoading] = useState(true)
  const pollRef = useRef(null)
  const [shiftBriefing, setShiftBriefing] = useState('')
  const [trendAnalysis, setTrendAnalysis] = useState('')

  async function fetchAll() {
    try {
      const [tRes, sRes] = await Promise.all([
        axios.get(`${API}/tickets`),
        axios.get(`${API}/stats`),
      ])
      setTickets(tRes.data || [])
      const s = sRes.data || {}
      setStats({
        pending: s.pending ?? 0,
        approved: s.approved ?? 0,
        rejected: s.rejected ?? 0,
        total: s.total ?? 0,
      })
    } catch {
      // backend not yet available — show empty state
    } finally {
      setLoading(false)
    }
  }

  async function pollGlpi() {
    try {
      const res = await axios.get(`${API}/glpi/pending-review`)
      const incoming = res.data || []
      if (incoming.length > 0 && !glpiPanel) setBellVisible(true)
      setGlpiTickets(incoming)
    } catch {
      // silent
    }
  }

  async function fetchTrendAnalysis() {
    try {
      const res = await axios.get(`${API}/trend-analysis`)
      setTrendAnalysis(res.data?.trend || '')
    } catch { /* silent */ }
  }

  useEffect(() => {
    fetchAll()
    axios.get(`${API}/shift-briefing`).then(r => setShiftBriefing(r.data?.briefing || '')).catch(() => {})
    pollRef.current = setInterval(pollGlpi, 15000)
    return () => clearInterval(pollRef.current)
  }, [])

  async function handleGlpiAction(glpiId, action) {
    try {
      await axios.post(`${API}/glpi/review`, { glpi_id: glpiId, action })
    } catch { /* silent */ }
    setGlpiPanel(null)
    setBellVisible(false)
    setGlpiTickets(prev => prev.filter(t => t.glpi_id !== glpiId))
  }

  function openGlpiPanel() {
    if (glpiTickets.length > 0) {
      setGlpiPanel(glpiTickets[0])
      setBellVisible(false)
    }
  }

  const filtered = filter === 'All' ? tickets : tickets.filter(t => t.Severity === filter)

  const filterBtn = (sev) => ({
    padding: '6px 16px', borderRadius: 999, fontSize: 13, cursor: 'pointer',
    border: filter === sev ? '1px solid #3b82f6' : '1px solid #1f2937',
    background: filter === sev ? '#1e3a5f' : '#111827',
    color: filter === sev ? '#93c5fd' : '#6b7280',
    transition: 'all 0.15s',
  })

  return (
    <div style={{ padding: 32, color: '#f9fafb', minHeight: '100vh' }}>
      {/* Header */}
      <div style={{ marginBottom: 28 }}>
        <div style={{ fontSize: 22, fontWeight: 700, color: '#f9fafb' }}>NOC Operations Dashboard</div>
        <div style={{ fontSize: 13, color: '#4b5563', marginTop: 4 }}>
          Real-time alert triage — AI-powered analysis pipeline
        </div>
      </div>

      {/* Stat Cards */}
      <div style={{ display: 'flex', gap: 16, marginBottom: 28 }}>
        <StatCard label="Pending Tickets" value={stats.pending} color="#f59e0b" />
        <StatCard label="Approved" value={stats.approved} color="#22c55e" />
        <StatCard label="Rejected" value={stats.rejected} color="#ef4444" />
        <StatCard label="Total Processed" value={stats.total} color="#60a5fa" />
      </div>

      {/* Shift Briefing Banner */}
      {shiftBriefing && (
        <div style={{ marginBottom: 16, padding: '12px 16px', background: '#1e3a5f', border: '1px solid #1d4ed8', borderRadius: 8, color: '#93c5fd', fontSize: 13 }}>
          <span style={{ fontWeight: 600, marginRight: 8 }}>Shift Briefing:</span>{shiftBriefing}
        </div>
      )}

      {/* Trend Analysis Banner */}
      {trendAnalysis && (
        <div style={{ marginBottom: 16, padding: '12px 16px', background: '#78350f', border: '1px solid #b45309', borderRadius: 8, color: '#fcd34d', fontSize: 13 }}>
          <span style={{ fontWeight: 600, marginRight: 8 }}>Trend Analysis:</span>{trendAnalysis}
        </div>
      )}

      {/* Filter + Table */}
      <div style={{ background: '#111827', border: '1px solid #1f2937', borderRadius: 12, overflow: 'hidden' }}>
        {/* Filter bar */}
        <div style={{ display: 'flex', gap: 8, padding: '16px 20px', borderBottom: '1px solid #1f2937', alignItems: 'center' }}>
          <span style={{ fontSize: 13, color: '#6b7280', marginRight: 4 }}>Severity:</span>
          {SEVERITIES.map(s => (
            <button key={s} style={filterBtn(s)} onClick={() => setFilter(s)}>{s}</button>
          ))}
          <span style={{ marginLeft: 'auto', fontSize: 12, color: '#374151' }}>
            {filtered.length} ticket{filtered.length !== 1 ? 's' : ''}
          </span>
        </div>

        {/* Table header */}
        <div style={{
          display: 'grid', gridTemplateColumns: '120px 100px 110px 1fr 140px',
          gap: 16, padding: '10px 20px',
          fontSize: 11, color: '#4b5563', letterSpacing: 1, textTransform: 'uppercase',
          borderBottom: '1px solid #1f2937',
        }}>
          <span>Ticket ID</span><span>Severity</span><span>Category</span>
          <span>Alert Message</span><span style={{ textAlign: 'right' }}>Timestamp</span>
        </div>

        {/* Rows */}
        {loading ? (
          <div style={{ padding: 40, textAlign: 'center', color: '#4b5563' }}>Loading tickets…</div>
        ) : filtered.length === 0 ? (
          <div style={{ padding: 40, textAlign: 'center', color: '#4b5563' }}>No tickets found.</div>
        ) : (
          filtered.map(ticket => (
            <TicketRow
              key={ticket.Ticket_ID}
              ticket={ticket}
              onSelect={t => { fetchTrendAnalysis(); navigate('/operations', { state: { ticket: t, openedAt: Date.now() } }) }}
            />
          ))
        )}
      </div>

      {/* GLPI panel */}
      {glpiPanel && (
        <GLPINotificationPanel
          ticket={glpiPanel}
          onClose={() => setGlpiPanel(null)}
          onAction={handleGlpiAction}
        />
      )}

      {/* Bell badge */}
      {bellVisible && !glpiPanel && (
        <button
          onClick={openGlpiPanel}
          style={{
            position: 'fixed', bottom: 32, right: 32,
            background: '#ef4444', color: '#fff',
            border: 'none', borderRadius: '50%', width: 52, height: 52,
            fontSize: 22, cursor: 'pointer', zIndex: 90,
            animation: 'pulse 1.5s infinite',
            boxShadow: '0 0 20px rgba(239,68,68,0.5)',
          }}
          title={`${glpiTickets.length} GLPI ticket(s) pending review`}
        >
          🔔
        </button>
      )}
    </div>
  )
}
