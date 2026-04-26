"""Reactor API endpoint — trigger reactions to DM messages via DOM-click."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator
from pathlib import Path

router = APIRouter(prefix="/reactor", tags=["reactor"])


class ReactRequest(BaseModel):
    """Request to send a reaction to a DM message."""
    item_id: int = Field(..., description="Database ID of the item to react to")
    emoji: str = Field(default="❤", description="Single emoji character to send")
    dry_run: bool = Field(default=False, description="If true, log intent but do not open browser")

    @field_validator("emoji")
    @classmethod
    def validate_emoji(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("emoji must not be empty")
        if len(v) > 2:
            raise ValueError("emoji must be a single emoji character (max 2 chars)")
        return v

    @field_validator("item_id")
    @classmethod
    def validate_item_id(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("item_id must be positive")
        return v


@router.post("/react")
def send_reaction_endpoint(request: ReactRequest):
    """Send a reaction to an Instagram DM message via DOM-click.

    Opens a real browser, navigates to the thread, finds the message
    bubble, hovers to reveal the react button, opens the emoji picker,
    and clicks the heart emoji. Takes 30-60 seconds.

    Returns status info and confirmation of the fired mutation.
    """
    db_path = "instagram_dm_tracker.db"
    cookies_path = str(Path("test-cookies/cookies.json").absolute())

    from reactor.reactor import send_reaction

    result = send_reaction(
        item_id=request.item_id,
        emoji=request.emoji,
        db_path=db_path,
        cookies_path=cookies_path,
        dry_run=request.dry_run,
    )

    status = result.get("status", "error")

    if status == "success":
        return result

    if status in ("already_reacted", "dry_run"):
        return result

    if status == "error":
        reason = result.get("reason", "unknown")
        if reason == "item_not_found":
            raise HTTPException(status_code=404, detail=f"Item {request.item_id} not found")
        if reason in ("bubble_not_found", "react_button_not_found", "emoji_not_found_in_picker"):
            raise HTTPException(status_code=422, detail=result)
        if reason == "blocker_detected":
            raise HTTPException(status_code=500, detail="Instagram blocker detected during reaction")
        if reason == "mutation_not_confirmed":
            raise HTTPException(status_code=502, detail=result)
        raise HTTPException(status_code=500, detail=result)

    return result
