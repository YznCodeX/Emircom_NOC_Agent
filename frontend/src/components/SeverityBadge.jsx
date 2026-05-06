import { SEV_COLORS } from '../constants'

export default function SeverityBadge({ severity }) {
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
