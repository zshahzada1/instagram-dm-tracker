#!/usr/bin/env python3
"""
P7 Comments Recon v2
Broad network interceptor — captures ALL IG network calls, not just /api/graphql.
Extracts inline JSON from page HTML.
READ-ONLY — no writes, no reactions, no clicks that send anything.
"""

import json
import re
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
TARGET_ITEM_TYPE = "reel"
TARGET_URL = f"https://www.instagram.com/{TARGET_ITEM_TYPE}/{TARGET_SHORTCODE}/"

IG_DOMAINS = ('instagram.com', 'cdninstagram.com', 'facebook.com')

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

def is_ig_url(url: str) -> bool:
    return any(d in url for d in IG_DOMAINS)

def extract_inline_json(html: str) -> list[dict]:
    """Find all <script> tags containing JSON and extract them."""
    results = []
    # Pattern 1: <script type="application/json">...</script>
    for m in re.finditer(r'<script[^>]*type=["\']application/json["\'][^>]*>(.*?)</script>', html, re.DOTALL):
        try:
            data = json.loads(m.group(1))
            results.append({'source': 'application/json script tag', 'data': data})
        except Exception:
            pass

    # Pattern 2: window.__additionalDataLoaded(...)
    for m in re.finditer(r'window\.__additionalDataLoaded\s*\(\s*["\'][^"\']+["\']\s*,\s*(\{.*?\})\s*\)', html, re.DOTALL):
        try:
            data = json.loads(m.group(1))
            results.append({'source': 'window.__additionalDataLoaded', 'data': data})
        except Exception:
            pass

    # Pattern 3: window._sharedData = {...}
    m = re.search(r'window\._sharedData\s*=\s*(\{.*?\})\s*;', html, re.DOTALL)
    if m:
        try:
            data = json.loads(m.group(1))
            results.append({'source': 'window._sharedData', 'data': data})
        except Exception:
            pass

    # Pattern 4: require("TimeSliceImpl")... or other script data blobs — look for JSON with media/shortcode
    for m in re.finditer(r'(\{"require":\[\[.*?\]\]\})', html, re.DOTALL):
        try:
            data = json.loads(m.group(1))
            s = json.dumps(data)
            if 'comment' in s.lower() or TARGET_SHORTCODE in s:
                results.append({'source': 'require() blob', 'data': data})
        except Exception:
            pass

    return results

def find_comment_data(obj, path='', depth=0) -> list[tuple[str, any]]:
    """Recursively find any list that looks like comments."""
    found = []
    if depth > 8:
        return found
    if isinstance(obj, list) and len(obj) > 0:
        first = obj[0]
        if isinstance(first, dict) and any(
            k in first for k in ('text', 'pk', 'comment_like_count', 'created_at_utc', 'has_liked_comment')
        ):
            found.append((path, obj))
    if isinstance(obj, dict):
        for k, v in obj.items():
            found.extend(find_comment_data(v, f'{path}.{k}', depth+1))
    elif isinstance(obj, list):
        for i, item in enumerate(obj[:10]):
            found.extend(find_comment_data(item, f'{path}[{i}]', depth+1))
    return found

