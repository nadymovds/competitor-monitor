import { useState, useEffect } from 'react'
import { hapticFeedback, showAlert, showConfirm } from '../../services/telegram'
import { createGroup, updateGroup, deleteGroup, getMentionSearchTerms, createMentionSearchTerm, updateMentionSearchTerm, deleteMentionSearchTerm, getMentionSources, createMentionSource, updateMentionSource, deleteMentionSource, getMentionIgnoredSources, createMentionIgnoredSource, deleteMentionIgnoredSource } from '../../services/supabase'
import {
  getNewsCategories, getAllNewsChannels,
  createCategory, updateCategory, toggleCategoryVisibility, deleteCategory as deleteCategoryApi,
  createChannel, updateChannel, deleteChannel as deleteChannelApi
} from '../../services/news'

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

  // News categories state
  const [categories, setCategories] = useState([])
  const [editingCategory, setEditingCategory] = useState(null)
  const [showNewCategoryForm, setShowNewCategoryForm] = useState(false)
  const [newCatName, setNewCatName] = useState('')
  const [newCatColor, setNewCatColor] = useState('#3b82f6')
  const [newCatDescription, setNewCatDescription] = useState('')
  const [editCatName, setEditCatName] = useState('')
  const [editCatColor, setEditCatColor] = useState('')
  const [editCatDescription, setEditCatDescription] = useState('')

  // News channels state
  const [channels, setChannels] = useState([])
  const [editingChannel, setEditingChannel] = useState(null)
  const [showNewChannelForm, setShowNewChannelForm] = useState(false)
  const [newChUsername, setNewChUsername] = useState('')
  const [newChTitle, setNewChTitle] = useState('')
  const [newChSourceType, setNewChSourceType] = useState('telegram')
  const [newChUrl, setNewChUrl] = useState('')
  const [newChCssConfig, setNewChCssConfig] = useState('')
  const [editChUsername, setEditChUsername] = useState('')
  const [editChTitle, setEditChTitle] = useState('')
  const [editChSourceType, setEditChSourceType] = useState('telegram')
  const [editChUrl, setEditChUrl] = useState('')
  const [editChCssConfig, setEditChCssConfig] = useState('')

  // Mention search terms state
  const [mentionTerms, setMentionTerms] = useState([])
  const [editingTerm, setEditingTerm] = useState(null)
  const [showNewTermForm, setShowNewTermForm] = useState(false)
  const [newTermValue, setNewTermValue] = useState('')
  const [newTermMatchType, setNewTermMatchType] = useState('partial')
  const [editTermValue, setEditTermValue] = useState('')
  const [editTermMatchType, setEditTermMatchType] = useState('partial')

  // Mention sources state
  const [mentionSources, setMentionSources] = useState([])
  const [editingMentionSource, setEditingMentionSource] = useState(null)
  const [showNewMentionSourceForm, setShowNewMentionSourceForm] = useState(false)
  const [newMsSourceType, setNewMsSourceType] = useState('telegram')
  const [newMsUsername, setNewMsUsername] = useState('')
  const [newMsTitle, setNewMsTitle] = useState('')
  const [newMsUrl, setNewMsUrl] = useState('')
  const [newMsCssConfig, setNewMsCssConfig] = useState('')
  const [editMsSourceType, setEditMsSourceType] = useState('telegram')
  const [editMsUsername, setEditMsUsername] = useState('')
  const [editMsTitle, setEditMsTitle] = useState('')
  const [editMsUrl, setEditMsUrl] = useState('')
  const [editMsCssConfig, setEditMsCssConfig] = useState('')

  // Ignored sources state
  const [ignoredSources, setIgnoredSources] = useState([])
  const [showNewIgnoredForm, setShowNewIgnoredForm] = useState(false)
  const [newIgnoredPattern, setNewIgnoredPattern] = useState('')

  const isAdmin = user?.role === 'admin'
  const soon = () => { hapticFeedback('warning'); showAlert('Эта функция скоро будет доступна') }

  useEffect(() => {
    if (!isAdmin) return
    async function loadNewsSettings() {
      try {
        const [cats, chs] = await Promise.all([getNewsCategories(), getAllNewsChannels()])
        setCategories(cats)
        setChannels(chs)
      } catch (err) {
        console.error('Error loading news settings:', err)
      }
    }
    loadNewsSettings()
  }, [isAdmin])

  useEffect(() => {
    if (!isAdmin) return
    async function loadMentionSettings() {
      try {
        const [terms, sources, ignored] = await Promise.all([getMentionSearchTerms(), getMentionSources(), getMentionIgnoredSources()])
        setMentionTerms(terms)
        setMentionSources(sources)
        setIgnoredSources(ignored)
      } catch (err) {
        console.error('Error loading mention settings:', err)
      }
    }
    loadMentionSettings()
  }, [isAdmin])

  // --- Groups handlers ---

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

  // --- News categories handlers ---

  const handleToggleCategoryVisibility = async (cat) => {
    hapticFeedback('light')
    try {
      const updated = await toggleCategoryVisibility(cat.id, !cat.is_visible)
      setCategories(prev => prev.map(c => c.id === updated.id ? updated : c))
      hapticFeedback('success')
    } catch (err) {
      console.error('Error toggling category visibility:', err)
      hapticFeedback('error')
      showAlert('Ошибка: ' + err.message)
    }
  }

  const handleEditCategory = (cat) => {
    hapticFeedback('light')
    setEditingCategory(cat)
    setEditCatName(cat.name)
    setEditCatColor(cat.color)
    setEditCatDescription(cat.description || '')
  }

  const handleCancelEditCategory = () => {
    hapticFeedback('light')
    setEditingCategory(null)
    setEditCatName('')
    setEditCatColor('')
    setEditCatDescription('')
  }

  const handleSaveCategory = async () => {
    if (!editCatName.trim()) {
      hapticFeedback('error')
      showAlert('Введите название категории')
      return
    }

    hapticFeedback('light')
    setSaving(true)
    try {
      const updated = await updateCategory(editingCategory.id, {
        name: editCatName.trim(),
        color: editCatColor,
        description: editCatDescription.trim() || null
      })
      setCategories(prev => prev.map(c => c.id === updated.id ? updated : c))
      setEditingCategory(null)
      setEditCatName('')
      setEditCatColor('')
      setEditCatDescription('')
      hapticFeedback('success')
    } catch (err) {
      console.error('Error updating category:', err)
      hapticFeedback('error')
      showAlert('Ошибка сохранения: ' + err.message)
    } finally {
      setSaving(false)
    }
  }

  const handleDeleteCategory = async (cat) => {
    hapticFeedback('warning')
    const confirmed = await showConfirm(`Удалить категорию "${cat.name}"? Новости будут перенесены в категорию "Прочее".`)
    if (!confirmed) return

    setSaving(true)
    try {
      await deleteCategoryApi(cat.id)
      setCategories(prev => prev.filter(c => c.id !== cat.id))
      setEditingCategory(null)
      hapticFeedback('success')
    } catch (err) {
      console.error('Error deleting category:', err)
      hapticFeedback('error')
      showAlert('Ошибка удаления: ' + err.message)
    } finally {
      setSaving(false)
    }
  }

  const handleCreateCategory = async () => {
    if (!newCatName.trim()) {
      hapticFeedback('error')
      showAlert('Введите название категории')
      return
    }

    hapticFeedback('light')
    setSaving(true)
    try {
      const created = await createCategory({
        name: newCatName.trim(),
        color: newCatColor,
        description: newCatDescription.trim() || null
      })
      setCategories(prev => [...prev, created])
      setShowNewCategoryForm(false)
      setNewCatName('')
      setNewCatColor('#3b82f6')
      setNewCatDescription('')
      hapticFeedback('success')
    } catch (err) {
      console.error('Error creating category:', err)
      hapticFeedback('error')
      showAlert('Ошибка создания: ' + err.message)
    } finally {
      setSaving(false)
    }
  }

  // --- News channels handlers ---

  const handleEditChannel = (ch) => {
    hapticFeedback('light')
    setEditingChannel(ch)
    setEditChUsername(ch.username || '')
    setEditChTitle(ch.title || '')
    setEditChSourceType(ch.source_type || 'telegram')
    setEditChUrl(ch.url || '')
    setEditChCssConfig(ch.css_config || '')
  }

  const handleCancelEditChannel = () => {
    hapticFeedback('light')
    setEditingChannel(null)
    setEditChUsername('')
    setEditChTitle('')
    setEditChSourceType('telegram')
    setEditChUrl('')
    setEditChCssConfig('')
  }

  const handleSaveChannel = async () => {
    if (editChSourceType === 'telegram') {
      if (!editChUsername.trim()) {
        hapticFeedback('error')
        showAlert('Введите username канала')
        return
      }
    } else {
      if (!editChUrl.trim()) {
        hapticFeedback('error')
        showAlert('Введите URL источника')
        return
      }
    }

    hapticFeedback('light')
    setSaving(true)
    try {
      const updated = await updateChannel(editingChannel.id, {
        username: editChSourceType === 'telegram' ? editChUsername.trim() : null,
        title: editChTitle.trim() || null,
        url: editChSourceType === 'website' ? editChUrl.trim() : null,
        cssConfig: editChSourceType === 'website' && editChCssConfig.trim() ? editChCssConfig.trim() : null
      })
      setChannels(prev => prev.map(c => c.id === updated.id ? updated : c))
      setEditingChannel(null)
      setEditChUsername('')
      setEditChTitle('')
      setEditChSourceType('telegram')
      setEditChUrl('')
      setEditChCssConfig('')
      hapticFeedback('success')
    } catch (err) {
      console.error('Error updating channel:', err)
      hapticFeedback('error')
      showAlert('Ошибка сохранения: ' + err.message)
    } finally {
      setSaving(false)
    }
  }

  const handleDeleteChannel = async (ch) => {
    hapticFeedback('warning')
    const channelName = ch.source_type === 'website' ? ch.title || ch.url : `@${ch.username}`
    const confirmed = await showConfirm(`Удалить источник "${channelName}"? Все новости этого источника будут удалены.`)
    if (!confirmed) return

    setSaving(true)
    try {
      await deleteChannelApi(ch.id)
      setChannels(prev => prev.filter(c => c.id !== ch.id))
      setEditingChannel(null)
      hapticFeedback('success')
    } catch (err) {
      console.error('Error deleting channel:', err)
      hapticFeedback('error')
      showAlert('Ошибка удаления: ' + err.message)
    } finally {
      setSaving(false)
    }
  }

  const handleCreateChannel = async () => {
    if (newChSourceType === 'telegram') {
      if (!newChUsername.trim()) {
        hapticFeedback('error')
        showAlert('Введите username канала')
        return
      }
    } else {
      if (!newChUrl.trim()) {
        hapticFeedback('error')
        showAlert('Введите URL источника')
        return
      }
    }

    hapticFeedback('light')
    setSaving(true)
    try {
      const created = await createChannel({
        username: newChSourceType === 'telegram' ? newChUsername.trim() : null,
        title: newChTitle.trim() || null,
        sourceType: newChSourceType,
        url: newChSourceType === 'website' ? newChUrl.trim() : null,
        cssConfig: newChSourceType === 'website' && newChCssConfig.trim() ? newChCssConfig.trim() : null
      })
      setChannels(prev => [...prev, created])
      setShowNewChannelForm(false)
      setNewChUsername('')
      setNewChTitle('')
      setNewChSourceType('telegram')
      setNewChUrl('')
      setNewChCssConfig('')
      hapticFeedback('success')
    } catch (err) {
      console.error('Error creating channel:', err)
      hapticFeedback('error')
      showAlert('Ошибка создания: ' + err.message)
    } finally {
      setSaving(false)
    }
  }

  // --- Mention search terms handlers ---

  const handleToggleTermActive = async (term) => {
    hapticFeedback('light')
    try {
      const updated = await updateMentionSearchTerm(term.id, { isActive: !term.is_active })
      setMentionTerms(prev => prev.map(t => t.id === updated.id ? updated : t))
      hapticFeedback('success')
    } catch (err) {
      hapticFeedback('error')
      showAlert('Ошибка: ' + err.message)
    }
  }

  const handleEditTerm = (term) => {
    hapticFeedback('light')
    setEditingTerm(term)
    setEditTermValue(term.term)
    setEditTermMatchType(term.match_type || 'partial')
  }

  const handleSaveTerm = async () => {
    if (!editTermValue.trim()) {
      hapticFeedback('error')
      showAlert('Введите поисковый термин')
      return
    }
    hapticFeedback('light')
    setSaving(true)
    try {
      const updated = await updateMentionSearchTerm(editingTerm.id, { term: editTermValue.trim(), matchType: editTermMatchType })
      setMentionTerms(prev => prev.map(t => t.id === updated.id ? updated : t))
      setEditingTerm(null)
      setEditTermValue('')
      setEditTermMatchType('partial')
      hapticFeedback('success')
    } catch (err) {
      hapticFeedback('error')
      showAlert('Ошибка сохранения: ' + err.message)
    } finally {
      setSaving(false)
    }
  }

  const handleDeleteTerm = async (term) => {
    hapticFeedback('warning')
    const confirmed = await showConfirm(`Удалить термин "${term.term}"?`)
    if (!confirmed) return
    setSaving(true)
    try {
      await deleteMentionSearchTerm(term.id)
      setMentionTerms(prev => prev.filter(t => t.id !== term.id))
      setEditingTerm(null)
      hapticFeedback('success')
    } catch (err) {
      hapticFeedback('error')
      showAlert('Ошибка удаления: ' + err.message)
    } finally {
      setSaving(false)
    }
  }

  const handleCreateTerm = async () => {
    if (!newTermValue.trim()) {
      hapticFeedback('error')
      showAlert('Введите поисковый термин')
      return
    }
    hapticFeedback('light')
    setSaving(true)
    try {
      const created = await createMentionSearchTerm({ term: newTermValue.trim(), matchType: newTermMatchType })
      setMentionTerms(prev => [...prev, created])
      setShowNewTermForm(false)
      setNewTermValue('')
      setNewTermMatchType('partial')
      hapticFeedback('success')
    } catch (err) {
      hapticFeedback('error')
      showAlert('Ошибка создания: ' + err.message)
    } finally {
      setSaving(false)
    }
  }

  // --- Mention sources handlers ---

  const handleToggleMentionSourceActive = async (src) => {
    hapticFeedback('light')
    try {
      const updated = await updateMentionSource(src.id, { isActive: !src.is_active })
      setMentionSources(prev => prev.map(s => s.id === updated.id ? updated : s))
      hapticFeedback('success')
    } catch (err) {
      hapticFeedback('error')
      showAlert('Ошибка: ' + err.message)
    }
  }

  const handleEditMentionSource = (src) => {
    hapticFeedback('light')
    setEditingMentionSource(src)
    setEditMsSourceType(src.source_type || 'telegram')
    setEditMsUsername(src.username || '')
    setEditMsTitle(src.title || '')
    setEditMsUrl(src.url || '')
    setEditMsCssConfig(src.css_config || '')
  }

  const handleSaveMentionSource = async () => {
    if (editMsSourceType === 'telegram' && !editMsUsername.trim()) {
      hapticFeedback('error')
      showAlert('Введите username канала')
      return
    }
    if (editMsSourceType === 'website' && !editMsUrl.trim()) {
      hapticFeedback('error')
      showAlert('Введите URL сайта')
      return
    }
    hapticFeedback('light')
    setSaving(true)
    try {
      const updated = await updateMentionSource(editingMentionSource.id, {
        username: editMsSourceType === 'telegram' ? editMsUsername.trim() : null,
        title: editMsTitle.trim() || null,
        url: editMsSourceType === 'website' ? editMsUrl.trim() : null,
        cssConfig: editMsSourceType === 'website' && editMsCssConfig.trim() ? editMsCssConfig.trim() : null
      })
      setMentionSources(prev => prev.map(s => s.id === updated.id ? updated : s))
      setEditingMentionSource(null)
      hapticFeedback('success')
    } catch (err) {
      hapticFeedback('error')
      showAlert('Ошибка сохранения: ' + err.message)
    } finally {
      setSaving(false)
    }
  }

  const handleDeleteMentionSource = async (src) => {
    hapticFeedback('warning')
    const name = src.source_type === 'website' ? src.title || src.url : `@${src.username}`
    const confirmed = await showConfirm(`Удалить источник "${name}"?`)
    if (!confirmed) return
    setSaving(true)
    try {
      await deleteMentionSource(src.id)
      setMentionSources(prev => prev.filter(s => s.id !== src.id))
      setEditingMentionSource(null)
      hapticFeedback('success')
    } catch (err) {
      hapticFeedback('error')
      showAlert('Ошибка удаления: ' + err.message)
    } finally {
      setSaving(false)
    }
  }

  const handleCreateMentionSource = async () => {
    if (newMsSourceType === 'telegram' && !newMsUsername.trim()) {
      hapticFeedback('error')
      showAlert('Введите username канала')
      return
    }
    if (newMsSourceType === 'website' && !newMsUrl.trim()) {
      hapticFeedback('error')
      showAlert('Введите URL сайта')
      return
    }
    hapticFeedback('light')
    setSaving(true)
    try {
      const created = await createMentionSource({
        sourceType: newMsSourceType,
        username: newMsSourceType === 'telegram' ? newMsUsername.trim() : null,
        title: newMsTitle.trim() || null,
        url: newMsSourceType === 'website' ? newMsUrl.trim() : null,
        cssConfig: newMsSourceType === 'website' && newMsCssConfig.trim() ? newMsCssConfig.trim() : null
      })
      setMentionSources(prev => [...prev, created])
      setShowNewMentionSourceForm(false)
      setNewMsUsername('')
      setNewMsTitle('')
      setNewMsSourceType('telegram')
      setNewMsUrl('')
      setNewMsCssConfig('')
      hapticFeedback('success')
    } catch (err) {
      hapticFeedback('error')
      showAlert('Ошибка создания: ' + err.message)
    } finally {
      setSaving(false)
    }
  }

  // --- Ignored sources handlers ---

  const handleCreateIgnoredSource = async () => {
    if (!newIgnoredPattern.trim()) {
      hapticFeedback('error')
      showAlert('Введите домен или путь (например: example.com или t.me/channel_name)')
      return
    }
    hapticFeedback('light')
    setSaving(true)
    try {
      const created = await createMentionIgnoredSource({ pattern: newIgnoredPattern.trim() })
      setIgnoredSources(prev => [...prev, created])
      setShowNewIgnoredForm(false)
      setNewIgnoredPattern('')
      hapticFeedback('success')
    } catch (err) {
      hapticFeedback('error')
      showAlert('Ошибка создания: ' + err.message)
    } finally {
      setSaving(false)
    }
  }

  const handleDeleteIgnoredSource = async (src) => {
    hapticFeedback('warning')
    const confirmed = await showConfirm(`Удалить "${src.pattern}" из списка игнорируемых?`)
    if (!confirmed) return
    setSaving(true)
    try {
      await deleteMentionIgnoredSource(src.id)
      setIgnoredSources(prev => prev.filter(s => s.id !== src.id))
      hapticFeedback('success')
    } catch (err) {
      hapticFeedback('error')
      showAlert('Ошибка удаления: ' + err.message)
    } finally {
      setSaving(false)
    }
  }

  const handleToggleChannelActive = async (ch) => {
    hapticFeedback('light')
    try {
      const updated = await updateChannel(ch.id, { isActive: !ch.is_active })
      setChannels(prev => prev.map(c => c.id === updated.id ? updated : c))
      hapticFeedback('success')
    } catch (err) {
      console.error('Error toggling channel:', err)
      hapticFeedback('error')
      showAlert('Ошибка: ' + err.message)
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
                    style={inputStyle}
                  />

                  <div>
                    <div style={{ fontSize: 13, color: '#9ca3af', marginBottom: 8 }}>Цвет</div>
                    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                      {COLORS.map(color => (
                        <ColorButton key={color} color={color} selected={editColor === color} onClick={() => { hapticFeedback('light'); setEditColor(color) }} />
                      ))}
                    </div>
                  </div>

                  <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
                    <button onClick={handleSaveGroup} disabled={saving} style={{ ...btnPrimary, opacity: saving ? 0.6 : 1, cursor: saving ? 'not-allowed' : 'pointer' }}>
                      {saving ? 'Сохранение...' : 'Сохранить'}
                    </button>
                    <button onClick={handleCancelEdit} disabled={saving} style={btnSecondary}>Отмена</button>
                    <button onClick={() => handleDeleteGroup(g)} disabled={saving} style={btnDanger}>Удалить</button>
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
                style={inputStyle}
              />

              <div>
                <div style={{ fontSize: 13, color: '#9ca3af', marginBottom: 8 }}>Цвет</div>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  {COLORS.map(color => (
                    <ColorButton key={color} color={color} selected={newGroupColor === color} onClick={() => { hapticFeedback('light'); setNewGroupColor(color) }} />
                  ))}
                </div>
              </div>

              <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
                <button onClick={handleCreateGroup} disabled={saving} style={{ ...btnSuccess, opacity: saving ? 0.6 : 1, cursor: saving ? 'not-allowed' : 'pointer' }}>
                  {saving ? 'Создание...' : 'Создать группу'}
                </button>
                <button onClick={() => { hapticFeedback('light'); setShowNewGroupForm(false); setNewGroupName(''); setNewGroupColor('#3b82f6') }} disabled={saving} style={btnSecondary}>
                  Отмена
                </button>
              </div>
            </div>
          </div>
        )}

        {isAdmin && !showNewGroupForm && (
          <button
            onClick={() => { hapticFeedback('light'); setShowNewGroupForm(true); setEditingGroup(null) }}
            style={addBtnStyle}
          >
            + Добавить группу
          </button>
        )}
      </Section>

      {/* Категории новостей — только для админов */}
      {isAdmin && (
        <Section title="Категории новостей" count={categories.length}>
          {categories.map((cat, i) => (
            <div key={cat.id}>
              {editingCategory?.id === cat.id ? (
                <div style={{ padding: 16, borderBottom: i < categories.length - 1 ? '1px solid #2a2a3a' : 'none' }}>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                    <input
                      type="text"
                      value={editCatName}
                      onChange={(e) => setEditCatName(e.target.value)}
                      placeholder="Название категории"
                      style={inputStyle}
                    />
                    <input
                      type="text"
                      value={editCatDescription}
                      onChange={(e) => setEditCatDescription(e.target.value)}
                      placeholder="Описание (необязательно)"
                      style={inputStyle}
                    />

                    <div>
                      <div style={{ fontSize: 13, color: '#9ca3af', marginBottom: 8 }}>Цвет</div>
                      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                        {COLORS.map(color => (
                          <ColorButton key={color} color={color} selected={editCatColor === color} onClick={() => { hapticFeedback('light'); setEditCatColor(color) }} />
                        ))}
                      </div>
                    </div>

                    <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
                      <button onClick={handleSaveCategory} disabled={saving} style={{ ...btnPrimary, opacity: saving ? 0.6 : 1, cursor: saving ? 'not-allowed' : 'pointer' }}>
                        {saving ? 'Сохранение...' : 'Сохранить'}
                      </button>
                      <button onClick={handleCancelEditCategory} disabled={saving} style={btnSecondary}>Отмена</button>
                      <button onClick={() => handleDeleteCategory(cat)} disabled={saving} style={btnDanger}>Удалить</button>
                    </div>
                  </div>
                </div>
              ) : (
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '14px 16px', borderBottom: i < categories.length - 1 ? '1px solid #2a2a3a' : 'none' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10, flex: 1, minWidth: 0 }}>
                    <button
                      onClick={() => handleToggleCategoryVisibility(cat)}
                      style={{
                        width: 20, height: 20, borderRadius: 4, border: '2px solid ' + (cat.is_visible ? '#3b82f6' : '#4b5563'),
                        backgroundColor: cat.is_visible ? '#3b82f6' : 'transparent',
                        cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center',
                        flexShrink: 0, padding: 0
                      }}
                    >
                      {cat.is_visible && <span style={{ color: '#fff', fontSize: 12, lineHeight: 1 }}>✓</span>}
                    </button>
                    <span style={{ width: 10, height: 10, borderRadius: '50%', backgroundColor: cat.color, flexShrink: 0 }} />
                    <span style={{ fontSize: 15, color: cat.is_visible ? '#fff' : '#6b7280', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{cat.name}</span>
                  </div>
                  <button
                    onClick={() => handleEditCategory(cat)}
                    style={{ background: 'none', border: 'none', color: '#6b7280', fontSize: 16, cursor: 'pointer', flexShrink: 0 }}
                  >
                    ✎
                  </button>
                </div>
              )}
            </div>
          ))}

          {showNewCategoryForm && (
            <div style={{ padding: 16, borderTop: categories.length > 0 ? '1px solid #2a2a3a' : 'none' }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                <input
                  type="text"
                  value={newCatName}
                  onChange={(e) => setNewCatName(e.target.value)}
                  placeholder="Название категории"
                  style={inputStyle}
                />
                <input
                  type="text"
                  value={newCatDescription}
                  onChange={(e) => setNewCatDescription(e.target.value)}
                  placeholder="Описание (необязательно)"
                  style={inputStyle}
                />

                <div>
                  <div style={{ fontSize: 13, color: '#9ca3af', marginBottom: 8 }}>Цвет</div>
                  <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                    {COLORS.map(color => (
                      <ColorButton key={color} color={color} selected={newCatColor === color} onClick={() => { hapticFeedback('light'); setNewCatColor(color) }} />
                    ))}
                  </div>
                </div>

                <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
                  <button onClick={handleCreateCategory} disabled={saving} style={{ ...btnSuccess, opacity: saving ? 0.6 : 1, cursor: saving ? 'not-allowed' : 'pointer' }}>
                    {saving ? 'Создание...' : 'Создать категорию'}
                  </button>
                  <button onClick={() => { hapticFeedback('light'); setShowNewCategoryForm(false); setNewCatName(''); setNewCatColor('#3b82f6'); setNewCatDescription('') }} disabled={saving} style={btnSecondary}>
                    Отмена
                  </button>
                </div>
              </div>
            </div>
          )}

          {!showNewCategoryForm && (
            <button
              onClick={() => { hapticFeedback('light'); setShowNewCategoryForm(true); setEditingCategory(null) }}
              style={addBtnStyle}
            >
              + Добавить категорию
            </button>
          )}
        </Section>
      )}

      {/* Источники новостей — только для админов */}
      {isAdmin && (
        <Section title="Источники новостей" count={channels.length}>
          {channels.map((ch, i) => (
            <div key={ch.id}>
              {editingChannel?.id === ch.id ? (
                <div style={{ padding: 16, borderBottom: i < channels.length - 1 ? '1px solid #2a2a3a' : 'none' }}>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                    <div>
                      <div style={{ fontSize: 13, color: '#9ca3af', marginBottom: 8 }}>Тип источника</div>
                      <div style={{ display: 'flex', gap: 8 }}>
                        <button
                          onClick={() => { hapticFeedback('light'); setEditChSourceType('telegram') }}
                          style={editChSourceType === 'telegram' ? sourceTypeBtnActive : sourceTypeBtn}
                        >
                          📱 Telegram
                        </button>
                        <button
                          onClick={() => { hapticFeedback('light'); setEditChSourceType('website') }}
                          style={editChSourceType === 'website' ? sourceTypeBtnActive : sourceTypeBtn}
                        >
                          🌐 Веб-сайт
                        </button>
                      </div>
                    </div>

                    {editChSourceType === 'telegram' ? (
                      <div style={{ position: 'relative' }}>
                        <span style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', color: '#6b7280', fontSize: 15 }}>@</span>
                        <input
                          type="text"
                          value={editChUsername}
                          onChange={(e) => setEditChUsername(e.target.value.replace(/^@/, ''))}
                          placeholder="username"
                          style={{ ...inputStyle, paddingLeft: 28 }}
                        />
                      </div>
                    ) : (
                      <>
                        <input
                          type="text"
                          value={editChUrl}
                          onChange={(e) => setEditChUrl(e.target.value)}
                          placeholder="https://example.com/news"
                          style={inputStyle}
                        />
                        <input
                          type="text"
                          value={editChCssConfig}
                          onChange={(e) => setEditChCssConfig(e.target.value)}
                          placeholder="CSS-селекторы (JSON, необязательно)"
                          style={inputStyle}
                        />
                      </>
                    )}

                    <input
                      type="text"
                      value={editChTitle}
                      onChange={(e) => setEditChTitle(e.target.value)}
                      placeholder="Название (необязательно)"
                      style={inputStyle}
                    />

                    <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
                      <button onClick={handleSaveChannel} disabled={saving} style={{ ...btnPrimary, opacity: saving ? 0.6 : 1, cursor: saving ? 'not-allowed' : 'pointer' }}>
                        {saving ? 'Сохранение...' : 'Сохранить'}
                      </button>
                      <button onClick={handleCancelEditChannel} disabled={saving} style={btnSecondary}>Отмена</button>
                      <button onClick={() => handleDeleteChannel(ch)} disabled={saving} style={btnDanger}>Удалить</button>
                    </div>
                  </div>
                </div>
              ) : (
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '14px 16px', borderBottom: i < channels.length - 1 ? '1px solid #2a2a3a' : 'none' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10, flex: 1, minWidth: 0 }}>
                    <button
                      onClick={() => handleToggleChannelActive(ch)}
                      style={{
                        width: 20, height: 20, borderRadius: 4, border: '2px solid ' + (ch.is_active ? '#10b981' : '#4b5563'),
                        backgroundColor: ch.is_active ? '#10b981' : 'transparent',
                        cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center',
                        flexShrink: 0, padding: 0
                      }}
                    >
                      {ch.is_active && <span style={{ color: '#fff', fontSize: 12, lineHeight: 1 }}>✓</span>}
                    </button>
                    <span style={{ fontSize: 14, flexShrink: 0 }}>{ch.source_type === 'website' ? '🌐' : '📱'}</span>
                    <div style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {ch.source_type === 'website' ? (
                        <>
                          <span style={{ fontSize: 15, color: ch.is_active ? '#fff' : '#6b7280' }}>{ch.title || ch.url}</span>
                          {ch.title && ch.url && <span style={{ fontSize: 12, color: '#6b7280', marginLeft: 8 }}>{ch.url}</span>}
                        </>
                      ) : (
                        <>
                          <span style={{ fontSize: 15, color: ch.is_active ? '#fff' : '#6b7280' }}>@{ch.username}</span>
                          {ch.title && <span style={{ fontSize: 13, color: '#6b7280', marginLeft: 8 }}>{ch.title}</span>}
                        </>
                      )}
                    </div>
                  </div>
                  <button
                    onClick={() => handleEditChannel(ch)}
                    style={{ background: 'none', border: 'none', color: '#6b7280', fontSize: 16, cursor: 'pointer', flexShrink: 0 }}
                  >
                    ✎
                  </button>
                </div>
              )}
            </div>
          ))}

          {showNewChannelForm && (
            <div style={{ padding: 16, borderTop: channels.length > 0 ? '1px solid #2a2a3a' : 'none' }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                <div>
                  <div style={{ fontSize: 13, color: '#9ca3af', marginBottom: 8 }}>Тип источника</div>
                  <div style={{ display: 'flex', gap: 8 }}>
                    <button
                      onClick={() => { hapticFeedback('light'); setNewChSourceType('telegram') }}
                      style={newChSourceType === 'telegram' ? sourceTypeBtnActive : sourceTypeBtn}
                    >
                      📱 Telegram
                    </button>
                    <button
                      onClick={() => { hapticFeedback('light'); setNewChSourceType('website') }}
                      style={newChSourceType === 'website' ? sourceTypeBtnActive : sourceTypeBtn}
                    >
                      🌐 Веб-сайт
                    </button>
                  </div>
                </div>

                {newChSourceType === 'telegram' ? (
                  <div style={{ position: 'relative' }}>
                    <span style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', color: '#6b7280', fontSize: 15 }}>@</span>
                    <input
                      type="text"
                      value={newChUsername}
                      onChange={(e) => setNewChUsername(e.target.value.replace(/^@/, ''))}
                      placeholder="username"
                      style={{ ...inputStyle, paddingLeft: 28 }}
                    />
                  </div>
                ) : (
                  <>
                    <input
                      type="text"
                      value={newChUrl}
                      onChange={(e) => setNewChUrl(e.target.value)}
                      placeholder="https://example.com/news"
                      style={inputStyle}
                    />
                    <input
                      type="text"
                      value={newChCssConfig}
                      onChange={(e) => setNewChCssConfig(e.target.value)}
                      placeholder="CSS-селекторы (JSON, необязательно)"
                      style={inputStyle}
                    />
                  </>
                )}

                <input
                  type="text"
                  value={newChTitle}
                  onChange={(e) => setNewChTitle(e.target.value)}
                  placeholder="Название (необязательно)"
                  style={inputStyle}
                />

                <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
                  <button onClick={handleCreateChannel} disabled={saving} style={{ ...btnSuccess, opacity: saving ? 0.6 : 1, cursor: saving ? 'not-allowed' : 'pointer' }}>
                    {saving ? 'Создание...' : 'Создать источник'}
                  </button>
                  <button onClick={() => { hapticFeedback('light'); setShowNewChannelForm(false); setNewChUsername(''); setNewChTitle(''); setNewChSourceType('telegram'); setNewChUrl(''); setNewChCssConfig('') }} disabled={saving} style={btnSecondary}>
                    Отмена
                  </button>
                </div>
              </div>
            </div>
          )}

          {!showNewChannelForm && (
            <button
              onClick={() => { hapticFeedback('light'); setShowNewChannelForm(true); setEditingChannel(null) }}
              style={addBtnStyle}
            >
              + Добавить источник
            </button>
          )}
        </Section>
      )}

      {/* Поиск упоминаний — только для админов */}
      {isAdmin && (
        <Section title="Поиск упоминаний" count={mentionTerms.length}>
          {mentionTerms.map((term, i) => (
            <div key={term.id}>
              {editingTerm?.id === term.id ? (
                <div style={{ padding: 16, borderBottom: i < mentionTerms.length - 1 ? '1px solid #2a2a3a' : 'none' }}>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                    <input
                      type="text"
                      value={editTermValue}
                      onChange={(e) => setEditTermValue(e.target.value)}
                      placeholder="Поисковый термин"
                      style={inputStyle}
                    />
                    <MatchTypeToggle value={editTermMatchType} onChange={setEditTermMatchType} />
                    <div style={{ display: 'flex', gap: 8 }}>
                      <button onClick={handleSaveTerm} disabled={saving} style={{ ...btnPrimary, opacity: saving ? 0.6 : 1, cursor: saving ? 'not-allowed' : 'pointer' }}>
                        {saving ? 'Сохранение...' : 'Сохранить'}
                      </button>
                      <button onClick={() => { hapticFeedback('light'); setEditingTerm(null); setEditTermValue(''); setEditTermMatchType('partial') }} disabled={saving} style={btnSecondary}>Отмена</button>
                      <button onClick={() => handleDeleteTerm(term)} disabled={saving} style={btnDanger}>Удалить</button>
                    </div>
                  </div>
                </div>
              ) : (
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '14px 16px', borderBottom: i < mentionTerms.length - 1 ? '1px solid #2a2a3a' : 'none' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10, flex: 1, minWidth: 0 }}>
                    <button
                      onClick={() => handleToggleTermActive(term)}
                      style={{
                        width: 20, height: 20, borderRadius: 4, border: '2px solid ' + (term.is_active ? '#10b981' : '#4b5563'),
                        backgroundColor: term.is_active ? '#10b981' : 'transparent',
                        cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center',
                        flexShrink: 0, padding: 0
                      }}
                    >
                      {term.is_active && <span style={{ color: '#fff', fontSize: 12, lineHeight: 1 }}>✓</span>}
                    </button>
                    <span style={{ fontSize: 15, color: term.is_active ? '#fff' : '#6b7280' }}>{term.term}</span>
                    <span style={{ fontSize: 11, padding: '2px 6px', borderRadius: 4, backgroundColor: term.match_type === 'full' ? '#f59e0b22' : '#3b82f622', color: term.match_type === 'full' ? '#f59e0b' : '#60a5fa', flexShrink: 0 }}>
                      {term.match_type === 'full' ? 'полное' : 'частичное'}
                    </span>
                  </div>
                  <button onClick={() => handleEditTerm(term)} style={{ background: 'none', border: 'none', color: '#6b7280', fontSize: 16, cursor: 'pointer', flexShrink: 0 }}>✎</button>
                </div>
              )}
            </div>
          ))}

          {showNewTermForm && (
            <div style={{ padding: 16, borderTop: mentionTerms.length > 0 ? '1px solid #2a2a3a' : 'none' }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                <input
                  type="text"
                  value={newTermValue}
                  onChange={(e) => setNewTermValue(e.target.value)}
                  placeholder="Например: SKAI, ООО Рога и Копыта"
                  style={inputStyle}
                />
                <MatchTypeToggle value={newTermMatchType} onChange={setNewTermMatchType} />
                <div style={{ display: 'flex', gap: 8 }}>
                  <button onClick={handleCreateTerm} disabled={saving} style={{ ...btnSuccess, opacity: saving ? 0.6 : 1, cursor: saving ? 'not-allowed' : 'pointer' }}>
                    {saving ? 'Создание...' : 'Добавить'}
                  </button>
                  <button onClick={() => { hapticFeedback('light'); setShowNewTermForm(false); setNewTermValue(''); setNewTermMatchType('partial') }} disabled={saving} style={btnSecondary}>Отмена</button>
                </div>
              </div>
            </div>
          )}

          {!showNewTermForm && (
            <button onClick={() => { hapticFeedback('light'); setShowNewTermForm(true); setEditingTerm(null) }} style={addBtnStyle}>
              + Добавить термин
            </button>
          )}
        </Section>
      )}

      {/* Источники для упоминаний — только для админов */}
      {isAdmin && (
        <Section title="Источники для упоминаний" count={mentionSources.length}>
          {mentionSources.map((src, i) => (
            <div key={src.id}>
              {editingMentionSource?.id === src.id ? (
                <div style={{ padding: 16, borderBottom: i < mentionSources.length - 1 ? '1px solid #2a2a3a' : 'none' }}>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                    <div>
                      <div style={{ fontSize: 13, color: '#9ca3af', marginBottom: 8 }}>Тип источника</div>
                      <div style={{ display: 'flex', gap: 8 }}>
                        <button onClick={() => { hapticFeedback('light'); setEditMsSourceType('telegram') }} style={editMsSourceType === 'telegram' ? sourceTypeBtnActive : sourceTypeBtn}>📱 Telegram</button>
                        <button onClick={() => { hapticFeedback('light'); setEditMsSourceType('website') }} style={editMsSourceType === 'website' ? sourceTypeBtnActive : sourceTypeBtn}>🌐 Веб-сайт</button>
                      </div>
                    </div>

                    {editMsSourceType === 'telegram' ? (
                      <div style={{ position: 'relative' }}>
                        <span style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', color: '#6b7280', fontSize: 15 }}>@</span>
                        <input type="text" value={editMsUsername} onChange={(e) => setEditMsUsername(e.target.value.replace(/^@/, ''))} placeholder="username" style={{ ...inputStyle, paddingLeft: 28 }} />
                      </div>
                    ) : (
                      <>
                        <input type="text" value={editMsUrl} onChange={(e) => setEditMsUrl(e.target.value)} placeholder="https://example.com/news" style={inputStyle} />
                        <input type="text" value={editMsCssConfig} onChange={(e) => setEditMsCssConfig(e.target.value)} placeholder="CSS-селекторы (JSON, необязательно)" style={inputStyle} />
                      </>
                    )}

                    <input type="text" value={editMsTitle} onChange={(e) => setEditMsTitle(e.target.value)} placeholder="Название (необязательно)" style={inputStyle} />

                    <div style={{ display: 'flex', gap: 8 }}>
                      <button onClick={handleSaveMentionSource} disabled={saving} style={{ ...btnPrimary, opacity: saving ? 0.6 : 1, cursor: saving ? 'not-allowed' : 'pointer' }}>
                        {saving ? 'Сохранение...' : 'Сохранить'}
                      </button>
                      <button onClick={() => { hapticFeedback('light'); setEditingMentionSource(null) }} disabled={saving} style={btnSecondary}>Отмена</button>
                      <button onClick={() => handleDeleteMentionSource(src)} disabled={saving} style={btnDanger}>Удалить</button>
                    </div>
                  </div>
                </div>
              ) : (
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '14px 16px', borderBottom: i < mentionSources.length - 1 ? '1px solid #2a2a3a' : 'none' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10, flex: 1, minWidth: 0 }}>
                    <button
                      onClick={() => handleToggleMentionSourceActive(src)}
                      style={{
                        width: 20, height: 20, borderRadius: 4, border: '2px solid ' + (src.is_active ? '#10b981' : '#4b5563'),
                        backgroundColor: src.is_active ? '#10b981' : 'transparent',
                        cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center',
                        flexShrink: 0, padding: 0
                      }}
                    >
                      {src.is_active && <span style={{ color: '#fff', fontSize: 12, lineHeight: 1 }}>✓</span>}
                    </button>
                    <span style={{ fontSize: 14, flexShrink: 0 }}>{src.source_type === 'website' ? '🌐' : '📱'}</span>
                    <div style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {src.source_type === 'website' ? (
                        <>
                          <span style={{ fontSize: 15, color: src.is_active ? '#fff' : '#6b7280' }}>{src.title || src.url}</span>
                          {src.title && src.url && <span style={{ fontSize: 12, color: '#6b7280', marginLeft: 8 }}>{src.url}</span>}
                        </>
                      ) : (
                        <>
                          <span style={{ fontSize: 15, color: src.is_active ? '#fff' : '#6b7280' }}>@{src.username}</span>
                          {src.title && <span style={{ fontSize: 13, color: '#6b7280', marginLeft: 8 }}>{src.title}</span>}
                        </>
                      )}
                    </div>
                  </div>
                  <button onClick={() => handleEditMentionSource(src)} style={{ background: 'none', border: 'none', color: '#6b7280', fontSize: 16, cursor: 'pointer', flexShrink: 0 }}>✎</button>
                </div>
              )}
            </div>
          ))}

          {showNewMentionSourceForm && (
            <div style={{ padding: 16, borderTop: mentionSources.length > 0 ? '1px solid #2a2a3a' : 'none' }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                <div>
                  <div style={{ fontSize: 13, color: '#9ca3af', marginBottom: 8 }}>Тип источника</div>
                  <div style={{ display: 'flex', gap: 8 }}>
                    <button onClick={() => { hapticFeedback('light'); setNewMsSourceType('telegram') }} style={newMsSourceType === 'telegram' ? sourceTypeBtnActive : sourceTypeBtn}>📱 Telegram</button>
                    <button onClick={() => { hapticFeedback('light'); setNewMsSourceType('website') }} style={newMsSourceType === 'website' ? sourceTypeBtnActive : sourceTypeBtn}>🌐 Веб-сайт</button>
                  </div>
                </div>

                {newMsSourceType === 'telegram' ? (
                  <div style={{ position: 'relative' }}>
                    <span style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', color: '#6b7280', fontSize: 15 }}>@</span>
                    <input type="text" value={newMsUsername} onChange={(e) => setNewMsUsername(e.target.value.replace(/^@/, ''))} placeholder="username" style={{ ...inputStyle, paddingLeft: 28 }} />
                  </div>
                ) : (
                  <>
                    <input type="text" value={newMsUrl} onChange={(e) => setNewMsUrl(e.target.value)} placeholder="https://example.com/news" style={inputStyle} />
                    <input type="text" value={newMsCssConfig} onChange={(e) => setNewMsCssConfig(e.target.value)} placeholder="CSS-селекторы (JSON, необязательно)" style={inputStyle} />
                  </>
                )}

                <input type="text" value={newMsTitle} onChange={(e) => setNewMsTitle(e.target.value)} placeholder="Название (необязательно)" style={inputStyle} />

                <div style={{ display: 'flex', gap: 8 }}>
                  <button onClick={handleCreateMentionSource} disabled={saving} style={{ ...btnSuccess, opacity: saving ? 0.6 : 1, cursor: saving ? 'not-allowed' : 'pointer' }}>
                    {saving ? 'Создание...' : 'Добавить источник'}
                  </button>
                  <button onClick={() => { hapticFeedback('light'); setShowNewMentionSourceForm(false); setNewMsUsername(''); setNewMsTitle(''); setNewMsSourceType('telegram'); setNewMsUrl(''); setNewMsCssConfig('') }} disabled={saving} style={btnSecondary}>Отмена</button>
                </div>
              </div>
            </div>
          )}

          {!showNewMentionSourceForm && (
            <button onClick={() => { hapticFeedback('light'); setShowNewMentionSourceForm(true); setEditingMentionSource(null) }} style={addBtnStyle}>
              + Добавить источник
            </button>
          )}
        </Section>
      )}

      {/* Игнорируемые источники — только для админов */}
      {isAdmin && (
        <Section title="Игнорируемые источники" count={ignoredSources.length}>
          <div style={{ padding: '8px 16px 4px', fontSize: 12, color: '#6b7280', lineHeight: 1.5 }}>
            Упоминания с этих сайтов и каналов не сохраняются. Домены игнорируются с поддоменами. Для TG-каналов укажите путь: t.me/channel_name
          </div>
          {ignoredSources.map((src, i) => (
            <div key={src.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px 16px', borderTop: '1px solid #2a2a3a' }}>
              <div style={{ overflow: 'hidden', flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 14, color: '#fff', fontFamily: 'monospace', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{src.pattern}</div>
                {src.description && <div style={{ fontSize: 12, color: '#6b7280', marginTop: 2 }}>{src.description}</div>}
              </div>
              <button
                onClick={() => handleDeleteIgnoredSource(src)}
                disabled={saving}
                style={{ background: 'none', border: 'none', color: '#ef4444', fontSize: 18, cursor: 'pointer', flexShrink: 0, padding: '0 0 0 12px', lineHeight: 1 }}
              >
                ×
              </button>
            </div>
          ))}

          {showNewIgnoredForm && (
            <div style={{ padding: 16, borderTop: '1px solid #2a2a3a' }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                <input
                  type="text"
                  value={newIgnoredPattern}
                  onChange={(e) => setNewIgnoredPattern(e.target.value)}
                  placeholder="example.com или t.me/channel_name"
                  style={inputStyle}
                  autoFocus
                />
                <div style={{ display: 'flex', gap: 8 }}>
                  <button onClick={handleCreateIgnoredSource} disabled={saving} style={{ ...btnSuccess, opacity: saving ? 0.6 : 1, cursor: saving ? 'not-allowed' : 'pointer' }}>
                    {saving ? 'Добавление...' : 'Добавить'}
                  </button>
                  <button onClick={() => { hapticFeedback('light'); setShowNewIgnoredForm(false); setNewIgnoredPattern('') }} disabled={saving} style={btnSecondary}>Отмена</button>
                </div>
              </div>
            </div>
          )}

          {!showNewIgnoredForm && (
            <button onClick={() => { hapticFeedback('light'); setShowNewIgnoredForm(true) }} style={addBtnStyle}>
              + Добавить исключение
            </button>
          )}
        </Section>
      )}

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
        <div style={{ fontSize: 13, color: '#6b7280' }}>Версия {import.meta.env.VITE_APP_VERSION}</div>
        <div style={{ fontSize: 12, color: '#4b5563', marginTop: 4 }}>© 2026 SKAI Eye</div>
      </div>
    </div>
  )
}

// --- Shared styles ---

const inputStyle = {
  width: '100%',
  padding: '10px 12px',
  fontSize: 15,
  backgroundColor: '#0d0d14',
  border: '1px solid #2a2a3a',
  borderRadius: 8,
  color: '#fff',
  outline: 'none',
  boxSizing: 'border-box'
}

const btnPrimary = {
  flex: 1,
  padding: '10px 16px',
  fontSize: 14,
  fontWeight: 500,
  backgroundColor: '#3b82f6',
  color: '#fff',
  border: 'none',
  borderRadius: 8,
}

const btnSuccess = {
  flex: 1,
  padding: '10px 16px',
  fontSize: 14,
  fontWeight: 500,
  backgroundColor: '#10b981',
  color: '#fff',
  border: 'none',
  borderRadius: 8,
}

const btnSecondary = {
  padding: '10px 16px',
  fontSize: 14,
  backgroundColor: '#374151',
  color: '#fff',
  border: 'none',
  borderRadius: 8,
  cursor: 'pointer'
}

const btnDanger = {
  padding: '10px 16px',
  fontSize: 14,
  backgroundColor: '#ef444420',
  color: '#ef4444',
  border: 'none',
  borderRadius: 8,
  cursor: 'pointer'
}

const addBtnStyle = {
  width: '100%',
  padding: 14,
  background: 'none',
  border: 'none',
  borderTop: '1px solid #2a2a3a',
  color: '#3b82f6',
  fontSize: 14,
  fontWeight: 500,
  cursor: 'pointer'
}

const sourceTypeBtn = {
  padding: '8px 16px',
  fontSize: 14,
  fontWeight: 500,
  backgroundColor: '#252532',
  color: '#9ca3af',
  border: 'none',
  borderRadius: 8,
  cursor: 'pointer'
}

const sourceTypeBtnActive = {
  padding: '8px 16px',
  fontSize: 14,
  fontWeight: 500,
  backgroundColor: '#3b82f620',
  color: '#3b82f6',
  border: 'none',
  borderRadius: 8,
  cursor: 'pointer'
}

// --- Shared components ---

function MatchTypeToggle({ value, onChange }) {
  return (
    <div>
      <div style={{ fontSize: 12, color: '#6b7280', marginBottom: 6 }}>Тип совпадения</div>
      <div style={{ display: 'flex', gap: 6 }}>
        <button
          onClick={() => { hapticFeedback('light'); onChange('partial') }}
          style={{
            padding: '6px 14px', fontSize: 13, fontWeight: 500, border: 'none', borderRadius: 8, cursor: 'pointer',
            backgroundColor: value === 'partial' ? '#3b82f620' : '#252532',
            color: value === 'partial' ? '#60a5fa' : '#9ca3af',
          }}
        >
          Частичное
        </button>
        <button
          onClick={() => { hapticFeedback('light'); onChange('full') }}
          style={{
            padding: '6px 14px', fontSize: 13, fontWeight: 500, border: 'none', borderRadius: 8, cursor: 'pointer',
            backgroundColor: value === 'full' ? '#f59e0b22' : '#252532',
            color: value === 'full' ? '#f59e0b' : '#9ca3af',
          }}
        >
          Полное
        </button>
      </div>
      <div style={{ fontSize: 11, color: '#4b5563', marginTop: 5 }}>
        {value === 'full'
          ? 'Весь текст запроса должен быть в сниппете'
          : 'Достаточно первого слова (бренда) в сниппете'}
      </div>
    </div>
  )
}

function ColorButton({ color, selected, onClick }) {
  return (
    <button
      onClick={onClick}
      style={{
        width: 32,
        height: 32,
        borderRadius: 8,
        backgroundColor: color,
        border: selected ? '2px solid #fff' : '2px solid transparent',
        cursor: 'pointer',
        transition: 'all 0.2s'
      }}
    />
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
