-- Migration: create password_resets table for password reset tokens
-- Run with: psql "$DATABASE_URL" -f migrations/0002_password_resets.sql

BEGIN;

CREATE TABLE IF NOT EXISTS public.password_resets (
  token text PRIMARY KEY,
  user_id uuid NOT NULL,
  expires_at timestamptz NOT NULL,
  created_at timestamptz DEFAULT now(),
  CONSTRAINT password_resets_user_fkey FOREIGN KEY (user_id)
    REFERENCES public.users(user_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS password_resets_expires_idx ON public.password_resets (expires_at);

COMMIT;
