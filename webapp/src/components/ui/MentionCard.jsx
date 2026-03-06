import React from 'react'
import { openLink, hapticFeedback } from '../../services/telegram'

const SOURCE_LABELS = {
  yandex:   { label: 'Яндекс',  color: '#ef4444' },
  telegram: { label: 'TG',      color: '#0ea5e9' },
  website:  { label: 'Портал',  color: '#8b5cf6' },
}

const SENTIMENT_LABELS = {
  positive: { icon: '😊', color: '#10b981' },
  neutral:  { icon: '😐', color: '#6b7280' },
  negative: { icon: '😟', color: '#ef4444' },
}

function formatDate(isoDate) {
  if (!isoDate) return ''
  const months = ['янв', 'фев', 'мар', 'апр', 'май', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек']
  const d = new Date(isoDate)
  return `${d.getDate()} ${months[d.getMonth()]} ${d.getFullYear()}`
}

function getDomain(url) {
  if (!url) return ''
  try {
    return new URL(url).hostname.replace(/^www\./, '')
  } catch {
    return ''
  }
}

// Для Яндекс-результатов source_name = "Яндекс" — не информативно,
// лучше показать домен сайта. Для TG и website source_name уже осмысленный.
function getDisplaySource(mention) {
  if (mention.source_type === 'yandex') {
    return getDomain(mention.url) || mention.source_name || ''
  }
  return mention.source_name || ''
}

export default function MentionCard({ mention }) {
  const source = SOURCE_LABELS[mention.source_type] || { label: mention.source_type, color: '#6b7280' }
  const sentiment = SENTIMENT_LABELS[mention.sentiment]
  const displaySource = getDisplaySource(mention)

  const handleClick = () => {
    if (!mention.url) return
    hapticFeedback('light')
    openLink(mention.url)
  }

  return (
    <div onClick={handleClick} style={styles.card}>
      {/* Шапка: бейджи + мета */}
      <div style={styles.header}>
        <div style={styles.badges}>
          <span style={{ ...styles.badge, backgroundColor: source.color + '22', color: source.color }}>
            {source.label}
          </span>
          {sentiment && (
            <span style={{ ...styles.badge, backgroundColor: SENTIMENT_LABELS[mention.sentiment].color + '22', color: SENTIMENT_LABELS[mention.sentiment].color }}>
              {sentiment.icon} {mention.sentiment === 'positive' ? 'Позитивно' : mention.sentiment === 'negative' ? 'Негативно' : 'Нейтрально'}
            </span>
          )}
        </div>
        <div style={styles.meta}>
          {displaySource && <span>{displaySource}</span>}
          {displaySource && mention.post_date && <span> · </span>}
          {mention.post_date && <span>{formatDate(mention.post_date)}</span>}
        </div>
      </div>

      {/* Заголовок */}
      {mention.title && (
        <div style={styles.title}>
          {mention.title}
          {mention.url && <span style={styles.linkIcon}> ↗</span>}
        </div>
      )}

      {/* URL источника */}
      {mention.url && (
        <div style={styles.url}>{mention.url}</div>
      )}

      {/* Саммари или сниппет */}
      {(mention.summary || mention.content_snippet) && (
        <div style={styles.summary}>
          {mention.summary || mention.content_snippet}
        </div>
      )}
    </div>
  )
}

const styles = {
  card: {
    backgroundColor: '#1a1a24',
    borderRadius: 12,
    padding: 16,
    border: '1px solid #2a2a3a',
    cursor: 'pointer',
    animation: 'slideUp 0.3s ease',
  },
  header: {
    display: 'flex',
    flexDirection: 'column',
    gap: 4,
    marginBottom: 8,
  },
  badges: {
    display: 'flex',
    flexWrap: 'wrap',
    gap: 6,
  },
  badge: {
    fontSize: 11,
    fontWeight: 600,
    padding: '3px 8px',
    borderRadius: 6,
    letterSpacing: 0.3,
  },
  meta: {
    fontSize: 12,
    color: '#6b7280',
  },
  title: {
    fontSize: 15,
    color: '#fff',
    fontWeight: 500,
    lineHeight: 1.4,
    marginBottom: 6,
    wordBreak: 'break-word',
  },
  linkIcon: {
    color: '#3b82f6',
    fontWeight: 400,
  },
  url: {
    fontSize: 11,
    color: '#4b5563',
    marginBottom: 6,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
  },
  summary: {
    fontSize: 13,
    color: '#9ca3af',
    lineHeight: 1.5,
    display: '-webkit-box',
    WebkitLineClamp: 3,
    WebkitBoxOrient: 'vertical',
    overflow: 'hidden',
    wordBreak: 'break-word',
  },
}
