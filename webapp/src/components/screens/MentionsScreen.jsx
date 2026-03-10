import React, { useState, useEffect, useRef } from 'react'
import { getMentions } from '../../services/mentions'
import { hapticFeedback } from '../../services/telegram'
import MentionCard from '../ui/MentionCard'
import ScrollToTopButton from '../ui/ScrollToTopButton'

const PAGE_SIZE = 10

const SOURCE_FILTERS = [
  { id: 'all',      label: 'Все' },
  { id: 'yandex',   label: 'Яндекс' },
  { id: 'telegram', label: 'TG' },
  { id: 'website',  label: 'Портал' },
]

const SENTIMENT_FILTERS = [
  { id: 'all',      label: 'Все' },
  { id: 'positive', label: 'Позитивные' },
  { id: 'neutral',  label: 'Нейтральные' },
  { id: 'negative', label: 'Негативные' },
]

const DATE_RANGES = [
  { value: 7,        label: '7 дн' },
  { value: 30,       label: '30 дн' },
  { value: 90,       label: '90 дн' },
  { value: 365,      label: 'Год' },
  { value: 'custom', label: 'Период...' },
]

function toDateInputValue(date) {
  return date.toISOString().slice(0, 10)
}

export default function MentionsScreen() {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [hasMore, setHasMore] = useState(false)
  const [offset, setOffset] = useState(0)

  const [selectedSource, setSelectedSource] = useState('all')
  const [selectedSentiment, setSelectedSentiment] = useState('all')
  const [dateRange, setDateRange] = useState(30)

  const today = new Date()
  const [customFrom, setCustomFrom] = useState(() => {
    const d = new Date(); d.setDate(d.getDate() - 30); return toDateInputValue(d)
  })
  const [customTo, setCustomTo] = useState(() => toDateInputValue(today))

  const observerTarget = useRef(null)
  const initialized = useRef(false)

  // Начальная загрузка
  useEffect(() => {
    if (!initialized.current) {
      initialized.current = true
      load(0)
    }
  }, [])

  // Перезагрузка при смене фильтров
  useEffect(() => {
    if (!initialized.current) return
    load(0)
  }, [selectedSource, selectedSentiment, dateRange, customFrom, customTo])

  // Infinite scroll
  useEffect(() => {
    const observer = new IntersectionObserver(
      entries => {
        if (entries[0].isIntersecting && hasMore && !loading && !loadingMore) {
          load(offset + PAGE_SIZE)
        }
      },
      { threshold: 0.1 }
    )
    if (observerTarget.current) observer.observe(observerTarget.current)
    return () => observer.disconnect()
  }, [hasMore, loading, loadingMore, offset])

  async function load(newOffset) {
    try {
      if (newOffset === 0) setLoading(true)
      else setLoadingMore(true)

      let dateTo, dateFrom
      if (dateRange === 'custom') {
        dateFrom = new Date(customFrom + 'T00:00:00')
        dateTo   = new Date(customTo   + 'T23:59:59')
      } else {
        dateTo   = new Date()
        dateFrom = new Date()
        dateFrom.setDate(dateFrom.getDate() - dateRange)
      }

      const sourceTypes = selectedSource !== 'all' ? [selectedSource] : []
      const sentiments  = selectedSentiment !== 'all' ? [selectedSentiment] : []

      const { items: newItems, hasMore: more } = await getMentions({
        limit: PAGE_SIZE,
        offset: newOffset,
        dateFrom: dateFrom.toISOString(),
        dateTo: dateTo.toISOString(),
        sourceTypes,
        sentiments,
      })

      if (newOffset === 0) setItems(newItems)
      else setItems(prev => [...prev, ...newItems])

      setHasMore(more)
      setOffset(newOffset)
    } catch (err) {
      console.error('Load mentions error:', err)
    } finally {
      setLoading(false)
      setLoadingMore(false)
    }
  }

  const handleSourceChange = (id) => {
    hapticFeedback('light')
    setSelectedSource(id)
    setOffset(0)
  }

  const handleSentimentChange = (id) => {
    hapticFeedback('light')
    setSelectedSentiment(id)
    setOffset(0)
  }

  const handleDateRangeChange = (value) => {
    hapticFeedback('light')
    setDateRange(value)
    setOffset(0)
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <h1 style={{ fontSize: 24, fontWeight: 700, margin: 0 }}>Упоминания</h1>

      {/* Фильтры */}
      <div style={styles.filtersBlock}>
        <FilterRow
          label="Источник"
          items={SOURCE_FILTERS}
          active={selectedSource}
          onChange={handleSourceChange}
        />
        <FilterRow
          label="Тональность"
          items={SENTIMENT_FILTERS}
          active={selectedSentiment}
          onChange={handleSentimentChange}
        />
        <FilterRow
          label="Период"
          items={DATE_RANGES.map(r => ({ id: r.value, label: r.label }))}
          active={dateRange}
          onChange={handleDateRangeChange}
        />
        {dateRange === 'custom' && (
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', paddingTop: 2 }}>
            <input
              type="date"
              value={customFrom}
              max={customTo}
              onChange={e => { hapticFeedback('light'); setCustomFrom(e.target.value) }}
              style={styles.dateInput}
            />
            <span style={{ color: '#6b7280', fontSize: 13 }}>—</span>
            <input
              type="date"
              value={customTo}
              min={customFrom}
              max={toDateInputValue(new Date())}
              onChange={e => { hapticFeedback('light'); setCustomTo(e.target.value) }}
              style={styles.dateInput}
            />
          </div>
        )}
      </div>

      {/* Контент */}
      {loading ? (
        <LoadingSkeleton />
      ) : items.length === 0 ? (
        <EmptyState />
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {items.map(item => (
            <MentionCard key={item.id} mention={item} />
          ))}
        </div>
      )}

      {/* Infinite scroll trigger */}
      {hasMore && !loading && (
        <div ref={observerTarget} style={{ height: 20, display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
          {loadingMore && <div style={{ fontSize: 13, color: '#6b7280' }}>Загрузка...</div>}
        </div>
      )}

      <ScrollToTopButton />
    </div>
  )
}

function FilterRow({ label, items, active, onChange }) {
  return (
    <div>
      <div style={styles.filterLabel}>{label}</div>
      <div style={styles.filterRow}>
        {items.map(item => (
          <button
            key={item.id}
            onClick={() => onChange(item.id)}
            style={{
              ...styles.filterBtn,
              backgroundColor: active === item.id ? '#3b82f620' : '#252532',
              color: active === item.id ? '#3b82f6' : '#9ca3af',
            }}
          >
            {item.label}
          </button>
        ))}
      </div>
    </div>
  )
}

function LoadingSkeleton() {
  return [1, 2, 3].map(i => (
    <div key={i} style={{ backgroundColor: '#1a1a24', borderRadius: 12, height: 120, animation: 'pulse 1.5s infinite' }} />
  ))
}

function EmptyState() {
  return (
    <div style={{ textAlign: 'center', padding: 60, color: '#6b7280' }}>
      <div style={{ fontSize: 48, marginBottom: 16 }}>📭</div>
      <div style={{ fontSize: 16, fontWeight: 500 }}>Упоминаний не найдено</div>
      <div style={{ fontSize: 13, marginTop: 8, opacity: 0.7 }}>Попробуйте изменить фильтры или зайдите позже</div>
    </div>
  )
}

const styles = {
  filtersBlock: {
    backgroundColor: '#1a1a24',
    borderRadius: 12,
    padding: 12,
    display: 'flex',
    flexDirection: 'column',
    gap: 10,
  },
  filterLabel: {
    fontSize: 11,
    color: '#6b7280',
    fontWeight: 600,
    textTransform: 'uppercase',
    marginBottom: 6,
  },
  filterRow: {
    display: 'flex',
    gap: 8,
    overflowX: 'auto',
    whiteSpace: 'nowrap',
    WebkitOverflowScrolling: 'touch',
    scrollbarWidth: 'none',
    msOverflowStyle: 'none',
  },
  filterBtn: {
    borderRadius: 16,
    padding: '6px 12px',
    fontSize: 13,
    fontWeight: 500,
    border: 'none',
    cursor: 'pointer',
    flexShrink: 0,
  },
  dateInput: {
    flex: 1,
    padding: '6px 10px',
    fontSize: 13,
    backgroundColor: '#252532',
    border: '1px solid #2a2a3a',
    borderRadius: 8,
    color: '#fff',
    outline: 'none',
    minWidth: 0,
  },
}
