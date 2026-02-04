import React, { useState, useEffect } from 'react'
import './App.css'
import FeedScreen from './components/screens/FeedScreen'
import ScansScreen from './components/screens/ScansScreen'
import CompetitorsScreen from './components/screens/CompetitorsScreen'
import SettingsScreen from './components/screens/SettingsScreen'
import BottomNav from './components/ui/BottomNav'
import { getTelegramUser } from './services/telegram'
import { checkUserAccess, getGroups } from './services/supabase'

export default function App() {
  const [activeTab, setActiveTab] = useState('feed')
  const [user, setUser] = useState(null)
  const [groups, setGroups] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [accessDenied, setAccessDenied] = useState(false)
  const [selectedCompetitorId, setSelectedCompetitorId] = useState(null)
  const [cameFromFeed, setCameFromFeed] = useState(false)

  useEffect(() => {
    async function init() {
      try {
        setLoading(true)
        const telegramUser = getTelegramUser()
        if (!telegramUser) {
          setAccessDenied(true)
          return
        }
        const { allowed, user: dbUser } = await checkUserAccess(telegramUser)
        if (!allowed) {
          setAccessDenied(true)
          return
        }
        setUser(dbUser)
        const groupsData = await getGroups()
        setGroups(groupsData)
      } catch (err) {
        console.error('Init error:', err)
        setError(err.message)
      } finally {
        setLoading(false)
      }
    }
    init()
  }, [])

  const navigateToCompetitorFromFeed = (competitorId) => {
    setSelectedCompetitorId(competitorId)
    setCameFromFeed(true)
  }

  const navigateToCompetitorFromMonitoring = (competitorId) => {
    setSelectedCompetitorId(competitorId)
    setCameFromFeed(false)
  }

  const handleBackFromCompetitor = () => {
    setSelectedCompetitorId(null)
  }

  const handleBackToFeed = () => {
    setSelectedCompetitorId(null)
    setCameFromFeed(false)
    setActiveTab('feed')
  }

  const handleTabChange = (tab) => {
    if (tab !== 'competitors') {
      setSelectedCompetitorId(null)
      setCameFromFeed(false)
    }
    setActiveTab(tab)
  }

  if (loading) {
    return (
      <div style={styles.loadingContainer}>
        <div style={styles.spinner} />
        <div style={styles.loadingText}>Загрузка...</div>
      </div>
    )
  }

  if (accessDenied) {
    return (
      <div style={styles.errorContainer}>
        <div style={{ fontSize: 48 }}>🔒</div>
        <div style={{ fontSize: 18, fontWeight: 600 }}>Доступ запрещён</div>
        <div style={{ fontSize: 14, color: '#6b7280', textAlign: 'center' }}>
          У вас нет доступа к этому приложению.
          <br />
          Обратитесь к администратору.
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div style={styles.errorContainer}>
        <div style={{ fontSize: 48 }}>⚠️</div>
        <div style={{ fontSize: 18, fontWeight: 600 }}>Ошибка загрузки</div>
        <div style={{ fontSize: 14, color: '#6b7280' }}>{error}</div>
        <button style={styles.retryButton} onClick={() => window.location.reload()}>
          Попробовать снова
        </button>
      </div>
    )
  }

  const renderScreen = () => {
    if (selectedCompetitorId) {
      return (
        <CompetitorsScreen 
          competitorId={selectedCompetitorId} 
          onBack={handleBackFromCompetitor}
          onBackToFeed={cameFromFeed ? handleBackToFeed : null}
        />
      )
    }

    switch (activeTab) {
      case 'feed':
        return <FeedScreen onNavigateToCompetitor={navigateToCompetitorFromFeed} />
      case 'scans':
        return <ScansScreen onNavigateToCompetitor={navigateToCompetitorFromMonitoring} />
      case 'competitors':
        return <CompetitorsScreen />
      case 'settings':
        return <SettingsScreen />
      default:
        return <FeedScreen onNavigateToCompetitor={navigateToCompetitorFromFeed} />
    }
  }

  return (
    <div style={styles.container}>
      <main style={styles.main}>{renderScreen()}</main>
      <BottomNav activeTab={activeTab} onTabChange={handleTabChange} />
    </div>
  )
}

const styles = {
  container: {
    minHeight: '100vh',
    backgroundColor: '#0f0f19',
    color: '#fff',
    display: 'flex',
    flexDirection: 'column'
  },
  main: {
    flex: 1,
    padding: '16px 16px 80px 16px'
  },
  loadingContainer: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    height: '100vh',
    gap: 16,
    backgroundColor: '#0f0f19'
  },
  spinner: {
    width: 40,
    height: 40,
    border: '3px solid rgba(59,130,246,0.2)',
    borderTopColor: '#3b82f6',
    borderRadius: '50%',
    animation: 'spin 1s linear infinite'
  },
  loadingText: {
    color: '#6b7280',
    fontSize: 14
  },
  errorContainer: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    height: '100vh',
    gap: 12,
    padding: 24,
    backgroundColor: '#0f0f19',
    textAlign: 'center'
  },
  retryButton: {
    marginTop: 16,
    padding: '12px 24px',
    backgroundColor: '#3b82f6',
    color: '#fff',
    border: 'none',
    borderRadius: 8,
    fontSize: 14,
    fontWeight: 500,
    cursor: 'pointer'
  }
}
