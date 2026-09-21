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
  last_sync: string
  records: number
}

export type MetricDirection = 'up' | 'down' | 'flat'

export interface Metric {
  id: string
  label: string
  value: string
  change: string
  detail: string
  direction: MetricDirection
}

export interface ChartSeries {
  id: string
  label: string
  points: number[]
}

export interface Chart {
  y_max: number
  labels: string[]
  series: ChartSeries[]
}

export interface Insight {
  headline: string
  detail: string
}

export interface MetricsResponse {
  metrics: Metric[]
  chart: Chart
  insight: Insight
}

export interface QueryResponse {
  question: string
  answer: string
  sources: string[]
  rows: Record<string, string | number>[]
  generated_at: string
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
  connectors: (signal?: AbortSignal) => request<Connector[]>('/api/connectors', { signal }),
  metrics: (signal?: AbortSignal) => request<MetricsResponse>('/api/metrics', { signal }),
  query: (question: string, sources?: string[]) =>
    request<QueryResponse>('/api/query', {
      method: 'POST',
      body: JSON.stringify({ question, sources }),
    }),
}
