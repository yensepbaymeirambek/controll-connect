import { useCallback } from 'react'
import { Activity, AlertCircle, BarChart3, CircleHelp, Database, LayoutDashboard, Loader2, RefreshCw, Search, Settings2, Sparkles } from 'lucide-react'
import './App.css'
import { api, type Chart, type Connector, type Metric } from './lib/api'
import { buildPath, toAreaPath } from './lib/chart'
import { useResource } from './hooks/useResource'
import { CardView } from './components/CardView'
import { Chat } from './components/Chat'

const CHART_WIDTH = 700
const CHART_HEIGHT = 220

function App() {
  const metrics = useResource(useCallback((signal: AbortSignal) => api.metrics(signal), []))
  const connectors = useResource(useCallback((signal: AbortSignal) => api.connectors(signal), []))

  const reloadAll = () => {
    metrics.reload()
    connectors.reload()
  }

  const configured = connectors.data?.configured ?? true
  const sourceErrors = metrics.data?.errors ?? []

  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand"><span className="brand-mark"><Sparkles size={16} /></span><span>signal<span className="brand-dot">.</span></span></div>
      <nav className="nav-list">
        <p className="nav-label">Workspace</p>
        <button className="nav-item active"><LayoutDashboard size={17} />Overview</button>
        <button className="nav-item"><BarChart3 size={17} />Dashboards</button>
        <p className="nav-label">Manage</p>
        <button className="nav-item"><Database size={17} />Connections<span className="nav-count">{connectors.data?.connectors.length ?? 0}</span></button>
        <button className="nav-item"><Settings2 size={17} />Settings</button>
      </nav>
      <div className="sidebar-bottom">
        <div className="usage"><small>Last sync</small><strong className="sync-time">{formatSync(metrics.data?.last_sync ?? null)}</strong></div>
      </div>
    </aside>

    <main className="main-content">
      <header className="topbar">
        <div className="breadcrumbs"><span>Workspace</span><span>/</span><strong>Overview</strong></div>
        <div className="top-actions">
          <button className="icon-button" title="Help"><CircleHelp size={18} /></button>
          <button className="icon-button" title="Search"><Search size={18} /></button>
          <button className="primary-button" onClick={reloadAll} disabled={metrics.loading}>
            {metrics.loading ? <Loader2 size={15} className="spin" /> : <RefreshCw size={15} />} Refresh
          </button>
        </div>
      </header>

      <div className="page-content">
        {!configured && <div className="banner">
          <AlertCircle size={16} />
          <div>
            <strong>No connectors configured</strong>
            <p>Set <code>JIRA_MCP_URL</code> to point at a Jira MCP server, or start the demo stack with the bundled stand-in.</p>
          </div>
        </div>}

        {sourceErrors.map((sourceError) => <div key={sourceError.source} className="banner banner-error">
          <AlertCircle size={16} />
          <div><strong>{sourceError.source} is failing</strong><p>{sourceError.message}</p></div>
        </div>)}

        <Chat onAnswered={reloadAll} />

        <section className="metric-grid">
          {metrics.loading && !metrics.data && Array.from({ length: 4 }, (_, index) => <div key={index} className="metric skeleton" />)}
          {metrics.error && <StateMessage kind="error" message={metrics.error} />}
          {metrics.data?.metrics.map((metric) => <MetricCard key={metric.id} metric={metric} />)}
        </section>

        <section className="dashboard-grid">
          <div className="panel chart-panel">
            <div className="panel-header"><div><h2>Created vs. resolved</h2><p>Weekly, from issue timestamps</p></div></div>
            {metrics.loading && !metrics.data && <StateMessage kind="loading" message="Loading chart…" />}
            {metrics.data && <WorkChart chart={metrics.data.chart} />}
          </div>

          <div className="right-stack">
            <div className="panel source-panel">
              <div className="panel-header"><div><h2>Connected sources</h2><p>Live status from each MCP server</p></div></div>
              {connectors.loading && !connectors.data && <StateMessage kind="loading" message="Checking sources…" />}
              {connectors.error && <StateMessage kind="error" message={connectors.error} />}
              {connectors.data?.connectors.length === 0 && !connectors.loading && <p className="empty">Nothing connected yet.</p>}
              {connectors.data?.connectors.map((connector) => <SourceRow key={connector.id} connector={connector} />)}
            </div>
            {metrics.data?.breakdown.by_state && <div className="panel"><CardView card={metrics.data.breakdown.by_state} /></div>}
          </div>
        </section>

        {metrics.data?.breakdown.by_assignee && <section className="panel">
          <CardView card={metrics.data.breakdown.by_assignee} />
        </section>}
      </div>
    </main>
  </div>
}

function formatSync(iso: string | null): string {
  if (!iso) return 'never'
  const seconds = Math.round((Date.now() - new Date(iso).getTime()) / 1000)
  if (seconds < 60) return `${seconds}s ago`
  if (seconds < 3600) return `${Math.round(seconds / 60)}m ago`
  return `${Math.round(seconds / 3600)}h ago`
}

function StateMessage({ kind, message }: { kind: 'loading' | 'error'; message: string }) {
  return <p className={`state-message ${kind}`}>{kind === 'loading' ? <Loader2 size={14} className="spin" /> : <AlertCircle size={14} />}{message}</p>
}

function MetricCard({ metric }: { metric: Metric }) {
  return <div className="metric">
    <div className={`metric-icon ${metric.direction === 'down' ? 'orange' : 'blue'}`}><Activity size={18} /></div>
    <div className="metric-copy"><span>{metric.label}</span><strong>{metric.value}</strong><small>{metric.detail}</small></div>
  </div>
}

function WorkChart({ chart }: { chart: Chart }) {
  const [created, resolved] = chart.series
  const createdPath = created ? buildPath(created.points, chart.y_max, CHART_WIDTH, CHART_HEIGHT) : ''
  const resolvedPath = resolved ? buildPath(resolved.points, chart.y_max, CHART_WIDTH, CHART_HEIGHT) : ''
  const ticks = Array.from({ length: 5 }, (_, index) => Math.round((chart.y_max / 4) * (4 - index)))

  return <>
    <div className="chart-legend">{chart.series.map((series, index) => <span key={series.id}><i className={`legend-dot ${index === 0 ? 'teal' : 'coral'}`} /> {series.label}</span>)}</div>
    <div className="chart">
      <div className="chart-y">{ticks.map((tick, index) => <span key={index}>{tick}</span>)}</div>
      <div className="chart-area">
        <div className="grid-lines"><i /><i /><i /><i /><i /></div>
        <svg viewBox={`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`} preserveAspectRatio="none" aria-label="Created versus resolved">
          <path className="area-fill" d={toAreaPath(createdPath, CHART_WIDTH, CHART_HEIGHT)} />
          <path className="line teal-line" d={createdPath} />
          <path className="line coral-line" d={resolvedPath} />
        </svg>
        <div className="chart-x">{chart.labels.map((label) => <span key={label}>{label}</span>)}</div>
      </div>
    </div>
  </>
}

function SourceRow({ connector }: { connector: Connector }) {
  return <div className="source-row">
    <span className={`source-logo ${connector.id}`}>{connector.name[0]}</span>
    <span>
      <strong>{connector.name}</strong>
      <small>{connector.status === 'connected' ? `${connector.records.toLocaleString()} records` : connector.detail ?? connector.status}</small>
    </span>
    <span className={`status-dot ${connector.status === 'connected' ? '' : 'warn'}`} title={connector.status} />
  </div>
}

export default App
