import { useEffect, useState } from 'react'
import {
  PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer,
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
} from 'recharts'

const API = 'http://localhost:8001'

const COLORS = ['#6366f1', '#22d3ee', '#f59e0b', '#ef4444', '#10b981', '#a78bfa']

const card = {
  background: '#111827',
  border: '1px solid #1f2937',
  borderRadius: 10,
  padding: '20px 24px',
}

const chartTheme = {
  background: '#111827',
  text: '#6b7280',
  grid: '#1f2937',
}

function KpiCard({ label, value, accent }) {
  return (
    <div style={{ ...card, borderLeft: `4px solid ${accent || '#6366f1'}`, flex: 1, minWidth: 140 }}>
      <div style={{ fontSize: 28, fontWeight: 700, color: '#f9fafb' }}>{value}</div>
      <div style={{ fontSize: 12, color: '#6b7280', marginTop: 4 }}>{label}</div>
    </div>
  )
}

function SectionTitle({ children }) {
  return (
    <div style={{ fontSize: 13, fontWeight: 600, color: '#9ca3af', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 12, marginTop: 32 }}>
      {children}
    </div>
  )
}

export default function Analytics() {
  const [tickets, setTickets] = useState([])
  const [loading, setLoading] = useState(true)
  const [filters, setFilters] = useState({ category: 'All', severity: 'All', status: 'All' })

  useEffect(() => {
    fetch(`${API}/tickets/processed`)
      .then(r => r.json())
      .then(data => { setTickets(data); setLoading(false) })
      .catch(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '60vh', color: '#6b7280' }}>
        Loading analytics...
      </div>
    )
  }

  // ── KPI calculations ─────────────────────────────────────────────────────
  const total = tickets.length
  const approved = tickets.filter(t => t.Status === 'Approved').length
  const rejected = tickets.filter(t => t.Status === 'Rejected').length
  const critical = tickets.filter(t => t.Severity === 'Critical').length
  const slaBreached = tickets.filter(t => t.SLA_Breached).length
  const slaCompliance = total > 0 ? (((total - slaBreached) / total) * 100).toFixed(1) : '—'
  const confScores = tickets
    .map(t => parseFloat(t.Confidence_Score))
    .filter(n => !isNaN(n))
  const avgConf = confScores.length > 0
    ? (confScores.reduce((a, b) => a + b, 0) / confScores.length).toFixed(1)
    : '—'

  // ── Chart data ────────────────────────────────────────────────────────────
  const categoryCount = {}
  const severityCount = {}
  const statusByCategory = {}
  const slaByCategory = {}

  tickets.forEach(t => {
    const cat = t.Category || 'Unknown'
    const sev = t.Severity || 'Unknown'
    const st = t.Status || 'Unknown'

    categoryCount[cat] = (categoryCount[cat] || 0) + 1
    severityCount[sev] = (severityCount[sev] || 0) + 1

    if (!statusByCategory[cat]) statusByCategory[cat] = { category: cat, Approved: 0, Rejected: 0 }
    statusByCategory[cat][st] = (statusByCategory[cat][st] || 0) + 1

    if (!slaByCategory[sev]) slaByCategory[sev] = { severity: sev, OK: 0, Breached: 0 }
    if (t.SLA_Breached) slaByCategory[sev].Breached += 1
    else slaByCategory[sev].OK += 1
  })

  // Confidence histogram
  const confBuckets = { '0–20': 0, '20–40': 0, '40–60': 0, '60–80': 0, '80–100': 0 }
  confScores.forEach(n => {
    if (n <= 20) confBuckets['0–20']++
    else if (n <= 40) confBuckets['20–40']++
    else if (n <= 60) confBuckets['40–60']++
    else if (n <= 80) confBuckets['60–80']++
    else confBuckets['80–100']++
  })

  const pieData = Object.entries(categoryCount).map(([name, value]) => ({ name, value }))
  const severityData = Object.entries(severityCount).map(([name, value]) => ({ name, value }))
  const statusByCatData = Object.values(statusByCategory)
  const slaData = Object.values(slaByCategory)
  const confHistData = Object.entries(confBuckets).map(([name, value]) => ({ name, value }))
  const volumeData = Object.entries(categoryCount).map(([name, value]) => ({ name, value }))

  // ── Filter options ────────────────────────────────────────────────────────
  const categories = ['All', ...new Set(tickets.map(t => t.Category).filter(Boolean))]
  const severities = ['All', ...new Set(tickets.map(t => t.Severity).filter(Boolean))]
  const statuses = ['All', ...new Set(tickets.map(t => t.Status).filter(Boolean))]

  const filtered = tickets.filter(t =>
    (filters.category === 'All' || t.Category === filters.category) &&
    (filters.severity === 'All' || t.Severity === filters.severity) &&
    (filters.status === 'All' || t.Status === filters.status)
  )

  const dropdownStyle = {
    background: '#1f2937', color: '#d1d5db', border: '1px solid #374151',
    borderRadius: 6, padding: '6px 12px', fontSize: 13, cursor: 'pointer',
  }

  const tooltipStyle = { backgroundColor: '#1f2937', border: '1px solid #374151', color: '#d1d5db', fontSize: 12 }

  return (
    <div style={{ background: '#0a0e1a', minHeight: '100vh', padding: '28px 32px', fontFamily: 'inherit' }}>
      <div style={{ fontSize: 22, fontWeight: 700, color: '#f9fafb', marginBottom: 4 }}>Analytics</div>
      <div style={{ fontSize: 13, color: '#6b7280', marginBottom: 28 }}>
        {total} tickets processed
      </div>

      {/* KPI cards */}
      <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap', marginBottom: 8 }}>
        <KpiCard label="Total Processed" value={total} accent="#6366f1" />
        <KpiCard label="Approved" value={approved} accent="#10b981" />
        <KpiCard label="Rejected" value={rejected} accent="#ef4444" />
        <KpiCard label="Critical" value={critical} accent="#f59e0b" />
        <KpiCard label="Avg Confidence" value={avgConf === '—' ? '—' : `${avgConf}%`} accent="#22d3ee" />
        <KpiCard label="SLA Compliance" value={slaCompliance === '—' ? '—' : `${slaCompliance}%`} accent="#a78bfa" />
      </div>

      {/* Charts grid */}
      <SectionTitle>Charts</SectionTitle>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>

        {/* Category donut */}
        <div style={card}>
          <div style={{ fontSize: 13, fontWeight: 600, color: '#d1d5db', marginBottom: 16 }}>Category Breakdown</div>
          <ResponsiveContainer width="100%" height={220}>
            <PieChart>
              <Pie data={pieData} cx="50%" cy="50%" innerRadius={55} outerRadius={85} dataKey="value" paddingAngle={3}>
                {pieData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
              </Pie>
              <Tooltip contentStyle={tooltipStyle} />
              <Legend iconType="circle" iconSize={9} wrapperStyle={{ fontSize: 12, color: '#6b7280' }} />
            </PieChart>
          </ResponsiveContainer>
        </div>

        {/* Severity distribution */}
        <div style={card}>
          <div style={{ fontSize: 13, fontWeight: 600, color: '#d1d5db', marginBottom: 16 }}>Severity Distribution</div>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={severityData} barCategoryGap="35%">
              <CartesianGrid strokeDasharray="3 3" stroke={chartTheme.grid} />
              <XAxis dataKey="name" tick={{ fill: chartTheme.text, fontSize: 12 }} />
              <YAxis tick={{ fill: chartTheme.text, fontSize: 12 }} />
              <Tooltip contentStyle={tooltipStyle} />
              <Bar dataKey="value" name="Tickets" radius={[4, 4, 0, 0]}>
                {severityData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Status by category stacked */}
        <div style={card}>
          <div style={{ fontSize: 13, fontWeight: 600, color: '#d1d5db', marginBottom: 16 }}>Status by Category</div>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={statusByCatData} barCategoryGap="30%">
              <CartesianGrid strokeDasharray="3 3" stroke={chartTheme.grid} />
              <XAxis dataKey="category" tick={{ fill: chartTheme.text, fontSize: 11 }} />
              <YAxis tick={{ fill: chartTheme.text, fontSize: 12 }} />
              <Tooltip contentStyle={tooltipStyle} />
              <Legend iconType="square" iconSize={10} wrapperStyle={{ fontSize: 12, color: '#6b7280' }} />
              <Bar dataKey="Approved" stackId="a" fill="#10b981" radius={[0, 0, 0, 0]} />
              <Bar dataKey="Rejected" stackId="a" fill="#ef4444" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Confidence histogram */}
        <div style={card}>
          <div style={{ fontSize: 13, fontWeight: 600, color: '#d1d5db', marginBottom: 16 }}>Confidence Score Distribution</div>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={confHistData} barCategoryGap="25%">
              <CartesianGrid strokeDasharray="3 3" stroke={chartTheme.grid} />
              <XAxis dataKey="name" tick={{ fill: chartTheme.text, fontSize: 12 }} />
              <YAxis tick={{ fill: chartTheme.text, fontSize: 12 }} />
              <Tooltip contentStyle={tooltipStyle} />
              <Bar dataKey="value" name="Tickets" fill="#6366f1" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* SLA compliance by severity */}
        <div style={card}>
          <div style={{ fontSize: 13, fontWeight: 600, color: '#d1d5db', marginBottom: 16 }}>SLA Compliance by Severity</div>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={slaData} barCategoryGap="30%">
              <CartesianGrid strokeDasharray="3 3" stroke={chartTheme.grid} />
              <XAxis dataKey="severity" tick={{ fill: chartTheme.text, fontSize: 12 }} />
              <YAxis tick={{ fill: chartTheme.text, fontSize: 12 }} />
              <Tooltip contentStyle={tooltipStyle} />
              <Legend iconType="square" iconSize={10} wrapperStyle={{ fontSize: 12, color: '#6b7280' }} />
              <Bar dataKey="OK" name="On Time" fill="#10b981" radius={[0, 0, 0, 0]} />
              <Bar dataKey="Breached" name="Breached" fill="#ef4444" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Ticket volume by category */}
        <div style={card}>
          <div style={{ fontSize: 13, fontWeight: 600, color: '#d1d5db', marginBottom: 16 }}>Ticket Volume by Category</div>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={volumeData} barCategoryGap="35%">
              <CartesianGrid strokeDasharray="3 3" stroke={chartTheme.grid} />
              <XAxis dataKey="name" tick={{ fill: chartTheme.text, fontSize: 11 }} />
              <YAxis tick={{ fill: chartTheme.text, fontSize: 12 }} />
              <Tooltip contentStyle={tooltipStyle} />
              <Bar dataKey="value" name="Tickets" fill="#22d3ee" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Audit log */}
      <SectionTitle>Audit Log</SectionTitle>
      <div style={{ display: 'flex', gap: 10, marginBottom: 14, flexWrap: 'wrap' }}>
        {[
          { label: 'Category', key: 'category', options: categories },
          { label: 'Severity', key: 'severity', options: severities },
          { label: 'Status', key: 'status', options: statuses },
        ].map(({ label, key, options }) => (
          <div key={key} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ fontSize: 12, color: '#6b7280' }}>{label}:</span>
            <select
              style={dropdownStyle}
              value={filters[key]}
              onChange={e => setFilters(f => ({ ...f, [key]: e.target.value }))}
            >
              {options.map(o => <option key={o} value={o}>{o}</option>)}
            </select>
          </div>
        ))}
        <span style={{ fontSize: 12, color: '#4b5563', alignSelf: 'center', marginLeft: 6 }}>
          {filtered.length} row{filtered.length !== 1 ? 's' : ''}
        </span>
      </div>

      <div style={{ ...card, padding: 0, overflow: 'hidden' }}>
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ background: '#1f2937' }}>
                {['Ticket ID', 'Category', 'Severity', 'Status', 'Confidence', 'SLA Breached', 'Response Time'].map(h => (
                  <th key={h} style={{ padding: '10px 14px', textAlign: 'left', color: '#9ca3af', fontWeight: 600, borderBottom: '1px solid #374151', whiteSpace: 'nowrap' }}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0 ? (
                <tr>
                  <td colSpan={7} style={{ padding: '28px 14px', textAlign: 'center', color: '#4b5563' }}>
                    No tickets match the selected filters.
                  </td>
                </tr>
              ) : filtered.map((t, i) => {
                const sevColor = { Critical: '#ef4444', High: '#f59e0b', Medium: '#6366f1', Low: '#10b981' }[t.Severity] || '#6b7280'
                const stColor = t.Status === 'Approved' ? '#10b981' : '#ef4444'
                return (
                  <tr key={t.Ticket_ID || i} style={{ borderBottom: '1px solid #1f2937' }}>
                    <td style={{ padding: '9px 14px', color: '#e5e7eb', fontFamily: 'monospace' }}>{t.Ticket_ID || '—'}</td>
                    <td style={{ padding: '9px 14px', color: '#d1d5db' }}>{t.Category || '—'}</td>
                    <td style={{ padding: '9px 14px' }}>
                      <span style={{ background: `${sevColor}22`, color: sevColor, padding: '2px 8px', borderRadius: 4, fontSize: 12 }}>
                        {t.Severity || '—'}
                      </span>
                    </td>
                    <td style={{ padding: '9px 14px' }}>
                      <span style={{ background: `${stColor}22`, color: stColor, padding: '2px 8px', borderRadius: 4, fontSize: 12 }}>
                        {t.Status || '—'}
                      </span>
                    </td>
                    <td style={{ padding: '9px 14px', color: '#9ca3af' }}>
                      {t.Confidence_Score !== '' && t.Confidence_Score != null ? `${t.Confidence_Score}%` : '—'}
                    </td>
                    <td style={{ padding: '9px 14px' }}>
                      <span style={{ color: t.SLA_Breached ? '#ef4444' : '#10b981', fontSize: 13 }}>
                        {t.SLA_Breached ? '⚠ Yes' : '✓ No'}
                      </span>
                    </td>
                    <td style={{ padding: '9px 14px', color: '#9ca3af' }}>
                      {t.Response_Time_Secs != null ? `${t.Response_Time_Secs}s` : '—'}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* PIR section */}
      <SectionTitle>Post-Incident Reports (PIR)</SectionTitle>
      <div style={{ ...card, display: 'flex', alignItems: 'center', gap: 14, color: '#4b5563' }}>
        <div style={{ fontSize: 28 }}>📄</div>
        <div>
          <div style={{ fontSize: 14, fontWeight: 600, color: '#6b7280' }}>PIR Downloads — Coming Soon</div>
          <div style={{ fontSize: 12, marginTop: 4 }}>Generated post-incident reports will appear here for download.</div>
        </div>
      </div>
    </div>
  )
}
