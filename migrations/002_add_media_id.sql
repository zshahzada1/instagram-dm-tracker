-- P7: Add media_id column to items table
-- This stores Instagram's internal numeric media ID, which differs from media_shortcode
-- Required for the comments endpoint

ALTER TABLE items ADD COLUMN media_id TEXT;
