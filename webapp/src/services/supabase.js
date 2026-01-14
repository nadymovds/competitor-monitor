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
    .select(`*, competitor_groups(group_id, groups(id, name, color))`)
    .eq('is_active', true)
    .order('name')

  if (filters.search) {
    query = query.ilike('name', `%${filters.search}%`)
  }

  const { data, error } = await query
  if (error) throw error
  
  return data.map(c => ({
    ...c,
    groups: c.competitor_groups?.map(cg => cg.groups) || []
  }))
}

export async function getCompetitorWithHistory(competitorId) {
  const { data, error } = await supabase.rpc('get_competitor_with_groups', { p_competitor_id: competitorId })
  if (error) throw error
  return data?.[0] || null
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
