import json
import time
import random
import sqlite3
from pathlib import Path
from urllib.parse import parse_qs
from dataclasses import dataclass
from typing import Optional

from camoufox.sync_api import Camoufox

DB_PATH = Path("instagram_dm_tracker.db")
COOKIES_PATH = Path("test-cookies/cookies.json")
TARGET_QUERY = "PolarisPostCommentsContainerQuery"

class CommentsNotLoadedError(Exception):
    pass

class CommentFetchError(Exception):
    pass

@dataclass
class CommentUser:
    id: str
    username: str
    profile_pic_url: str
    is_verified: bool

@dataclass
class Comment:
    pk: str
    text: str
    created_at: int
    comment_like_count: int
    child_comment_count: int
    has_liked_comment: bool
    is_edited: bool
    giphy_media_info: Optional[dict]
    user: CommentUser

@dataclass
class CommentsResult:
    item_id: int
    media_id: str
    comments: list[Comment]
    has_next_page: bool
    end_cursor: Optional[str]
    comment_count_total: Optional[int]

def _jitter(base: float) -> float:
    return base + random.uniform(0.5, 1.5)

def _load_cookies(context):
    raw = json.loads(COOKIES_PATH.read_text())
    out = []
    for c in raw:
        conv = {
            "name": c["name"], "value": c["value"],
            "domain": c["domain"], "path": c["path"],
            "httpOnly": c.get("httpOnly", False),
            "secure": c.get("secure", True),
        }
        if c.get("expirationDate"):
            conv["expires"] = int(c["expirationDate"])
        ss = c.get("sameSite", "unspecified")
        conv["sameSite"] = {
            "no_restriction": "None", "none": "None",
            "lax": "Lax", "strict": "Strict",
        }.get(ss, "None")
        out.append(conv)
    context.add_cookies(out)

def _parse_comment(node: dict) -> Comment:
    u = node.get('user') or {}
    return Comment(
        pk=node['pk'],
        text=node.get('text', ''),
        created_at=node.get('created_at', 0),
        comment_like_count=node.get('comment_like_count', 0),
        child_comment_count=node.get('child_comment_count', 0),
        has_liked_comment=node.get('has_liked_comment', False),
        is_edited=node.get('is_edited', False),
        giphy_media_info=node.get('giphy_media_info'),
        user=CommentUser(
            id=u.get('id', ''),
            username=u.get('username', ''),
            profile_pic_url=u.get('profile_pic_url', ''),
            is_verified=u.get('is_verified', False),
        )
    )

def fetch_comments(item_id: int) -> CommentsResult:
    # Look up item
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT media_shortcode, item_type, media_id FROM items WHERE id=?",
            (item_id,)
        ).fetchone()
    if not row:
        raise CommentFetchError(f"Item {item_id} not found in DB")
    shortcode, item_type, cached_media_id = row
    if not shortcode:
        raise CommentFetchError(f"Item {item_id} has no media_shortcode")

    url_type = "reel" if item_type == "reel" else "p"
    target_url = f"https://www.instagram.com/{url_type}/{shortcode}/"

    captured = []
    all_queries = []

    def handle_response(response):
        if 'instagram.com' not in response.url:
            return
        if '/api/graphql' not in response.url:
            return
        if response.request.method != 'POST':
            return
        try:
            # Try to get post_data, but handle errors gracefully
            post_data = None
            try:
                post_data = response.request.post_data
                if post_data and isinstance(post_data, bytes):
                    post_data = post_data.decode('utf-8', errors='replace')
            except Exception:
                pass

            friendly_name = ''
            if post_data:
                try:
                    parsed = parse_qs(post_data)
                    friendly_name = (parsed.get('fb_api_req_friendly_name') or [''])[0]
                except Exception:
                    pass

            all_queries.append(friendly_name or '(no name)')

            # Try to capture the response body immediately
            try:
                body = response.body()
                if body:
                    response_json = json.loads(body.decode('utf-8', errors='replace'))

                    # Check if this is our target query by looking at the response structure
                    if friendly_name == TARGET_QUERY:
                        variables = {}
                        if post_data:
                            try:
                                parsed = parse_qs(post_data)
                                variables_raw = (parsed.get('variables') or ['{}'])[0]
                                variables = json.loads(variables_raw)
                            except Exception:
                                pass
                        captured.append({'variables': variables, 'response': response_json})
                        print(f"DEBUG: Successfully captured {TARGET_QUERY}")
            except Exception as e:
                print(f"DEBUG: Error parsing response body: {e}")
        except Exception as e:
            print(f"DEBUG: Error in response handler: {e}")
            import traceback
            traceback.print_exc()

    with Camoufox(headless=False) as browser:
        context = browser.new_context(viewport={'width': 1280, 'height': 900})
        _load_cookies(context)
        page = context.new_page()
        page.on('response', handle_response)

        page.goto(target_url, wait_until='domcontentloaded', timeout=30000)
        time.sleep(_jitter(6.0))

        # Click comment button — ONLY [aria-label="Comment"], never Like
        try:
            btn = page.locator('[aria-label="Comment"]').first
            btn.wait_for(timeout=15000)
            btn.click()
        except Exception as e:
            page.close()
            raise CommentsNotLoadedError(f"Comment button not found: {e}")

        # Wait for query to fire
        deadline = time.time() + 20.0
        while time.time() < deadline and not captured:
            time.sleep(0.5)

        # Wait a bit more for any pending responses to be processed
        time.sleep(2.0)

        page.close()

    print(f"DEBUG: All queries captured: {all_queries}")
    print(f"DEBUG: Looking for: {TARGET_QUERY}")
    print(f"DEBUG: Captured array length: {len(captured)}")
    if captured:
        print(f"DEBUG: Captured keys: {captured[0].keys()}")

    if not captured:
        raise CommentsNotLoadedError("PolarisPostCommentsContainerQuery not captured within timeout")

    call = captured[0]
    media_id = call['variables'].get('media_id', cached_media_id or '')

    # Cache media_id if we got it and didn't have it
    if media_id and not cached_media_id:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                "UPDATE items SET media_id=?, updated_at=datetime('now') WHERE id=?",
                (media_id, item_id)
            )

    # Parse response
    try:
        connection = (
            call['response']
            .get('data', {})
            .get('xdt_api__v1__media__media_id__comments__connection', {})
        )
        edges = connection.get('edges', [])
        page_info = connection.get('page_info', {})
        comments = [_parse_comment(e['node']) for e in edges if 'node' in e]
    except Exception as e:
        raise CommentFetchError(f"Failed to parse response: {e}")

    return CommentsResult(
        item_id=item_id,
        media_id=media_id,
        comments=comments,
        has_next_page=page_info.get('has_next_page', False),
        end_cursor=page_info.get('end_cursor'),
        comment_count_total=None,  # available from PolarisClipsDesktopCommentsPopoverQuery if needed
    )
