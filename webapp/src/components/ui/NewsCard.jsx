import React, { useState, useEffect, useLayoutEffect, useRef } from 'react'
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
  const [needsExpand, setNeedsExpand] = useState(false)
  const textRef = useRef(null)
  const pickerRef = useRef(null)

  // Определяем, обрезается ли текст (overflow за 3 строки)
  useLayoutEffect(() => {
    const el = textRef.current
    if (el && !expanded) {
      setNeedsExpand(el.scrollHeight > el.clientHeight + 1)
    }
  })

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

  const handleOpen = (e) => {
    e.stopPropagation()
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
  if (mediaIcons.length > 0) metaParts.push(mediaIcons.join(' '))

  const rawTitle = post.title || ''
  const bodyText = post.content_text || post.summary || ''

  // Если body начинается с title — не дублируем, показываем только body
  const showTitle = rawTitle && !bodyText.startsWith(rawTitle)
  const displayText = showTitle
    ? (bodyText ? `${rawTitle}\n${bodyText}` : rawTitle)
    : (bodyText || rawTitle || 'Без заголовка')

  return (
    <div style={styles.card}>
      {/* Текст: заголовок + тело, кликабельный для expand/collapse */}
      <div onClick={handleToggleExpand} style={{ cursor: 'pointer' }}>
        {expanded ? (
          <div style={styles.expandedText}>
            {showTitle && <><span style={styles.titleText}>{rawTitle}</span>{'\n'}</>}
            {showTitle ? bodyText : displayText}
          </div>
        ) : (
          <>
            <div ref={textRef} style={styles.clampedText}>
              {showTitle && <><span style={styles.titleText}>{rawTitle}</span>{'\n'}</>}
              {showTitle ? bodyText : displayText}
            </div>
            {needsExpand && (
              <div style={styles.showMore}>Показать полностью</div>
            )}
          </>
        )}
      </div>

      {/* Мета + категории + Оригинал */}
      <div style={styles.footer}>
        <div style={styles.meta}>{metaParts.join(' · ')}</div>
        <div style={styles.tagsRow}>
          {post.categories.map(cat => (
            <CategoryBadge
              key={cat.id}
              name={cat.name}
              color={cat.color}
              isManual={cat.is_manual}
              onRemove={isAdmin ? () => onCategoryRemove(post.id, cat.id) : null}
            />
          ))}
          {isAdmin && (
            <div style={styles.pickerWrapper} ref={pickerRef}>
              <button
                onClick={(e) => { e.stopPropagation(); hapticFeedback('light'); setShowCategoryPicker(!showCategoryPicker) }}
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
          {post.post_url && (
            <button onClick={handleOpen} style={styles.originalBtn}>
              Оригинал ↗
            </button>
          )}
        </div>
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
  clampedText: {
    fontSize: 14,
    color: '#d1d5db',
    lineHeight: 1.5,
    whiteSpace: 'pre-wrap',
    display: '-webkit-box',
    WebkitLineClamp: 3,
    WebkitBoxOrient: 'vertical',
    overflow: 'hidden',
    wordBreak: 'break-word',
  },
  expandedText: {
    fontSize: 14,
    color: '#d1d5db',
    lineHeight: 1.5,
    whiteSpace: 'pre-wrap',
    wordBreak: 'break-word',
  },
  titleText: {
    fontWeight: 600,
    color: '#fff',
    fontSize: 15,
  },
  showMore: {
    color: '#3b82f6',
    fontSize: 13,
    fontWeight: 500,
    marginTop: 4,
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
  tagsRow: {
    display: 'flex',
    flexWrap: 'wrap',
    alignItems: 'center',
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
  originalBtn: {
    background: 'none',
    border: 'none',
    color: '#3b82f6',
    fontSize: 12,
    fontWeight: 500,
    cursor: 'pointer',
    padding: '4px 0',
    whiteSpace: 'nowrap',
  },
}
