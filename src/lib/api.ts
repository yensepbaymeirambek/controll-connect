// Requests go to relative paths so they are same-origin: the vite proxy in dev
// and nginx in prod forward them to the backend by service name. Set VITE_API_URL
// only when pointing the app at a backend on a different origin.
const BASE_URL = (import.meta.env.VITE_API_URL ?? '').replace(/\/$/, '')

export class ApiError extends Error {
  status?: number

  constructor(message: string, status?: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

export interface Connector {
  id: string
  name: string
  status: string
  detail: string | null
  records: number
  last_sync: string | null
}

export interface ConnectorsResponse {
  connectors: Connector[]
  configured: boolean
}

export interface Metric {
  id: string
  label: string
  value: string
  detail: string
  change: string
  direction: 'up' | 'down' | 'flat'
}

export interface Chart {
  y_max: number
  labels: string[]
  series: { id: string; label: string; points: number[] }[]
}

export interface SourceError {
  source: string
  message: string
}

/** Cards carry data computed by the backend; the model only chooses what to compute. */
export type Card =
  | { kind: 'metric'; title: string; value: string; detail: string }
  | { kind: 'bar' | 'line'; title: string; group_by: string; data: { label: string; value: number }[] }
  | { kind: 'table'; title: string; columns: string[]; rows: Record<string, string | number | null>[] }

export interface MetricsResponse {
  metrics: Metric[]
  chart: Chart
  breakdown: { by_state: Card | null; by_assignee: Card | null }
  last_sync: string | null
  errors: SourceError[]
  configured: boolean
}

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

export type ChatMode = 'llm' | 'unconfigured' | 'error'

export interface ChatResponse {
  answer: string
  cards: Card[]
  errors: SourceError[]
  generated_at: string
  record_count: number
  mode: ChatMode
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${BASE_URL}${path}`, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...init?.headers },
    })
  } catch {
    throw new ApiError('Cannot reach the API. Is the backend running?')
  }
  if (!response.ok) {
    throw new ApiError(`Request to ${path} failed (${response.status})`, response.status)
  }
  return (await response.json()) as T
}

export const api = {
  connectors: (signal?: AbortSignal) => request<ConnectorsResponse>('/api/connectors', { signal }),
  metrics: (signal?: AbortSignal, refresh = false) =>
    request<MetricsResponse>(`/api/metrics${refresh ? '?refresh=true' : ''}`, { signal }),
  chat: (messages: ChatMessage[], refresh = false) =>
    request<ChatResponse>('/api/chat', { method: 'POST', body: JSON.stringify({ messages, refresh }) }),
}
