import React, { useState, useEffect, useMemo } from 'react'
import { getScanReports, getRecentChanges } from '../../services/supabase'
import { openLink, hapticFeedback } from '../../services/telegram'

export default function MonitoringScreen({ user, groups, onNavigateToCompetitor }) {
  const [reports, setReports] = useState([])
  const [changes, setChanges] = useState([])
  const [loading, setLoading] = useState(true)
  const [selectedGroups, setSelectedGroups] = useState([])
  const [activeCategory, setActiveCategory] = useState('all')

  useEffect(() => {
    async function loadData() {
      try {
        setLoading(true)
        const [reportsData, changesData] = await Promise.all([getScanReports(5), getRecentChanges(30)])
        setReports(reportsData)
        setChanges(changesData)
      } catch (err) {
        console.error('Load error:', err)
      } finally {
        setLoading(false)
      }
    }
    loadData()
  }, [])

  const lastReport = reports[0]

  const filteredChanges = useMemo(() => {
    let result = changes
    if (selectedGroups.length > 0) {
      result = result.filter(c => (c.groups || []).some(g => selectedGroups.includes(g.id)))
    }
    if (activeCategory !== 'all') {
      result = result.filter(c => c.change_type === activeCategory)
    }
    return result
  }, [changes, selectedGroups, activeCategory])

  const categoryCounts = useMemo(() => {
    const filtered = selectedGroups.length > 0 ? changes.filter(c => (c.groups || []).some(g => selectedGroups.includes(g.id))) : changes
    return {
      all: filtered.length,
      products: filtered.filter(c => c.change_type === 'products').length,
      news: filtered.filter(c => c.change_type === 'news').length,
      technical: filtered.filter(c => c.change_type === 'technical').length
    }
  }, [changes, selectedGroups])

  const toggleGroup = (id) => { hapticFeedback('light'); setSelectedGroups(prev => prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]) }
  const resetFilters = () => { hapticFeedback('light'); setSelectedGroups([]) }

  if (loading) return <div style={{ padding: 20, textAlign: 'center', color: '#6b7280' }}>Загрузка...</div>

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <h1 style={{ fontSize: 24, fontWeight: 700, margin: 0 }}>Мониторинг</h1>

      {lastReport && (
        <div style={{ backgroundColor: '#1a1a24', borderRadius: 12, padding: 16 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 12 }}>
            <span style={{ fontSize: 14, fontWeight: 600 }}>{formatDate(lastReport.report_date)}</span>
            <span style={{ fontSize: 12, color: '#6b7280' }}>{lastReport.duration_seconds ? `${Math.floor(lastReport.duration_seconds/60)}м ${lastReport.duration_seconds%60}с` : ''}</span>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, textAlign: 'center' }}>
            <div><div style={{ fontSize: 20, fontWeight: 700, color: '#6b7280' }}>{lastReport.total_sites || 0}</div><div style={{ fontSize: 11, color: '#6b7280' }}>Сайтов</div></div>
            <div><div style={{ fontSize: 20, fontWeight: 700, color: '#22c55e' }}>{lastReport.successful_sites || 0}</div><div style={{ fontSize: 11, color: '#6b7280' }}>Успешно</div></div>
            <div><div style={{ fontSize: 20, fontWeight: 700, color: '#3b82f6' }}>{lastReport.changes_count || 0}</div><div style={{ fontSize: 11, color: '#6b7280' }}>Изменений</div></div>
            <div><div style={{ fontSize: 20, fontWeight: 700, color: '#ef4444' }}>{lastReport.problems_count || 0}</div><div style={{ fontSize: 11, color: '#6b7280' }}>Проблем</div></div>
          </div>
        </div>
      )}

      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <span style={{ fontSize: 14, color: '#9ca3af' }}>Фильтр по группам</span>
          {selectedGroups.length > 0 && <button onClick={resetFilters} style={{ fontSize: 12, color: '#3b82f6', background: 'none', border: 'none' }}>Сбросить</button>}
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          {groups.map(g => (
            <button key={g.id} onClick={() => toggleGroup(g.id)} style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '8px 12px', borderRadius: 20, backgroundColor: selectedGroups.includes(g.id) ? g.color + '20' : '#252532', border: selectedGroups.includes(g.id) ? `1px solid ${g.color}` : '1px solid transparent', cursor: 'pointer' }}>
              <span style={{ width: 8, height: 8, borderRadius: '50%', backgroundColor: g.color }} />
              <span style={{ fontSize: 13, color: '#fff' }}>{g.name}</span>
            </button>
          ))}
        </div>
      </div>

      <div style={{ display: 'flex', gap: 8, overflowX: 'auto' }}>
        {[{ id: 'all', label: 'Все' }, { id: 'products', label: 'Продукты' }, { id: 'news', label: 'Новости' }, { id: 'technical', label: 'Тех.' }].map(cat => (
          <button key={cat.id} onClick={() => { hapticFeedback('light'); setActiveCategory(cat.id) }} style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '8px 14px', borderRadius: 8, backgroundColor: activeCategory === cat.id ? '#3b82f6' : '#252532', color: activeCategory === cat.id ? '#fff' : '#9ca3af', fontSize: 13, fontWeight: 500, whiteSpace: 'nowrap', cursor: 'pointer' }}>
            {cat.label} <span style={{ opacity: 0.7, fontSize: 12 }}>{categoryCounts[cat.id]}</span>
          </button>
        ))}
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {filteredChanges.length === 0 ? (
          <div style={{ textAlign: 'center', padding: 40, color: '#6b7280' }}>📭 Нет изменений</div>
        ) : filteredChanges.map((c, i) => (
          <div key={i} style={{ backgroundColor: '#1a1a24', borderRadius: 12, padding: 14 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 10 }}>
              <div>
                <button onClick={() => onNavigateToCompetitor(c.competitor_id)} style={{ fontSize: 15, fontWeight: 600, color: '#fff', background: 'none', border: 'none', padding: 0, textAlign: 'left', cursor: 'pointer', textDecoration: 'underline', textDecorationColor: 'rgba(255,255,255,0.3)' }}>{c.competitor_name}</button>
                <button onClick={() => openLink(`https://${c.competitor_url}`)} style={{ display: 'block', fontSize: 12, color: '#3b82f6', background: 'none', border: 'none', padding: 0, marginTop: 4, cursor: 'pointer' }}>🌐 {c.competitor_url}</button>
              </div>
              <span style={{ fontSize: 11, fontWeight: 500, padding: '4px 8px', borderRadius: 4, backgroundColor: c.change_type === 'products' ? '#22c55e20' : c.change_type === 'news' ? '#f59e0b20' : '#6b728020', color: c.change_type === 'products' ? '#22c55e' : c.change_type === 'news' ? '#f59e0b' : '#6b7280' }}>
                {c.change_type === 'products' ? 'Продукт' : c.change_type === 'news' ? 'Новость' : 'Тех.'}
              </span>
            </div>
            <div style={{ fontSize: 14, color: '#d1d5db', lineHeight: 1.5 }}>{c.summary}</div>
            {c.groups?.length > 0 && (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 10 }}>
                {c.groups.map(g => <span key={g.id} style={{ fontSize: 11, padding: '3px 8px', borderRadius: 4, backgroundColor: g.color + '20', color: g.color }}>{g.name}</span>)}
              </div>
            )}
            <div style={{ fontSize: 12, color: '#6b7280', marginTop: 10 }}>{formatDate(c.scan_date)}</div>
          </div>
        ))}
      </div>
    </div>
  )
}

function formatDate(d) {
  if (!d) return ''
  return new Date(d).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short', year: 'numeric' })
}
