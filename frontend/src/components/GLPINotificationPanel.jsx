import { SEV_COLORS } from '../constants'
import SeverityBadge from './SeverityBadge'

export default function GLPINotificationPanel({ ticket, onClose, onAction }) {
  const lines = ticket.ai_comment
    ? ticket.ai_comment.replace(/<[^>]+>/g, '').split('\n').filter(l => l.trim())
    : []
  const priorityLabels = { 6: 'Critical', 5: 'Very High', 4: 'High', 3: 'Medium', 2: 'Low' }
  const priority = priorityLabels[ticket.priority] || 'Medium'
  const c = SEV_COLORS[priority] || SEV_COLORS.Medium

  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.75)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100, padding: 24,
    }}>
      <div style={{
        background: '#111827', border: `1px solid ${c.dot}44`, borderRadius: 16,
        width: '100%', maxWidth: 680, maxHeight: '85vh', overflowY: 'auto', padding: 28,
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 20 }}>
          <div>
            <div style={{ fontSize: 11, color: '#6b7280', letterSpacing: 1, textTransform: 'uppercase', marginBottom: 6 }}>
              🤖 AI Agent — Awaiting Your Review
            </div>
            <div style={{ fontSize: 18, fontWeight: 700, color: '#f9fafb' }}>GLPI #{ticket.glpi_id}</div>
            <div style={{ fontSize: 13, color: '#9ca3af', marginTop: 4 }}>{ticket.title}</div>
            <div style={{ marginTop: 8, display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
              <SeverityBadge severity={priority} />
              {ticket.assigned_team && (
                <span style={{ background: '#1e3a5f', color: '#93c5fd', padding: '2px 10px', borderRadius: 999, fontSize: 12, fontWeight: 500 }}>
                  👥 {ticket.assigned_team}
                </span>
              )}
            </div>
          </div>
          <button onClick={onClose} style={{
            background: 'none', border: '1px solid #374151', color: '#9ca3af',
            borderRadius: 8, padding: '6px 14px', cursor: 'pointer', fontSize: 13,
          }}>✕</button>
        </div>

        <div style={{
          background: '#0a0e1a', border: '1px solid #1f2937', borderRadius: 8,
          padding: 16, marginBottom: 20, fontSize: 13, color: '#d1d5db', lineHeight: 1.8,
        }}>
          {lines.length > 0
            ? lines.map((line, i) => (
                <div key={i} style={{ color: line.includes('=') ? '#60a5fa' : line.startsWith('✅') ? '#6ee7b7' : '#d1d5db' }}>
                  {line}
                </div>
              ))
            : <div style={{ color: '#6b7280' }}>No AI analysis available yet.</div>
          }
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
