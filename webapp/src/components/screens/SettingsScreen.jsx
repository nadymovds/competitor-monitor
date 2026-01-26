import { useState } from 'react'
import { hapticFeedback, showAlert, showConfirm } from '../../services/telegram'
import { createGroup, updateGroup, deleteGroup } from '../../services/supabase'

const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#06b6d4', '#84cc16']

export default function SettingsScreen({ user, groups: initialGroups }) {
  const [groups, setGroups] = useState(initialGroups || [])
  const [editingGroup, setEditingGroup] = useState(null)
  const [showNewGroupForm, setShowNewGroupForm] = useState(false)
  const [newGroupName, setNewGroupName] = useState('')
  const [newGroupColor, setNewGroupColor] = useState('#3b82f6')
  const [editName, setEditName] = useState('')
  const [editColor, setEditColor] = useState('')
  const [saving, setSaving] = useState(false)

  const isAdmin = user?.role === 'admin'
  const soon = () => { hapticFeedback('warning'); showAlert('Эта функция скоро будет доступна') }

  const handleEditGroup = (group) => {
    hapticFeedback('light')
    setEditingGroup(group)
    setEditName(group.name)
    setEditColor(group.color)
  }

  const handleCancelEdit = () => {
    hapticFeedback('light')
    setEditingGroup(null)
    setEditName('')
    setEditColor('')
  }

  const handleSaveGroup = async () => {
    if (!editName.trim()) {
      hapticFeedback('error')
      showAlert('Введите название группы')
      return
    }

    hapticFeedback('light')
    setSaving(true)
    try {
      const updated = await updateGroup(editingGroup.id, {
        name: editName.trim(),
        color: editColor
      })
      setGroups(prev => prev.map(g => g.id === updated.id ? updated : g))
      setEditingGroup(null)
      setEditName('')
      setEditColor('')
      hapticFeedback('success')
    } catch (err) {
      console.error('Error updating group:', err)
      hapticFeedback('error')
      showAlert('Ошибка сохранения: ' + err.message)
    } finally {
      setSaving(false)
    }
  }

  const handleDeleteGroup = async (group) => {
    hapticFeedback('warning')
    const confirmed = await showConfirm(`Удалить группу "${group.name}"? Все конкуренты будут откреплены от этой группы.`)
    if (!confirmed) return

    setSaving(true)
    try {
      await deleteGroup(group.id)
      setGroups(prev => prev.filter(g => g.id !== group.id))
      setEditingGroup(null)
      hapticFeedback('success')
    } catch (err) {
      console.error('Error deleting group:', err)
      hapticFeedback('error')
      showAlert('Ошибка удаления: ' + err.message)
    } finally {
      setSaving(false)
    }
  }

  const handleCreateGroup = async () => {
    if (!newGroupName.trim()) {
      hapticFeedback('error')
      showAlert('Введите название группы')
      return
    }

    hapticFeedback('light')
    setSaving(true)
    try {
      const created = await createGroup(newGroupName.trim(), newGroupColor)
      setGroups(prev => [...prev, created])
      setShowNewGroupForm(false)
      setNewGroupName('')
      setNewGroupColor('#3b82f6')
      hapticFeedback('success')
    } catch (err) {
      console.error('Error creating group:', err)
      hapticFeedback('error')
      showAlert('Ошибка создания: ' + err.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <h1 style={{ fontSize: 24, fontWeight: 700, margin: 0 }}>Настройки</h1>

      <Section title="Профиль">
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: 16 }}>
          <div style={{ width: 48, height: 48, borderRadius: '50%', backgroundColor: '#3b82f6', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 20, fontWeight: 600 }}>{user?.display_name?.charAt(0) || '?'}</div>
          <div>
            <div style={{ fontSize: 16, fontWeight: 600 }}>{user?.display_name || 'Пользователь'}</div>
            <span style={{ fontSize: 12, padding: '3px 8px', borderRadius: 4, backgroundColor: isAdmin ? '#f59e0b20' : '#3b82f620', color: isAdmin ? '#f59e0b' : '#3b82f6' }}>{isAdmin ? 'Администратор' : 'Просмотр'}</span>
          </div>
        </div>
        {user?.telegram_username && <div style={{ fontSize: 13, color: '#6b7280', padding: '0 16px 16px', borderTop: '1px solid #2a2a3a', paddingTop: 12 }}>@{user.telegram_username}</div>}
      </Section>

      <Section title="Группы конкурентов" count={groups.length}>
        {groups.map((g, i) => (
          <div key={g.id}>
            {editingGroup?.id === g.id ? (
              // Режим редактирования
              <div style={{ padding: 16, borderBottom: i < groups.length - 1 ? '1px solid #2a2a3a' : 'none' }}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                  <input
                    type="text"
                    value={editName}
                    onChange={(e) => setEditName(e.target.value)}
                    placeholder="Название группы"
                    style={{
                      width: '100%',
                      padding: '10px 12px',
                      fontSize: 15,
                      backgroundColor: '#0d0d14',
                      border: '1px solid #2a2a3a',
                      borderRadius: 8,
                      color: '#fff',
                      outline: 'none'
                    }}
                  />

                  <div>
                    <div style={{ fontSize: 13, color: '#9ca3af', marginBottom: 8 }}>Цвет</div>
                    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                      {COLORS.map(color => (
                        <button
                          key={color}
                          onClick={() => { hapticFeedback('light'); setEditColor(color) }}
                          style={{
                            width: 32,
                            height: 32,
                            borderRadius: 8,
                            backgroundColor: color,
                            border: editColor === color ? '2px solid #fff' : '2px solid transparent',
                            cursor: 'pointer',
                            transition: 'all 0.2s'
                          }}
                        />
                      ))}
                    </div>
                  </div>

                  <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
                    <button
                      onClick={handleSaveGroup}
                      disabled={saving}
                      style={{
                        flex: 1,
                        padding: '10px 16px',
                        fontSize: 14,
                        fontWeight: 500,
                        backgroundColor: '#3b82f6',
                        color: '#fff',
                        border: 'none',
                        borderRadius: 8,
                        cursor: saving ? 'not-allowed' : 'pointer',
                        opacity: saving ? 0.6 : 1
                      }}
                    >
                      {saving ? 'Сохранение...' : 'Сохранить'}
                    </button>
                    <button
                      onClick={handleCancelEdit}
                      disabled={saving}
                      style={{
                        padding: '10px 16px',
                        fontSize: 14,
                        backgroundColor: '#374151',
                        color: '#fff',
                        border: 'none',
                        borderRadius: 8,
                        cursor: 'pointer'
                      }}
                    >
                      Отмена
                    </button>
                    <button
                      onClick={() => handleDeleteGroup(g)}
                      disabled={saving}
                      style={{
                        padding: '10px 16px',
                        fontSize: 14,
                        backgroundColor: '#ef444420',
                        color: '#ef4444',
                        border: 'none',
                        borderRadius: 8,
                        cursor: 'pointer'
                      }}
                    >
                      Удалить
                    </button>
                  </div>
                </div>
              </div>
            ) : (
              // Режим просмотра
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '14px 16px', borderBottom: i < groups.length - 1 ? '1px solid #2a2a3a' : 'none' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <span style={{ width: 10, height: 10, borderRadius: '50%', backgroundColor: g.color }} />
                  <span style={{ fontSize: 15, color: '#fff' }}>{g.name}</span>
                </div>
                {isAdmin && (
                  <button
                    onClick={() => handleEditGroup(g)}
                    style={{ background: 'none', border: 'none', color: '#6b7280', fontSize: 16, cursor: 'pointer' }}
                  >
                    ✎
                  </button>
                )}
              </div>
            )}
          </div>
        ))}

        {/* Форма создания новой группы */}
        {isAdmin && showNewGroupForm && (
          <div style={{ padding: 16, borderTop: groups.length > 0 ? '1px solid #2a2a3a' : 'none' }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              <input
                type="text"
                value={newGroupName}
                onChange={(e) => setNewGroupName(e.target.value)}
                placeholder="Название группы"
                style={{
                  width: '100%',
                  padding: '10px 12px',
                  fontSize: 15,
                  backgroundColor: '#0d0d14',
                  border: '1px solid #2a2a3a',
                  borderRadius: 8,
                  color: '#fff',
                  outline: 'none'
                }}
              />

              <div>
                <div style={{ fontSize: 13, color: '#9ca3af', marginBottom: 8 }}>Цвет</div>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  {COLORS.map(color => (
                    <button
                      key={color}
                      onClick={() => { hapticFeedback('light'); setNewGroupColor(color) }}
                      style={{
                        width: 32,
                        height: 32,
                        borderRadius: 8,
                        backgroundColor: color,
                        border: newGroupColor === color ? '2px solid #fff' : '2px solid transparent',
                        cursor: 'pointer',
                        transition: 'all 0.2s'
                      }}
                    />
                  ))}
                </div>
              </div>

              <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
                <button
                  onClick={handleCreateGroup}
                  disabled={saving}
                  style={{
                    flex: 1,
                    padding: '10px 16px',
                    fontSize: 14,
                    fontWeight: 500,
                    backgroundColor: '#10b981',
                    color: '#fff',
                    border: 'none',
                    borderRadius: 8,
                    cursor: saving ? 'not-allowed' : 'pointer',
                    opacity: saving ? 0.6 : 1
                  }}
                >
                  {saving ? 'Создание...' : 'Создать группу'}
                </button>
                <button
                  onClick={() => { hapticFeedback('light'); setShowNewGroupForm(false); setNewGroupName(''); setNewGroupColor('#3b82f6') }}
                  disabled={saving}
                  style={{
                    padding: '10px 16px',
                    fontSize: 14,
                    backgroundColor: '#374151',
                    color: '#fff',
                    border: 'none',
                    borderRadius: 8,
                    cursor: 'pointer'
                  }}
                >
                  Отмена
                </button>
              </div>
            </div>
          </div>
        )}

        {isAdmin && !showNewGroupForm && (
          <button
            onClick={() => { hapticFeedback('light'); setShowNewGroupForm(true); setEditingGroup(null) }}
            style={{ width: '100%', padding: 14, background: 'none', border: 'none', borderTop: '1px solid #2a2a3a', color: '#3b82f6', fontSize: 14, fontWeight: 500, cursor: 'pointer' }}
          >
            + Добавить группу
          </button>
        )}
      </Section>

      {false && <Section title="Уведомления">
        <Row label="Об изменениях" desc="Получать уведомления о новых изменениях" toggle enabled onToggle={soon} />
        <Row label="Об ошибках" desc="Получать уведомления о проблемах сканирования" toggle enabled={false} onToggle={soon} border />
      </Section>}

      {false && isAdmin && (
        <Section title="Расписание сканирования">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '14px 16px' }}>
            <span style={{ fontSize: 15, color: '#fff' }}>Автосканирование</span>
            <Toggle enabled onToggle={soon} />
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '0 16px 12px', fontSize: 14, color: '#9ca3af' }}>🕐 Каждый день в 10:00 (МСК)</div>
          <button onClick={soon} style={{ width: '100%', padding: 14, background: 'none', border: 'none', borderTop: '1px solid #2a2a3a', color: '#3b82f6', fontSize: 14, fontWeight: 500, cursor: 'pointer' }}>Изменить расписание</button>
        </Section>
      )}

      <div style={{ textAlign: 'center', padding: '20px 0', marginTop: 20 }}>
        <div style={{ fontSize: 13, color: '#6b7280' }}>Версия 1.0.0</div>
        <div style={{ fontSize: 12, color: '#4b5563', marginTop: 4 }}>© 2026 Competitor Monitor</div>
      </div>
    </div>
  )
}

