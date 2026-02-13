# Структура базы данных

Полная схема PostgreSQL базы данных системы мониторинга конкурентов и новостей.

## Основные таблицы

### Конкуренты

#### `competitors`
Основная таблица конкурентов.

| Поле | Тип | Описание |
|------|-----|----------|
| id | uuid | PK, первичный ключ |
| name | varchar | Название конкурента |
| url | text | Основной URL |
| comment | jsonb | Комментарии (массив) |
| last_scan_id | uuid | FK → scan_results.id |
| created_at | timestamptz | Дата создания |
| updated_at | timestamptz | Дата обновления |
| description | text | Описание |
| is_active | boolean | Активен ли конкурент |

#### `competitor_urls`
URL-адреса конкурентов для мониторинга.

| Поле | Тип | Описание |
|------|-----|----------|
| id | uuid | PK |
| competitor_id | uuid | FK → competitors.id |
| url | text | URL для мониторинга |
| label | text | Метка/название |
| is_active | boolean | Активен ли URL |
| sort_order | integer | Порядок сортировки |
| created_at | timestamptz | Дата создания |
| source_type | text | 'website' или 'telegram' |
| last_message_id | integer | ID последнего сообщения (для TG) |

#### `competitor_content`
Кэш контента конкурентов.

| Поле | Тип | Описание |
|------|-----|----------|
| competitor_id | uuid | PK, FK → competitors.id |
| content_text | text | Текст контента |
| content_hash | text | Хэш контента |
| updated_at | timestamptz | Дата обновления |

#### `url_content`
Кэш контента по URL.

| Поле | Тип | Описание |
|------|-----|----------|
| url_id | uuid | PK, FK → competitor_urls.id |
| content_text | text | Текст контента |
| content_hash | text | Хэш контента |
| updated_at | timestamptz | Дата обновления |

### Сканирование и изменения

#### `summary_reports`
Сводные отчеты по сканированию.

| Поле | Тип | Описание |
|------|-----|----------|
| id | uuid | PK |
| report_id | varchar | Уникальный ID отчета |
| report_date | date | Дата отчета |
| overall_llm_report | text | Общий отчет от LLM |
| created_at | timestamptz | Дата создания |
| total_sites | integer | Всего сайтов |
| successful_sites | integer | Успешно просканировано |
| changes_count | integer | Количество изменений |
| problems_count | integer | Количество проблем |
| duration_seconds | integer | Длительность в секундах |
| pdf_url | text | URL PDF-отчета |

#### `scan_results`
Результаты сканирования.

| Поле | Тип | Описание |
|------|-----|----------|
| id | uuid | PK |
| scan_id | varchar | Уникальный ID сканирования |
| scan_date | date | Дата сканирования |
| competitor_id | uuid | FK → competitors.id |
| last_hash | varchar | Последний хэш контента |
| content_changed | boolean | Был ли изменен контент |
| raw_change_data | text | Сырые данные изменений |
| llm_summary | text | Краткое описание от LLM |
| report_id | uuid | FK → summary_reports.id |
| created_at | timestamptz | Дата создания |
| change_type | text | Тип изменения |
| tags | text[] | Теги |
| url_id | uuid | FK → competitor_urls.id |
| scanned_url | text | Просканированный URL |

#### `changes`
Обнаруженные изменения конкурентов.

| Поле | Тип | Описание |
|------|-----|----------|
| id | uuid | PK |
| competitor_id | uuid | FK → competitors.id |
| detected_at | timestamptz | Время обнаружения |
| category | text | Категория (products/prices/services/news) |
| summary | text | Описание изменения (от LLM) |
| tags | text[] | Теги (массив) |
| content_hash | text | Хэш измененного контента |
| report_id | uuid | FK → summary_reports.id |
| url_id | uuid | FK → competitor_urls.id (какой URL изменился) |
| scanned_url | text | Просканированный URL |
| is_meaningful | boolean | Значимое ли изменение (true по умолчанию, может фильтроваться) |

