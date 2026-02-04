# Архитектура системы мониторинга

## Обзор

Система мониторинга конкурентов и отраслевых новостей состоит из нескольких компонентов:

1. **Python Backend** - скрипты для сканирования и обработки
2. **Supabase** - PostgreSQL база данных + Auth
3. **Web App** - React-приложение (Vite)
4. **Telegram Bot** - интерфейс управления
5. **GitHub Actions** - автоматизация сканирования

---

## Компоненты системы

### 1. Python Backend

#### Основные модули

**`monitor.py`** - Мониторинг конкурентов
- Сканирование веб-сайтов конкурентов
- Мониторинг Telegram-каналов конкурентов
- Определение изменений через LLM
- Категоризация изменений (products/prices/services/news)
- Генерация PDF-отчетов
- Отправка уведомлений в Telegram

**`news_monitor.py`** - Мониторинг отраслевых новостей
- Сканирование новостных Telegram-каналов
- Парсинг новостных веб-сайтов
- Классификация новостей по категориям через LLM
- Дедупликация по content_hash
- Генерация новостных дайджестов
- Создание записей в `news_digests` для статистики

#### Процесс мониторинга новостей

1. **Фаза 1: Сканирование источников**
   - 1A: Telegram-каналы (через Telethon)
   - 1B: Веб-сайты (через Playwright)
   - Сохранение постов в `news_posts` с `is_processed=false`

2. **Фаза 2: LLM-обработка**
   - Обработка необработанных постов (`is_processed=false`)
   - Извлечение заголовка и саммари
   - Классификация по категориям
   - Дедупликация по `content_hash`
   - Обновление `is_processed=true`

3. **Фаза 3: Генерация дайджеста**
   - Создание записи в `news_digests` со статистикой:
     - `digest_date` - дата сканирования
     - `period_start/period_end` - период охвата
     - `posts_count` - количество постов
     - `categories_summary` - сводка по категориям (JSONB)
   - Связывание постов через `news_digest_posts`
   - Генерация PDF (опционально)
   - Отправка в Telegram

#### Зависимости

```
playwright - автоматизация браузера
telethon - Telegram API
supabase - клиент БД
openai / groq - LLM для анализа
reportlab - генерация PDF
beautifulsoup4 - парсинг HTML
aiohttp - асинхронные HTTP-запросы
```

### 2. База данных (Supabase/PostgreSQL)

См. [`DATABASE_SCHEMA.md`](./DATABASE_SCHEMA.md) для полной схемы.

#### Ключевые особенности

- **UUID для основных сущностей** - глобальная уникальность
- **Serial для служебных таблиц** - производительность
- **JSONB для гибких структур** - конфигурация, метаданные
- **Timestamp с timezone** - корректная работа с датами
- **Foreign Keys** - целостность данных
- **Мягкое удаление** - `is_active` флаги

#### Индексирование

Критичные индексы:
- По датам (`created_at`, `post_date`) для фильтрации
- По FK (`competitor_id`, `channel_id`) для JOIN
- По статусу (`is_active`, `is_processed`) для фильтрации

### 3. Web Application

#### Технологии

```
React 18 - UI фреймворк
Vite - сборщик и dev-сервер
Supabase JS Client - работа с БД
Telegram Web App SDK - интеграция с Telegram
```

#### Структура

```
webapp/
├── src/
│   ├── components/
│   │   ├── screens/      # Экраны приложения
│   │   │   ├── FeedScreen.jsx        # Единая лента
│   │   │   ├── ScansScreen.jsx       # История сканирований
│   │   │   ├── CompetitorsScreen.jsx # Список конкурентов
│   │   │   └── SettingsScreen.jsx    # Настройки
│   │   └── ui/           # UI компоненты
│   │       ├── BottomNav.jsx
│   │       ├── NewsCard.jsx
│   │       ├── ScanCard.jsx
│   │       └── ...
│   ├── services/
│   │   ├── supabase.js   # Клиент Supabase
│   │   ├── news.js       # API новостей
│   │   ├── feed.js       # API единой ленты
│   │   └── telegram.js   # Telegram Web App
│   └── main.jsx
└── index.html
```

#### Основные экраны

**FeedScreen** - Единая лента
- Объединяет изменения конкурентов и отраслевые новости
- Фильтры по типу, группам, категориям, источникам
- Infinite scroll
- Период: последние 7 дней

**ScansScreen** - История сканирований
- Переключатель: Конкуренты / Новости
- Для конкурентов: данные из `summary_reports`
- Для новостей: данные из `news_digests`
- Разворачиваемые карточки с деталями

**CompetitorsScreen** - Управление конкурентами
- Список конкурентов с группировкой
- Детальная страница конкурента
- История изменений

**SettingsScreen** - Настройки и управление
- Управление категориями новостей
- Управление каналами новостей
- Группы конкурентов

#### Работа с API

Все запросы к БД идут через Supabase JS Client:
```javascript
import { supabase } from './supabase.js'

const { data, error } = await supabase
  .from('news_posts')
  .select('*')
  .eq('is_processed', true)
```

