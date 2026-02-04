import React from 'react'

const scheduleByType = {
  competitors: {
    label: 'Следующее сканирование конкурентов',
    time: 'Пн 15:30 МСК',
  },
  news: {
    label: 'Следующее сканирование новостей',
    time: 'Пн 15:00 МСК',
  },
}

export default function NextScanInfo({ type = 'competitors' }) {
  const schedule = scheduleByType[type] || scheduleByType.competitors

  return (
    <div style={styles.wrapper}>
      <div style={styles.dot} />
      <div style={styles.texts}>
        <span style={styles.label}>{schedule.label}</span>
        <span style={styles.time}>{schedule.time}</span>
      </div>
    </div>
  )
}

const styles = {
  wrapper: {
    display: 'flex',
    alignItems: 'center',
    gap: 12,
    padding: '10px 14px',
    backgroundColor: '#151521',
    border: '1px solid #2a2a3a',
    borderRadius: 12,
  },
  dot: {
    width: 10,
    height: 10,
    borderRadius: '50%',
    backgroundColor: '#22c55e',
    boxShadow: '0 0 12px rgba(34, 197, 94, 0.6)',
  },
  texts: {
    display: 'flex',
    flexDirection: 'column',
    gap: 2,
  },
  label: {
    fontSize: 12,
    color: '#9ca3af',
  },
  time: {
    fontSize: 15,
    fontWeight: 600,
    color: '#fff',
  },
}
