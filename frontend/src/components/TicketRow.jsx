import { CAT_ICONS } from '../constants'
import SeverityBadge from './SeverityBadge'

export default function TicketRow({ ticket, onSelect }) {
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
      <SeverityBadge severity={ticket.Severity || 'Medium'} />
      <span style={{ fontSize: 13, color: '#9ca3af' }}>{CAT_ICONS[ticket.Category] || '📋'} {ticket.Category}</span>
      <span style={{ fontSize: 13, color: '#d1d5db', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        {ticket.Alert_Message || ticket.description || '—'}
      </span>
      <span style={{ fontSize: 12, color: '#4b5563', textAlign: 'right' }}>{ticket.Timestamp || '—'}</span>
    </div>
  )
}