### 4. Telegram Bot

Простой бот для управления системой через Telegram.

#### Функции

- Запуск сканирования по требованию
- Получение уведомлений о завершении
- Просмотр отчетов через Web App

#### Интеграция

- Bot API для команд и сообщений
- Web App для UI (`webapp/`)
- Inline кнопки для быстрых действий

### 5. Автоматизация (GitHub Actions)

#### Расписание

```yaml
# Мониторинг конкурентов - каждый понедельник 15:30 МСК
schedule:
  - cron: '30 12 * * 1'  # UTC

# Мониторинг новостей - каждый понедельник 15:00 МСК
schedule:
  - cron: '0 12 * * 1'  # UTC
```

#### Процесс

1. Checkout кода
2. Установка зависимостей
3. Запуск Python скрипта
4. Сохранение результатов в Supabase
5. Отправка уведомлений в Telegram

---

## Поток данных

### Мониторинг новостей

```
┌──────────────┐
│ news_monitor │ (Python script)
└──────┬───────┘
       │
       ├─1─> Сканирование источников
       │     ├─ Telegram каналы
       │     └─ Веб-сайты
       │     ↓
       │     news_posts (is_processed=false)
       │
       ├─2─> LLM обработка
       │     ├─ Извлечение заголовка
       │     ├─ Генерация summary
       │     └─ Классификация по категориям
       │     ↓
       │     news_posts (is_processed=true)
       │     news_post_categories
       │
       └─3─> Создание дайджеста
             ├─ Статистика сканирования
             ↓
             news_digests
             news_digest_posts (связь с постами)
             ↓
             PDF + Telegram уведомление
```

### Отображение в Web App

```
┌─────────────┐
│ ScansScreen │
└──────┬──────┘
       │
       ├─> getNewsDigests()
       │   ↓
       │   SELECT * FROM news_digests
       │   + подсчет каналов через news_digest_posts
       │   ↓
       │   Список дайджестов
       │
       └─> getNewsDigestDetails(digestId)
           ↓
           SELECT news_digest_posts WHERE digest_id
           + JOIN news_posts
           + JOIN news_post_categories
           ↓
           Список постов дайджеста
```

### Единая лента (FeedScreen)

```
┌────────────┐
│ FeedScreen │
└──────┬─────┘
       │
       └─> getUnifiedFeed(params)
           ↓
           ┌─ feedType='all' ──────────────────┐
           │  UNION                             │
           ├─ changes (конкуренты - web)       │
           ├─ competitor_tg_posts (конкуренты) │
           └─ news_posts (отраслевые новости)  │
           ↓
           Единый массив, сортировка по дате
```

---

## Безопасность

### Row Level Security (RLS)

Настроено в Supabase для таблиц:
- `users` - доступ только к своей записи
- Остальные таблицы - read для авторизованных

### Аутентификация

- Telegram Web App - передача `initData`
- Проверка через `checkUserAccess(telegramUser)`
- Роли: admin, editor, viewer

---

## Мониторинг и отладка

### Логирование

Python скрипты выводят подробные логи:
```
📊 Мониторинг новостей запущен
⏱️ Период: 28.01.2026 — 03.02.2026
📱 TG-каналов: 15 активных
✅ Сохранено 42 новых новостей
🤖 Обработано LLM: 38 из 42
📰 Постов в дайджесте: 35
```

### Отслеживание ошибок

- `scan_problems` - проблемы при сканировании
- `competitor_health` / `url_health` - отслеживание последовательных сбоев
- Telegram уведомления об ошибках

---

## Масштабирование

### Текущие ограничения

- LLM запросы: семафор на 5 одновременных
- Между запросами к веб-сайтам: пауза 2-3 сек
- Telegram API: стандартные лимиты

### Потенциальные улучшения

1. **Кэширование** - Redis для частых запросов
2. **Очередь задач** - Celery для фоновой обработки
3. **CDN** - для статики и PDF
4. **Партиционирование таблиц** - по датам для архива

---

## Разработка

### Локальный запуск

```bash
# Backend
cd /path/to/competitor-monitor
python3 news_monitor.py

# Frontend
cd webapp
npm install
npm run dev
```

### Переменные окружения

```bash
# Backend (.env)
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_KEY=xxx
TELEGRAM_BOT_TOKEN=xxx
TELEGRAM_CHAT_ID=xxx
GROQ_API_KEY=xxx

# Frontend (webapp/.env)
VITE_SUPABASE_URL=https://xxx.supabase.co
VITE_SUPABASE_ANON_KEY=xxx
```

### Деплой

- **Backend**: GitHub Actions (автоматический запуск)
- **Frontend**: Vercel / Netlify (для prod) или Telegram Web App (текущий)
- **База данных**: Supabase (managed PostgreSQL)

---

## Поддержка

См. также:
- [DATABASE_SCHEMA.md](./DATABASE_SCHEMA.md) - полная схема БД
- [README.md](../README.md) - общее описание проекта
