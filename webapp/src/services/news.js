import { supabase } from './supabase.js'

export async function getNewsCategories() {
  const { data, error } = await supabase
    .from('news_categories')
    .select('id, name, description, color, is_visible, sort_order')
    .order('sort_order')
  if (error) throw error
  return data
}

export async function getNewsChannels() {
  const { data, error } = await supabase
    .from('news_channels')
    .select('id, username, title, is_active, last_scan_at, source_type, url, css_config')
    .eq('is_active', true)
    .order('title')
  if (error) throw error
  return data
}

export async function getAllNewsChannels() {
  const { data, error } = await supabase
    .from('news_channels')
    .select('id, username, title, is_active, source_type, url, css_config')
    .order('title')
  if (error) throw error
  return data
}

export async function getNewsPosts({ categories = [], channels = [], sourceTypes = [], searchQuery = '', dateFrom, dateTo, limit = 20, offset = 0 } = {}) {
  // Всегда используем inner join — посты без категорий (нерелевантные) не показываем
  const categoryJoin = 'news_post_categories!inner(category_id, confidence, is_manual, news_categories(id, name, color, is_visible, sort_order))'

  // Use inner join when filtering by source_type
  const channelsJoin = sourceTypes.length > 0
    ? 'news_channels!inner(id, username, title, source_type)'
    : 'news_channels(id, username, title, source_type)'

  let query = supabase
    .from('news_posts')
    .select(`
      *,
      ${channelsJoin},
      ${categoryJoin}
    `, { count: 'exact' })
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

  if (dateFrom) {
    query = query.gte('post_date', dateFrom)
  }

  if (dateTo) {
    query = query.lte('post_date', dateTo)
  }

  // Добавляем фильтр поиска
  if (searchQuery.trim()) {
    const searchTerm = `%${searchQuery}%`
    query = query.or(`title.ilike.${searchTerm},content_text.ilike.${searchTerm},summary.ilike.${searchTerm}`, { foreignTable: '' })
  }

  query = query
    .order('post_date', { ascending: false })
    .range(offset, offset + limit - 1)

  const { data, count, error } = await query
  if (error) throw error

  const posts = data.map(post => ({
    ...post,
    channel: post.news_channels,
    source_type: post.news_channels?.source_type || 'telegram',
    categories: (() => {
      const visible = (post.news_post_categories || [])
        .map(pc => ({
          ...pc.news_categories,
          confidence: pc.confidence,
          is_manual: pc.is_manual,
        }))
        .filter(cat => cat.is_visible !== false)
      return visible.length > 0
        ? visible
        : [{ id: null, name: 'Прочее', color: '#888888', is_visible: true }]
    })()
  }))

  // Дедупликация по content_hash — одинаковый контент показываем только один раз
  const seenHashes = new Set()
  const uniquePosts = posts.filter(post => {
    const hash = post.content_hash
    if (!hash) return true
    if (seenHashes.has(hash)) return false
    seenHashes.add(hash)
    return true
  })

  return { posts: uniquePosts, count }
}

export async function addPostCategory(postId, categoryId) {
  const { data, error } = await supabase
    .from('news_post_categories')
    .upsert(
      { post_id: postId, category_id: categoryId, is_manual: true },
      { onConflict: 'post_id, category_id' }
    )
    .select()
    .single()
  if (error) throw error
  return data
}

export async function removePostCategory(postId, categoryId) {
  const { error } = await supabase
    .from('news_post_categories')
    .delete()
    .eq('post_id', postId)
    .eq('category_id', categoryId)
  if (error) throw error
}

export async function createCategory({ name, color, description }) {
  const { data: maxOrder } = await supabase
    .from('news_categories')
    .select('sort_order')
    .order('sort_order', { ascending: false })
    .limit(1)
    .single()

  const { data, error } = await supabase
    .from('news_categories')
    .insert({
      name,
      color: color || '#6B7280',
      description: description || null,
      sort_order: (maxOrder?.sort_order || 0) + 1
    })
    .select()
    .single()
  if (error) throw error
  return data
}

export async function updateCategory(categoryId, { name, color, description }) {
  const updates = { updated_at: new Date().toISOString() }
  if (name !== undefined) updates.name = name
  if (color !== undefined) updates.color = color
  if (description !== undefined) updates.description = description

  const { data, error } = await supabase
    .from('news_categories')
    .update(updates)
    .eq('id', categoryId)
    .select()
    .single()
  if (error) throw error
  return data
}

export async function toggleCategoryVisibility(categoryId, isVisible) {
  const { data, error } = await supabase
    .from('news_categories')
    .update({ is_visible: isVisible, updated_at: new Date().toISOString() })
    .eq('id', categoryId)
    .select()
    .single()
  if (error) throw error
  return data
}

