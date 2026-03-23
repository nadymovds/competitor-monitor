import React, { useState, useEffect, useRef } from 'react'
import { hapticFeedback } from '../../services/telegram'
import { getCompetitorScans, getCompetitorScanDetails } from '../../services/supabase'
import { getNewsDigests, getNewsDigestDetails, getNewsChannelTags } from '../../services/news'
import ScanCard from '../ui/ScanCard'
import NextScanInfo from '../ui/NextScanInfo'

export default function ScansScreen({ onNavigateToCompetitor, onBack }) {
  const [scanType, setScanType] = useState('competitors') // 'competitors' | 'news'
  const [scans, setScans] = useState([])
  const [loading, setLoading] = useState(true)
  const [hasMore, setHasMore] = useState(true)
  const [offset, setOffset] = useState(0)
  const [availableTags, setAvailableTags] = useState([])
  const [selectedTag, setSelectedTag] = useState(null) // null = все
  const loadMoreRef = useRef(null)

  const PAGE_SIZE = 10

  useEffect(() => {
    // Сброс и загрузка при смене типа
    setScans([])
    setOffset(0)
    setHasMore(true)
    setSelectedTag(null)
    loadScans(scanType, 0, null, true)
    if (scanType === 'news') {
      getNewsChannelTags().then(setAvailableTags).catch(() => {})
    }
  }, [scanType])

  useEffect(() => {
    if (!loadMoreRef.current || !hasMore || loading) return

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && !loading && hasMore) {
          loadScans(scanType, offset, selectedTag, false)
        }
      },
      { rootMargin: '100px' }
    )

    observer.observe(loadMoreRef.current)
    return () => observer.disconnect()
  }, [loading, hasMore, offset, scanType, selectedTag])

  const loadScans = async (type, currentOffset, tag, isInitial = false) => {
    if (loading && !isInitial) return
    setLoading(true)

    try {
      let result
      if (type === 'competitors') {
        result = await getCompetitorScans(PAGE_SIZE, currentOffset)
      } else {
        result = await getNewsDigests(PAGE_SIZE, currentOffset, tag)
      }

      // Извлекаем данные из объекта {scans/digests, hasMore}
      const data = type === 'competitors' ? result.scans : result.digests

      setHasMore(result.hasMore)
      setScans(prev => currentOffset === 0 ? data : [...prev, ...data])
      setOffset(currentOffset + PAGE_SIZE)
    } catch (err) {
      console.error('Failed to load scans:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleExpandScan = async (scanId) => {
    if (scanType === 'competitors') {
      return await getCompetitorScanDetails(scanId)
    } else {
      return await getNewsDigestDetails(scanId)
    }
  }

  const handleScanTypeChange = (type) => {
    hapticFeedback('light')
    setScanType(type)
  }

  const handleTagChange = (tag) => {
    hapticFeedback('light')
    setSelectedTag(tag)
    setScans([])
    setOffset(0)
    setHasMore(true)
    loadScans(scanType, 0, tag, true)
  }

  return (
    <div style={styles.container}>
      {/* Header */}
      <div style={styles.header}>
        {onBack && (
          <button onClick={() => { hapticFeedback('light'); onBack() }} style={styles.backButton}>
            ← Настройки
          </button>
        )}
        <h1 style={styles.title}>Сканирования</h1>
      </div>

      {/* Segmented Control */}
      <div style={styles.segmentedControl}>
        <button
          onClick={() => handleScanTypeChange('competitors')}
          style={{
            ...styles.segment,
            ...(scanType === 'competitors' ? styles.segmentActive : {})
          }}
        >
          Конкуренты
        </button>
        <button
          onClick={() => handleScanTypeChange('news')}
          style={{
            ...styles.segment,
            ...(scanType === 'news' ? styles.segmentActive : {})
          }}
        >
          Новости
        </button>
      </div>

      {/* Next Scan Info */}
      <NextScanInfo scanType={scanType} />

      {/* Tag filter (news only) */}
      {scanType === 'news' && availableTags.length > 0 && (
        <div style={{ display: 'flex', gap: 8, overflowX: 'auto', whiteSpace: 'nowrap', marginBottom: 12, scrollbarWidth: 'none' }}>
          {[null, ...availableTags].map(tag => (
            <button
              key={tag ?? '__all__'}
              onClick={() => handleTagChange(tag)}
              style={{
                borderRadius: 16, padding: '6px 12px', fontSize: 13, fontWeight: 500,
                border: 'none', cursor: 'pointer', flexShrink: 0,
                backgroundColor: selectedTag === tag ? '#3b82f620' : '#1a1a24',
                color: selectedTag === tag ? '#3b82f6' : '#9ca3af',
              }}
            >
              {tag === null ? 'Все' : tag.toUpperCase()}
            </button>
          ))}
        </div>
      )}

      {/* Scans List */}
      <div style={styles.scansList}>
        {scans.map(scan => (
          <ScanCard
            key={scan.id}
            scan={scan}
            scanType={scanType}
            onExpand={handleExpandScan}
            onNavigateToCompetitor={onNavigateToCompetitor}
          />
        ))}

        {loading && (
          <div style={{ textAlign: 'center', padding: 20, color: '#6b7280' }}>
            Загрузка...
          </div>
        )}

        {!loading && scans.length === 0 && (
          <div style={{ textAlign: 'center', padding: 40, color: '#6b7280' }}>
            <div style={{ fontSize: 48, marginBottom: 12 }}>📭</div>
            <div style={{ fontSize: 16, fontWeight: 500, marginBottom: 8 }}>
              {scanType === 'competitors' ? 'Нет сканирований конкурентов' : 'Нет дайджестов новостей'}
            </div>
            <div style={{ fontSize: 13, opacity: 0.7 }}>
              {scanType === 'competitors' 
                ? 'Сканирования появятся после запуска мониторинга'
                : 'Дайджесты появятся после обработки новостей'}
            </div>
          </div>
        )}

        {/* Infinite scroll trigger */}
        {hasMore && <div ref={loadMoreRef} style={{ height: 20 }} />}
      </div>
    </div>
  )
}

const styles = {
  container: {
    minHeight: '100vh',
    paddingBottom: 80,
    backgroundColor: '#0f0f19'
  },
  header: {
    paddingBottom: 12
  },
  backButton: {
    background: 'none',
    border: 'none',
    color: '#3b82f6',
    fontSize: 14,
    fontWeight: 500,
    cursor: 'pointer',
    padding: '0 0 8px 0',
    display: 'block'
  },
  title: {
    fontSize: 24,
    fontWeight: 700,
    color: '#fff',
    margin: 0
  },
  segmentedControl: {
    display: 'flex',
    gap: 0,
    backgroundColor: '#1a1a24',
    borderRadius: 8,
    padding: 3,
    border: '1px solid #2a2a3a',
    marginBottom: 12
  },
  segment: {
    flex: 1,
    padding: '8px 16px',
    fontSize: 14,
    fontWeight: 500,
    color: '#9ca3af',
    backgroundColor: 'transparent',
    border: 'none',
    borderRadius: 6,
    cursor: 'pointer',
    transition: 'all 0.2s'
  },
  segmentActive: {
    color: '#fff',
    backgroundColor: '#3b82f6'
  },
  scansList: {
    display: 'flex',
    flexDirection: 'column',
    gap: 12
  }
}
