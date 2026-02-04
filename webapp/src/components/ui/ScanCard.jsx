import React, { useState } from 'react'
import { hapticFeedback, openLink, openTelegramLink } from '../../services/telegram'

const CATEGORY_CONFIG = {
  products: { label: 'Продукт', color: '#22c55e' },
  prices: { label: 'Цена', color: '#ef4444' },
  services: { label: 'Условия', color: '#3b82f6' },
  news: { label: 'Новость', color: '#f59e0b' }
}

export default function ScanCard({ scan, scanType, onExpand, onNavigateToCompetitor }) {
  const [isExpanded, setIsExpanded] = useState(false)
  const [details, setDetails] = useState(null)
  const [loading, setLoading] = useState(false)

  const handleToggle = async () => {
    hapticFeedback('light')
    
    if (!isExpanded && !details) {
      setLoading(true)
      try {
        const loadedDetails = await onExpand(scan.id)
        setDetails(loadedDetails)
      } catch (err) {
        console.error('Failed to load scan details:', err)
      } finally {
        setLoading(false)
      }
    }
    
    setIsExpanded(!isExpanded)
  }

  const formatDate = (dateStr) => {
    if (!dateStr) return ''
    return new Date(dateStr).toLocaleDateString('ru-RU', {
      day: 'numeric',
      month: 'long',
      year: 'numeric'
    })
  }

  const ensureProtocol = (url) => {
    if (!url) return url
    if (url.startsWith('http://') || url.startsWith('https://')) return url
    return `https://${url}`
  }

  if (scanType === 'competitors') {
    return (
      <div style={styles.card}>
        {/* Заголовок */}
        <button onClick={handleToggle} style={styles.header}>
          <span style={styles.date}>{formatDate(scan.report_date)}</span>
          <span style={{ ...styles.arrow, transform: isExpanded ? 'rotate(180deg)' : 'rotate(0)' }}>▼</span>
        </button>

        {/* Свернутая статистика */}
        {!isExpanded && (
          <div style={styles.stats}>
            <StatBox label="Источники" value={scan.total_sites || 0} />
            <StatBox 
              label="Успешно" 
              value={scan.successful_sites || 0}
              subvalue={scan.total_sites ? `${Math.round((scan.successful_sites / scan.total_sites) * 100)}%` : null}
              color="#22c55e"
            />
            <StatBox label="Изменений" value={scan.total_changes || 0} color="#3b82f6" />
            <StatBox label="Ошибки" value={scan.problems_count || 0} color="#ef4444" />
          </div>
        )}

        {/* Развернутое содержимое */}
        {isExpanded && (
          <div style={styles.content}>
            {loading ? (
              <div style={{ textAlign: 'center', padding: 20, color: '#6b7280' }}>Загрузка...</div>
            ) : (
              <>
                {/* Статистика */}
                <div style={{ ...styles.stats, marginBottom: 16 }}>
                  <StatBox label="Источники" value={scan.total_sites || 0} />
                  <StatBox 
                    label="Успешно" 
                    value={scan.successful_sites || 0}
                    subvalue={scan.total_sites ? `${Math.round((scan.successful_sites / scan.total_sites) * 100)}%` : null}
                    color="#22c55e"
                  />
                  <StatBox label="Изменений" value={scan.total_changes || 0} color="#3b82f6" />
                  <StatBox label="Ошибки" value={scan.problems_count || 0} color="#ef4444" />
                </div>

                {/* Список изменений */}
                {details && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                    <div style={{ fontSize: 14, fontWeight: 600, color: '#e5e7eb', marginBottom: 4 }}>
                      Все изменения ({(details.changes?.length || 0) + (details.tgPosts?.length || 0)})
                    </div>
                    
                    {/* Website changes */}
                    {details.changes?.map((change, idx) => (
                      <ChangeItem 
                        key={`web_${idx}`}
                        change={change}
                        sourceType="website"
                        onNavigate={() => onNavigateToCompetitor && onNavigateToCompetitor(change.competitors?.id)}
                      />
                    ))}
                    
                    {/* TG posts */}
                    {details.tgPosts?.map((post, idx) => (
                      <ChangeItem 
                        key={`tg_${idx}`}
                        change={post}
                        sourceType="telegram"
                        onNavigate={() => onNavigateToCompetitor && onNavigateToCompetitor(post.competitor_id)}
                      />
                    ))}
                    
                    {(details.changes?.length === 0 && details.tgPosts?.length === 0) && (
                      <div style={{ textAlign: 'center', padding: 20, color: '#6b7280', fontSize: 14 }}>
                        Нет изменений
                      </div>
                    )}
                  </div>
                )}
              </>
            )}
          </div>
        )}
      </div>
    )
  } else {
    // News digest
    return (
      <div style={styles.card}>
        {/* Заголовок */}
        <button onClick={handleToggle} style={styles.header}>
          <span style={styles.date}>{formatDate(scan.created_at)}</span>
          <span style={{ ...styles.arrow, transform: isExpanded ? 'rotate(180deg)' : 'rotate(0)' }}>▼</span>
        </button>

        {/* Свернутая статистика */}
        {!isExpanded && (
          <div style={{ ...styles.stats, gridTemplateColumns: 'repeat(3, 1fr)' }}>
            <StatBox label="Каналов" value={scan.total_channels || 0} />
            <StatBox label="Постов" value={scan.total_posts || 0} color="#3b82f6" />
            <StatBox label="Период" value={scan.period_days ? `${scan.period_days}д` : '7д'} />
          </div>
        )}

        {/* Развернутое содержимое */}
        {isExpanded && (
          <div style={styles.content}>
            {loading ? (
              <div style={{ textAlign: 'center', padding: 20, color: '#6b7280' }}>Загрузка...</div>
            ) : (
              <>
                <div style={{ ...styles.stats, gridTemplateColumns: 'repeat(3, 1fr)', marginBottom: 16 }}>
                  <StatBox label="Каналов" value={scan.total_channels || 0} />
                  <StatBox label="Постов" value={scan.total_posts || 0} color="#3b82f6" />
                  <StatBox label="Период" value={scan.period_days ? `${scan.period_days}д` : '7д'} />
                </div>

                {/* Список постов */}
                {details && details.posts && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                    <div style={{ fontSize: 14, fontWeight: 600, color: '#e5e7eb', marginBottom: 4 }}>
                      Все посты ({details.posts.length})
                    </div>
                    
                    {details.posts.map((post, idx) => (
                      <NewsPostItem key={idx} post={post} />
                    ))}
                    
                    {details.posts.length === 0 && (
                      <div style={{ textAlign: 'center', padding: 20, color: '#6b7280', fontSize: 14 }}>
                        Нет постов
                      </div>
                    )}
                  </div>
                )}
              </>
            )}
          </div>
        )}
      </div>
    )
  }
}

