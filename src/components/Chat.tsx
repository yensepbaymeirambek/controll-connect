import { useRef, useState } from 'react'
import { AlertCircle, Loader2, Send, Sparkles } from 'lucide-react'
import { api, ApiError, type Card, type ChatMessage } from '../lib/api'
import { CardGrid } from './CardView'

interface Turn {
  role: 'user' | 'assistant'
  content: string
  cards?: Card[]
  failed?: boolean
}

const SUGGESTIONS = [
  'What is overdue right now?',
  'Break open work down by assignee',
  'Show the oldest unresolved issues',
]

export function Chat({ onAnswered }: { onAnswered?: () => void }) {
  const [turns, setTurns] = useState<Turn[]>([])
  const [draft, setDraft] = useState('')
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const endRef = useRef<HTMLDivElement>(null)

  const send = async (text: string) => {
    const question = text.trim()
    if (!question || pending) return

    const history: ChatMessage[] = [...turns.map(({ role, content }) => ({ role, content })), { role: 'user', content: question }]
    setTurns((current) => [...current, { role: 'user', content: question }])
    setDraft('')
    setPending(true)
    setError(null)

    try {
      const response = await api.chat(history)
      setTurns((current) => [...current, {
        role: 'assistant',
        content: response.answer,
        cards: response.cards,
        failed: response.mode === 'error' || response.mode === 'unconfigured',
      }])
      onAnswered?.()
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Unexpected error')
    } finally {
      setPending(false)
      requestAnimationFrame(() => endRef.current?.scrollIntoView({ behavior: 'smooth' }))
    }
  }

  return <section className="ask-panel">
    <div className="ask-heading">
      <span className="sparkle-icon"><Sparkles size={17} /></span>
      <div><h2>Ask your workspace</h2><p>Answers and dashboards built from your connected data.</p></div>
    </div>

    {turns.length === 0 && <div className="suggestions">
      {SUGGESTIONS.map((suggestion) => <button key={suggestion} onClick={() => send(suggestion)} disabled={pending}>{suggestion}</button>)}
    </div>}

    {turns.length > 0 && <div className="thread">
      {turns.map((turn, index) => <div key={index} className={`turn turn-${turn.role}`}>
        <p className={turn.failed ? 'turn-failed' : ''}>{turn.content}</p>
        {turn.cards && turn.cards.length > 0 && <CardGrid cards={turn.cards} />}
      </div>)}
      {pending && <div className="turn turn-assistant"><p className="thinking"><Loader2 size={14} className="spin" /> Working…</p></div>}
      <div ref={endRef} />
    </div>}

    <div className="query-input">
      <input
        value={draft}
        onChange={(event) => setDraft(event.target.value)}
        onKeyDown={(event) => event.key === 'Enter' && send(draft)}
        placeholder="Ask anything, or ask for a chart"
        disabled={pending}
      />
      <button onClick={() => send(draft)} disabled={pending || !draft.trim()} aria-label="Send">
        {pending ? <Loader2 size={16} className="spin" /> : <Send size={16} />}
      </button>
    </div>

    {error && <p className="ask-error"><AlertCircle size={13} /> {error}</p>}
  </section>
}
