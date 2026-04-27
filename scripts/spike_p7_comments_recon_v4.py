#!/usr/bin/env python3
"""
P7 Comments Recon v4 — Full schema capture
Targets PolarisPostCommentsContainerQuery only. No truncation.
READ-ONLY.
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
TARGET_QUERIES = {
    'PolarisPostCommentsContainerQuery',
    'PolarisClipsDesktopCommentsPopoverQuery',
}

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

target_calls = []  # full, untruncated

def handle_response(response):
    if 'instagram.com' not in response.url:
        return
    if response.request.method != 'POST':
        return
    try:
        post_data = response.request.post_data or ''
        parsed = parse_qs(post_data)
        friendly_name = (parsed.get('fb_api_req_friendly_name') or [''])[0]
        if friendly_name not in TARGET_QUERIES:
            return
        doc_id = (parsed.get('doc_id') or [''])[0]
        variables_raw = (parsed.get('variables') or ['{}'])[0]
        try:
            variables = json.loads(variables_raw)
        except Exception:
            variables = {}

        body = response.body()
        response_json = json.loads(body.decode('utf-8', errors='replace'))

        target_calls.append({
            'friendly_name': friendly_name,
            'doc_id': doc_id,
            'variables': variables,
            'response_status': response.status,
            'response_json': response_json,  # FULL, no truncation
            'timestamp': datetime.now().isoformat(),
        })
        print(f"  [CAPTURED] {friendly_name} (doc_id={doc_id}) at {datetime.now().isoformat()}")
    except Exception as e:
        pass

if __name__ == '__main__':
    print(f"Target: {TARGET_URL}")
    print(f"Watching for: {TARGET_QUERIES}")

    with Camoufox(headless=False) as browser:
        context = browser.new_context(viewport={'width': 1280, 'height': 900})
        load_cookies(context, COOKIES_PATH)
        page = context.new_page()
        page.on('response', handle_response)

        print("\nNavigating...")
        page.goto(TARGET_URL, wait_until='domcontentloaded', timeout=30000)
        time.sleep(jitter(5.0))
        page.screenshot(path=str(ARTIFACTS_DIR / 'p7v4_01_loaded.png'))

        print("Clicking comment button...")
        try:
            btn = page.locator('[aria-label="Comment"]').first
            btn.wait_for(timeout=5000)
            btn.click()
        except Exception as e:
            print(f"Comment button click failed: {e}")
            print("Trying fallback selector...")
            try:
                page.locator('svg[aria-label="Comment"]').locator('..').click()
            except Exception as e2:
                print(f"Fallback also failed: {e2}")

        print("Waiting for comments to load (10s)...")
        time.sleep(10.0)
        page.screenshot(path=str(ARTIFACTS_DIR / 'p7v4_02_comments_open.png'))
        print(f"Calls captured so far: {len(target_calls)}")

        # Scroll comments panel to trigger pagination
        print("Scrolling comments panel to trigger pagination...")
        page.mouse.move(950, 500)
        for i in range(6):
            page.mouse.wheel(0, 800)
            time.sleep(jitter(2.5))
            print(f"  Scroll {i+1}/6 — captured calls: {len(target_calls)}")

        time.sleep(jitter(3.0))
        page.screenshot(path=str(ARTIFACTS_DIR / 'p7v4_03_scrolled.png'))
        page.close()

    print(f"\n=== RESULTS ===")
    print(f"Total target calls captured: {len(target_calls)}")

    if not target_calls:
        print("STOP: No target calls captured. Check screenshots and retry.")
    else:
        for i, call in enumerate(target_calls):
            out_path = ARTIFACTS_DIR / f"p7v4_call_{i:02d}_{call['friendly_name']}.json"
            with open(out_path, 'w') as f:
                json.dump(call, f, indent=2)
            print(f"\n--- Call {i} ---")
            print(f"  friendly_name: {call['friendly_name']}")
            print(f"  doc_id: {call['doc_id']}")
            print(f"  variables: {json.dumps(call['variables'])}")
            print(f"  status: {call['response_status']}")
            print(f"  written to: {out_path}")

            # Walk the response to find comment arrays and print schema
            def find_comment_arrays(obj, path='', depth=0):
                found = []
                if depth > 8: return found
                if isinstance(obj, list) and len(obj) > 0:
                    first = obj[0]
                    if isinstance(first, dict) and 'node' in first:
                        node = first['node']
                        if isinstance(node, dict) and any(
                            k in node for k in ('text', 'pk', 'comment_like_count', 'created_at_utc')
                        ):
                            found.append((path + '[].node', [item['node'] for item in obj if 'node' in item]))
                    elif isinstance(first, dict) and any(
                        k in first for k in ('text', 'pk', 'comment_like_count', 'created_at_utc')
                    ) and 'text' in first:
                        found.append((path, obj))
                if isinstance(obj, dict):
                    for k, v in obj.items():
                        found.extend(find_comment_arrays(v, f'{path}.{k}', depth+1))
                elif isinstance(obj, list):
                    for idx, item in enumerate(obj[:3]):
                        found.extend(find_comment_arrays(item, f'{path}[{idx}]', depth+1))
                return found

            hits = find_comment_arrays(call['response_json'])
            if hits:
                for arr_path, arr in hits:
                    print(f"\n  COMMENT ARRAY at: {arr_path}")
                    print(f"  Count: {len(arr)}")
                    first = arr[0]
                    print(f"  All keys on first comment: {list(first.keys())}")
                    # Print every field name + type/sample
                    for k, v in first.items():
                        if isinstance(v, dict):
                            print(f"    {k}: dict with keys {list(v.keys())}")
                        elif isinstance(v, list):
                            print(f"    {k}: list[{len(v)}] first={v[0] if v else None}")
                        else:
                            print(f"    {k}: {type(v).__name__} = {repr(v)[:80]}")
            else:
                print("  No comment arrays found in this call — check the full JSON file")

    print("\nScreenshots: p7v4_01_loaded.png, p7v4_02_comments_open.png, p7v4_03_scrolled.png")
