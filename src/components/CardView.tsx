import type { Card } from '../lib/api'

/** Renders one backend-computed card. Bars are scaled against the card's own max. */
export function CardView({ card }: { card: Card }) {
  if (card.kind === 'metric') {
    return <div className="card card-metric">
      <span className="card-title">{card.title}</span>
      <strong className="card-value">{card.value}</strong>
      <small>{card.detail}</small>
    </div>
  }

  if (card.kind === 'bar' || card.kind === 'line') {
    const max = Math.max(...card.data.map((row) => row.value), 1)
    return <div className="card">
      <span className="card-title">{card.title}</span>
      <ul className="bar-list">
        {card.data.map((row) => <li key={row.label}>
          <span className="bar-label" title={row.label}>{row.label}</span>
          <span className="bar-track"><i style={{ width: `${(row.value / max) * 100}%` }} /></span>
          <span className="bar-value">{row.value}</span>
        </li>)}
      </ul>
    </div>
  }

  if (card.kind !== 'table') return null

  return <div className="card card-wide">
    <span className="card-title">{card.title}</span>
    <div className="table-scroll">
      <table className="card-table">
        <thead><tr>{card.columns.map((column) => <th key={column}>{column}</th>)}</tr></thead>
        <tbody>
          {card.rows.map((row, index) => <tr key={index}>
            {card.columns.map((column) => <td key={column}>{row[column] ?? '—'}</td>)}
          </tr>)}
        </tbody>
      </table>
    </div>
  </div>
}

export function CardGrid({ cards }: { cards: Card[] }) {
  if (cards.length === 0) return null
  return <div className="card-grid">{cards.map((card, index) => <CardView key={`${card.title}-${index}`} card={card} />)}</div>
}
