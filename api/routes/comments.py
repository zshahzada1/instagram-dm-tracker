from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
import asyncio

from comments.fetcher import fetch_comments, CommentsNotLoadedError, CommentFetchError

router = APIRouter(prefix="/comments", tags=["comments"])

class CommentUserOut(BaseModel):
    id: str
    username: str
    profile_pic_url: str
    is_verified: bool

class CommentOut(BaseModel):
    pk: str
    text: str
    created_at: int
    comment_like_count: int
    child_comment_count: int
    has_liked_comment: bool
    is_edited: bool
    has_gif: bool
    user: CommentUserOut

class CommentsResponse(BaseModel):
    item_id: int
    media_id: str
    comments: list[CommentOut]
    has_next_page: bool
    end_cursor: Optional[str]
    total_fetched: int

@router.get("/{item_id}", response_model=CommentsResponse)
async def get_comments(item_id: int):
    """
    Fetch comments for a media item by opening a real browser session.
    Takes 15-25 seconds. Returns first page (~15 comments).
    """
    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(fetch_comments, item_id),
            timeout=45.0
        )
    except CommentsNotLoadedError as e:
        raise HTTPException(status_code=503, detail=f"Comments not loaded: {e}")
    except CommentFetchError as e:
        raise HTTPException(status_code=500, detail=f"Fetch error: {e}")
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Comment fetch timed out after 45s")

    return CommentsResponse(
        item_id=result.item_id,
        media_id=result.media_id,
        comments=[
            CommentOut(
                pk=c.pk,
                text=c.text,
                created_at=c.created_at,
                comment_like_count=c.comment_like_count,
                child_comment_count=c.child_comment_count,
                has_liked_comment=c.has_liked_comment,
                is_edited=c.is_edited,
                has_gif=c.giphy_media_info is not None,
                user=CommentUserOut(
                    id=c.user.id,
                    username=c.user.username,
                    profile_pic_url=c.user.profile_pic_url,
                    is_verified=c.user.is_verified,
                )
            )
            for c in result.comments
        ],
        has_next_page=result.has_next_page,
        end_cursor=result.end_cursor,
        total_fetched=len(result.comments),
    )
