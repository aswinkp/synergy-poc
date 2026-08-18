import type { AuthUser, Chat, Message } from './types'

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
    request<{ chat_id: string; message: Message }>('/api/chat', {
      method: 'POST',
      body: JSON.stringify({ chat_id: chatId, message }),
    }),
}
