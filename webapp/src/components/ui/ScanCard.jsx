import React from 'react'
import { openLink, openTelegramLink, hapticFeedback } from '../../services/telegram'

const CATEGORY_LABELS = {
  products: 'Продукты',
  prices: 'Цены',
  services: 'Условия',
  news: 'Новости',
}

function formatDate(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleDateString('ru-RU', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  })
}

function formatTime(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleTimeString('ru-RU', {
    hour: '2-digit',
    minute: '2-digit',
  })
}

function formatDuration(seconds) {
  if (!seconds) return null
  const mins = Math.floor(seconds / 60)
  if (mins < 1) return `${seconds}s`
  const hours = Math.floor(mins / 60)
  const minutes = mins % 60
  if (hours > 0) return `${hours}ч ${minutes}м`
  return `${minutes}м`
}

function SummaryStat({ label, value }) {
  return (
    <div style={styles.stat}>
      <span style={styles.statLabel}>{label}</span>
      <span style={styles.statValue}>{value}</span>
    </div>
  )
}

function DetailSection({ title, children }) {
  return (
    <div style={styles.section}>
      <div style={styles.sectionTitle}>{title}</div>
      {children}
    </div>
  )
}

function ChangeItem({ item, onNavigateToCompetitor }) {
  return (
    <div style={styles.detailItem}>
      <div style={styles.detailHeader}>
        <button
          type="button"
          style={styles.detailTitle}
          onClick={() => {
            hapticFeedback('light')
            onNavigateToCompetitor?.(item.competitor?.id, 'scans')
          }}
          disabled={!item.competitor?.id}
        >
          {item.competitor?.name || 'Неизвестный конкурент'}
        </button>
        <span style={styles.detailMeta}>{formatDate(item.detected_at || item.timestamp)} {formatTime(item.detected_at || item.timestamp)}</span>
      </div>
      {item.summary && <div style={styles.detailSummary}>{item.summary}</div>}
      <div style={styles.detailFooter}>
        {item.category && (<span style={styles.metaPill}>{CATEGORY_LABELS[item.category] || item.category}</span>)}
        {item.url && (
          <button
            type="button"
            style={styles.linkButton}
            onClick={() => {
              hapticFeedback('light')
              openLink(item.url)
            }}
          >
            Открыть источник
          </button>
        )}
        {item.urlLabel && (
          <span style={styles.urlLabel}>{item.urlLabel}</span>
        )}
      </div>
      {item.tags?.length > 0 && (
        <div style={styles.tagsRow}>
          {item.tags.map(tag => (
            <span key={tag} style={styles.tagChip}>#{tag}</span>
          ))}
        </div>
      )}
    </div>
  )
}

function TgPostItem({ item }) {
  return (
    <div style={styles.detailItem}>
      <div style={styles.detailHeader}>
        <span style={styles.detailTitle}>{item.competitor?.name || item.channel_title || 'Telegram'}</span>
        <span style={styles.detailMeta}>{formatDate(item.post_date || item.detected_at)} {formatTime(item.post_date || item.detected_at)}</span>
      </div>
      <div style={styles.detailSummary}>{item.summary || item.title || 'Без описания'}</div>
      <div style={styles.detailFooter}>
        {item.channel_username && <span style={styles.metaPill}>@{item.channel_username}</span>}
        {typeof item.views_count === 'number' && <span style={styles.metaPill}>{item.views_count} просмотров</span>}
        {item.post_url && (
          <button
            type="button"
            style={styles.linkButton}
            onClick={() => {
              hapticFeedback('light')
              openTelegramLink(item.post_url)
            }}
          >
            Открыть пост
          </button>
        )}
      </div>
      {item.tags?.length > 0 && (
        <div style={styles.tagsRow}>
          {item.tags.map(tag => (
            <span key={tag} style={styles.tagChip}>#{tag}</span>
          ))}
        </div>
      )}
    </div>
  )
}

