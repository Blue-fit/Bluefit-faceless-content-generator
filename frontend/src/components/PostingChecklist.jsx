import { useState } from 'react'
import styles from './PostingChecklist.module.css'

// Shown next to the posts, at the moment they download and publish them.
// Dutch, because the client is. Ticks are per browser only: a reminder, not state
// the backend cares about.
const STEPS = [
  "Plaats alle drie als Reel, ook de foto's. Reels bereiken mensen die je nog niet volgen, een gewone feedpost vrijwel alleen je volgers.",
  'Voeg in Instagram trending audio toe. Kies iets dat nú opkomt, niet een nummer dat al overal voorbijkomt.',
  "Post 's avonds tussen 20:00 en 21:00.",
  'Spreid de drie posts over de week, bijvoorbeeld maandag, woensdag en vrijdag. Alle drie op één dag kost bereik.',
  'De eerste regel van de caption is de haak. Instagram kapt af na ongeveer 125 tekens, dus wat daarvoor staat bepaalt of iemand doorleest.',
  'Voeg een locatie toe: Nijmegen of Lent. Dat helpt lokaal bereik.',
  'Houd het op 3 tot 5 hashtags die echt bij het onderwerp passen.',
  'Deel de post daarna in je Stories en reageer het eerste uur op reacties. Vroege interactie weegt zwaar.',
]

export default function PostingChecklist() {
  const [done, setDone] = useState(() => new Set())

  function toggle(i) {
    setDone(prev => {
      const next = new Set(prev)
      next.has(i) ? next.delete(i) : next.add(i)
      return next
    })
  }

  return (
    <section className={styles.card} aria-labelledby="posting-checklist-title">
      <div className={styles.head}>
        <div>
          <div className={styles.eyebrow}>Voor je plaatst</div>
          <h2 id="posting-checklist-title" className={styles.title}>Checklist</h2>
        </div>
        <span className={styles.count}>{done.size}/{STEPS.length}</span>
      </div>

      <ol className={styles.list}>
        {STEPS.map((step, i) => (
          <li key={i} className={done.has(i) ? styles.itemDone : styles.item}>
            <label className={styles.label}>
              <input
                type="checkbox"
                className={styles.box}
                checked={done.has(i)}
                onChange={() => toggle(i)}
              />
              <span className={styles.text}>{step}</span>
            </label>
          </li>
        ))}
      </ol>
    </section>
  )
}
