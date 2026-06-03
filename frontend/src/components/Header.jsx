import { Link, useNavigate, useLocation } from 'react-router-dom'
import styles from './Header.module.css'

export default function Header({ weekLabel }) {
  const navigate = useNavigate()
  const location = useLocation()
  const isWeekPage = location.pathname.startsWith('/week/')

  return (
    <header className={styles.header}>
      <div className={styles.inner}>
        <div className={styles.left}>
          {isWeekPage && (
            <button className={styles.back} onClick={() => navigate('/')} aria-label="Back to home">
              <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M10 6H2M6 2L2 6l4 4" />
              </svg>
            </button>
          )}
          <Link className={styles.logo} to="/">
            <div className={styles.logoMark} aria-hidden="true" />
            <div className={styles.logoText}>
              <span className={styles.logoName}>Blue Fit</span>
              <span className={styles.logoSub}>Content Studio</span>
            </div>
          </Link>
        </div>

        <div className={styles.right}>
          {isWeekPage && weekLabel ? (
            <span className={styles.crumb}>{weekLabel}</span>
          ) : (
            <span className={styles.meta}>June 2026</span>
          )}
        </div>
      </div>
    </header>
  )
}