function NewsPostItem({ item }) {
  const body = item.summary || item.content_text || null
  const channelName = item.channel ? (item.channel.title || item.channel.username || 'Источник') : null
  const postUrl = item.post_url || item.link || null
  return (
    <div style={styles.detailItem}>
      <div style={styles.detailHeader}>
        <span style={styles.detailTitle}>{item.title || item.summary || 'Без заголовка'}</span>
        <span style={styles.detailMeta}>{formatDate(item.post_date)} {formatTime(item.post_date)}</span>
      </div>
      {channelName && (
        <div style={styles.detailMeta}>{channelName}</div>
      )}
      {body && <div style={styles.detailSummary}>{body}</div>}
      <div style={styles.detailFooter}>
        {item.categories?.length > 0 && (
          <div style={styles.tagsRow}>
            {item.categories.map(category => (
              <span key={category.id} style={styles.metaPill}>{category.name}</span>
            ))}
          </div>
        )}
        {postUrl && (
          <button
            type="button"
            style={styles.linkButton}
            onClick={() => {
              hapticFeedback('light')
              openLink(postUrl)
            }}
          >
            Открыть публикацию
          </button>
        )}
      </div>
    </div>
  )
}

export default function ScanCard({
  type,
  scan,
  isExpanded,
  onToggle,
  loadingDetails,
  details,
  onNavigateToCompetitor,
}) {
  const durationLabel = formatDuration(scan.durationSeconds)

  return (
    <div style={styles.card}>
      <button
        type="button"
        style={styles.header}
        onClick={() => {
          hapticFeedback('light')
          onToggle?.(scan.id)
        }}
      >
        <span style={styles.headerTitle}>{formatDate(scan.reportDate || scan.digestDate)}</span>
        <span style={styles.headerMeta}>
          {durationLabel && <span style={styles.metaPill}>{durationLabel}</span>}
          <span style={styles.arrow}>{isExpanded ? '▲' : '▼'}</span>
        </span>
      </button>

      <div style={styles.summaryRow}>
        {type === 'competitors' ? (
          <>
            <SummaryStat label="Источники" value={scan.totalSites ?? '—'} />
            <SummaryStat label="Успешно" value={scan.successRate != null ? `${scan.successRate}%` : '—'} />
            <SummaryStat label="Изменений" value={scan.changesCount ?? '0'} />
            <SummaryStat label="Ошибки" value={scan.problemsCount ?? '0'} />
          </>
        ) : (
          <>
            <SummaryStat label="Каналов" value={scan.totalChannels ?? '—'} />
            <SummaryStat label="Постов" value={scan.totalPosts ?? '—'} />
            <SummaryStat
              label="Период"
              value={`${formatDate(scan.periodStart)} — ${formatDate(scan.periodEnd)}`}
            />
          </>
        )}
      </div>

      {isExpanded && (
        <div style={styles.detailsContainer}>
          {loadingDetails ? (
            <div style={styles.loading}>Загрузка...</div>
          ) : (
            <>
              {type === 'competitors' ? (
                <>
                  {scan.overallSummary && (
                    <div style={styles.summaryBox}>{scan.overallSummary}</div>
                  )}
                  <DetailSection title="Изменения на сайтах">
                    {details?.changes?.length ? (
                      details.changes.map(change => (
                        <ChangeItem
                          key={change.id}
                          item={change}
                          onNavigateToCompetitor={onNavigateToCompetitor}
                        />
                      ))
                    ) : (
                      <div style={styles.emptyDetail}>Изменений не зафиксировано</div>
                    )}
                  </DetailSection>
                  <DetailSection title="Telegram">
                    {details?.tgPosts?.length ? (
                      details.tgPosts.map(post => (
                        <TgPostItem key={post.id} item={post} />
                      ))
                    ) : (
                      <div style={styles.emptyDetail}>Постов не найдено</div>
                    )}
                  </DetailSection>
                </>
              ) : (
                <>
                  {scan.summary && <div style={styles.summaryBox}>{scan.summary}</div>}
                  <DetailSection title="Публикации">
                    {details?.posts?.length ? (
                      details.posts.map(post => (
                        <NewsPostItem key={post.id} item={post} />
                      ))
                    ) : (
                      <div style={styles.emptyDetail}>Публикации отсутствуют</div>
                    )}
                  </DetailSection>
                </>
              )}
            </>
          )}
        </div>
      )}
    </div>
  )
}

