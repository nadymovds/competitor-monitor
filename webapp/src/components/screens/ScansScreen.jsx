import React, { useState, useEffect, useRef } from 'react'
import { hapticFeedback } from '../../services/telegram'
import { getCompetitorScans, getCompetitorScanDetails } from '../../services/supabase'
import { getNewsDigests, getNewsDigestDetails } from '../../services/news'
import ScanCard from '../ui/ScanCard'
import NextScanInfo from '../ui/NextScanInfo'

export default function ScansScreen({ onNavigateToCompetitor }) {
  const [scanType, setScanType] = useState('competitors') // 'competitors' | 'news'
  const [scans, setScans] = useState([])
  const [loading, setLoading] = useState(true)
  const [hasMore, setHasMore] = useState(true)
  const [offset, setOffset] = useState(0)
  const loadMoreRef = useRef(null)

  const PAGE_SIZE = 10

  useEffect(() => {
    // Сброс при смене типа
    setLoading(true)
    setScans([])
    setOffset(0)
    setHasMore(true)
    loadScans(scanType, 0)
  }, [scanType])

  useEffect(() => {
    if (!loadMoreRef.current || !hasMore) return

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && !loading && hasMore) {
          loadScans(scanType, offset)
        }
      },
      { rootMargin: '100px' }
    )

    observer.observe(loadMoreRef.current)
    return () => observer.disconnect()
  }, [loading, hasMore, offset, scanType])

  const loadScans = async (type, currentOffset) => {
    if (loading) return
    setLoading(true)

    try {
      let result
      if (type === 'competitors') {
        result = await getCompetitorScans(currentOffset, PAGE_SIZE)
      } else {
        result = await getNewsDigests(currentOffset, PAGE_SIZE)
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

  return (
    <div style={styles.container}>
      {/* Header */}
      <div style={styles.header}>
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
            Нет сканирований
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
    padding: '16px 16px 12px 16px'
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
    margin: '0 16px 12px 16px'
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
    gap: 12,
    padding: '0 16px'
  }
}
