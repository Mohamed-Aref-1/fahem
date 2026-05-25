import { useState, useRef, useEffect } from 'react'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:3000'

let msgId = 0
const nextId = () => ++msgId

// ── Markdown-like renderer ────────────────────────────────────────────────────
function renderLine(line, key) {
  // Match image anywhere in the line (model may add bullets or trailing text)
  const imgMatch = line.match(/!\[([^\]]*)\]\(([^)\s]+)\)/)
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

  const patterns = [
    { re: /\*\*([^*]+)\*\*/, render: (m, k) => <strong key={k}>{m[1]}</strong> },
    { re: /~~([^~]+)~~/, render: (m, k) => <s key={k} className="text-gray-400">{m[1]}</s> },
    { re: /\[([^\]]+)\]\(([^)]+)\)/, render: (m, k) => (
      <a key={k} href={m[2]} target="_blank" rel="noopener noreferrer"
        className="text-blue-600 underline font-semibold">{m[1]}</a>
    )},
  ]

  const parts = []
  let remaining = line
  let i = 0
  while (remaining.length > 0) {
    let earliest = null, earliestIdx = Infinity, matchedP = null
    for (const p of patterns) {
      const m = remaining.match(p.re)
      if (m && m.index < earliestIdx) { earliest = m; earliestIdx = m.index; matchedP = p }
    }
    if (!earliest) { parts.push(remaining); break }
    if (earliestIdx > 0) parts.push(remaining.slice(0, earliestIdx))
    parts.push(matchedP.render(earliest, `${key}-${i++}`))
    remaining = remaining.slice(earliestIdx + earliest[0].length)
  }
  return <div key={key}>{parts}</div>
}

function MessageText({ text }) {
  return (
    <div className="leading-relaxed">
      {text.split('\n').map((line, i) => renderLine(line, i))}
    </div>
  )
}

function TypingDots() {
  return (
    <div className="typing-dots">
      <div className="typing-dot" /><div className="typing-dot" /><div className="typing-dot" />
    </div>
  )
}

function ToolCallChips({ toolCalls }) {
  if (!toolCalls?.length) return null
  return (
    <div className="flex flex-col gap-1 mb-2">
      {toolCalls.map((tc, i) => (
        <div key={i} className="flex items-center gap-1.5 text-xs text-gray-500 bg-gray-50 rounded-lg px-2.5 py-1.5 border border-gray-100">
          {tc.status === 'running' ? (
            <span className="w-3 h-3 border-2 border-gray-200 border-t-blue-500 rounded-full animate-spin shrink-0" />
          ) : (
            <span className="text-green-500 shrink-0">✓</span>
          )}
          <span className="font-medium">{tc.label}</span>
          {tc.status === 'done' && tc.count !== '' && tc.count != null && (
            <span className="text-gray-400 mr-auto">({tc.count})</span>
          )}
        </div>
      ))}
    </div>
  )
}

