import { useState, useRef, useEffect } from 'react'
import { Link } from 'react-router-dom'

const API_URL = import.meta.env.VITE_API_URL || '/api'

let msgId = 0
const nextId = () => ++msgId

// ── Markdown-like renderer ────────────────────────────────────────────────────
function renderLine(line, key) {
  // Image: ![alt](url)
  const imgMatch = line.match(/^!\[([^\]]*)\]\(([^)]+)\)$/)
  if (imgMatch) {
    return (
      <img
        key={key}
        src={imgMatch[2]}
        alt={imgMatch[1]}
        className="max-w-full rounded-xl my-1 shadow-sm"
        onError={e => { e.currentTarget.style.display = 'none' }}
      />
    )
  }

  // Parse inline: **bold**, ~~strike~~, [text](url)
  const parts = []
  let remaining = line
  let i = 0

  const patterns = [
    { re: /\*\*([^*]+)\*\*/, render: (m, k) => <strong key={k}>{m[1]}</strong> },
    { re: /~~([^~]+)~~/, render: (m, k) => <s key={k} className="text-gray-400">{m[1]}</s> },
    { re: /\[([^\]]+)\]\(([^)]+)\)/, render: (m, k) => (
      <a key={k} href={m[2]} target="_blank" rel="noopener noreferrer"
        className="text-blue-600 underline font-semibold">{m[1]}</a>
    )},
  ]

  while (remaining.length > 0) {
    let earliest = null
    let earliestIndex = Infinity
    let matchedPattern = null

    for (const p of patterns) {
      const m = remaining.match(p.re)
      if (m && m.index < earliestIndex) {
        earliest = m
        earliestIndex = m.index
        matchedPattern = p
      }
    }

    if (!earliest) {
      parts.push(remaining)
      break
    }

    if (earliestIndex > 0) {
      parts.push(remaining.slice(0, earliestIndex))
    }
    parts.push(matchedPattern.render(earliest, `${key}-${i++}`))
    remaining = remaining.slice(earliestIndex + earliest[0].length)
  }

  return <div key={key}>{parts}</div>
}

function MessageText({ text }) {
  const lines = text.split('\n')
  return (
    <div className="leading-relaxed">
      {lines.map((line, i) => renderLine(line, i))}
    </div>
  )
}

// ── Typing indicator ──────────────────────────────────────────────────────────
function TypingDots() {
  return (
    <div className="typing-dots">
      <div className="typing-dot" />
      <div className="typing-dot" />
      <div className="typing-dot" />
    </div>
  )
}

