import { createClient } from '@supabase/supabase-js'

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY

export const supabase = createClient(supabaseUrl, supabaseAnonKey)

export async function getGroups() {
  const { data, error } = await supabase.from('groups').select('*').order('sort_order')
  if (error) throw error
  return data
}

export async function getCompetitors(filters = {}) {
  let query = supabase
    .from('competitors')
    .select(`
      *,
      competitor_groups(group_id, groups(id, name, color)),
      competitor_urls(id, url, label, is_active, sort_order, source_type)
    `)
    .eq('is_active', true)
    .order('name')

  if (filters.search) {
    query = query.ilike('name', `%${filters.search}%`)
  }

  const { data, error } = await query
  if (error) throw error

  return data.map(c => ({
    ...c,
    groups: c.competitor_groups?.map(cg => cg.groups) || [],
    urls: (c.competitor_urls || []).sort((a, b) => a.sort_order - b.sort_order)
  }))
}

export async function getCompetitorWithHistory(competitorId) {
  // Получаем конкурента с URLs
  const { data: competitor, error: compError } = await supabase
    .from('competitors')
    .select(`
      *,
      competitor_groups(group_id, groups(id, name, color)),
      competitor_urls(id, url, label, is_active, sort_order, source_type)
    `)
    .eq('id', competitorId)
    .single()

  if (compError) throw compError

  // Получаем историю изменений с URL
  const { data: changes, error: changesError } = await supabase
    .from('changes')
    .select('*, competitor_urls(url, label)')
    .eq('competitor_id', competitorId)
    .order('detected_at', { ascending: false })
    .limit(50)

  if (changesError) throw changesError

  // Получаем посты из Telegram-каналов
  const { data: tgPosts, error: tgError } = await supabase
    .from('competitor_tg_posts')
    .select('*')
    .eq('competitor_id', competitorId)
    .eq('is_processed', true)
    .neq('category', 'technical')
    .order('post_date', { ascending: false })
    .limit(50)

  if (tgError) throw tgError

  return {
    ...competitor,
    groups: competitor.competitor_groups?.map(cg => cg.groups) || [],
    urls: (competitor.competitor_urls || []).sort((a, b) => a.sort_order - b.sort_order),
    changes_history: changes || [],
    tg_posts: tgPosts || []
  }
}

export async function getScanReports(limit = 10) {
  const { data, error } = await supabase
    .from('summary_reports')
    .select('*')
    .order('report_date', { ascending: false })
    .limit(limit)
  if (error) throw error
  return data
}

export async function getRecentChanges(daysBack = 7, groupIds = null, changeType = null) {
  const { data, error } = await supabase.rpc('get_recent_changes', {
    p_days_back: daysBack,
    p_group_ids: groupIds,
    p_change_type: changeType
  })
  if (error) throw error
  return data
}

export async function getUserByTelegramId(telegramId) {
  const { data, error } = await supabase
    .from('users')
    .select('*')
    .eq('telegram_id', telegramId)
    .single()
  if (error && error.code !== 'PGRST116') throw error
  return data
}

export async function checkUserAccess(telegramUser) {
  const { data, error } = await supabase
    .from('users')
    .select('*')
    .eq('telegram_id', telegramUser.id)
    .single()

  if (error && error.code === 'PGRST116') {
    // Пользователь не найден в БД - доступ запрещён
    return { allowed: false, user: null }
  }
  if (error) throw error

  // Пользователь найден - обновляем last_seen_at
  await supabase
    .from('users')
    .update({ last_seen_at: new Date().toISOString() })
    .eq('telegram_id', telegramUser.id)

  return { allowed: true, user: data }
}

export async function upsertUser(telegramUser) {
  const { data, error } = await supabase
    .from('users')
    .upsert({
      telegram_id: telegramUser.id,
      telegram_username: telegramUser.username,
      display_name: telegramUser.first_name + (telegramUser.last_name ? ' ' + telegramUser.last_name : ''),
      last_seen_at: new Date().toISOString()
    }, { onConflict: 'telegram_id' })
    .select()
    .single()
  if (error) throw error
  return data
}

