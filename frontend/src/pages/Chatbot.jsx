import { useState, useRef, useEffect } from 'react'

const API = 'http://localhost:8001'

const SUGGESTIONS = [
  "What's still pending?",
  "Any Critical tickets?",
  "Summarize the shift",
  "Which team got the most tickets?",
  "Any SLA breaches?",
  "List hardware failures",
]

const MAX_TURNS = 10  // 20 messages

export default function Chatbot() {
  const [messages, setMessages] = useState([
    { role: 'assistant', content: 'Hello! I am the Emircom NOC AI Assistant. Ask me about tickets, alerts, SLA status, or shift handoff.' }
  ])
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [showLogs, setShowLogs] = useState(false)
  const [logs, setLogs] = useState('')
  const bottomRef = useRef(null)
  const esRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  function trimHistory(msgs) {
    // Keep first (greeting) + last MAX_TURNS*2 messages
    if (msgs.length <= MAX_TURNS * 2 + 1) return msgs
    return [msgs[0], ...msgs.slice(-(MAX_TURNS * 2))]
  }

  function sendMessage(text) {
    if (!text.trim() || streaming) return

    let finalText = text.trim()
    if (showLogs && logs.trim()) {
      finalText = `[LOGS]\n${logs.trim()}\n[/LOGS]\n\n${finalText}`
      setShowLogs(false)
      setLogs('')
    }

    const userMsg = { role: 'user', content: text.trim() }
    const assistantMsg = { role: 'assistant', content: '' }

    setMessages(prev => trimHistory([...prev, userMsg, assistantMsg]))
    setInput('')
    setStreaming(true)

    const encoded = encodeURIComponent(finalText)
    const es = new EventSource(`${API}/chatbot/stream?message=${encoded}`)
    esRef.current = es

    es.onmessage = (e) => {
      if (e.data === '[DONE]') {
        es.close()
        setStreaming(false)
        return
      }
      setMessages(prev => {
        const next = [...prev]
        next[next.length - 1] = {
          ...next[next.length - 1],
          content: next[next.length - 1].content + e.data,
        }
        return next
      })
    }

    es.onerror = () => {
      es.close()
      setStreaming(false)
      setMessages(prev => {
        const next = [...prev]
        if (next[next.length - 1].content === '') {
          next[next.length - 1] = { role: 'assistant', content: 'Connection error. Please try again.' }
        }
        return next
      })
    }
  }

  function handleKey(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage(input)
    }
  }

  function clearChat() {
    if (esRef.current) { esRef.current.close(); setStreaming(false) }
    setMessages([{ role: 'assistant', content: 'Hello! I am the Emircom NOC AI Assistant. Ask me about tickets, alerts, SLA status, or shift handoff.' }])
    setInput('')
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 80px)', background: '#111827', borderRadius: 12, overflow: 'hidden', border: '1px solid #1f2937' }}>

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '14px 20px', background: '#1f2937', borderBottom: '1px solid #374151' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ fontSize: 22 }}>🤖</span>
          <div>
            <div style={{ color: '#f9fafb', fontWeight: 700, fontSize: 15 }}>NOC AI Assistant</div>
            <div style={{ color: '#6b7280', fontSize: 12 }}>Emircom Network Operations Center</div>
          </div>
        </div>
        <button onClick={clearChat} style={{ background: '#374151', color: '#9ca3af', border: 'none', borderRadius: 8, padding: '6px 14px', cursor: 'pointer', fontSize: 13 }}>
          Clear Chat
        </button>
      </div>

      {/* Messages */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '20px 16px', display: 'flex', flexDirection: 'column', gap: 12 }}>
        {messages.map((msg, i) => (
          <div key={i} style={{ display: 'flex', flexDirection: msg.role === 'user' ? 'row-reverse' : 'row', alignItems: 'flex-end', gap: 8 }}>
            <div style={{ fontSize: 20, flexShrink: 0 }}>{msg.role === 'user' ? '👷' : '🤖'}</div>
            <div style={{
              maxWidth: '72%',
              padding: '10px 14px',
              borderRadius: msg.role === 'user' ? '18px 18px 4px 18px' : '18px 18px 18px 4px',
              background: msg.role === 'user' ? '#1d4ed8' : '#1f2937',
              color: '#f3f4f6',
              fontSize: 14,
              lineHeight: 1.6,
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
              border: msg.role === 'user' ? 'none' : '1px solid #374151',
            }}>
              {msg.content}
              {streaming && i === messages.length - 1 && msg.role === 'assistant' && (
                <span style={{ display: 'inline-block', width: 8, height: 14, background: '#60a5fa', marginLeft: 4, borderRadius: 2, animation: 'blink 0.8s step-end infinite', verticalAlign: 'middle' }} />
              )}
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Suggested questions */}
      <div style={{ padding: '8px 16px', display: 'flex', flexWrap: 'wrap', gap: 6, borderTop: '1px solid #1f2937' }}>
        {SUGGESTIONS.map(s => (
          <button key={s} onClick={() => sendMessage(s)} disabled={streaming} style={{
            background: '#1f2937', color: '#93c5fd', border: '1px solid #374151',
            borderRadius: 20, padding: '4px 12px', fontSize: 12, cursor: streaming ? 'not-allowed' : 'pointer',
            opacity: streaming ? 0.5 : 1, whiteSpace: 'nowrap',
          }}>{s}</button>
        ))}
      </div>

      {/* Paste Logs panel */}
      {showLogs && (
        <div style={{ padding: '0 16px 8px' }}>
          <textarea
            value={logs}
            onChange={e => setLogs(e.target.value)}
            placeholder="Paste raw syslog or device output here — it will be prepended to your next message..."
            style={{
              width: '100%', height: 100, background: '#0d1117', color: '#86efac',
              border: '1px solid #374151', borderRadius: 8, padding: 10,
              fontSize: 12, fontFamily: 'monospace', resize: 'vertical', boxSizing: 'border-box',
            }}
          />
        </div>
      )}

      {/* Input bar */}
      <div style={{ padding: '12px 16px', background: '#1f2937', borderTop: '1px solid #374151', display: 'flex', gap: 8, alignItems: 'flex-end' }}>
        <button
          onClick={() => setShowLogs(v => !v)}
          title="Paste Logs"
          style={{
            background: showLogs ? '#065f46' : '#374151', color: showLogs ? '#6ee7b7' : '#9ca3af',
            border: 'none', borderRadius: 8, padding: '9px 12px', cursor: 'pointer', fontSize: 13, flexShrink: 0,
          }}
        >
          📋
        </button>
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKey}
          placeholder="Ask about tickets, alerts, SLA, shifts…"
          disabled={streaming}
          style={{
            flex: 1, background: '#111827', color: '#f3f4f6', border: '1px solid #374151',
            borderRadius: 8, padding: '9px 14px', fontSize: 14, outline: 'none',
          }}
        />
        <button
          onClick={() => sendMessage(input)}
          disabled={streaming || !input.trim()}
          style={{
            background: streaming || !input.trim() ? '#374151' : '#2563eb',
            color: streaming || !input.trim() ? '#6b7280' : '#fff',
            border: 'none', borderRadius: 8, padding: '9px 18px',
            cursor: streaming || !input.trim() ? 'not-allowed' : 'pointer',
            fontWeight: 700, fontSize: 14, flexShrink: 0,
          }}
        >
          Send
        </button>
      </div>

      <style>{`@keyframes blink { 0%,100%{opacity:1} 50%{opacity:0} }`}</style>
    </div>
  )
}
