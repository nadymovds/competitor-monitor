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

**`monitor.py`** - Мониторинг конкурентов (режимы: `--mode websites` / `--mode telegram`)
- Сканирование веб-сайтов конкурентов (Playwright, async)
- Мониторинг Telegram-каналов конкурентов (Telethon)
- Определение изменений через LLM (Groq / llama-3.3-70b-versatile)
- Категоризация изменений (products/prices/services/news/technical)
- Генерация PDF-отчётов
- Отправка уведомлений в личные чаты и групповые чаты (`TELEGRAM_GROUP_CHAT_IDS`)

**`news_monitor.py`** - Мониторинг отраслевых новостей
- Сканирование новостных Telegram-каналов
- Парсинг новостных веб-сайтов
- Классификация новостей по категориям через LLM
- Дедупликация по content_hash
- Генерация новостных дайджестов
- Создание записей в `news_digests` для статистики
- Отправка PDF с инлайн-кнопкой «Показать посты»

**`mentions_monitor.py`** - Мониторинг упоминаний компании
- Поиск по Yandex Search API (асинхронный)
- Поиск по Google Custom Search API (опционально)
- Парсинг Telegram-каналов через Playwright
- Парсинг веб-порталов через Playwright (CSS-селекторы)
- Анализ тональности и генерация summary через Groq LLM
- Дедупликация по URL (`UNIQUE` constraint)
- Сохранение в `mention_scans` и `mentions`
- Запускается раз в неделю (понедельник, 09:00 МСК)

**`bot.py`** - Telegram Bot с async polling
- Обработка инлайн-кнопок (`CallbackQueryHandler`)
- По нажатию «Показать посты» — отправляет посты дайджеста порциями по 10
- Пагинация через callback_data: `show_posts:{digest_id}:{offset}`
- Работает в фоне параллельно с cron-скриптами (постоянный процесс)

#### Процесс мониторинга упоминаний

1. **Фаза 1: Поиск**
   - Yandex Search API: запрос по каждому термину из `mention_search_terms`
   - Telegram-каналы из `mention_sources` (type=telegram): Playwright
   - Веб-порталы из `mention_sources` (type=website): Playwright + CSS-селекторы

2. **Фаза 2: LLM-обработка**
   - Анализ тональности (positive / negative / neutral)
   - Генерация краткого summary
   - Дедупликация по URL (ON CONFLICT DO NOTHING)

3. **Фаза 3: Сохранение**
   - Создание записи `mention_scans` (status=running → completed/failed)
   - Запись результатов в `mentions`

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

#### CSS-селекторы для веб-парсинга

Для web-источников новостей система использует `css_config` в таблице `news_channels`:
```json
{
  "title_selector": "h1.post-title",
  "content_selector": ".post-content",
  "date_selector": ".post-date",
  "pagination_selector": "a.next-page"
}
```

#### Здоровье URL

Система отслеживает состояние каждого URL через `url_health`:
- Счётчик последовательных ошибок
- Время последнего успешного сканирования
- Тип последней ошибки (timeout, 404, etc.)

#### Зависимости

```
playwright - автоматизация браузера
telethon - Telegram API
supabase - клиент БД
openai / groq - LLM для анализа
reportlab - генерация PDF
beautifulsoup4 - парсинг HTML
aiohttp - асинхронные HTTP-запросы
python-dotenv - управление переменными окружения
python-telegram-bot>=20.0 - async bot с polling (bot.py)
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

#### Аутентификация

Система использует Telegram Web App для аутентификации:
1. Пользователь открывает Web App через Telegram Bot
2. Передаётся `initData` (JWT токен от Telegram)
3. Проверяется подпись и извлекается `user_id`
4. Создаётся/обновляется запись в таблице `users`
5. Проверяется роль пользователя (admin/editor/viewer)

См. `webapp/src/services/telegram.js` для деталей.

#### Управление ролями

| Роль | Права |
|------|-------|
| **admin** | Полный доступ. Управление конкурентами, каналами, категориями. |
| **editor** | Редактирование конкурентов и каналов. Просмотр статистики. |
| **viewer** | Только просмотр ленты и статистики. Нет редактирования. |

#### Технологии

```
React 18 - UI фреймворк
Vite - сборщик и dev-сервер
Supabase JS Client - работа с БД и RLS
Telegram Web App SDK - интеграция с Telegram
React Router - навигация между экранами
```

#### Структура

```
webapp/
├── src/
│   ├── components/
│   │   ├── screens/      # Экраны приложения
│   │   │   ├── FeedScreen.jsx        # Единая лента (конкуренты + новости)
│   │   │   ├── ScansScreen.jsx       # История сканирований (подстраница Settings)
│   │   │   ├── CompetitorsScreen.jsx # Список конкурентов
│   │   │   ├── MentionsScreen.jsx    # Упоминания компании
│   │   │   └── SettingsScreen.jsx    # Настройки (включает кнопку → ScansScreen)
│   │   └── ui/           # UI компоненты
│   │       ├── BottomNav.jsx         # 4 вкладки: feed/competitors/mentions/settings
│   │       ├── FeedTypeToggle.jsx    # Переключатель Все/Конкуренты/Новости
│   │       ├── MultiSelect.jsx       # Dropdown с множественным выбором
│   │       ├── NewsCard.jsx
│   │       ├── MentionCard.jsx       # Карточка упоминания
│   │       ├── ScanCard.jsx          # Карточка сканирования (collapse/expand)
│   │       ├── NextScanInfo.jsx      # Дата следующего сканирования
│   │       ├── NewsFilters.jsx       # Фильтры новостей
│   │       └── ...
│   ├── services/
│   │   ├── supabase.js   # Клиент Supabase + CRUD
│   │   ├── mentions.js   # API упоминаний
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
- Infinite scroll (10 элементов за раз)
- Период: последние 30 дней (до 8 недель назад)

