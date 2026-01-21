export const tg = window.Telegram?.WebApp

export function initTelegram() {
  if (!tg) return false
  tg.ready()
  tg.expand()
  tg.enableClosingConfirmation()
  tg.setHeaderColor('#0d0d14')
  tg.setBackgroundColor('#0d0d14')
  return true
}

export function getTelegramUser() {
  if (!tg?.initDataUnsafe?.user) {
    if (import.meta.env.DEV) {
      return { id: 457121917, first_name: 'Dev', last_name: 'User', username: 'devuser' }
    }
    return null
  }
  return tg.initDataUnsafe.user
}

export function hapticFeedback(type = 'light') {
  if (!tg?.HapticFeedback) return
  if (type === 'light' || type === 'medium' || type === 'heavy') {
    tg.HapticFeedback.impactOccurred(type)
  } else if (type === 'success' || type === 'warning' || type === 'error') {
    tg.HapticFeedback.notificationOccurred(type)
  }
}

export function openLink(url) {
  if (tg?.openLink) tg.openLink(url)
  else window.open(url, '_blank')
}

export function showBackButton(onClick) {
  if (!tg?.BackButton) return
  tg.BackButton.onClick(onClick)
  tg.BackButton.show()
}

export function hideBackButton() {
  if (!tg?.BackButton) return
  tg.BackButton.hide()
}

export function showAlert(message) {
  if (tg?.showAlert) return new Promise(r => tg.showAlert(message, r))
  alert(message)
  return Promise.resolve()
}

export function showConfirm(message) {
  if (tg?.showConfirm) return new Promise(r => tg.showConfirm(message, r))
  return Promise.resolve(window.confirm(message))
}
