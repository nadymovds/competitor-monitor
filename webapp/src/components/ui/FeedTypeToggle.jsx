import React from 'react'
import { hapticFeedback } from '../../services/telegram'

export default function FeedTypeToggle({ feedType, onChange }) {
  const types = [
    { id: 'all', label: 'Все' },
    { id: 'competitors', label: 'Конкуренты' },
    { id: 'news', label: 'Новости отрасли' }
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
            backgroundColor: feedType === type.id ? '#3b82f6' : 'transparent',
            color: feedType === type.id ? '#fff' : '#9ca3af'
          }}
        >
          {type.label}
        </button>
      ))}
    </div>
  )
}

const styles = {
  container: {
    display: 'flex',
    gap: 0,
    backgroundColor: '#1a1a24',
    borderRadius: 8,
    padding: 3,
    border: '1px solid #2a2a3a'
  },
  button: {
    flex: 1,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    padding: '8px 12px',
    borderRadius: 6,
    border: 'none',
    cursor: 'pointer',
    fontSize: 13,
    fontWeight: 500,
    transition: 'all 0.2s',
    whiteSpace: 'nowrap'
  }
}
