"""Items API endpoints."""
import sqlite3
import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from api.db import get_db
from api.schemas import Item, ItemsListResponse, ItemWatchedUpdate

router = APIRouter(prefix="/items", tags=["items"])


@router.get("", response_model=ItemsListResponse)
def list_items(
    thread_id: int | None = None,
    watched: bool | None = None,
    item_type: str | None = None,
    sender: str = Query(default="her", description="Filter by sender: 'me', 'her', or 'all'"),
    sort: str = Query(default="sent_at_desc", description="Sort order"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    conn: sqlite3.Connection = Depends(get_db),
) -> ItemsListResponse:
    """
    List media items with filtering and pagination.

    Args:
        thread_id: Filter by thread ID.
        watched: Filter by watched status.
        item_type: Filter by item type (reel, post, carousel, story).
        sender: Filter by sender ('me', 'her', or 'all').
        sort: Sort order (sent_at_desc, sent_at_asc, first_seen_desc).
        limit: Max items to return (1-200).
        offset: Pagination offset.

    Returns:
        Paginated list of items.
    """
    where_clauses = []
    params = []

    if thread_id is not None:
        where_clauses.append("i.thread_id = ?")
        params.append(thread_id)

    if watched is not None:
        where_clauses.append("i.watched = ?")
        params.append(1 if watched else 0)

    if item_type is not None:
        if item_type not in ("reel", "post", "carousel", "story"):
            raise HTTPException(status_code=422, detail="item_type must be one of: reel, post, carousel, story")
        where_clauses.append("i.item_type = ?")
        params.append(item_type)

    if sender != "all":
        if sender not in ("me", "her"):
            raise HTTPException(status_code=422, detail="sender must be one of: me, her, all")
        where_clauses.append("i.sender = ?")
        params.append(sender)

    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

    # Sort mapping
    sort_map = {
        "sent_at_desc": "i.sent_at DESC",
        "sent_at_asc": "i.sent_at ASC",
        "first_seen_desc": "i.first_seen_at DESC",
    }
    if sort not in sort_map:
        raise HTTPException(status_code=422, detail=f"sort must be one of: {', '.join(sort_map.keys())}")
    order_sql = sort_map[sort]

    # Get total count
    count_query = f"SELECT COUNT(*) FROM items i WHERE {where_sql}"
    total = conn.execute(count_query, params).fetchone()[0]

    # Get items with pagination
    items_query = f"""
    SELECT
        i.id,
        i.thread_id,
        i.ig_message_id,
        i.item_type,
        i.media_shortcode,
        i.media_url,
        i.poster_handle,
        i.caption,
        i.sent_at,
        i.sender,
        i.watched,
        i.my_existing_reaction,
        i.my_auto_sent_reaction,
        i.first_seen_at,
        i.created_at,
        i.updated_at
    FROM items i
    WHERE {where_sql}
    ORDER BY {order_sql}
    LIMIT ? OFFSET ?
    """
    items_params = params + [limit, offset]
    cursor = conn.execute(items_query, items_params)

    items = []
    for row in cursor.fetchall():
        # Synthesize instagram_url
        instagram_url = None
        if row["media_shortcode"]:
            if row["item_type"] == "reel":
                instagram_url = f"https://www.instagram.com/reel/{row['media_shortcode']}/"
            elif row["item_type"] in ("post", "carousel"):
                instagram_url = f"https://www.instagram.com/p/{row['media_shortcode']}/"

        item = Item(
            id=row["id"],
            thread_id=row["thread_id"],
            ig_message_id=row["ig_message_id"],
            item_type=row["item_type"],
            media_shortcode=row["media_shortcode"],
            media_url=row["media_url"],
            poster_handle=row["poster_handle"],
            caption=row["caption"],
            sent_at=row["sent_at"],
            sender=row["sender"],
            watched=bool(row["watched"]),
            my_existing_reaction=row["my_existing_reaction"],
            my_auto_sent_reaction=row["my_auto_sent_reaction"],
            first_seen_at=row["first_seen_at"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            instagram_url=instagram_url,
        )
        items.append(item)

    return ItemsListResponse(total=total, limit=limit, offset=offset, items=items)


@router.get("/{item_id}", response_model=Item)
def get_item(item_id: int, conn: sqlite3.Connection = Depends(get_db)) -> Item:
    """
    Get a specific item by ID.

    Args:
        item_id: Item database ID.

    Returns:
        Item with synthesized instagram_url.

    Raises:
        HTTPException: 404 if item not found.
    """
    query = """
    SELECT
        i.id,
        i.thread_id,
        i.ig_message_id,
        i.item_type,
        i.media_shortcode,
        i.media_url,
        i.poster_handle,
        i.caption,
        i.sent_at,
        i.sender,
        i.watched,
        i.my_existing_reaction,
        i.my_auto_sent_reaction,
        i.first_seen_at,
        i.created_at,
        i.updated_at
    FROM items i
    WHERE i.id = ?
    """
    cursor = conn.execute(query, (item_id,))
    row = cursor.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Item not found")

    # Synthesize instagram_url
    instagram_url = None
    if row["media_shortcode"]:
        if row["item_type"] == "reel":
            instagram_url = f"https://www.instagram.com/reel/{row['media_shortcode']}/"
        elif row["item_type"] in ("post", "carousel"):
            instagram_url = f"https://www.instagram.com/p/{row['media_shortcode']}/"

    return Item(
        id=row["id"],
        thread_id=row["thread_id"],
        ig_message_id=row["ig_message_id"],
        item_type=row["item_type"],
        media_shortcode=row["media_shortcode"],
        media_url=row["media_url"],
        poster_handle=row["poster_handle"],
        caption=row["caption"],
        sent_at=row["sent_at"],
        sender=row["sender"],
        watched=bool(row["watched"]),
        my_existing_reaction=row["my_existing_reaction"],
        my_auto_sent_reaction=row["my_auto_sent_reaction"],
        first_seen_at=row["first_seen_at"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        instagram_url=instagram_url,
    )


@router.patch("/{item_id}/watched", response_model=Item)
def update_item_watched(
    item_id: int, update: ItemWatchedUpdate, conn: sqlite3.Connection = Depends(get_db)
) -> Item:
    """
    Update an item's watched status.

    Args:
        item_id: Item database ID.
        update: Watched status update.

    Returns:
        Updated item.

    Raises:
        HTTPException: 404 if item not found, 422 if request malformed.
    """
    # Check if item exists
    check_query = "SELECT id FROM items WHERE id = ?"
    if conn.execute(check_query, (item_id,)).fetchone() is None:
        raise HTTPException(status_code=404, detail="Item not found")

    # Update watched status
    update_query = """
    UPDATE items
    SET watched = ?, updated_at = CURRENT_TIMESTAMP
    WHERE id = ?
    """
    conn.execute(update_query, (1 if update.watched else 0, item_id))
    conn.commit()

    # Return updated item
    return get_item(item_id, conn)


@router.get("/{item_id}/thumbnail")
async def get_item_thumbnail(
    item_id: int,
    conn: sqlite3.Connection = Depends(get_db),
):
    """
    Proxy thumbnail image for an item.

    Fetches the item's media_url server-side and streams it to the UI.
    Bypasses CORS and auth issues with direct cdninstagram.com access.

    Args:
        item_id: Item database ID.

    Returns:
        StreamingResponse with image bytes and upstream Content-Type.

    Raises:
        HTTPException: 404 if item not found, 502 if upstream fails.
    """
    # Look up item
    query = """
    SELECT id, media_url
    FROM items
    WHERE id = ?
    """
    cursor = conn.execute(query, (item_id,))
    row = cursor.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Item not found")

    media_url = row["media_url"]
    if not media_url:
        raise HTTPException(status_code=404, detail="Item has no media URL")

    try:
        # Fetch thumbnail server-side
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(media_url)
            response.raise_for_status()

            # Stream response to client
            from fastapi.responses import StreamingResponse

            return StreamingResponse(
                response.aiter_bytes(),
                media_type=response.headers.get("content-type", "image/jpeg"),
                headers={
                    "Cache-Control": "public, max-age=3600",
                },
            )
    except httpx.HTTPError as e:
        # Don't log full URLs (contain signed tokens)
        raise HTTPException(status_code=502, detail="Failed to fetch thumbnail from upstream")
