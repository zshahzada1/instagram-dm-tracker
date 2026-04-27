#!/usr/bin/env python3
"""
P7 Comments Recon Spike
Passive network intercept — no writes, no reactions.
Two passes:
  Pass A: navigate via DM inbox (real user flow)
  Pass B: navigate directly to post URL (control)
"""

import json
import time
import random
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from camoufox.sync_api import Camoufox
from playwright.sync_api import sync_playwright

COOKIES_PATH = Path("test-cookies/cookies.json")
ARTIFACTS_DIR = Path("artifacts")
ARTIFACTS_DIR.mkdir(exist_ok=True)

# --- FILL IN from Step 1 ---
TARGET_SHORTCODE = "DWNK5V3DW_L"
TARGET_ITEM_TYPE = "reel"  # or "post"
TARGET_POSTER_HANDLE = "nickc.tv"
TARGET_DIRECT_URL = f"https://www.instagram.com/{TARGET_ITEM_TYPE}/{TARGET_SHORTCODE}/"
DM_INBOX_URL = "https://www.instagram.com/direct/inbox/"
# ---

def jitter(base: float) -> float:
    return base + random.uniform(0.5, 1.5)

def load_cookies(context, path: Path):
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

def make_interceptor(label: str) -> tuple[list, callable]:
    """Returns (captured_calls list, handler function)."""
    calls = []

    def handler(response):
        if '/api/graphql' not in response.url:
            return
        try:
            post_data = response.request.post_data or ''
            parsed = parse_qs(post_data)
            friendly_name = (parsed.get('fb_api_req_friendly_name') or [''])[0]
            doc_id = (parsed.get('doc_id') or [''])[0]
            variables_raw = (parsed.get('variables') or ['{}'])[0]
            try:
                variables = json.loads(variables_raw)
            except Exception:
                variables = {}

            body = response.body()
            try:
                response_json = json.loads(body.decode('utf-8', errors='replace'))
            except Exception:
                response_json = None

            calls.append({
                'pass': label,
                'friendly_name': friendly_name,
                'doc_id': doc_id,
                'variables': variables,
                'response_status': response.status,
                'response_json': response_json,
                'url': response.url,
                'timestamp': datetime.now().isoformat(),
            })
        except Exception:
            pass

    return calls, handler

def scroll_comments(page, n: int = 4):
    """Scroll inside comments section slowly, jittered."""
    for i in range(n):
        page.keyboard.press('PageDown')
        time.sleep(jitter(2.0))

def run_pass_a_dm_flow(context) -> list:
    """Pass A: open DM inbox, find the thread, click through to the post."""
    page = context.new_page()
    calls, handler = make_interceptor("pass_a_dm")
    page.on('response', handler)

    print("[Pass A] Navigating to DM inbox...")
    page.goto(DM_INBOX_URL, wait_until='networkidle', timeout=30000)
    time.sleep(jitter(3.0))
    page.screenshot(path=str(ARTIFACTS_DIR / "p7_a1_inbox.png"))

    # Find and click the DM thread (look for the thread that contains the target poster)
    # The thread list shows sender avatars and preview text; find the right thread
    # Strategy: click the first/topmost thread (the active conversation)
    thread_links = page.query_selector_all('a[href*="/direct/t/"]')
    print(f"[Pass A] Found {len(thread_links)} thread links")
    if not thread_links:
        print("[Pass A] STOP: No thread links found in inbox. Screenshot saved.")
        page.screenshot(path=str(ARTIFACTS_DIR / "p7_a1_inbox_fail.png"))
        page.close()
        return calls

    # Click the first thread
    thread_links[0].click()
    time.sleep(jitter(3.0))
    page.screenshot(path=str(ARTIFACTS_DIR / "p7_a2_thread_open.png"))

    # Look for the target shortcode in an anchor or post link
    target_link = page.query_selector(f'a[href*="{TARGET_SHORTCODE}"]')
    if not target_link:
        print(f"[Pass A] STOP: Target shortcode {TARGET_SHORTCODE} not visible in thread. May need to scroll up.")
        page.screenshot(path=str(ARTIFACTS_DIR / "p7_a2_thread_no_target.png"))
        page.close()
        return calls

    print(f"[Pass A] Found target link, clicking through to post...")
    target_link.click()
    time.sleep(jitter(5.0))
    page.screenshot(path=str(ARTIFACTS_DIR / "p7_a3_post_via_dm.png"))

    _interact_with_comments(page, "p7_a4", "p7_a5", "p7_a6")

    page.close()
    return calls

