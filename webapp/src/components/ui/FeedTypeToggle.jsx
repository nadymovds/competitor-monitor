import React from 'react'
import { hapticFeedback } from '../../services/telegram'

export default function FeedTypeToggle({ feedType, onChange }) {
  const types = [
    { id: 'all', label: 'Все', icon: '📊' },
    { id: 'competitors', label: 'Конкуренты', icon: '👥' },
    { id: 'news', label: 'Новости отрасли', icon: '📰' }
  ]

  const handleClick = (id) => {
    if (id !== feedType) {
      hapticFeedback('light')
      onChange(id)
    }
  }

  return (
    <div style={styles.container}>
      {types.map(type => (
        <button
          key={type.id}
          onClick={() => handleClick(type.id)}
          style={{
            ...styles.button,
            backgroundColor: feedType === type.id ? '#3b82f6' : '#252532',
            color: feedType === type.id ? '#fff' : '#9ca3af',
            borderColor: feedType === type.id ? '#3b82f6' : 'transparent'
          }}
        >
          <span style={{ fontSize: 18 }}>{type.icon}</span>
          <span style={{ fontSize: 13, fontWeight: 500 }}>{type.label}</span>
        </button>
      ))}
    </div>
  )
}

const styles = {
  container: {
    display: 'flex',
    gap: 8,
    padding: '8px 0'
  },
  button: {
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: 6,
    padding: '12px 8px',
    borderRadius: 12,
    border: '1px solid',
    cursor: 'pointer',
    transition: 'all 0.2s'
  }
}
