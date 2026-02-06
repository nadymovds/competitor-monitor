import React, { useState, useEffect, useRef } from 'react'
import { getUnifiedFeed, getLastScanDate } from '../../services/feed'
import { getNewsCategories, getNewsChannels } from '../../services/news'
import { hapticFeedback, openLink, openTelegramLink } from '../../services/telegram'
import FeedTypeToggle from '../ui/FeedTypeToggle'
import NewsFilters from '../ui/NewsFilters'
import MultiSelect from '../ui/MultiSelect'
import ScrollToTopButton from '../ui/ScrollToTopButton'
import NewsCard from '../ui/NewsCard'

const CATEGORY_CONFIG = {
  products: { label: 'Продукты', color: '#22c55e' },
  prices: { label: 'Цены', color: '#ef4444' },
  services: { label: 'Условия', color: '#3b82f6' },
  news: { label: 'Новости', color: '#f59e0b' }
}

const PAGE_SIZE = 10

export default function FeedScreen({ user, groups, onNavigateToCompetitor }) {
  // Основное состояние
  const [feedType, setFeedType] = useState('all')
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [hasMore, setHasMore] = useState(false)
  const [offset, setOffset] = useState(0)
  const [dateRange, setDateRange] = useState(30) // в днях, по умолчанию месяц
  const [customDateFrom, setCustomDateFrom] = useState('')
  const [customDateTo, setCustomDateTo] = useState('')
  const [showCustomDatePicker, setShowCustomDatePicker] = useState(false)

  // Фильтры для конкурентов
  const [selectedGroups, setSelectedGroups] = useState([])
  const [activeSourceFilter, setActiveSourceFilter] = useState('all')
  const [activeCategory, setActiveCategory] = useState('all')

  // Фильтры для новостей
  const [newsCategories, setNewsCategories] = useState([])
  const [newsChannels, setNewsChannels] = useState([])
  const [selectedNewsCategories, setSelectedNewsCategories] = useState([])
  const [selectedNewsChannels, setSelectedNewsChannels] = useState([])
  const [selectedNewsSourceTypes, setSelectedNewsSourceTypes] = useState([])

  // Ref для отслеживания скролла
  const observerTarget = useRef(null)
  const initialized = useRef(false)

  // Дата последнего сканирования
  const [lastScanDate, setLastScanDate] = useState(null)

  // Загрузка справочников
  useEffect(() => {
    async function loadReferences() {
      try {
        const [cats, chs, lastScan] = await Promise.all([
          getNewsCategories(),
          getNewsChannels(),
          getLastScanDate()
        ])
        setNewsCategories(cats)
        setNewsChannels(chs)
        setLastScanDate(lastScan)
      } catch (err) {
        console.error('Failed to load references:', err)
      }
    }
    loadReferences()
  }, [])

  // Начальная загрузка ленты
  useEffect(() => {
    if (!initialized.current) {
      initialized.current = true
      loadFeed(0)
    }
  }, [])

  // Реакция на изменение фильтров
  useEffect(() => {
    if (!initialized.current) return
    setOffset(0)
    loadFeed(0)
  }, [
    feedType,
    selectedGroups,
    activeSourceFilter,
    activeCategory,
    selectedNewsCategories,
    selectedNewsChannels,
    selectedNewsSourceTypes,
    dateRange,
    customDateFrom,
    customDateTo,
    showCustomDatePicker
  ])

  // Infinite scroll observer
  useEffect(() => {
    const observer = new IntersectionObserver(
      entries => {
        if (entries[0].isIntersecting && hasMore && !loading && !loadingMore) {
          handleLoadMore()
        }
      },
      { threshold: 0.1 }
    )

    if (observerTarget.current) {
      observer.observe(observerTarget.current)
    }

    return () => observer.disconnect()
  }, [hasMore, loading, loadingMore])

  async function loadFeed(newOffset) {
    try {
      if (newOffset === 0) {
        setLoading(true)
      } else {
        setLoadingMore(true)
      }

      // Период: использует выбранный диапазон дат или пользовательский
      let dateTo, dateFrom
      
      if (showCustomDatePicker && customDateFrom && customDateTo) {
        dateFrom = new Date(customDateFrom)
        dateTo = new Date(customDateTo)
      } else {
        dateTo = new Date()
        dateFrom = new Date()
        dateFrom.setDate(dateFrom.getDate() - dateRange)
      }

      const params = {
        feedType,
        dateFrom: dateFrom.toISOString(),
        dateTo: dateTo.toISOString(),
        limit: PAGE_SIZE,
        offset: newOffset
      }

      // Фильтры конкурентов
      if (feedType === 'competitors') {
        params.groupIds = selectedGroups
        params.sourceType = activeSourceFilter
        params.competitorCategory = activeCategory
      }

      // Фильтры новостей
      if (feedType === 'news') {
        // Если не выбраны конкретные категории, используем все видимые
        params.newsCategories = selectedNewsCategories.length > 0
          ? selectedNewsCategories
          : newsCategories.filter(c => c.is_visible).map(c => c.id)
        params.newsChannels = selectedNewsChannels
        params.newsSourceTypes = selectedNewsSourceTypes
      }

      const { items: newItems, hasMore: more } = await getUnifiedFeed(params)

      if (newOffset === 0) {
        setItems(newItems)
      } else {
        setItems(prev => [...prev, ...newItems])
      }

      setHasMore(more)
      setOffset(newOffset)
    } catch (err) {
      console.error('Load feed error:', err)
    } finally {
      setLoading(false)
      setLoadingMore(false)
    }
  }

  const handleLoadMore = () => {
    if (!hasMore || loading || loadingMore) return
    loadFeed(offset + PAGE_SIZE)
  }

  const handleFeedTypeChange = (type) => {
    setFeedType(type)
    // Сбрасываем фильтры при смене типа
    setSelectedGroups([])
    setActiveSourceFilter('all')
    setActiveCategory('all')
    setSelectedNewsCategories([])
    setSelectedNewsChannels([])
    setSelectedNewsSourceTypes([])
  }

const resetCompetitorFilters = () => {
    hapticFeedback('light')
    setSelectedGroups([])
    setActiveSourceFilter('all')
    setActiveCategory('all')
  }

  const handleNewsFiltersChange = ({ categories, channels, sourceTypes }) => {
    setSelectedNewsCategories(categories || [])
    setSelectedNewsChannels(channels || [])
    setSelectedNewsSourceTypes(sourceTypes || [])
  }

  // Подсчёт по категориям для конкурентов
  const getCategoryCounts = () => {
    if (feedType !== 'competitors') return {}
    const counts = { all: items.length }
    for (const cat of Object.keys(CATEGORY_CONFIG)) {
      counts[cat] = items.filter(item => item.category === cat).length
    }
    return counts
  }

  // Подсчёт по источникам для конкурентов
  const getSourceCounts = () => {
    if (feedType !== 'competitors') return {}
    return {
      all: items.length,
      website: items.filter(item => item.source_type === 'website').length,
      telegram: items.filter(item => item.source_type === 'telegram').length
    }
  }

  const categoryCounts = getCategoryCounts()
  const sourceCounts = getSourceCounts()
  const visibleNewsCategories = newsCategories.filter(c => c.is_visible)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div>
        <h1 style={{ fontSize: 24, fontWeight: 700, margin: 0, marginBottom: 4 }}>Лента новостей</h1>
        {lastScanDate && (
          <div style={{ fontSize: 12, color: '#6b7280' }}>
            Последнее сканирование: {formatDateTime(lastScanDate)}
          </div>
        )}
      </div>

      {/* Переключатель типа */}
      <FeedTypeToggle feedType={feedType} onChange={handleFeedTypeChange} />

      {/* Фильтр по периоду дат */}
      <div style={{ backgroundColor: '#1a1a24', borderRadius: 12, padding: 12, display: 'flex', flexDirection: 'column', gap: 10 }}>
        <div>
          <div style={{ fontSize: 11, color: '#6b7280', fontWeight: 600, textTransform: 'uppercase', marginBottom: 6 }}>Период</div>
          <div style={{ display: 'flex', gap: 8, overflowX: 'auto', whiteSpace: 'nowrap', WebkitOverflowScrolling: 'touch', scrollbarWidth: 'none', msOverflowStyle: 'none' }}>
            {[
              { value: 7, label: 'Неделя' },
              { value: 30, label: 'Месяц' },
              { value: 90, label: 'Квартал' },
              { value: 365, label: 'Год' },
              { value: 'custom', label: 'Свой...' }
            ].map(range => (
              <button
                key={range.value}
                onClick={() => {
                  hapticFeedback('light')
                  if (range.value === 'custom') {
                    setShowCustomDatePicker(!showCustomDatePicker)
                  } else {
                    setDateRange(range.value)
                    setShowCustomDatePicker(false)
                  }
                }}
                style={{
                  borderRadius: 16, padding: '6px 12px', fontSize: 13, fontWeight: 500,
                  border: 'none', cursor: 'pointer', flexShrink: 0, display: 'inline-flex', alignItems: 'center', gap: 4,
                  backgroundColor: (range.value === 'custom' && showCustomDatePicker) || (range.value !== 'custom' && !showCustomDatePicker && dateRange === range.value) ? '#3b82f620' : '#252532',
                  color: (range.value === 'custom' && showCustomDatePicker) || (range.value !== 'custom' && !showCustomDatePicker && dateRange === range.value) ? '#3b82f6' : '#9ca3af'
                }}
              >
                {range.label}
              </button>
            ))}
          </div>
          {showCustomDatePicker && (
            <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginTop: 10 }}>
              <input
                type="date"
                value={customDateFrom}
                onChange={(e) => setCustomDateFrom(e.target.value)}
                style={{
                  flex: 1, padding: '8px 12px', fontSize: 13, borderRadius: 8,
                  border: '1px solid #3b3b45', backgroundColor: '#252532', color: '#e5e7eb',
                  fontFamily: 'inherit'
                }}
              />
              <span style={{ color: '#6b7280' }}>—</span>
              <input
                type="date"
                value={customDateTo}
                onChange={(e) => setCustomDateTo(e.target.value)}
                style={{
                  flex: 1, padding: '8px 12px', fontSize: 13, borderRadius: 8,
                  border: '1px solid #3b3b45', backgroundColor: '#252532', color: '#e5e7eb',
                  fontFamily: 'inherit'
                }}
              />
            </div>
          )}
        </div>
      </div>

      {/* Фильтры для режима "Конкуренты" */}
      {feedType === 'competitors' && (
        <div style={{ backgroundColor: '#1a1a24', borderRadius: 12, padding: 12, display: 'flex', flexDirection: 'column', gap: 10 }}>
          {/* Фильтр по источникам */}
          <div>
            <div style={{ fontSize: 11, color: '#6b7280', fontWeight: 600, textTransform: 'uppercase', marginBottom: 6 }}>Источник</div>
            <div style={{ display: 'flex', gap: 8, overflowX: 'auto', whiteSpace: 'nowrap', WebkitOverflowScrolling: 'touch', scrollbarWidth: 'none', msOverflowStyle: 'none' }}>
              {[
                { id: 'all', label: 'Все источники' },
                { id: 'website', label: '🌐 Web' },
                { id: 'telegram', label: '📢 TG' }
              ].map(src => (
                <button
                  key={src.id}
                  onClick={() => {
                    hapticFeedback('light')
                    setActiveSourceFilter(src.id)
                  }}
                  style={{
                    borderRadius: 16, padding: '6px 12px', fontSize: 13, fontWeight: 500,
                    border: 'none', cursor: 'pointer', flexShrink: 0, display: 'inline-flex', alignItems: 'center', gap: 4,
                    backgroundColor: activeSourceFilter === src.id ? '#3b82f620' : '#252532',
                    color: activeSourceFilter === src.id ? '#3b82f6' : '#9ca3af'
                  }}
                >
                  {src.label}
                  {sourceCounts[src.id] !== undefined && (
                    <span style={{ opacity: 0.7 }}>({sourceCounts[src.id]})</span>
                  )}
                </button>
              ))}
            </div>
          </div>

          {/* Фильтр по категориям */}
          <div>
            <div style={{ fontSize: 11, color: '#6b7280', fontWeight: 600, textTransform: 'uppercase', marginBottom: 6 }}>Категория</div>
            <div style={{ display: 'flex', gap: 8, overflowX: 'auto', whiteSpace: 'nowrap', WebkitOverflowScrolling: 'touch', scrollbarWidth: 'none', msOverflowStyle: 'none' }}>
              {Object.entries(categoryCounts).map(([id, count]) => (
                <button
                  key={id}
                  onClick={() => {
                    hapticFeedback('light')
                    setActiveCategory(id)
                  }}
                  style={{
                    borderRadius: 16, padding: '6px 12px', fontSize: 13, fontWeight: 500,
                    border: 'none', cursor: 'pointer', flexShrink: 0, display: 'inline-flex', alignItems: 'center', gap: 4,
                    backgroundColor: activeCategory === id ? '#3b82f620' : '#252532',
                    color: activeCategory === id ? '#3b82f6' : '#9ca3af'
                  }}
                >
                  {id === 'all' ? <><span style={{ color: '#3b82f6' }}>●</span> Все</> : <><span style={{ color: CATEGORY_CONFIG[id]?.color || '#6b7280' }}>●</span> {CATEGORY_CONFIG[id]?.label || id}</>}
                  <span style={{ opacity: 0.7 }}>({count})</span>
                </button>
              ))}
            </div>
          </div>

          {/* Фильтр по группам */}
          <div style={{ position: 'relative', zIndex: 10 }}>
            <div style={{ fontSize: 11, color: '#6b7280', fontWeight: 600, textTransform: 'uppercase', marginBottom: 6, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span>Группы</span>
              {(selectedGroups.length > 0 || activeSourceFilter !== 'all' || activeCategory !== 'all') && (
                <button
                  onClick={resetCompetitorFilters}
                  style={{ fontSize: 11, color: '#3b82f6', background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}
                >
                  Сбросить
                </button>
              )}
            </div>
            <MultiSelect
              options={groups}
              selectedIds={selectedGroups}
              onChange={setSelectedGroups}
              placeholder="Все группы"
            />
          </div>
        </div>
      )}

      {/* Фильтры для режима "Новости" */}
      {feedType === 'news' && (
        <NewsFilters
          categories={visibleNewsCategories}
          channels={newsChannels}
          selectedCategories={selectedNewsCategories}
          selectedChannels={selectedNewsChannels}
          selectedSourceTypes={selectedNewsSourceTypes}
          dateRange="week"
          onChange={handleNewsFiltersChange}
          hideDate={true}
          hideHeader={false}
        />
      )}

      {/* Список элементов */}
      {loading ? (
        <LoadingSkeleton />
      ) : items.length === 0 ? (
        <EmptyState feedType={feedType} />
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {items.map(item => (
            <FeedItem
              key={item.id}
              item={item}
              onNavigateToCompetitor={onNavigateToCompetitor}
            />
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

// Компонент элемента ленты
function FeedItem({ item, onNavigateToCompetitor }) {
  const isCompetitor = item.type === 'competitor_change' || item.type === 'competitor_tg'
  const isNews = item.type === 'industry_news'
  const isTelegram = item.source_type === 'telegram'

  if (isCompetitor) {
    return <CompetitorFeedItem item={item} onNavigate={() => onNavigateToCompetitor(item.competitor_id)} />
  }

  if (isNews) {
    return <NewsFeedItem item={item} />
  }

  return null
}

// Компонент изменения конкурента
function CompetitorFeedItem({ item, onNavigate }) {
  const typeColors = {
    products: '#22c55e',
    services: '#3b82f6',
    news: '#f59e0b',
    prices: '#ef4444'
  }

  const typeLabels = {
    products: 'Продукт',
    services: 'Условия',
    news: 'Новость',
    prices: 'Цена'
  }

  const category = item.category || 'news'
  const isTelegram = item.source_type === 'telegram'
  const linkUrl = isTelegram ? item.post_url : item.competitor_url

  return (
    <div style={{ backgroundColor: '#1a1a24', borderRadius: 12, padding: 14 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 10 }}>
        <div style={{ flex: 1 }}>
          <button
            onClick={onNavigate}
            style={{
              fontSize: 15, fontWeight: 600, color: '#fff', background: 'none', border: 'none',
              padding: 0, textAlign: 'left', cursor: 'pointer',
              textDecoration: 'underline', textDecorationColor: 'rgba(255,255,255,0.3)'
            }}
          >
            {item.competitor_name || 'Неизвестный'}
          </button>
          <button
            onClick={() => isTelegram ? openTelegramLink(linkUrl) : openLink(ensureProtocol(linkUrl))}
            style={{
              display: 'block', fontSize: 12, color: '#3b82f6', background: 'none',
              border: 'none', padding: 0, marginTop: 4, cursor: 'pointer'
            }}
          >
            {isTelegram ? `📢 @${item.channel_username}` : `🌐 ${item.competitor_url}`}
          </button>
          <div style={{ fontSize: 11, color: '#6b7280', marginTop: 4 }}>
            {formatDateTime(item.detected_at)}
          </div>
        </div>
        <div style={{ display: 'flex', gap: 6, alignItems: 'flex-start', flexShrink: 0, marginLeft: 12 }}>
          <span style={{
            fontSize: 10, fontWeight: 500, padding: '4px 8px', borderRadius: 6,
            backgroundColor: isTelegram ? '#8b5cf620' : '#6b728020',
            color: isTelegram ? '#8b5cf6' : '#6b7280'
          }}>
            {isTelegram ? 'TG' : 'Web'}
          </span>
          <span style={{
            fontSize: 10, fontWeight: 500, padding: '4px 8px', borderRadius: 6,
            backgroundColor: (typeColors[category] || '#6b7280') + '20',
            color: typeColors[category] || '#6b7280'
          }}>
            {typeLabels[category] || category}
          </span>
        </div>
      </div>

      <div style={{ fontSize: 14, fontWeight: 400, color: '#e5e7eb', lineHeight: 1.6, marginBottom: 10 }}>
        {item.summary}
      </div>

      {item.tags?.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 8 }}>
          {item.tags.map((tag, i) => (
            <span
              key={i}
              style={{
                fontSize: 11, color: '#9ca3af', backgroundColor: '#252532',
                padding: '4px 8px', borderRadius: 6
              }}
            >
              {tag}
            </span>
          ))}
        </div>
      )}

      {item.groups?.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
          {item.groups.map(g => (
            <span
              key={g.id}
              style={{
                fontSize: 11, padding: '4px 8px', borderRadius: 6,
                backgroundColor: g.color + '20', color: g.color
              }}
            >
              {g.name}
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

// Компонент новости отрасли (использует NewsCard)
function NewsFeedItem({ item }) {
  const post = {
    id: item.id,
    title: item.title,
    content_text: item.content_text,
    summary: item.summary,
    post_url: item.post_url,
    post_date: item.post_date || item.detected_at,
    source_type: item.source_type,
    channel: item.channel,
    categories: item.categories || [],
    has_photo: item.has_photo,
    has_video: item.has_video,
    has_document: item.has_document,
    views_count: item.views_count
  }

  return <NewsCard post={post} />
}

function LoadingSkeleton() {
  return [1, 2, 3].map(i => (
    <div
      key={i}
      style={{
        backgroundColor: '#1a1a24',
        borderRadius: 12,
        height: 180,
        animation: 'pulse 1.5s infinite'
      }}
    />
  ))
}

function EmptyState({ feedType }) {
  const messages = {
    all: 'Нет обновлений в выбранном периоде',
    competitors: 'Нет изменений у конкурентов',
    news: 'Новостей не найдено'
  }

  return (
    <div style={{ textAlign: 'center', padding: 60, color: '#6b7280' }}>
      <div style={{ fontSize: 48, marginBottom: 16 }}>📭</div>
      <div style={{ fontSize: 16, fontWeight: 500 }}>{messages[feedType]}</div>
      <div style={{ fontSize: 13, marginTop: 8, opacity: 0.7 }}>
        Попробуйте изменить фильтры или зайдите позже
      </div>
    </div>
  )
}

function formatDateTime(dateStr) {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  const now = new Date()
  const diff = now - date
  const hours = Math.floor(diff / (1000 * 60 * 60))
  const days = Math.floor(hours / 24)

  if (days === 0) {
    if (hours === 0) {
      const mins = Math.floor(diff / (1000 * 60))
      return mins <= 1 ? 'только что' : `${mins} мин назад`
    }
    return `${hours} ч назад`
  }

  if (days === 1) return 'вчера'
  if (days < 7) return `${days} дн назад`

  return date.toLocaleDateString('ru-RU', {
    day: 'numeric',
    month: 'short',
    year: date.getFullYear() !== now.getFullYear() ? 'numeric' : undefined
  })
}

function ensureProtocol(url) {
  if (!url) return url
  if (url.startsWith('http://') || url.startsWith('https://')) return url
  return `https://${url}`
}
