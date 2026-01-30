import React, { useState, useEffect, useMemo } from 'react'
import { getCompetitors, getCompetitorWithHistory, updateCompetitor, createCompetitor, addCompetitorToGroup, removeCompetitorFromGroup, createGroup, addCompetitorUrl, updateCompetitorUrl, deleteCompetitorUrl } from '../../services/supabase'
import { openLink, hapticFeedback, showBackButton, hideBackButton, showAlert } from '../../services/telegram'
import ScrollToTopButton from '../ui/ScrollToTopButton'

export default function CompetitorsScreen({ user, groups: initialGroups, selectedCompetitorId, cameFromMonitoring, onBackToMonitoring, onClearSelection }) {
  const [competitors, setCompetitors] = useState([])
  const [loading, setLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedCompetitor, setSelectedCompetitor] = useState(null)
  const [details, setDetails] = useState(null)
  const [detailsLoading, setDetailsLoading] = useState(false)
  const [visibleChangesCount, setVisibleChangesCount] = useState(5)

  // Редактирование
  const [editMode, setEditMode] = useState(false)
  const [editData, setEditData] = useState({ description: '', is_active: true })
  const [editUrls, setEditUrls] = useState([])
  const [saving, setSaving] = useState(false)
  const [groups, setGroups] = useState(initialGroups || [])
  const [competitorGroups, setCompetitorGroups] = useState([])
  const [showNewGroupForm, setShowNewGroupForm] = useState(false)
  const [newGroupName, setNewGroupName] = useState('')
  const [newGroupColor, setNewGroupColor] = useState('#3b82f6')

  // Создание конкурента
  const [showCreateForm, setShowCreateForm] = useState(false)
  const [newCompetitorData, setNewCompetitorData] = useState({ name: '', url: '', description: '' })
  const [newCompetitorGroups, setNewCompetitorGroups] = useState([])
  const [creating, setCreating] = useState(false)

  // Фильтры
  const [filterGroupIds, setFilterGroupIds] = useState([])
  const [statusFilter, setStatusFilter] = useState('all') // 'all' | 'active' | 'inactive'

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
    let result = competitors

    // Фильтр по поиску
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase()
      result = result.filter(c => c.name.toLowerCase().includes(q) || c.url.toLowerCase().includes(q))
    }

    // Фильтр по группам
    if (filterGroupIds.length > 0) {
      result = result.filter(c =>
        c.groups?.some(g => filterGroupIds.includes(g.id))
      )
    }

    // Фильтр по статусу сканирования
    if (statusFilter === 'active') {
      result = result.filter(c => c.is_active !== false)
    } else if (statusFilter === 'inactive') {
      result = result.filter(c => c.is_active === false)
    }

    return result
  }, [competitors, searchQuery, filterGroupIds, statusFilter])

  const hasActiveFilters = filterGroupIds.length > 0 || statusFilter !== 'all'

  const clearFilters = () => {
    hapticFeedback('light')
    setFilterGroupIds([])
    setStatusFilter('all')
  }

  const toggleGroupFilter = (groupId) => {
    hapticFeedback('light')
    setFilterGroupIds(prev =>
      prev.includes(groupId)
        ? prev.filter(id => id !== groupId)
        : [...prev, groupId]
    )
  }

  const handleSelect = async (c) => {
    hapticFeedback('light')
    setSelectedCompetitor(c)
    setEditMode(false)
    setVisibleChangesCount(5)
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
      description: details?.description || selectedCompetitor.description || '',
      is_active: selectedCompetitor.is_active !== false
    })
    setEditUrls(details?.urls || selectedCompetitor?.urls || [])
    setEditMode(true)
  }

  const MAX_URLS_PER_COMPETITOR = 5

  const handleAddUrl = () => {
    hapticFeedback('light')
    const activeUrls = editUrls.filter(u => !u.isDeleted)
    if (activeUrls.length >= MAX_URLS_PER_COMPETITOR) {
      showAlert(`Максимум ${MAX_URLS_PER_COMPETITOR} URL на конкурента`)
      return
    }
    setEditUrls(prev => [...prev, { url: '', label: '', is_active: true, isNew: true }])
  }

  const handleUpdateUrl = (index, field, value) => {
    setEditUrls(prev => prev.map((u, i) => i === index ? { ...u, [field]: value } : u))
  }

  const handleDeleteUrl = (index) => {
    hapticFeedback('light')
    const url = editUrls[index]
    if (url.id && !url.isNew) {
      setEditUrls(prev => prev.map((u, i) => i === index ? { ...u, isDeleted: true } : u))
    } else {
      setEditUrls(prev => prev.filter((_, i) => i !== index))
    }
  }

  const handleToggleUrlActive = (index) => {
    hapticFeedback('light')
    setEditUrls(prev => prev.map((u, i) => i === index ? { ...u, is_active: !u.is_active } : u))
  }

  const handleSave = async () => {
    hapticFeedback('light')
    setSaving(true)
    try {
      // Сохраняем основные данные конкурента
      await updateCompetitor(selectedCompetitor.id, {
        description: editData.description,
        is_active: editData.is_active
      })

      // Обрабатываем URL
      const savedUrls = []
      for (const url of editUrls) {
        if (url.isDeleted && url.id) {
          await deleteCompetitorUrl(url.id)
        } else if (url.isNew && url.url) {
          const saved = await addCompetitorUrl(selectedCompetitor.id, url.url, url.label || null)
          savedUrls.push(saved)
        } else if (url.id && !url.isNew && !url.isDeleted) {
          const saved = await updateCompetitorUrl(url.id, {
            url: url.url,
            label: url.label || null,
            is_active: url.is_active
          })
          savedUrls.push(saved)
        }
      }

      // Собираем финальный список URL
      const finalUrls = editUrls
        .filter(u => !u.isDeleted)
        .map(u => u.isNew ? savedUrls.find(s => s.url === u.url) || u : u)
        .sort((a, b) => (a.sort_order || 0) - (b.sort_order || 0))

      // Обновляем локальное состояние
      setSelectedCompetitor(prev => ({ ...prev, description: editData.description, is_active: editData.is_active, urls: finalUrls }))
      setDetails(prev => prev ? { ...prev, description: editData.description, urls: finalUrls } : prev)
      setCompetitors(prev => prev.map(c =>
        c.id === selectedCompetitor.id
          ? { ...c, description: editData.description, is_active: editData.is_active, urls: finalUrls }
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

  const handleCreateCompetitor = async () => {
    if (!newCompetitorData.name.trim()) {
      showAlert('Введите название конкурента')
      return
    }
    if (!newCompetitorData.url.trim()) {
      showAlert('Введите URL сайта')
      return
    }

    hapticFeedback('light')
    setCreating(true)

    try {
      const created = await createCompetitor(
        newCompetitorData.name.trim(),
        newCompetitorData.url.trim(),
        newCompetitorData.description.trim() || null
      )

      // Add groups to the new competitor
      for (const group of newCompetitorGroups) {
        await addCompetitorToGroup(created.id, group.id)
      }

      // Add to local state
      setCompetitors(prev => [...prev, { ...created, groups: newCompetitorGroups, urls: [] }].sort((a, b) => a.name.localeCompare(b.name)))

      // Reset form and close
      setNewCompetitorData({ name: '', url: '', description: '' })
      setNewCompetitorGroups([])
      setShowCreateForm(false)
      showAlert('Конкурент добавлен')
    } catch (err) {
      console.error(err)
      showAlert('Ошибка создания: ' + err.message)
    } finally {
      setCreating(false)
    }
  }

  const handleToggleNewCompetitorGroup = (group) => {
    hapticFeedback('light')
    setNewCompetitorGroups(prev =>
      prev.some(g => g.id === group.id)
        ? prev.filter(g => g.id !== group.id)
        : [...prev, group]
    )
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
    const history = (Array.isArray(rawHistory) ? rawHistory : [])
      .filter(h => h.category !== 'technical')
      .map(h => ({
        ...h,
        parsed: parseLlmSummary(h.summary)
      }))
    const visibleHistory = history.slice(0, visibleChangesCount)
    const hasMoreChanges = history.length > visibleChangesCount

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

          {/* URLs */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <label style={{ fontSize: 14, color: '#9ca3af' }}>URL сайтов</label>

            {editUrls.filter(u => !u.isDeleted).map((u, index) => {
              const actualIndex = editUrls.findIndex(eu => eu === u)
              return (
                <div key={u.id || index} style={{
                  display: 'flex',
                  gap: 8,
                  alignItems: 'center',
                  padding: 12,
                  backgroundColor: '#252532',
                  borderRadius: 8
                }}>
                  <input
                    type="text"
                    value={u.label || ''}
                    onChange={e => handleUpdateUrl(actualIndex, 'label', e.target.value)}
                    placeholder="Метка"
                    style={{
                      width: 70,
                      padding: '8px 10px',
                      backgroundColor: '#1a1a24',
                      border: '1px solid #2a2a3a',
                      borderRadius: 6,
                      color: '#fff',
                      fontSize: 13,
                      outline: 'none'
                    }}
                  />
                  <input
                    type="text"
                    value={u.url}
                    onChange={e => handleUpdateUrl(actualIndex, 'url', e.target.value)}
                    placeholder="example.com"
                    style={{
                      flex: 1,
                      padding: '8px 10px',
                      backgroundColor: '#1a1a24',
                      border: '1px solid #2a2a3a',
                      borderRadius: 6,
                      color: '#fff',
                      fontSize: 13,
                      outline: 'none'
                    }}
                  />
                  <button
                    onClick={() => handleToggleUrlActive(actualIndex)}
                    style={{
                      width: 32,
                      height: 32,
                      borderRadius: 6,
                      border: 'none',
                      backgroundColor: u.is_active !== false ? '#22c55e20' : '#ef444420',
                      color: u.is_active !== false ? '#22c55e' : '#ef4444',
                      cursor: 'pointer',
                      fontSize: 14
                    }}
                  >
                    {u.is_active !== false ? '✓' : '✗'}
                  </button>
                  <button
                    onClick={() => handleDeleteUrl(actualIndex)}
                    style={{
                      width: 32,
                      height: 32,
                      borderRadius: 6,
                      border: 'none',
                      backgroundColor: '#ef444420',
                      color: '#ef4444',
                      cursor: 'pointer',
                      fontSize: 14
                    }}
                  >
                    🗑
                  </button>
                </div>
              )
            })}

            <button
              onClick={handleAddUrl}
              style={{
                padding: '10px 16px',
                backgroundColor: '#252532',
                border: '1px dashed #3b82f6',
                borderRadius: 8,
                color: '#3b82f6',
                fontSize: 14,
                cursor: 'pointer'
              }}
            >
              + Добавить URL
            </button>
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

        {/* URLs */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {(details?.urls || selectedCompetitor?.urls || []).length > 0 ? (
            (details?.urls || selectedCompetitor?.urls || []).map(u => (
              <button
                key={u.id}
                onClick={() => openLink(ensureProtocol(u.url))}
                style={{
                  fontSize: 14,
                  color: '#3b82f6',
                  background: 'none',
                  border: 'none',
                  padding: 0,
                  cursor: 'pointer',
                  textAlign: 'left',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8
                }}
              >
                🌐 {u.label && <span style={{ color: '#9ca3af' }}>[{u.label}]</span>} {u.url}
                {u.is_active === false && (
                  <span style={{ fontSize: 10, color: '#ef4444', backgroundColor: '#ef444420', padding: '2px 6px', borderRadius: 4 }}>откл.</span>
                )}
              </button>
            ))
          ) : selectedCompetitor.url ? (
            <button onClick={() => openLink(ensureProtocol(selectedCompetitor.url))} style={{ fontSize: 14, color: '#3b82f6', background: 'none', border: 'none', padding: 0, cursor: 'pointer', textAlign: 'left' }}>
              🌐 {selectedCompetitor.url}
            </button>
          ) : null}
        </div>

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
              {visibleHistory.map((h, i) => {
                const typeColors = {
                  products: '#22c55e',
                  news: '#f59e0b',
                  prices: '#ef4444'
                }
                const typeLabels = {
                  products: 'Продукт',
                  news: 'Новость',
                  prices: 'Цена'
                }
                const category = h.parsed.category || h.change_type || 'news'

                return (
                  <div key={i} style={{ padding: 12, backgroundColor: '#1a1a24', borderRadius: 10, borderLeft: `3px solid ${typeColors[category] || '#3b82f6'}` }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                      <span style={{ fontSize: 12, color: '#6b7280' }}>{formatDate(h.detected_at || h.scan_date)}</span>
                      <span style={{
                        fontSize: 10, fontWeight: 500, padding: '2px 6px', borderRadius: 4,
                        backgroundColor: (typeColors[category] || '#6b7280') + '20',
                        color: typeColors[category] || '#6b7280'
                      }}>
                        {typeLabels[category] || category}
                      </span>
                    </div>

                    {/* Показываем URL где произошло изменение */}
                    {(h.scanned_url || h.competitor_urls?.url) && (
                      <div style={{
                        fontSize: 11,
                        color: '#3b82f6',
                        marginBottom: 8,
                        display: 'flex',
                        alignItems: 'center',
                        gap: 4
                      }}>
                        🔗 {h.competitor_urls?.label && `[${h.competitor_urls.label}] `}
                        {h.scanned_url || h.competitor_urls?.url}
                      </div>
                    )}

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

              {hasMoreChanges && (
                <button
                  onClick={() => {
                    hapticFeedback('light')
                    setVisibleChangesCount(prev => prev + 5)
                  }}
                  style={{
                    padding: '12px 16px',
                    backgroundColor: '#252532',
                    border: 'none',
                    borderRadius: 10,
                    color: '#3b82f6',
                    fontSize: 14,
                    cursor: 'pointer',
                    width: '100%'
                  }}
                >
                  Показать ещё ({history.length - visibleChangesCount})
                </button>
              )}
            </div>
          )}
        </div>
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h1 style={{ fontSize: 24, fontWeight: 700, margin: 0 }}>Конкуренты</h1>
        {isAdmin && (
          <button
            onClick={() => { hapticFeedback('light'); setShowCreateForm(true) }}
            style={{
              padding: '8px 16px',
              backgroundColor: '#3b82f6',
              border: 'none',
              borderRadius: 8,
              color: '#fff',
              fontSize: 14,
              fontWeight: 600,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: 6
            }}
          >
            <span style={{ fontSize: 18 }}>+</span> Добавить
          </button>
        )}
      </div>

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

      {/* Фильтры */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {/* Фильтр по статусу */}
        <div style={{ display: 'flex', gap: 8 }}>
          {[
            { value: 'all', label: 'Все' },
            { value: 'active', label: 'Активные' },
            { value: 'inactive', label: 'Отключённые' }
          ].map(opt => (
            <button
              key={opt.value}
              onClick={() => { hapticFeedback('light'); setStatusFilter(opt.value) }}
              style={{
                padding: '6px 12px',
                fontSize: 13,
                borderRadius: 8,
                border: 'none',
                cursor: 'pointer',
                backgroundColor: statusFilter === opt.value ? '#3b82f6' : '#1a1a24',
                color: statusFilter === opt.value ? '#fff' : '#9ca3af',
                transition: 'all 0.2s'
              }}
            >
              {opt.label}
            </button>
          ))}
        </div>

        {/* Фильтр по группам */}
        {groups.length > 0 && (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {groups.map(g => {
              const isSelected = filterGroupIds.includes(g.id)
              return (
                <button
                  key={g.id}
                  onClick={() => toggleGroupFilter(g.id)}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 6,
                    padding: '5px 10px',
                    fontSize: 12,
                    borderRadius: 6,
                    border: isSelected ? `1px solid ${g.color}` : '1px solid transparent',
                    cursor: 'pointer',
                    backgroundColor: isSelected ? g.color + '30' : '#1a1a24',
                    color: isSelected ? g.color : '#9ca3af',
                    transition: 'all 0.2s'
                  }}
                >
                  <span style={{
                    width: 8,
                    height: 8,
                    borderRadius: '50%',
                    backgroundColor: g.color
                  }} />
                  {g.name}
                </button>
              )
            })}
          </div>
        )}

        {/* Кнопка сброса фильтров */}
        {hasActiveFilters && (
          <button
            onClick={clearFilters}
            style={{
              alignSelf: 'flex-start',
              padding: '4px 10px',
              fontSize: 12,
              borderRadius: 6,
              border: 'none',
              cursor: 'pointer',
              backgroundColor: '#ef444420',
              color: '#ef4444'
            }}
          >
            ✕ Сбросить фильтры
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
              <div style={{ fontSize: 13, color: '#3b82f6', display: 'flex', flexDirection: 'column', gap: 2 }}>
                {c.urls?.length > 0 ? (
                  c.urls.map((u, i) => (
                    <div key={u.id || i} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                      {u.label && <span style={{ color: '#6b7280', fontSize: 11 }}>[{u.label}]</span>}
                      <span style={{ opacity: u.is_active === false ? 0.5 : 1 }}>{u.url}</span>
                      {u.is_active === false && (
                        <span style={{ fontSize: 9, color: '#ef4444', backgroundColor: '#ef444420', padding: '1px 4px', borderRadius: 3 }}>откл</span>
                      )}
                    </div>
                  ))
                ) : (
                  c.url
                )}
              </div>
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

      {/* Create Competitor Modal */}
      {showCreateForm && (
        <div
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: 'rgba(0, 0, 0, 0.7)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
            padding: 20
          }}
          onClick={() => { setShowCreateForm(false); setNewCompetitorData({ name: '', url: '', description: '' }) }}
        >
          <div
            style={{
              backgroundColor: '#1a1a24',
              borderRadius: 16,
              padding: 24,
              maxWidth: 500,
              width: '100%',
              display: 'flex',
              flexDirection: 'column',
              gap: 16
            }}
            onClick={e => e.stopPropagation()}
          >
            <h2 style={{ fontSize: 20, fontWeight: 700, margin: 0 }}>Добавить конкурента</h2>

            {/* Name */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <label style={{ fontSize: 14, color: '#9ca3af' }}>Название *</label>
              <input
                type="text"
                value={newCompetitorData.name}
                onChange={e => setNewCompetitorData(prev => ({ ...prev, name: e.target.value }))}
                placeholder='ООО "Компания"'
                style={{
                  padding: '12px 16px',
                  backgroundColor: '#252532',
                  border: '1px solid #2a2a3a',
                  borderRadius: 10,
                  color: '#fff',
                  fontSize: 15,
                  outline: 'none'
                }}
              />
            </div>

            {/* URL */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <label style={{ fontSize: 14, color: '#9ca3af' }}>URL сайта *</label>
              <input
                type="text"
                value={newCompetitorData.url}
                onChange={e => setNewCompetitorData(prev => ({ ...prev, url: e.target.value }))}
                placeholder="https://example.com"
                style={{
                  padding: '12px 16px',
                  backgroundColor: '#252532',
                  border: '1px solid #2a2a3a',
                  borderRadius: 10,
                  color: '#fff',
                  fontSize: 15,
                  outline: 'none'
                }}
              />
            </div>

            {/* Description */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <label style={{ fontSize: 14, color: '#9ca3af' }}>Описание</label>
              <textarea
                value={newCompetitorData.description}
                onChange={e => setNewCompetitorData(prev => ({ ...prev, description: e.target.value }))}
                placeholder="Краткое описание конкурента..."
                rows={3}
                style={{
                  padding: '12px 16px',
                  backgroundColor: '#252532',
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

            {/* Groups */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <label style={{ fontSize: 14, color: '#9ca3af' }}>Группы</label>
              {groups.length === 0 ? (
                <div style={{ padding: 12, color: '#6b7280', fontSize: 13, textAlign: 'center', backgroundColor: '#252532', borderRadius: 8 }}>
                  Нет доступных групп
                </div>
              ) : (
                <div style={{
                  backgroundColor: '#252532',
                  borderRadius: 10,
                  overflow: 'hidden'
                }}>
                  {groups.map((group, i) => {
                    const isSelected = newCompetitorGroups.some(g => g.id === group.id)
                    return (
                      <button
                        key={group.id}
                        onClick={() => handleToggleNewCompetitorGroup(group)}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: 12,
                          width: '100%',
                          padding: '12px 14px',
                          backgroundColor: 'transparent',
                          border: 'none',
                          borderBottom: i < groups.length - 1 ? '1px solid #1a1a24' : 'none',
                          cursor: 'pointer',
                          textAlign: 'left'
                        }}
                      >
                        <span style={{
                          width: 18,
                          height: 18,
                          borderRadius: 4,
                          backgroundColor: isSelected ? group.color : 'transparent',
                          border: `2px solid ${group.color}`,
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          color: '#fff',
                          fontSize: 11
                        }}>
                          {isSelected && '✓'}
                        </span>
                        <span style={{
                          width: 8,
                          height: 8,
                          borderRadius: '50%',
                          backgroundColor: group.color
                        }} />
                        <span style={{ fontSize: 14, color: '#fff' }}>{group.name}</span>
                      </button>
                    )
                  })}
                </div>
              )}
            </div>

            {/* Buttons */}
            <div style={{ display: 'flex', gap: 12, marginTop: 8 }}>
              <button
                onClick={() => { setShowCreateForm(false); setNewCompetitorData({ name: '', url: '', description: '' }) }}
                disabled={creating}
                style={{
                  flex: 1,
                  padding: '12px 16px',
                  backgroundColor: '#252532',
                  border: 'none',
                  borderRadius: 10,
                  color: '#9ca3af',
                  fontSize: 15,
                  cursor: creating ? 'not-allowed' : 'pointer',
                  opacity: creating ? 0.5 : 1
                }}
              >
                Отмена
              </button>
              <button
                onClick={handleCreateCompetitor}
                disabled={creating}
                style={{
                  flex: 1,
                  padding: '12px 16px',
                  backgroundColor: creating ? '#6b7280' : '#3b82f6',
                  border: 'none',
                  borderRadius: 10,
                  color: '#fff',
                  fontSize: 15,
                  fontWeight: 600,
                  cursor: creating ? 'not-allowed' : 'pointer'
                }}
              >
                {creating ? 'Создание...' : 'Создать'}
              </button>
            </div>
          </div>
        </div>
      )}

      <ScrollToTopButton />
    </div>
  )
}

function formatDate(d) {
  if (!d) return ''
  return new Date(d).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short', year: 'numeric' })
}

function ensureProtocol(url) {
  if (!url) return url
  if (url.startsWith('http://') || url.startsWith('https://')) return url
  return `https://${url}`
}
