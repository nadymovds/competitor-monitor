-- Добавляем колонну is_meaningful в таблицу changes
-- Это позволяет отделить незначимые обновления (типа "нет значимых изменений")
-- от действительных обновлений контента

ALTER TABLE changes
ADD COLUMN is_meaningful BOOLEAN DEFAULT TRUE;

-- Создаем индекс для быстрых запросов с фильтром is_meaningful
CREATE INDEX idx_changes_is_meaningful ON changes(is_meaningful);

-- Комбинированный индекс для частых запросов по конкуренту и значимости
CREATE INDEX idx_changes_competitor_meaningful ON changes(competitor_id, is_meaningful, detected_at DESC);
