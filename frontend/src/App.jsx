import './App.css'

const SPEND_CAP = 50
const SPEND_CURRENT = 31.40

const WEEKS = [
  {
    id: 'w-2026-23',
    label: 'Week of June 2',
    dateRange: '2 – 8 Jun 2026',
    status: 'ready',
    posts: [
      { type: 'image' },
      { type: 'image' },
      { type: 'video' },
    ],
  },
  {
    id: 'w-2026-22',
    label: 'Week of May 26',
    dateRange: '26 May – 1 Jun 2026',
    status: 'ready',
    posts: [
      { type: 'image' },
      { type: 'image' },
      { type: 'video' },
    ],
  },
  {
    id: 'w-2026-21',
    label: 'Week of May 19',
    dateRange: '19 – 25 May 2026',
    status: 'ready',
    posts: [
      { type: 'image' },
      { type: 'image' },
      { type: 'video' },
    ],
  },
  {
    id: 'w-2026-20',
    label: 'Week of May 12',
    dateRange: '12 – 18 May 2026',
    status: 'ready',
    posts: [
      { type: 'image' },
      { type: 'image' },
      { type: 'video' },
    ],
  },
  {
    id: 'w-2026-19',
    label: 'Week of May 5',
    dateRange: '5 – 11 May 2026',
    status: 'ready',
    posts: [
      { type: 'image' },
      { type: 'image' },
      { type: 'video' },
    ],
  },
  {
    id: 'w-2026-24',
    label: 'Week of June 9',
    dateRange: '9 – 15 Jun 2026',
    status: 'pending',
    posts: [],
  },
]

function getSpendState(current, cap) {
  const pct = (current / cap) * 100
  if (pct >= 100) return { state: 'red', pct: Math.min(pct, 100), label: 'Cap reached' }
  if (pct >= 80) return { state: 'amber', pct, label: 'Near limit' }
  return { state: 'green', pct, label: 'On track' }
}

const POST_ICONS = { image: '🖼', video: '▶' }
const STATUS_LABELS = { ready: 'Ready', pending: 'Pending', generating: 'Generating' }

function WeekCard({ week, onClick }) {
  const readyCount = week.posts.length

  return (
    <button className="week-card" onClick={() => onClick(week)} aria-label={`Open ${week.label}`}>
      <div className="card-top">
        <div>
          <div className="card-week-label">Weekly Content</div>
          <div className="card-date">{week.label}</div>
        </div>
        <span className={`card-badge ${week.status}`}>
          {STATUS_LABELS[week.status]}
        </span>
      </div>

      <div className="card-posts">
        {week.status === 'ready' ? (
          week.posts.map((post, i) => (
            <div key={i} className={`post-thumb ${post.type}`}>
              <span className="post-thumb-icon">{POST_ICONS[post.type]}</span>
              <span className="post-thumb-type">{post.type}</span>
            </div>
          ))
        ) : (
          <>
            <div className="post-thumb"><span className="post-thumb-icon">·</span></div>
            <div className="post-thumb"><span className="post-thumb-icon">·</span></div>
            <div className="post-thumb"><span className="post-thumb-icon">·</span></div>
          </>
        )}
      </div>

      <div className="card-footer">
        <span className="card-post-count">
          {week.status === 'ready'
            ? <><strong>{readyCount}</strong> posts ready to review</>
            : 'Scheduled for generation'}
        </span>
        <span className="card-arrow">
          <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M2 6h8M6 2l4 4-4 4" />
          </svg>
        </span>
      </div>
    </button>
  )
}

export default function App() {
  const { state, pct, label } = getSpendState(SPEND_CURRENT, SPEND_CAP)

  function handleWeekClick(week) {
    // Will navigate to week detail view in Phase 2
    console.log('Open week:', week.id)
  }

  const sorted = [...WEEKS].sort((a, b) => b.id.localeCompare(a.id))

  return (
    <div className="app">
      {/* Header */}
      <header className="header">
        <div className="header-inner">
          <a className="logo" href="/">
            <div className="logo-mark" aria-hidden="true" />
            <div className="logo-text">
              <span className="logo-name">Blue Fit</span>
              <span className="logo-sub">Content Studio</span>
            </div>
          </a>
          <span className="header-meta">June 2026</span>
        </div>
      </header>

      {/* Spend Bar */}
      <div className="spend-section">
        <div className="spend-inner">
          <div className="spend-label-group">
            <div className="spend-heading">Monthly Spend</div>
            <div className="spend-amount">
              <span className="spend-current">€{SPEND_CURRENT.toFixed(2)}</span>
              <span className="spend-separator">/</span>
              <span className="spend-cap">€{SPEND_CAP}</span>
            </div>
          </div>

          <div className="spend-track">
            <div className="spend-bar-bg">
              <div
                className={`spend-bar-fill ${state}`}
                style={{ width: `${pct}%` }}
                role="progressbar"
                aria-valuenow={pct}
                aria-valuemin={0}
                aria-valuemax={100}
              />
            </div>
            <div className="spend-ticks">
              <span className="spend-tick">€0</span>
              <span className="spend-tick">€{SPEND_CAP * 0.5}</span>
              <span className="spend-tick">€{SPEND_CAP}</span>
            </div>
          </div>

          <div className={`spend-status ${state}`}>
            <span className="spend-status-dot" />
            {label}
          </div>
        </div>
      </div>

      {/* Week Grid */}
      <main className="main">
        <div className="section-header">
          <div>
            <div className="section-eyebrow">Content Calendar</div>
            <h1 className="section-title">Weekly Posts</h1>
          </div>
          <span className="section-count">{sorted.filter(w => w.status === 'ready').length} weeks ready</span>
        </div>

        <div className="weeks-grid">
          {sorted.length === 0 ? (
            <div className="empty-state"><p>No content generated yet.</p></div>
          ) : (
            sorted.map(week => (
              <WeekCard key={week.id} week={week} onClick={handleWeekClick} />
            ))
          )}
        </div>
      </main>
    </div>
  )
}
