import { Link, useNavigate, useLocation } from 'react-router-dom'
import logo from '@brand/Logo.png'
import { useData } from '../context/DataContext'
import styles from './Header.module.css'

export default function Header({ monthLabel, weekLabel }) {
  const navigate = useNavigate()
  const location = useLocation()
  const { weeks } = useData()
  const isMonthPage = location.pathname.startsWith('/month/')
  const isWeekPage = location.pathname.startsWith('/week/')
  const showBack = isMonthPage || isWeekPage

  function handleBack() {
    if (isWeekPage) {
      const weekId = location.pathname.split('/week/')[1]
      const week = weeks.find(w => w.id === weekId)
      navigate(week ? `/month/${week.monthId}` : '/')
    } else {
      navigate('/')
    }
  }

  const rightLabel = isWeekPage && weekLabel
    ? weekLabel
    : isMonthPage && monthLabel
      ? monthLabel
      : 'Content Calendar'

  return (
    <header className={styles.header}>
      <div className={styles.inner}>
        <div className={styles.left}>
          {showBack && (
            <button className={styles.back} onClick={handleBack} aria-label="Go back">
              <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M10 6H2M6 2L2 6l4 4" />
              </svg>
            </button>
          )}
          <Link className={styles.logo} to="/">
            <img src={logo} alt="Blue Fit" className={styles.logoImg} />
            <div className={styles.logoText}>
              <span className={styles.logoName}>Blue Fit</span>
              <span className={styles.logoSub}>Content Studio</span>
            </div>
          </Link>
        </div>

        <div className={styles.right}>
          <span className={isWeekPage || isMonthPage ? styles.crumb : styles.meta}>
            {rightLabel}
          </span>
        </div>
      </div>
    </header>
  )
}
