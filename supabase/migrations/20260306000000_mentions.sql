-- Мониторинг упоминаний компании
-- Задача 1: схема таблиц

-- =============================================
-- 1. mention_search_terms
-- Варианты названий компании для поиска
-- =============================================
CREATE TABLE IF NOT EXISTS public.mention_search_terms (
    id          serial PRIMARY KEY,
    term        varchar(255) NOT NULL,
    description text,
    is_active   boolean NOT NULL DEFAULT true,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now()
);

-- =============================================
-- 2. mention_sources
-- ТГ-каналы и веб-порталы для мониторинга
-- Аналог news_channels
-- =============================================
CREATE TABLE IF NOT EXISTS public.mention_sources (
    id              serial PRIMARY KEY,
    source_type     text        NOT NULL CHECK (source_type IN ('telegram', 'website')),
    username        varchar(255),           -- username канала (для telegram)
    title           varchar(255) NOT NULL,
    description     text,
    url             text,                   -- URL для website
    css_config      jsonb,                  -- CSS-селекторы для парсинга (аналог news_channels)
    is_active       boolean      NOT NULL DEFAULT true,
    last_scan_at    timestamptz,
    created_at      timestamptz  NOT NULL DEFAULT now(),
    updated_at      timestamptz  NOT NULL DEFAULT now()
);

-- =============================================
-- 3. mention_scans
-- История запусков скрипта
-- Аналог summary_reports
-- =============================================
CREATE TABLE IF NOT EXISTS public.mention_scans (
    id              serial PRIMARY KEY,
    scan_date       date         NOT NULL DEFAULT CURRENT_DATE,
    status          text         NOT NULL DEFAULT 'running' CHECK (status IN ('running', 'completed', 'failed')),
    mentions_found  integer      NOT NULL DEFAULT 0,   -- новых упоминаний за скан
    duration_seconds integer,
    error_message   text,
    created_at      timestamptz  NOT NULL DEFAULT now(),
    completed_at    timestamptz
);

-- =============================================
-- 4. mentions
-- Найденные упоминания; UNIQUE по url
-- =============================================
CREATE TABLE IF NOT EXISTS public.mentions (
    id              serial PRIMARY KEY,
    scan_id         integer      REFERENCES public.mention_scans(id) ON DELETE SET NULL,
    source_type     text         NOT NULL CHECK (source_type IN ('yandex', 'telegram', 'website')),
    url             text         NOT NULL,
    title           text,
    content_snippet text,
    post_date       timestamptz,
    sentiment       text         CHECK (sentiment IN ('positive', 'negative', 'neutral')),
    summary         text,
    search_term     varchar(255),           -- какой термин нашёл это упоминание
    source_name     text,                   -- название источника (канала / сайта)
    is_processed    boolean      NOT NULL DEFAULT false,
    created_at      timestamptz  NOT NULL DEFAULT now(),

    CONSTRAINT mentions_url_unique UNIQUE (url)
);

-- =============================================
-- Индексы
-- =============================================
CREATE INDEX IF NOT EXISTS idx_mentions_scan_id       ON public.mentions (scan_id);
CREATE INDEX IF NOT EXISTS idx_mentions_source_type   ON public.mentions (source_type);
CREATE INDEX IF NOT EXISTS idx_mentions_sentiment     ON public.mentions (sentiment);
CREATE INDEX IF NOT EXISTS idx_mentions_post_date     ON public.mentions (post_date DESC);
CREATE INDEX IF NOT EXISTS idx_mentions_is_processed  ON public.mentions (is_processed) WHERE is_processed = false;
CREATE INDEX IF NOT EXISTS idx_mention_sources_active ON public.mention_sources (is_active) WHERE is_active = true;

-- =============================================
-- Начальные данные: варианты названий компании
-- Замените на реальные названия вашей компании
-- =============================================
INSERT INTO public.mention_search_terms (term, description) VALUES
    ('SKAI',    'Основное название бренда'),
    ('SKAI.Видеоаналитика',      'Название продукта'),
    ('SKAI Платформа',      'Название продукта'),
    ('ООО "СМА-РТ"', 'Юридическое название')
ON CONFLICT DO NOTHING;
