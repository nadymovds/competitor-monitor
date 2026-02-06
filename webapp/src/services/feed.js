import { supabase } from './supabase.js'

/**
 * Получить объединённую ленту обновлений (конкуренты + новости)
 * @param {Object} params - Параметры запроса
 * @param {string} params.feedType - 'all' | 'competitors' | 'news'
 * @param {string} [params.dateFrom] - Дата начала (ISO string)
 * @param {string} [params.dateTo] - Дата окончания (ISO string)
 * @param {number} [params.limit=10] - Количество элементов
 * @param {number} [params.offset=0] - Смещение для пагинации
 * @param {number[]} [params.groupIds] - ID групп конкурентов (для feedType='competitors')
 * @param {string} [params.sourceType] - 'all' | 'website' | 'telegram' (для feedType='competitors')
 * @param {string} [params.competitorCategory] - 'all' | 'products' | 'prices' | 'services' | 'news'
 * @param {number[]} [params.newsCategories] - ID категорий новостей (для feedType='news')
 * @param {number[]} [params.newsChannels] - ID каналов новостей (для feedType='news')
 * @param {string[]} [params.newsSourceTypes] - ['telegram', 'website'] (для feedType='news')
 * @returns {Promise<{items: FeedItem[], hasMore: boolean}>}
 */
export async function getUnifiedFeed({
  feedType,
  dateFrom,
  dateTo,
  limit = 10,
  offset = 0,
  groupIds = [],
  sourceType = 'all',
  competitorCategory = 'all',
  newsCategories = [],
  newsChannels = [],
  newsSourceTypes = []
}) {
  let allItems = []

  if (feedType === 'all' || feedType === 'competitors') {
    // Получаем изменения с сайтов конкурентов
    const websiteChanges = await getCompetitorWebsiteChanges({
      dateFrom,
      dateTo,
      groupIds,
      sourceType: sourceType === 'telegram' ? null : 'website',
      category: competitorCategory
    })

    // Получаем посты из TG-каналов конкурентов
    const tgPosts = await getCompetitorTgPosts({
      dateFrom,
      dateTo,
      groupIds,
      sourceType: sourceType === 'website' ? null : 'telegram',
      category: competitorCategory
    })

    allItems = [...websiteChanges, ...tgPosts]
  }

  if (feedType === 'all' || feedType === 'news') {
    // Получаем новости отрасли
    const newsPosts = await getIndustryNews({
      dateFrom,
      dateTo,
      categories: newsCategories,
      channels: newsChannels,
      sourceTypes: newsSourceTypes
    })

    allItems = [...allItems, ...newsPosts]
  }

  // Сортируем по дате (новые первые)
  allItems.sort((a, b) => new Date(b.detected_at) - new Date(a.detected_at))

  // Применяем пагинацию
  const paginatedItems = allItems.slice(offset, offset + limit)
  const hasMore = allItems.length > offset + limit

  return { items: paginatedItems, hasMore }
}

/**
 * Получить изменения с веб-сайтов конкурентов
 */
async function getCompetitorWebsiteChanges({ dateFrom, dateTo, groupIds, sourceType, category }) {
  if (!sourceType || sourceType !== 'website') return []

  let query = supabase
    .from('changes')
    .select(`
      *,
      competitors (
        id, 
        name, 
        url,
        competitor_groups(group_id, groups(id, name, color))
      ),
      competitor_urls (url, label)
    `)
    .eq('is_meaningful', true)
    .neq('category', 'technical')

  if (dateFrom) query = query.gte('detected_at', dateFrom)
  if (dateTo) query = query.lte('detected_at', dateTo)
  if (category && category !== 'all') query = query.eq('category', category)

  const { data, error } = await query
  if (error) throw error

  // Фильтруем по группам (если указаны)
  let filtered = data || []
  if (groupIds.length > 0) {
    filtered = filtered.filter(item => {
      const itemGroups = item.competitors?.competitor_groups?.map(cg => cg.group_id) || []
      return itemGroups.some(gid => groupIds.includes(gid))
    })
  }

  return filtered.map(item => ({
    id: `change_${item.id}`,
    type: 'competitor_change',
    source_type: 'website',
    competitor_id: item.competitors?.id,
    competitor_name: item.competitors?.name,
    competitor_url: item.competitors?.url,
    scanned_url: item.scanned_url || item.competitor_urls?.url,
    url_label: item.competitor_urls?.label,
    category: item.category,
    summary: item.summary,
    tags: item.tags || [],
    detected_at: item.detected_at,
    groups: item.competitors?.competitor_groups?.map(cg => cg.groups) || []
  }))
}

/**
 * Получить посты из Telegram-каналов конкурентов
 */
