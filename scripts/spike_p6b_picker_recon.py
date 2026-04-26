#!/usr/bin/env python3
"""
P6b — Emoji picker confirmation spike (READ-ONLY until picker).

Goal: Confirm that clicking the react button ([aria-label*="React"] SVG)
opens the emoji picker dialog. We probe the DOM for picker elements but
NEVER click an emoji. The script stops as soon as the picker is confirmed.

Architecture rule: READS are passive intercepts. WRITES are DOM-clicks only.
This script performs exactly ONE DOM click: on the react button (the SVG).
It does NOT click any emoji. It does NOT send a reaction.
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

import json
import time
import os
import re
import random
import sqlite3
from pathlib import Path
from datetime import datetime

try:
    import camoufox
except ImportError:
    print("ERROR: Camoufox not installed. Run: pip install camoufox[geoip]")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

MEDIA_IMG_SELECTOR = 'img[src*="cdninstagram"][src*="-15/"]'
MSG_LIST_SELECTOR = '[data-pagelet="IGDMessagesList"]'
DB_PATH = "instagram_dm_tracker.db"

PICKER_PROBE_SELECTORS = [
    # Heart emoji (most common reaction)
    '[aria-label="❤"]',
    'button[aria-label="❤"]',
    '[aria-label="❤️"]',
    'button[aria-label="❤️"]',
    # Emoji picker container patterns
    '[role="dialog"]',
    '[role="listbox"]',
    '[role="menu"]',
    '[role="toolbar"]',
    'div[role="toolbar"]',
    # Emoji buttons inside the picker
    '[role="dialog"] button',
    '[role="listbox"] button',
    '[role="menu"] button',
    # Any emoji-labeled element that appeared after clicking react
    '[aria-label*="❤"]',
    '[aria-label="😂"]',
    '[aria-label="😮"]',
    '[aria-label="😢"]',
    '[aria-label="😡"]',
    '[aria-label="🔥"]',
    # Generic: floating UI that appeared after the click
    '[data-visualcompletion="ignore-dynamic"]',
    # Any button with just an emoji as text content
    'button:has-text("❤")',
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_cookies(path="test-cookies/cookies.json"):
    if not os.path.exists(path):
        raise FileNotFoundError(f"Cookies not found at {path}")
    with open(path, "r") as f:
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


def jitter(lo=1.5, hi=3.0):
    d = random.uniform(lo, hi)
    time.sleep(d)
    return d


def check_blockers(page):
    found = []
    checks = [
        ('text=Suspicious Login', 'Suspicious Login'),
        ('text=Checkpoint', 'Checkpoint'),
        ('iframe[src*="captcha"]', 'CAPTCHA'),
        ('text=unusual', 'Unusual activity'),
    ]
    for sel, label in checks:
        try:
            if page.query_selector(sel):
                found.append(label)
        except Exception:
            pass
    return found


def handle_blockers(page, tag="blocker"):
    found = check_blockers(page)
    if not found:
        return False
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    ss = f"artifacts/{tag}_{ts}.png"
    page.screenshot(path=ss)
    report = (
        f"# Blocker — {', '.join(found)}\n\n"
        f"**Time:** {datetime.now().isoformat()}\n"
        f"**Screenshot:** {ss}\n\n"
        f"## Action Required\n"
        f"1. Complete the challenge in the browser window.\n"
        f"2. Re-export cookies if session expired.\n"
    )
    rp = f"artifacts/{tag}_{ts}.md"
    Path(rp).write_text(report, encoding="utf-8")
    print(f"\n[BLOCKER] {', '.join(found)}")
    print(f"  Screenshot: {ss}")
    print(f"  Report:     {rp}")
    return True


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


def lookup_item(item_id_str):
    """Look up an item in the DB by its integer ID. Returns dict or None."""
    if not os.path.exists(DB_PATH):
        print(f"ERROR: DB not found at {DB_PATH}")
        return None

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("""
        SELECT i.id, i.ig_message_id, i.item_type, i.media_url,
               i.poster_handle, i.caption, i.my_existing_reaction,
               i.sender, t.thread_url, t.display_name
        FROM items i
        JOIN threads t ON i.thread_id = t.id
        WHERE i.id = ?
    """, (item_id_str,))
    row = cur.fetchone()
    conn.close()

    if row is None:
        print(f"No item found with id={item_id_str}")
        return None

    return dict(row)


def find_bubble_for_item(page, media_url, scroll_retries=20):
    """
    Find the img element whose src[:80] matches media_url[:80].
    Scrolls the message list container up to load older messages if not
    found in the initial viewport. Returns locator or None.
    """
    prefix = media_url[:80]
    msg_list = page.locator(MSG_LIST_SELECTOR)

    for attempt in range(scroll_retries + 1):
        # Check current viewport
        all_imgs = page.locator(MEDIA_IMG_SELECTOR).all()
        seen_prefixes = set()
        for img in all_imgs:
            try:
                src = img.get_attribute("src") or ""
                seen_prefixes.add(src[:60])
                if src[:80] == prefix:
                    img.scroll_into_view_if_needed()
                    time.sleep(0.5)
                    return img
            except Exception:
                pass

        if attempt == scroll_retries:
            print(f"  Checked {len(seen_prefixes)} unique img srcs across all scrolls")
            break

        # Not found — scroll up to load older messages
        # Find the actual scrollable ancestor of the message list
        print(f"  Scrolling up (attempt {attempt + 1}/{scroll_retries})...", end=" ")
        try:
            # The scrollable container may be a parent, not the pagelet itself.
            # Find it by looking for the element with overflow-y: auto/scroll
            scrollable = page.locator(MSG_LIST_SELECTOR).first.evaluate("""el => {
                let cur = el;
                while (cur && cur !== document.body) {
                    const style = getComputedStyle(cur);
                    if ((style.overflowY === 'auto' || style.overflowY === 'scroll') && cur.scrollHeight > cur.clientHeight) {
                        return { tag: cur.tagName, className: cur.className.substring(0,40), scrollTop: cur.scrollTop, scrollHeight: cur.scrollHeight, clientHeight: cur.clientHeight };
                    }
                    cur = cur.parentElement;
                }
                return null;
            }""")
            if scrollable:
                print(f"found scrollable: {scrollable['tag']} scrollTop={scrollable['scrollTop']}", end=" ")
                msg_list.first.evaluate("""el => {
                    let cur = el;
                    while (cur && cur !== document.body) {
                        const style = getComputedStyle(cur);
                        if ((style.overflowY === 'auto' || style.overflowY === 'scroll') && cur.scrollHeight > cur.clientHeight) {
                            cur.scrollTop = Math.max(0, cur.scrollTop - 600);
                            return;
                        }
                        cur = cur.parentElement;
                    }
                }""")
            else:
                # Fallback: try wheel on the viewport center
                page.mouse.wheel(0, -600)
                print("viewport wheel fallback", end=" ")
            time.sleep(2.5)
            print("done")
        except Exception as e:
            print(f"failed: {e}")
            time.sleep(1.0)

    return None


def scan_picker_dom(page):
    """
    Scan DOM for emoji picker elements. Returns dict of findings.
    """
    results = {}
    for sel in PICKER_PROBE_SELECTORS:
        try:
            loc = page.locator(sel)
            count = loc.count()
            if count > 0:
                visible = False
                snippets = []
                for i in range(min(count, 5)):
                    try:
                        el = loc.nth(i)
                        vis = el.is_visible()
                        html = el.evaluate("el => el.outerHTML")[:200]
                        snippets.append({"visible": vis, "html": html})
                        if vis:
                            visible = True
                    except Exception:
                        pass
                results[sel] = {
                    "count": count,
                    "any_visible": visible,
                    "elements": snippets,
                }
        except Exception:
            pass
    return results


def screenshot(page, path):
    page.screenshot(path=path)
    print(f"  Screenshot: {path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    os.makedirs("artifacts", exist_ok=True)
    print("=" * 65)
    print("P6b — Emoji picker confirmation spike")
    print("Goal: Confirm react button click opens emoji picker")
    print("=" * 65)

    # --- Collect inputs ---
    thread_url = input("\nPaste the IG DM thread URL: ").strip()
    if not thread_url or "instagram.com/direct/t/" not in thread_url:
        print("Invalid URL. Must contain instagram.com/direct/t/")
        sys.exit(1)

    item_id_str = input("Paste the item ID to test (from DB — use one with my_existing_reaction already set): ").strip()
    if not item_id_str.isdigit():
        print("Invalid item ID. Must be an integer.")
        sys.exit(1)

    # --- Look up item in DB ---
    print(f"\nLooking up item {item_id_str} in DB...")
    item = lookup_item(item_id_str)
    if item is None:
        sys.exit(1)

    print(f"  Found: id={item['id']}, type={item['item_type']}, "
          f"poster=@{item['poster_handle']}, sender={item['sender']}")
    print(f"  Existing reaction: {item['my_existing_reaction'] or '(none)'}")
    print(f"  media_url prefix: {item['media_url'][:80]}...")

    if not item.get("my_existing_reaction"):
        print("\n[WARN] This item has no existing reaction.")
        print("If something goes wrong and a reaction fires, it will be a NEW reaction.")
        confirm = input("Continue anyway? (y/n): ").strip().lower()
        if confirm != 'y':
            print("Aborted.")
            sys.exit(0)

    ig_message_id = item["ig_message_id"]
    media_url = item["media_url"]

    findings = {
        "timestamp": datetime.now().isoformat(),
        "thread_url": thread_url,
        "item_id": item["id"],
        "ig_message_id": ig_message_id,
        "item_type": item["item_type"],
        "media_url_prefix": media_url[:80],
        "poster_handle": item["poster_handle"],
        "existing_reaction": item["my_existing_reaction"],
        "db_lookup_ok": True,
        "bubble_found": False,
        "react_button_appeared": False,
        "react_button_aria_label": None,
        "picker_opened": False,
        "picker_findings": {},
        "error": None,
    }

    with camoufox.Camoufox(headless=False) as browser:
        ctx = browser.new_context(viewport={"width": 1528, "height": 794})
        ctx.add_cookies(load_cookies())
        print(f"\nLoaded {len(load_cookies())} cookies")

        page = ctx.new_page()

        # --- Navigate to thread ---
        print("\n[1/6] Navigating to thread...")
        page.goto(thread_url)
        jitter(4.5, 5.5)

        if handle_blockers(page, "p6b_blocker"):
            findings["error"] = "blocker detected"
            browser.close()
            return

        dismiss_popups(page)
        print("  Thread loaded.")

        # --- Wait for messages ---
        print("\n[2/6] Waiting for messages to render...")
        try:
            page.wait_for_selector(MSG_LIST_SELECTOR, timeout=15000)
            print(f"  {MSG_LIST_SELECTOR} is visible.")
        except Exception:
            print("  [WARN] Message list selector not found within timeout.")
        jitter(3, 5)

        # --- Find bubble by CDN URL prefix ---
        print("\n[3/6] Finding bubble by CDN URL prefix match...")
        bubble = find_bubble_for_item(page, media_url)

        if bubble is None:
            print(f"  [STOP] Bubble not found for media_url prefix: {media_url[:80]}")
            print("  The item may not be in the current viewport. Scrolling not yet implemented.")
            screenshot(page, "artifacts/p6b_bubble_not_found.png")
            findings["error"] = "bubble not found in viewport"
            browser.close()
            findings["recommendation"] = (
                "CDN URL prefix matching works but item was not in viewport. "
                "Implement scroll-to-load-more before bubble search."
            )
            output_findings(findings)
            return

        print("  Bubble found via CDN URL prefix match.")
        findings["bubble_found"] = True

        # --- Hover + wait for react button ---
        print("\n[4/6] Hovering bubble, waiting for react button...")
        bubble.scroll_into_view_if_needed()
        time.sleep(0.5)
        bubble.hover()
        time.sleep(3.0)

        # Look for react button
        react_btn = None
        try:
            react_loc = page.locator('[aria-label*="React"]').first
            react_loc.wait_for(state="visible", timeout=4000)
            react_btn = react_loc
            aria = react_btn.get_attribute("aria-label")
            print(f"  React button found: aria-label='{aria}'")
            findings["react_button_appeared"] = True
            findings["react_button_aria_label"] = aria
            findings["react_button_tag"] = react_btn.evaluate("el => el.tagName")
        except Exception as e:
            print(f"  [STOP] React button did not appear after hover. ({e})")
            screenshot(page, "artifacts/p6b_hover_failed.png")
            findings["error"] = "react button did not appear"
            browser.close()
            findings["recommendation"] = (
                "React button did not appear on hover. Possible causes: "
                "item is own message (can't react to self), or IG changed behavior."
            )
            output_findings(findings)
            return

        screenshot(page, "artifacts/p6b_react_btn_visible.png")

        # --- Click react button ---
        print("\n[5/6] Clicking react button (SVG) to open emoji picker...")
        print("  This is the ONLY click we perform. We will NOT click any emoji.")
        try:
            react_btn.click()
            time.sleep(2.0)
        except Exception as e:
            print(f"  [ERROR] Click failed: {e}")
            findings["error"] = f"react button click failed: {e}"
            browser.close()
            output_findings(findings)
            return

        screenshot(page, "artifacts/p6b_picker_state.png")
        print("  Click complete. Scanning for picker...")

        # --- Scan for emoji picker ---
        print("\n[6/6] Scanning DOM for emoji picker elements...")
        picker_results = scan_picker_dom(page)
        findings["picker_findings"] = picker_results

        # Determine if picker opened
        visible_elements = []
        hidden_elements = []
        for sel, data in picker_results.items():
            if data["any_visible"]:
                visible_elements.append(sel)
            else:
                hidden_elements.append(sel)

        findings["picker_opened"] = len(visible_elements) > 0

        print(f"\n  Visible picker elements ({len(visible_elements)}):")
        for sel in visible_elements:
            data = picker_results[sel]
            print(f"    {sel}: count={data['count']}")
            for el in data["elements"]:
                if el["visible"]:
                    print(f"      html: {el['html'][:120]}")

        if hidden_elements:
            print(f"\n  Hidden/absent elements ({len(hidden_elements)}):")
            for sel in hidden_elements:
                data = picker_results[sel]
                print(f"    {sel}: count={data['count']} (none visible)")

        if findings["picker_opened"]:
            print("\n  *** PICKER CONFIRMED OPEN ***")
            print(f"  Working selectors: {visible_elements}")
            print("  STOPPING — not clicking any emoji.")

        browser.close()

    # --- Recommendations ---
    if findings["picker_opened"]:
        findings["recommendation"] = (
            f"Picker opened successfully. Visible selectors: {visible_elements}. "
            f"Next step (P6c): click one of the visible emoji buttons to fire "
            f"IGDirectReactionSendMutation and verify end-to-end. "
            f"Use {visible_elements[0] if visible_elements else '[aria-label=\"❤\"]'} "
            f"as the emoji button selector."
        )
    elif findings["error"] is None:
        findings["recommendation"] = (
            "React button was clicked but no picker elements found in DOM. "
            "Review artifacts/p6b_picker_state.png to manually inspect. "
            "Possible: picker appeared as a native browser element outside the page DOM, "
            "or picker has a different container structure than expected."
        )

    output_findings(findings)


def output_findings(findings):
    path = "artifacts/p6b_spike_findings.json"
    Path(path).write_text(json.dumps(findings, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nFindings written: {path}")

    print("\n" + "=" * 65)
    print("P6b SPIKE COMPLETE")
    print(f"  Bubble found:     {findings.get('bubble_found', False)}")
    print(f"  React button:     {findings.get('react_button_appeared', False)}")
    print(f"  Picker opened:    {findings.get('picker_opened', False)}")
    print(f"  Error:            {findings.get('error') or '(none)'}")
    if findings.get("react_button_aria_label"):
        print(f"  React btn label:  {findings['react_button_aria_label']}")
    visible = [s for s, d in findings.get("picker_findings", {}).items() if d.get("any_visible")]
    if visible:
        print(f"  Picker selectors: {visible}")
    print(f"  Zero reactions fired. Zero emojis clicked.")
    print("=" * 65)


if __name__ == "__main__":
    main()
