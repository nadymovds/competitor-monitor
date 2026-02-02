import React, { useState, useEffect, useRef } from 'react'
import { getNewsCategories, getNewsChannels, getNewsPosts, addPostCategory, removePostCategory } from '../../services/news'
import { hapticFeedback, showAlert } from '../../services/telegram'
import NewsCard from '../ui/NewsCard'
import NewsFilters from '../ui/NewsFilters'
import ScrollToTopButton from '../ui/ScrollToTopButton'

const PAGE_SIZE = 20

export default function NewsScreen({ user }) {
  // Данные
  const [posts, setPosts] = useState([])
  const [categories, setCategories] = useState([])
  const [channels, setChannels] = useState([])
  const [totalCount, setTotalCount] = useState(0)
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)

  // Фильтры
  const [selectedCategories, setSelectedCategories] = useState([])
  const [selectedChannels, setSelectedChannels] = useState([])
  const [dateRange, setDateRange] = useState('week')
  const [customDateFrom, setCustomDateFrom] = useState('')
  const [customDateTo, setCustomDateTo] = useState('')

  // Пагинация
  const [offset, setOffset] = useState(0)

  // Флаг первой загрузки — чтобы useEffect фильтров не стрелял дважды
  const initialized = useRef(false)

  // Начальная загрузка
  useEffect(() => {
    async function init() {
      try {
        const [cats, chs] = await Promise.all([getNewsCategories(), getNewsChannels()])
        setCategories(cats)
        setChannels(chs)
        await loadPosts(0, cats)
      } catch (e) {
        console.error('NewsScreen init error:', e)
      } finally {
        initialized.current = true
      }
    }
    init()
  }, [])

  // Реакция на изменение фильтров
  useEffect(() => {
    if (!initialized.current) return
    setOffset(0)
    loadPosts(0)
  }, [selectedCategories, selectedChannels, dateRange, customDateFrom, customDateTo])

  function computeDateRange() {
    const now = new Date()
    let dateFrom, dateTo
    if (dateRange === 'week') {
      const d = new Date(now)
      d.setDate(d.getDate() - 7)
      dateFrom = d.toISOString()
    } else if (dateRange === 'month') {
      const d = new Date(now)
      d.setDate(d.getDate() - 30)
      dateFrom = d.toISOString()
    } else if (dateRange === 'custom') {
      dateFrom = customDateFrom || undefined
      dateTo = customDateTo || undefined
    }
    // 'all' — без фильтра
    return { dateFrom, dateTo }
  }

  async function loadPosts(newOffset, allCats = null) {
    try {
      if (newOffset === 0) setLoading(true)
      const { dateFrom, dateTo } = computeDateRange()
      // Если пользователь не выбрал конкретные категории — фильтруем по всем видимым
      const cats = allCats || categories
      const effectiveCategories = selectedCategories.length > 0
        ? selectedCategories
        : cats.filter(c => c.is_visible).map(c => c.id)
      const { posts: newPosts, count } = await getNewsPosts({
        categories: effectiveCategories,
        channels: selectedChannels,
        dateFrom,
        dateTo,
        limit: PAGE_SIZE,
        offset: newOffset,
      })
      if (newOffset === 0) {
        setPosts(newPosts)
      } else {
        setPosts(prev => [...prev, ...newPosts])
      }
      setTotalCount(count)
      setOffset(newOffset)
    } catch (e) {
      console.error('loadPosts error:', e)
    } finally {
      setLoading(false)
      setLoadingMore(false)
    }
  }

  const handleLoadMore = () => {
    setLoadingMore(true)
    loadPosts(offset + PAGE_SIZE)
  }

  const handleFilterChange = ({ categories: cats, channels: chs, dateRange: dr, customDateFrom: cdf, customDateTo: cdt }) => {
    setSelectedCategories(cats)
    setSelectedChannels(chs)
    setDateRange(dr)
    setCustomDateFrom(cdf)
    setCustomDateTo(cdt)
  }

  const handleCategoryAdd = async (postId, categoryId) => {
    try {
      await addPostCategory(postId, categoryId)
      const cat = categories.find(c => c.id === categoryId)
      if (cat) {
        setPosts(prev => prev.map(p =>
          p.id === postId
            ? { ...p, categories: [...p.categories, { ...cat, is_manual: true }] }
            : p
        ))
      }
      hapticFeedback('success')
    } catch (e) {
      console.error('addPostCategory error:', e)
      showAlert('Не удалось изменить категорию')
    }
  }

  const handleCategoryRemove = async (postId, categoryId) => {
    try {
      await removePostCategory(postId, categoryId)
      setPosts(prev => prev.map(p =>
        p.id === postId
          ? { ...p, categories: p.categories.filter(c => c.id !== categoryId) }
          : p
      ))
      hapticFeedback('light')
    } catch (e) {
      console.error('removePostCategory error:', e)
      showAlert('Не удалось изменить категорию')
    }
  }

  const isAdmin = user?.role === 'admin'
  // Видимые категории — всегда только is_visible, независимо от роли
  const visibleCategories = categories.filter(c => c.is_visible)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div>
        <h1 style={{ fontSize: 24, fontWeight: 700, color: '#fff', margin: 0 }}>Новости</h1>
        {channels.length > 0 && (() => {
          const lastScan = channels
            .map(ch => ch.last_scan_at)
            .filter(Boolean)
            .sort()
            .pop()
          return lastScan ? (
            <div style={{ fontSize: 13, color: '#6b7280', marginTop: 4 }}>
              Обновлено {new Date(lastScan).toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric', hour: '2-digit', minute: '2-digit' })}
            </div>
          ) : null
        })()}
      </div>

      <NewsFilters
        categories={visibleCategories}
        channels={channels}
        selectedCategories={selectedCategories}
        selectedChannels={selectedChannels}
        dateRange={dateRange}
        customDateFrom={customDateFrom}
        customDateTo={customDateTo}
        onChange={handleFilterChange}
      />

      <div style={{ fontSize: 13, color: '#6b7280' }}>
        Найдено: {totalCount}
      </div>

      {loading ? (
        <LoadingSkeleton />
      ) : posts.length === 0 ? (
        <EmptyState />
      ) : (
        posts.map(post => (
          <NewsCard
            key={post.id}
            post={post}
            isAdmin={isAdmin}
            allCategories={categories}
            onCategoryAdd={handleCategoryAdd}
            onCategoryRemove={handleCategoryRemove}
          />
        ))
      )}

      {!loading && posts.length < totalCount && (
        <button onClick={handleLoadMore} disabled={loadingMore} style={styles.loadMoreBtn}>
          {loadingMore ? 'Загрузка...' : `Показать ещё (${totalCount - posts.length})`}
        </button>
      )}
      <ScrollToTopButton />
    </div>
  )
}

function LoadingSkeleton() {
  return [1, 2, 3].map(i => (
    <div key={i} style={{ backgroundColor: '#1a1a24', borderRadius: 12, height: 160, animation: 'pulse 1.5s infinite' }} />
  ))
}

function EmptyState() {
  return (
    <div style={{ textAlign: 'center', padding: 40, color: '#6b7280' }}>
      <div style={{ fontSize: 48 }}>📭</div>
      <div style={{ fontSize: 16, fontWeight: 500, marginTop: 12 }}>Новостей не найдено</div>
      <div style={{ fontSize: 13, marginTop: 8 }}>Попробуйте изменить фильтры или период</div>
    </div>
  )
}

const styles = {
  loadMoreBtn: {
    backgroundColor: '#252532',
    color: '#d1d5db',
    border: '1px solid #2a2a3a',
    borderRadius: 10,
    padding: '12px 16px',
    fontSize: 14,
    fontWeight: 500,
    cursor: 'pointer',
    textAlign: 'center',
    width: '100%',
  },
}
