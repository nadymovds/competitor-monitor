import React from 'react'

export default function NextScanInfo({ scanType }) {
  // Вычисляем дату следующего сканирования
  const getNextScanTime = () => {
    const now = new Date()
    const nextScan = new Date()
    
    // Устанавливаем следующий понедельник
    const daysUntilMonday = (1 - now.getDay() + 7) % 7 || 7
    nextScan.setDate(now.getDate() + daysUntilMonday)
    
    if (scanType === 'competitors') {
      // Конкуренты: Понедельник 15:30 МСК
      nextScan.setHours(15, 30, 0, 0)
    } else {
      // Новости: Понедельник 15:00 МСК
      nextScan.setHours(15, 0, 0, 0)
    }
    
    // Если сегодня понедельник и время уже прошло, берём следующий понедельник
    if (now.getDay() === 1) {
      const targetHour = scanType === 'competitors' ? 15 : 15
      const targetMinute = scanType === 'competitors' ? 30 : 0
      if (now.getHours() > targetHour || (now.getHours() === targetHour && now.getMinutes() >= targetMinute)) {
        nextScan.setDate(nextScan.getDate() + 7)
      }
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
    padding: '10px 16px',
    backgroundColor: '#1a1a24',
    borderRadius: 8,
    border: '1px solid #2a2a3a'
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
