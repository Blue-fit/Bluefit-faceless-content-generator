import { useEffect, useState } from 'react'
import { fetchSpend } from '../api'
import styles from './SpendBar.module.css'

function getSpendState(pct) {
  if (pct >= 100) return { state: 'red', label: 'Cap reached', warning: 'You have reached your monthly budget. Edits are paused until you approve further spend.' }
  if (pct >= 80) return { state: 'amber', label: 'Near limit', warning: `You've used ${pct.toFixed(0)}% of your budget. Further edits may exceed your cap.` }
  return { state: 'green', label: 'On track', warning: null }
}

export default function SpendBar() {
  const [pct, setPct] = useState(0)
  const [loaded, setLoaded] = useState(false)

  useEffect(() => {
    fetchSpend()
      .then(data => {
        const p = data.cap_eur > 0 ? (data.spent_eur / data.cap_eur) * 100 : 0
        setPct(Math.min(p, 100))
        setLoaded(true)
      })
      .catch(() => setLoaded(true))
  }, [])

  const { state, label, warning } = getSpendState(pct)

  return (
    <div className={styles.wrap}>
      <div className={styles.inner}>
        <div className={styles.labelGroup}>
          <div className={styles.heading}>Monthly Spend</div>
          <div className={styles.amount}>
            <span className={styles.current}>{loaded ? `${pct.toFixed(0)}%` : '—'}</span>
            <span className={styles.sep}> of budget used</span>
          </div>
        </div>

        <div className={styles.track}>
          <div className={styles.barBg}>
            <div
              className={`${styles.barFill} ${styles[state]}`}
              style={{ width: `${pct}%` }}
              role="progressbar"
              aria-valuenow={pct}
              aria-valuemin={0}
              aria-valuemax={100}
            />
          </div>
          <div className={styles.ticks}>
            <span>0%</span>
            <span>50%</span>
            <span>100%</span>
          </div>
        </div>

        <div className={`${styles.status} ${styles[state]}`}>
          <span className={styles.dot} />
          {loaded ? label : 'Loading...'}
        </div>
      </div>

      {warning && (
        <div className={`${styles.warning} ${styles[`warning_${state}`]}`}>
          <span className={styles.warningIcon}>{state === 'red' ? '🔴' : '🟡'}</span>
          {warning}
        </div>
      )}
    </div>
  )
}
