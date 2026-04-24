# SQLite Schema Design

**Version:** 1.0
**Based on:** Instagram DM Thread Reconnaissance (2026-04-23)
**Approach:** Network-intercept with GraphQL response parsing

## Overview

This schema supports an Instagram DM media scanner that:
- Tracks multiple threads
- Identifies new media items (reels, posts, carousels, stories)
- Stores message IDs for reliable reactions
- Maintains scan history and settings
- Supports carousel slide tracking

## Design Principles

1. **Stable IDs First:** Use Instagram's real message IDs from GraphQL responses
2. **Natural Key Fallback:** If message ID unavailable, use composite key
3. **Audit Trail:** Track when items are first seen vs. watched
4. **Performance:** Index on common query patterns
5. **Simplicity:** Avoid over-engineering for non-coder user

## Schema Definition

### 1. threads

Stores Instagram DM threads being monitored.

```sql
CREATE TABLE threads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ig_thread_id TEXT NOT NULL UNIQUE,        -- Instagram's thread ID from GraphQL
    display_name TEXT NOT NULL,               -- Human-readable name (e.g., "John Doe")
    participant_handle TEXT,                  -- Instagram username (e.g., "johndoe")
    thread_url TEXT NOT NULL,                 -- Full Instagram DM URL
    last_scanned_at TIMESTAMP,                -- Last successful scan timestamp
    auto_refresh_enabled BOOLEAN DEFAULT 0,   -- Whether to auto-refresh this thread
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX idx_threads_ig_thread_id ON threads(ig_thread_id);
CREATE INDEX idx_threads_last_scanned ON threads(last_scanned_at);
```

**Rationale:**
- `ig_thread_id` is unique and stable from GraphQL
- `display_name` for UI (full name from GraphQL)
- `participant_handle` for debugging/identification
- `auto_refresh_enabled` for future automation features

### 2. items

Stores individual media items found in DM threads.

```sql
CREATE TABLE items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    thread_id INTEGER NOT NULL,               -- Foreign key to threads
    ig_message_id TEXT,                       -- Instagram's message ID from GraphQL (STABLE)
    natural_key TEXT,                         -- Fallback: timestamp_sender_content_hash
    item_type TEXT NOT NULL,                  -- 'reel', 'post', 'carousel', 'story'
    media_shortcode TEXT,                     -- Instagram media shortcode (e.g., "C123xyz")
    media_url TEXT NOT NULL,                  -- Direct CDN URL to media
    poster_handle TEXT,                       -- Username who posted the media
    caption TEXT,                             -- Media caption text
    sent_at TIMESTAMP NOT NULL,               -- When message was sent
    sender TEXT NOT NULL,                     -- 'me' or 'her' (from participant IDs)
    watched BOOLEAN DEFAULT 0,                -- Whether user has watched this item
    my_existing_reaction TEXT,                -- Emoji if already reacted: '❤', '😂', etc.
    my_auto_sent_reaction TEXT,               -- Emoji if auto-reacted: '❤', '😂', etc.
    dom_fingerprint TEXT,                     -- JSON blob: {timestamp_ms, poster_handle, caption_snippet}
                                              -- used to match stored message_id back to a rendered DOM bubble
                                              -- needed because IG DOM has no stable per-bubble IDs
    first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  -- When scanner first found item
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (thread_id) REFERENCES threads(id) ON DELETE CASCADE,
    UNIQUE(ig_message_id),                    -- Prevent duplicates from same IG message
    UNIQUE(natural_key)                       -- Prevent duplicates when ig_message_id NULL
);

-- Critical performance indexes
CREATE INDEX idx_items_thread_id ON items(thread_id);
CREATE INDEX idx_items_thread_sent ON items(thread_id, sent_at DESC);  -- Common query pattern
CREATE INDEX idx_items_watched ON items(watched);                     -- Filter unwatched
CREATE INDEX idx_items_item_type ON items(item_type);                  -- Filter by type
CREATE INDEX idx_items_first_seen ON items(first_seen_at);             -- Chronological discovery
```

**Rationale:**
- `ig_message_id` is the stable identifier from GraphQL for reactions
- `natural_key` as fallback if message ID unavailable (rare)
- `item_type` enum for filtering and UI rendering
- `media_shortcode` for linking to original Instagram post/reel
- `watched` flag for user workflow (mark as seen)
- `my_existing_reaction` to avoid re-reacting
- `my_auto_sent_reaction` to distinguish manual vs auto reactions
- `dom_fingerprint` (JSON TEXT) stores `{timestamp_ms, poster_handle, caption_snippet}` — used to match a stored `ig_message_id` back to a rendered DOM bubble when reacting. IG's DOM has no stable per-bubble IDs; class names are obfuscated. The fingerprint lets the scanner correlate network-intercepted message IDs with DOM position.
- `first_seen_at` vs `sent_at` for scan logic

