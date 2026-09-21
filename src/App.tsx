import { useCallback, useState } from 'react'
import { Activity, AlertCircle, ArrowUpRight, BarChart3, Check, ChevronDown, CircleHelp, CloudDownload, Database, FileText, Filter, LayoutDashboard, Loader2, MoreHorizontal, Plus, Search, Send, Settings2, Sparkles, Users, Zap } from 'lucide-react'
import './App.css'
import { api, ApiError, type Chart, type Connector, type Metric, type QueryResponse } from './lib/api'
import { buildPath, toAreaPath } from './lib/chart'
import { useResource } from './hooks/useResource'

const CHART_WIDTH = 700
const CHART_HEIGHT = 220

// Presentation for each metric the API can return; the backend sends data, not styling.
const METRIC_STYLES: Record<string, { icon: React.ReactNode; tone: string }> = {
  tasks_completed: { icon: <Check size={18} />, tone: 'green' },
  open_work: { icon: <Activity size={18} />, tone: 'blue' },
  contributors: { icon: <Users size={18} />, tone: 'orange' },
  freshness: { icon: <FileText size={18} />, tone: 'purple' },
}

const SOURCE_COLORS: Record<string, string> = { jira: 'jira', asana: 'asana', linear: 'linear' }

function App() {
  const [query, setQuery] = useState('')
  const [activeNav, setActiveNav] = useState('Overview')
  const [answer, setAnswer] = useState<QueryResponse | null>(null)
  const [asking, setAsking] = useState(false)
  const [askError, setAskError] = useState<string | null>(null)

  const metrics = useResource(useCallback((signal: AbortSignal) => api.metrics(signal), []))
  const connectors = useResource(useCallback((signal: AbortSignal) => api.connectors(signal), []))

  const submitQuery = async () => {
    const question = query.trim()
    if (!question || asking) return
    setAsking(true)
    setAskError(null)
    try {
      setAnswer(await api.query(question))
      setQuery('')
    } catch (error) {
      setAskError(error instanceof ApiError ? error.message : 'Unexpected error')
    } finally {
      setAsking(false)
    }
  }

  const navItems = [{ label: 'Overview', icon: LayoutDashboard }, { label: 'Ask data', icon: Sparkles }, { label: 'Dashboards', icon: BarChart3 }, { label: 'Exports', icon: CloudDownload }]

  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand"><span className="brand-mark"><Sparkles size={16} /></span><span>signal<span className="brand-dot">.</span></span></div>
      <div className="workspace-switcher"><span className="workspace-avatar">N</span><span><strong>Northstar team</strong><small>Workspace</small></span><ChevronDown size={14} /></div>
      <nav className="nav-list"><p className="nav-label">Workspace</p>{navItems.map(({ label, icon: Icon }) => <button key={label} className={`nav-item ${activeNav === label ? 'active' : ''}`} onClick={() => setActiveNav(label)}><Icon size={17} />{label}{label === 'Ask data' && <span className="nav-kbd">⌘ K</span>}</button>)}<p className="nav-label">Manage</p><button className="nav-item"><Database size={17} />Connections<span className="nav-count">{connectors.data?.length ?? '–'}</span></button><button className="nav-item"><Settings2 size={17} />Settings</button></nav>
      <div className="sidebar-bottom"><div className="usage"><div><span>Sync capacity</span><strong>72%</strong></div><div className="usage-bar"><span /></div><small>Resets in 12 days</small></div><div className="user-row"><div className="user-avatar">AM</div><span><strong>Alex Morgan</strong><small>Admin</small></span><MoreHorizontal size={17} /></div></div>
    </aside>
    <main className="main-content">
      <header className="topbar"><div className="breadcrumbs"><span>Northstar team</span><span>/</span><strong>{activeNav}</strong></div><div className="top-actions"><button className="icon-button" title="Help"><CircleHelp size={18} /></button><button className="icon-button" title="Search"><Search size={18} /></button><button className="primary-button"><Plus size={16} /> Add connection</button></div></header>
      <div className="page-content">
        <section className="intro"><div><p className="eyebrow"><Activity size={14} /> LIVE WORKSPACE</p><h1>Good morning, Alex</h1><p className="subheading">Your connected work, distilled into decisions.</p></div><button className="date-button">Last 30 days <ChevronDown size={15} /></button></section>

        <section className="ask-panel">
          <div className="ask-heading"><span className="sparkle-icon"><Sparkles size={17} /></span><div><h2>Ask your workspace</h2><p>Query Jira, Asana, and more in plain language.</p></div><span className="beta-tag">BETA</span></div>
          <div className="query-input">
            <input value={query} onChange={(event) => setQuery(event.target.value)} onKeyDown={(event) => event.key === 'Enter' && submitQuery()} placeholder="e.g. Which projects are at risk this month?" disabled={asking} />
            <button onClick={submitQuery} disabled={asking || !query.trim()} aria-label="Send question">{asking ? <Loader2 size={16} className="spin" /> : <Send size={16} />}</button>
          </div>
          {askError && <p className="ask-error"><AlertCircle size={13} /> {askError}</p>}
          {answer && !askError && <div className="answer" aria-live="polite">
            <p className="answer-question">{answer.question}</p>
            <p className="answer-text">{answer.answer}</p>
            {answer.rows.length > 0 && <table className="answer-table"><thead><tr>{Object.keys(answer.rows[0]).map((key) => <th key={key}>{key}</th>)}</tr></thead><tbody>{answer.rows.map((row, index) => <tr key={index}>{Object.values(row).map((value, cell) => <td key={cell}>{value}</td>)}</tr>)}</tbody></table>}
            <p className="query-suggestion"><Zap size={13} /> Answered from: <span>{answer.sources.join(', ')}</span></p>
          </div>}
          {!answer && !askError && <div className="query-suggestion"><Zap size={13} /> Try: <span>Show me overdue Jira issues by team</span></div>}
        </section>

        <section className="metric-grid">
          {metrics.loading && Array.from({ length: 4 }, (_, index) => <div key={index} className="metric skeleton" />)}
          {metrics.error && <StateMessage kind="error" message={metrics.error} />}
          {metrics.data?.metrics.map((metric) => <MetricCard key={metric.id} metric={metric} />)}
        </section>

        <section className="dashboard-grid">
          <div className="panel chart-panel">
            <div className="panel-header"><div><h2>Work completed</h2><p>Across all connected sources</p></div><div className="panel-actions"><button className="filter-button"><Filter size={14} /> Filter</button><button className="icon-button"><MoreHorizontal size={17} /></button></div></div>
            {metrics.loading && <StateMessage kind="loading" message="Loading chart…" />}
            {metrics.error && <StateMessage kind="error" message={metrics.error} />}
            {metrics.data && <WorkChart chart={metrics.data.chart} />}
          </div>
          <div className="right-stack">
            <div className="panel source-panel">
              <div className="panel-header"><div><h2>Connected sources</h2><p>Sync status at a glance</p></div><button className="icon-button" aria-label="Add source"><Plus size={17} /></button></div>
              {connectors.loading && <StateMessage kind="loading" message="Loading sources…" />}
              {connectors.error && <StateMessage kind="error" message={connectors.error} />}
              {connectors.data?.map((connector) => <SourceRow key={connector.id} connector={connector} />)}
              {connectors.data && <button className="view-all">Manage connections <ArrowUpRight size={14} /></button>}
            </div>
            {metrics.data && <div className="panel insight-panel">
              <div className="insight-icon"><Sparkles size={18} /></div>
              <div><p className="eyebrow">AI INSIGHT</p><h3>{metrics.data.insight.headline}</h3><p>{metrics.data.insight.detail}</p></div>
              <button className="icon-button" aria-label="Open insight"><ArrowUpRight size={16} /></button>
            </div>}
          </div>
        </section>
      </div>
    </main>
  </div>
}