#### `competitor_tg_posts`
Посты конкурентов из Telegram.

| Поле | Тип | Описание |
|------|-----|----------|
| id | serial | PK |
| competitor_id | uuid | FK → competitors.id |
| url_id | uuid | FK → competitor_urls.id |
| channel_username | text | Username канала |
| message_id | integer | ID сообщения |
| post_url | text | URL поста |
| content_text | text | Текст поста |
| title | text | Заголовок |
| summary | text | Краткое описание |
| category | text | Категория (products/prices/news/technical) |
| tags | text[] | Теги |
| post_date | timestamptz | Дата публикации |
| has_photo | boolean | Есть фото |
| has_video | boolean | Есть видео |
| has_document | boolean | Есть документ |
| views_count | integer | Количество просмотров |
| content_hash | text | Хэш контента |
| is_processed | boolean | Обработан ли LLM |
| report_id | text | ID отчета |
| detected_at | timestamptz | Время обнаружения |
| created_at | timestamptz | Дата создания |

#### `scan_problems`
Проблемы при сканировании.

| Поле | Тип | Описание |
|------|-----|----------|
| id | uuid | PK |
| report_id | uuid | FK → summary_reports.id |
| competitor_id | uuid | FK → competitors.id |
| competitor_url | text | URL конкурента |
| problem_type | text | Тип проблемы |
| error_message | text | Сообщение об ошибке |
| created_at | timestamptz | Дата создания |
| url_id | uuid | FK → competitor_urls.id |
| scanned_url | text | Просканированный URL |

### Мониторинг здоровья

#### `competitor_health`
Здоровье конкурентов (отслеживание последовательных ошибок).

| Поле | Тип | Описание |
|------|-----|----------|
| competitor_id | uuid | PK, FK → competitors.id |
| consecutive_failures | integer | Счётчик последовательных ошибок при сканировании |
| last_success_at | timestamp | Дата/время последнего успешного сканирования |
| last_error_type | text | Тип последней ошибки (timeout, connection_error, etc.) |

#### `url_health`
Здоровье отдельных URL (отслеживание ошибок).

| Поле | Тип | Описание |
|------|-----|----------|
| url_id | uuid | PK, FK → competitor_urls.id |
| consecutive_failures | integer | Счётчик последовательных ошибок |
| last_success_at | timestamp | Дата/время последнего успешного сканирования |
| last_error_type | text | Тип последней ошибки |

### Группировка

#### `groups`
Группы для организации конкурентов.

| Поле | Тип | Описание |
|------|-----|----------|
| id | uuid | PK |
| name | text | Название группы |
| color | text | Цвет группы (hex) |
| description | text | Описание |
| sort_order | integer | Порядок сортировки |
| created_at | timestamptz | Дата создания |

#### `competitor_groups`
Связь конкурентов с группами (many-to-many).

| Поле | Тип | Описание |
|------|-----|----------|
| competitor_id | uuid | PK, FK → competitors.id |
| group_id | uuid | PK, FK → groups.id |
| created_at | timestamptz | Дата создания |

---

## Новостной мониторинг

### `news_channels`
Каналы и источники новостей (Telegram каналы и веб-сайты).