**Item Types:**
- `reel`: Instagram Reel shared in DM
- `post`: Regular feed post shared in DM  
- `carousel`: Multi-slide post shared in DM
- `story`: Story share (usually expired, but track anyway)

### 3. carousel_slides

Stores individual slides for carousel posts.

```sql
CREATE TABLE carousel_slides (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER NOT NULL,                -- Foreign key to items (parent carousel)
    slide_index INTEGER NOT NULL,            -- 0-based slide position
    media_url TEXT NOT NULL,                 -- CDN URL for this slide
    media_type TEXT NOT NULL,                -- 'image' or 'video'
    thumbnail_url TEXT,                      -- Thumbnail URL (if different)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (item_id) REFERENCES items(id) ON DELETE CASCADE,
    UNIQUE(item_id, slide_index)             -- One entry per slide per item
);

-- Indexes
CREATE INDEX idx_carousel_item_id ON carousel_slides(item_id);
CREATE INDEX idx_carousel_slide_order ON carousel_slides(item_id, slide_index);
```

**Rationale:**
- Carousels need per-slide tracking for full viewing
- `slide_index` maintains order
- `media_type` distinguishes image vs video slides
- `thumbnail_url` for video preview in UI

### 4. settings

Application-wide key-value settings.

```sql
CREATE TABLE settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    description TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Default settings (inserted on schema creation)
INSERT INTO settings (key, value, description) VALUES
('default_reaction_emoji', '❤', 'Default emoji for auto-reactions'),
('auto_refresh_minutes', '5', 'Minutes between auto-refresh scans'),
('auto_next_enabled', '0', 'Auto-advance to next unwatched item'),
('auto_react_enabled', '0', 'Automatically react to new items'),
('sort_order', 'sent_at_desc', 'Default sort: sent_at_desc, sent_at_asc, first_seen_desc');

-- Index
CREATE INDEX idx_settings_key ON settings(key);
```

**Rationale:**
- Simple key-value for easy configuration
- No complex schema needed for basic settings
- `description` for UI tooltips

**Settings Keys:**
- `default_reaction_emoji`: Which emoji to use for auto-reactions
- `auto_refresh_minutes`: How often to scan threads
- `auto_next_enabled`: Whether to auto-advance in UI
- `auto_react_enabled`: Whether to automatically react
- `sort_order`: Default item ordering in UI

### 5. scan_runs

Audit trail of scan operations.

```sql
CREATE TABLE scan_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    thread_id INTEGER NOT NULL,               -- Thread scanned
    started_at TIMESTAMP NOT NULL,            -- Scan start time
    completed_at TIMESTAMP,                   -- Scan end time (NULL if failed/running)
    new_items_found INTEGER DEFAULT 0,        -- Count of new items discovered
    status TEXT NOT NULL,                     -- 'running', 'completed', 'failed'
    error_message TEXT,                       -- Error details if failed
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (thread_id) REFERENCES threads(id) ON DELETE CASCADE
);

-- Indexes
CREATE INDEX idx_scan_runs_thread_id ON scan_runs(thread_id);
CREATE INDEX idx_scan_runs_started_at ON scan_runs(started_at DESC);
CREATE INDEX idx_scan_runs_status ON scan_runs(status);
```

**Rationale:**
- Debugging scan issues
- Performance monitoring
- Audit trail for automation
- Track how many new items per scan

## Migration Approach

### Recommendation: Manual SQL Versioning

**Why not Alembic?**
- User is non-coder
- Simple schema (5 tables)
- No complex migrations anticipated
- Easier to debug and understand
- No additional dependencies

### Migration System Design

**Version Table:**
```sql
CREATE TABLE schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    description TEXT
);

INSERT INTO schema_version (version, description) VALUES (1, 'Initial schema');
```

**Migration Scripts:**
```
migrations/
├── 001_initial_schema.sql
├── 002_add_reaction_tracking.sql  -- Future
└── 003_add_full_text_search.sql   -- Future
```

