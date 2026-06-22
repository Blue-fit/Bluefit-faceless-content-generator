import { useNavigate } from 'react-router-dom'
import { useData } from '../context/DataContext'
import styles from './HomePage.module.css'

function MonthCard({ month, weeks, onClick }) {
  const readyCount = weeks.filter(w => w.status === 'ready').length
  const allReady = readyCount === weeks.length && weeks.length > 0

  return (
    <button className={styles.card} onClick={() => onClick(month)} aria-label={`Open ${month.label}`}>
      <div className={styles.cardTop}>
        <div>
          <div className={styles.cardEyebrow}>Content Calendar</div>
          <div className={styles.cardDate}>{month.label}</div>
        </div>
        <span className={`${styles.badge} ${allReady ? styles.ready : styles.pending}`}>
          {readyCount}/{weeks.length} Ready
        </span>
      </div>

      <div className={styles.weekList}>
        {weeks.map(w => (
          <div key={w.id} className={styles.weekRow}>
            <span className={styles.weekLabel}>{w.label}</span>
            <span className={`${styles.weekStatus} ${styles[w.status]}`}>
              {w.status === 'ready' ? `${w.posts.length} posts` : 'Pending'}
            </span>
          </div>
        ))}
      </div>

      <div className={styles.cardFooter}>
        <span className={styles.postCount}>
          <strong>{weeks.length}</strong> weeks &middot; <strong>{readyCount}</strong> ready to review
        </span>
        <span className={styles.arrow}>
          <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M2 6h8M6 2l4 4-4 4" />
          </svg>
        </span>
      </div>
    </button>
  )
}

export default function HomePage() {
  const navigate = useNavigate()
  const { months, weeks, loading, error } = useData()

  const readyMonths = months.filter(m =>
    weeks.filter(w => w.monthId === m.id).some(w => w.status === 'ready')
  ).length

  if (loading) return <main className={styles.main}><p style={{ color: 'var(--text-muted)' }}>Loading...</p></main>
  if (error) return <main className={styles.main}><p style={{ color: 'red' }}>Failed to load: {error}</p></main>

  return (
    <main className={styles.main}>
      <div className={styles.sectionHeader}>
        <div>
          <div className={styles.eyebrow}>Content Calendar</div>
          <h1 className={styles.title}>Monthly Overview</h1>
        </div>
        <span className={styles.count}>{readyMonths} months active</span>
      </div>

      <div className={styles.grid}>
        {months.map(month => {
          const monthWeeks = weeks.filter(w => w.monthId === month.id).sort((a, b) => b.id.localeCompare(a.id))
          return (
            <MonthCard
              key={month.id}
              month={month}
              weeks={monthWeeks}
              onClick={m => navigate(`/month/${m.id}`)}
            />
          )
        })}
      </div>
    </main>
  )
}