**ScansScreen** - История сканирований
- Переключатель: Конкуренты / Новости
- Для конкурентов: данные из `summary_reports`
- Для новостей: данные из `news_digests`
- Разворачиваемые карточки с деталями

**CompetitorsScreen** - Управление конкурентами
- Список конкурентов с группировкой
- Детальная страница конкурента
- История изменений

**MentionsScreen** - Упоминания компании
- Список упоминаний из `mentions`
- Фильтры: источник (Яндекс / TG / Портал), тональность, период
- Infinite scroll (pagination по 10)

**SettingsScreen** - Настройки и управление
- Управление категориями новостей
- Управление каналами новостей (включая редактирование тегов `tags` для фильтрации по странам)
- Группы конкурентов
- Поиск упоминаний: CRUD для `mention_search_terms` (только admin)
- Источники упоминаний: CRUD для `mention_sources` (только admin)
- Кнопка «История сканирований» → открывает ScansScreen как подстраницу

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

Бот для управления системой, запуска сканирований и отправки отчетов.

#### Функции

- **Запуск сканирования** по требованию (создание записи в `scan_requests`)
- **Управление расписанием** (сохранение в `bot_settings`)
- **Отправка отчетов** - PDF-файлы с инлайн-кнопкой «Показать посты»
- **Просмотр постов дайджеста** прямо в чате — порциями по 10
- **Просмотр статистики** через Web App inline-кнопок
- **Управление ролями** - назначение прав доступа пользователям

#### Файлы

- **`bot.py`** — Flask webhook-сервер, задеплоен на Render.com (обрабатывает инлайн-кнопки)
- **`monitor.py`** / **`news_monitor.py`** / **`mentions_monitor.py`** — cron-скрипты, запускаются по расписанию в GitHub Actions
- **`resend_digest_to_groups.py`** — утилита для переотправки последнего дайджеста в групповые чаты (без инлайн-кнопок, со ссылкой на бот); запускается вручную через workflow_dispatch

#### Интеграция

- Bot API для команд и сообщений
- Web App Telegram (UI через `webapp/`)
- Supabase для загрузки постов дайджеста (`news_digest_posts` → `news_posts`)
- Запись в `bot_settings` для управления интервалами
- Запись в `scan_requests` для запросов на сканирование

#### Команды

```
/start - Инициализация пользователя
/scan - Запустить сканирование конкурентов
/news - Запустить сканирование новостей
/status - Статус текущего сканирования
/settings - Управление расписанием
/users - Управление ролями (admin)
```

#### Инлайн-кнопки (CallbackQuery)

| callback_data | Действие |
|---|---|
| `show_posts:{digest_id}:0` | Показать первые 10 постов дайджеста |
| `show_posts:{digest_id}:{offset}` | Показать следующую порцию постов |

### 5. Автоматизация (GitHub Actions)

#### Расписание

Система поддерживает два режима запуска:

**1. По расписанию (автоматический):**
```yaml
# monitor.py --mode websites — каждый четверг 18:00 МСК
schedule:
  - cron: '0 15 * * 4'  # UTC

# monitor.py --mode telegram — ежедневно 09:00 МСК
schedule:
  - cron: '0 6 * * *'  # UTC

# news_monitor.py — каждую пятницу 9:00 МСК (RU)
schedule:
  - cron: '0 6 * * 5'  # UTC

# news_monitor.py --tags kz — каждую пятницу 9:30 МСК (KZ)
schedule:
  - cron: '30 6 * * 5'  # UTC

# mentions_monitor.py — каждый понедельник 9:00 МСК
schedule:
  - cron: '0 6 * * 1'  # UTC
```

**2. Ручной запуск:**
```yaml
# resend_digest_to_groups.py — workflow_dispatch (по требованию)
# Переотправляет последний дайджест в групповые чаты
```

**3. По требованию (через Telegram Bot):**
- Пользователь отправляет `/scan` или `/news`
- Bot создаёт запись в `scan_requests`
- GitHub Actions webhook срабатывает на новую запись
- После выполнения обновляется `status` (pending → running → completed/failed)