async function getCompetitorTgPosts({ dateFrom, dateTo, groupIds, sourceType, category }) {
  if (!sourceType || sourceType !== 'telegram') return []

  let query = supabase
    .from('competitor_tg_posts')
    .select(`
      *,
      competitors (
        id,
        name,
        competitor_groups(group_id, groups(id, name, color))
      )
    `)
    .eq('is_processed', true)
    .neq('category', 'technical')

  if (dateFrom) query = query.gte('post_date', dateFrom)
  if (dateTo) query = query.lte('post_date', dateTo)
  if (category && category !== 'all') query = query.eq('category', category)

  const { data, error } = await query
  if (error) throw error

  // Фильтруем по группам (если указаны)
  let filtered = data || []
  if (groupIds.length > 0) {
    filtered = filtered.filter(item => {
      const itemGroups = item.competitors?.competitor_groups?.map(cg => cg.group_id) || []
      return itemGroups.some(gid => groupIds.includes(gid))
    })
  }

  return filtered.map(item => ({
    id: `tg_${item.id}`,
    type: 'competitor_tg',
    source_type: 'telegram',
    competitor_id: item.competitor_id,
    competitor_name: item.competitors?.name,
    post_url: item.post_url,
    channel_username: item.channel_username,
    category: item.category,
    summary: item.content_text || item.summary || item.title || 'Нет описания',
    tags: item.tags || [],
    detected_at: item.post_date || item.detected_at,
    groups: item.competitors?.competitor_groups?.map(cg => cg.groups) || []
  }))
}

/**
 * Получить новости отрасли
 */
async function getIndustryNews({ dateFrom, dateTo, categories, channels, sourceTypes }) {
  const categoryJoin = categories.length > 0
    ? 'news_post_categories!inner(category_id, confidence, is_manual, news_categories(id, name, color, is_visible, sort_order))'
    : 'news_post_categories(category_id, confidence, is_manual, news_categories(id, name, color, is_visible, sort_order))'

  const channelsJoin = sourceTypes.length > 0
    ? 'news_channels!inner(id, username, title, source_type)'
    : 'news_channels(id, username, title, source_type)'

  let query = supabase
    .from('news_posts')
    .select(`
      *,
      ${channelsJoin},
      ${categoryJoin}
    `)
    .eq('is_processed', true)

  if (categories.length > 0) {
    query = query.in('news_post_categories.category_id', categories)
  }

  if (channels.length > 0) {
    query = query.in('channel_id', channels)
  }

  if (sourceTypes.length > 0) {
    query = query.in('news_channels.source_type', sourceTypes)
  }

  if (dateFrom) query = query.gte('post_date', dateFrom)
  if (dateTo) query = query.lte('post_date', dateTo)

  const { data, error } = await query
  if (error) throw error

  // Дедупликация по content_hash
  const seenHashes = new Set()
  const uniquePosts = (data || []).filter(post => {
    const hash = post.content_hash
    if (!hash) return true
    if (seenHashes.has(hash)) return false
    seenHashes.add(hash)
    return true
  })

  return uniquePosts.map(post => ({
    id: `news_${post.id}`,
    type: 'industry_news',
    source_type: post.news_channels?.source_type || 'telegram',
    channel_id: post.channel_id,
    channel: {
      id: post.news_channels?.id,
      title: post.news_channels?.title,
      username: post.news_channels?.username,
      source_type: post.news_channels?.source_type
    },
    post_url: post.post_url,
    title: post.title || '',
    content_text: post.content_text || '',
    summary: post.summary || '',
    post_date: post.post_date,
    has_photo: post.has_photo,
    has_video: post.has_video,
    has_document: post.has_document,
    views_count: post.views_count,
    tags: post.tags || [],
    detected_at: post.post_date,
    categories: (post.news_post_categories || [])
      .map(pc => ({
        ...pc.news_categories,
        confidence: pc.confidence,
        is_manual: pc.is_manual
      }))
      .filter(cat => cat.is_visible !== false)
  }))
}

/**
 * Получить дату последнего сканирования (самое позднее из всех источников)
 * @returns {Promise<string|null>} - Дата последнего сканирования в ISO формате
 */
export async function getLastScanDate() {
  try {
    // Получаем последнее изменение с сайтов конкурентов
    const { data: lastChange } = await supabase
      .from('changes')
      .select('detected_at')
      .order('detected_at', { ascending: false })
      .limit(1)
      .single()

    // Получаем последний пост из TG-каналов конкурентов
    const { data: lastTgPost } = await supabase
      .from('competitor_tg_posts')
      .select('post_date, detected_at')
      .order('post_date', { ascending: false })
      .limit(1)
      .single()

    // Получаем последнюю новость отрасли
    const { data: lastNews } = await supabase
      .from('news_posts')
      .select('post_date')
      .order('post_date', { ascending: false })
      .limit(1)
      .single()

    // Собираем все даты
    const dates = []
    if (lastChange?.detected_at) dates.push(new Date(lastChange.detected_at))
    if (lastTgPost?.post_date) dates.push(new Date(lastTgPost.post_date))
    if (lastTgPost?.detected_at) dates.push(new Date(lastTgPost.detected_at))
    if (lastNews?.post_date) dates.push(new Date(lastNews.post_date))

    // Находим самую позднюю дату
    if (dates.length === 0) return null
    
    const latestDate = new Date(Math.max(...dates))
    return latestDate.toISOString()
  } catch (err) {
    console.error('Failed to get last scan date:', err)
    return null
  }
}
