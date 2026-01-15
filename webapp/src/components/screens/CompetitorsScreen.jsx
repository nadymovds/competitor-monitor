import React, { useState, useEffect, useMemo } from 'react'
import { getCompetitors, getCompetitorWithHistory } from '../../services/supabase'
import { openLink, hapticFeedback, showBackButton, hideBackButton } from '../../services/telegram'

export default function CompetitorsScreen({ user, groups, selectedCompetitorId, cameFromMonitoring, onBackToMonitoring, onClearSelection }) {
  const [competitors, setCompetitors] = useState([])
  const [loading, setLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedCompetitor, setSelectedCompetitor] = useState(null)
  const [details, setDetails] = useState(null)
  const [detailsLoading, setDetailsLoading] = useState(false)

  useEffect(() => {
    async function load() {
      try {
        setLoading(true)
        const data = await getCompetitors()
        setCompetitors(data)
      } catch (err) {
        console.error(err)
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  useEffect(() => {
    if (selectedCompetitorId && competitors.length > 0) {
      const c = competitors.find(x => x.id === selectedCompetitorId)
      if (c) handleSelect(c)
    }
  }, [selectedCompetitorId, competitors])

  useEffect(() => {
    if (selectedCompetitor) showBackButton(handleBack)
    else hideBackButton()
    return () => hideBackButton()
  }, [selectedCompetitor, cameFromMonitoring])

  const filtered = useMemo(() => {
    if (!searchQuery.trim()) return competitors
    const q = searchQuery.toLowerCase()
    return competitors.filter(c => c.name.toLowerCase().includes(q) || c.url.toLowerCase().includes(q))
  }, [competitors, searchQuery])

  const handleSelect = async (c) => {
    hapticFeedback('light')
    setSelectedCompetitor(c)
    setDetailsLoading(true)
    try {
      const d = await getCompetitorWithHistory(c.id)
      setDetails(d)
    } catch (err) {
      console.error(err)
    } finally {
      setDetailsLoading(false)
    }
  }

  const handleBack = () => {
    hapticFeedback('light')
    if (cameFromMonitoring) onBackToMonitoring()
    else { setSelectedCompetitor(null); setDetails(null); onClearSelection() }
  }

  // Парсинг llm_summary
  const parseLlmSummary = (summary) => {
    if (!summary) return { summary: '', category: null, tags: [] }
    
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
      return { summary: summary, category: null, tags: [] }
    }
  }

  if (selectedCompetitor) {
    // Парсим историю изменений
    const rawHistory = details?.changes_history || []
    const history = (Array.isArray(rawHistory) ? rawHistory : []).map(h => ({
      ...h,
      parsed: parseLlmSummary(h.summary)
    }))

    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <button onClick={handleBack} style={{ background: 'none', border: 'none', color: '#3b82f6', fontSize: 15, cursor: 'pointer' }}>← Назад</button>
          {cameFromMonitoring && <span style={{ fontSize: 11, color: '#f59e0b', backgroundColor: '#f59e0b20', padding: '4px 8px', borderRadius: 4 }}>из отчёта</span>}
        </div>
        
        <div style={{ fontSize: 22, fontWeight: 700 }}>{selectedCompetitor.name}</div>
        
        <button onClick={() => openLink(`https://${selectedCompetitor.url}`)} style={{ fontSize: 14, color: '#3b82f6', background: 'none', border: 'none', padding: 0, cursor: 'pointer', textAlign: 'left' }}>
          🌐 {selectedCompetitor.url}
        </button>
        
        {(details?.description || selectedCompetitor.description) && (
          <div style={{ fontSize: 14, color: '#9ca3af', padding: 12, backgroundColor: '#1a1a24', borderRadius: 8 }}>
            {details?.description || selectedCompetitor.description}
          </div>
        )}
        
        {details?.groups?.length > 0 && (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            {(Array.isArray(details.groups) ? details.groups : []).map(g => (
              <span key={g.id} style={{ fontSize: 11, padding: '3px 8px', borderRadius: 4, backgroundColor: g.color + '20', color: g.color }}>
                {g.name}
              </span>
            ))}
          </div>
        )}
        
        <div style={{ marginTop: 8 }}>
          <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 12 }}>История изменений</h3>
          
          {detailsLoading ? (
            <div style={{ color: '#6b7280', textAlign: 'center', padding: 24 }}>Загрузка...</div>
          ) : history.length === 0 ? (
            <div style={{ color: '#6b7280', textAlign: 'center', padding: 24 }}>Изменений пока не обнаружено</div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {history.map((h, i) => {
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
                const category = h.parsed.category || h.change_type || 'technical'
                
                return (
                  <div key={i} style={{ padding: 12, backgroundColor: '#1a1a24', borderRadius: 10, borderLeft: `3px solid ${typeColors[category] || '#3b82f6'}` }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                      <span style={{ fontSize: 12, color: '#6b7280' }}>{formatDate(h.scan_date)}</span>
                      <span style={{ 
                        fontSize: 10, fontWeight: 500, padding: '2px 6px', borderRadius: 4,
                        backgroundColor: (typeColors[category] || '#6b7280') + '20',
                        color: typeColors[category] || '#6b7280'
                      }}>
                        {typeLabels[category] || category}
                      </span>
                    </div>
                    
                    <div style={{ fontSize: 14, color: '#d1d5db', lineHeight: 1.5 }}>
                      {h.parsed.summary}
                    </div>
                    
                    {h.parsed.tags?.length > 0 && (
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 8 }}>
                        {h.parsed.tags.map((t, j) => (
                          <span key={j} style={{ fontSize: 10, color: '#9ca3af', backgroundColor: '#252532', padding: '2px 6px', borderRadius: 4 }}>
                            {t}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          )}
        </div>
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <h1 style={{ fontSize: 24, fontWeight: 700, margin: 0 }}>Конкуренты</h1>
      
      <div style={{ position: 'relative' }}>
        <span style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', opacity: 0.5 }}>🔍</span>
        <input 
          type="text" 
          placeholder="Поиск..." 
          value={searchQuery} 
          onChange={e => setSearchQuery(e.target.value)} 
          style={{ width: '100%', padding: '12px 40px', backgroundColor: '#1a1a24', border: '1px solid #2a2a3a', borderRadius: 10, color: '#fff', fontSize: 15, outline: 'none' }} 
        />
        {searchQuery && (
          <button onClick={() => setSearchQuery('')} style={{ position: 'absolute', right: 12, top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', color: '#6b7280', cursor: 'pointer' }}>
            ✕
          </button>
        )}
      </div>
      
      <div style={{ fontSize: 13, color: '#6b7280' }}>{filtered.length} из {competitors.length}</div>
      
      {loading ? (
        <div style={{ color: '#6b7280', textAlign: 'center', padding: 40 }}>Загрузка...</div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {filtered.map(c => (
            <button 
              key={c.id} 
              onClick={() => handleSelect(c)} 
              style={{ display: 'flex', flexDirection: 'column', gap: 6, padding: 14, backgroundColor: '#1a1a24', borderRadius: 12, border: 'none', textAlign: 'left', cursor: 'pointer' }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: 15, fontWeight: 600, color: '#fff' }}>{c.name}</span>
                <span style={{ color: '#6b7280' }}>→</span>
              </div>
              <div style={{ fontSize: 13, color: '#3b82f6' }}>{c.url}</div>
              {c.description && <div style={{ fontSize: 13, color: '#9ca3af' }}>{c.description}</div>}
              {c.groups?.length > 0 && (
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 6 }}>
                  {c.groups.map(g => (
                    <span key={g.id} style={{ fontSize: 11, padding: '3px 8px', borderRadius: 4, backgroundColor: g.color + '20', color: g.color }}>
                      {g.name}
                    </span>
                  ))}
                </div>
              )}
            </button>
          ))}
          {filtered.length === 0 && <div style={{ textAlign: 'center', padding: 40, color: '#6b7280' }}>🔍 Ничего не найдено</div>}
        </div>
      )}
    </div>
  )
}

function formatDate(d) {
  if (!d) return ''
  return new Date(d).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short', year: 'numeric' })
}
