import { useState } from 'react'
import { useParams, Navigate } from 'react-router-dom'
import { WEEKS, PILLAR_COLORS } from '../data'
import styles from './WeekPage.module.css'

function PostCard({ post }) {
  const [messages, setMessages] = useState(post.messages)
  const [input, setInput] = useState('')
  const [showExplain, setShowExplain] = useState(false)
  const [currentVersion, setCurrentVersion] = useState(post.currentVersion)
  const pillarStyle = PILLAR_COLORS[post.pillar] || {}

  function sendMessage(e) {
    e.preventDefault()
    if (!input.trim()) return
    const userMsg = { role: 'user', text: input.trim() }
    const agentReply = { role: 'agent', text: `Got it — I'll apply your edit: "${input.trim()}". Generating a new version now...` }
    setMessages(prev => [...prev, userMsg, agentReply])
    setCurrentVersion(v => v + 1)
    setInput('')
  }

  return (
    <div className={styles.postCard}>
      {/* Post preview */}
      <div className={`${styles.preview} ${styles[post.type]}`}>
        <div className={styles.previewInner}>
          <span className={styles.previewIcon}>{post.type === 'video' ? '▶' : '🖼'}</span>
          <span className={styles.previewType}>{post.type === 'video' ? `Video · ${post.duration}` : 'Image'}</span>
        </div>
        <div className={styles.previewActions}>
          <button className={styles.downloadBtn} title="Download asset">
            <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M7 1v8M4 6l3 3 3-3M2 11h10" />
            </svg>
            Download
          </button>
        </div>
      </div>

      {/* Post meta */}
      <div className={styles.meta}>
        <div className={styles.metaLeft}>
          <span className={styles.pillar} style={{ background: pillarStyle.bg, color: pillarStyle.text }}>
            {post.pillar}
          </span>
          <span className={styles.version}>Version {currentVersion} of {Math.max(post.totalVersions, currentVersion)}</span>
        </div>
        <button
          className={`${styles.explainBtn} ${showExplain ? styles.explainActive : ''}`}
          onClick={() => setShowExplain(v => !v)}
        >
          <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="7" cy="7" r="6" />
            <path d="M7 6.5v4M7 4.5v.5" />
          </svg>
          Why this post?
        </button>
      </div>

      {/* Explain panel */}
      {showExplain && (
        <div className={styles.explainPanel}>
          <div className={styles.explainTitle}>Strategic reasoning</div>
          <p>This post was created based on this week's trend research, which identified <strong>sustainable movement</strong> as a high-engagement topic for Blue Fit's audience. The <strong>{post.pillar}</strong> pillar was selected to balance this week's content mix. The caption uses the <strong>{post.type === 'video' ? 'question' : 'observation'}</strong> engagement template to drive comments.</p>
        </div>
      )}

      {/* Caption */}
      <div className={styles.caption}>
        <div className={styles.captionLabel}>Caption</div>
        <p className={styles.captionText}>{post.caption}</p>
      </div>

      {/* Chat thread */}
      <div className={styles.chat}>
        <div className={styles.chatLabel}>Post thread</div>
        <div className={styles.messages}>
          {messages.map((msg, i) => (
            <div key={i} className={`${styles.message} ${styles[msg.role]}`}>
              <div className={styles.messageAvatar}>
                {msg.role === 'agent' ? 'BF' : 'You'}
              </div>
              <div className={styles.messageBubble}>{msg.text}</div>
            </div>
          ))}
        </div>

        <form className={styles.chatForm} onSubmit={sendMessage}>
          <input
            className={styles.chatInput}
            value={input}
            onChange={e => setInput(e.target.value)}
            placeholder="Request an edit, ask a question..."
          />
          <button className={styles.sendBtn} type="submit" disabled={!input.trim()}>
            <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M13 1L1 7l5 2 2 5 5-13z" />
            </svg>
          </button>
        </form>
      </div>
    </div>
  )
}

export default function WeekPage() {
  const { weekId } = useParams()
  const week = WEEKS.find(w => w.id === weekId)

  if (!week) return <Navigate to="/" replace />
  if (week.status === 'pending') {
    return (
      <main className={styles.main}>
        <div className={styles.pendingState}>
          <div className={styles.pendingIcon}>🗓</div>
          <h2>Content not generated yet</h2>
          <p>This week's posts will be generated on Friday at 09:00 UTC.</p>
        </div>
      </main>
    )
  }

  return (
    <main className={styles.main}>
      <div className={styles.header}>
        <div>
          <div className={styles.eyebrow}>Content Calendar</div>
          <h1 className={styles.title}>{week.label}</h1>
          <p className={styles.dateRange}>{week.dateRange}</p>
        </div>
        <div className={styles.headerRight}>
          <span className={styles.readyBadge}>{week.posts.length} posts ready</span>
        </div>
      </div>

      <div className={styles.posts}>
        {week.posts.map(post => (
          <PostCard key={post.id} post={post} />
        ))}
      </div>
    </main>
  )
}
