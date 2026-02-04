import React, { useState, useRef, useEffect } from 'react'
import { hapticFeedback } from '../../services/telegram'

export default function MultiSelect({ 
  options = [], 
  selectedIds = [], 
  onChange, 
  placeholder = 'Выберите...', 
  label = '' 
}) {
  const [isOpen, setIsOpen] = useState(false)
  const dropdownRef = useRef(null)

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setIsOpen(false)
      }
    }

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside)
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [isOpen])

  const toggleDropdown = () => {
    hapticFeedback('light')
    setIsOpen(!isOpen)
  }

  const toggleOption = (id) => {
    hapticFeedback('light')
    const newSelected = selectedIds.includes(id)
      ? selectedIds.filter(x => x !== id)
      : [...selectedIds, id]
    onChange(newSelected)
  }

  const selectedOptions = options.filter(opt => selectedIds.includes(opt.id))
  const displayText = selectedOptions.length > 0
    ? selectedOptions.map(opt => opt.name).join(', ')
    : placeholder

  return (
    <div style={styles.container} ref={dropdownRef}>
      {label && <div style={styles.label}>{label}</div>}
      
      <button onClick={toggleDropdown} style={styles.trigger}>
        <span style={{ 
          ...styles.triggerText, 
          color: selectedOptions.length > 0 ? '#e5e7eb' : '#6b7280' 
        }}>
          {displayText}
        </span>
        <span style={{ 
          ...styles.arrow, 
          transform: isOpen ? 'rotate(180deg)' : 'rotate(0)' 
        }}>
          ▼
        </span>
      </button>

      {isOpen && (
        <div style={styles.dropdown}>
          {options.map(option => {
            const isSelected = selectedIds.includes(option.id)
            return (
              <div
                key={option.id}
                onClick={() => toggleOption(option.id)}
                style={{
                  ...styles.option,
                  backgroundColor: isSelected ? '#252532' : 'transparent'
                }}
              >
                <div style={styles.checkbox}>
                  {isSelected && <div style={styles.checkmark}>✓</div>}
                </div>
                <div style={styles.optionContent}>
                  {option.color && (
                    <span style={{ 
                      ...styles.colorDot, 
                      backgroundColor: option.color 
                    }} />
                  )}
                  <span style={styles.optionText}>{option.name}</span>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

const styles = {
  container: {
    position: 'relative',
    width: '100%'
  },
  label: {
    fontSize: 14,
    color: '#9ca3af',
    marginBottom: 8
  },
  trigger: {
    width: '100%',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '10px 12px',
    backgroundColor: '#1a1a24',
    border: '1px solid #2a2a3a',
    borderRadius: 8,
    cursor: 'pointer',
    transition: 'all 0.2s'
  },
  triggerText: {
    fontSize: 13,
    flex: 1,
    textAlign: 'left',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap'
  },
  arrow: {
    fontSize: 10,
    color: '#6b7280',
    marginLeft: 8,
    transition: 'transform 0.2s',
    flexShrink: 0
  },
  dropdown: {
    position: 'absolute',
    top: '100%',
    left: 0,
    right: 0,
    marginTop: 4,
    backgroundColor: '#1a1a24',
    border: '1px solid #2a2a3a',
    borderRadius: 8,
    maxHeight: 240,
    overflowY: 'auto',
    zIndex: 1000,
    boxShadow: '0 4px 12px rgba(0,0,0,0.3)'
  },
  option: {
    display: 'flex',
    alignItems: 'center',
    gap: 10,
    padding: '10px 12px',
    cursor: 'pointer',
    transition: 'background-color 0.15s'
  },
  checkbox: {
    width: 18,
    height: 18,
    borderRadius: 4,
    border: '2px solid #3b82f6',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    flexShrink: 0
  },
  checkmark: {
    fontSize: 12,
    color: '#3b82f6',
    fontWeight: 700
  },
  optionContent: {
    flex: 1,
    display: 'flex',
    alignItems: 'center',
    gap: 8
  },
  colorDot: {
    width: 8,
    height: 8,
    borderRadius: '50%',
    flexShrink: 0
  },
  optionText: {
    fontSize: 13,
    color: '#e5e7eb'
  }
}
