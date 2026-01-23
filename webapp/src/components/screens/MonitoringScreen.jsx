import React, { useState, useEffect, useMemo } from 'react'
import { getScanReports, supabase } from '../../services/supabase'
import { openLink, hapticFeedback } from '../../services/telegram'

export default function MonitoringScreen({ user, groups, onNavigateToCompetitor }) {
  const [reports, setReports] = useState([])
  const [loading, setLoading] = useState(true)
  const [expandedReportId, setExpandedReportId] = useState(null)
  const [reportChanges, setReportChanges] = useState({})
  const [selectedGroups, setSelectedGroups] = useState([])
  const [activeCategory, setActiveCategory] = useState('all')

  // Загрузка отчётов
  useEffect(() => {
    async function loadData() {
      try {
        setLoading(true)
        const reportsData = await getScanReports(10)
        setReports(reportsData)
        
        // Автоматически раскрываем последний отчёт
        if (reportsData.length > 0) {
          const lastReport = reportsData[0]
          setExpandedReportId(lastReport.id)
          loadReportChanges(lastReport.id)
        }
      } catch (err) {
        console.error('Load error:', err)
      } finally {
        setLoading(false)
      }
    }
    loadData()
  }, [])

  // Загрузка изменений для конкретного отчёта
  const loadReportChanges = async (reportId) => {
    if (reportChanges[reportId]) return // Уже загружено
    
    try {
      const { data, error } = await supabase
        .from('scan_results')
        .select(`
          *,
          competitors (id, name, url, competitor_groups(group_id, groups(id, name, color)))
        `)
        .eq('report_id', reportId)
        .eq('content_changed', true)
      
      if (error) throw error
      
      // Преобразуем данные
      const changes = data.map(item => ({
        ...item,
        competitor_id: item.competitors?.id,
        competitor_name: item.competitors?.name,
        competitor_url: item.competitors?.url,
        groups: item.competitors?.competitor_groups?.map(cg => cg.groups) || [],
        parsed_summary: parseLlmSummary(item.llm_summary)
      }))
      
      setReportChanges(prev => ({ ...prev, [reportId]: changes }))
    } catch (err) {
      console.error('Load changes error:', err)
    }
  }

  // Парсинг llm_summary (может быть JSON или текст)
  const parseLlmSummary = (summary) => {
    if (!summary) return { summary: '', category: null, tags: [] }
    
    // Убираем markdown код-блоки если есть
    let cleaned = summary.trim()
    if (cleaned.startsWith('```')) {
      cleaned = cleaned.replace(/^```\w*\n?/, '').replace(/\n?```$/, '')
    }
    
    try {
      const parsed = JSON.parse(cleaned)
      return {
        summary: parsed.summary || parsed.description || cleaned,
        category: parsed.category || null,
        tags: parsed.tags || []
      }
    } catch {
      // Если не JSON — возвращаем как есть
      return { summary: summary, category: null, tags: [] }
    }
  }

  // Переключение раскрытия отчёта
  const toggleReport = (reportId) => {
    hapticFeedback('light')
    if (expandedReportId === reportId) {
      setExpandedReportId(null)
    } else {
      setExpandedReportId(reportId)
      loadReportChanges(reportId)
    }
  }

  // Фильтрация изменений
  const getFilteredChanges = (reportId) => {
    const changes = reportChanges[reportId] || []
    let result = changes

    if (selectedGroups.length > 0) {
      result = result.filter(c => (c.groups || []).some(g => selectedGroups.includes(g.id)))
    }

    if (activeCategory !== 'all') {
      result = result.filter(c => {
        const category = c.parsed_summary?.category || c.change_type
        return category === activeCategory
      })
    }

    return result
  }

  // Подсчёт по категориям для текущего отчёта
  const getCategoryCounts = (reportId) => {
    const changes = reportChanges[reportId] || []
    const filtered = selectedGroups.length > 0 
      ? changes.filter(c => (c.groups || []).some(g => selectedGroups.includes(g.id)))
      : changes

    return {
      all: filtered.length,
      products: filtered.filter(c => (c.parsed_summary?.category || c.change_type) === 'products').length,
      news: filtered.filter(c => (c.parsed_summary?.category || c.change_type) === 'news').length,
      technical: filtered.filter(c => (c.parsed_summary?.category || c.change_type) === 'technical').length
    }
  }

  const toggleGroup = (id) => { 
    hapticFeedback('light')
    setSelectedGroups(prev => prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]) 
  }
  
  const resetFilters = () => { 
    hapticFeedback('light')
    setSelectedGroups([]) 
  }

  if (loading) return <div style={{ padding: 20, textAlign: 'center', color: '#6b7280' }}>Загрузка...</div>

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <h1 style={{ fontSize: 24, fontWeight: 700, margin: 0 }}>Мониторинг</h1>

      {/* Фильтр по группам */}
      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <span style={{ fontSize: 14, color: '#9ca3af' }}>Фильтр по группам</span>
          {selectedGroups.length > 0 && (
            <button onClick={resetFilters} style={{ fontSize: 12, color: '#3b82f6', background: 'none', border: 'none', cursor: 'pointer' }}>
              Сбросить
            </button>
          )}
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          {groups.map(g => (
            <button 
              key={g.id} 
              onClick={() => toggleGroup(g.id)} 
              style={{ 
                display: 'flex', alignItems: 'center', gap: 6, padding: '8px 12px', borderRadius: 20, 
                backgroundColor: selectedGroups.includes(g.id) ? g.color + '20' : '#252532', 
                border: selectedGroups.includes(g.id) ? `1px solid ${g.color}` : '1px solid transparent', 
                cursor: 'pointer' 
              }}
            >
              <span style={{ width: 8, height: 8, borderRadius: '50%', backgroundColor: g.color }} />
              <span style={{ fontSize: 13, color: '#fff' }}>{g.name}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Список сканирований */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {reports.length === 0 ? (
          <div style={{ textAlign: 'center', padding: 40, color: '#6b7280' }}>📭 Нет сканирований</div>
        ) : (
          reports.map(report => {
            const isExpanded = expandedReportId === report.id
            const changes = reportChanges[report.id] || []
            const filteredChanges = getFilteredChanges(report.id)
            const categoryCounts = getCategoryCounts(report.id)
            
            return (
              <div key={report.id} style={{ backgroundColor: '#1a1a24', borderRadius: 12, overflow: 'hidden' }}>
                {/* Заголовок отчёта (кликабельный) */}
                <button 
                  onClick={() => toggleReport(report.id)}
                  style={{ 
                    width: '100%', padding: 16, background: 'none', border: 'none', 
                    cursor: 'pointer', textAlign: 'left' 
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                    <span style={{ fontSize: 15, fontWeight: 600, color: '#fff' }}>
                      {formatDate(report.report_date)}
                    </span>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      {report.duration_seconds && (
                        <span style={{ fontSize: 12, color: '#6b7280' }}>
                          {Math.floor(report.duration_seconds / 60)}м {report.duration_seconds % 60}с
                        </span>
                      )}
                      <span style={{ 
                        fontSize: 18, color: '#6b7280', 
                        transform: isExpanded ? 'rotate(180deg)' : 'rotate(0)', 
                        transition: 'transform 0.2s' 
                      }}>
                        ▼
                      </span>
                    </div>
                  </div>
                  
                  {/* Статистика */}
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8, textAlign: 'center' }}>
                    <StatBox label="Сайтов" value={report.total_sites || 0} color="#6b7280" />
                    <StatBox 
                      label="Успешно" 
                      value={report.successful_sites || 0} 
                      subvalue={report.total_sites ? `${Math.round((report.successful_sites / report.total_sites) * 100)}%` : null}
                      color="#22c55e" 
                    />
                    <StatBox label="Изменений" value={report.changes_count || changes.length} color="#3b82f6" />
                    <StatBox label="Проблем" value={report.problems_count || 0} color="#ef4444" />
                  </div>
                </button>

                {/* Раскрытое содержимое */}
                {isExpanded && (
                  <div style={{ borderTop: '1px solid #2a2a3a', padding: 16 }}>
                    {/* Категории */}
                    <div style={{ display: 'flex', gap: 8, marginBottom: 16, overflowX: 'auto' }}>
                      {[
                        { id: 'all', label: 'Все' },
                        { id: 'products', label: 'Продукты' },
                        { id: 'news', label: 'Новости' },
                        { id: 'technical', label: 'Тех.' }
                      ].map(cat => (
                        <button 
                          key={cat.id} 
                          onClick={() => { hapticFeedback('light'); setActiveCategory(cat.id) }} 
                          style={{ 
                            display: 'flex', alignItems: 'center', gap: 6, padding: '6px 12px', borderRadius: 6, 
                            backgroundColor: activeCategory === cat.id ? '#3b82f6' : '#252532', 
                            color: activeCategory === cat.id ? '#fff' : '#9ca3af', 
                            fontSize: 12, fontWeight: 500, whiteSpace: 'nowrap', cursor: 'pointer' 
                          }}
                        >
                          {cat.label} <span style={{ opacity: 0.7 }}>{categoryCounts[cat.id]}</span>
                        </button>
                      ))}
                    </div>

                    {/* Список изменений */}
                    {filteredChanges.length === 0 ? (
                      <div style={{ textAlign: 'center', padding: 20, color: '#6b7280', fontSize: 14 }}>
                        Нет изменений {activeCategory !== 'all' ? 'в этой категории' : ''}
                      </div>
                    ) : (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                        {filteredChanges.map((change, idx) => (
                          <ChangeCard 
                            key={idx} 
                            change={change} 
                            onNavigate={() => onNavigateToCompetitor(change.competitor_id)}
                          />
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )
          })
        )}
      </div>
    </div>
  )
}

// Компонент статистики
function StatBox({ label, value, subvalue, color }) {
  return (
    <div>
      <div style={{ fontSize: 18, fontWeight: 700, color }}>{value}</div>
      {subvalue && <div style={{ fontSize: 10, color: '#6b7280' }}>{subvalue}</div>}
      <div style={{ fontSize: 11, color: '#6b7280' }}>{label}</div>
    </div>
  )
}

// Компонент карточки изменения
function ChangeCard({ change, onNavigate }) {
  const typeColors = {
    products: '#22c55e',
    news: '#f59e0b',
    technical: '#6b7280',
    prices: '#ef4444'
  }
  const typeLabels = {
    products: 'Продукт',
    news: 'Новость',
    technical: 'Тех.',
    prices: 'Цена'
  }

  const category = change.parsed_summary?.category || change.change_type || 'technical'
  const summary = change.parsed_summary?.summary || change.llm_summary || 'Нет описания'
  const tags = change.parsed_summary?.tags || change.tags || []

  return (
    <div style={{ backgroundColor: '#252532', borderRadius: 10, padding: 12 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 8 }}>
        <div>
          <button 
            onClick={onNavigate}
            style={{ 
              fontSize: 14, fontWeight: 600, color: '#fff', background: 'none', border: 'none', 
              padding: 0, textAlign: 'left', cursor: 'pointer', 
              textDecoration: 'underline', textDecorationColor: 'rgba(255,255,255,0.3)' 
            }}
          >
            {change.competitor_name || 'Неизвестный'}
          </button>
          <button 
            onClick={() => openLink(`https://${change.competitor_url}`)}
            style={{ 
              display: 'block', fontSize: 11, color: '#3b82f6', background: 'none', 
              border: 'none', padding: 0, marginTop: 2, cursor: 'pointer' 
            }}
          >
            🌐 {change.competitor_url}
          </button>
        </div>
        <span style={{ 
          fontSize: 10, fontWeight: 500, padding: '3px 6px', borderRadius: 4, 
          backgroundColor: (typeColors[category] || '#6b7280') + '20', 
          color: typeColors[category] || '#6b7280' 
        }}>
          {typeLabels[category] || category}
        </span>
      </div>
      
      {/* Показываем URL где произошло изменение */}
      {change.scanned_url && (
        <div style={{ fontSize: 11, color: '#6b7280', marginBottom: 8 }}>
          🔗 {change.scanned_url}
        </div>
      )}

      <div style={{ fontSize: 13, color: '#d1d5db', lineHeight: 1.5 }}>
        {summary}
      </div>

      {tags.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginTop: 8 }}>
          {tags.map((tag, i) => (
            <span key={i} style={{ fontSize: 10, color: '#9ca3af', backgroundColor: '#1a1a24', padding: '2px 6px', borderRadius: 3 }}>
              {tag}
            </span>
          ))}
        </div>
      )}

      {change.groups?.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginTop: 8 }}>
          {change.groups.map(g => (
            <span key={g.id} style={{ fontSize: 10, padding: '2px 6px', borderRadius: 3, backgroundColor: g.color + '20', color: g.color }}>
              {g.name}
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

function formatDate(d) {
  if (!d) return ''
  return new Date(d).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short', year: 'numeric' })
}
