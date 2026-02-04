import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import FeedTypeToggle from '../ui/FeedTypeToggle'
import ScrollToTopButton from '../ui/ScrollToTopButton'
import CategoryBadge from '../ui/CategoryBadge'
import { getUnifiedFeed } from '../../services/feed'
import { getNewsCategories, getNewsChannels } from '../../services/news'
import { hapticFeedback, openLink, openTelegramLink } from '../../services/telegram'

const PAGE_SIZE = 10
const MAX_WEEKS = 8
const COMPETITOR_CATEGORIES = [
  { id: 'all', label: 'Все' },
  { id: 'products', label: 'Продукты' },
  { id: 'prices', label: 'Цены' },
  { id: 'services', label: 'Условия' },
  { id: 'news', label: 'Новости' },
]
const COMPETITOR_CATEGORY_COLORS = {
  products: '#22c55e',
  prices: '#ef4444',
  services: '#3b82f6',
  news: '#f59e0b',
}
const SOURCE_OPTIONS = [
  { id: 'all', label: 'Все' },
  { id: 'website', label: 'Web' },
  { id: 'telegram', label: 'TG' },
]
const NEWS_SOURCE_OPTIONS = [
  { id: 'telegram', label: 'Telegram' },
  { id: 'website', label: 'Web' },
]

function getWeekRange(weekIndex) {
  const now = new Date()
  const end = new Date(now)
  if (weekIndex > 0) {
    end.setHours(23, 59, 59, 999)
    end.setDate(end.getDate() - weekIndex * 7)
  }
  const start = new Date(end)
  start.setDate(start.getDate() - 6)
  start.setHours(0, 0, 0, 0)
  return {
    dateFrom: start.toISOString(),
    dateTo: (weekIndex === 0 ? now : end).toISOString(),
  }
}

