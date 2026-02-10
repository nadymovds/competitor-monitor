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

function prepareTextForCopy(post) {
  const rawTitle = post.title || ''
  const contentText = post.content_text || ''
  const summaryText = post.summary || ''

  // Если content_text начинается с заголовка — используем content_text целиком (он уже содержит заголовок)
  if (contentText && rawTitle && contentText.startsWith(rawTitle)) {
    return contentText
  }

  const lines = []

  // Добавляем заголовок если есть
  if (rawTitle) {
    lines.push(rawTitle)
  }

  // Добавляем содержимое если есть и не дублирует заголовок
  const bodyText = contentText || summaryText
  if (bodyText && bodyText !== rawTitle) {
    lines.push(bodyText)
  }

  // Объединяем с пустой строкой для разделения
  return lines.filter(line => line.trim()).join('\n\n')
}

function prepareLinkForCopy(url) {
  if (!url) return ''
  
  // Используем Markdown формат для гиперссылки
  // [Ссылка](url) - будет работать в приложениях, поддерживающих Markdown
  // В приложениях без Markdown поддержки будет просто текст и URL
  return `[Ссылка](${url})`
}

function copyToClipboard(text) {
  // Проверяем наличие Clipboard API
  if (!navigator.clipboard) {
    // Fallback для старых браузеров
    return Promise.reject(new Error('Clipboard API не поддерживается'))
  }
  
  // Используем Clipboard API для копирования текста
  return navigator.clipboard
    .writeText(text)
    .then(() => {
      return { success: true }
    })
    .catch((error) => {
      console.error('Ошибка при копировании в буфер обмена:', error)
      return { success: false, error }
    })
}

export default function NewsCard({ post, isAdmin, allCategories, onCategoryAdd, onCategoryRemove }) {
  const [expanded, setExpanded] = useState(false)
  const [showCategoryPicker, setShowCategoryPicker] = useState(false)
  const [needsExpand, setNeedsExpand] = useState(false)
  const [toastMessage, setToastMessage] = useState('')
  const toastTimeoutRef = useRef(null)
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

  // Очистка тоста при размонтировании компонента
  useEffect(() => {
    return () => {
      if (toastTimeoutRef.current) {
        clearTimeout(toastTimeoutRef.current)
      }
    }
  }, [])

  const showToast = (message, duration = 2000) => {
    // Очищаем предыдущий таймер если существует
    if (toastTimeoutRef.current) {
      clearTimeout(toastTimeoutRef.current)
    }
    
    setToastMessage(message)
    toastTimeoutRef.current = setTimeout(() => {
      setToastMessage('')
    }, duration)
  }

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

  const handleCopy = (e) => {
    e.stopPropagation()
    hapticFeedback('light')
    
    // Подготавливаем текст для копирования
    const text = prepareTextForCopy(post)
    const link = prepareLinkForCopy(post.post_url)
    
    // Объединяем текст и ссылку
    const fullText = link ? `${text}\n\n${link}` : text
    
    // Копируем в буфер обмена
    copyToClipboard(fullText).then((result) => {
      if (result.success) {
        showToast('Скопировано')
      } else {
        showToast('Ошибка копирования')
      }
    })
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
  const sourceType = post.source_type || post.channel?.source_type || 'telegram'
  const sourceIcon = sourceType === 'website' ? '🌐' : '📱'

  if (sourceType === 'website') {
    // Для веб-источника показываем title
    if (post.channel?.title) metaParts.push(`${sourceIcon} ${post.channel.title}`)
    else metaParts.push(sourceIcon)
  } else {
    // Для Telegram показываем @username
    if (post.channel?.username) metaParts.push(`${sourceIcon} @${post.channel.username}`)
    else if (post.channel?.title) metaParts.push(`${sourceIcon} ${post.channel.title}`)
    else metaParts.push(sourceIcon)
  }
  if (post.post_date) metaParts.push(formatDate(post.post_date))
  const views = formatViews(post.views_count)
  if (views) metaParts.push(`${views} 👁`)
  if (mediaIcons.length > 0) metaParts.push(mediaIcons.join(' '))

  const rawTitle = post.title || ''
  const contentText = post.content_text || ''
  const summaryText = post.summary || ''

  const normalizeText = (str) => (str || '').replace(/\.{2,}$/, '').trim().slice(0, 40)
  const isDuplicateBody = rawTitle && contentText && normalizeText(rawTitle) === normalizeText(contentText)

  // Если content_text совпадает с title, используем summary как основной текст
  const bodyText = isDuplicateBody ? (summaryText || contentText) : (contentText || summaryText)

  // Заголовок показываем если body не начинается с него
  const showTitle = rawTitle && !bodyText.startsWith(rawTitle)

  // В свёрнутом виде: показываем title как обычный текст если body пустой или совпадает
  const displayBody = bodyText

  // Fallback: если и title скрыт, и body пуст — показываем title
  const showFallbackTitle = !showTitle && !displayBody && rawTitle

  // Показываем "Показать полностью" если текст обрезается ИЛИ есть summary для показа
  const hasSummaryToShow = isDuplicateBody && summaryText && summaryText !== rawTitle
  const canExpand = needsExpand || hasSummaryToShow

  return (
    <div style={styles.card}>
      {/* Toast уведомление */}
      {toastMessage && (
        <div style={styles.toast}>
          {toastMessage}
        </div>
      )}

      {/* Текст: заголовок + тело, кликабельный для expand/collapse */}
      <div onClick={handleToggleExpand} style={{ cursor: 'pointer' }}>
        {expanded ? (
          <div style={styles.expandedText}>
            {(showTitle || showFallbackTitle) && <><span style={styles.titleText}>{rawTitle}</span>{'\n'}</>}
            {displayBody}
          </div>
        ) : (
          <>
            <div ref={textRef} style={styles.clampedText}>
              {(showTitle || showFallbackTitle) && <><span style={styles.titleText}>{rawTitle}</span>{'\n'}</>}
              {displayBody}
            </div>
            {canExpand && (
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
          {isAdmin && post.post_url && (
            <button onClick={handleCopy} style={styles.copyBtn}>
              Копировать
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
    position: 'relative',
  },
  toast: {
    position: 'absolute',
    top: 10,
    left: '50%',
    transform: 'translateX(-50%)',
    backgroundColor: '#10b981',
    color: '#fff',
    padding: '8px 16px',
    borderRadius: 6,
    fontSize: 13,
    fontWeight: 500,
    zIndex: 100,
    animation: 'slideDown 0.3s ease',
    boxShadow: '0 4px 12px rgba(16, 185, 129, 0.3)',
  },
  clampedText: {
    fontSize: 14,
    color: '#d1d5db',
    lineHeight: 1.5,
    whiteSpace: 'normal',
    display: '-webkit-box',
    WebkitLineClamp: 4,
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
  copyBtn: {
    background: 'none',
    border: 'none',
    color: '#10b981',
    fontSize: 12,
    fontWeight: 500,
    cursor: 'pointer',
    padding: '4px 0',
    whiteSpace: 'nowrap',
  },
}
