export type ChartType = 'bar' | 'pie' | 'line' | 'area' | 'table'

export interface Visualization {
  type: ChartType
  title: string
  data: Array<Record<string, string | number | null>>
  labelKey?: string
  valueKeys?: string[]
}

export interface ExportAttachment {
  id: string
  format: 'csv' | 'xlsx' | 'pptx'
  filename: string
  url: string
  row_count: number
  size_bytes: number
  title: string
}

export type AgentStepStatus = 'pending' | 'running' | 'complete'

export interface AgentStep {
  id: string
  label: string
  status: AgentStepStatus
  result?: string
}

export interface ChatResponse {
  chat_id: string
  message: Message
}

export type AgentStreamEvent =
  | { event: 'plan'; steps: Array<{ id: string; label: string }> }
  | { event: 'step'; id: string; status: 'running' | 'complete'; result?: string }
  | { event: 'content'; delta: string }
  | { event: 'result'; result: ChatResponse }
  | { event: 'error'; message: string }

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  visualization?: Visualization | null
  attachment?: ExportAttachment | null
  created_at: string
}

export interface Chat {
  id: string
  title: string
  created_at: string
  updated_at: string
  messages?: Message[]
}

export interface AuthUser {
  id: string
  email: string
  name: string
}