function formatDateTime(isoString) {
  if (!isoString) return ''
  const date = new Date(isoString)
  return date.toLocaleString('ru-RU', {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function formatNewsMeta(item) {
  const parts = []
  const sourceType = item.sourceType
  if (item.channel) {
    if (sourceType === 'website') {
      if (item.channel.title) parts.push(`🌐 ${item.channel.title}`)
      else parts.push('🌐')
    } else if (item.channel.username) {
      parts.push(`📣 @${item.channel.username}`)
    } else if (item.channel.title) {
      parts.push(`📣 ${item.channel.title}`)
    }
  }
  if (item.timestamp) parts.push(formatDateTime(item.timestamp))
  if (item.stats?.views) parts.push(`${item.stats.views} 👁`)
  const mediaHints = []
  if (item.stats?.hasPhoto) mediaHints.push('📷')
  if (item.stats?.hasVideo) mediaHints.push('🎥')
  if (item.stats?.hasDocument) mediaHints.push('📎')
  if (mediaHints.length > 0) parts.push(mediaHints.join(' '))
  return parts.join(' · ')
}

export default function FeedScreen({ groups = [], onNavigateToCompetitor }) {
  const [feedType, setFeedType] = useState('all')
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [hasMore, setHasMore] = useState(true)
  const [weeksState, setWeeksState] = useState([{ index: 0, offset: 0, hasMore: true }])
  const [newsCategories, setNewsCategories] = useState([])
  const [newsChannels, setNewsChannels] = useState([])
  const [defaultNewsCategoryIds, setDefaultNewsCategoryIds] = useState([])
  const [metaLoaded, setMetaLoaded] = useState(false)

  const [selectedGroups, setSelectedGroups] = useState([])
  const [activeSourceFilter, setActiveSourceFilter] = useState('all')
  const [activeCategory, setActiveCategory] = useState('all')

  const [selectedCategories, setSelectedCategories] = useState([])
  const [selectedChannels, setSelectedChannels] = useState([])
  const [newsSourceTypes, setNewsSourceTypes] = useState([])

  const sentinelRef = useRef(null)
  const fetchingRef = useRef(false)

  useEffect(() => {
    async function loadMeta() {
      try {
        const [cats, chs] = await Promise.all([getNewsCategories(), getNewsChannels()])
        setNewsCategories(cats)
        setNewsChannels(chs)
        const visible = cats.filter(cat => cat.is_visible !== false).map(cat => cat.id)
        setDefaultNewsCategoryIds(visible)
      } catch (err) {
        console.error('FeedScreen meta error:', err)
      } finally {
        setMetaLoaded(true)
      }
    }
    loadMeta()
  }, [])

  const competitorFilterKey = useMemo(() => {
    const groupsKey = [...selectedGroups].sort((a, b) => a - b)
    return JSON.stringify([groupsKey, activeSourceFilter, activeCategory])
  }, [selectedGroups, activeSourceFilter, activeCategory])

  const newsFilterKey = useMemo(() => {
    const catsKey = [...selectedCategories].sort((a, b) => a - b)
    const channelsKey = [...selectedChannels].sort((a, b) => a - b)
    const sourcesKey = [...newsSourceTypes].sort()
    const defaultsKey = [...defaultNewsCategoryIds].sort((a, b) => a - b)
    return JSON.stringify([catsKey, channelsKey, sourcesKey, defaultsKey])
  }, [selectedCategories, selectedChannels, newsSourceTypes, defaultNewsCategoryIds])

  const loadKey = useMemo(() => {
    if (feedType === 'competitors') return `competitors|${competitorFilterKey}`
    if (feedType === 'news') return `news|${newsFilterKey}`
    return `all|${competitorFilterKey}|${newsFilterKey}`
  }, [feedType, competitorFilterKey, newsFilterKey])

  const canLoad = feedType === 'competitors' || metaLoaded

  const loadMore = useCallback(
    async (isInitial = false, presetWeeks = null) => {
      if (fetchingRef.current) return
      fetchingRef.current = true
      if (!isInitial) setLoadingMore(true)

      let workingWeeks = presetWeeks ? presetWeeks.map(week => ({ ...week })) : weeksState.map(week => ({ ...week }))
      let collected = []
      let attempts = 0

      while (attempts < MAX_WEEKS && workingWeeks.length > 0) {
        const current = workingWeeks[workingWeeks.length - 1]
        if (!current.hasMore) {
          if (current.index + 1 >= MAX_WEEKS) break
          workingWeeks.push({ index: current.index + 1, offset: 0, hasMore: true })
          attempts += 1
          continue
        }

        const { dateFrom, dateTo } = getWeekRange(current.index)

        try {
          const response = await getUnifiedFeed({
            feedType,
            dateFrom,
            dateTo,
            limit: PAGE_SIZE,
            offset: current.offset,
            groupIds: selectedGroups,
            sourceType: activeSourceFilter,
            competitorCategory: activeCategory,
            newsCategories: selectedCategories,
            newsChannels: selectedChannels,
            newsSourceTypes,
            defaultNewsCategoryIds,
          })

          if (response.items.length > 0) {
            collected = response.items
            workingWeeks[workingWeeks.length - 1] = {
              ...current,
              offset: current.offset + response.items.length,
              hasMore: response.hasMore,
            }
            break
          }

          workingWeeks[workingWeeks.length - 1] = { ...current, hasMore: false }
          if (current.index + 1 >= MAX_WEEKS) break
          workingWeeks.push({ index: current.index + 1, offset: 0, hasMore: true })
        } catch (err) {
          console.error('FeedScreen load error:', err)
          break
        }

        attempts += 1
      }

      setWeeksState(workingWeeks)
      if (collected.length > 0) {
        if (isInitial && presetWeeks) {
          setItems(collected)
        } else {
          setItems(prev => [...prev, ...collected])
        }
      } else if (isInitial && presetWeeks) {
        setItems([])
      }

      const maxWeekIndex = workingWeeks[workingWeeks.length - 1]?.index ?? 0
      const morePossible = workingWeeks.some(week => week.hasMore) || maxWeekIndex < MAX_WEEKS - 1
      setHasMore(morePossible)

      setLoading(false)
      setLoadingMore(false)
      fetchingRef.current = false
    },
    [weeksState, feedType, selectedGroups, activeSourceFilter, activeCategory, selectedCategories, selectedChannels, newsSourceTypes, defaultNewsCategoryIds]
  )

  useEffect(() => {
    if (!canLoad) return
    const initialWeeks = [{ index: 0, offset: 0, hasMore: true }]
    setWeeksState(initialWeeks)
    setItems([])
    setHasMore(true)
    setLoading(true)
    fetchingRef.current = false
    loadMore(true, initialWeeks)
  }, [canLoad, loadKey, loadMore])

  useEffect(() => {
    if (!hasMore) return
    const node = sentinelRef.current
    if (!node) return

    const observer = new IntersectionObserver(entries => {
      const [entry] = entries
      if (entry.isIntersecting && !loading && !loadingMore) {
        loadMore()
      }
    }, { rootMargin: '240px' })

    observer.observe(node)
    return () => observer.disconnect()
  }, [hasMore, loading, loadingMore, loadMore])

  const visibleNewsCategories = useMemo(
    () => newsCategories.filter(cat => cat.is_visible !== false),
    [newsCategories]
  )

  const sortedChannels = useMemo(
    () => [...newsChannels].sort((a, b) => (a.title || '').localeCompare(b.title || '')),
    [newsChannels]
  )

  const toggleGroup = (id) => {
    hapticFeedback('light')
    setSelectedGroups(prev => prev.includes(id) ? prev.filter(item => item !== id) : [...prev, id])
  }

  const toggleNewsCategory = (id) => {
    hapticFeedback('light')
    setSelectedCategories(prev => prev.includes(id) ? prev.filter(item => item !== id) : [...prev, id])
  }

  const toggleNewsChannel = (id) => {
    hapticFeedback('light')
    setSelectedChannels(prev => prev.includes(id) ? prev.filter(item => item !== id) : [...prev, id])
  }

  const toggleNewsSourceType = (id) => {
    hapticFeedback('light')
    setNewsSourceTypes(prev => prev.includes(id) ? prev.filter(item => item !== id) : [...prev, id])
  }

  const resetCompetitorFilters = () => {
    hapticFeedback('light')
    setSelectedGroups([])
    setActiveSourceFilter('all')
    setActiveCategory('all')
  }

  const resetNewsFilters = () => {
    hapticFeedback('light')
    setSelectedCategories([])
    setSelectedChannels([])
    setNewsSourceTypes([])
  }

  const renderCompetitorFilters = () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{ fontSize: 13, color: '#9ca3af' }}>Фильтр по группам</span>
        {(selectedGroups.length > 0 || activeSourceFilter !== 'all' || activeCategory !== 'all') && (
          <button onClick={resetCompetitorFilters} style={styles.resetButton}>Сбросить</button>
        )}
      </div>
      <div style={styles.chipsRow}>
        {groups.map(group => {
          const active = selectedGroups.includes(group.id)
          return (
            <button
              key={group.id}
              type="button"
              onClick={() => toggleGroup(group.id)}
              style={{
                ...styles.groupChip,
                backgroundColor: active ? `${group.color}26` : '#1a1a24',
                borderColor: active ? group.color : 'transparent',
                color: '#fff',
              }}
            >
              <span style={{ width: 8, height: 8, borderRadius: '50%', backgroundColor: group.color, display: 'inline-block' }} />
              {group.name}
            </button>
          )
        })}
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <span style={{ fontSize: 13, color: '#9ca3af' }}>Источник</span>
        <div style={styles.chipsRow}>
          {SOURCE_OPTIONS.map(option => {
            const active = option.id === activeSourceFilter
            return (
              <button
                key={option.id}
                type="button"
                onClick={() => { hapticFeedback('light'); setActiveSourceFilter(option.id) }}
                style={{
                  ...styles.filterChip,
                  backgroundColor: active ? '#3b82f6' : '#1a1a24',
                  color: active ? '#fff' : '#9ca3af',
                }}
              >
                {option.label}
              </button>
            )
          })}
        </div>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <span style={{ fontSize: 13, color: '#9ca3af' }}>Категория</span>
        <div style={styles.chipsRow}>
          {COMPETITOR_CATEGORIES.map(option => {
            const active = option.id === activeCategory
            return (
              <button
                key={option.id}
                type="button"
                onClick={() => { hapticFeedback('light'); setActiveCategory(option.id) }}
                style={{
                  ...styles.filterChip,
                  backgroundColor: active ? '#3b82f6' : '#1a1a24',
                  color: active ? '#fff' : '#9ca3af',
                }}
              >
                {option.label}
              </button>
            )
          })}
        </div>
      </div>
    </div>
  )

  const renderNewsFilters = () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{ fontSize: 13, color: '#9ca3af' }}>Категории</span>
        {(selectedCategories.length > 0 || selectedChannels.length > 0 || newsSourceTypes.length > 0) && (
          <button onClick={resetNewsFilters} style={styles.resetButton}>Сбросить</button>
        )}
      </div>
      <div style={styles.chipsRow}>
        {visibleNewsCategories.map(category => {
          const active = selectedCategories.includes(category.id)
          return (
            <button
              key={category.id}
              type="button"
              onClick={() => toggleNewsCategory(category.id)}
              style={{
                ...styles.filterChip,
                backgroundColor: active ? `${category.color}26` : '#1a1a24',
                color: active ? category.color : '#9ca3af',
                borderColor: active ? category.color : 'transparent',
              }}
            >
              {category.name}
            </button>
          )
        })}
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <span style={{ fontSize: 13, color: '#9ca3af' }}>Каналы</span>
        <div style={styles.chipsRow}>
          {sortedChannels.map(channel => {
            const active = selectedChannels.includes(channel.id)
            return (
              <button
                key={channel.id}
                type="button"
                onClick={() => toggleNewsChannel(channel.id)}
                style={{
                  ...styles.filterChip,
                  backgroundColor: active ? '#3b82f6' : '#1a1a24',
                  color: active ? '#fff' : '#9ca3af',
                }}
              >
                {channel.title || channel.username || 'Без названия'}
              </button>
            )
          })}
        </div>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <span style={{ fontSize: 13, color: '#9ca3af' }}>Источник</span>
        <div style={styles.chipsRow}>
          {NEWS_SOURCE_OPTIONS.map(option => {
            const active = newsSourceTypes.includes(option.id)
            return (
              <button
                key={option.id}
                type="button"
                onClick={() => toggleNewsSourceType(option.id)}
                style={{
                  ...styles.filterChip,
                  backgroundColor: active ? '#3b82f6' : '#1a1a24',
                  color: active ? '#fff' : '#9ca3af',
                }}
              >
                {option.label}
              </button>
            )
          })}
        </div>
      </div>
    </div>
  )

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
      <header style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h1 style={{ margin: 0, fontSize: 24, fontWeight: 700 }}>Лента</h1>
          <FeedTypeToggle value={feedType} onChange={setFeedType} />
        </div>
        <span style={{ fontSize: 13, color: '#9ca3af' }}>Последние 7 дней, следующие недели подгружаются автоматически</span>
      </header>

      {feedType === 'competitors' && renderCompetitorFilters()}
      {feedType === 'news' && renderNewsFilters()}
      {feedType === 'all' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div style={{ backgroundColor: '#151521', borderRadius: 12, padding: 12, border: '1px solid #2a2a3a' }}>
            <div style={{ fontSize: 13, color: '#9ca3af' }}>Фильтры конкурентов</div>
            {renderCompetitorFilters()}
          </div>
          <div style={{ backgroundColor: '#151521', borderRadius: 12, padding: 12, border: '1px solid #2a2a3a' }}>
            <div style={{ fontSize: 13, color: '#9ca3af' }}>Фильтры новостей</div>
            {renderNewsFilters()}
          </div>
        </div>
      )}

      {loading ? (
        <LoadingState />
      ) : items.length === 0 ? (
        <EmptyState />
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          {items.map(item => (
            <FeedItemCard
              key={item.id}
              item={item}
              onNavigateToCompetitor={onNavigateToCompetitor}
            />
          ))}
        </div>
      )}

      <div ref={sentinelRef} style={{ height: 1, width: '100%' }} />
      {loadingMore && <LoadingMoreIndicator />}
      <ScrollToTopButton />
    </div>
  )
}