// ── Main floating widget ──────────────────────────────────────────────────────
export default function FloatingChat() {
  const [isOpen, setIsOpen]         = useState(false)
  const [showBubble, setShowBubble] = useState(false)
  const [messages, setMessages]     = useState([
    { id: nextId(), role: 'bot', text: 'أهلاً! أنا فاهم 👋\nاسألني عن أي منتج موضة على نون وهرشحلك الأفضل مع كوبون خصم حصري!' },
  ])
  const [input, setInput]           = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const bottomRef    = useRef(null)
  const inputRef     = useRef(null)
  const abortRef     = useRef(null)
  const pendingRef   = useRef('')   // chars received but not yet displayed
  const typeTimerRef = useRef(null) // interval handle for typewriter
  const activeBotId  = useRef(null) // which message is being typed

  const TICK_MS            = 30  // ms between ticks
  const hasTokenRef        = useRef(false) // did any text token arrive for current message?

  const TOOL_GREETINGS = {
    search_products:         'لحظة، خلّيني أدور لك على أفضل الخيارات ✨',
    get_products_by_filters: 'حاضر! بشوف لك أحسن المنتجات المتاحة 🛍️',
    get_best_deals:          'يلا نشوف أحسن العروض والخصومات! 💰',
    get_top_rated_products:  'هجيبلك الأعلى تقييماً من العملاء ⭐',
    get_catalog_summary:     'هشوف إيه اللي عندنا في قاعدة البيانات 📊',
    get_product_by_sku:      'خلّيني أجيب لك تفاصيل المنتج 📦',
    get_filter_values:       'هشوف الخيارات المتاحة عندنا في قاعدة البيانات 📋',
  }

  // Show tooltip bubble after 1.8s
  useEffect(() => {
    const t = setTimeout(() => setShowBubble(true), 1800)
    return () => clearTimeout(t)
  }, [])

  // Scroll to bottom on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // Focus input when chat opens
  useEffect(() => {
    if (isOpen) setTimeout(() => inputRef.current?.focus(), 80)
  }, [isOpen])

  const timeStr = new Date().toLocaleTimeString('ar-EG', { hour: '2-digit', minute: '2-digit' })

  const openChat = () => {
    setIsOpen(true)
    setShowBubble(false)
  }

  const stopTypewriter = () => {
    if (typeTimerRef.current) {
      clearInterval(typeTimerRef.current)
      typeTimerRef.current = null
    }
  }

  const startTypewriter = (botId) => {
    if (typeTimerRef.current) return
    typeTimerRef.current = setInterval(() => {
      if (pendingRef.current.length === 0) return
      // Reveal one full line at a time so markdown (links, bold) always renders completely
      const newlineIdx = pendingRef.current.indexOf('\n')
      const chunk = newlineIdx === -1
        ? pendingRef.current
        : pendingRef.current.slice(0, newlineIdx + 1)
      pendingRef.current = pendingRef.current.slice(chunk.length)
      setMessages(prev => prev.map(m =>
        m.id === botId ? { ...m, text: m.text + chunk } : m
      ))
    }, TICK_MS)
  }

  const sendMessage = async (text) => {
    if (!text.trim() || isStreaming) return

    stopTypewriter()
    pendingRef.current = ''
    hasTokenRef.current = false

    const userMsg = { id: nextId(), role: 'user', text: text.trim() }
    const botId   = nextId()
    activeBotId.current = botId

    setMessages(prev => [
      ...prev,
      userMsg,
      { id: botId, role: 'bot', text: '', modelText: '', streaming: true, toolCalls: [] },
    ])
    setInput('')
    setIsStreaming(true)

    const history = [...messages, userMsg]
      .filter(m => m.role === 'user' || (m.role === 'bot' && m.text && !m.streaming))
      .map(m => ({ role: m.role === 'bot' ? 'assistant' : 'user', content: m.modelText || m.text }))

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

      const reader  = res.body.getReader()
      const decoder = new TextDecoder()
      let sseBuffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        sseBuffer += decoder.decode(value, { stream: true })
        const lines = sseBuffer.split('\n')
        sseBuffer = lines.pop() ?? ''
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          const raw = line.slice(6).trim()
          if (!raw) continue
          try {
            const event = JSON.parse(raw)
            if (event.type === 'token') {
              hasTokenRef.current = true
              pendingRef.current += event.content
              // Track clean model response separately for history (no injected greetings)
              setMessages(prev => prev.map(m =>
                m.id === botId ? { ...m, modelText: (m.modelText || '') + event.content } : m
              ))
              startTypewriter(botId)
            } else if (event.type === 'tool_start') {
              // If model skipped text and jumped straight to tool, inject a friendly greeting
              if (!hasTokenRef.current) {
                const greeting = TOOL_GREETINGS[event.name] || 'لحظة، جاري البحث... 🔍'
                pendingRef.current = greeting + '\n'
                hasTokenRef.current = true
                startTypewriter(botId)
              }
              setMessages(prev => prev.map(m =>
                m.id === botId ? {
                  ...m,
                  toolCalls: [...(m.toolCalls || []), { name: event.name, label: event.label, index: event.index, status: 'running' }],
                } : m
              ))
            } else if (event.type === 'tool_done') {
              setMessages(prev => prev.map(m =>
                m.id === botId ? {
                  ...m,
                  toolCalls: (m.toolCalls || []).map(tc =>
                    tc.index === event.index ? { ...tc, status: 'done', count: event.count } : tc
                  ),
                } : m
              ))
            } else if (event.type === 'done') {
              // Wait until typewriter drains all pending chars before marking done
              const drain = () => {
                if (pendingRef.current.length === 0) {
                  stopTypewriter()
                  setMessages(prev => prev.map(m =>
                    m.id === botId ? { ...m, streaming: false } : m
                  ))
                  setIsStreaming(false)
                  abortRef.current = null
                } else {
                  setTimeout(drain, TICK_MS * 2)
                }
              }
              drain()
              return // skip the finally block — drain() handles cleanup
            } else if (event.type === 'error') {
              stopTypewriter()
              setMessages(prev => prev.map(m =>
                m.id === botId ? { ...m, text: `خطأ: ${event.message}`, streaming: false } : m
              ))
            }
          } catch { /* ignore malformed SSE */ }
        }
      }
    } catch (err) {
      stopTypewriter()
      if (err.name !== 'AbortError') {
        setMessages(prev => prev.map(m =>
          m.id === botId
            ? { ...m, text: 'عذراً، تعذّر الاتصال. حاول مرة أخرى.', streaming: false }
            : m
        ))
      }
    } finally {
      setIsStreaming(false)
      abortRef.current = null
    }
  }

  return (
    <div className="fixed bottom-6 right-6 z-50 flex flex-col items-end gap-3" dir="rtl">

      {/* ── Chat panel ── */}
      {isOpen && (
        <div
          className="chat-slide-up flex flex-col overflow-hidden rounded-3xl shadow-2xl border border-white/20"
          style={{
            width: '480px',
            height: 'calc(100vh - 150px)',
            backgroundImage: 'url(/whatsapp_bg.jpeg)',
            backgroundSize: 'cover',
            backgroundPosition: 'center',
          }}
        >
          {/* Header */}
          <div
            className="text-white px-5 py-3.5 flex items-center gap-3 shrink-0 shadow-md"
            style={{ background: 'linear-gradient(to right, #162F66, #1e3f8a)' }}
          >
            <img src="/logo.png" alt="فاهم" className="w-11 h-11 rounded-full object-cover shadow-lg shrink-0" />
            <div className="flex-1">
              <div className="font-bold text-base tracking-wide">فاهم | Fahim</div>
              <div className="text-xs" style={{ color: 'rgba(255,255,255,0.8)' }}>
                مساعد التسوق الذكي • Noon.com
              </div>
            </div>
            <div className="flex items-center gap-2">
              <div className="flex items-center gap-1.5 text-xs font-semibold px-2.5 py-1 rounded-lg"
                style={{ backgroundColor: 'rgba(255,255,255,0.15)' }}>
                <span className={`w-2 h-2 rounded-full ${isStreaming ? 'bg-yellow-400 animate-pulse' : 'bg-green-400'}`} />
                {isStreaming ? 'يفكر...' : 'متصل'}
              </div>
              <button
                onClick={() => setIsOpen(false)}
                className="w-8 h-8 rounded-full flex items-center justify-center hover:opacity-80 transition-opacity cursor-pointer border-0"
                style={{ backgroundColor: 'rgba(255,255,255,0.15)' }}
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <path d="M18 6 6 18M6 6l12 12" />
                </svg>
              </button>
            </div>
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto px-4 py-3 flex flex-col gap-1">
            {messages.map(msg => (
              <div key={msg.id}>
                {msg.role === 'bot' ? (
                  <div className="flex items-end gap-2 mb-1 mt-2">
                    <img src="/logo.png" alt="فاهم" className="w-8 h-8 rounded-full object-cover shrink-0 shadow-sm self-start mt-1" />
                    <div className="max-w-[84%]">
                      <div className="bg-white rounded-tl-none rounded-tr-2xl rounded-b-2xl px-3.5 py-2.5 text-base text-gray-900 shadow-sm">
                        {msg.streaming && !msg.text && !msg.toolCalls?.length ? (
                          <TypingDots />
                        ) : (
                          <>
                            {msg.text ? <MessageText text={msg.text} /> : null}
                            {msg.streaming && msg.text && (
                              <span className="inline-block w-0.5 h-3.5 bg-gray-400 animate-pulse ml-0.5 rounded-sm align-middle" />
                            )}
                          </>
                        )}
                        <ToolCallChips toolCalls={msg.toolCalls} />
                        {!msg.streaming && (
                          <div className="text-[10px] text-gray-400 mt-1 text-left">{timeStr}</div>
                        )}
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="flex justify-start mb-1 mt-2">
                    <div className="bg-[#DCF8C6] rounded-tr-none rounded-tl-2xl rounded-b-2xl px-3.5 py-2.5 max-w-[78%] text-base text-gray-900 shadow-sm">
                      {msg.text}
                      <div className="text-[10px] text-gray-500 mt-1 text-left flex items-center justify-end gap-1">
                        {timeStr}
                        <svg viewBox="0 0 16 15" width="14" height="14" className="fill-blue-500">
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

          {/* Input */}
          <div className="bg-[#f0f2f5] px-3 py-2.5 flex items-center gap-2 shrink-0">
            <button
              onClick={() => sendMessage(input)}
              disabled={!input.trim() || isStreaming}
              className={`w-10 h-10 rounded-full flex items-center justify-center shrink-0 border-0 cursor-pointer transition-colors ${
                input.trim() && !isStreaming
                  ? 'bg-[#162F66] text-white hover:bg-[#1e3f8a]'
                  : 'bg-gray-300 text-white cursor-not-allowed'
              }`}
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" className="rotate-180 -mr-0.5">
                <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z" />
              </svg>
            </button>
            <input
              ref={inputRef}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && !e.shiftKey && sendMessage(input)}
              placeholder="اكتب سؤالك..."
              disabled={isStreaming}
              className="flex-1 bg-white border-none rounded-full px-4 py-2.5 text-base outline-none shadow-sm disabled:opacity-60"
              style={{ fontFamily: "'Cairo', sans-serif" }}
            />
          </div>
        </div>
      )}

      {/* ── Tooltip bubble "اسأل فاهم" ── */}
      {!isOpen && showBubble && (
        <div className="bubble-pop flex items-center gap-2 cursor-pointer" onClick={openChat}>
          <div
            className="text-white text-base font-bold px-5 py-3 rounded-2xl rounded-br-none shadow-xl relative"
            style={{ background: 'linear-gradient(to right, #162F66, #1e3f8a)' }}
          >
            اسأل فاهم ✨
            {/* tail */}
            <div className="absolute -bottom-2 right-3 w-0 h-0"
              style={{ borderLeft: '8px solid transparent', borderRight: '8px solid transparent', borderTop: '8px solid #1e3f8a' }} />
          </div>
          <button
            onClick={e => { e.stopPropagation(); setShowBubble(false) }}
            className="w-5 h-5 rounded-full bg-gray-200 hover:bg-gray-300 flex items-center justify-center text-gray-500 border-0 cursor-pointer text-xs font-bold shrink-0"
          >×</button>
        </div>
      )}

      {/* ── Floating Fahim button — hidden while chat is open ── */}
      {!isOpen && (
        <button
          onClick={openChat}
          className="logo-bob fahim-pulse relative w-20 h-20 rounded-full border-0 cursor-pointer p-0 overflow-visible"
          style={{ background: 'none' }}
          aria-label="اسأل فاهم"
        >
          <img
            src="/logo.png"
            alt="فاهم"
            className="w-20 h-20 rounded-full object-cover shadow-xl border-4 border-white"
          />
          <span className="absolute top-0.5 right-0.5 w-5 h-5 bg-green-500 rounded-full border-2 border-white" />
        </button>
      )}

    </div>
  )
}
