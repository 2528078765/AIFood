-- Token-based free tier migration
ALTER TABLE users ADD COLUMN IF NOT EXISTS free_tokens_remaining INTEGER DEFAULT 1000000;
ALTER TABLE users DROP COLUMN IF EXISTS trial_started_at;
UPDATE users SET free_tokens_remaining = 1000000 WHERE free_tokens_remaining IS NULL OR free_tokens_remaining > 1000000;
