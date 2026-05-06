export const API = 'http://localhost:8001'

export const SLA_MINUTES = { Critical: 15, High: 60, Medium: 240, Low: 1440 }

export const SEV_COLORS = {
  Critical: { bg: '#7f1d1d', text: '#fca5a5', dot: '#ef4444' },
  High:     { bg: '#78350f', text: '#fcd34d', dot: '#f59e0b' },
  Medium:   { bg: '#1e3a5f', text: '#93c5fd', dot: '#3b82f6' },
  Low:      { bg: '#14532d', text: '#86efac', dot: '#22c55e' },
}

export const CAT_ICONS = {
  Network: '🌐', Security: '🔒', Hardware: '💾', Cloud: '☁️', Application: '📱',
}

export const TEAM_NAMES = {
  Network: 'NOC Network Team',
  Security: 'NOC Security Team',
  Hardware: 'NOC Hardware Team',
  Cloud: 'NOC Cloud Team',
  Application: 'NOC Application Team',
}

export const TEAM_EMAILS = {
  Network: 'noc-network@emircom.com',
  Security: 'noc-security@emircom.com',
  Hardware: 'noc-hardware@emircom.com',
  Cloud: 'noc-cloud@emircom.com',
  Application: 'noc-application@emircom.com',
}
