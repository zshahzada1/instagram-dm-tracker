"""React to Instagram DM messages via DOM-click.

Architecture rule: NEVER POST to /api/graphql. Reactions fire because
Playwright clicks the real IG UI. Captured mutations are for verification only.
"""

import json
import os
import random
import re
import sys
import io
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Any

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

try:
    import camoufox
except ImportError:
    print("ERROR: Camoufox is not installed!")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Timing constants (do not deviate)
# ---------------------------------------------------------------------------

HOVER_WAIT = 3.0
REACT_BTN_TIMEOUT = 4000  # ms
PICKER_WAIT = 2.0
MUTATION_WAIT = 6.0
SCROLL_PAUSE = 1.5
MAX_SCROLL_ATTEMPTS = 20

# ---------------------------------------------------------------------------
# Selectors (confirmed from P6a and P6b spikes)
# ---------------------------------------------------------------------------

MEDIA_IMG_SELECTOR = 'img[src*="cdninstagram"][src*="-15/"]'
MSG_LIST_SELECTOR = '[data-pagelet="IGDMessagesList"]'
REACT_BTN_SELECTOR = '[aria-label*="React"]'

PICKER_CONTAINER = '[role="dialog"]'

# Emoji button probes inside picker (tried in order, first visible match wins)
HEART_PROBES = [
    '[role="dialog"] [aria-label="{emoji}"]',
    '[role="dialog"] [aria-label*="{emoji}"]',
    '[role="dialog"] [role="button"]:first-child',
    '[role="dialog"] div[role="button"]:first-child',
    '[role="dialog"] span[role="button"]:first-child',
    '[role="dialog"] button:first-child',
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _jitter(base: float, delta: float = 0.3) -> float:
    d = base + random.uniform(-delta, delta)
    time.sleep(d)
    return d


def load_cookies(path: str) -> list:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Cookies not found at {path}")
    with open(path) as f:
        raw = json.load(f)
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
    return out


def check_blockers(page):
    for sel, label in [
        ('text=Suspicious Login', 'Suspicious Login'),
        ('text=Checkpoint', 'Checkpoint'),
        ('iframe[src*="captcha"]', 'CAPTCHA'),
        ('text=unusual', 'Unusual activity'),
    ]:
        try:
            if page.query_selector(sel):
                return label
        except Exception:
            pass
    return None


def dismiss_popups(page):
    for selector in ['button:has-text("Not Now")', '[aria-label="Close"]']:
        try:
            el = page.query_selector(selector)
            if el and el.is_visible():
                el.click()
                time.sleep(0.8)
        except Exception:
            pass
    try:
        page.keyboard.press("Escape")
        time.sleep(0.5)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------

def find_bubble(page, media_url: str):
    """Find the img element whose src[:80] matches media_url[:80].

    Scrolls the message list up to MAX_SCROLL_ATTEMPTS times to load older
    messages if not found in the initial viewport. Returns locator or None.
    """
    prefix = media_url[:80]

    for attempt in range(MAX_SCROLL_ATTEMPTS + 1):
        all_imgs = page.locator(MEDIA_IMG_SELECTOR).all()
        for img in all_imgs:
            try:
                src = img.get_attribute("src") or ""
                if src[:80] == prefix:
                    img.scroll_into_view_if_needed()
                    time.sleep(0.5)
                    return img
            except Exception:
                pass

        if attempt == MAX_SCROLL_ATTEMPTS:
            break

        # Scroll up to load older messages
        try:
            page.mouse.wheel(0, -600)
            _jitter(SCROLL_PAUSE)
        except Exception:
            time.sleep(1.0)

    return None


def find_heart_in_picker(page, emoji: str):
    """Dump picker DOM, then probe for emoji button. Returns locator or None."""
    os.makedirs("artifacts", exist_ok=True)

    # Dump picker innerHTML for diagnostics
    try:
        html = page.locator(PICKER_CONTAINER).first.inner_html()
        Path("artifacts/p6c_picker_dom.html").write_text(html, encoding="utf-8")
        print(f"  Picker DOM dumped: artifacts/p6c_picker_dom.html ({len(html)} chars)")
    except Exception as e:
        print(f"  [WARN] Could not dump picker DOM: {e}")

    # Probe selectors in order
    for sel_template in HEART_PROBES:
        sel = sel_template.format(emoji=emoji)
        try:
            loc = page.locator(sel).first
            loc.wait_for(state="visible", timeout=2000)
            aria = None
            try:
                aria = loc.get_attribute("aria-label")
            except Exception:
                pass
            tag = loc.evaluate("el => el.tagName")
            print(f"  Heart button found: selector='{sel}' tag={tag} aria-label={aria}")
            return loc
        except Exception:
            continue

    print(f"  [WARN] No heart button found with any probe selector")
    return None


def send_reaction(
    item_id: int,
    emoji: str,
    db_path: str = "instagram_dm_tracker.db",
    cookies_path: str = "test-cookies/cookies.json",
    dry_run: bool = False,
) -> dict:
    """Send a reaction to a DM message via DOM-click on the real IG UI."""

    # --- 1. Look up item in DB ---
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("""
        SELECT i.id, i.ig_message_id, i.item_type, i.media_url,
               i.poster_handle, i.my_existing_reaction, i.my_auto_sent_reaction,
               i.sender, t.thread_url, t.ig_thread_id, t.display_name
        FROM items i
        JOIN threads t ON i.thread_id = t.id
        WHERE i.id = ?
    """, (item_id,))
    row = cur.fetchone()
    conn.close()

    if row is None:
        return {"status": "error", "reason": "item_not_found", "item_id": item_id}

    item = dict(row)

    # --- 2. Already reacted? ---
    if item.get("my_existing_reaction") == emoji:
        return {"status": "already_reacted", "emoji": emoji, "skipped": True,
                "item_id": item_id, "source": "my_existing_reaction"}
    if item.get("my_auto_sent_reaction") == emoji:
        return {"status": "already_reacted", "emoji": emoji, "skipped": True,
                "item_id": item_id, "source": "my_auto_sent_reaction"}

    if dry_run:
        return {"status": "dry_run", "would_react_with": emoji, "item_id": item_id,
                "poster_handle": item["poster_handle"],
                "ig_message_id": item["ig_message_id"]}

    # --- 3. Open browser ---
    thread_url = item["thread_url"]
    ig_message_id = item["ig_message_id"]
    media_url = item["media_url"]
    poster_handle = item["poster_handle"]

    print(f"\n{'='*60}")
    print(f"P6c REACTOR: item_id={item_id}  emoji={emoji}")
    print(f"  poster=@{poster_handle}  ig_message_id={ig_message_id}")
    print(f"  thread_url={thread_url}")
    print(f"{'='*60}")

    captured_mutations = []

    def on_request(request):
        try:
            if request.url and "graphql" in request.url:
                post_data = request.post_data or ""
                if "IGDirectReactionSendMutation" in post_data:
                    captured_mutations.append({
                        "source": "request",
                        "friendly_name": "IGDirectReactionSendMutation",
                        "url": request.url[:120],
                    })
                    print(f"  [NETWORK] REQUEST: IGDirectReactionSendMutation intercepted", flush=True)
        except Exception:
            pass

    def on_response(response):
        try:
            if response.url and "graphql" in response.url:
                # Capture any graphql response that comes after our reaction click
                body_snippet = ""
                try:
                    body_snippet = response.text()[:500]
                except Exception:
                    pass
                captured_mutations.append({
                    "source": "response",
                    "status": response.status,
                    "url": response.url[:120],
                    "body_snippet": body_snippet,
                })
                if response.status == 200 and body_snippet:
                    print(f"  [NETWORK] RESPONSE: HTTP 200, body={body_snippet[:120]}")
        except Exception:
            pass

    with camoufox.Camoufox(headless=False) as browser:
        ctx = browser.new_context(viewport={"width": 1528, "height": 794})
        ctx.add_cookies(load_cookies(cookies_path))
        page = ctx.new_page()
        page.on("request", on_request)
        page.on("response", on_response)

        # Navigate
        print("\n[1] Navigating to thread...")
        page.goto(thread_url)
        _jitter(5.0, 0.5)

        if check_blockers(page):
            ctx.close()
            return {"status": "error", "reason": "blocker_detected"}

        dismiss_popups(page)

        try:
            page.wait_for_selector(MSG_LIST_SELECTOR, timeout=15000)
        except Exception:
            pass
        _jitter(4.0, 1.0)

        # Find bubble
        print("\n[2] Finding bubble by CDN URL prefix...")
        bubble = find_bubble(page, media_url)
        if bubble is None:
            ctx.close()
            return {"status": "error", "reason": "bubble_not_found",
                    "media_url_prefix": media_url[:80]}

        print(f"  Bubble found.")

        # Hover bubble
        print("\n[3] Hovering bubble...")
        bubble.scroll_into_view_if_needed()
        time.sleep(0.5)
        bubble.hover()
        _jitter(HOVER_WAIT)

        # Find react button
        print("\n[4] Finding react button...")
        react_btn = None
        try:
            react_loc = page.locator(REACT_BTN_SELECTOR).first
            react_loc.wait_for(state="visible", timeout=REACT_BTN_TIMEOUT)
            react_btn = react_loc
            aria = react_btn.get_attribute("aria-label")
            print(f"  React button: aria-label='{aria}' tag={react_btn.evaluate('el => el.tagName')}")
        except Exception as e:
            ctx.close()
            return {"status": "error", "reason": "react_button_not_found",
                    "detail": str(e)[:200]}

        # Click react button
        print("\n[5] Clicking react button to open picker...")
        react_btn.click()
        _jitter(PICKER_WAIT)

        # Find heart in picker
        print("\n[6] Finding heart emoji in picker...")
        heart_btn = find_heart_in_picker(page, emoji)

        if heart_btn is None:
            page.keyboard.press("Escape")
            ctx.close()
            return {"status": "error", "reason": "emoji_not_found_in_picker",
                    "emoji": emoji, "picker_dom": "artifacts/p6c_picker_dom.html"}

        # CATASTROPHIC FAILURE CHECKLIST
        print("\n[7] Pre-flight catastrophe check:")
        print(f"  1. Bubble CDN prefix matched: YES")
        print(f"  2. React button aria-label confirmed above")
        print(f"  3. Heart button is inside [role='dialog']")
        print(f"  FIRING REACTION: item_id={item_id}, ig_message_id={ig_message_id}, emoji={emoji}")

        # Click heart
        print("\n[8] Clicking heart emoji...")
        heart_btn.click()
        _jitter(MUTATION_WAIT)

        ctx.close()

    # --- Verify mutation ---
    print(f"\n[9] Verifying mutation capture...")
    print(f"  Total captured: {len(captured_mutations)}")
    for m in captured_mutations:
        src = m.get("source", "?")
        st = m.get("status", m.get("friendly_name", "?"))
        print(f"    [{src}] {st}")

    mutation_requested = any(
        m.get("friendly_name") == "IGDirectReactionSendMutation"
        for m in captured_mutations
    )
    mutation_200 = any(
        m.get("source") == "response" and m.get("status") == 200
        for m in captured_mutations
    )
    confirmed = mutation_requested and mutation_200

    if confirmed:
        conn = sqlite3.connect(db_path)
        conn.execute(
            "UPDATE items SET my_auto_sent_reaction = ?, updated_at = ? WHERE id = ?",
            (emoji, datetime.now(timezone.utc).isoformat(), item_id),
        )
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE items SET watched=1, updated_at=datetime('now') WHERE id=?",
            (item_id,)
        )
        conn.commit()
        conn.close()
        print(f"  DB updated: my_auto_sent_reaction = '{emoji}' for item {item_id}")
        return {"status": "success", "emoji": emoji, "message_id": ig_message_id,
                "mutation_confirmed": True, "item_id": item_id}
    else:
        response_statuses = [m["status"] for m in captured_mutations if m.get("source") == "response"]
        print(f"  Mutation NOT confirmed. request_seen={mutation_requested}, response_statuses={response_statuses}")
        return {"status": "error", "reason": "mutation_not_confirmed",
                "http_statuses": response_statuses or "none",
                "captured_count": len(captured_mutations),
                "mutation_requested": mutation_requested,
                "mutation_200": mutation_200}