**Migration Logic:**
```python
def run_migrations(db_path):
    current_version = get_current_version(db_path)
    for migration_file in sorted(migration_files):
        migration_version = int(migration_file.split('_')[0])
        if migration_version > current_version:
            apply_migration(db_path, migration_file)
```

### Initial Setup Script

```python
def initialize_database(db_path='instagram_dm_tracker.db'):
    """Create database schema and apply initial migration."""
    conn = sqlite3.connect(db_path)
    
    # Read and execute migration 001
    with open('migrations/001_initial_schema.sql', 'r') as f:
        sql = f.read()
        conn.executescript(sql)
    
    conn.commit()
    conn.close()
    print(f"Database initialized at {db_path}")
```

## Additional Fields Based on Recon Findings

### Fields Added After Recon

1. **threads.ig_thread_id**: Direct from GraphQL `id` field
2. **threads.participant_handle**: From GraphQL `users[0].username`
3. **items.ig_message_id**: From GraphQL message `id` (critical for reactions)
4. **items.media_shortcode**: Extracted from media URLs or GraphQL response
5. **items.sent_at**: From GraphQL timestamp fields
6. **items.sender**: Derived from participant ID comparison

### Fields Not in Original Spec

1. **items.my_existing_reaction**: Track existing reactions to avoid duplicates
2. **items.my_auto_sent_reaction**: Distinguish manual vs auto reactions
3. **items.first_seen_at**: Separate from sent_at for scan logic
4. **scan_runs.new_items_found**: Metric for automation effectiveness

## Performance Considerations

### Index Strategy

**High-Query Paths:**
1. `items(thread_id, sent_at DESC)` - Main thread view
2. `items(watched)` - Unwatched items filter
3. `items(item_type)` - Type filtering
4. `scan_runs(thread_id, started_at DESC)` - Scan history

**Storage Estimates:**
- 100 threads × 50 items × 2KB = ~10MB database
- Indexes add ~20% overhead
- Carousel slides: additional ~10% for multi-slide posts

### Query Optimization

**Common Query: Get unwatched items for thread**
```sql
SELECT * FROM items 
WHERE thread_id = ? AND watched = 0 
ORDER BY sent_at DESC;
```
**Uses indexes:** `idx_items_thread_sent`, `idx_items_watched`

**Common Query: Check for new items**
```sql
SELECT COUNT(*) FROM items 
WHERE thread_id = ? AND first_seen_at > ?;
```
**Uses indexes:** `idx_items_thread_id`, `idx_items_first_seen`

## Data Integrity

### Foreign Keys
- All `thread_id` fields reference `threads(id)`
- `ON DELETE CASCADE` automatically cleans up orphans

### Unique Constraints
- `threads.ig_thread_id` - One DB entry per Instagram thread
- `items.ig_message_id` - One DB entry per Instagram message
- `items.natural_key` - Fallback uniqueness
- `carousel_slides(item_id, slide_index)` - One entry per slide

### Data Validation
- `item_type` should be one of: 'reel', 'post', 'carousel', 'story'
- `sender` should be 'me' or 'her'
- `watched` should be 0 or 1
- `status` in scan_runs should be 'running', 'completed', 'failed'

## Future Extensions

### Potential v2.0 Additions

1. **Full-Text Search:**
   ```sql
   CREATE VIRTUAL TABLE items_fts USING fts5(
       caption, poster_handle,
       content='items',
       content_rowid='id'
   );
   ```

2. **Reaction History:**
   ```sql
   CREATE TABLE reaction_history (
       id INTEGER PRIMARY KEY,
       item_id INTEGER NOT NULL,
       reaction_emoji TEXT NOT NULL,
       reacted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
       FOREIGN KEY (item_id) REFERENCES items(id)
   );
   ```

3. **Media Metadata:**
   ```sql
   ALTER TABLE items ADD COLUMN media_width INTEGER;
   ALTER TABLE items ADD COLUMN media_height INTEGER;
   ALTER TABLE items ADD COLUMN media_duration INTEGER;  -- For videos
   ```

## Summary

This schema provides:
- ✅ Stable message ID storage for reliable reactions
- ✅ Support for all Instagram media types
- ✅ Carousel slide tracking
- ✅ Audit trail for debugging
- ✅ Simple settings management
- ✅ Performance-optimized indexes
- ✅ Data integrity constraints
- ✅ Migration path for future changes

**Next Step:** Implement schema in Prompt 3 scanner build.

---

**Database File:** `instagram_dm_tracker.db`
**Migration Directory:** `migrations/`
**Initial Schema Version:** 1
