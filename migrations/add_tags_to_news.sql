-- Добавление тегов к источникам новостей и дайджестам
-- Теги позволяют группировать источники по разрезам (страна, тематика и т.д.)
-- и генерировать отдельные PDF-отчёты для каждого тега

-- Массив тегов на каждом канале (один канал может иметь несколько тегов)
ALTER TABLE news_channels
ADD COLUMN IF NOT EXISTS tags TEXT[] NOT NULL DEFAULT '{}';

-- Тег дайджеста: NULL = глобальный запуск (все источники), иначе — конкретный тег
ALTER TABLE news_digests
ADD COLUMN IF NOT EXISTS tag TEXT DEFAULT NULL;

-- Индекс для быстрой фильтрации дайджестов по тегу
CREATE INDEX IF NOT EXISTS idx_news_digests_tag ON news_digests (tag);
