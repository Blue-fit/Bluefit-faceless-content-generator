import { SPEND_CAP, SPEND_CURRENT } from '../data'
import styles from './SpendBar.module.css'

function getSpendState(current, cap) {
  const pct = (current / cap) * 100
  if (pct >= 100) return { state: 'red', pct: 100, label: 'Cap reached', warning: 'You have reached your monthly budget. Edits are paused until you approve further spend.' }
  if (pct >= 80) return { state: 'amber', pct, label: 'Near limit', warning: `You've used ${pct.toFixed(0)}% of your budget. Further edits may exceed your cap.` }
  return { state: 'green', pct, label: 'On track', warning: null }
}

export default function SpendBar() {
  const { state, pct, label, warning } = getSpendState(SPEND_CURRENT, SPEND_CAP)

  return (
    <div className={styles.wrap}>
      <div className={styles.inner}>
        <div className={styles.labelGroup}>
          <div className={styles.heading}>Monthly Spend</div>
          <div className={styles.amount}>
            <span className={styles.current}>€{SPEND_CURRENT.toFixed(2)}</span>
            <span className={styles.sep}>/</span>
            <span className={styles.cap}>€{SPEND_CAP}</span>
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
            <span>€0</span>
            <span>€{SPEND_CAP * 0.5}</span>
            <span>€{SPEND_CAP}</span>
          </div>
        </div>

        <div className={`${styles.status} ${styles[state]}`}>
          <span className={styles.dot} />
          {label}
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
