import { supabase } from './supabase.js'

export async function getMentions({
  limit = 10,
  offset = 0,
  dateFrom,
  dateTo,
  sourceTypes = [],
  sentiments = []
} = {}) {
  let query = supabase
    .from('mentions')
    .select('*', { count: 'exact' })

  if (sourceTypes.length > 0) {
    query = query.in('source_type', sourceTypes)
  }

  if (sentiments.length > 0) {
    query = query.in('sentiment', sentiments)
  }

  if (dateFrom) {
    query = query.gte('post_date', dateFrom)
  }

  if (dateTo) {
    query = query.lte('post_date', dateTo)
  }

  query = query
    .order('post_date', { ascending: false, nullsFirst: false })
    .order('created_at', { ascending: false })
    .range(offset, offset + limit - 1)

  const { data, count, error } = await query
  if (error) throw error

  return {
    items: data || [],
    hasMore: (count || 0) > offset + limit
  }
}