def run_pass_b_direct(context) -> list:
    """Pass B: navigate directly to the post URL."""
    page = context.new_page()
    calls, handler = make_interceptor("pass_b_direct")
    page.on('response', handler)

    print(f"[Pass B] Navigating directly to {TARGET_DIRECT_URL}")
    page.goto(TARGET_DIRECT_URL, wait_until='networkidle', timeout=30000)
    time.sleep(jitter(5.0))
    page.screenshot(path=str(ARTIFACTS_DIR / "p7_b1_post_direct.png"))

    _interact_with_comments(page, "p7_b2", "p7_b3", "p7_b4")

    page.close()
    return calls

def _interact_with_comments(page, ss_loaded: str, ss_expanded: str, ss_scrolled: str):
    """Shared: attempt to expand comments and scroll. READ-ONLY."""
    # Some posts render comments inline; others show "View all N comments"
    view_all = page.query_selector('a[href*="/comments/"], span:has-text("View all"), button:has-text("View all")')
    if view_all:
        print(f"  Found 'View all comments' link, clicking...")
        view_all.click()
        time.sleep(jitter(3.0))
    else:
        print("  Comments appear inline or not found — skipping expand click")
    page.screenshot(path=str(ARTIFACTS_DIR / f"{ss_expanded}_comments_visible.png"))

    scroll_comments(page, n=4)
    page.screenshot(path=str(ARTIFACTS_DIR / f"{ss_scrolled}_comments_scrolled.png"))

def analyse(all_calls: list) -> dict:
    """Find comments-related GraphQL calls and extract field shapes."""
    # Keywords that suggest a comments query
    COMMENT_KEYWORDS = [
        'comment', 'Comment', 'MediaComment', 'FeedComment',
        'GraphComments', 'media_comments', 'xdt_api__v1__media'
    ]

    comment_calls = [
        c for c in all_calls
        if any(kw in (c.get('friendly_name') or '') or
               any(kw in str(v) for v in (c.get('variables') or {}).values())
               for kw in COMMENT_KEYWORDS)
    ]

    # Also capture any calls that returned a 'comments' key in the response
    for c in all_calls:
        rj = c.get('response_json') or {}
        body_str = json.dumps(rj)
        if 'comment' in body_str.lower() and c not in comment_calls:
            comment_calls.append(c)

    # Deduplicate by doc_id
    seen_doc_ids = set()
    unique_comment_calls = []
    for c in comment_calls:
        key = c.get('doc_id') or c.get('friendly_name') or str(c.get('timestamp'))
        if key not in seen_doc_ids:
            seen_doc_ids.add(key)
            unique_comment_calls.append(c)

    # All distinct friendly_names seen (for full picture)
    all_names = list({c.get('friendly_name') for c in all_calls if c.get('friendly_name')})

    return {
        'total_graphql_calls': len(all_calls),
        'comment_related_calls': len(comment_calls),
        'unique_comment_calls': unique_comment_calls,
        'all_friendly_names': sorted(all_names),
    }

