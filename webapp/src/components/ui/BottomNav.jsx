import React from 'react'
import { hapticFeedback } from '../../services/telegram'

export default function BottomNav({ activeTab, onTabChange }) {
  const tabs = [
    { id: 'feed', label: 'Лента', icon: '🗞️' },
    { id: 'scans', label: 'Сканирования', icon: '🛰️' },
    { id: 'competitors', label: 'Конкуренты', icon: '👥' },
    { id: 'settings', label: 'Настройки', icon: '⚙️' }
  ]

  const handleClick = (id) => {
    if (id !== activeTab) {
      hapticFeedback('light')
      onTabChange(id)
    }
  }

  return (
    <nav style={styles.nav}>
      {tabs.map(tab => (
        <button key={tab.id} onClick={() => handleClick(tab.id)} style={{...styles.tab, color: activeTab === tab.id ? '#3b82f6' : '#6b7280'}}>
          <span style={{ fontSize: 22 }}>{tab.icon}</span>
          <span style={{ fontSize: 11, fontWeight: 500 }}>{tab.label}</span>
        </button>
      ))}
    </nav>
  )
}

const styles = {
  nav: { position: 'fixed', bottom: 0, left: 0, right: 0, display: 'flex', justifyContent: 'space-around', backgroundColor: '#1a1a24', borderTop: '1px solid #2a2a3a', padding: '8px 0', paddingBottom: 'max(8px, env(safe-area-inset-bottom))', zIndex: 100 },
  tab: { display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4, padding: '8px 12px', background: 'none', border: 'none', cursor: 'pointer' }
}
