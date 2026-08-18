import { useEffect, useMemo, useRef, useState } from 'react'
import { ArrowUp, BarChart3, Download, FileSpreadsheet, LogOut, Menu, MessageSquareText, PanelLeftClose, Plus, Sparkles, Trash2, X } from 'lucide-react'
import { api, ApiError } from './api'
import ChartView from './ChartView'
import LoginScreen from './LoginScreen'
import type { AuthUser, Chat, ExportAttachment, Message } from './types'

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

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function ExportCard({ attachment }: { attachment: ExportAttachment }) {
  return (
    <div className="export-card">
      <div className="export-icon"><FileSpreadsheet size={20} /></div>
      <div className="export-details">
        <strong>{attachment.filename}</strong>
        <span>{attachment.format.toUpperCase()} · {attachment.row_count.toLocaleString()} rows · {formatBytes(attachment.size_bytes)}</span>
      </div>
      <a className="download-export" href={attachment.url} download={attachment.filename}>
        <span>Download</span><Download size={16} />
      </a>
    </div>
  )
}

export default function App() {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [authReady, setAuthReady] = useState(false)
  const [chats, setChats] = useState<Chat[]>([])
  const [activeId, setActiveId] = useState<string | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [records, setRecords] = useState<number | null>(null)
  const [headcountEmployees, setHeadcountEmployees] = useState<number | null>(null)
  const [error, setError] = useState('')
  const endRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  const activeChat = useMemo(() => chats.find((chat) => chat.id === activeId), [chats, activeId])

  const resetWorkspace = () => {
    setChats([])
    setActiveId(null)
    setMessages([])
    setRecords(null)
    setHeadcountEmployees(null)
    setInput('')
  }

  const handleRequestError = (reason: unknown, fallback: string) => {
    if (reason instanceof ApiError && reason.status === 401) {
      resetWorkspace()
      setUser(null)
      return
    }
    setError(reason instanceof Error ? reason.message : fallback)
  }

  const refreshChats = async () => {
    const next = await api.chats()
    setChats(next)
  }

  useEffect(() => {
    api.me()
      .then(setUser)
      .catch((reason) => {
        if (!(reason instanceof ApiError && reason.status === 401)) {
          setError(reason instanceof Error ? reason.message : 'Could not check your session')
        }
      })
      .finally(() => setAuthReady(true))
  }, [])

  useEffect(() => {
    if (!user) return
    Promise.all([api.chats(), api.health()])
      .then(([chatList, health]) => {
        setChats(chatList)
        setRecords(health.records)
        setHeadcountEmployees(health.headcount_employees)
      })
      .catch((reason) => handleRequestError(reason, 'Could not load the workspace'))
  }, [user])

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
      handleRequestError(reason, 'Could not open that chat')
    }
  }

  const removeChat = async (event: React.MouseEvent, id: string) => {
    event.stopPropagation()
    if (!window.confirm('Delete this analysis and its messages?')) return
    try {
      await api.removeChat(id)
      setChats((current) => current.filter((chat) => chat.id !== id))
      if (activeId === id) newChat()
    } catch (reason) {
      handleRequestError(reason, 'Could not delete that chat')
    }
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
      handleRequestError(reason, 'The question could not be answered')
    } finally {
      setLoading(false)
      inputRef.current?.focus()
    }
  }

  const logout = async () => {
    try {
      await api.logout()
    } finally {
      resetWorkspace()
      setUser(null)
      document.body.classList.remove('sidebar-collapsed')
    }
  }

  if (!authReady) {
    return <div className="auth-loading"><div className="brand-mark"><BarChart3 size={19} /></div><span>Loading Synergy…</span></div>
  }

  if (!user) {
    return <LoginScreen onAuthenticated={(authenticatedUser) => { setError(''); setUser(authenticatedUser) }} />
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
          <div className="user-avatar">{user.name.slice(0, 1).toUpperCase()}</div>
          <div className="signed-in-user">
            <strong>{user.name}</strong>
            <small>{user.email}</small>
          </div>
          <button className="logout-button" onClick={logout} aria-label="Sign out"><LogOut size={16} /></button>
        </div>
        <div className="report-status"><span className="status-dot" /><span>{records?.toLocaleString() ?? '—'} learning · {headcountEmployees?.toLocaleString() ?? '—'} employees</span></div>
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
                    {message.attachment && <ExportCard attachment={message.attachment} />}
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