const styles = {
  card: {
    backgroundColor: '#151521',
    border: '1px solid #2a2a3a',
    borderRadius: 16,
    padding: 16,
    display: 'flex',
    flexDirection: 'column',
    gap: 12,
  },
  header: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    background: 'none',
    border: 'none',
    padding: 0,
    cursor: 'pointer',
    color: '#fff',
    textAlign: 'left',
  },
  headerTitle: {
    fontSize: 16,
    fontWeight: 600,
  },
  headerMeta: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
  },
  arrow: {
    fontSize: 14,
    color: '#9ca3af',
  },
  summaryRow: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))',
    gap: 12,
  },
  stat: {
    display: 'flex',
    flexDirection: 'column',
    gap: 4,
    backgroundColor: '#1a1a24',
    borderRadius: 12,
    padding: '10px 12px',
  },
  statLabel: {
    fontSize: 12,
    color: '#9ca3af',
  },
  statValue: {
    fontSize: 16,
    fontWeight: 600,
  },
  detailsContainer: {
    display: 'flex',
    flexDirection: 'column',
    gap: 16,
    borderTop: '1px solid #2a2a3a',
    paddingTop: 16,
  },
  summaryBox: {
    backgroundColor: '#1a1a24',
    border: '1px solid #2a2a3a',
    borderRadius: 12,
    padding: 12,
    fontSize: 13,
    color: '#e5e7eb',
    lineHeight: 1.6,
  },
  section: {
    display: 'flex',
    flexDirection: 'column',
    gap: 12,
  },
  sectionTitle: {
    fontSize: 13,
    fontWeight: 600,
    color: '#9ca3af',
  },
  detailItem: {
    display: 'flex',
    flexDirection: 'column',
    gap: 8,
    backgroundColor: '#1a1a24',
    borderRadius: 12,
    padding: 12,
    border: '1px solid #2a2a3a',
  },
  detailHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: 12,
  },
  detailTitle: {
    background: 'none',
    border: 'none',
    padding: 0,
    fontSize: 14,
    fontWeight: 600,
    color: '#fff',
    cursor: 'pointer',
    textAlign: 'left',
  },
  detailMeta: {
    fontSize: 11,
    color: '#6b7280',
    whiteSpace: 'nowrap',
  },
  detailSummary: {
    fontSize: 13,
    color: '#e5e7eb',
    lineHeight: 1.5,
  },
  detailFooter: {
    display: 'flex',
    flexWrap: 'wrap',
    gap: 8,
    alignItems: 'center',
  },
  linkButton: {
    backgroundColor: '#2563eb',
    color: '#fff',
    border: 'none',
    borderRadius: 8,
    padding: '6px 12px',
    fontSize: 12,
    cursor: 'pointer',
  },
  urlLabel: {
    fontSize: 11,
    color: '#9ca3af',
  },
  tagsRow: {
    display: 'flex',
    flexWrap: 'wrap',
    gap: 6,
  },
  tagChip: {
    fontSize: 11,
    color: '#9ca3af',
    backgroundColor: '#111525',
    borderRadius: 999,
    padding: '4px 10px',
  },
  metaPill: {
    fontSize: 11,
    color: '#9ca3af',
    backgroundColor: '#1f2937',
    padding: '4px 10px',
    borderRadius: 999,
  },
  emptyDetail: {
    fontSize: 13,
    color: '#6b7280',
  },
  loading: {
    fontSize: 13,
    color: '#9ca3af',
  },
}
