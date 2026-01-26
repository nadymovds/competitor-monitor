import { jsPDF } from 'jspdf'

// Цвета для категорий (как в Python версии)
const CATEGORY_COLORS = {
  products: [34, 197, 94],    // #22c55e - зелёный
  prices: [239, 68, 68],      // #ef4444 - красный
  news: [245, 158, 11]        // #f59e0b - оранжевый
}

const CATEGORY_LABELS = {
  products: 'ПРОДУКТЫ',
  prices: 'ЦЕНЫ',
  news: 'НОВОСТИ'
}

const CATEGORY_EMOJI = {
  products: '',
  prices: '',
  news: ''
}

// Цвета для тегов
const TAG_COLORS = {
  'новый продукт': [34, 197, 94],
  'обновление': [59, 130, 246],
  'акция': [239, 68, 68],
  'новость': [245, 158, 11],
  'интеграция': [168, 85, 247],
  'тарифы': [236, 72, 153]
}

/**
 * Генерирует PDF отчёт по результатам сканирования
 * @param {Object} report - данные отчёта из summary_reports
 * @param {Array} changes - массив изменений из changes таблицы
 */
export function generateReportPDF(report, changes) {
  const doc = new jsPDF({
    orientation: 'portrait',
    unit: 'mm',
    format: 'a4'
  })

  const pageWidth = doc.internal.pageSize.getWidth()
  const pageHeight = doc.internal.pageSize.getHeight()
  const margin = 15
  const contentWidth = pageWidth - margin * 2
  let y = margin

  // Заголовок
  doc.setFontSize(16)
  doc.setFont('helvetica', 'bold')
  doc.text('Отчёт мониторинга конкурентов', pageWidth / 2, y, { align: 'center' })
  y += 8

  // Дата
  doc.setFontSize(10)
  doc.setFont('helvetica', 'normal')
  doc.setTextColor(128, 128, 128)
  const dateStr = formatDateRussian(report.report_date)
  doc.text(dateStr, pageWidth / 2, y, { align: 'center' })
  y += 12

  // Статистика
  doc.setTextColor(0, 0, 0)
  doc.setFontSize(9)

  const stats = [
    `Конкурентов: ${report.total_sites || 0}`,
    `Успешно: ${report.successful_sites || 0}`,
    `Изменений: ${report.changes_count || changes.length}`,
    `Проблем: ${report.problems_count || 0}`
  ]

  const successRate = report.total_sites
    ? Math.round((report.successful_sites / report.total_sites) * 100)
    : 0
  stats.push(`Успешность: ${successRate}%`)

  doc.text(stats.join('  |  '), pageWidth / 2, y, { align: 'center' })
  y += 15

  // Группируем изменения по категориям
  const categorized = {
    products: changes.filter(c => c.category === 'products'),
    prices: changes.filter(c => c.category === 'prices'),
    news: changes.filter(c => c.category === 'news')
  }

  // Отрисовка категорий
  const categories = ['products', 'prices', 'news']

  for (const category of categories) {
    const items = categorized[category]
    if (items.length === 0) continue

    // Проверяем нужна ли новая страница
    if (y > pageHeight - 40) {
      doc.addPage()
      y = margin
    }

    // Заголовок категории
    const [r, g, b] = CATEGORY_COLORS[category]
    doc.setFontSize(12)
    doc.setFont('helvetica', 'bold')
    doc.setTextColor(r, g, b)
    doc.text(`${CATEGORY_EMOJI[category]} ${CATEGORY_LABELS[category]}`, margin, y)
    y += 8

    // Элементы категории
    for (const item of items) {
      // Проверяем нужна ли новая страница
      if (y > pageHeight - 30) {
        doc.addPage()
        y = margin
      }

      // Название компании
      doc.setFontSize(10)
      doc.setFont('helvetica', 'bold')
      doc.setTextColor(0, 0, 0)

      let companyName = item.competitor_name || 'Неизвестный'
      if (item.url_label) {
        companyName += ` [${item.url_label}]`
      }
      doc.text(companyName, margin, y)

      // URL как ссылка
      const url = item.scanned_url || item.competitor_url
      if (url) {
        const fullUrl = url.startsWith('http') ? url : `https://${url}`
        doc.setFontSize(8)
        doc.setTextColor(59, 130, 246)
        doc.textWithLink(url, margin, y + 4, { url: fullUrl })
      }
      y += 10

      // Summary текст
      doc.setFontSize(9)
      doc.setFont('helvetica', 'normal')
      doc.setTextColor(60, 60, 60)

      const summary = item.summary || 'Нет описания'
      const lines = doc.splitTextToSize(summary, contentWidth - 5)

      for (const line of lines) {
        if (y > pageHeight - 15) {
          doc.addPage()
          y = margin
        }
        doc.text(line, margin + 3, y)
        y += 4.5
      }

      // Теги
      if (item.tags && item.tags.length > 0) {
        y += 2
        doc.setFontSize(8)
        let tagX = margin + 3

        for (const tag of item.tags) {
          const tagWidth = doc.getTextWidth(tag) + 4

          if (tagX + tagWidth > pageWidth - margin) {
            tagX = margin + 3
            y += 5
          }

          // Фон тега
          const tagColor = TAG_COLORS[tag.toLowerCase()] || [156, 163, 175]
          doc.setFillColor(tagColor[0], tagColor[1], tagColor[2], 0.2)
          doc.roundedRect(tagX - 1, y - 3, tagWidth, 4.5, 1, 1, 'F')

          // Текст тега
          doc.setTextColor(tagColor[0], tagColor[1], tagColor[2])
          doc.text(tag, tagX + 1, y)
          tagX += tagWidth + 2
        }
        y += 6
      }

      y += 6
    }

    y += 5
  }

  // Если нет изменений
  if (changes.length === 0) {
    doc.setFontSize(12)
    doc.setTextColor(128, 128, 128)
    doc.text('Нет значимых изменений за этот период', pageWidth / 2, y + 20, { align: 'center' })
  }

  // Сохраняем файл
  const fileName = `competitor_report_${formatDateForFilename(report.report_date)}.pdf`
  doc.save(fileName)

  return fileName
}

function formatDateRussian(dateStr) {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  const months = [
    'января', 'февраля', 'марта', 'апреля', 'мая', 'июня',
    'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря'
  ]
  return `${date.getDate()} ${months[date.getMonth()]} ${date.getFullYear()}`
}

function formatDateForFilename(dateStr) {
  if (!dateStr) return 'unknown'
  const date = new Date(dateStr)
  return date.toISOString().split('T')[0]
}