// Компонент изменения конкурента
function ChangeItem({ change, sourceType, onNavigate }) {
  const category = change.category || 'news'
  const isTelegram = sourceType === 'telegram'
  const linkUrl = isTelegram ? change.post_url : change.competitors?.url

  return (
    <div style={styles.changeItem}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 6 }}>
        <button
          onClick={onNavigate}
          style={styles.competitorName}
        >
          {isTelegram ? change.competitors?.name : change.competitors?.name || 'Неизвестный'}
        </button>
        <div style={{ display: 'flex', gap: 4 }}>
          <span style={{
            ...styles.badge,
            backgroundColor: isTelegram ? '#8b5cf620' : '#6b728020',
            color: isTelegram ? '#8b5cf6' : '#6b7280'
          }}>
            {isTelegram ? 'TG' : 'Web'}
          </span>
          <span style={{
            ...styles.badge,
            backgroundColor: (CATEGORY_CONFIG[category]?.color || '#6b7280') + '20',
            color: CATEGORY_CONFIG[category]?.color || '#6b7280'
          }}>
            {CATEGORY_CONFIG[category]?.label || category}
          </span>
        </div>
      </div>
      
      {linkUrl && (
        <button
          onClick={() => isTelegram ? openTelegramLink(linkUrl) : openLink(ensureProtocol(linkUrl))}
          style={styles.link}
        >
          {isTelegram ? `📢 @${change.channel_username}` : `🌐 ${linkUrl}`}
        </button>
      )}
      
      <div style={styles.summary}>{change.summary}</div>
      
      {change.tags?.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginTop: 6 }}>
          {change.tags.map((tag, i) => (
            <span key={i} style={styles.tag}>{tag}</span>
          ))}
        </div>
      )}
    </div>
  )
}