function StateMessage({ kind, message }: { kind: 'loading' | 'error'; message: string }) {
  return <p className={`state-message ${kind}`}>{kind === 'loading' ? <Loader2 size={14} className="spin" /> : <AlertCircle size={14} />}{message}</p>
}

function MetricCard({ metric }: { metric: Metric }) {
  const style = METRIC_STYLES[metric.id] ?? { icon: <Activity size={18} />, tone: 'blue' }
  return <div className="metric">
    <div className={`metric-icon ${style.tone}`}>{style.icon}</div>
    <div className="metric-copy"><span>{metric.label}</span><strong>{metric.value}</strong><small className={metric.direction === 'down' ? '' : 'positive'}>{metric.change} <em>{metric.detail}</em></small></div>
  </div>
}

function WorkChart({ chart }: { chart: Chart }) {
  const [completed, created] = chart.series
  const completedPath = completed ? buildPath(completed.points, chart.y_max, CHART_WIDTH, CHART_HEIGHT) : ''
  const createdPath = created ? buildPath(created.points, chart.y_max, CHART_WIDTH, CHART_HEIGHT) : ''
  const ticks = Array.from({ length: 5 }, (_, index) => Math.round((chart.y_max / 4) * (4 - index)))

  return <>
    <div className="chart-legend">{chart.series.map((series, index) => <span key={series.id}><i className={`legend-dot ${index === 0 ? 'teal' : 'coral'}`} /> {series.label}</span>)}</div>
    <div className="chart">
      <div className="chart-y">{ticks.map((tick) => <span key={tick}>{tick}</span>)}</div>
      <div className="chart-area">
        <div className="grid-lines"><i /><i /><i /><i /><i /></div>
        <svg viewBox={`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`} preserveAspectRatio="none" aria-label="Work completed chart">
          <path className="area-fill" d={toAreaPath(completedPath, CHART_WIDTH, CHART_HEIGHT)} />
          <path className="line teal-line" d={completedPath} />
          <path className="line coral-line" d={createdPath} />
        </svg>
        <div className="chart-x">{chart.labels.map((label) => <span key={label}>{label}</span>)}</div>
      </div>
    </div>
  </>
}

function SourceRow({ connector }: { connector: Connector }) {
  return <div className="source-row">
    <span className={`source-logo ${SOURCE_COLORS[connector.id] ?? ''}`}>{connector.name[0]}</span>
    <span><strong>{connector.name}</strong><small>Last synced {connector.last_sync} · {connector.records.toLocaleString()} records</small></span>
    <span className={`status-dot ${connector.status === 'connected' ? '' : 'warn'}`} title={connector.status} />
  </div>
}

export default App