export async function deleteCategory(categoryId) {
  // Move posts to "Прочее" category before deleting
  const { data: otherCategory } = await supabase
    .from('news_categories')
    .select('id')
    .eq('name', 'Прочее')
    .single()

  if (otherCategory) {
    // Get posts in the category being deleted
    const { data: postCategories } = await supabase
      .from('news_post_categories')
      .select('post_id')
      .eq('category_id', categoryId)

    if (postCategories?.length > 0) {
      const postIds = postCategories.map(pc => pc.post_id)
      // Add "Прочее" category to those posts (upsert to avoid duplicates)
      for (const postId of postIds) {
        await supabase
          .from('news_post_categories')
          .upsert(
            { post_id: postId, category_id: otherCategory.id, is_manual: true },
            { onConflict: 'post_id, category_id' }
          )
      }
    }
  }

  const { error } = await supabase
    .from('news_categories')
    .delete()
    .eq('id', categoryId)
  if (error) throw error
}

export async function createChannel({ username, title, sourceType = 'telegram', url, cssConfig }) {
  const insertData = {
    title: title || null,
    source_type: sourceType
  }

  if (sourceType === 'telegram') {
    insertData.username = username?.replace(/^@/, '') || null
  } else {
    // website
    insertData.url = url || null
    insertData.css_config = cssConfig || null
    insertData.username = null
  }

  const { data, error } = await supabase
    .from('news_channels')
    .insert(insertData)
    .select()
    .single()
  if (error) throw error
  return data
}

export async function updateChannel(channelId, { username, title, isActive, url, cssConfig }) {
  const updates = { updated_at: new Date().toISOString() }
  if (username !== undefined) updates.username = username?.replace(/^@/, '') || null
  if (title !== undefined) updates.title = title
  if (isActive !== undefined) updates.is_active = isActive
  if (url !== undefined) updates.url = url
  if (cssConfig !== undefined) updates.css_config = cssConfig

  const { data, error } = await supabase
    .from('news_channels')
    .update(updates)
    .eq('id', channelId)
    .select()
    .single()
  if (error) throw error
  return data
}

export async function deleteChannel(channelId) {
  const { error } = await supabase
    .from('news_channels')
    .delete()
    .eq('id', channelId)
  if (error) throw error
}

// === Функции для страницы "Сканирования" ===

export async function getNewsDigests(limit = 10, offset = 0) {
  const twoMonthsAgo = new Date()
  twoMonthsAgo.setMonth(twoMonthsAgo.getMonth() - 2)

  const { data, error, count } = await supabase
    .from('news_digests')
    .select('*', { count: 'exact' })
    .gte('created_at', twoMonthsAgo.toISOString())
    .order('created_at', { ascending: false })
    .range(offset, offset + limit - 1)

  if (error) throw error

  // Подсчитываем количество каналов для каждого дайджеста
  const digestsWithStats = await Promise.all((data || []).map(async (digest) => {
    // Получаем уникальные каналы из постов дайджеста
    const { data: posts } = await supabase
      .from('news_digest_posts')
      .select('post_id, news_posts!inner(channel_id)')
      .eq('digest_id', digest.id)
    
    const uniqueChannels = new Set(posts?.map(p => p.news_posts?.channel_id).filter(Boolean) || [])
    
    return {
      ...digest,
      total_posts: digest.posts_count || 0,
      total_channels: uniqueChannels.size,
      period_days: Math.ceil((new Date(digest.period_end) - new Date(digest.period_start)) / (1000 * 60 * 60 * 24))
    }
  }))

  return {
    digests: digestsWithStats,
    hasMore: (count || 0) > offset + limit
  }
}

export async function getNewsDigestDetails(digestId) {
  // Получаем посты через связующую таблицу news_digest_posts
  const { data: digestPosts, error: digestError } = await supabase
    .from('news_digest_posts')
    .select('post_id, rank_in_category')
    .eq('digest_id', digestId)
    .order('rank_in_category', { ascending: true })

  if (digestError) throw digestError

  if (!digestPosts || digestPosts.length === 0) {
    return { posts: [] }
  }

  // Получаем полную информацию о постах
  const postIds = digestPosts.map(dp => dp.post_id)
  
  const { data, error } = await supabase
    .from('news_posts')
    .select(`
      *,
      news_channels (id, username, title, source_type),
      news_post_categories (
        category_id,
        confidence,
        is_manual,
        news_categories (id, name, color, is_visible)
      )
    `)
    .in('id', postIds)
    .order('post_date', { ascending: false })

  if (error) throw error

  // Форматируем посты
  const posts = (data || []).map(post => ({
    ...post,
    channel: post.news_channels,
    source_type: post.news_channels?.source_type || 'telegram',
    categories: (() => {
      const visible = (post.news_post_categories || [])
        .map(pc => ({
          ...pc.news_categories,
          confidence: pc.confidence,
          is_manual: pc.is_manual
        }))
        .filter(cat => cat.is_visible !== false)
      return visible.length > 0
        ? visible
        : [{ id: null, name: 'Прочее', color: '#888888', is_visible: true }]
    })()
  }))

  return { posts }
}
