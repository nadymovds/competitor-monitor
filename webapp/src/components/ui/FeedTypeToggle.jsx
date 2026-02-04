import React from 'react'
import { hapticFeedback } from '../../services/telegram'

const OPTIONS = [
  { id: 'all', label: 'Все' },
  { id: 'competitors', label: 'Конкуренты' },
  { id: 'news', label: 'Новости' },
]

export default function FeedTypeToggle({ value, onChange }) {
  const handleSelect = (id) => {
    if (id === value) return
    hapticFeedback('light')
    onChange?.(id)
  }

  return (
    <div style={styles.wrapper}>
      {OPTIONS.map(option => {
        const isActive = option.id === value
        return (
          <button
            key={option.id}
            type="button"
            onClick={() => handleSelect(option.id)}
            style={{
              ...styles.button,
              backgroundColor: isActive ? '#3b82f6' : 'transparent',
              color: isActive ? '#fff' : '#9ca3af',
              borderColor: isActive ? '#3b82f6' : '#2a2a3a',
            }}
          >
            {option.label}
          </button>
        )
      })}
    </div>
  )
}

const styles = {
  wrapper: {
    display: 'inline-flex',
    padding: 4,
    backgroundColor: '#151521',
    borderRadius: 12,
    border: '1px solid #2a2a3a',
    gap: 4,
  },
  button: {
    padding: '8px 14px',
    borderRadius: 9,
    border: '1px solid transparent',
    fontSize: 13,
    fontWeight: 600,
    cursor: 'pointer',
    transition: 'background-color 0.2s ease, color 0.2s ease',
  },
}
