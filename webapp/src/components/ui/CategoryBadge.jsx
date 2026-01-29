import React from 'react'

export default function CategoryBadge({ name, color, isManual, onRemove, size = 'normal' }) {
  const isSmall = size === 'small'

  const badgeStyle = {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 4,
    backgroundColor: `${color}26`,
    color: color,
    borderRadius: 6,
    padding: isSmall ? '2px 6px' : '4px 8px',
    fontSize: isSmall ? 10 : 12,
    fontWeight: 500,
    border: isManual ? `1px solid ${color}` : 'none',
    lineHeight: 1.3,
  }

  const dotStyle = {
    fontSize: isSmall ? 8 : 10,
  }

  return (
    <span style={badgeStyle}>
      <span style={dotStyle}>●</span>
      {name}
      {onRemove && (
        <span
          onClick={onRemove}
          style={styles.removeBtn}
          role="button"
        >
          ✕
        </span>
      )}
    </span>
  )
}

const styles = {
  removeBtn: {
    fontSize: 10,
    cursor: 'pointer',
    opacity: 0.7,
    marginLeft: 2,
  },
}
