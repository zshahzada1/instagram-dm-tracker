"""Threads API endpoints."""
import sqlite3
from fastapi import APIRouter, Depends, HTTPException
from api.db import get_db
from api.schemas import Thread

router = APIRouter(prefix="/threads", tags=["threads"])


@router.get("", response_model=list[Thread])
def list_threads(conn: sqlite3.Connection = Depends(get_db)) -> list[Thread]:
    """
    List all tracked threads with computed stats.

    Returns:
        List of threads with total_items and unwatched_count computed.
    """
    query = """
    SELECT
        t.id,
        t.ig_thread_id,
        t.display_name,
        t.participant_handle,
        t.thread_url,
        t.last_scanned_at,
        t.auto_refresh_enabled,
        t.created_at,
        t.updated_at,
        COALESCE(SUM(CASE WHEN i.id IS NOT NULL THEN 1 ELSE 0 END), 0) as total_items,
        COALESCE(SUM(CASE WHEN i.sender = 'her' AND i.watched = 0 THEN 1 ELSE 0 END), 0) as unwatched_count,
        MAX(i.sent_at) as last_item_sent_at
    FROM threads t
    LEFT JOIN items i ON t.id = i.thread_id
    GROUP BY t.id
    ORDER BY t.updated_at DESC
    """
    cursor = conn.execute(query)
    threads = []
    for row in cursor.fetchall():
        thread = Thread(
            id=row["id"],
            ig_thread_id=row["ig_thread_id"],
            display_name=row["display_name"],
            participant_handle=row["participant_handle"],
            thread_url=row["thread_url"],
            last_scanned_at=row["last_scanned_at"],
            auto_refresh_enabled=bool(row["auto_refresh_enabled"]),
            total_items=row["total_items"],
            unwatched_count=row["unwatched_count"],
            last_item_sent_at=row["last_item_sent_at"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
        threads.append(thread)
    return threads


@router.get("/{thread_id}", response_model=Thread)
def get_thread(thread_id: int, conn: sqlite3.Connection = Depends(get_db)) -> Thread:
    """
    Get a specific thread by ID.

    Args:
        thread_id: Thread database ID.

    Returns:
        Thread with computed stats.

    Raises:
        HTTPException: 404 if thread not found.
    """
    query = """
    SELECT
        t.id,
        t.ig_thread_id,
        t.display_name,
        t.participant_handle,
        t.thread_url,
        t.last_scanned_at,
        t.auto_refresh_enabled,
        t.created_at,
        t.updated_at,
        COALESCE(SUM(CASE WHEN i.id IS NOT NULL THEN 1 ELSE 0 END), 0) as total_items,
        COALESCE(SUM(CASE WHEN i.sender = 'her' AND i.watched = 0 THEN 1 ELSE 0 END), 0) as unwatched_count,
        MAX(i.sent_at) as last_item_sent_at
    FROM threads t
    LEFT JOIN items i ON t.id = i.thread_id
    WHERE t.id = ?
    GROUP BY t.id
    """
    cursor = conn.execute(query, (thread_id,))
    row = cursor.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Thread not found")
    return Thread(
        id=row["id"],
        ig_thread_id=row["ig_thread_id"],
        display_name=row["display_name"],
        participant_handle=row["participant_handle"],
        thread_url=row["thread_url"],
        last_scanned_at=row["last_scanned_at"],
        auto_refresh_enabled=bool(row["auto_refresh_enabled"]),
        total_items=row["total_items"],
        unwatched_count=row["unwatched_count"],
        last_item_sent_at=row["last_item_sent_at"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )
