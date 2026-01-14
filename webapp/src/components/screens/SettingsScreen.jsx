import React from 'react'
import { hapticFeedback, showAlert } from '../../services/telegram'

export default function SettingsScreen({ user, groups }) {
  const isAdmin = user?.role === 'admin'
  const soon = () => { hapticFeedback('warning'); showAlert('Эта функция скоро будет доступна') }

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
          <div key={g.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '14px 16px', borderBottom: i < groups.length - 1 ? '1px solid #2a2a3a' : 'none' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <span style={{ width: 10, height: 10, borderRadius: '50%', backgroundColor: g.color }} />
              <span style={{ fontSize: 15, color: '#fff' }}>{g.name}</span>
            </div>
            {isAdmin && <button onClick={soon} style={{ background: 'none', border: 'none', color: '#6b7280', fontSize: 16, cursor: 'pointer' }}>✎</button>}
          </div>
        ))}
        {isAdmin && <button onClick={soon} style={{ width: '100%', padding: 14, background: 'none', border: 'none', borderTop: '1px solid #2a2a3a', color: '#3b82f6', fontSize: 14, fontWeight: 500, cursor: 'pointer' }}>+ Добавить группу</button>}
      </Section>

      <Section title="Уведомления">
        <Row label="Об изменениях" desc="Получать уведомления о новых изменениях" toggle enabled onToggle={soon} />
        <Row label="Об ошибках" desc="Получать уведомления о проблемах сканирования" toggle enabled={false} onToggle={soon} border />
      </Section>

      {isAdmin && (
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