// Компонент новостного поста
function NewsPostItem({ post }) {
  const isTelegram = post.source_type === 'telegram'
  
  return (
    <div style={styles.changeItem}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 6 }}>
        <button
          onClick={() => isTelegram ? openTelegramLink(post.post_url) : openLink(post.post_url)}
          style={styles.link}
        >
          {isTelegram ? `📢 ${post.channel?.title || post.channel?.username}` : `🌐 ${post.channel?.title}`}
        </button>
        <span style={{
          ...styles.badge,
          backgroundColor: isTelegram ? '#8b5cf620' : '#6b728020',
          color: isTelegram ? '#8b5cf6' : '#6b7280'
        }}>
          {isTelegram ? 'TG' : 'Web'}
        </span>
      </div>
      
      {post.title && (
        <div style={{ fontSize: 14, fontWeight: 600, color: '#fff', marginBottom: 6 }}>
          {post.title}
        </div>
      )}
      
      <div style={styles.summary}>{post.summary}</div>
      
      {post.categories?.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginTop: 6 }}>
          {post.categories.map(cat => (
            <span key={cat.id} style={{
              ...styles.badge,
              backgroundColor: cat.color + '20',
              color: cat.color
            }}>
              {cat.name}
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

// Компонент статистики
function StatBox({ label, value, subvalue, color = '#6b7280' }) {
  return (
    <div style={{ flex: 1, textAlign: 'center' }}>
      <div style={{ fontSize: 18, fontWeight: 700, color }}>{value}</div>
      {subvalue && <div style={{ fontSize: 10, color: '#6b7280' }}>{subvalue}</div>}
      <div style={{ fontSize: 11, color: '#6b7280' }}>{label}</div>
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
    backgroundColor: '#1a1a24',
    borderRadius: 12,
    overflow: 'hidden'
  },
  header: {
    width: '100%',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 16,
    background: 'none',
    border: 'none',
    cursor: 'pointer'
  },
  date: {
    fontSize: 15,
    fontWeight: 600,
    color: '#fff'
  },
  arrow: {
    fontSize: 10,
    color: '#6b7280',
    transition: 'transform 0.2s'
  },
  stats: {
    display: 'grid',
    gridTemplateColumns: 'repeat(4, 1fr)',
    gap: 8,
    padding: '0 16px 16px 16px'
  },
  content: {
    padding: 16,
    borderTop: '1px solid #2a2a3a'
  },
  changeItem: {
    backgroundColor: '#252532',
    borderRadius: 8,
    padding: 12
  },
  competitorName: {
    fontSize: 14,
    fontWeight: 600,
    color: '#fff',
    background: 'none',
    border: 'none',
    padding: 0,
    cursor: 'pointer',
    textDecoration: 'underline',
    textDecorationColor: 'rgba(255,255,255,0.3)',
    textAlign: 'left'
  },
  link: {
    fontSize: 12,
    color: '#3b82f6',
    background: 'none',
    border: 'none',
    padding: 0,
    cursor: 'pointer',
    marginBottom: 6,
    display: 'block',
    textAlign: 'left'
  },
  summary: {
    fontSize: 13,
    color: '#e5e7eb',
    lineHeight: 1.5
  },
  badge: {
    fontSize: 10,
    fontWeight: 500,
    padding: '3px 6px',
    borderRadius: 4
  },
  tag: {
    fontSize: 11,
    color: '#9ca3af',
    backgroundColor: '#1a1a24',
    padding: '3px 6px',
    borderRadius: 4
  }
}
