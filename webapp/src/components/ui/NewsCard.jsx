import React, { useState, useEffect, useRef } from 'react'
import CategoryBadge from './CategoryBadge'
import { openLink, hapticFeedback } from '../../services/telegram'

function formatDate(isoDate) {
  const months = ['янв', 'фев', 'мар', 'апр', 'май', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек']
  const d = new Date(isoDate)
  return `${d.getDate()} ${months[d.getMonth()]} ${d.getFullYear()}`
}

function formatViews(count) {
  if (!count) return null
  if (count >= 1000000) return (count / 1000000).toFixed(1) + 'M'
  if (count >= 1000) return (count / 1000).toFixed(1) + 'K'
  return String(count)
}

export default function NewsCard({ post, isAdmin, allCategories, onCategoryAdd, onCategoryRemove }) {
  const [expanded, setExpanded] = useState(false)
  const [showCategoryPicker, setShowCategoryPicker] = useState(false)
  const pickerRef = useRef(null)

  const hasLongContent = post.content_text && post.content_text.length > 200

  // Закрытие dropdown по клику вне области
  useEffect(() => {
    if (!showCategoryPicker) return
    function handleClickOutside(e) {
      if (pickerRef.current && !pickerRef.current.contains(e.target)) {
        setShowCategoryPicker(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [showCategoryPicker])

  const handleToggleExpand = () => {
    hapticFeedback('light')
    setExpanded(!expanded)
  }

  const handleOpen = () => {
    if (post.post_url) {
      hapticFeedback('light')
      openLink(post.post_url)
    }
  }

  const handlePickCategory = (categoryId) => {
    onCategoryAdd(post.id, categoryId)
    setShowCategoryPicker(false)
  }

  // Категории, которых ещё нет на посте
  const assignedIds = new Set(post.categories.map(c => c.id))
  const availableCategories = (allCategories || []).filter(c => !assignedIds.has(c.id))

  // Медиа-индикаторы
  const mediaIcons = []
  if (post.has_photo) mediaIcons.push('📷')
  if (post.has_video) mediaIcons.push('🎥')
  if (post.has_document) mediaIcons.push('📎')

  // Мета-строка
  const metaParts = []
  if (post.channel?.username) metaParts.push(`@${post.channel.username}`)
  if (post.channel?.title && post.channel.title !== post.channel.username) metaParts.push(post.channel.title)
  if (post.post_date) metaParts.push(formatDate(post.post_date))
  const views = formatViews(post.views_count)
  if (views) metaParts.push(`${views} 👁`)

  return (
    <div style={styles.card}>
      {/* Заголовок + медиа */}
      <div style={styles.header}>
        <div style={styles.title}>{post.title || 'Без заголовка'}</div>
        {mediaIcons.length > 0 && (
          <div style={styles.mediaIcons}>{mediaIcons.join(' ')}</div>
        )}
      </div>

      {/* Текст */}
      <div style={styles.body}>
        {post.summary && (
          <div style={styles.summary}>{post.summary}</div>
        )}

        {hasLongContent && !expanded && (
          <button onClick={handleToggleExpand} style={styles.toggleBtn}>
            Показать полностью ▼
          </button>
        )}

        {expanded && post.content_text && (
          <>
            <div style={styles.contentText}>{post.content_text}</div>
            <button onClick={handleToggleExpand} style={styles.toggleBtn}>
              Свернуть ▲
            </button>
          </>
        )}

        {!post.summary && !hasLongContent && post.content_text && (
          <div style={styles.summary}>{post.content_text}</div>
        )}
      </div>

      {/* Мета + категории + действия */}
      <div style={styles.footer}>
        <div style={styles.meta}>{metaParts.join(' · ')}</div>

        {post.categories.length > 0 && (
          <div style={styles.categories}>
            {post.categories.map(cat => (
              <CategoryBadge
                key={cat.id}
                name={cat.name}
                color={cat.color}
                isManual={cat.is_manual}
                onRemove={isAdmin ? () => onCategoryRemove(post.id, cat.id) : null}
              />
            ))}
          </div>
        )}

        {/* Админ: добавление категории */}
        {isAdmin && (
          <div style={styles.pickerWrapper} ref={pickerRef}>
            <button
              onClick={() => { hapticFeedback('light'); setShowCategoryPicker(!showCategoryPicker) }}
              style={styles.addCategoryBtn}
            >
              + Категория
            </button>
            {showCategoryPicker && availableCategories.length > 0 && (
              <div style={styles.dropdown}>
                {availableCategories.map(cat => (
                  <button
                    key={cat.id}
                    onClick={() => handlePickCategory(cat.id)}
                    style={styles.dropdownItem}
                  >
                    <span style={{ color: cat.color }}>●</span> {cat.name}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Ссылка "Открыть" */}
        {post.post_url && (
          <div style={styles.openRow}>
            <button onClick={handleOpen} style={styles.openBtn}>
              Открыть →
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

const styles = {
  card: {
    backgroundColor: '#1a1a24',
    borderRadius: 12,
    padding: 16,
    border: '1px solid #2a2a3a',
    animation: 'slideUp 0.3s ease',
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    gap: 8,
  },
  title: {
    fontSize: 15,
    fontWeight: 600,
    color: '#fff',
    flex: 1,
  },
  mediaIcons: {
    fontSize: 14,
    flexShrink: 0,
  },
  body: {
    marginTop: 10,
    borderTop: '1px solid #2a2a3a',
    paddingTop: 10,
  },
  summary: {
    fontSize: 14,
    color: '#d1d5db',
    lineHeight: 1.5,
    whiteSpace: 'pre-wrap',
  },
  contentText: {
    fontSize: 14,
    color: '#d1d5db',
    lineHeight: 1.5,
    marginTop: 8,
    whiteSpace: 'pre-wrap',
  },
  toggleBtn: {
    background: 'none',
    border: 'none',
    color: '#3b82f6',
    fontSize: 13,
    cursor: 'pointer',
    padding: '6px 0',
    fontWeight: 500,
  },
  footer: {
    marginTop: 10,
    borderTop: '1px solid #2a2a3a',
    paddingTop: 10,
    display: 'flex',
    flexDirection: 'column',
    gap: 8,
  },
  meta: {
    fontSize: 12,
    color: '#6b7280',
  },
  categories: {
    display: 'flex',
    flexWrap: 'wrap',
    gap: 6,
  },
  pickerWrapper: {
    position: 'relative',
  },
  addCategoryBtn: {
    background: 'none',
    border: '1px dashed #3b82f6',
    color: '#3b82f6',
    fontSize: 12,
    borderRadius: 6,
    padding: '4px 10px',
    cursor: 'pointer',
    fontWeight: 500,
  },
  dropdown: {
    position: 'absolute',
    top: '100%',
    left: 0,
    marginTop: 4,
    backgroundColor: '#252532',
    borderRadius: 8,
    border: '1px solid #2a2a3a',
    padding: 4,
    zIndex: 10,
    minWidth: 160,
  },
  dropdownItem: {
    display: 'flex',
    alignItems: 'center',
    gap: 6,
    width: '100%',
    padding: '8px 10px',
    background: 'none',
    border: 'none',
    color: '#d1d5db',
    fontSize: 13,
    cursor: 'pointer',
    borderRadius: 6,
    textAlign: 'left',
  },
  openRow: {
    display: 'flex',
    justifyContent: 'flex-end',
  },
  openBtn: {
    background: 'none',
    border: 'none',
    color: '#3b82f6',
    fontSize: 13,
    fontWeight: 500,
    cursor: 'pointer',
    padding: '4px 0',
  },
}
