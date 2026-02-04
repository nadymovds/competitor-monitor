import { supabase } from './supabase'
import { getNewsPosts } from './news'

const COMPETITOR_ALLOWED_CATEGORIES = ['products', 'prices', 'services', 'news']

function computeFetchLimit(limit, offset) {
  const base = limit + offset + 20
  return Math.min(Math.max(base, 50), 500)
}

function mapWebsiteChange(row) {
  const competitor = row.competitors || {}
  const groups = (competitor.competitor_groups || []).map(link => link.groups).filter(Boolean)
  const urlInfo = row.competitor_urls || {}
  return {
    id: `change-${row.id}`,
    feedSource: 'competitors',
    sourceType: 'website',
    timestamp: row.detected_at,
    summary: row.summary,
    category: COMPETITOR_ALLOWED_CATEGORIES.includes(row.category) ? row.category : 'news',
    tags: row.tags || [],
    competitor: {
      id: competitor.id,
      name: competitor.name,
      rootUrl: competitor.url,
    },
    scannedUrl: row.scanned_url || urlInfo.url || competitor.url,
    urlLabel: urlInfo.label || null,
    groups,
  }
}

function mapTelegramChange(row) {
  return {
    id: `tg-${row.id}`,
    feedSource: 'competitors',
    sourceType: 'telegram',
    timestamp: row.post_date || row.detected_at,
    summary: row.summary || row.title || 'Без описания',
    category: COMPETITOR_ALLOWED_CATEGORIES.includes(row.category) ? row.category : 'news',
    tags: row.tags || [],
    competitor: {
      id: row.competitor_id,
      name: row.competitors?.name,
      rootUrl: row.post_url || null,
    },
    postUrl: row.post_url || null,
    channelUsername: row.channel_username || null,
    groups: [],
  }
}

function mapNewsPost(post) {
  return {
    id: `news-${post.id}`,
    feedSource: 'news',
    sourceType: post.source_type || post.channel?.source_type || 'telegram',
    timestamp: post.post_date,
    title: post.title || post.summary || 'Без заголовка',
    summary: post.content_text || post.summary || post.title || 'Без описания',
    postUrl: post.post_url || post.link || null,
    channel: post.channel || null,
    categories: post.categories || [],
    stats: {
      views: post.views_count || null,
      hasPhoto: Boolean(post.has_photo),
      hasVideo: Boolean(post.has_video),
      hasDocument: Boolean(post.has_document),
    },
  }
}

function filterCompetitorItem(item, { groupIds, sourceType, competitorCategory }) {
  if (groupIds.length > 0) {
    const groupIdsSet = new Set(groupIds)
    const belongs = item.groups.some(g => groupIdsSet.has(g?.id))
    if (!belongs) return false
  }
  if (sourceType !== 'all' && item.sourceType !== sourceType) {
    return false
  }
  if (competitorCategory !== 'all' && item.category !== competitorCategory) {
    return false
  }
  return true
}

function filterNewsItem(item, { newsCategories, newsChannels, newsSourceTypes }) {
  if (newsSourceTypes.length > 0) {
    const matchSource = newsSourceTypes.includes(item.sourceType)
    if (!matchSource) return false
  }
  if (newsChannels.length > 0) {
    const channelId = item.channel?.id
    if (!channelId || !newsChannels.includes(channelId)) return false
  }
  if (newsCategories.length > 0) {
    const assignedIds = new Set((item.categories || []).map(c => c.id))
    const intersects = newsCategories.some(id => assignedIds.has(id))
    if (!intersects) return false
  }
  return true
}

export async function getUnifiedFeed({
  feedType = 'all',
  dateFrom,
  dateTo,
  limit = 10,
  offset = 0,
  groupIds = [],
  sourceType = 'all',
  competitorCategory = 'all',
  newsCategories = [],
  newsChannels = [],
  newsSourceTypes = [],
  defaultNewsCategoryIds = [],
} = {}) {
  const fetchLimit = computeFetchLimit(limit, offset)
  const needCompetitors = feedType === 'all' || feedType === 'competitors'
  const needNews = feedType === 'all' || feedType === 'news'

  const requests = []

  if (needCompetitors) {
    let changesQuery = supabase
      .from('changes')
      .select(`
        id,
        detected_at,
        summary,
        category,
        tags,
        scanned_url,
        competitor_urls ( url, label ),
        competitors (
          id,
          name,
          url,
          competitor_groups (
            group_id,
            groups ( id, name, color )
          )
        )
      `)
      .neq('category', 'technical')
      .order('detected_at', { ascending: false })
      .limit(fetchLimit)

    if (dateFrom) changesQuery = changesQuery.gte('detected_at', dateFrom)
    if (dateTo) changesQuery = changesQuery.lte('detected_at', dateTo)

    let tgQuery = supabase
      .from('competitor_tg_posts')
      .select(`
        id,
        competitor_id,
        competitors ( id, name ),
        post_url,
        post_date,
        detected_at,
        summary,
        title,
        category,
        tags,
        channel_username
      `)
      .eq('is_processed', true)
      .in('category', COMPETITOR_ALLOWED_CATEGORIES)
      .order('post_date', { ascending: false })
      .limit(fetchLimit)

    if (dateFrom) tgQuery = tgQuery.gte('post_date', dateFrom)
    if (dateTo) tgQuery = tgQuery.lte('post_date', dateTo)

    requests.push(Promise.all([changesQuery, tgQuery]))
  } else {
    requests.push(Promise.resolve([null, null]))
  }

  if (needNews) {
    const byCategories = newsCategories.length > 0 ? newsCategories : defaultNewsCategoryIds
    requests.push(
      getNewsPosts({
        categories: byCategories,
        channels: newsChannels,
        sourceTypes: newsSourceTypes,
        dateFrom,
        dateTo,
        limit: fetchLimit,
        offset: 0,
      })
    )
  } else {
    requests.push(Promise.resolve({ posts: [] }))
  }

  const [[changesRes, tgRes], newsRes] = await Promise.all(requests)

  let competitorItems = []
  if (needCompetitors) {
    const changeItems = (changesRes?.data || []).map(mapWebsiteChange)
    const tgItems = (tgRes?.data || []).map(mapTelegramChange)
    competitorItems = [...changeItems, ...tgItems]
      .filter(item => item.timestamp)
      .sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())
      .filter(item => filterCompetitorItem(item, { groupIds, sourceType, competitorCategory }))
  }

  let newsItems = []
  if (needNews) {
    const posts = newsRes?.posts || []
    newsItems = posts
      .map(mapNewsPost)
      .filter(item => item.timestamp)
      .sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())
      .filter(item => filterNewsItem(item, { newsCategories: newsCategories.length > 0 ? newsCategories : defaultNewsCategoryIds, newsChannels, newsSourceTypes }))
  }

  let merged = []
  if (feedType === 'competitors') {
    merged = competitorItems
  } else if (feedType === 'news') {
    merged = newsItems
  } else {
    merged = [...competitorItems, ...newsItems].sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())
  }

  const sliceStart = offset
  const sliceEnd = offset + limit
  const items = merged.slice(sliceStart, sliceEnd)
  const hasMore = merged.length > sliceEnd

  return {
    items,
    hasMore,
  }
}