#### Процесс

1. Checkout кода
2. Установка зависимостей (Python + Playwright)
3. Запуск Python скрипта (`monitor.py` или `news_monitor.py`)
4. Сохранение результатов в Supabase:
   - Новые записи в таблицы `changes`, `scan_results`, `news_posts`
   - Создание `summary_reports` и `news_digests`
5. Генерация PDF-отчетов
6. Отправка уведомлений в Telegram
7. Обновление `scan_requests.status`

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
# Backend — cron-скрипты (запускать вручную или по расписанию)
cd /path/to/competitor-monitor
python3 news_monitor.py
python3 competitor_monitor.py

# Telegram Bot — постоянный процесс (запускать отдельно)
python3 bot.py

# Frontend
cd webapp
npm install
npm run dev
```

### Деплой bot.py на Render.com

`bot.py` работает как **webhook-сервер** (Flask), задеплоенный на Render.com free tier.
Polling не используется — Telegram сам шлёт POST-запросы на `/webhook` при каждом нажатии кнопки.

**Почему не polling:** cron-скрипты запускаются в GitHub Actions (эфемерные контейнеры). Polling требует постоянно работающего процесса, который там недоступен. Webhook решает проблему без выделенного сервера.

**Шаги деплоя на Render.com:**

1. Создать новый **Web Service** из GitHub репо
2. Build Command: `pip install -r requirements.txt`
3. Start Command: `python bot.py` (или автоматически из `Procfile`)
4. Добавить Environment Variables:
   ```
   SUPABASE_URL=https://xxx.supabase.co
   SUPABASE_KEY=xxx
   TELEGRAM_BOT_TOKEN=xxx
   WEBHOOK_URL=https://your-app.onrender.com
   ```
5. После деплоя бот автоматически устанавливает webhook через `setWebhook` API

**Endpoint'ы:**
- `POST /webhook` — получает updates от Telegram
- `GET /` — health check

### Переменные окружения

```bash
# Backend — GitHub Actions secrets
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_KEY=xxx
TELEGRAM_BOT_TOKEN=xxx
TELEGRAM_CHAT_ID=xxx                         # личный чат для уведомлений
TELEGRAM_GROUP_CHAT_IDS=id1,id2              # групповые чаты (через запятую)
GROQ_API_KEY=xxx

# mentions_monitor.py — дополнительно
YANDEX_SEARCH_API_KEY=xxx
YANDEX_SEARCH_FOLDER_ID=xxx
GOOGLE_CSE_API_KEY=xxx                       # опционально
GOOGLE_CSE_ID=xxx                            # опционально

# news_monitor.py — опционально
NEWS_PERIOD_DAYS=7                           # период сбора новостей

# bot.py — Render.com Environment Variables
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_KEY=xxx
TELEGRAM_BOT_TOKEN=xxx
WEBHOOK_URL=https://your-app.onrender.com    # URL выданный Render

# Frontend (webapp/.env)
VITE_SUPABASE_URL=https://xxx.supabase.co
VITE_SUPABASE_ANON_KEY=xxx
```

### Деплой

- **Cron-скрипты** (`monitor.py`, `news_monitor.py`, `mentions_monitor.py`): GitHub Actions (эфемерные контейнеры)
- **Telegram Bot** (`bot.py`): Render.com free tier (webhook-сервер, постоянно доступен)
- **Frontend** (`webapp/`): GitHub Pages (автодеплой при push в `webapp/**`)
- **База данных**: Supabase (managed PostgreSQL)

---

## Управление пользователями

### Таблица users

Каждый пользователь, зашедший в Web App, создаёт или обновляет запись в `users`:

```sql
create table public.users (
  id uuid primary key default gen_random_uuid(),
  telegram_id bigint unique not null,
  telegram_username text,
  display_name text,
  role text default 'viewer' check (role in ('admin', 'editor', 'viewer')),
  is_active boolean default true,
  created_at timestamptz default now(),
  last_seen_at timestamptz
);
```

### RLS Политики

Все таблицы защищены RLS политиками:
- Авторизованные пользователи могут читать основные таблицы
- Редактирование доступно только для admin/editor
- Отслеживание `last_seen_at` при каждом запросе

---

## Мониторинг здоровья системы

### Отслеживание ошибок

Для каждого конкурента и URL система отслеживает:
- `consecutive_failures` - счетчик подряд идущих ошибок
- `last_success_at` - время последнего успешного сканирования
- `last_error_type` - тип последней ошибки (timeout, connection_error, parse_error, etc.)

Это позволяет:
1. **Пропускать проблемные URL** временно
2. **Отправлять алерты** при достижении порога ошибок
3. **Анализировать тренды** в логах сканирования

---

## Поддержка

См. также:
- [DATABASE_SCHEMA.md](./DATABASE_SCHEMA.md) - полная схема БД
- [README.md](../README.md) - общее описание проекта
