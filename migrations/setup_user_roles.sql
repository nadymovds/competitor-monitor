-- Migration: Setup User Roles in Auth
-- Date: 2026-02-11
-- Purpose: Ensure 'users' table has 'role' column and JWT claims are configured

-- ============================================================================
-- 1. Add 'role' column to public.users table if it doesn't exist
-- ============================================================================

ALTER TABLE public.users 
ADD COLUMN IF NOT EXISTS role TEXT DEFAULT 'viewer' 
CHECK (role IN ('admin', 'viewer'));

-- ============================================================================
-- 2. Create or update Postgres function to set JWT claims
-- ============================================================================
-- This function will be used by Supabase in Auth to set custom JWT claims
-- based on the user's role stored in public.users table

CREATE OR REPLACE FUNCTION public.set_user_claims(user_id UUID)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  user_role TEXT;
BEGIN
  -- Get user role from users table (matched by auth.uid())
  -- NOTE: This assumes your users table has a column linking to auth.users
  -- If your linking is different (e.g., telegram_id), adjust the WHERE clause
  
  SELECT role INTO user_role
  FROM public.users
  WHERE id = user_id  -- Adjust this condition based on how you link users
  LIMIT 1;
  
  -- Default to 'viewer' if role not found
  user_role := COALESCE(user_role, 'viewer');
  
  RETURN jsonb_build_object(
    'user_role', user_role
  );
END;
$$;

-- ============================================================================
-- 3. Alternative: Manual JWT Setup in Supabase Dashboard
-- ============================================================================
-- 
-- If the above function approach doesn't work, you can manually configure
-- JWT claims in the Supabase Dashboard:
--
-- 1. Go to: Project Settings → Auth Providers → JWT
-- 2. In "JWT Template", add a custom claim:
--    {
--      "user_role": "SELECT CASE WHEN users.role = 'admin' THEN 'admin' ELSE 'viewer' END FROM public.users WHERE users.telegram_id = raw_user_meta_data ->> 'telegram_id'"
--    }
--
-- OR (simpler):
--    {
--      "user_role": "{{ user.user_metadata.user_role }}"
--    }
--
-- Then in your client code when authenticating, set user_metadata with:
--    {
--      "user_role": "admin"  // or "viewer"
--    }

-- ============================================================================
-- 4. Verify role column exists
-- ============================================================================

SELECT EXISTS (
  SELECT 1 
  FROM information_schema.columns 
  WHERE table_schema = 'public' 
  AND table_name = 'users' 
  AND column_name = 'role'
) as role_column_exists;

-- ============================================================================
-- NOTES FOR IMPLEMENTATION:
-- ============================================================================
--
-- A. In your Node.js/JavaScript code (webapp/src/services/supabase.js):
--    When you retrieve the user from 'users' table, you need to store 
--    the role somewhere that Supabase Auth JWT will pick it up.
--
-- B. Option 1: Store role in Auth User Metadata (RECOMMENDED)
--    - In checkUserAccess(), after retrieving user from DB:
--      await supabase.auth.updateUser({
--        data: { user_role: dbUser.role }
--      })
--    - Then Supabase will include 'user_role' in auth.jwt()
--
-- C. Option 2: Set it directly in auth.users table
--    - Run: UPDATE auth.users SET raw_user_meta_data = 
--           jsonb_set(raw_user_meta_data, '{user_role}', '"admin"')
--           WHERE id = (SELECT auth_user_id FROM public.users WHERE telegram_id = ...)
--    - Requires service role key and more complex logic
--
-- D. Option 3: Custom claims via JWT template (see step 3 above)
--    - Configure in Supabase Dashboard Auth settings
--    - Most reliable but requires manual dashboard configuration
--
-- RECOMMENDED APPROACH:
-- Implement Option B in checkUserAccess() function:
--
--    export async function checkUserAccess(telegramUser) {
--      const { data, error } = await supabase
--        .from('users')
--        .select('*')
--        .eq('telegram_id', telegramUser.id)
--        .single()
--      
--      if (error?.code === 'PGRST116') {
--        return { allowed: false, user: null }
--      }
--      if (error) throw error
--      
--      // UPDATE USER METADATA WITH ROLE
--      const { error: updateError } = await supabase.auth.updateUser({
--        data: { user_role: data.role || 'viewer' }
--      })
--      
--      if (updateError) console.error('Failed to set user role:', updateError)
--      
--      await supabase
--        .from('users')
--        .update({ last_seen_at: new Date().toISOString() })
--        .eq('telegram_id', telegramUser.id)
--      
--      return { allowed: true, user: data }
--    }
--