| Поле | Тип | Описание |
|------|-----|----------|
| id | serial | PK |
| username | varchar | Username канала (уникальный) или домен сайта |
| title | varchar | Название канала/сайта |
| description | text | Описание |
| is_active | boolean | Активен ли источник для сканирования |
| competitor_id | uuid | FK → competitors.id (опционально, если это источник конкурента) |
| last_message_id | bigint | ID последнего сообщения (для Telegram) |
| last_scan_at | timestamptz | Время последнего сканирования |
| created_at | timestamptz | Дата создания |
| updated_at | timestamptz | Дата обновления |
| source_type | text | 'telegram' или 'website' |
| url | text | URL (для website, например https://site.com/news) |
| css_config | jsonb | Конфигурация CSS-селекторов для парсинга (title, content, date, pagination) |

### `news_categories`
Категории новостей.

| Поле | Тип | Описание |
|------|-----|----------|
| id | serial | PK |
| name | varchar | Название категории (уникальное) |
| description | text | Описание |
| color | varchar | Цвет категории (hex) |
| is_visible | boolean | Видима ли категория |
| sort_order | integer | Порядок сортировки |
| created_at | timestamptz | Дата создания |
| updated_at | timestamptz | Дата обновления |

### `news_posts`
Новостные посты.

| Поле | Тип | Описание |
|------|-----|----------|
| id | serial | PK |
| channel_id | integer | FK → news_channels.id |
| message_id | bigint | ID сообщения |
| post_url | text | URL поста |
| title | varchar | Заголовок |
| content_text | text | Текст контента |
| summary | text | Краткое описание |
| post_date | timestamptz | Дата публикации |
| has_photo | boolean | Есть фото |
| has_video | boolean | Есть видео |
| has_document | boolean | Есть документ |
| views_count | integer | Количество просмотров |
| content_hash | varchar | Хэш контента |
| is_processed | boolean | Обработан ли LLM |
| created_at | timestamptz | Дата создания |
| source_type | text | 'telegram' или 'website' |
| article_url | text | URL статьи (для website) |

### `news_post_categories`
Связь постов с категориями (many-to-many).

| Поле | Тип | Описание |
|------|-----|----------|
| id | serial | PK |
| post_id | integer | FK → news_posts.id |
| category_id | integer | FK → news_categories.id |
| confidence | double precision | Уверенность классификации (0-1) |
| is_manual | boolean | Назначена ли категория вручную |
| created_at | timestamptz | Дата создания |

### `news_digests`
Дайджесты новостей (статистика сканирований).

| Поле | Тип | Описание |
|------|-----|----------|
| id | serial | PK |
| digest_date | date | Дата дайджеста |
| period_start | date | Начало периода |
| period_end | date | Конец периода |
| posts_count | integer | Количество постов в дайджесте |
| categories_summary | jsonb | Сводка по категориям |
| pdf_url | text | URL PDF-файла |
| telegram_message_id | bigint | ID сообщения в Telegram |
| created_at | timestamptz | Дата создания |

### `news_digest_posts`
Связь дайджестов с постами (many-to-many).

| Поле | Тип | Описание |
|------|-----|----------|
| digest_id | integer | PK, FK → news_digests.id |
| post_id | integer | PK, FK → news_posts.id |
| rank_in_category | integer | Ранг в категории |

---

## Пользователи и управление доступом

### `users`
Пользователи системы с поддержкой ролей.

| Поле | Тип | Описание |
|------|-----|----------|
| id | uuid | PK |
| telegram_id | bigint | Telegram ID (уникальный) для идентификации |
| telegram_username | text | Username в Telegram (@username) |
| display_name | text | Отображаемое имя пользователя |
| role | text | Роль: admin (полный доступ), editor (редактирование), viewer (только чтение) |
| is_active | boolean | Активен ли пользователь (можно заблокировать) |
| created_at | timestamptz | Дата первого входа |
| last_seen_at | timestamptz | Время последней активности в приложении |

**Примечание:** Запись создаётся автоматически при первом входе через Telegram Web App.

---

## Telegram Bot

### `bot_settings`
Настройки Telegram Bot для управления расписанием.

| Поле | Тип | Описание |
|------|-----|----------|
| id | serial | PK |
| chat_id | bigint | ID чата (уникальный) - в каком чате управлять ботом |
| schedule_hours | integer | Интервал между автоматическими сканированиями (в часах) |
| is_active | boolean | Активны ли автоматические сканирования |
| created_at | timestamp | Дата создания записи |

### `scan_requests`
История запросов на сканирование (для отслеживания по требованию запусков).

| Поле | Тип | Описание |
|------|-----|----------|
| id | serial | PK |
| chat_id | bigint | ID чата, откуда был сделан запрос |
| github_run_id | bigint | ID запуска GitHub Actions workflow |
| status | text | Статус: pending → running → completed/failed |
| requested_at | timestamp | Время запроса пользователем |

---

## Связи между таблицами

### Мониторинг конкурентов
```
competitors (1) ──< competitor_urls (N)
competitors (1) ──< competitor_groups (N) ──> groups (1)
competitors (1) ──< changes (N)
competitors (1) ──< competitor_tg_posts (N)
competitors (1) ──< scan_results (N)
competitors (1) ──o competitor_content (0..1)
competitors (1) ──o competitor_health (0..1)

summary_reports (1) ──< scan_results (N)
summary_reports (1) ──< changes (N)
summary_reports (1) ──< scan_problems (N)

competitor_urls (1) ──< changes (N)
competitor_urls (1) ──< competitor_tg_posts (N)
competitor_urls (1) ──< scan_results (N)
competitor_urls (1) ──o url_content (0..1)
competitor_urls (1) ──o url_health (0..1)
```

### Новостной мониторинг
```
news_channels (1) ──< news_posts (N)
news_categories (1) ──< news_post_categories (N)
news_posts (1) ──< news_post_categories (N)
news_posts (1) ──< news_digest_posts (N)

news_digests (1) ──< news_digest_posts (N)

competitors (1) ──< news_channels (N)  [опционально]
```

---

## Индексы

Основные индексы для оптимизации производительности:

- `competitors.url` - поиск по URL
- `competitor_urls.competitor_id` - фильтрация по конкуренту
- `changes.competitor_id` - фильтрация по конкуренту
- `changes.report_id` - фильтрация по отчету
- `news_posts.channel_id` - фильтрация по каналу
- `news_posts.is_processed` - фильтрация необработанных
- `news_post_categories.post_id` - связь постов с категориями
- `news_digest_posts.digest_id` - связь дайджестов с постами
- `users.telegram_id` - авторизация по Telegram

---

## Ключевые принципы проектирования

### Типы первичных ключей

1. **UUID** - для основных сущностей (конкуренты, изменения, новости)
   - Позволяет безопасно репликировать и менять глобальные ID
   - Примеры: `competitors`, `changes`, `scan_results`, `users`, `groups`

2. **Serial/INT** - для служебных таблиц (новостные посты, категории, дайджесты)
   - Меньший размер в памяти
   - Подходит для быстроразвёртывающихся последовательностей
   - Примеры: `news_posts`, `news_categories`, `news_digests`

### Дедупликация

- **content_hash** (SHA256 или MD5) используется для:
  - Поиска дубликатов контента (`news_posts.content_hash`, `competitor_tg_posts.content_hash`)
  - Фильтрации ранее виденного контента
  - Откладывания обновления только при изменении хеша

### Мягкое удаление

Вместо удаления используются флаги `is_active`:
- Позволяет восстанавливать данные
- Сохраняет историю и связи
- Пример: `competitors.is_active`, `competitor_urls.is_active`, `news_channels.is_active`

### Временные метки

- **created_at** (timestamptz) - дата создания (никогда не меняется)
- **updated_at** (timestamptz) - дата последнего обновления
- **last_scan_at** - для источников новостей
- **last_seen_at** - для отслеживания активности пользователей

### Гибкие структуры (JSONB)

- **comment** в `competitors` - массив комментариев
- **css_config** в `news_channels` - конфигурация парсинга
- **categories_summary** в `news_digests` - статистика по категориям

Это позволяет не пересоздавать таблицы при изменении структуры данных.

### Foreign Keys и целостность

Все связи между таблицами защищены через `CONSTRAINT` с `FOREIGN KEY`:
```sql
CONSTRAINT changes_competitor_id_fkey FOREIGN KEY (competitor_id) REFERENCES public.competitors(id)
```

Это обеспечивает:
- Невозможность создать изменение без конкурента
- Автоматическое каскадное удаление (если настроено)
- Контроль данных на уровне БД
