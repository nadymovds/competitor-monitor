# Инструкция по развертыванию исправления #05

## Что было исправлено

Система теперь правильно обрабатывает ситуации, когда при сканировании сайта конкурента обнаруживаются "нет значимых изменений". Такие обновления:
- Сохраняются в БД с флагом `is_meaningful = false` (для аудита)
- НЕ отображаются в UI (фильтруются на frontend)
- НЕ учитываются в счетчиках источников

## Шаги развертывания

### 1. Применить миграцию БД в Supabase

1. Откройте Supabase Dashboard
2. Перейдите в SQL Editor
3. Запустите миграцию из файла `migrations/add_is_meaningful_to_changes.sql`:

```sql
ALTER TABLE changes
ADD COLUMN is_meaningful BOOLEAN DEFAULT TRUE;

CREATE INDEX idx_changes_is_meaningful ON changes(is_meaningful);
CREATE INDEX idx_changes_competitor_meaningful ON changes(competitor_id, is_meaningful, detected_at DESC);
```

### 2. Развернуть Backend

1. Загрузить обновленный `monitor.py` на сервер
2. Перезапустить скрипт мониторинга

### 3. Развернуть Frontend

```bash
cd /Users/Denis/Documents/competitor-monitor/webapp
npm install  # если есть новые зависимости
npm run build
# или npm run dev для локальной разработки
```

### 4. Проверить изменения в коде

Измененные файлы:
- `monitor.py` - функции save_change(), save_change_for_url() и логика сканирования
- `webapp/src/services/supabase.js` - getCompetitorWithHistory()
- `webapp/src/services/feed.js` - getCompetitorWebsiteChanges()
- `docs/DATABASE_SCHEMA.md` - документация схемы
- `migrations/add_is_meaningful_to_changes.sql` - новая миграция

## Проверка работы

### 1. В Supabase SQL Editor
```sql
-- Проверить что колонна добавлена
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'changes' AND column_name = 'is_meaningful';

-- Должно вернуть одну строку с is_meaningful: boolean
```

### 2. На Frontend
1. Открыть экран "Конкуренты"
2. Выбрать конкурента
3. В истории изменений должны отображаться только значимые обновления
4. Карточки с "Нет значимых изменений" должны быть скрыты

### 3. В ленте обновлений ("Все")
- Сканирование без изменений не должно добавлять карточки
- Счетчики источников (Web, TG) должны считать корректно

## Откат (если что-то пошло не так)

### Откатить миграцию БД
```sql
DROP INDEX IF EXISTS idx_changes_competitor_meaningful;
DROP INDEX IF EXISTS idx_changes_is_meaningful;

ALTER TABLE changes
DROP COLUMN IF EXISTS is_meaningful;
```

### Откатить код
Вернуть предыдущие версии файлов из git:
```bash
git checkout HEAD~1 -- monitor.py webapp/src/services/supabase.js webapp/src/services/feed.js
```

## Примечания

- Все существующие записи в таблице `changes` получат значение `is_meaningful = TRUE` (по умолчанию)
- Это НЕ изменит поведение существующих данных - они будут отображаться как раньше
- Новые сканирования будут правильно помечать незначимые изменения

## Вопросы и поддержка

Если возникли проблемы при развертывании, проверьте:
1. Что миграция БД успешно применена (нет ошибок в Supabase)
2. Что файлы исправления загружены на сервер
3. Что frontend пересобран и кэш браузера очищен (Ctrl+Shift+Delete)