if __name__ == '__main__':
    all_requests = []  # every IG request URL seen
    all_responses = []  # IG responses with parseable bodies

    def handle_response(response):
        url = response.url
        if not is_ig_url(url):
            return
        # Log the URL regardless
        entry = {
            'url': url,
            'status': response.status,
            'method': response.request.method,
            'timestamp': datetime.now().isoformat(),
            'body_json': None,
            'post_data_friendly_name': None,
        }
        # Try to parse body
        try:
            body = response.body()
            if body:
                try:
                    entry['body_json'] = json.loads(body.decode('utf-8', errors='replace'))
                except Exception:
                    pass
        except Exception:
            pass
        # If it's a POST, grab friendly_name
        if response.request.method == 'POST':
            try:
                post_data = response.request.post_data or ''
                parsed = parse_qs(post_data)
                entry['post_data_friendly_name'] = (parsed.get('fb_api_req_friendly_name') or [''])[0]
                entry['doc_id'] = (parsed.get('doc_id') or [''])[0]
            except Exception:
                pass
        all_responses.append(entry)
        all_requests.append(url)

    print(f"Target: {TARGET_URL}")

    with Camoufox(headless=False) as browser:
        context = browser.new_context(viewport={'width': 1280, 'height': 900})
        load_cookies(context, COOKIES_PATH)
        page = context.new_page()
        page.on('response', handle_response)

        print("Navigating to reel...")
        page.goto(TARGET_URL, wait_until='domcontentloaded', timeout=30000)
        time.sleep(jitter(5.0))
        page.screenshot(path=str(ARTIFACTS_DIR / 'p7v2_b1_loaded.png'))

        # Extract inline JSON from page HTML BEFORE any clicks
        print("Extracting inline JSON from page HTML...")
        html = page.content()
        inline_data = extract_inline_json(html)
        print(f"  Found {len(inline_data)} inline JSON blobs")

        # Look for comments section and interact (read-only)
        print("Looking for comments section...")
        # Try to find and click "View all X comments" if present
        try:
            view_all = page.locator('span:has-text("View all"), a:has-text("View all"), button:has-text("View all")').first
            if view_all.is_visible(timeout=3000):
                print("  Clicking 'View all comments'...")
                view_all.click()
                time.sleep(jitter(3.0))
            else:
                print("  'View all' not visible — comments may be inline")
        except Exception as e:
            print(f"  No 'View all' found: {e}")

        page.screenshot(path=str(ARTIFACTS_DIR / 'p7v2_b2_comments.png'))

        # Scroll slowly to trigger any lazy-loaded comment requests
        print("Scrolling to trigger lazy loads...")
        for i in range(5):
            page.keyboard.press('PageDown')
            time.sleep(jitter(2.0))

        time.sleep(jitter(3.0))
        page.screenshot(path=str(ARTIFACTS_DIR / 'p7v2_b3_scrolled.png'))
        page.close()

    # --- Analysis ---
    print(f"\nTotal IG responses captured: {len(all_responses)}")

    # 1. All unique URL paths (deduplicated)
    unique_paths = sorted(set(
        urlparse(r['url']).path for r in all_responses
    ))
    print(f"\nAll unique IG URL paths seen ({len(unique_paths)}):")
    for p in unique_paths:
        print(f"  {p}")

    # 2. Responses with 'comment' anywhere in body
    comment_responses = [
        r for r in all_responses
        if r['body_json'] and 'comment' in json.dumps(r['body_json']).lower()
    ]
    print(f"\nResponses containing 'comment' in body: {len(comment_responses)}")
    for r in comment_responses:
        print(f"  {r['method']} {urlparse(r['url']).path} (status={r['status']}, friendly={r.get('post_data_friendly_name')})")

    # 3. Inline JSON with comment data
    comment_inline = []
    for blob in inline_data:
        hits = find_comment_data(blob['data'])
        if hits:
            comment_inline.append({'source': blob['source'], 'hits': hits})

    print(f"\nInline JSON blobs with comment-like data: {len(comment_inline)}")
    for ci in comment_inline:
        print(f"  Source: {ci['source']}")
        for path, arr in ci['hits']:
            print(f"    Path: {path}, count={len(arr)}, first_keys={list(arr[0].keys())[:10]}")

    # --- Write artifacts ---

    # Truncation helper
    def trunc(obj, d=0):
        if d > 3: return '...'
        if isinstance(obj, dict): return {k: trunc(v, d+1) for k, v in list(obj.items())[:15]}
        if isinstance(obj, list): return [trunc(i, d+1) for i in obj[:3]] + (['...'] if len(obj) > 3 else [])
        return obj

    # All IG requests (URL log)
    with open(ARTIFACTS_DIR / 'p7v2_all_ig_urls.txt', 'w') as f:
        for url in all_requests:
            f.write(url + '\n')

    # Comment-containing responses
    with open(ARTIFACTS_DIR / 'p7v2_comment_responses.json', 'w') as f:
        json.dump([{**r, 'body_json': trunc(r['body_json'])} for r in comment_responses], f, indent=2)

    # Inline JSON blobs (truncated)
    with open(ARTIFACTS_DIR / 'p7v2_inline_json.json', 'w') as f:
        serialisable = []
        for blob in inline_data:
            serialisable.append({'source': blob['source'], 'data': trunc(blob['data'])})
        json.dump(serialisable, f, indent=2)

    # Full responses (all, truncated)
    with open(ARTIFACTS_DIR / 'p7v2_all_responses.json', 'w') as f:
        json.dump([{**r, 'body_json': trunc(r['body_json'])} for r in all_responses], f, indent=2)

    print("\nArtifacts written:")
    print("  artifacts/p7v2_all_ig_urls.txt")
    print("  artifacts/p7v2_comment_responses.json")
    print("  artifacts/p7v2_inline_json.json")
    print("  artifacts/p7v2_all_responses.json")
    print("  artifacts/p7v2_b1_loaded.png, p7v2_b2_comments.png, p7v2_b3_scrolled.png")
