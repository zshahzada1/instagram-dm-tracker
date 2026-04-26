"""Pydantic schemas for API request/response models."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class Thread(BaseModel):
    """Instagram DM thread representation."""
    id: int
    ig_thread_id: str
    display_name: str
    participant_handle: Optional[str] = None
    thread_url: str
    last_scanned_at: Optional[str] = None
    auto_refresh_enabled: bool = False
    total_items: int = 0
    unwatched_count: int = 0
    last_item_sent_at: Optional[str] = None
    created_at: str
    updated_at: str


class Item(BaseModel):
    """Media item shared in a DM thread."""
    id: int
    thread_id: int
    ig_message_id: Optional[str] = None
    item_type: str
    media_shortcode: Optional[str] = None
    media_url: str
    poster_handle: Optional[str] = None
    caption: Optional[str] = None
    sent_at: str
    sender: str
    watched: bool = False
    my_existing_reaction: Optional[str] = None
    my_auto_sent_reaction: Optional[str] = None
    first_seen_at: str
    created_at: str
    updated_at: str
    instagram_url: Optional[str] = None


class ItemsListResponse(BaseModel):
    """Response model for items list endpoint."""
    total: int
    limit: int
    offset: int
    items: list[Item]


class ItemWatchedUpdate(BaseModel):
    """Request model for updating item watched status."""
    watched: bool


class ScanRequest(BaseModel):
    """Request model for starting a scan."""
    thread_url: str
    max_messages: Optional[int] = 200


class ScanResult(BaseModel):
    """Result from a scan operation."""
    success: bool
    scan_run_id: Optional[int] = None
    thread_id: Optional[int] = None
    thread_key: Optional[str] = None
    thread_internal_id: Optional[str] = None
    display_name: Optional[str] = None
    participant_handle: Optional[str] = None
    messages_parsed: Optional[int] = None
    items_inserted: Optional[int] = None
    items_ignored: Optional[int] = None
    item_type_inserted_counts: Optional[dict] = None
    pagination: Optional[dict] = None
    error: Optional[str] = None


class ScanRun(BaseModel):
    """Scan run representation."""
    id: int
    thread_id: Optional[int] = None
    started_at: str
    completed_at: Optional[str] = None
    new_items_found: int = 0
    status: str
    error_message: Optional[str] = None


class Setting(BaseModel):
    """Application setting representation."""
    key: str
    value: str
    description: Optional[str] = None
    updated_at: str


class SettingUpdate(BaseModel):
    """Request model for updating a setting."""
    value: str


class ConflictResponse(BaseModel):
    """Response when a conflicting operation is attempted."""
    detail: str
    scan_run_id: int