// ── Main chat ─────────────────────────────────────────────────────────────────
export default function ChatPage() {
  const [messages, setMessages] = useState([
    {
      id: nextId(),
      role: 'bot',
      text: 'أهلاً! أنا فاهم 👋\n\nاسألني عن أي منتج موضة على نون وهرشحلك الأفضل مع كوبون خصم حصري!\n\nHi! I\'m Fahim 👋\n\nAsk me about any fashion product on Noon and I\'ll recommend the best for you!',
    },
  ])
  const [input, setInput] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const bottomRef = useRef(null)
  const inputRef = useRef(null)
  const abortRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const timeStr = new Date().toLocaleTimeString('ar-EG', { hour: '2-digit', minute: '2-digit' })

  const sendMessage = async (text) => {
    if (!text.trim() || isStreaming) return

    const userMsg = { id: nextId(), role: 'user', text: text.trim() }
    const botId = nextId()

    setMessages(prev => [
      ...prev,
      userMsg,
      { id: botId, role: 'bot', text: '', streaming: true },
    ])
    setInput('')
    setIsStreaming(true)

    // Build conversation history for the API (exclude the empty bot placeholder)
    const history = [...messages, userMsg]
      .filter(m => m.role === 'user' || (m.role === 'bot' && m.text && !m.streaming))
      .map(m => ({ role: m.role === 'bot' ? 'assistant' : 'user', content: m.text }))

    const controller = new AbortController()
    abortRef.current = controller

    try {
      const res = await fetch(`${API_URL}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ messages: history }),
        signal: controller.signal,
      })

      if (!res.ok) throw new Error(`Server error: ${res.status}`)

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() ?? ''

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          const raw = line.slice(6).trim()
          if (!raw) continue

          try {
            const event = JSON.parse(raw)
            if (event.type === 'token') {
              setMessages(prev => prev.map(m =>
                m.id === botId ? { ...m, text: m.text + event.content } : m
              ))
            } else if (event.type === 'done') {
              setMessages(prev => prev.map(m =>
                m.id === botId ? { ...m, streaming: false } : m
              ))
            } else if (event.type === 'error') {
              setMessages(prev => prev.map(m =>
                m.id === botId
                  ? { ...m, text: `خطأ: ${event.message}`, streaming: false }
                  : m
              ))
            }
          } catch {
            // ignore malformed SSE line
          }
        }
      }
    } catch (err) {
      if (err.name !== 'AbortError') {
        setMessages(prev => prev.map(m =>
          m.id === botId
            ? { ...m, text: 'عذراً، تعذّر الاتصال بالخادم. حاول مرة أخرى.\nSorry, could not reach the server. Please try again.', streaming: false }
            : m
        ))
      }
    } finally {
      setIsStreaming(false)
      abortRef.current = null
      inputRef.current?.focus()
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage(input)
    }
  }

  return (
    <div className="min-h-screen bg-[#ECE5DD] flex items-center justify-center py-0 sm:py-8 px-0 sm:px-4 font-sans" dir="rtl">
      <div
        className="w-full max-w-[480px] sm:rounded-3xl shadow-none sm:shadow-2xl overflow-hidden flex flex-col relative"
        style={{
          height: '100dvh',
          maxHeight: '100dvh',
          backgroundImage: 'radial-gradient(#162F66 0.5px, transparent 0.5px)',
          backgroundSize: '24px 24px',
          backgroundBlendMode: 'multiply',
          backgroundColor: '#ECE5DD',
        }}
      >
        {/* Header */}
        <div
          className="text-white px-4 py-3 flex items-center gap-3 shadow-md shrink-0 z-10"
          style={{ background: 'linear-gradient(to right, #162F66, #1e3f8a)' }}
        >
          <Link
            to="/"
            className="shrink-0 flex items-center justify-center w-8 h-8 rounded-full hover:opacity-80 transition-opacity"
            style={{ backgroundColor: 'rgba(255,255,255,0.2)' }}
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="rotate-180">
              <path d="m15 18-6-6 6-6" />
            </svg>
          </Link>
          <img src="/logo.png" alt="فاهم" className="w-11 h-11 rounded-full object-cover shadow-lg shrink-0" />
          <div className="flex-1">
            <div className="font-bold text-base tracking-wide">فاهم | Fahim</div>
            <div className="text-[11px] mt-0.5" style={{ color: 'rgba(255,255,255,0.85)' }}>مساعد التسوق الذكي • Noon.com</div>
          </div>
          <div
            className="rounded-xl px-2.5 py-1 text-[11px] font-semibold flex items-center gap-1.5"
            style={{ backgroundColor: 'rgba(255,255,255,0.15)' }}
          >
            <span className={`w-2 h-2 rounded-full ${isStreaming ? 'bg-yellow-400 animate-pulse' : 'bg-green-400'}`} />
            {isStreaming ? 'يفكر...' : 'متصل'}
          </div>
        </div>

        {/* Date chip */}
        <div className="flex justify-center pt-3 pb-1 z-10 relative">
          <div className="rounded-lg px-3 py-1 text-[11px] text-gray-600 font-medium" style={{ backgroundColor: 'rgba(0,0,0,0.05)' }}>
            اليوم
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-3 pb-4 flex flex-col gap-1 z-10 relative min-h-0">
          {messages.map(msg => (
            <div key={msg.id}>
              {msg.role === 'bot' ? (
                <div className="flex justify-end items-end gap-1.5 mb-1 mt-2">
                  <div className="max-w-[82%]">
                    <div className="bg-white rounded-tl-none rounded-tr-2xl rounded-b-2xl px-3.5 py-2.5 text-sm text-gray-900 shadow-sm">
                      {msg.streaming && !msg.text ? (
                        <TypingDots />
                      ) : (
                        <>
                          <MessageText text={msg.text} />
                          {msg.streaming && (
                            <span className="inline-block w-1 h-4 bg-gray-400 animate-pulse ml-0.5 rounded-sm align-middle" />
                          )}
                        </>
                      )}
                      {!msg.streaming && (
                        <div className="text-[10px] text-gray-400 mt-1 text-left">{timeStr}</div>
                      )}
                    </div>
                  </div>
                  <img src="/logo.png" alt="فاهم" className="w-7 h-7 rounded-full object-cover shrink-0 shadow-sm self-start mt-1" />
                </div>
              ) : (
                <div className="flex justify-start mb-1 mt-2">
                  <div className="bg-[#DCF8C6] rounded-tr-none rounded-tl-2xl rounded-b-2xl px-3.5 py-2.5 max-w-[78%] text-sm text-gray-900 leading-relaxed shadow-sm">
                    {msg.text}
                    <div className="text-[10px] text-gray-500 mt-1 text-left flex items-center justify-end gap-1">
                      {timeStr}
                      <svg viewBox="0 0 16 15" width="16" height="15" className="fill-blue-500">
                        <path d="M15.01 3.316l-.478-.372a.365.365 0 0 0-.51.063L8.666 9.879a.32.32 0 0 1-.484.033l-.358-.325a.32.32 0 0 0-.484.032l-.378.483a.418.418 0 0 0 .036.541l1.32 1.266c.143.14.361.125.484-.033l6.272-8.048a.366.366 0 0 0-.064-.512zm-4.1 0l-.478-.372a.365.365 0 0 0-.51.063L4.566 9.879a.32.32 0 0 1-.484.033L1.891 7.769a.366.366 0 0 0-.515.006l-.423.433a.364.364 0 0 0 .006.514l3.258 3.185c.143.14.361.125.484-.033l6.272-8.048a.365.365 0 0 0-.063-.51z" />
                      </svg>
                    </div>
                  </div>
                </div>
              )}
            </div>
          ))}
          <div ref={bottomRef} />
        </div>

        {/* Input area */}
        <div className="bg-[#f0f2f5] px-2 py-2.5 flex items-center gap-2 shrink-0 z-10">
          <button
            onClick={() => sendMessage(input)}
            disabled={!input.trim() || isStreaming}
            className={`w-10 h-10 rounded-full flex items-center justify-center shrink-0 transition-colors border-0 cursor-pointer ${
              input.trim() && !isStreaming
                ? 'bg-[#162F66] text-white hover:bg-[#1e3f8a]'
                : 'bg-gray-300 text-white cursor-not-allowed'
            }`}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" className="rotate-180 -mr-1">
              <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z" />
            </svg>
          </button>
          <input
            ref={inputRef}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="اكتب سؤالك هنا... / Ask me anything..."
            disabled={isStreaming}
            className="flex-1 bg-white border-none rounded-full px-4 py-2.5 text-[15px] outline-none shadow-sm disabled:opacity-60"
            style={{ fontFamily: "'Cairo', sans-serif" }}
          />
        </div>
      </div>
    </div>
  )
}
