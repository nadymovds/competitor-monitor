-- Таблица игнорируемых источников для мониторинга упоминаний
CREATE TABLE IF NOT EXISTS mention_ignored_sources (
  id          SERIAL PRIMARY KEY,
  pattern     TEXT NOT NULL UNIQUE,
  description TEXT,
  created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Включаем RLS
ALTER TABLE mention_ignored_sources ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow read for authenticated" ON mention_ignored_sources
  FOR SELECT TO authenticated USING (true);

CREATE POLICY "Allow all for service_role" ON mention_ignored_sources
  FOR ALL TO service_role USING (true);

-- Предустановленные игнорируемые источники
INSERT INTO mention_ignored_sources (pattern, description) VALUES
  ('skai.online',      'Наш основной сайт'),
  ('skai.kz',          'Наш сайт KZ'),
  ('t.me/skai_online', 'Наш TG-канал'),
  ('scout-corp.com',   'Scout Corp')
ON CONFLICT (pattern) DO NOTHING;
