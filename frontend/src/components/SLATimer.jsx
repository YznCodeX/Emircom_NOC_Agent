import { useState, useEffect } from 'react'
import { SLA_MINUTES } from '../constants'

export default function SLATimer({ severity, startTime }) {
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
  const slaLabel = SLA_MINUTES[severity] < 60
    ? `${SLA_MINUTES[severity]}min`
    : `${SLA_MINUTES[severity] / 60}hr`

  return (
    <div style={{ background: '#0a0e1a', border: `1px solid ${color}44`, borderRadius: 8, padding: 14, marginBottom: 16 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
        <span style={{ fontSize: 11, color: '#4b5563', textTransform: 'uppercase', letterSpacing: 1 }}>
          ⏱ SLA Timer — {severity} ({slaLabel} window)
        </span>
        <span style={{ fontSize: 13, fontWeight: 700, color: breached ? '#ef4444' : color, fontFamily: 'monospace' }}>
          {breached
            ? '⚠️ SLA BREACHED'
            : `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')} remaining`}
        </span>
      </div>
      <div style={{ background: '#1f2937', borderRadius: 999, height: 6 }}>
        <div style={{ height: 6, borderRadius: 999, background: color, width: `${pct}%`, transition: 'width 1s linear' }} />
      </div>
    </div>
  )
}
