#!/usr/bin/env python3
"""
P7 Comments Recon v3
Clicks the comment icon to trigger comment loading, then captures network calls.
READ-ONLY — no likes, no replies, no sends.
"""

import json
import time
import random
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from camoufox.sync_api import Camoufox

COOKIES_PATH = Path("test-cookies/cookies.json")
ARTIFACTS_DIR = Path("artifacts")
ARTIFACTS_DIR.mkdir(exist_ok=True)

TARGET_SHORTCODE = "DWNK5V3DW_L"
TARGET_URL = f"https://www.instagram.com/reel/{TARGET_SHORTCODE}/"
IG_DOMAINS = ('instagram.com', 'cdninstagram.com')

def jitter(base):
    return base + random.uniform(0.5, 1.5)

def load_cookies(context, path):
    raw = json.loads(path.read_text())
    cookies = []
    for c in raw:
        cookie = {
            'name': c.get('name'),
            'value': c.get('value'),
            'domain': c.get('domain', '.instagram.com'),
            'path': c.get('path', '/'),
            'httpOnly': c.get('httpOnly', False),
            'secure': c.get('secure', True),
        }
        if 'expirationDate' in c:
            cookie['expires'] = int(c.pop('expirationDate'))
        cookies.append(cookie)
    context.add_cookies(cookies)

def is_ig_url(url):
    return any(d in url for d in IG_DOMAINS)

all_responses = []

def handle_response(response):
    url = response.url
    if not is_ig_url(url):
        return
    entry = {
        'url': url,
        'path': urlparse(url).path,
        'status': response.status,
        'method': response.request.method,
        'timestamp': datetime.now().isoformat(),
        'body_json': None,
        'friendly_name': None,
        'doc_id': None,
    }
    try:
        body = response.body()
        if body:
            try:
                entry['body_json'] = json.loads(body.decode('utf-8', errors='replace'))
            except Exception:
                pass
    except Exception:
        pass
    if response.request.method == 'POST':
        try:
            post_data = response.request.post_data or ''
            parsed = parse_qs(post_data)
            entry['friendly_name'] = (parsed.get('fb_api_req_friendly_name') or [''])[0]
            entry['doc_id'] = (parsed.get('doc_id') or [''])[0]
        except Exception:
            pass
    all_responses.append(entry)

