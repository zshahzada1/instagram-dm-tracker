#!/usr/bin/env python3
"""
Prompt 2.75 — DOM-click reaction spike.

Architecture rule: READS are passive intercepts. WRITES are DOM-clicks only.
This script proves the hover → smiley → emoji DOM-click path works end-to-end.
We never construct or POST to /api/graphql ourselves.

Guardrails:
- Headed browser only (visible window).
- Exactly ONE reaction on ONE user-chosen message.
- No messages sent. No page.evaluate() that posts anything.
- Jittered 1.5-3s delays. 3-5s settle after navigation.
- Checkpoint/captcha → screenshot + blocker report, stop.
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

import json
import time
import os
import re
import random
from pathlib import Path
from datetime import datetime
from urllib.parse import parse_qs

try:
    import camoufox
except ImportError:
    print("ERROR: Camoufox not installed. Run: pip install camoufox[geoip]")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def jitter(lo=1.5, hi=3.0):
    d = random.uniform(lo, hi)
    time.sleep(d)
    return d


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


def check_blockers(page):
    checks = [
        ('text=Suspicious Login', 'Suspicious Login'),
        ('text=Checkpoint', 'Checkpoint'),
        ('iframe[src*="captcha"]', 'CAPTCHA'),
        ('text=unusual', 'Unusual activity'),
    ]
    found = []
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
            if el:
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
# Network capture (passive — only to verify mutation fired after DOM-click)
# ---------------------------------------------------------------------------

class ReactionCapture:
    """Captures only IGDirectReactionSendMutation calls."""

    def __init__(self):
        self.entries = []

    def on_request(self, request):
        if "/api/graphql" not in request.url:
            return
        post = request.post_data or ""
        parsed = parse_qs(post)
        name = (parsed.get("fb_api_req_friendly_name") or [""])[0]
        if "Reaction" not in name and "reaction" not in name.lower():
            return
        doc_id = (parsed.get("doc_id") or [""])[0]
        try:
            variables = json.loads((parsed.get("variables") or ["{}"])[0])
        except Exception:
            variables = {}
        self.entries.append({
            "timestamp": datetime.now().isoformat(),
            "friendly_name": name,
            "doc_id": doc_id,
            "variables": variables,
            "response_status": None,
            "response_body": None,
            "_request_url": request.url,
        })

    def on_response(self, response):
        if "/api/graphql" not in response.url:
            return
        # Match to last unmatched entry
        for entry in reversed(self.entries):
            if entry.get("response_status") is None:
                entry["response_status"] = response.status
                try:
                    body = response.body()
                    entry["response_body"] = json.loads(body.decode("utf-8", errors="replace"))
                except Exception:
                    pass
                break

    def save(self, path="artifacts/recon_reaction_domclick.json"):
        out = {
            "captured_at": datetime.now().isoformat(),
            "total_reaction_calls": len(self.entries),
            "entries": self.entries,
        }
        Path(path).write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
        return path


# ---------------------------------------------------------------------------
# DOM helpers
# ---------------------------------------------------------------------------

def find_message_bubbles(page):
    """
    Return list of Playwright locators for message bubbles in the thread.

    Strategy (in priority order):
      1. Children of [data-pagelet="IGDMessagesList"] that contain an <img> or
         an <a href="/reel/"> or an <a href="/p/"> link — these are shared media.
      2. Fallback: all direct children of the messages list that are visible divs.

    Returns a list of (index, locator, description) tuples.
    """
    msg_list = page.locator('[data-pagelet="IGDMessagesList"]')
    if not msg_list.count():
        print("  [WARN] IGDMessagesList pagelet not found — trying full page fallback")
        msg_list = page.locator("body")

    # Strategy 1: containers with a thumbnail image (shared reels/posts render a preview img)
    # IG uses <a class="_a6hd"> or similar for the media link; the img is a sibling/child
    # Look for any div that directly wraps an <img> with a cdninstagram src
    bubbles = []

    # Try: any element inside the messages list that has a descendant img with cdninstagram
    all_imgs = msg_list.locator("img[src*='cdninstagram']").all()
    seen_parents = []
    for img in all_imgs:
        try:
            # Walk up to find the "bubble" — a div that's a direct child or grandchild of the list
            # We use the bounding box to group images that are close together
            box = img.bounding_box()
            if not box or box["height"] < 50:  # skip tiny profile pics
                continue
            # The bubble parent: go up 3 levels from img
            # (img → div.overlay → div.image-container → div.bubble)
            # We'll use nth-of-type matching on the image itself as the anchor
            bubbles.append(img)
        except Exception:
            pass

    if not bubbles:
        print("  [INFO] No cdninstagram images found — falling back to all visible children")
        try:
            # All direct children of the message list area
            children = msg_list.locator("> div > div > div").all()
            bubbles = [c for c in children if c.is_visible()]
        except Exception:
            pass

    return bubbles


def describe_bubble(bubble, index):
    """Try to produce a text description of a message bubble for user identification."""
    desc_parts = []
    try:
        box = bubble.bounding_box()
        if box:
            desc_parts.append(f"at y={int(box['y'])}, size={int(box['width'])}x{int(box['height'])}")
    except Exception:
        pass
    try:
        src = bubble.get_attribute("src") or ""
        if "cdninstagram" in src:
            # Extract cache key from URL
            m = re.search(r"ig_cache_key=([^&]{6,30})", src)
            if m:
                desc_parts.append(f"cache_key={m.group(1)[:12]}...")
    except Exception:
        pass
    return f"Image #{index+1}: " + (", ".join(desc_parts) if desc_parts else "(no details)")


def hover_and_react(page, bubble, capture, emoji="❤"):
    """
    Perform the full DOM-click reaction sequence:
      1. Hover over the message bubble.
      2. Wait for the reaction action bar to appear.
      3. Click the smiley/emoji react button.
      4. Wait for emoji picker.
      5. Click the target emoji.

    Logs every step. Returns True if emoji was clicked.
    """
    print("\n[REACT] Step 1/5 — Hovering over message bubble...")
    try:
        bubble.scroll_into_view_if_needed()
        time.sleep(0.5)
        bubble.hover()
    except Exception as e:
        print(f"  [ERROR] Hover failed: {e}")
        return False

    jitter(1.5, 2.5)
    print("  Hover complete.")

    # Step 2: Wait for reaction action bar
    print("[REACT] Step 2/5 — Waiting for reaction bar to appear...")
    # IG reaction bar appears as a floating element near the message
    # Look for: button with emoji face SVG, or aria-label containing React/emoji
    react_btn = None
    react_selectors = [
        # aria-label patterns (most stable)
        '[aria-label="React to message"]',
        'button[aria-label*="React"]',
        'button[aria-label*="react"]',
        # SVG title patterns
        'button:has(svg > title:text("React"))',
        'button:has(svg[aria-label="React to message"])',
        # Emoji face icon (smiley face path characteristic)
        'button:has(svg path[d*="11.99 2C6.47 2"])',  # common smiley path
        # Fallback: any button that appears only after hover in a floating bar
        '[role="toolbar"] button:first-child',
        'div[role="toolbar"] button',
    ]

    for sel in react_selectors:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=2000):
                react_btn = el
                print(f"  Found react button via: {sel}")
                break
        except Exception:
            pass

    if react_btn is None:
        print("  [WARN] React button not found via aria/role selectors.")
        print("         Trying screenshot + manual confirmation...")
        page.screenshot(path="artifacts/spike_react_hover_state.png")
        print("  Screenshot saved: artifacts/spike_react_hover_state.png")
        print("  Inspect the screenshot to identify the reaction button.")
        confirm = input("\n  Type the CSS selector for the react smiley button, or 'skip' to abort: ").strip()
        if not confirm or confirm.lower() == "skip":
            return False
        try:
            react_btn = page.locator(confirm).first
        except Exception as e:
            print(f"  [ERROR] Could not use selector '{confirm}': {e}")
            return False

    jitter(0.8, 1.5)

    # Step 3: Click the react button
    print("[REACT] Step 3/5 — Clicking react smiley button...")
    try:
        react_btn.click()
    except Exception as e:
        print(f"  [ERROR] Click on react button failed: {e}")
        return False

    jitter(1.0, 2.0)
    print("  Clicked.")

    # Step 4: Wait for emoji picker
    print("[REACT] Step 4/5 — Waiting for emoji picker...")
    picker_selectors = [
        f'[aria-label="{emoji}"]',
        f'button[aria-label="{emoji}"]',
        f'[role="dialog"] button:has-text("{emoji}")',
        f'[role="listbox"] [aria-label="{emoji}"]',
        # Positional fallback: first emoji in the picker row
        '[role="dialog"] button:first-child',
        '[role="listbox"] button:first-child',
        # Generic: any button containing the emoji character
        f'button:has-text("{emoji}")',
    ]

    emoji_btn = None
    for sel in picker_selectors:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=3000):
                emoji_btn = el
                print(f"  Found emoji button via: {sel}")
                break
        except Exception:
            pass

    if emoji_btn is None:
        print("  [WARN] Emoji picker not found via selectors.")
        page.screenshot(path="artifacts/spike_react_picker_state.png")
        print("  Screenshot saved: artifacts/spike_react_picker_state.png")
        confirm = input(f"\n  Type CSS selector for the '{emoji}' emoji button, or 'skip': ").strip()
        if not confirm or confirm.lower() == "skip":
            return False
        try:
            emoji_btn = page.locator(confirm).first
        except Exception as e:
            print(f"  [ERROR] {e}")
            return False

    jitter(0.5, 1.0)

    # Step 5: Click the emoji
    print(f"[REACT] Step 5/5 — Clicking {emoji} emoji...")
    try:
        emoji_btn.click()
    except Exception as e:
        print(f"  [ERROR] Emoji click failed: {e}")
        return False

    print(f"  Clicked {emoji}.")
    return True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    os.makedirs("artifacts", exist_ok=True)
    print("=" * 65)
    print("Prompt 2.75 — DOM-click reaction spike")
    print("Architecture: reads=passive intercept | writes=DOM-click only")
    print("=" * 65)

    thread_url = input("\nPaste DM thread URL (instagram.com/direct/t/...): ").strip()
    if not thread_url or "instagram.com/direct/t/" not in thread_url:
        print("Invalid URL. Must contain instagram.com/direct/t/")
        sys.exit(1)

    capture = ReactionCapture()

    with camoufox.Camoufox(headless=False) as browser:
        ctx = browser.new_context(
            viewport={"width": 1528, "height": 794},
        )
        ctx.add_cookies(load_cookies())
        print(f"Loaded {len(load_cookies())} cookies")

        page = ctx.new_page()

        # Install passive network listener
        page.on("request", capture.on_request)
        page.on("response", capture.on_response)

        # Step 1: Inbox
        print("\n[1/6] Navigating to inbox...")
        page.goto("https://www.instagram.com/direct/inbox/")
        jitter(3.5, 4.5)
        if handle_blockers(page, "blocker_inbox"):
            browser.close()
            return
        dismiss_popups(page)
        print("  Inbox loaded.")

        # Step 2: Thread
        print(f"\n[2/6] Navigating to thread...")
        page.goto(thread_url)
        jitter(4.5, 5.5)
        if handle_blockers(page, "blocker_thread"):
            browser.close()
            return
        dismiss_popups(page)
        print("  Thread loaded.")

        # Step 3: Let thread fully render
        print("\n[3/6] Waiting for messages to render (8-10s)...")
        jitter(8, 10)

        # Step 4: Find message bubbles
        print("\n[4/6] Finding message bubbles in DOM...")
        bubbles = find_message_bubbles(page)
        print(f"  Found {len(bubbles)} candidate message image(s).")

        if not bubbles:
            print("  [ERROR] No message bubbles found.")
            print("  Check the screenshots and inspect the DOM manually.")
            page.screenshot(path="artifacts/spike_react_no_bubbles.png")
            browser.close()
            return

        print()
        print("  Message images visible in viewport:")
        for i, b in enumerate(bubbles[:10]):
            desc = describe_bubble(b, i)
            print(f"    [{i+1}] {desc}")

        # Step 5: User identifies which message to react to
        print()
        input("[5/6] Scroll in the browser to a message you want to react to "
              "(a reel/post shared by the other person). "
              "Do NOT click anything yourself. Press Enter when ready: ")

        desc = input("  Describe the message (e.g. '3rd from bottom', poster handle, "
                     "or a few words from the caption): ").strip()

        print()
        print("  Re-scanning bubbles after your scroll...")
        bubbles = find_message_bubbles(page)
        print(f"  Found {len(bubbles)} candidate image(s).")
        for i, b in enumerate(bubbles[:10]):
            print(f"    [{i+1}] {describe_bubble(b, i)}")

        if not bubbles:
            print("  [ERROR] Still no bubbles found after scroll. Aborting.")
            browser.close()
            return

        choice_raw = input(
            f"\n  Which image number to react to? (1-{min(len(bubbles), 10)}) "
            f"[default=1]: "
        ).strip()
        try:
            choice_idx = (int(choice_raw) - 1) if choice_raw else 0
            if not (0 <= choice_idx < len(bubbles)):
                choice_idx = 0
        except ValueError:
            choice_idx = 0

        bubble = bubbles[choice_idx]
        print(f"\n  Selected: {describe_bubble(bubble, choice_idx)}")

        confirm = input(
            "\n  I will hover over this image, click the reaction smiley icon, "
            "and click ❤.\n  Type 'go' to proceed, anything else to abort: "
        ).strip().lower()

        if confirm != "go":
            print("Aborted by user.")
            browser.close()
            return

        # Step 6: DOM-click reaction
        print("\n[6/6] Performing DOM-click reaction sequence...")
        page.screenshot(path="artifacts/spike_react_before.png")
        print("  Before screenshot: artifacts/spike_react_before.png")

        success = hover_and_react(page, bubble, capture, emoji="❤")

        if success:
            print("\n  Waiting 5s for GraphQL mutation to fire...")
            time.sleep(5)
            page.screenshot(path="artifacts/spike_react_after.png")
            print("  After screenshot: artifacts/spike_react_after.png")
        else:
            print("\n  [WARN] DOM-click sequence did not complete cleanly.")
            page.screenshot(path="artifacts/spike_react_failed.png")

        browser.close()

    # ---------------------------------------------------------------------------
    # Analyze captured network traffic
    # ---------------------------------------------------------------------------
    capture_path = capture.save()
    print(f"\n[RESULT] Reaction network capture: {capture_path}")
    print(f"  Total reaction-related GraphQL calls captured: {len(capture.entries)}")

    # Check for success
    mutation_name = "IGDirectReactionSendMutation"
    matched = [e for e in capture.entries if e.get("friendly_name") == mutation_name]
    if matched:
        print(f"\n  [SUCCESS] {mutation_name} fired {len(matched)} time(s).")
        for e in matched:
            status = e.get("response_status")
            variables = e.get("variables", {})
            inp = variables.get("input", {})
            print(f"    HTTP status: {status}")
            print(f"    emoji:       {inp.get('emoji')}")
            print(f"    message_id:  {inp.get('message_id')}")
            print(f"    thread_id:   {inp.get('thread_id')}")
            print(f"    reaction_status: {inp.get('reaction_status')}")
            if status == 200:
                print(f"    [OK] HTTP 200 confirmed — DOM-click reaction path verified.")
    else:
        print(f"\n  [WARN] {mutation_name} NOT captured.")
        print("  Either the reaction click didn't register, or the picker closed before selection.")
        print("  Check screenshots: spike_react_before.png, spike_react_after.png")
        if capture.entries:
            print(f"  Other reaction-related calls captured: {len(capture.entries)}")
            for e in capture.entries:
                print(f"    {e.get('friendly_name')} — status {e.get('response_status')}")

    # Write structured findings log
    findings = {
        "timestamp": datetime.now().isoformat(),
        "thread_url": thread_url,
        "user_description": desc if "desc" in dir() else "",
        "bubble_count_found": len(bubbles) if "bubbles" in dir() else 0,
        "dom_click_success": success if "success" in dir() else False,
        "mutation_fired": len(matched) > 0 if "matched" in dir() else False,
        "mutation_details": matched[0] if (matched if "matched" in dir() else []) else None,
        "selectors_attempted": {
            "message_bubbles": [
                "img[src*='cdninstagram'] inside [data-pagelet='IGDMessagesList']"
            ],
            "react_button": [
                '[aria-label="React to message"]',
                'button[aria-label*="React"]',
                '[role="toolbar"] button:first-child',
            ],
            "emoji_picker_heart": [
                '[aria-label="❤"]',
                'button[aria-label="❤"]',
                '[role="dialog"] button:first-child',
            ],
        },
        "screenshots": {
            "before": "artifacts/spike_react_before.png",
            "after": "artifacts/spike_react_after.png",
        },
    }
    findings_path = "artifacts/spike_react_domclick_findings.json"
    Path(findings_path).write_text(json.dumps(findings, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n  Findings log: {findings_path}")

    print("\n" + "=" * 65)
    print("SPIKE COMPLETE — review screenshots and findings log.")
    print("Then check docs/react_domclick_findings.md for full analysis.")
    print("=" * 65)


if __name__ == "__main__":
    main()
