import { useParams, Navigate, useNavigate } from 'react-router-dom'
import { MONTHS, WEEKS } from '../data'
import styles from './MonthPage.module.css'

const POST_ICONS = { image: '🖼', video: '▶' }
const STATUS_LABELS = { ready: 'Ready', pending: 'Pending' }

function WeekCard({ week, onClick }) {
  return (
    <button className={styles.card} onClick={() => onClick(week)} aria-label={`Open ${week.label}`}>
      <div className={styles.cardTop}>
        <div>
          <div className={styles.cardEyebrow}>Weekly Content</div>
          <div className={styles.cardDate}>{week.label}</div>
        </div>
        <span className={`${styles.badge} ${styles[week.status]}`}>
          {STATUS_LABELS[week.status]}
        </span>
      </div>

      <div className={styles.thumbs}>
        {week.status === 'ready' ? (
          week.posts.map((post, i) => (
            <div key={i} className={`${styles.thumb} ${styles[post.type]}`}>
              <span className={styles.thumbIcon}>{POST_ICONS[post.type]}</span>
              <span className={styles.thumbType}>{post.type}</span>
              {post.type === 'video' && <span className={styles.thumbDuration}>{post.duration}</span>}
            </div>
          ))
        ) : (
          [0, 1, 2].map(i => <div key={i} className={styles.thumb}><span className={styles.thumbIcon}>·</span></div>)
        )}
      </div>

      <div className={styles.cardFooter}>
        <span className={styles.postCount}>
          {week.status === 'ready'
            ? <><strong>{week.posts.length}</strong> posts ready to review</>
            : 'Scheduled for generation'}
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

export default function MonthPage() {
  const { monthId } = useParams()
  const navigate = useNavigate()
  const month = MONTHS.find(m => m.id === monthId)
  const weeks = WEEKS.filter(w => w.monthId === monthId).sort((a, b) => b.id.localeCompare(a.id))

  if (!month) return <Navigate to="/" replace />

  const readyCount = weeks.filter(w => w.status === 'ready').length

  return (
    <main className={styles.main}>
      <div className={styles.sectionHeader}>
        <div>
          <div className={styles.eyebrow}>{month.label}</div>
          <h1 className={styles.title}>Weekly Posts</h1>
        </div>
        <span className={styles.count}>{readyCount} weeks ready</span>
      </div>

      <div className={styles.grid}>
        {weeks.map(week => (
          <WeekCard key={week.id} week={week} onClick={w => navigate(`/week/${w.id}`)} />
        ))}
      </div>
    </main>
  )
}