function Section({ title, count, children }) {
  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
        <span style={{ fontSize: 14, color: '#9ca3af' }}>{title}</span>
        {count !== undefined && <span style={{ fontSize: 13, color: '#6b7280' }}>{count}</span>}
      </div>
      <div style={{ backgroundColor: '#1a1a24', borderRadius: 12, overflow: 'hidden' }}>{children}</div>
    </div>
  )
}

function Row({ label, desc, toggle, enabled, onToggle, border }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '14px 16px', borderTop: border ? '1px solid #2a2a3a' : 'none' }}>
      <div style={{ flex: 1, marginRight: 12 }}>
        <div style={{ fontSize: 15, color: '#fff' }}>{label}</div>
        {desc && <div style={{ fontSize: 13, color: '#6b7280', marginTop: 2 }}>{desc}</div>}
      </div>
      {toggle && <Toggle enabled={enabled} onToggle={onToggle} />}
    </div>
  )
}

function Toggle({ enabled, onToggle }) {
  return (
    <button onClick={onToggle} style={{ width: 48, height: 28, borderRadius: 14, border: 'none', cursor: 'pointer', position: 'relative', backgroundColor: enabled ? '#3b82f6' : '#374151', transition: 'background-color 0.2s' }}>
      <span style={{ position: 'absolute', top: 4, left: 4, width: 20, height: 20, borderRadius: '50%', backgroundColor: '#fff', transition: 'transform 0.2s', transform: enabled ? 'translateX(20px)' : 'translateX(0)' }} />
    </button>
  )
}
