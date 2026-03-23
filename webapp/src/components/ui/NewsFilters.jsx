import React, { useState } from 'react'
import { hapticFeedback } from '../../services/telegram'

const dateRangeLabels = {
  week: 'Неделя',
  month: 'Месяц',
  all: 'Все',
  custom: 'Свой...',
}

const sourceTypeLabels = {
  telegram: '📱 Telegram',
  website: '🌐 Веб-сайты',
}

export default function NewsFilters({
  categories,
  channels,
  selectedCategories,
  selectedChannels,
  selectedSourceTypes = [],
  availableTags = [],
  selectedTags = [],
  dateRange,
  customDateFrom,
  customDateTo,
  onChange,
  hideDate = false,
  hideHeader = false,
}) {
  const [collapsed, setCollapsed] = useState(true)

  const toggleCategory = (id) => {
    hapticFeedback('light')
    const next = selectedCategories.includes(id)
      ? selectedCategories.filter(c => c !== id)
      : [...selectedCategories, id]
    onChange({ categories: next, channels: selectedChannels, sourceTypes: selectedSourceTypes, tags: selectedTags, dateRange, customDateFrom, customDateTo })
  }

  const selectAllCategories = () => {
    hapticFeedback('light')
    onChange({ categories: [], channels: selectedChannels, sourceTypes: selectedSourceTypes, tags: selectedTags, dateRange, customDateFrom, customDateTo })
  }

  const toggleChannel = (id) => {
    hapticFeedback('light')
    const next = selectedChannels.includes(id)
      ? selectedChannels.filter(c => c !== id)
      : [...selectedChannels, id]
    onChange({ categories: selectedCategories, channels: next, sourceTypes: selectedSourceTypes, tags: selectedTags, dateRange, customDateFrom, customDateTo })
  }

  const selectAllChannels = () => {
    hapticFeedback('light')
    onChange({ categories: selectedCategories, channels: [], sourceTypes: selectedSourceTypes, tags: selectedTags, dateRange, customDateFrom, customDateTo })
  }

  const toggleSourceType = (type) => {
    hapticFeedback('light')
    const next = selectedSourceTypes.includes(type)
      ? selectedSourceTypes.filter(t => t !== type)
      : [...selectedSourceTypes, type]
    onChange({ categories: selectedCategories, channels: selectedChannels, sourceTypes: next, tags: selectedTags, dateRange, customDateFrom, customDateTo })
  }

  const selectAllSourceTypes = () => {
    hapticFeedback('light')
    onChange({ categories: selectedCategories, channels: selectedChannels, sourceTypes: [], tags: selectedTags, dateRange, customDateFrom, customDateTo })
  }

  const toggleTag = (tag) => {
    hapticFeedback('light')
    const next = selectedTags.includes(tag)
      ? selectedTags.filter(t => t !== tag)
      : [...selectedTags, tag]
    onChange({ categories: selectedCategories, channels: selectedChannels, sourceTypes: selectedSourceTypes, tags: next, dateRange, customDateFrom, customDateTo })
  }

  const selectAllTags = () => {
    hapticFeedback('light')
    onChange({ categories: selectedCategories, channels: selectedChannels, sourceTypes: selectedSourceTypes, tags: [], dateRange, customDateFrom, customDateTo })
  }

  const changeDateRange = (value) => {
    hapticFeedback('light')
    onChange({ categories: selectedCategories, channels: selectedChannels, sourceTypes: selectedSourceTypes, tags: selectedTags, dateRange: value, customDateFrom, customDateTo })
  }

  const changeCustomDate = (field, value) => {
    onChange({
      categories: selectedCategories,
      channels: selectedChannels,
      sourceTypes: selectedSourceTypes,
      tags: selectedTags,
      dateRange,
      customDateFrom: field === 'from' ? value : customDateFrom,
      customDateTo: field === 'to' ? value : customDateTo,
    })
  }

  // Сводка для свёрнутого состояния
  const buildSummary = () => {
    const parts = []
    if (selectedCategories.length > 0) {
      const names = categories
        .filter(c => selectedCategories.includes(c.id))
        .map(c => c.name)
      parts.push(names.join(', '))
    }
    if (selectedSourceTypes.length > 0) {
      const names = selectedSourceTypes.map(t => sourceTypeLabels[t] || t)
      parts.push(names.join(', '))
    }
    if (selectedTags.length > 0) {
      parts.push(selectedTags.map(t => t.toUpperCase()).join(', '))
    }
    if (selectedChannels.length > 0) {
      const names = channels
        .filter(c => selectedChannels.includes(c.id))
        .map(c => c.title || `@${c.username}`)
      parts.push(names.join(', '))
    }
    if (!hideDate) {
      parts.push(dateRangeLabels[dateRange] || dateRange)
    }
    return parts.join(' · ')
  }

  return (
    <div style={styles.container}>
      {/* Заголовок */}
      {!hideHeader && (
        <button
          onClick={() => { hapticFeedback('light'); setCollapsed(!collapsed) }}
          style={styles.headerBtn}
        >
          <span style={styles.headerTitle}>Фильтры</span>
          <span style={styles.headerArrow}>{collapsed ? '▼' : '▲'}</span>
        </button>
      )}

      {collapsed ? (
        <div style={styles.summary}>{buildSummary()}</div>
      ) : (
        <div style={styles.content}>
          {/* Категории */}
          <div>
            <div style={styles.sectionLabel}>Категории</div>
            <div style={styles.pillRow}>
              <button
                onClick={selectAllCategories}
                style={selectedCategories.length === 0 ? styles.pillActive : styles.pill}
              >
                Все
              </button>
              {categories.map(cat => {
                const active = selectedCategories.includes(cat.id)
                return (
                  <button
                    key={cat.id}
                    onClick={() => toggleCategory(cat.id)}
                    style={active
                      ? { ...styles.pillBase, backgroundColor: `${cat.color}26`, color: cat.color }
                      : styles.pill
                    }
                  >
                    <span style={{ color: active ? cat.color : '#6b7280' }}>●</span> {cat.name}
                  </button>
                )
              })}
            </div>
          </div>

          {/* Тип источника */}
          <div style={{ marginTop: 10 }}>
            <div style={styles.sectionLabel}>Тип источника</div>
            <div style={styles.pillRow}>
              <button
                onClick={selectAllSourceTypes}
                style={selectedSourceTypes.length === 0 ? styles.pillActive : styles.pill}
              >
                Все
              </button>
              {Object.entries(sourceTypeLabels).map(([type, label]) => {
                const active = selectedSourceTypes.includes(type)
                return (
                  <button
                    key={type}
                    onClick={() => toggleSourceType(type)}
                    style={active ? styles.pillActive : styles.pill}
                  >
                    {label}
                  </button>
                )
              })}
            </div>
          </div>

          {/* Теги */}
          {availableTags.length > 0 && (
            <div style={{ marginTop: 10 }}>
              <div style={styles.sectionLabel}>Теги</div>
              <div style={styles.pillRow}>
                <button
                  onClick={selectAllTags}
                  style={selectedTags.length === 0 ? styles.pillActive : styles.pill}
                >
                  Все
                </button>
                {availableTags.map(tag => {
                  const active = selectedTags.includes(tag)
                  return (
                    <button
                      key={tag}
                      onClick={() => toggleTag(tag)}
                      style={active ? styles.pillActive : styles.pill}
                    >
                      {tag.toUpperCase()}
                    </button>
                  )
                })}
              </div>
            </div>
          )}

          {/* Источники */}
          <div style={{ marginTop: 10 }}>
            <div style={styles.sectionLabel}>Источники</div>
            <div style={styles.pillRow}>
              <button
                onClick={selectAllChannels}
                style={selectedChannels.length === 0 ? styles.pillActive : styles.pill}
              >
                Все
              </button>
              {channels.map(ch => {
                const active = selectedChannels.includes(ch.id)
                return (
                  <button
                    key={ch.id}
                    onClick={() => toggleChannel(ch.id)}
                    style={active ? styles.pillChannelActive : styles.pill}
                  >
                    {ch.title || `@${ch.username}`}
                  </button>
                )
              })}
            </div>
          </div>

          {/* Период */}
          {!hideDate && (
            <div style={{ marginTop: 10 }}>
              <div style={styles.sectionLabel}>Период</div>
              <div style={styles.pillRow}>
                {Object.entries(dateRangeLabels).map(([value, label]) => (
                  <button
                    key={value}
                    onClick={() => changeDateRange(value)}
                    style={dateRange === value ? styles.pillActive : styles.pill}
                  >
                    {label}
                  </button>
                ))}
              </div>
              {dateRange === 'custom' && (
                <div style={styles.dateInputRow}>
                  <input
                    type="date"
                    value={customDateFrom}
                    onChange={e => changeCustomDate('from', e.target.value)}
                    style={styles.dateInput}
                  />
                  <span style={{ color: '#6b7280', fontSize: 13 }}>—</span>
                  <input
                    type="date"
                    value={customDateTo}
                    onChange={e => changeCustomDate('to', e.target.value)}
                    style={styles.dateInput}
                  />
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

const scrollbarHide = {
  scrollbarWidth: 'none',
  msOverflowStyle: 'none',
}

const styles = {
  container: {
    backgroundColor: '#1a1a24',
    borderRadius: 12,
    padding: 12,
  },
  headerBtn: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    width: '100%',
    background: 'none',
    border: 'none',
    cursor: 'pointer',
    padding: 0,
  },
  headerTitle: {
    fontSize: 14,
    fontWeight: 600,
    color: '#fff',
  },
  headerArrow: {
    fontSize: 12,
    color: '#6b7280',
  },
  summary: {
    fontSize: 12,
    color: '#9ca3af',
    marginTop: 6,
  },
  content: {
    marginTop: 10,
  },
  sectionLabel: {
    fontSize: 11,
    color: '#6b7280',
    fontWeight: 600,
    textTransform: 'uppercase',
    marginBottom: 6,
  },
  pillRow: {
    display: 'flex',
    gap: 8,
    overflowX: 'auto',
    whiteSpace: 'nowrap',
    WebkitOverflowScrolling: 'touch',
    ...scrollbarHide,
  },
  pillBase: {
    borderRadius: 16,
    padding: '6px 12px',
    fontSize: 13,
    fontWeight: 500,
    border: 'none',
    cursor: 'pointer',
    flexShrink: 0,
    display: 'inline-flex',
    alignItems: 'center',
    gap: 4,
  },
  pill: {
    borderRadius: 16,
    padding: '6px 12px',
    fontSize: 13,
    fontWeight: 500,
    border: 'none',
    cursor: 'pointer',
    flexShrink: 0,
    display: 'inline-flex',
    alignItems: 'center',
    gap: 4,
    backgroundColor: '#252532',
    color: '#9ca3af',
  },
  pillActive: {
    borderRadius: 16,
    padding: '6px 12px',
    fontSize: 13,
    fontWeight: 500,
    border: 'none',
    cursor: 'pointer',
    flexShrink: 0,
    display: 'inline-flex',
    alignItems: 'center',
    gap: 4,
    backgroundColor: '#3b82f620',
    color: '#3b82f6',
  },
  pillChannelActive: {
    borderRadius: 16,
    padding: '6px 12px',
    fontSize: 13,
    fontWeight: 500,
    border: 'none',
    cursor: 'pointer',
    flexShrink: 0,
    display: 'inline-flex',
    alignItems: 'center',
    gap: 4,
    backgroundColor: '#3b82f620',
    color: '#3b82f6',
  },
  dateInputRow: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    marginTop: 8,
  },
  dateInput: {
    backgroundColor: '#252532',
    border: '1px solid #2a2a3a',
    borderRadius: 8,
    padding: '6px 10px',
    color: '#d1d5db',
    fontSize: 13,
    colorScheme: 'dark',
  },
}
