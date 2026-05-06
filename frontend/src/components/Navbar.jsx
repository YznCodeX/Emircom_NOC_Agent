import { NavLink } from 'react-router-dom'
import { useState, useEffect } from 'react'

const NAV_ITEMS = [
  { to: '/', icon: '🏠', label: 'Dashboard' },
  { to: '/operations', icon: '⚡', label: 'Operations' },
  { to: '/analytics', icon: '📊', label: 'Analytics' },
  { to: '/chatbot', icon: '🤖', label: 'AI Chat' },
  { to: '/reports', icon: '📋', label: 'Reports' },
]

export default function Navbar() {
  const [clock, setClock] = useState(new Date())

  useEffect(() => {
    const iv = setInterval(() => setClock(new Date()), 1000)
    return () => clearInterval(iv)
  }, [])

  return (
    <div style={{
      width: 220, background: '#060910', borderRight: '1px solid #1f2937',
      display: 'flex', flexDirection: 'column', height: '100vh',
      position: 'sticky', top: 0, flexShrink: 0,
    }}>
      {/* Logo */}
      <div style={{ padding: '20px 20px 16px', borderBottom: '1px solid #1f2937' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ fontSize: 22 }}>🛡️</span>
          <div>
            <div style={{ fontWeight: 700, fontSize: 13, color: '#f9fafb', lineHeight: 1.2 }}>Emircom NOC</div>
            <div style={{ fontSize: 11, color: '#4b5563' }}>Command Center</div>
          </div>
        </div>
      </div>

      {/* Nav Links */}
      <nav style={{ padding: '12px 8px', flex: 1 }}>
        {NAV_ITEMS.map(({ to, icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            style={({ isActive }) => ({
              display: 'flex', alignItems: 'center', gap: 10,
              padding: '10px 12px', borderRadius: 8, marginBottom: 4,
              textDecoration: 'none', fontSize: 13,
              fontWeight: isActive ? 600 : 400,
              color: isActive ? '#60a5fa' : '#6b7280',
              background: isActive ? 'rgba(30,58,95,0.4)' : 'transparent',
              border: isActive ? '1px solid rgba(29,78,216,0.2)' : '1px solid transparent',
              transition: 'all 0.15s',
            })}
          >
            <span style={{ fontSize: 16 }}>{icon}</span>
            {label}
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      <div style={{ padding: '16px 20px', borderTop: '1px solid #1f2937' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
          <span style={{ width: 7, height: 7, borderRadius: '50%', background: '#22c55e', display: 'inline-block' }} />
          <span style={{ fontSize: 11, color: '#6b7280' }}>Live</span>
        </div>
        <div style={{ fontSize: 12, color: '#374151', fontFamily: 'monospace' }}>
          {clock.toLocaleTimeString()}
        </div>
      </div>
    </div>
  )
}