def extract_comment_shape(call: dict) -> dict:
    """Walk the response JSON to find comment arrays and map their fields."""
    rj = call.get('response_json') or {}
    body_str = json.dumps(rj)

    # Find path to comments array by recursively searching for list containing comment-like objects
    def find_comments(obj, path=""):
        if isinstance(obj, list) and len(obj) > 0:
            first = obj[0]
            if isinstance(first, dict) and any(
                k in first for k in ('text', 'pk', 'user', 'created_at', 'comment_like_count')
            ):
                return path, obj
        if isinstance(obj, dict):
            for k, v in obj.items():
                result = find_comments(v, f"{path}.{k}")
                if result:
                    return result
        return None

    found = find_comments(rj)
    if not found:
        return {'comment_array_path': None, 'first_comment_keys': None}

    path, comments = found
    first = comments[0] if comments else {}
    # Sample up to 2 comments for field map
    samples = comments[:2]

    return {
        'comment_array_path': path,
        'comment_count_in_response': len(comments),
        'first_comment_keys': list(first.keys()),
        'sample_comments': [
            {k: v for k, v in s.items() if k not in ('user',)} for s in samples
        ],
        'has_replies': any('replies' in str(s) for s in samples),
        'has_gif': any('gif' in json.dumps(s).lower() for s in samples),
        'pagination_keys': [k for k in first.keys() if 'cursor' in k.lower() or 'page' in k.lower() or 'next' in k.lower()],
    }

if __name__ == '__main__':
    print(f"Target: {TARGET_DIRECT_URL}")
    print(f"Cookies: {COOKIES_PATH}")

    all_calls_a = []
    all_calls_b = []

    with Camoufox(headless=False) as browser:
        context = browser.new_context(viewport={'width': 1280, 'height': 900})
        load_cookies(context, COOKIES_PATH)

        print("\n=== PASS A: DM inbox flow ===")
        all_calls_a = run_pass_a_dm_flow(context)

        time.sleep(jitter(3.0))

        print("\n=== PASS B: Direct URL ===")
        all_calls_b = run_pass_b_direct(context)

    all_calls = all_calls_a + all_calls_b
    analysis = analyse(all_calls)

    # Write full captured calls (truncate response bodies for readability)
    def truncate(obj, depth=0):
        if depth > 4:
            return '...'
        if isinstance(obj, dict):
            return {k: truncate(v, depth+1) for k, v in list(obj.items())[:20]}
        if isinstance(obj, list):
            return [truncate(i, depth+1) for i in obj[:5]] + (['...'] if len(obj) > 5 else [])
        return obj

    out_all = ARTIFACTS_DIR / "p7_all_graphql_calls.json"
    with open(out_all, 'w') as f:
        json.dump([{**c, 'response_json': truncate(c.get('response_json'))} for c in all_calls], f, indent=2)

    # Write comment-specific analysis
    comment_analysis = []
    for call in analysis['unique_comment_calls']:
        shape = extract_comment_shape(call)
        comment_analysis.append({
            'pass': call.get('pass'),
            'friendly_name': call.get('friendly_name'),
            'doc_id': call.get('doc_id'),
            'variables': call.get('variables'),
            'response_status': call.get('response_status'),
            'shape': shape,
        })

    out_comments = ARTIFACTS_DIR / "p7_comment_calls.json"
    with open(out_comments, 'w') as f:
        json.dump({
            'target_shortcode': TARGET_SHORTCODE,
            'target_poster': TARGET_POSTER_HANDLE,
            'total_graphql_calls': analysis['total_graphql_calls'],
            'comment_related_count': analysis['comment_related_calls'],
            'all_friendly_names': analysis['all_friendly_names'],
            'comment_calls': comment_analysis,
        }, f, indent=2)

    print(f"\n=== ANALYSIS SUMMARY ===")
    print(f"Total GraphQL calls captured: {analysis['total_graphql_calls']}")
    print(f"Comment-related calls: {analysis['comment_related_calls']}")
    print(f"\nAll friendly_names seen:")
    for name in analysis['all_friendly_names']:
        print(f"  {name}")
    print(f"\nComment call details:")
    for ca in comment_analysis:
        print(f"  [{ca['pass']}] {ca['friendly_name']} (doc_id={ca['doc_id']})")
        s = ca['shape']
        print(f"    array_path: {s['comment_array_path']}")
        print(f"    fields: {s['first_comment_keys']}")
        print(f"    has_replies: {s.get('has_replies')} | has_gif: {s.get('has_gif')}")
        print(f"    pagination_keys: {s.get('pagination_keys')}")

    print(f"\nArtifacts written:")
    print(f"  {out_all}")
    print(f"  {out_comments}")
