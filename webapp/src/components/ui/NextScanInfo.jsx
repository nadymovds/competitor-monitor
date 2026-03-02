import React from 'react'

export default function NextScanInfo({ scanType }) {
  // Вычисляем дату следующего сканирования
  const getNextScanTime = () => {
    const now = new Date()
    const nextScan = new Date()
    const targetDay = scanType === 'competitors' ? 4 : 5 // 4 = четверг, 5 = пятница
    const targetHour = scanType === 'competitors' ? 18 : 9
    const targetMinute = 0
    
    const daysUntilTarget = (targetDay - now.getDay() + 7) % 7
    nextScan.setDate(now.getDate() + daysUntilTarget)
    nextScan.setHours(targetHour, targetMinute, 0, 0)
    
    if (daysUntilTarget === 0 && now >= nextScan) {
      nextScan.setDate(nextScan.getDate() + 7)
    }
    
    return nextScan
  }

  const formatNextScan = () => {
    const nextScan = getNextScanTime()
    const dayOfWeek = nextScan.toLocaleDateString('ru-RU', { weekday: 'short' })
    const time = nextScan.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
    const date = nextScan.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })
    
    return `${dayOfWeek.charAt(0).toUpperCase() + dayOfWeek.slice(1)} ${date}, ${time} МСК`
  }

  return (
    <div style={styles.container}>
      <div style={styles.label}>Следующее сканирование:</div>
      <div style={styles.time}>{formatNextScan()}</div>
    </div>
  )
}

const styles = {
  container: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    padding: '10px 16px'
  },
  label: {
    fontSize: 13,
    color: '#9ca3af'
  },
  time: {
    fontSize: 13,
    fontWeight: 600,
    color: '#3b82f6'
  }
}
