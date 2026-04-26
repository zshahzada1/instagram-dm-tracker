# Instagram DM Tracker API Documentation

## Overview

The FastAPI backend provides a read-only API for managing Instagram DM media tracker data. All endpoints use JSON for requests and responses. The API runs on `http://localhost:8000` by default.

**Important:** This API is read-only with respect to Instagram. The only write operations are local database updates (marking items as watched, updating settings) and triggering scans that use passive GraphQL interception.

## Base URL

```
http://localhost:8000
```

## Authentication

None. This API runs on localhost for a single user.

## Endpoints

### Threads

#### GET /threads

List all tracked threads with computed stats.

**Response:**
```json
[
  {
    "id": 1,
    "ig_thread_id": "110975426965828",
    "display_name": "bel",
    "participant_handle": "isabellahay.nes",
    "thread_url": "https://www.instagram.com/direct/t/110975426965828/",
    "last_scanned_at": "2026-04-26T01:24:45.125728+00:00",
    "auto_refresh_enabled": false,
    "total_items": 177,
    "unwatched_count": 174,
    "last_item_sent_at": "2026-04-25T18:49:37.337000+00:00",
    "created_at": "2026-04-26 01:21:47",
    "updated_at": "2026-04-26T01:24:45.125740+00:00"
  }
]
```

The `total_items` and `unwatched_count` fields are computed via JOINs. `unwatched_count` only counts items where `sender='her'` and `watched=0`.

**Status Codes:**
- `200 OK` - Success

#### GET /threads/{id}

Get a specific thread by database ID.

**Response:** Same as GET /threads but a single object.

**Status Codes:**
- `200 OK` - Success
- `404 Not Found` - Thread not found

---

### Items

#### GET /items

List media items with filtering and pagination.

**Query Parameters:**
- `thread_id` (int, optional) - Filter by thread ID
- `watched` (bool, optional) - Filter by watched status
- `item_type` (string, optional) - One of: `reel`, `post`, `carousel`, `story`
- `sender` (string, default: `her`) - One of: `me`, `her`, `all`
- `sort` (string, default: `sent_at_desc`) - One of: `sent_at_desc`, `sent_at_asc`, `first_seen_desc`
- `limit` (int, default: 50, max: 200) - Max items to return
- `offset` (int, default: 0) - Pagination offset

**Response:**
```json
{
  "total": 142,
  "limit": 50,
  "offset": 0,
  "items": [
    {
      "id": 47,
      "thread_id": 1,
      "ig_message_id": "mid.$cAAA...",
      "item_type": "reel",
      "media_shortcode": "DXWHYO8ieJM",
      "media_url": "https://scontent...",
      "poster_handle": "clipsngl",
      "caption": null,
      "sent_at": "2026-04-23T18:24:07Z",
      "sender": "her",
      "watched": false,
      "my_existing_reaction": null,
      "my_auto_sent_reaction": null,
      "first_seen_at": "2026-04-26 01:21:47",
      "created_at": "2026-04-26 01:21:47",
      "updated_at": "2026-04-26 01:21:47",
      "instagram_url": "https://www.instagram.com/reel/DXWHYO8ieJM/"
    }
  ]
}
```

The `instagram_url` field is synthesized from `item_type` and `media_shortcode`. For stories, this field may be `null`.

**Status Codes:**
- `200 OK` - Success
- `422 Unprocessable Entity` - Invalid filter parameter

#### GET /items/{id}

Get a specific item by database ID.

**Response:** Same as a single item from GET /items.

**Status Codes:**
- `200 OK` - Success
- `404 Not Found` - Item not found

#### PATCH /items/{id}/watched

Update an item's watched status.

**Request Body:**
```json
{ "watched": true }
```

**Response:** The updated item (same shape as GET /items/{id}).

**Status Codes:**
- `200 OK` - Success
- `404 Not Found` - Item not found
- `422 Unprocessable Entity` - Malformed request body

#### GET /items/{id}/thumbnail

Proxy thumbnail image for an item.

