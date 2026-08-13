export type ChartType = 'bar' | 'pie' | 'line' | 'area' | 'table'

export interface Visualization {
  type: ChartType
  title: string
  data: Array<Record<string, string | number | null>>
  labelKey?: string
  valueKeys?: string[]
}

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  visualization?: Visualization | null
  created_at: string
}

export interface Chat {
  id: string
  title: string
  created_at: string
  updated_at: string
  messages?: Message[]
}
