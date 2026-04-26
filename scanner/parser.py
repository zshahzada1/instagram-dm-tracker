"""Parse Instagram DM message nodes into media item data."""
import re
import json
from datetime import datetime, timezone


def extract_shortcode(target_url: str) -> str | None:
    """
    Extract Instagram media shortcode from target URL.

    Args:
        target_url: The Instagram media URL (reel, post, or carousel)

    Returns:
        The shortcode string or None if not found.
    """
    reel_match = re.search(r'/reel/([^/?]+)', target_url)
    if reel_match:
        return reel_match.group(1)

    post_match = re.search(r'/p/([^/?]+)', target_url)
    if post_match:
        return post_match.group(1)

    return None


def parse_message_node(node: dict, viewer_interop_id: str) -> dict | None:
    """
    Parse a message node into a media item dict, or return None for unsupported types.

    Args:
        node: A message node from IGDThreadDetailMainViewContainerQuery response
        viewer_interop_id: The viewer's interop_messaging_user_fbid

    Returns:
        A dict with parsed item data, or None for unsupported message types.
    """
    message_id = node.get("message_id")
    if not message_id or not message_id.startswith("mid.$"):
        return None

    content_type = node.get("content_type")
    content = node.get("content") or {}
    sender_fbid = node.get("sender_fbid")
    timestamp_ms = node.get("timestamp_ms")

    if not timestamp_ms:
        return None

    try:
        sent_at = datetime.fromtimestamp(int(timestamp_ms) / 1000, tz=timezone.utc).isoformat()
    except (ValueError, TypeError):
        return None

    sender = 'me' if sender_fbid == viewer_interop_id else 'her'

    reactions = node.get("reactions", [])
    my_existing_reaction = None
    for r in reactions:
        if r.get("sender_fbid") == viewer_interop_id:
            my_existing_reaction = r.get("reaction")
            break

    item_type = None
    media_shortcode = None
    poster_handle = None
    caption = None
    media_url = None

    xma = (content.get("xma") or {}) if content.get("__typename") == "SlideMessageXMAContent" else {}

    if content_type == "MESSAGE_INLINE_SHARE":
        xma_typename = xma.get("__typename")

        if xma_typename == "SlideMessagePortraitXMA":
            target_url = xma.get("target_url", "")
            if "/reel/" in target_url:
                item_type = "reel"
                media_shortcode = extract_shortcode(target_url)
                poster_handle = xma.get("xmaHeaderTitle")
                preview = xma.get("xmaPreviewImage") or {}
                media_url = preview.get("url")

        elif xma_typename == "SlideMessageStandardXMA":
            target_url = xma.get("target_url", "")
            preview = xma.get("xmaPreviewImage") or {}
            if "carousel_share_child_media_id" in target_url:
                item_type = "carousel"
                media_shortcode = extract_shortcode(target_url)
                poster_handle = xma.get("xmaHeaderTitle")
                caption = xma.get("xmaTitle")
                media_url = preview.get("url")
            else:
                item_type = "post"
                media_shortcode = extract_shortcode(target_url)
                poster_handle = xma.get("xmaHeaderTitle")
                caption = xma.get("xmaTitle")
                media_url = preview.get("url")

    elif content_type == "MONTAGE_SHARE_XMA":
        item_type = "story"
        target_url = xma.get("target_url", "")
        media_shortcode = extract_shortcode(target_url)
        poster_handle = xma.get("xmaHeaderTitle")
        preview = xma.get("xmaPreviewImage") or {}
        media_url = preview.get("url")

    if item_type is None:
        return None

    if not media_url:
        return None

    caption_snippet = caption[:30] if caption else None
    dom_fingerprint = json.dumps({
        "timestamp_ms": timestamp_ms,
        "poster_handle": poster_handle,
        "caption_snippet": caption_snippet
    })

    return {
        "ig_message_id": message_id,
        "item_type": item_type,
        "media_shortcode": media_shortcode,
        "media_url": media_url,
        "poster_handle": poster_handle,
        "caption": caption,
        "sent_at": sent_at,
        "sender": sender,
        "my_existing_reaction": my_existing_reaction,
        "dom_fingerprint": dom_fingerprint,
    }
