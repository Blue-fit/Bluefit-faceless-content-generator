import { useEffect, useState } from 'react'
import { useParams, Navigate } from 'react-router-dom'
import { useData } from '../context/DataContext'
import { sendChatMessage, fetchExplain } from '../api'
import { PILLAR_COLORS } from '../data'
import styles from './WeekPage.module.css'

function MediaModal({ url, type, onClose }) {
  useEffect(() => {
    function onKey(e) { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div className={styles.modalOverlay} onClick={onClose}>
      <div className={styles.modalContent} onClick={e => e.stopPropagation()}>
        <button className={styles.modalClose} onClick={onClose} aria-label="Close">
          <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
            <path d="M1 1l12 12M13 1L1 13" />
          </svg>
        </button>
        {type === 'video'
          ? <video src={url} controls autoPlay className={styles.modalMedia} />
          : <img src={url} alt="Full post" className={styles.modalMedia} />
        }
      </div>
    </div>
  )
}

function downloadAsset(url, pillar) {
  const BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'
  const slug = pillar.toLowerCase().replace(/\s+/g, '-')
  const a = document.createElement('a')
  a.href = `${BASE}/download?url=${encodeURIComponent(url)}&pillar=${encodeURIComponent(slug)}`
  a.click()
}

function PostCard({ post }) {
  const [messages, setMessages] = useState(post.messages)
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [showExplain, setShowExplain] = useState(false)
  const [explainText, setExplainText] = useState(null)
  const [explainLoading, setExplainLoading] = useState(false)
  const [explainError, setExplainError] = useState(false)
  const [showModal, setShowModal] = useState(false)

  async function toggleExplain() {
    const next = !showExplain
    setShowExplain(next)
    if (next && explainText == null && !explainLoading) {
      setExplainLoading(true)
      setExplainError(false)
      try {
        const data = await fetchExplain(post.id)
        setExplainText(data.explanation)
      } catch {
        setExplainError(true)
      } finally {
        setExplainLoading(false)
      }
    }
  }

  const [currentVersion, setCurrentVersion] = useState(post.currentVersion)
  const [totalVersions, setTotalVersions] = useState(post.totalVersions)
  const [caption, setCaption] = useState(post.caption)
  const pillarStyle = PILLAR_COLORS[post.pillar] || {}

  async function sendMessage(e) {
    e.preventDefault()
    if (!input.trim() || sending) return
    const text = input.trim()
    setInput('')
    setMessages(prev => [...prev, { role: 'user', text }])
    setSending(true)
    try {
      const result = await sendChatMessage(post.id, text)
      setMessages(prev => [...prev, { role: result.role, text: result.text }])
      if (result.version) {
        setCurrentVersion(result.version.version_number)
        setTotalVersions(v => Math.max(v, result.version.version_number))
        if (result.version.caption) setCaption(result.version.caption)
      }
    } catch {
      setMessages(prev => [...prev, { role: 'agent', text: 'Something went wrong. Please try again.' }])
    } finally {
      setSending(false)
    }
  }

  return (
    <div className={styles.postCard}>
      {/* Post preview */}
      {showModal && <MediaModal url={post.asset_url} type={post.type} onClose={() => setShowModal(false)} />}
      <div className={`${styles.preview} ${styles[post.type]}`}>
        <div className={styles.previewInner}>
          {post.asset_url ? (
            post.type === 'video'
              ? <video src={post.asset_url} controls className={styles.previewMedia} />
              : <img src={post.asset_url} alt="Post asset" className={styles.previewMedia} />
          ) : (
            <>
              <span className={styles.previewIcon}>{post.type === 'video' ? '▶' : '🖼'}</span>
              <span className={styles.previewType}>{post.type === 'video' ? 'Video' : 'Image'}</span>
            </>
          )}
        </div>
        {post.asset_url && (
          <div className={styles.previewActions}>
            <button className={styles.viewBtn} onClick={() => setShowModal(true)}>
              <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M1 7s2.5-5 6-5 6 5 6 5-2.5 5-6 5-6-5-6-5z" /><circle cx="7" cy="7" r="2" />
              </svg>
              View
            </button>
            <button className={styles.downloadBtn} onClick={() => downloadAsset(post.asset_url, post.pillar)}>
              <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M7 1v8M4 6l3 3 3-3M2 11h10" />
              </svg>
              Download
            </button>
          </div>
        )}
      </div>

      {/* Post meta */}
      <div className={styles.meta}>
        <div className={styles.metaLeft}>
          <span className={styles.pillar} style={{ background: pillarStyle.bg, color: pillarStyle.text }}>
            {post.pillar}
          </span>
          <span className={styles.version}>Version {currentVersion} of {Math.max(totalVersions, currentVersion)}</span>
        </div>
        <button
          className={`${styles.explainBtn} ${showExplain ? styles.explainActive : ''}`}
          onClick={toggleExplain}
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
          {explainLoading && <p>Generating explanation…</p>}
          {explainError && <p>Couldn't load the explanation — please try again.</p>}
          {!explainLoading && !explainError && explainText && (
            <p style={{ whiteSpace: 'pre-wrap' }}>{explainText}</p>
          )}
        </div>
      )}

      {/* Caption */}
      <div className={styles.caption}>
        <div className={styles.captionLabel}>Caption</div>
        <p className={styles.captionText}>{caption}</p>
      </div>

      {/* Chat thread */}
      <div className={styles.chat}>
        <div className={styles.chatLabel}>Post thread</div>
        <div className={styles.messages}>
          {messages.map((msg, i) => (
            <div key={i} className={`${styles.message} ${styles[msg.role]}`}>
              <div className={styles.messageAvatar}>
                {msg.role === 'agent' || msg.role === 'model' ? 'BF' : 'You'}
              </div>
              <div className={styles.messageBubble}>{msg.text}</div>
            </div>
          ))}
          {sending && (
            <div className={`${styles.message} ${styles.agent}`}>
              <div className={styles.messageAvatar}>BF</div>
              <div className={styles.messageBubble} style={{ opacity: 0.5 }}>Generating...</div>
            </div>
          )}
        </div>

        <form className={styles.chatForm} onSubmit={sendMessage}>
          <input
            className={styles.chatInput}
            value={input}
            onChange={e => setInput(e.target.value)}
            placeholder="Request an edit, ask a question..."
            disabled={sending}
          />
          <button className={styles.sendBtn} type="submit" disabled={!input.trim() || sending}>
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
  const { weeks } = useData()
  const week = weeks.find(w => w.id === weekId)

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
