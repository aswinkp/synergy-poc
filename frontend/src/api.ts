import type { Chat, Message } from './types'

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...options?.headers },
  })
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(body.detail || 'Something went wrong')
  }
  return response.json() as Promise<T>
}

export const api = {
  health: () => request<{ status: string; records: number; workbook: string }>('/api/health'),
  chats: () => request<Chat[]>('/api/chats'),
  chat: (id: string) => request<Chat>(`/api/chats/${id}`),
  removeChat: (id: string) => fetch(`/api/chats/${id}`, { method: 'DELETE' }),
  ask: (chatId: string | null, message: string) =>
    request<{ chat_id: string; message: Message }>('/api/chat', {
      method: 'POST',
      body: JSON.stringify({ chat_id: chatId, message }),
    }),
}