function FeedItemCard({ item, onNavigateToCompetitor }) {
  if (item.feedSource === 'competitors') {
    return <CompetitorFeedCard item={item} onNavigateToCompetitor={onNavigateToCompetitor} />
  }
  return <NewsFeedCard item={item} />
}

function CompetitorFeedCard({ item, onNavigateToCompetitor }) {
  const categoryColor = COMPETITOR_CATEGORY_COLORS[item.category] || '#6b7280'
  return (
    <div style={styles.card}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <button
            type="button"
            onClick={() => {
              hapticFeedback('light')
              onNavigateToCompetitor?.(item.competitor?.id, 'feed')
            }}
            style={styles.competitorLink}
          >
            {item.competitor?.name || 'Неизвестный конкурент'}
          </button>
          <span style={{ fontSize: 12, color: '#6b7280' }}>{formatDateTime(item.timestamp)}</span>
        </div>
        <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          <span style={{...styles.badge, backgroundColor: item.sourceType === 'telegram' ? '#8b5cf620' : '#1a1a24', color: item.sourceType === 'telegram' ? '#8b5cf6' : '#9ca3af'}}>
            {item.sourceType === 'telegram' ? 'TG' : 'Web'}
          </span>
          <span style={{...styles.badge, backgroundColor: `${categoryColor}26`, color: categoryColor}}>
            {COMPETITOR_CATEGORIES.find(cat => cat.id === item.category)?.label || '—'}
          </span>
        </div>
      </div>

      <div style={{ marginTop: 10, fontSize: 14, color: '#d1d5db', lineHeight: 1.5 }}>
        {item.summary || 'Без описания'}
      </div>

      {item.scannedUrl && item.sourceType === 'website' && (
        <button
          type="button"
          onClick={() => { hapticFeedback('light'); openLink(ensureProtocol(item.scannedUrl)) }}
          style={styles.subtleLink}
        >
          🔗 {item.scannedUrl}
        </button>
      )}

      {item.postUrl && item.sourceType === 'telegram' && (
        <button
          type="button"
          onClick={() => { hapticFeedback('light'); openTelegramLink(item.postUrl) }}
          style={styles.subtleLink}
        >
          📢 @{item.channelUsername || 'канал'}
        </button>
      )}

      {item.tags?.length > 0 && (
        <div style={styles.tagRow}>
          {item.tags.map(tag => (
            <span key={tag} style={styles.tag}>#{tag}</span>
          ))}
        </div>
      )}

      {item.groups?.length > 0 && (
        <div style={styles.groupRow}>
          {item.groups.map(group => (
            <span key={group.id} style={{...styles.groupBadge, color: group.color, backgroundColor: `${group.color}26`}}>
              {group.name}
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

function NewsFeedCard({ item }) {
  const meta = formatNewsMeta(item)
  return (
    <div style={styles.card}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        <div style={{ fontSize: 15, fontWeight: 600, color: '#fff' }}>{item.title}</div>
        <div style={{ fontSize: 13, color: '#d1d5db', lineHeight: 1.6 }}>{item.summary}</div>
      </div>

      <div style={{ marginTop: 12, display: 'flex', flexDirection: 'column', gap: 8 }}>
        {meta && <span style={{ fontSize: 12, color: '#6b7280' }}>{meta}</span>}
        {item.categories?.length > 0 && (
          <div style={styles.tagRow}>
            {item.categories.map(category => (
              <CategoryBadge key={category.id} name={category.name} color={category.color || '#6b7280'} size="small" />
            ))}
          </div>
        )}
        {item.postUrl && (
          <button
            type="button"
            onClick={() => { hapticFeedback('light'); openLink(item.postUrl) }}
            style={styles.subtleLink}
          >
            Оригинал ↗
          </button>
        )}
      </div>
    </div>
  )
}

function LoadingState() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {[1, 2, 3].map(i => (
        <div key={i} style={styles.skeleton} />
      ))}
    </div>
  )
}

function LoadingMoreIndicator() {
  return (
    <div style={{ textAlign: 'center', color: '#6b7280', fontSize: 13 }}>Загрузка...</div>
  )
}

function EmptyState() {
  return (
    <div style={styles.emptyState}>
      <div style={{ fontSize: 42 }}>📭</div>
      <div style={{ fontSize: 16, fontWeight: 600 }}>Свежих обновлений нет</div>
      <div style={{ fontSize: 13, color: '#9ca3af' }}>Попробуйте изменить фильтры или дождитесь новых событий</div>
    </div>
  )
}

function ensureProtocol(url) {
  if (!url) return url
  if (url.startsWith('http://') || url.startsWith('https://')) return url
  return `https://${url}`
}

const styles = {
  card: {
    backgroundColor: '#151521',
    borderRadius: 14,
    border: '1px solid #2a2a3a',
    padding: 16,
    display: 'flex',
    flexDirection: 'column',
    gap: 10,
  },
  badge: {
    fontSize: 11,
    fontWeight: 600,
    padding: '4px 8px',
    borderRadius: 8,
  },
  groupChip: {
    display: 'flex',
    alignItems: 'center',
    gap: 6,
    padding: '6px 12px',
    borderRadius: 20,
    border: '1px solid transparent',
    fontSize: 12,
    cursor: 'pointer',
    backgroundColor: '#1a1a24',
  },
  filterChip: {
    padding: '6px 12px',
    borderRadius: 12,
    border: '1px solid transparent',
    fontSize: 12,
    cursor: 'pointer',
    backgroundColor: '#1a1a24',
  },
  resetButton: {
    border: 'none',
    background: 'none',
    fontSize: 12,
    color: '#3b82f6',
    cursor: 'pointer',
  },
  chipsRow: {
    display: 'flex',
    flexWrap: 'wrap',
    gap: 8,
  },
  competitorLink: {
    border: 'none',
    background: 'none',
    padding: 0,
    color: '#fff',
    fontSize: 16,
    fontWeight: 600,
    cursor: 'pointer',
    textAlign: 'left',
  },
  subtleLink: {
    border: 'none',
    background: 'none',
    padding: 0,
    fontSize: 12,
    color: '#3b82f6',
    cursor: 'pointer',
    textAlign: 'left',
  },
  tagRow: {
    display: 'flex',
    flexWrap: 'wrap',
    gap: 6,
  },
  tag: {
    backgroundColor: '#1a1a24',
    color: '#9ca3af',
    fontSize: 11,
    padding: '3px 8px',
    borderRadius: 6,
  },
  groupRow: {
    display: 'flex',
    flexWrap: 'wrap',
    gap: 6,
  },
  groupBadge: {
    fontSize: 11,
    padding: '4px 8px',
    borderRadius: 6,
  },
  skeleton: {
    height: 120,
    borderRadius: 14,
    background: 'linear-gradient(90deg, #1a1a24 0%, #1f1f2d 50%, #1a1a24 100%)',
    backgroundSize: '200% 100%',
    animation: 'pulse 1.4s ease-in-out infinite',
  },
  emptyState: {
    textAlign: 'center',
    padding: 40,
    backgroundColor: '#151521',
    borderRadius: 14,
    border: '1px solid #2a2a3a',
    display: 'flex',
    flexDirection: 'column',
    gap: 10,
    alignItems: 'center',
  },
}
