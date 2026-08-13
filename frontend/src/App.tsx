import { useEffect, useMemo, useRef, useState } from 'react'
import { ArrowUp, BarChart3, Menu, MessageSquareText, MoreHorizontal, PanelLeftClose, Plus, Sparkles, Trash2, X } from 'lucide-react'
import { api } from './api'
import ChartView from './ChartView'
import type { Chat, Message } from './types'

const prompts = [
  'Show completion status as a donut chart',
  'How many unique employees are in the report?',
  'Show the top 10 courses as a bar chart',
]

function formatRelative(value: string) {
  const date = new Date(value)
  const now = new Date()
  if (date.toDateString() === now.toDateString()) return 'Today'
  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

export default function App() {
  const [chats, setChats] = useState<Chat[]>([])
  const [activeId, setActiveId] = useState<string | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [records, setRecords] = useState<number | null>(null)
  const [error, setError] = useState('')
  const endRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  const activeChat = useMemo(() => chats.find((chat) => chat.id === activeId), [chats, activeId])

  const refreshChats = async () => {
    const next = await api.chats()
    setChats(next)
  }

  useEffect(() => {
    Promise.all([api.chats(), api.health()])
      .then(([chatList, health]) => {
        setChats(chatList)
        setRecords(health.records)
      })
      .catch((reason) => setError(reason.message))
  }, [])

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  const newChat = () => {
    setActiveId(null)
    setMessages([])
    setInput('')
    setSidebarOpen(false)
    setTimeout(() => inputRef.current?.focus(), 0)
  }

  const openChat = async (id: string) => {
    setError('')
    try {
      const chat = await api.chat(id)
      setActiveId(id)
      setMessages(chat.messages || [])
      setSidebarOpen(false)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Could not open that chat')
    }
  }

  const removeChat = async (event: React.MouseEvent, id: string) => {
    event.stopPropagation()
    if (!window.confirm('Delete this analysis and its messages?')) return
    await api.removeChat(id)
    setChats((current) => current.filter((chat) => chat.id !== id))
    if (activeId === id) newChat()
  }

  const submit = async (value = input) => {
    const question = value.trim()
    if (!question || loading) return
    setError('')
    setInput('')
    const optimistic: Message = {
      id: `pending-${Date.now()}`,
      role: 'user',
      content: question,
      created_at: new Date().toISOString(),
    }
    setMessages((current) => [...current, optimistic])
    setLoading(true)
    try {
      const result = await api.ask(activeId, question)
      setActiveId(result.chat_id)
      setMessages((current) => [...current, result.message])
      await refreshChats()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'The question could not be answered')
    } finally {
      setLoading(false)
      inputRef.current?.focus()
    }
  }

  return (
    <div className="app-shell">
      {sidebarOpen && <button className="sidebar-scrim" onClick={() => setSidebarOpen(false)} aria-label="Close sidebar" />}
      <aside className={`sidebar ${sidebarOpen ? 'open' : ''}`}>
        <div className="brand-row">
          <div className="brand-mark"><BarChart3 size={19} /></div>
          <div><strong>Synergy</strong><span>Learning intelligence</span></div>
          <button className="mobile-close" onClick={() => setSidebarOpen(false)} aria-label="Close sidebar"><X size={19} /></button>
        </div>
        <button className="new-chat" onClick={newChat}><Plus size={17} /> New analysis</button>
        <div className="history-label"><span>Recent</span><span>{chats.length}</span></div>
        <nav className="chat-list" aria-label="Previous chats">
          {chats.map((chat) => (
            <button key={chat.id} className={`chat-item ${activeId === chat.id ? 'active' : ''}`} onClick={() => openChat(chat.id)}>
              <MessageSquareText size={15} />
              <span className="chat-title"><strong>{chat.title}</strong><small>{formatRelative(chat.updated_at)}</small></span>
              <span className="delete-chat" role="button" aria-label={`Delete ${chat.title}`} onClick={(event) => removeChat(event, chat.id)}><Trash2 size={14} /></span>
            </button>
          ))}
          {!chats.length && <p className="empty-history">Your analyses will appear here.</p>}
        </nav>
        <div className="data-status">
          <span className="status-dot" />
          <div><strong>Report connected</strong><small>{records?.toLocaleString() ?? '—'} course records</small></div>
          <MoreHorizontal size={17} />
        </div>
      </aside>

      <main className="main-panel">
        <header className="topbar">
          <button className="menu-button" onClick={() => setSidebarOpen(true)} aria-label="Open sidebar"><Menu size={20} /></button>
          <div className="active-title"><span>{activeChat?.title || 'New analysis'}</span><small>Learning Overall Report</small></div>
          <button className="collapse-button" onClick={() => document.body.classList.toggle('sidebar-collapsed')} aria-label="Toggle sidebar"><PanelLeftClose size={19} /></button>
        </header>

        <section className={`conversation ${messages.length ? 'has-messages' : ''}`} aria-live="polite">
          {!messages.length ? (
            <div className="welcome">
              <div className="spark-icon"><Sparkles size={24} /></div>
              <p className="eyebrow">Your report, ready to explore</p>
              <h1>What would you like to know?</h1>
              <p className="welcome-copy">Ask in plain English. I can calculate an answer, compare groups, or turn the result into the chart you need.</p>
              <div className="prompt-grid">
                {prompts.map((prompt) => <button key={prompt} onClick={() => submit(prompt)}>{prompt}<ArrowUp size={15} /></button>)}
              </div>
            </div>
          ) : (
            <div className="message-list">
              {messages.map((message) => (
                <article key={message.id} className={`message ${message.role}`}>
                  {message.role === 'assistant' && <div className="assistant-avatar"><Sparkles size={15} /></div>}
                  <div className="message-body">
                    <p>{message.content}</p>
                    {message.visualization && <ChartView visualization={message.visualization} />}
                  </div>
                </article>
              ))}
              {loading && <div className="message assistant"><div className="assistant-avatar"><Sparkles size={15} /></div><div className="thinking"><i/><i/><i/></div></div>}
              <div ref={endRef} />
            </div>
          )}
        </section>

        <div className="composer-region">
          {error && <div className="error-toast">{error}<button onClick={() => setError('')} aria-label="Dismiss"><X size={14}/></button></div>}
          <div className="composer">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(event) => setInput(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' && !event.shiftKey) {
                  event.preventDefault()
                  submit()
                }
              }}
              rows={1}
              placeholder="Ask anything about the learning report…"
              aria-label="Ask a question about the report"
            />
            <button className="send-button" disabled={!input.trim() || loading} onClick={() => submit()} aria-label="Send message"><ArrowUp size={19} /></button>
          </div>
          <p className="composer-note">Answers are calculated from the connected Excel report. Verify critical decisions.</p>
        </div>
      </main>
    </div>
  )
}
