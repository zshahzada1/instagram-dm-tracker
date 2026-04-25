-- Instagram DM Media Tracker - Initial Schema
-- Version: 1
-- Based on Instagram DM Thread Reconnaissance (2026-04-23)

-- Enable foreign keys
PRAGMA foreign_keys = ON;

-- 1. threads table
CREATE TABLE IF NOT EXISTS threads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ig_thread_id TEXT NOT NULL UNIQUE,
    thread_internal_id TEXT,
    display_name TEXT NOT NULL,
    participant_handle TEXT,
    thread_url TEXT NOT NULL,
    last_scanned_at TIMESTAMP,
    auto_refresh_enabled BOOLEAN DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for threads
CREATE INDEX IF NOT EXISTS idx_threads_ig_thread_id ON threads(ig_thread_id);
CREATE INDEX IF NOT EXISTS idx_threads_last_scanned ON threads(last_scanned_at);

-- 2. items table
CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    thread_id INTEGER NOT NULL,
    ig_message_id TEXT,
    natural_key TEXT,
    item_type TEXT NOT NULL,
    media_shortcode TEXT,
    media_url TEXT NOT NULL,
    poster_handle TEXT,
    caption TEXT,
    sent_at TIMESTAMP NOT NULL,
    sender TEXT NOT NULL,
    watched BOOLEAN DEFAULT 0,
    my_existing_reaction TEXT,
    my_auto_sent_reaction TEXT,
    dom_fingerprint TEXT,
    first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (thread_id) REFERENCES threads(id) ON DELETE CASCADE,
    UNIQUE(ig_message_id),
    UNIQUE(natural_key)
);

-- Indexes for items
CREATE INDEX IF NOT EXISTS idx_items_thread_id ON items(thread_id);
CREATE INDEX IF NOT EXISTS idx_items_thread_sent ON items(thread_id, sent_at DESC);
CREATE INDEX IF NOT EXISTS idx_items_watched ON items(watched);
CREATE INDEX IF NOT EXISTS idx_items_item_type ON items(item_type);
CREATE INDEX IF NOT EXISTS idx_items_first_seen ON items(first_seen_at);

-- 3. carousel_slides table
CREATE TABLE IF NOT EXISTS carousel_slides (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER NOT NULL,
    slide_index INTEGER NOT NULL,
    media_url TEXT NOT NULL,
    media_type TEXT NOT NULL,
    thumbnail_url TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (item_id) REFERENCES items(id) ON DELETE CASCADE,
    UNIQUE(item_id, slide_index)
);

-- Indexes for carousel_slides
CREATE INDEX IF NOT EXISTS idx_carousel_item_id ON carousel_slides(item_id);
CREATE INDEX IF NOT EXISTS idx_carousel_slide_order ON carousel_slides(item_id, slide_index);

-- 4. settings table
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    description TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Default settings
INSERT OR IGNORE INTO settings (key, value, description) VALUES
('default_reaction_emoji', '❤', 'Default emoji for auto-reactions'),
('auto_refresh_minutes', '5', 'Minutes between auto-refresh scans'),
('auto_next_enabled', '0', 'Auto-advance to next unwatched item'),
('auto_react_enabled', '0', 'Automatically react to new items'),
('sort_order', 'sent_at_desc', 'Default sort: sent_at_desc, sent_at_asc, first_seen_desc');

-- Index for settings
CREATE INDEX IF NOT EXISTS idx_settings_key ON settings(key);

-- 5. scan_runs table
CREATE TABLE IF NOT EXISTS scan_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    thread_id INTEGER,
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    new_items_found INTEGER DEFAULT 0,
    status TEXT NOT NULL,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (thread_id) REFERENCES threads(id) ON DELETE CASCADE
);

-- Indexes for scan_runs
CREATE INDEX IF NOT EXISTS idx_scan_runs_thread_id ON scan_runs(thread_id);
CREATE INDEX IF NOT EXISTS idx_scan_runs_started_at ON scan_runs(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_scan_runs_status ON scan_runs(status);

-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    description TEXT
);

-- Insert initial schema version
INSERT OR IGNORE INTO schema_version (version, description) VALUES (1, 'Initial schema');
