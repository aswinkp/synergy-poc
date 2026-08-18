import type { AgentStreamEvent, AuthUser, Chat, ChatResponse } from './types'

export class ApiError extends Error {
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    ...options,
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...options?.headers },
  })
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new ApiError(body.detail || 'Something went wrong', response.status)
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

async function agentReview(
  chatId: string | null,
  message: string,
  onEvent: (event: AgentStreamEvent) => void,
): Promise<ChatResponse> {
  const response = await fetch('/api/agent-review', {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ chat_id: chatId, message }),
  })
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new ApiError(body.detail || 'The analysis could not start', response.status)
  }
  if (!response.body) throw new Error('The analysis returned no event stream')

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let result: ChatResponse | null = null

  const handleLine = (line: string) => {
    if (!line.trim()) return
    const event = JSON.parse(line) as AgentStreamEvent
    onEvent(event)
    if (event.event === 'error') throw new Error(event.message)
    if (event.event === 'result') result = event.result
  }

  while (true) {
    const { done, value } = await reader.read()
    buffer += decoder.decode(value, { stream: !done })
    const lines = buffer.split('\n')
    buffer = lines.pop() || ''
    for (const line of lines) handleLine(line)
    if (done) break
  }
  handleLine(buffer)
  if (!result) throw new Error('The analysis ended without a result')
  return result
}

export const api = {
  me: () => request<AuthUser>('/api/auth/me'),
  login: (email: string, password: string) =>
    request<AuthUser>('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }),
  logout: () => request<void>('/api/auth/logout', { method: 'POST' }),
  health: () => request<{
    status: string
    records: number
    headcount_employees: number
    workbook: string
    headcount_workbook: string | null
  }>('/api/health'),
  chats: () => request<Chat[]>('/api/chats'),
  chat: (id: string) => request<Chat>(`/api/chats/${id}`),
  removeChat: (id: string) => request<void>(`/api/chats/${id}`, { method: 'DELETE' }),
  ask: (chatId: string | null, message: string) =>
    request<ChatResponse>('/api/chat', {
      method: 'POST',
      body: JSON.stringify({ chat_id: chatId, message }),
    }),
  agentReview,
}
