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
- Отправка PDF с инлайн-кнопкой «Показать посты»

**`bot.py`** - Telegram Bot с async polling
- Обработка инлайн-кнопок (`CallbackQueryHandler`)
- По нажатию «Показать посты» — отправляет посты дайджеста порциями по 10
- Пагинация через callback_data: `show_posts:{digest_id}:{offset}`
- Работает в фоне параллельно с cron-скриптами (постоянный процесс)

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

Бот для управления системой, запуска сканирований и отправки отчетов.

#### Функции

- **Запуск сканирования** по требованию (создание записи в `scan_requests`)
- **Управление расписанием** (сохранение в `bot_settings`)
- **Отправка отчетов** - PDF-файлы с инлайн-кнопкой «Показать посты»
- **Просмотр постов дайджеста** прямо в чате — порциями по 10
- **Просмотр статистики** через Web App inline-кнопок
- **Управление ролями** - назначение прав доступа пользователям

#### Файлы

- **`bot.py`** — постоянно работающий процесс с async polling, обрабатывает инлайн-кнопки
- **`news_monitor.py`** / **`competitor_monitor.py`** — cron-скрипты, запускаются по расписанию

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
# Мониторинг конкурентов - каждый четверг 18:00 МСК
schedule:
  - cron: '0 15 * * 4'  # UTC

# Мониторинг новостей - каждую пятницу 9:00 МСК
schedule:
  - cron: '0 6 * * 5'  # UTC
```

**2. По требованию (через Telegram Bot):**
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

### Запуск bot.py в фоне

**Через nohup (простой вариант):**
```bash
nohup python3 bot.py >> logs/bot.log 2>&1 &
```

**Через systemd (рекомендуется для сервера):**
```ini
# /etc/systemd/system/competitor-bot.service
[Unit]
Description=Competitor Monitor Telegram Bot
After=network.target

[Service]
WorkingDirectory=/path/to/competitor-monitor
ExecStart=/usr/bin/python3 bot.py
Restart=always
EnvironmentFile=/path/to/competitor-monitor/.env

[Install]
WantedBy=multi-user.target
```
```bash
systemctl enable competitor-bot
systemctl start competitor-bot
```

**Через supervisor:**
```ini
# /etc/supervisor/conf.d/competitor-bot.conf
[program:competitor-bot]
directory=/path/to/competitor-monitor
command=python3 bot.py
autostart=true
autorestart=true
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
