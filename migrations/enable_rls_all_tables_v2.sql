-- Migration: Enable RLS on all public tables with JWT user_role claims
-- Date: 2026-02-11
-- Purpose: Fix security warnings - enable Row Level Security with appropriate policies
--
-- Note: This migration expects 'user_role' to be available in auth.jwt()
-- Set up via: supabase.auth.updateUser({ data: { user_role: 'admin' | 'viewer' } })

-- Helper function to check if user is admin
CREATE OR REPLACE FUNCTION is_admin()
RETURNS boolean
LANGUAGE SQL
STABLE
AS $$
  SELECT (auth.jwt() ->> 'user_metadata')::jsonb ->> 'user_role' = 'admin'
$$;

-- ============================================================================
-- 1. NEWS TABLES
-- ============================================================================

-- news_channels
ALTER TABLE public.news_channels ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow all users to read news_channels" ON public.news_channels
  FOR SELECT USING (true);

CREATE POLICY "Allow admins to manage news_channels" ON public.news_channels
  FOR INSERT WITH CHECK (is_admin());

CREATE POLICY "Allow admins to update news_channels" ON public.news_channels
  FOR UPDATE USING (is_admin());

CREATE POLICY "Allow admins to delete news_channels" ON public.news_channels
  FOR DELETE USING (is_admin());

-- news_categories
ALTER TABLE public.news_categories ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow all users to read news_categories" ON public.news_categories
  FOR SELECT USING (true);

CREATE POLICY "Allow admins to manage news_categories" ON public.news_categories
  FOR INSERT WITH CHECK (is_admin());

CREATE POLICY "Allow admins to update news_categories" ON public.news_categories
  FOR UPDATE USING (is_admin());

CREATE POLICY "Allow admins to delete news_categories" ON public.news_categories
  FOR DELETE USING (is_admin());

-- news_posts
ALTER TABLE public.news_posts ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow all users to read news_posts" ON public.news_posts
  FOR SELECT USING (true);

CREATE POLICY "Allow admins to manage news_posts" ON public.news_posts
  FOR INSERT WITH CHECK (is_admin());

CREATE POLICY "Allow admins to update news_posts" ON public.news_posts
  FOR UPDATE USING (is_admin());

CREATE POLICY "Allow admins to delete news_posts" ON public.news_posts
  FOR DELETE USING (is_admin());

-- news_digests
ALTER TABLE public.news_digests ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow all users to read news_digests" ON public.news_digests
  FOR SELECT USING (true);

CREATE POLICY "Allow admins to manage news_digests" ON public.news_digests
  FOR INSERT WITH CHECK (is_admin());

CREATE POLICY "Allow admins to update news_digests" ON public.news_digests
  FOR UPDATE USING (is_admin());

CREATE POLICY "Allow admins to delete news_digests" ON public.news_digests
  FOR DELETE USING (is_admin());

-- news_digest_posts
ALTER TABLE public.news_digest_posts ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow all users to read news_digest_posts" ON public.news_digest_posts
  FOR SELECT USING (true);

CREATE POLICY "Allow admins to manage news_digest_posts" ON public.news_digest_posts
  FOR INSERT WITH CHECK (is_admin());

CREATE POLICY "Allow admins to update news_digest_posts" ON public.news_digest_posts
  FOR UPDATE USING (is_admin());

CREATE POLICY "Allow admins to delete news_digest_posts" ON public.news_digest_posts
  FOR DELETE USING (is_admin());

-- news_post_categories
ALTER TABLE public.news_post_categories ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow all users to read news_post_categories" ON public.news_post_categories
  FOR SELECT USING (true);

CREATE POLICY "Allow admins to manage news_post_categories" ON public.news_post_categories
  FOR INSERT WITH CHECK (is_admin());

CREATE POLICY "Allow admins to update news_post_categories" ON public.news_post_categories
  FOR UPDATE USING (is_admin());

CREATE POLICY "Allow admins to delete news_post_categories" ON public.news_post_categories
  FOR DELETE USING (is_admin());

-- ============================================================================
-- 2. COMPETITOR TABLES
-- ============================================================================

-- competitor_tg_posts
ALTER TABLE public.competitor_tg_posts ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow all users to read competitor_tg_posts" ON public.competitor_tg_posts
  FOR SELECT USING (true);

CREATE POLICY "Allow admins to manage competitor_tg_posts" ON public.competitor_tg_posts
  FOR INSERT WITH CHECK (is_admin());

CREATE POLICY "Allow admins to update competitor_tg_posts" ON public.competitor_tg_posts
  FOR UPDATE USING (is_admin());

CREATE POLICY "Allow admins to delete competitor_tg_posts" ON public.competitor_tg_posts
  FOR DELETE USING (is_admin());

-- ============================================================================
-- IMPLEMENTATION CHECKLIST
-- ============================================================================
--
-- ✅ 1. Run both migrations in order:
--       a) setup_user_roles.sql (adds role column to users table)
--       b) enable_rls_all_tables.sql (THIS FILE - enables RLS with policies)
--
-- ✅ 2. Update webapp/src/services/supabase.js
--       - Modified checkUserAccess() to call supabase.auth.updateUser()
--       - This sets user_role in auth metadata
--
-- ✅ 3. Verify in Supabase Dashboard:
--       - Database → RLS Policies → check all tables have policies enabled
--       - Auth → Users → create test user
--       - Database → users table → insert test user with role='admin'
--
-- ✅ 4. Test in application:
--       - Login as viewer - should see read-only data
--       - Login as admin - should be able to create/edit/delete data
--
-- ⚠️  TROUBLESHOOTING:
--
-- If you get "JWT missing" errors:
--   - Make sure you're logged in (getTelegramUser returns valid user)
--   - Check that auth.updateUser() is being called in checkUserAccess()
--   - Verify user exists in 'users' table with telegram_id
--
-- If RLS policies block admin operations:
--   - Check auth.jwt() includes user_metadata
--   - Run: SELECT auth.jwt() in Supabase SQL Editor as test user
--   - Make sure is_admin() function returns correct value
--
-- To debug JWT contents:
--   - Add this policy: FOR SELECT USING (true)
--   - Then run: SELECT auth.jwt()
--
