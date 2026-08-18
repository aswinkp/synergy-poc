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
  format: 'csv' | 'xlsx'
  filename: string
  url: string
  row_count: number
  size_bytes: number
  title: string
}

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
