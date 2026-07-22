-- Migration: create user_roles table and add RLS policies
-- Run this against your Neon/Supabase database (psql or Supabase SQL editor)

-- Ensure pgcrypto for gen_random_uuid() is available
CREATE EXTENSION IF NOT EXISTS pgcrypto;

BEGIN;

-- Create table if it does not exist
CREATE TABLE IF NOT EXISTS public.user_roles (
  id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id uuid NOT NULL,
  role text NOT NULL,
  created_at timestamptz DEFAULT now(),
  CONSTRAINT user_roles_user_id_role_unique UNIQUE (user_id, role),
  CONSTRAINT user_roles_user_fkey FOREIGN KEY (user_id)
    REFERENCES public.users(user_id) ON DELETE CASCADE
);

-- Enable Row Level Security
ALTER TABLE public.user_roles ENABLE ROW LEVEL SECURITY;

-- INSERT policy: allow authenticated admin/super_admin users to insert
CREATE POLICY allow_admins_insert_user_roles
ON public.user_roles
FOR INSERT
WITH CHECK (
  EXISTS (
    SELECT 1 FROM public.users u
    WHERE u.user_id = auth.uid()
      AND u.role IN ('admin','super_admin')
  )
);

-- UPDATE policy: allow admins to update, and ensure role stays valid
CREATE POLICY allow_admins_update_user_roles
ON public.user_roles
FOR UPDATE
USING (
  EXISTS (
    SELECT 1 FROM public.users u
    WHERE u.user_id = auth.uid()
      AND u.role IN ('admin','super_admin')
  )
)
WITH CHECK (
  role IN ('admin','super_admin')
);

-- SELECT policy: allow admins to view user_roles
CREATE POLICY allow_admins_select_user_roles
ON public.user_roles
FOR SELECT
USING (
  EXISTS (
    SELECT 1 FROM public.users u
    WHERE u.user_id = auth.uid()
      AND u.role IN ('admin','super_admin')
  )
);

COMMIT;

-- Notes:
-- - This assumes auth.uid() returns the same UUID as public.users.user_id in your users table.
-- - If your JWT uses email or a different claim, replace the auth.uid() comparison with
--   `u.email = current_setting('request.jwt.claims.email', true)` or the appropriate claim.
-- - To apply this migration locally, run:
--     psql "$DATABASE_URL" -f migrations/0001_user_roles_policies.sql