This endpoint fetches the item's `media_url` server-side and streams it to the UI, bypassing CORS and authentication issues with direct cdninstagram.com access.

**Response:** Streaming image bytes with upstream Content-Type header.

**Headers:**
- `Cache-Control: public, max-age=3600` - Thumbnail cached for 1 hour

**Status Codes:**
- `200 OK` - Success
- `404 Not Found` - Item not found or item has no media URL
- `502 Bad Gateway` - Failed to fetch thumbnail from upstream

---

### Scans

#### POST /scans

Start a new scan of an Instagram DM thread.

**Request Body:**
```json
{
  "thread_url": "https://www.instagram.com/direct/t/110975426965828/",
  "max_messages": 200
}
```

The `max_messages` field defaults to 200 if omitted.

**Behavior:**
- Validates the thread URL format
- Checks for running scans; returns 409 Conflict if one exists
- Invokes the scanner synchronously (blocks for 30-60s)
- Returns scan results on completion

**Success Response (200):**
```json
{
  "success": true,
  "scan_run_id": 12,
  "thread_id": 1,
  "display_name": "bel",
  "messages_parsed": 200,
  "items_inserted": 4,
  "items_ignored": 196,
  "item_type_inserted_counts": {
    "reel": 3, "post": 1, "carousel": 0, "story": 0
  },
  "pagination": {
    "success": true,
    "messages_found": 200,
    "attempts": 5
  }
}
```

**Failure Response (500):**
```json
{
  "success": false,
  "scan_run_id": 12,
  "error": "Blocker detected at thread"
}
```

**Conflict Response (409):**
```json
{
  "detail": "Scan already in progress",
  "scan_run_id": 4
}
```

**Status Codes:**
- `200 OK` - Scan completed successfully
- `409 Conflict` - Scan already in progress
- `422 Unprocessable Entity` - Invalid thread URL format
- `500 Internal Server Error` - Scan failed

#### GET /scans

List scan runs with optional filtering.

**Query Parameters:**
- `thread_id` (int, optional) - Filter by thread ID
- `limit` (int, default: 20, max: 100) - Max runs to return

**Response:**
```json
[
  {
    "id": 12,
    "thread_id": 1,
    "started_at": "2026-04-26T01:20:16.342599+00:00",
    "completed_at": "2026-04-26T01:21:47.048123+00:00",
    "new_items_found": 4,
    "status": "completed",
    "error_message": null
  }
]
```

Results are ordered by `started_at DESC`.

**Status Codes:**
- `200 OK` - Success

#### GET /scans/{id}

Get a specific scan run by database ID.

**Response:** Same as a single scan run from GET /scans.

**Status Codes:**
- `200 OK` - Success
- `404 Not Found` - Scan run not found

---

### Settings

#### GET /settings

List all application settings.

**Response:**
```json
[
  {
    "key": "default_reaction_emoji",
    "value": "❤",
    "description": "Default emoji for auto-reactions",
    "updated_at": "2026-04-25 15:32:31"
  },
  {
    "key": "auto_refresh_minutes",
    "value": "5",
    "description": "Minutes between auto-refresh scans",
    "updated_at": "2026-04-25 15:32:31"
  }
]
```

**Status Codes:**
- `200 OK` - Success

#### PATCH /settings/{key}

Update a setting value.

**Request Body:**
```json
{ "value": "10" }
```

**Response:** The updated setting row.

**Status Codes:**
- `200 OK` - Success
- `404 Not Found` - Setting key not found
- `422 Unprocessable Entity` - Malformed request body

Note: Only existing settings can be updated. New keys cannot be created via this endpoint.

---

## CORS

The API is configured to allow requests from:
- `http://localhost:3000`
- `http://localhost:5173`
- `http://127.0.0.1:3000`
- `http://127.0.0.1:5173`

All methods and headers are allowed. Credentials are not required.

## Running the API

```bash
source venv/bin/activate
uvicorn api.main:app --reload --port 8000
```

API documentation (Swagger UI) is available at `http://localhost:8000/docs`.
