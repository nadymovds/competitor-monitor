import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import ScanCard from '../ui/ScanCard'
import NextScanInfo from '../ui/NextScanInfo'
import ScrollToTopButton from '../ui/ScrollToTopButton'
import { getCompetitorScans, getCompetitorScanDetails } from '../../services/supabase'
import { getNewsDigests, getNewsDigestDetails } from '../../services/news'
import { hapticFeedback } from '../../services/telegram'

const PAGE_SIZE = 10
const TYPE_OPTIONS = [
  { id: 'competitors', label: 'Конкуренты' },
  { id: 'news', label: 'Новости' },
]

export default function ScansScreen({ onNavigateToCompetitor }) {
  const [activeType, setActiveType] = useState('competitors')
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [hasMore, setHasMore] = useState(true)
  const [offset, setOffset] = useState(0)
  const [error, setError] = useState(null)

  const [expandedIds, setExpandedIds] = useState([])
  const [detailsMap, setDetailsMap] = useState({})
  const [loadingDetailsIds, setLoadingDetailsIds] = useState([])

  const sentinelRef = useRef(null)

  const resetState = useCallback(() => {
    setItems([])
    setLoading(true)
    setLoadingMore(false)
    setHasMore(true)
    setOffset(0)
    setError(null)
    setExpandedIds([])
    setDetailsMap({})
    setLoadingDetailsIds([])
  }, [])

  const fetchPage = useCallback(
    async (pageOffset, append) => {
      try {
        if (append) setLoadingMore(true)
        else setLoading(true)

        const service = activeType === 'competitors' ? getCompetitorScans : getNewsDigests
        const { scans, digests, hasMore: more } = await service(PAGE_SIZE, pageOffset)
        const list = activeType === 'competitors' ? scans : digests

        setItems(prev => (append ? [...prev, ...list] : list))
        setHasMore(more)
        setOffset(pageOffset + list.length)
      } catch (err) {
        console.error('ScansScreen load error:', err)
        setError(err.message || 'Ошибка загрузки данных')
      } finally {
        setLoading(false)
        setLoadingMore(false)
      }
    },
    [activeType]
  )

  useEffect(() => {
    resetState()
  }, [activeType, resetState])

  useEffect(() => {
    if (items.length === 0 && loading) {
      fetchPage(0, false)
    }
  }, [fetchPage, items.length, loading])

  const loadMore = useCallback(() => {
    if (loading || loadingMore || !hasMore) return
    fetchPage(offset, true)
  }, [fetchPage, loading, loadingMore, hasMore, offset])

  useEffect(() => {
    const node = sentinelRef.current
    if (!node || !hasMore) return
    const observer = new IntersectionObserver(entries => {
      if (entries[0].isIntersecting) {
        loadMore()
      }
    }, { rootMargin: '160px' })

    observer.observe(node)
    return () => observer.disconnect()
  }, [hasMore, loadMore])

  const isLoadingDetails = useCallback(
    id => loadingDetailsIds.includes(id),
    [loadingDetailsIds]
  )

  const toggleCard = useCallback(
    async (id) => {
      setExpandedIds(prev => {
        if (prev.includes(id)) {
          return prev.filter(itemId => itemId !== id)
        }
        return [...prev, id]
      })

      if (detailsMap[id]) return
      if (loadingDetailsIds.includes(id)) return

      setLoadingDetailsIds(prev => [...prev, id])
      try {
        let details
        if (activeType === 'competitors') {
          details = await getCompetitorScanDetails(id)
        } else {
          details = await getNewsDigestDetails(id)
        }
        setDetailsMap(prev => ({ ...prev, [id]: details }))
      } catch (err) {
        console.error('ScansScreen details error:', err)
        setError(err.message || 'Ошибка загрузки деталей')
      } finally {
        setLoadingDetailsIds(prev => prev.filter(itemId => itemId !== id))
      }
    },
    [activeType, detailsMap, loadingDetailsIds]
  )

  const handleToggle = useCallback(
    (id) => {
      hapticFeedback('light')
      toggleCard(id)
    },
    [toggleCard]
  )

  const handleRetry = () => {
    resetState()
    fetchPage(0, false)
  }

  const scheduleType = useMemo(() => activeType, [activeType])

  return (
    <div style={styles.container}>
      <header style={styles.header}>
        <div style={styles.toggleGroup}>
          {TYPE_OPTIONS.map(option => {
            const isActive = option.id === activeType
            return (
              <button
                key={option.id}
                type="button"
                onClick={() => {
                  if (option.id !== activeType) {
                    hapticFeedback('light')
                    setActiveType(option.id)
                  }
                }}
                style={{
                  ...styles.toggleButton,
                  backgroundColor: isActive ? '#2563eb' : '#151521',
                  color: isActive ? '#fff' : '#9ca3af',
                  borderColor: isActive ? '#2563eb' : '#2a2a3a',
                }}
              >
                {option.label}
              </button>
            )
          })}
        </div>
        <NextScanInfo type={scheduleType} />
      </header>

      {error && (
        <div style={styles.errorBox}>
          <div>{error}</div>
          <button type="button" style={styles.retryButton} onClick={handleRetry}>Повторить</button>
        </div>
      )}

      {loading && items.length === 0 ? (
        <div style={styles.skeletons}>
          {[1, 2, 3].map(index => (
            <div key={index} style={styles.skeleton} />
          ))}
        </div>
      ) : (
        <div style={styles.list}>
          {items.map(item => (
            <ScanCard
              key={item.id}
              type={activeType}
              scan={item}
              isExpanded={expandedIds.includes(item.id)}
              onToggle={handleToggle}
              loadingDetails={isLoadingDetails(item.id)}
              details={detailsMap[item.id]}
              onNavigateToCompetitor={onNavigateToCompetitor}
            />
          ))}
          {hasMore && (
            <div ref={sentinelRef} style={styles.sentinel}>
              {loadingMore && <span style={styles.loadingMore}>Загрузка...</span>}
            </div>
          )}
        </div>
      )}

      <ScrollToTopButton />
    </div>
  )
}

