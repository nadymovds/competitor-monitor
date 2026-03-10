-- Добавляем тип совпадения к поисковым терминам
-- 'partial' (по умолчанию) — достаточно первого слова термина в тексте
-- 'full'                    — весь термин должен присутствовать в тексте

ALTER TABLE mention_search_terms
ADD COLUMN IF NOT EXISTS match_type TEXT NOT NULL DEFAULT 'partial'
CHECK (match_type IN ('full', 'partial'));
