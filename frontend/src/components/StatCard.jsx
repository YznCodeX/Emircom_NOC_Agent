export default function StatCard({ label, value, color }) {
  return (
    <div style={{
      background: '#111827', border: '1px solid #1f2937', borderRadius: 12,
      padding: '20px 24px', flex: 1,
    }}>
      <div style={{ fontSize: 28, fontWeight: 700, color: color || '#fff' }}>{value}</div>
      <div style={{ fontSize: 13, color: '#6b7280', marginTop: 4 }}>{label}</div>
    </div>
  )
}