const styles = {
  container: {
    padding: '20px 16px 80px',
    maxWidth: 640,
    margin: '0 auto',
    display: 'flex',
    flexDirection: 'column',
    gap: 20,
  },
  header: {
    display: 'flex',
    flexDirection: 'column',
    gap: 16,
  },
  toggleGroup: {
    display: 'inline-flex',
    gap: 8,
    backgroundColor: '#151521',
    borderRadius: 12,
    border: '1px solid #2a2a3a',
    padding: 4,
  },
  toggleButton: {
    border: '1px solid transparent',
    borderRadius: 9,
    padding: '8px 16px',
    fontSize: 13,
    fontWeight: 600,
    cursor: 'pointer',
  },
  errorBox: {
    backgroundColor: '#2a1315',
    border: '1px solid #ef4444',
    borderRadius: 12,
    padding: 16,
    display: 'flex',
    justifyContent: 'space-between',
    gap: 12,
    color: '#fca5a5',
    fontSize: 13,
  },
  retryButton: {
    backgroundColor: '#ef4444',
    color: '#fff',
    border: 'none',
    borderRadius: 8,
    padding: '6px 12px',
    fontWeight: 600,
    cursor: 'pointer',
  },
  skeletons: {
    display: 'flex',
    flexDirection: 'column',
    gap: 16,
  },
  skeleton: {
    height: 140,
    borderRadius: 16,
    background: 'linear-gradient(90deg, #151521 0%, #1f1f2d 50%, #151521 100%)',
    backgroundSize: '200% 100%',
    animation: 'pulse 1.4s ease-in-out infinite',
  },
  list: {
    display: 'flex',
    flexDirection: 'column',
    gap: 16,
  },
  sentinel: {
    display: 'flex',
    justifyContent: 'center',
    padding: 16,
  },
  loadingMore: {
    fontSize: 13,
    color: '#9ca3af',
  },
}