if __name__ == '__main__':
    print(f"Target: {TARGET_URL}")

    with Camoufox(headless=False) as browser:
        context = browser.new_context(viewport={'width': 1280, 'height': 900})
        load_cookies(context, COOKIES_PATH)
        page = context.new_page()
        page.on('response', handle_response)

        print("Navigating to reel...")
        page.goto(TARGET_URL, wait_until='domcontentloaded', timeout=30000)
        time.sleep(jitter(5.0))
        page.screenshot(path=str(ARTIFACTS_DIR / 'p7v3_01_loaded.png'))
        print("Page loaded. Screenshot: p7v3_01_loaded.png")

        # Find the comment button — Instagram Reels right-side action bar
        # Try multiple selectors in order of specificity
        comment_btn = None
        selectors = [
            '[aria-label="Comment"]',
            '[aria-label*="comment" i]',
            'svg[aria-label*="comment" i]',
            # The comment count button is often a div containing an SVG + count
            # Try finding by the comment count text near the heart (547K likes visible)
            'div[role="button"]:has(svg)',
        ]

        print("Looking for comment button...")
        for sel in selectors:
            try:
                candidates = page.query_selector_all(sel)
                print(f"  Selector '{sel}': {len(candidates)} matches")
                if candidates:
                    # Don't blindly click the first div[role=button]:has(svg) —
                    # that could be the Like button. Only use the specific aria-label selectors.
                    if 'aria-label' in sel and candidates:
                        comment_btn = candidates[0]
                        print(f"  -> Using this selector")
                        break
            except Exception as e:
                print(f"  Selector error: {e}")

        if not comment_btn:
            # Fallback: print all aria-labels on the right side to understand the DOM
            print("\nFallback: listing all aria-labels on the page...")
            all_btns = page.query_selector_all('[aria-label]')
            for btn in all_btns[:40]:
                try:
                    label = btn.get_attribute('aria-label')
                    tag = btn.evaluate('el => el.tagName')
                    print(f"  <{tag}> aria-label='{label}'")
                except Exception:
                    pass
            print("\nSTOP: Could not find comment button. See aria-label list above.")
            print("Screenshot saved: p7v3_02_no_comment_btn.png")
            page.screenshot(path=str(ARTIFACTS_DIR / 'p7v3_02_no_comment_btn.png'))
        else:
            # Mark network state before click so we can identify post-click calls
            pre_click_count = len(all_responses)
            print(f"\nClicking comment button... (responses before click: {pre_click_count})")
            comment_btn.click()
            time.sleep(jitter(10.0))  # Comments panel may take a moment
            page.screenshot(path=str(ARTIFACTS_DIR / 'p7v3_02_after_comment_click.png'))
            print(f"After click: {len(all_responses)} total responses (+{len(all_responses)-pre_click_count} new)")

            # Scroll within comments panel (if it appeared)
            # Don't use PageDown — that navigates the reel feed. Use mouse wheel on comments area.
            print("Scrolling comments panel (mouse wheel)...")
            try:
                # Comments panel is typically on the right side of the screen
                page.mouse.move(950, 500)
                for i in range(5):
                    page.mouse.wheel(0, 600)
                    time.sleep(jitter(2.0))
            except Exception as e:
                print(f"Scroll error: {e}")

            time.sleep(jitter(3.0))
            page.screenshot(path=str(ARTIFACTS_DIR / 'p7v3_03_comments_scrolled.png'))

        page.close()

    # --- Analysis ---
    print(f"\n=== ANALYSIS ===")
    print(f"Total IG responses: {len(all_responses)}")

    # All unique paths
    paths = sorted(set(r['path'] for r in all_responses))
    print(f"\nUnique IG paths ({len(paths)}):")
    for p in paths:
        print(f"  {p}")

    # Responses with 'comment' in body
    comment_resp = [
        r for r in all_responses
        if r['body_json'] and 'comment' in json.dumps(r['body_json']).lower()
    ]
    print(f"\nResponses with 'comment' in body: {len(comment_resp)}")
    for r in comment_resp:
        body_str = json.dumps(r['body_json'])
        # Does it contain actual comment text/pk fields (not just the word comment in passing)?
        has_real_comments = '"text"' in body_str and '"pk"' in body_str
        print(f"  {r['method']} {r['path']} friendly={r['friendly_name']} doc_id={r['doc_id']} real_comments={has_real_comments}")

    # Find comments with actual structure
    def find_comment_arrays(obj, path='', depth=0):
        found = []
        if depth > 6: return found
        if isinstance(obj, list) and len(obj) > 0:
            first = obj[0]
            if isinstance(first, dict) and any(
                k in first for k in ('text', 'pk', 'comment_like_count', 'created_at_utc', 'has_liked_comment', 'user')
            ) and 'text' in first:
                found.append((path, obj))
        if isinstance(obj, dict):
            for k, v in obj.items():
                found.extend(find_comment_arrays(v, f'{path}.{k}', depth+1))
        elif isinstance(obj, list):
            for i, item in enumerate(obj[:5]):
                found.extend(find_comment_arrays(item, f'{path}[{i}]', depth+1))
        return found

    print("\nSearching all responses for comment arrays...")
    for r in all_responses:
        if not r['body_json']:
            continue
        hits = find_comment_arrays(r['body_json'])
        if hits:
            print(f"\n  *** FOUND COMMENT ARRAY in {r['path']} friendly={r['friendly_name']} ***")
            for path, arr in hits:
                print(f"    path: {path}")
                print(f"    count: {len(arr)}")
                print(f"    first comment keys: {list(arr[0].keys())}")
                print(f"    sample text: {arr[0].get('text', '')[:80]}")

    # Write artifacts
    def trunc(obj, d=0):
        if d > 3: return '...'
        if isinstance(obj, dict): return {k: trunc(v, d+1) for k, v in list(obj.items())[:15]}
        if isinstance(obj, list): return [trunc(i, d+1) for i in obj[:3]] + (['...'] if len(obj) > 3 else [])
        return obj

    with open(ARTIFACTS_DIR / 'p7v3_comment_responses.json', 'w') as f:
        json.dump([{**r, 'body_json': trunc(r['body_json'])} for r in comment_resp], f, indent=2)

    with open(ARTIFACTS_DIR / 'p7v3_all_responses.json', 'w') as f:
        json.dump([{**r, 'body_json': trunc(r['body_json'])} for r in all_responses], f, indent=2)

    print("\nArtifacts: p7v3_comment_responses.json, p7v3_all_responses.json")
    print("Screenshots: p7v3_01_loaded.png, p7v3_02_after_comment_click.png, p7v3_03_comments_scrolled.png")
