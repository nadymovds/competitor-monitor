import React, { useState, useEffect, useMemo } from 'react'
import { getCompetitors, getCompetitorWithHistory, updateCompetitor, addCompetitorToGroup, removeCompetitorFromGroup, createGroup } from '../../services/supabase'
import { openLink, hapticFeedback, showBackButton, hideBackButton, showAlert } from '../../services/telegram'

export default function CompetitorsScreen({ user, groups: initialGroups, selectedCompetitorId, cameFromMonitoring, onBackToMonitoring, onClearSelection }) {
  const [competitors, setCompetitors] = useState([])
  const [loading, setLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedCompetitor, setSelectedCompetitor] = useState(null)
  const [details, setDetails] = useState(null)
  const [detailsLoading, setDetailsLoading] = useState(false)

  // Редактирование
  const [editMode, setEditMode] = useState(false)
  const [editData, setEditData] = useState({ url: '', description: '', is_active: true })
  const [saving, setSaving] = useState(false)
  const [groups, setGroups] = useState(initialGroups || [])
  const [competitorGroups, setCompetitorGroups] = useState([])
  const [showNewGroupForm, setShowNewGroupForm] = useState(false)
  const [newGroupName, setNewGroupName] = useState('')
  const [newGroupColor, setNewGroupColor] = useState('#3b82f6')

  const isAdmin = user?.role === 'admin'

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
  }, [selectedCompetitor, cameFromMonitoring, editMode])

  const filtered = useMemo(() => {
    if (!searchQuery.trim()) return competitors
    const q = searchQuery.toLowerCase()
    return competitors.filter(c => c.name.toLowerCase().includes(q) || c.url.toLowerCase().includes(q))
  }, [competitors, searchQuery])

  const handleSelect = async (c) => {
    hapticFeedback('light')
    setSelectedCompetitor(c)
    setEditMode(false)
    setDetailsLoading(true)
    try {
      const d = await getCompetitorWithHistory(c.id)
      setDetails(d)
      setCompetitorGroups(d?.groups || c.groups || [])
    } catch (err) {
      console.error(err)
    } finally {
      setDetailsLoading(false)
    }
  }

  const handleBack = () => {
    hapticFeedback('light')
    if (editMode) {
      setEditMode(false)
      return
    }
    if (cameFromMonitoring) onBackToMonitoring()
    else { setSelectedCompetitor(null); setDetails(null); onClearSelection() }
  }

  const handleStartEdit = () => {
    hapticFeedback('light')
    setEditData({
      url: selectedCompetitor.url || '',
      description: details?.description || selectedCompetitor.description || '',
      is_active: selectedCompetitor.is_active !== false
    })
    setEditMode(true)
  }

  const handleSave = async () => {
    hapticFeedback('light')
    setSaving(true)
    try {
      await updateCompetitor(selectedCompetitor.id, {
        url: editData.url,
        description: editData.description,
        is_active: editData.is_active
      })

      // Обновляем локальное состояние
      setSelectedCompetitor(prev => ({ ...prev, url: editData.url, description: editData.description, is_active: editData.is_active }))
      setDetails(prev => prev ? { ...prev, description: editData.description } : prev)
      setCompetitors(prev => prev.map(c =>
        c.id === selectedCompetitor.id
          ? { ...c, url: editData.url, description: editData.description, is_active: editData.is_active }
          : c
      ))

      setEditMode(false)
      showAlert('Изменения сохранены')
    } catch (err) {
      console.error(err)
      showAlert('Ошибка сохранения: ' + err.message)
    } finally {
      setSaving(false)
    }
  }

  const handleToggleGroup = async (group) => {
    hapticFeedback('light')
    const isInGroup = competitorGroups.some(g => g.id === group.id)

    try {
      if (isInGroup) {
        await removeCompetitorFromGroup(selectedCompetitor.id, group.id)
        setCompetitorGroups(prev => prev.filter(g => g.id !== group.id))
      } else {
        await addCompetitorToGroup(selectedCompetitor.id, group.id)
        setCompetitorGroups(prev => [...prev, group])
      }

      // Обновляем список конкурентов
      setCompetitors(prev => prev.map(c => {
        if (c.id === selectedCompetitor.id) {
          const newGroups = isInGroup
            ? c.groups.filter(g => g.id !== group.id)
            : [...c.groups, group]
          return { ...c, groups: newGroups }
        }
        return c
      }))
    } catch (err) {
      console.error(err)
      showAlert('Ошибка: ' + err.message)
    }
  }

  const handleCreateGroup = async () => {
    if (!newGroupName.trim()) {
      showAlert('Введите название группы')
      return
    }

    hapticFeedback('light')
    try {
      const newGroup = await createGroup(newGroupName.trim(), newGroupColor)
      setGroups(prev => [...prev, newGroup])
      setNewGroupName('')
      setNewGroupColor('#3b82f6')
      setShowNewGroupForm(false)
      showAlert('Группа создана')
    } catch (err) {
      console.error(err)
      showAlert('Ошибка создания группы: ' + err.message)
    }
  }

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

  const colorOptions = ['#3b82f6', '#22c55e', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#14b8a6', '#6b7280']

  if (selectedCompetitor) {
    const rawHistory = details?.changes_history || []
    const history = (Array.isArray(rawHistory) ? rawHistory : []).map(h => ({
      ...h,
      parsed: parseLlmSummary(h.summary)
    }))

    // Режим редактирования
    if (editMode && isAdmin) {
      return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <button onClick={handleBack} style={{ background: 'none', border: 'none', color: '#3b82f6', fontSize: 15, cursor: 'pointer' }}>← Отмена</button>
            <button
              onClick={handleSave}
              disabled={saving}
              style={{ background: 'none', border: 'none', color: saving ? '#6b7280' : '#22c55e', fontSize: 15, cursor: 'pointer', fontWeight: 600 }}
            >
              {saving ? 'Сохранение...' : 'Сохранить'}
            </button>
          </div>

          <div style={{ fontSize: 22, fontWeight: 700 }}>Редактирование</div>
          <div style={{ fontSize: 14, color: '#9ca3af' }}>{selectedCompetitor.name}</div>

          {/* URL */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <label style={{ fontSize: 14, color: '#9ca3af' }}>URL сайта</label>
            <input
              type="text"
              value={editData.url}
              onChange={e => setEditData(prev => ({ ...prev, url: e.target.value }))}
              placeholder="example.com"
              style={{
                padding: '12px 16px',
                backgroundColor: '#1a1a24',
                border: '1px solid #2a2a3a',
                borderRadius: 10,
                color: '#fff',
                fontSize: 15,
                outline: 'none'
              }}
            />
          </div>

          {/* Описание */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <label style={{ fontSize: 14, color: '#9ca3af' }}>Описание</label>
            <textarea
              value={editData.description}
              onChange={e => setEditData(prev => ({ ...prev, description: e.target.value }))}
              placeholder="Описание конкурента..."
              rows={4}
              style={{
                padding: '12px 16px',
                backgroundColor: '#1a1a24',
                border: '1px solid #2a2a3a',
                borderRadius: 10,
                color: '#fff',
                fontSize: 15,
                outline: 'none',
                resize: 'vertical',
                fontFamily: 'inherit'
              }}
            />
          </div>

          {/* Статус сканирования */}
          <div style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            padding: '14px 16px',
            backgroundColor: '#1a1a24',
            borderRadius: 10
          }}>
            <div>
              <div style={{ fontSize: 15, color: '#fff' }}>Сканирование</div>
              <div style={{ fontSize: 13, color: '#6b7280', marginTop: 2 }}>
                {editData.is_active ? 'Конкурент сканируется' : 'Сканирование отключено'}
              </div>
            </div>
            <button
              onClick={() => setEditData(prev => ({ ...prev, is_active: !prev.is_active }))}
              style={{
                width: 48,
                height: 28,
                borderRadius: 14,
                border: 'none',
                cursor: 'pointer',
                position: 'relative',
                backgroundColor: editData.is_active ? '#22c55e' : '#374151',
                transition: 'background-color 0.2s'
              }}
            >
              <span style={{
                position: 'absolute',
                top: 4,
                left: 4,
                width: 20,
                height: 20,
                borderRadius: '50%',
                backgroundColor: '#fff',
                transition: 'transform 0.2s',
                transform: editData.is_active ? 'translateX(20px)' : 'translateX(0)'
              }} />
            </button>
          </div>

          {/* Группы */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <label style={{ fontSize: 14, color: '#9ca3af' }}>Группы</label>
              <button
                onClick={() => setShowNewGroupForm(!showNewGroupForm)}
                style={{ background: 'none', border: 'none', color: '#3b82f6', fontSize: 13, cursor: 'pointer' }}
              >
                {showNewGroupForm ? 'Отмена' : '+ Новая группа'}
              </button>
            </div>

            {showNewGroupForm && (
              <div style={{
                padding: 12,
                backgroundColor: '#252532',
                borderRadius: 10,
                display: 'flex',
                flexDirection: 'column',
                gap: 12
              }}>
                <input
                  type="text"
                  value={newGroupName}
                  onChange={e => setNewGroupName(e.target.value)}
                  placeholder="Название группы"
                  style={{
                    padding: '10px 12px',
                    backgroundColor: '#1a1a24',
                    border: '1px solid #2a2a3a',
                    borderRadius: 8,
                    color: '#fff',
                    fontSize: 14,
                    outline: 'none'
                  }}
                />
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  {colorOptions.map(color => (
                    <button
                      key={color}
                      onClick={() => setNewGroupColor(color)}
                      style={{
                        width: 32,
                        height: 32,
                        borderRadius: 8,
                        backgroundColor: color,
                        border: newGroupColor === color ? '3px solid #fff' : 'none',
                        cursor: 'pointer'
                      }}
                    />
                  ))}
                </div>
                <button
                  onClick={handleCreateGroup}
                  style={{
                    padding: '10px 16px',
                    backgroundColor: '#3b82f6',
                    border: 'none',
                    borderRadius: 8,
                    color: '#fff',
                    fontSize: 14,
                    fontWeight: 500,
                    cursor: 'pointer'
                  }}
                >
                  Создать группу
                </button>
              </div>
            )}

            <div style={{
              backgroundColor: '#1a1a24',
              borderRadius: 10,
              overflow: 'hidden'
            }}>
              {groups.length === 0 ? (
                <div style={{ padding: 16, color: '#6b7280', textAlign: 'center' }}>
                  Нет доступных групп
                </div>
              ) : (
                groups.map((group, i) => {
                  const isInGroup = competitorGroups.some(g => g.id === group.id)
                  return (
                    <button
                      key={group.id}
                      onClick={() => handleToggleGroup(group)}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 12,
                        width: '100%',
                        padding: '14px 16px',
                        backgroundColor: 'transparent',
                        border: 'none',
                        borderBottom: i < groups.length - 1 ? '1px solid #2a2a3a' : 'none',
                        cursor: 'pointer',
                        textAlign: 'left'
                      }}
                    >
                      <span style={{
                        width: 20,
                        height: 20,
                        borderRadius: 4,
                        backgroundColor: isInGroup ? group.color : 'transparent',
                        border: `2px solid ${group.color}`,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        color: '#fff',
                        fontSize: 12
                      }}>
                        {isInGroup && '✓'}
                      </span>
                      <span style={{
                        width: 10,
                        height: 10,
                        borderRadius: '50%',
                        backgroundColor: group.color
                      }} />
                      <span style={{ fontSize: 15, color: '#fff' }}>{group.name}</span>
                    </button>
                  )
                })
              )}
            </div>
          </div>
        </div>
      )
    }

    // Обычный режим просмотра
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <button onClick={handleBack} style={{ background: 'none', border: 'none', color: '#3b82f6', fontSize: 15, cursor: 'pointer' }}>← Назад</button>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            {cameFromMonitoring && <span style={{ fontSize: 11, color: '#f59e0b', backgroundColor: '#f59e0b20', padding: '4px 8px', borderRadius: 4 }}>из отчёта</span>}
            {isAdmin && (
              <button
                onClick={handleStartEdit}
                style={{
                  background: 'none',
                  border: '1px solid #3b82f6',
                  color: '#3b82f6',
                  fontSize: 13,
                  padding: '4px 12px',
                  borderRadius: 6,
                  cursor: 'pointer'
                }}
              >
                ✎ Редактировать
              </button>
            )}
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{ fontSize: 22, fontWeight: 700 }}>{selectedCompetitor.name}</div>
          {selectedCompetitor.is_active === false && (
            <span style={{ fontSize: 11, color: '#ef4444', backgroundColor: '#ef444420', padding: '4px 8px', borderRadius: 4 }}>
              Отключён
            </span>
          )}
        </div>

        <button onClick={() => openLink(`https://${selectedCompetitor.url}`)} style={{ fontSize: 14, color: '#3b82f6', background: 'none', border: 'none', padding: 0, cursor: 'pointer', textAlign: 'left' }}>
          🌐 {selectedCompetitor.url}
        </button>

        {(details?.description || selectedCompetitor.description) && (
          <div style={{ fontSize: 14, color: '#9ca3af', padding: 12, backgroundColor: '#1a1a24', borderRadius: 8 }}>
            {details?.description || selectedCompetitor.description}
          </div>
        )}

        {competitorGroups?.length > 0 && (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            {competitorGroups.map(g => (
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
              style={{ display: 'flex', flexDirection: 'column', gap: 6, padding: 14, backgroundColor: '#1a1a24', borderRadius: 12, border: 'none', textAlign: 'left', cursor: 'pointer', opacity: c.is_active === false ? 0.6 : 1 }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{ fontSize: 15, fontWeight: 600, color: '#fff' }}>{c.name}</span>
                  {c.is_active === false && (
                    <span style={{ fontSize: 10, color: '#ef4444', backgroundColor: '#ef444420', padding: '2px 6px', borderRadius: 4 }}>
                      Откл.
                    </span>
                  )}
                </div>
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
