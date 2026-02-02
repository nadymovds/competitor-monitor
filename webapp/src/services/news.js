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
    .select('id, username, title, is_active, last_scan_at')
    .eq('is_active', true)
    .order('title')
  if (error) throw error
  return data
}

export async function getAllNewsChannels() {
  const { data, error } = await supabase
    .from('news_channels')
    .select('id, username, title, is_active')
    .order('title')
  if (error) throw error
  return data
}

export async function getNewsPosts({ categories = [], channels = [], dateFrom, dateTo, limit = 20, offset = 0 } = {}) {
  const categoryJoin = categories.length > 0
    ? 'news_post_categories!inner(category_id, confidence, is_manual, news_categories(id, name, color, is_visible, sort_order))'
    : 'news_post_categories(category_id, confidence, is_manual, news_categories(id, name, color, is_visible, sort_order))'

  let query = supabase
    .from('news_posts')
    .select(`
      *,
      news_channels(id, username, title),
      ${categoryJoin}
    `, { count: 'exact' })
    .eq('is_processed', true)

  if (categories.length > 0) {
    query = query.in('news_post_categories.category_id', categories)
  }

  if (channels.length > 0) {
    query = query.in('channel_id', channels)
  }

  if (dateFrom) {
    query = query.gte('post_date', dateFrom)
  }

  if (dateTo) {
    query = query.lte('post_date', dateTo)
  }

  query = query
    .order('post_date', { ascending: false })
    .range(offset, offset + limit - 1)

  const { data, count, error } = await query
  if (error) throw error

  const posts = data.map(post => ({
    ...post,
    channel: post.news_channels,
    categories: (post.news_post_categories || [])
      .map(pc => ({
        ...pc.news_categories,
        confidence: pc.confidence,
        is_manual: pc.is_manual,
      }))
      .filter(cat => cat.is_visible !== false)
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

export async function createChannel({ username, title }) {
  const cleanUsername = username.replace(/^@/, '')
  const { data, error } = await supabase
    .from('news_channels')
    .insert({
      username: cleanUsername,
      title: title || null
    })
    .select()
    .single()
  if (error) throw error
  return data
}

export async function updateChannel(channelId, { username, title, isActive }) {
  const updates = { updated_at: new Date().toISOString() }
  if (username !== undefined) updates.username = username.replace(/^@/, '')
  if (title !== undefined) updates.title = title
  if (isActive !== undefined) updates.is_active = isActive

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
