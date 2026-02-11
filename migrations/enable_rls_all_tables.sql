-- Migration: Enable RLS on all public tables
-- Date: 2026-02-11
-- Purpose: Fix security warnings - enable Row Level Security with appropriate policies

-- ============================================================================
-- 1. NEWS TABLES
-- ============================================================================

-- news_channels
ALTER TABLE public.news_channels ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow all users to read news_channels" ON public.news_channels
  FOR SELECT USING (true);

CREATE POLICY "Allow admins to manage news_channels" ON public.news_channels
  FOR INSERT WITH CHECK (
    (auth.jwt() ->> 'user_metadata'::text)::jsonb ->> 'user_role' = 'admin'
  );

CREATE POLICY "Allow admins to update news_channels" ON public.news_channels
  FOR UPDATE USING (
    auth.jwt() ->> 'user_role' = 'admin'
  );

CREATE POLICY "Allow admins to delete news_channels" ON public.news_channels
  FOR DELETE USING (
    auth.jwt() ->> 'user_role' = 'admin'
  );

-- news_categories
ALTER TABLE public.news_categories ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow all users to read news_categories" ON public.news_categories
  FOR SELECT USING (true);

CREATE POLICY "Allow admins to manage news_categories" ON public.news_categories
  FOR INSERT WITH CHECK (
    auth.jwt() ->> 'user_role' = 'admin'
  );

CREATE POLICY "Allow admins to update news_categories" ON public.news_categories
  FOR UPDATE USING (
    auth.jwt() ->> 'user_role' = 'admin'
  );

CREATE POLICY "Allow admins to delete news_categories" ON public.news_categories
  FOR DELETE USING (
    auth.jwt() ->> 'user_role' = 'admin'
  );

-- news_posts
ALTER TABLE public.news_posts ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow all users to read news_posts" ON public.news_posts
  FOR SELECT USING (true);

CREATE POLICY "Allow admins to manage news_posts" ON public.news_posts
  FOR INSERT WITH CHECK (
    auth.jwt() ->> 'user_role' = 'admin'
  );

CREATE POLICY "Allow admins to update news_posts" ON public.news_posts
  FOR UPDATE USING (
    auth.jwt() ->> 'user_role' = 'admin'
  );

CREATE POLICY "Allow admins to delete news_posts" ON public.news_posts
  FOR DELETE USING (
    auth.jwt() ->> 'user_role' = 'admin'
  );

-- news_digests
ALTER TABLE public.news_digests ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow all users to read news_digests" ON public.news_digests
  FOR SELECT USING (true);

CREATE POLICY "Allow admins to manage news_digests" ON public.news_digests
  FOR INSERT WITH CHECK (
    auth.jwt() ->> 'user_role' = 'admin'
  );

CREATE POLICY "Allow admins to update news_digests" ON public.news_digests
  FOR UPDATE USING (
    auth.jwt() ->> 'user_role' = 'admin'
  );

CREATE POLICY "Allow admins to delete news_digests" ON public.news_digests
  FOR DELETE USING (
    auth.jwt() ->> 'user_role' = 'admin'
  );

-- news_digest_posts
ALTER TABLE public.news_digest_posts ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow all users to read news_digest_posts" ON public.news_digest_posts
  FOR SELECT USING (true);

CREATE POLICY "Allow admins to manage news_digest_posts" ON public.news_digest_posts
  FOR INSERT WITH CHECK (
    auth.jwt() ->> 'user_role' = 'admin'
  );

CREATE POLICY "Allow admins to update news_digest_posts" ON public.news_digest_posts
  FOR UPDATE USING (
    auth.jwt() ->> 'user_role' = 'admin'
  );

CREATE POLICY "Allow admins to delete news_digest_posts" ON public.news_digest_posts
  FOR DELETE USING (
    auth.jwt() ->> 'user_role' = 'admin'
  );

-- news_post_categories
ALTER TABLE public.news_post_categories ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow all users to read news_post_categories" ON public.news_post_categories
  FOR SELECT USING (true);

CREATE POLICY "Allow admins to manage news_post_categories" ON public.news_post_categories
  FOR INSERT WITH CHECK (
    auth.jwt() ->> 'user_role' = 'admin'
  );

CREATE POLICY "Allow admins to update news_post_categories" ON public.news_post_categories
  FOR UPDATE USING (
    auth.jwt() ->> 'user_role' = 'admin'
  );

CREATE POLICY "Allow admins to delete news_post_categories" ON public.news_post_categories
  FOR DELETE USING (
    auth.jwt() ->> 'user_role' = 'admin'
  );

-- ============================================================================
-- 2. COMPETITOR TABLES
-- ============================================================================

-- competitor_tg_posts
ALTER TABLE public.competitor_tg_posts ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow all users to read competitor_tg_posts" ON public.competitor_tg_posts
  FOR SELECT USING (true);

CREATE POLICY "Allow admins to manage competitor_tg_posts" ON public.competitor_tg_posts
  FOR INSERT WITH CHECK (
    auth.jwt() ->> 'user_role' = 'admin'
  );

CREATE POLICY "Allow admins to update competitor_tg_posts" ON public.competitor_tg_posts
  FOR UPDATE USING (
    auth.jwt() ->> 'user_role' = 'admin'
  );

CREATE POLICY "Allow admins to delete competitor_tg_posts" ON public.competitor_tg_posts
  FOR DELETE USING (
    auth.jwt() ->> 'user_role' = 'admin'
  );

-- ============================================================================
-- NOTES:
-- ============================================================================
-- 
-- 1. RLS использует auth.jwt() ->> 'user_role' для проверки роли
--    Убедитесь, что значение 'user_role' корректно устанавливается в JWT token
--    в процессе аутентификации через Telegram Mini App
--
-- 2. Все SELECT запросы доступны всем (USING (true))
--    Это соответствует требованию "витрина - все видят одинаково"
--
-- 3. INSERT/UPDATE/DELETE доступны только админам
--    Политики проверяют auth.jwt() ->> 'user_role' = 'admin'
--
-- 4. Если у вас есть другие таблицы, которые нужно защитить,
--    добавьте аналогичные политики
--
-- 5. Для отладки RLS ошибок используйте:
--    SELECT * FROM information_schema.role_table_grants
--    WHERE table_schema = 'public'
--