// === Функции для редактирования конкурентов (admin) ===

export async function updateCompetitor(competitorId, updates) {
  const { data, error } = await supabase
    .from('competitors')
    .update(updates)
    .eq('id', competitorId)
    .select()
    .single()
  if (error) throw error
  return data
}

export async function createCompetitor(name, url, description = null) {
  const { data, error } = await supabase
    .from('competitors')
    .insert({
      name,
      url,
      description,
      is_active: true
    })
    .select()
    .single()
  if (error) throw error
  return data
}

export async function addCompetitorToGroup(competitorId, groupId) {
  const { data, error } = await supabase
    .from('competitor_groups')
    .insert({ competitor_id: competitorId, group_id: groupId })
    .select()
    .single()
  if (error) throw error
  return data
}

export async function removeCompetitorFromGroup(competitorId, groupId) {
  const { error } = await supabase
    .from('competitor_groups')
    .delete()
    .eq('competitor_id', competitorId)
    .eq('group_id', groupId)
  if (error) throw error
}

export async function createGroup(name, color) {
  // Получаем максимальный sort_order
  const { data: maxData } = await supabase
    .from('groups')
    .select('sort_order')
    .order('sort_order', { ascending: false })
    .limit(1)

  const nextOrder = (maxData?.[0]?.sort_order ?? 0) + 1

  const { data, error } = await supabase
    .from('groups')
    .insert({ name, color, sort_order: nextOrder })
    .select()
    .single()
  if (error) throw error
  return data
}

export async function getCompetitorGroups(competitorId) {
  const { data, error } = await supabase
    .from('competitor_groups')
    .select('group_id, groups(id, name, color)')
    .eq('competitor_id', competitorId)
  if (error) throw error
  return data.map(cg => cg.groups)
}

export async function updateGroup(groupId, updates) {
  const { data, error } = await supabase
    .from('groups')
    .update(updates)
    .eq('id', groupId)
    .select()
    .single()
  if (error) throw error
  return data
}

export async function deleteGroup(groupId) {
  // Сначала удаляем связи с конкурентами
  const { error: linkError } = await supabase
    .from('competitor_groups')
    .delete()
    .eq('group_id', groupId)
  if (linkError) throw linkError

  // Затем удаляем саму группу
  const { error } = await supabase
    .from('groups')
    .delete()
    .eq('id', groupId)
  if (error) throw error
}

// === Функции для управления URL конкурентов ===

export async function addCompetitorUrl(competitorId, url, label = null, sourceType = 'website') {
  const { data: maxOrder } = await supabase
    .from('competitor_urls')
    .select('sort_order')
    .eq('competitor_id', competitorId)
    .order('sort_order', { ascending: false })
    .limit(1)

  const nextOrder = (maxOrder?.[0]?.sort_order ?? 0) + 1

  const { data, error } = await supabase
    .from('competitor_urls')
    .insert({ competitor_id: competitorId, url, label, sort_order: nextOrder, source_type: sourceType })
    .select()
    .single()
  if (error) throw error
  return data
}

export async function updateCompetitorUrl(urlId, updates) {
  const { data, error } = await supabase
    .from('competitor_urls')
    .update(updates)
    .eq('id', urlId)
    .select()
    .single()
  if (error) throw error
  return data
}

export async function deleteCompetitorUrl(urlId) {
  const { error } = await supabase
    .from('competitor_urls')
    .delete()
    .eq('id', urlId)
  if (error) throw error
}

export async function getCompetitorTgPostsByReport(reportId) {
  const { data, error } = await supabase
    .from('competitor_tg_posts')
    .select('*, competitors(id, name)')
    .eq('report_id', reportId)
    .eq('is_processed', true)
    .order('post_date', { ascending: false })
  if (error) throw error
  return data
}
