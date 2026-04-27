#!/usr/bin/env python3
"""
Probe OffMsys Response Shape — Prompt 3.7 Step A

Navigate to bel's thread, trigger IGDMessageListOffMsysQuery via keyboard,
capture one complete request+response pair, and identify the JSON paths
to messages and page_info in the response body.

Architecture: read-only, passive intercept, no constructed GraphQL.
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

import json
import os
import random
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs

try:
    import camoufox
except ImportError:
    print("ERROR: Camoufox is not installed!")
    print("Install with: pip install camoufox[geoip]")
    sys.exit(1)

sys.path.insert(0, str(Path(__file__).parent.parent))
from scanner.capture import ThreadMessagesCapture


EXPECTED_THREAD_FBID = "110975426965828"
THREAD_URL = f"https://www.instagram.com/direct/t/{EXPECTED_THREAD_FBID}/"
COOKIE_PATH = Path(__file__).parent.parent / "test-cookies" / "cookies.json"
ARTIFACTS_DIR = Path(__file__).parent.parent / "artifacts"

OFF_MSYS_FRIENDLY = "IGDMessageListOffMsysQuery"


class OffMsysCapture:
    """Capture IGDMessageListOffMsysQuery request+response pairs.

    Pairs by FIFO within this friendly_name only. Stores full request
    variables and full response body (no truncation).
    """

    def __init__(self):
        self._request_queue: list = []
        self.pairs: list = []  # list of {request_variables, response_body, timestamp}

    def on_request(self, request) -> None:
        if '/api/graphql' not in request.url:
            return

        try:
            post_data = request.post_data
            if not post_data:
                return

            parsed = parse_qs(post_data)
            friendly_name = parsed.get('fb_api_req_friendly_name', [None])[0]
            if friendly_name != OFF_MSYS_FRIENDLY:
                return

            variables = None
            raw_vars = parsed.get('variables', [None])[0]
            if raw_vars:
                variables = json.loads(raw_vars)

            self._request_queue.append({
                "url": request.url,
                "friendly_name": friendly_name,
                "doc_id": parsed.get('doc_id', [None])[0],
                "variables": variables,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
        except Exception:
            pass

    def on_response(self, response) -> None:
        if not self._request_queue:
            return
        if '/api/graphql' not in response.url:
            return

        # FIFO: oldest pending OffMsys request gets this response
        entry = self._request_queue.pop(0)

        response_body = None
        try:
            body = response.body()
            response_body = json.loads(body.decode('utf-8', errors='replace'))
        except Exception as e:
            response_body = {"_error": str(e)}

        self.pairs.append({
            "request_variables": entry["variables"],
            "request_doc_id": entry["doc_id"],
            "response_body": response_body,
            "timestamp": entry["timestamp"],
        })


def load_cookies(cookie_path):
    if not os.path.exists(cookie_path):
        raise FileNotFoundError(
            f"Cookies file not found: {cookie_path}\n"
            "Export Instagram cookies using Cookie-Editor extension."
        )
    with open(cookie_path, 'r') as f:
        cookies = json.load(f)
    converted = []
    for c in cookies:
        conv = {
            'name': c['name'],
            'value': c['value'],
            'domain': c['domain'],
            'path': c['path'],
            'httpOnly': c.get('httpOnly', False),
            'secure': c.get('secure', True),
        }
        if 'expirationDate' in c and c['expirationDate']:
            conv['expires'] = int(c['expirationDate'])
        same_site = c.get('sameSite', 'unspecified')
        if same_site in ('no_restriction', 'none'):
            conv['sameSite'] = 'None'
        elif same_site == 'lax':
            conv['sameSite'] = 'Lax'
        elif same_site == 'strict':
            conv['sameSite'] = 'Strict'
        else:
            conv['sameSite'] = 'None'
        converted.append(conv)
    return converted


def jitter(lo, hi):
    delay = random.uniform(lo, hi)
    time.sleep(delay)
    return delay


def check_blockers(page):
    try:
        if page.locator("text=Check Your Information").count() > 0:
            return True, "Checkpoint/Verification required"
        if page.locator("text=suspicious login attempt").count() > 0:
            return True, "Suspicious login attempt"
    except Exception:
        pass
    return False, None


def dismiss_overlays(page):
    try:
        not_now = page.locator("button:has-text('Not Now')").first
        if not_now.is_visible():
            not_now.click()
            time.sleep(random.uniform(0.5, 1.0))
    except Exception:
        pass
    try:
        page.keyboard.press("Escape")
        time.sleep(random.uniform(0.3, 0.5))
    except Exception:
        pass


def walk_response_paths(obj, current_path="", max_depth=8, depth=0):
    """Walk a JSON response to find message lists and page_info.

    Returns list of dicts with path hints. Stops at max_depth.
    """
    if depth > max_depth:
        return []

    hints = []

    if isinstance(obj, dict):
        for key, val in obj.items():
            full_path = f"{current_path}.{key}" if current_path else key

            # Look for telltale keys
            if key in ("edges", "page_info", "has_next_page", "end_cursor",
                       "message_id", "content_type", "node", "messages",
                       "slide_messages", "thread_key", "id"):
                hint = {"path": full_path, "key": key, "type": type(val).__name__}
                if isinstance(val, list):
                    hint["length"] = len(val)
                    if len(val) > 0:
                        hint["first_item_keys"] = list(val[0].keys()) if isinstance(val[0], dict) else type(val[0]).__name__
                elif isinstance(val, dict):
                    hint["keys"] = list(val.keys())[:10]
                hint["sample"] = str(val)[:120] if not isinstance(val, (dict, list)) else None
                hints.append(hint)

            hints.extend(walk_response_paths(val, full_path, max_depth, depth + 1))

    elif isinstance(obj, list):
        for i, item in enumerate(obj[:3]):  # Only first 3
            full_path = f"{current_path}[{i}]"
            hints.extend(walk_response_paths(item, full_path, max_depth, depth + 1))

    return hints


def main():
    print("=" * 60)
    print("OffMsys Response Probe — Prompt 3.7 Step A")
    print(f"Thread: {THREAD_URL}")
    print("=" * 60)

    os.makedirs(ARTIFACTS_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    capture = ThreadMessagesCapture(expected_thread_fbid=EXPECTED_THREAD_FBID)
    offmsys = OffMsysCapture()

    thread_internal_id = None
    end_cursor = None

    with camoufox.Camoufox(headless=False) as browser:
        context = browser.new_context(viewport={"width": 1528, "height": 794})
        page = context.new_page()

        # Install all listeners
        page.on("request", capture.on_request)
        page.on("response", capture.on_response)
        page.on("request", offmsys.on_request)
        page.on("response", offmsys.on_response)

        cookies = load_cookies(str(COOKIE_PATH))
        context.add_cookies(cookies)
        print(f"\nLoaded {len(cookies)} cookies")

        # Navigate directly to thread
        print(f"\n[1] Navigating directly to thread...")
        page.goto(THREAD_URL, timeout=60000, wait_until="domcontentloaded")
        jitter(4.0, 5.0)

        blocked, reason = check_blockers(page)
        if blocked:
            ss_path = ARTIFACTS_DIR / f"offmsys_blocker_{timestamp}.png"
            page.screenshot(path=str(ss_path))
            print(f"BLOCKER: {reason}\nScreenshot: {ss_path}")
            return

        dismiss_overlays(page)

        print("  Waiting 10s for initial queries to settle...")
        jitter(10.0, 12.0)

        # Extract metadata from initial IGDThreadDetailMainViewContainerQuery
        extracted = capture.extract_messages()
        thread_key = extracted.get("thread_key")
        thread_internal_id = extracted.get("thread_internal_id")
        initial_count = len(extracted["messages"])
        page_info = extracted.get("page_info")
        end_cursor = page_info.get("end_cursor") if page_info else None

        print(f"\n  Thread key: {thread_key}")
        print(f"  Thread internal id: {thread_internal_id}")
        print(f"  Initial messages: {initial_count}")
        print(f"  end_cursor: {end_cursor[:50] if end_cursor else 'N/A'}...")
        print(f"  has_next_page: {page_info.get('has_next_page') if page_info else 'N/A'}")
        print(f"  OffMsys pairs so far: {len(offmsys.pairs)}")

        # ---- Trigger pagination via keyboard ----
        # The v2 probe succeeded with: body click, PageUp × 10, End, Home.
        # Let's try multiple approaches to maximize chance of triggering OffMsys.
        print(f"\n[2] Triggering pagination via keyboard (aggressive)...")

        # Click body to focus the page
        try:
            page.click('body')
            print("  Clicked body to focus page")
        except Exception as e:
            print(f"  [warn] body click failed: {e}")
        jitter(0.5, 1.0)

        # Approach 1: PageUp × 10 (matching v2 successful trigger)
        print("  Pressing PageUp × 10...")
        for i in range(10):
            try:
                page.keyboard.press("PageUp")
            except Exception as e:
                print(f"    PageUp {i+1} error: {e}")
            time.sleep(0.3)
        jitter(1.5, 2.0)

        # Approach 2: ArrowUp × 10
        print("  Pressing ArrowUp × 10...")
        for i in range(10):
            try:
                page.keyboard.press("ArrowUp")
            except Exception as e:
                pass
            time.sleep(0.2)
        jitter(1.0, 1.5)

        # Approach 3: End + Home — jump to bottom then top
        print("  Pressing End then Home...")
        try:
            page.keyboard.press("End")
            jitter(2.0, 3.0)
            page.keyboard.press("Home")
            jitter(2.0, 3.0)
        except Exception as e:
            print(f"    End/Home error: {e}")

        # Approach 4: Wait and try PageUp again
        print("  Second round: PageUp × 5...")
        for i in range(5):
            try:
                page.keyboard.press("PageUp")
            except Exception:
                pass
            time.sleep(0.5)
        jitter(1.0, 1.5)

        print("  Waiting 6s for debounced queries...")
        time.sleep(6)

        # Check after first round
        mid_count = len(offmsys.pairs)
        print(f"  OffMsys pairs after keyboard round 1: {mid_count}")

        # If still nothing, try one more round with click on media image first
        if mid_count == 0:
            print("  Still nothing. Trying click on message pane + more keys...")
            try:
                first_img = page.locator('img[src*="cdninstagram.com"]').first
                if first_img.is_visible():
                    first_img.click()
                    jitter(0.5, 1.0)
            except Exception:
                pass

            for i in range(10):
                try:
                    page.keyboard.press("PageUp")
                except Exception:
                    pass
                time.sleep(0.3)
            jitter(1.0, 2.0)

            try:
                page.keyboard.press("End")
                jitter(2.0, 3.0)
                page.keyboard.press("Home")
                jitter(2.0, 3.0)
            except Exception:
                pass

            print("  Waiting 6s for debounced queries...")
            time.sleep(6)

        # ---- Results ----
        offmsys_count = len(offmsys.pairs)
        print(f"\n[3] Results:")
        print(f"  OffMsys pairs captured: {offmsys_count}")

        if offmsys_count == 0:
            print("\n*** NO OffMsys query captured! ***")
            print("Keyboard trigger did not work. Writing debug note.")

            # Write debug note
            debug_path = ARTIFACTS_DIR / "offmsys_response_debug.md"
            with open(debug_path, 'w') as f:
                f.write(f"# OffMsys Response Probe — FAILED\n\n")
                f.write(f"**Date:** {timestamp}\n")
                f.write(f"**Thread:** {THREAD_URL}\n")
                f.write(f"**Issue:** No IGDMessageListOffMsysQuery was captured.\n\n")
                f.write(f"**Thread state:** key={thread_key}, internal_id={thread_internal_id}, "
                       f"initial_messages={initial_count}, has_next_page={page_info.get('has_next_page') if page_info else 'N/A'}\n\n")
                f.write(f"**What was tried:**\n")
                f.write(f"- Navigated directly to bel's thread\n")
                f.write(f"- Waited 10-12s for settle\n")
                f.write(f"- Clicked media image to focus\n")
                f.write(f"- PageUp × 3 with 2s sleeps\n")
                f.write(f"- Waited 5s after\n\n")
                f.write(f"**All GraphQL queries captured by ThreadMessagesCapture:** {len(capture._pairs)}\n\n")
                f.write(f"**Escalation:** Keyboard trigger is not reliable for firing OffMsys query. "
                       f"May need different focus element or different key.\n")
            print(f"  Debug note: {debug_path}")

            browser.close()
            return

        # ---- Analyze the response shape ----
        first_pair = offmsys.pairs[0]
        response_body = first_pair["response_body"]

        print(f"\n[4] Analyzing OffMsys response shape...")
        print(f"  Response body top-level keys: {list(response_body.keys())}")

        # Save the first pair
        sample_path = ARTIFACTS_DIR / "offmsys_response_sample.json"
        with open(sample_path, 'w') as f:
            json.dump(first_pair, f, indent=2, ensure_ascii=False)
        print(f"  Sample saved: {sample_path}")

        # Walk the response to find message paths and page_info
        print(f"\n[5] Walking response to find messages and page_info...")
        hints = walk_response_paths(response_body)

        # Filter to the most relevant hints
        print(f"\n  --- Key paths in OffMsys response ---")
        message_paths = []
        page_info_paths = []
        for h in hints:
            if h["key"] in ("edges", "node", "message_id", "messages", "slide_messages"):
                message_paths.append(h)
            if h["key"] in ("page_info", "has_next_page", "end_cursor"):
                page_info_paths.append(h)

        print(f"\n  Message-related paths:")
        for h in message_paths:
            extra = ""
            if "length" in h:
                extra = f"  length={h['length']}"
            if "keys" in h:
                extra = f"  keys={h['keys']}"
            if h.get("sample"):
                extra = f"  sample={h['sample']}"
            print(f"    {h['path']} ({h['type']}){extra}")

        print(f"\n  Page-info-related paths:")
        for h in page_info_paths:
            extra = ""
            if h.get("sample"):
                extra = f"  value={h['sample']}"
            print(f"    {h['path']} ({h['type']}){extra}")

        # Identify the definitive paths
        # Find the edges list — it's where the messages live
        edges_hints = [h for h in hints if h["key"] == "edges" and h.get("length")]
        pi_hints = [h for h in hints if h["key"] == "page_info" and "keys" in h]

        print(f"\n  === DEFINITIVE PATHS ===")
        if edges_hints:
            best_edges = max(edges_hints, key=lambda h: h.get("length", 0))
            messages_path = best_edges["path"].rsplit(".edges", 1)[0]
            print(f"  Messages list: {best_edges['path']} ({best_edges['length']} items)")
            if "first_item_keys" in best_edges:
                print(f"    First edge keys: {best_edges['first_item_keys']}")
            # Walk one more level to find the actual message node
            edges_val = response_body
            for part in best_edges["path"].split("."):
                if "[" in part:
                    key, idx = part.split("[")
                    idx = int(idx.rstrip("]"))
                    edges_val = edges_val[key][idx]
                else:
                    edges_val = edges_val.get(part, {})
            if edges_val and len(edges_val) > 0:
                first_edge = edges_val[0]
                if isinstance(first_edge, dict):
                    print(f"    First edge keys: {list(first_edge.keys())}")
                    if "node" in first_edge:
                        node = first_edge["node"]
                        if isinstance(node, dict):
                            print(f"    Node keys: {list(node.keys())}")
                            if "message_id" in node:
                                print(f"    message_id format: {node['message_id']}")
                            if "content_type" in node:
                                print(f"    content_type: {node['content_type']}")
        else:
            print(f"  Messages list: NOT FOUND (check full response)")

        if pi_hints:
            for h in pi_hints:
                print(f"  Page info: {h['path']}  keys={h['keys']}")
        else:
            print(f"  Page info: NOT FOUND (check full response)")

        # Also print the full response structure at top 3 levels for reference
        print(f"\n  === Response structure (top-level) ===")

        def print_structure(obj, indent=2, max_depth=4, depth=0):
            prefix = " " * (indent + depth * 2)
            if depth > max_depth:
                return
            if isinstance(obj, dict):
                for k, v in obj.items():
                    if isinstance(v, dict):
                        print(f"{prefix}{k}: <dict> keys={list(v.keys())[:8]}")
                        print_structure(v, indent, max_depth, depth + 1)
                    elif isinstance(v, list):
                        print(f"{prefix}{k}: <list> len={len(v)}")
                        if len(v) > 0 and isinstance(v[0], dict):
                            print(f"{prefix}  [0]: <dict> keys={list(v[0].keys())[:8]}")
                    elif isinstance(v, str) and len(v) > 60:
                        print(f"{prefix}{k}: <str> = {v[:60]}...")
                    else:
                        print(f"{prefix}{k}: {v}")
            elif isinstance(obj, list):
                print(f"{' ' * indent} <list> len={len(obj)}")

        print_structure(response_body)

        browser.close()

    print("\n" + "=" * 60)
    print("PROBE COMPLETE")
    print("=" * 60)

    if offmsys.pairs:
        print(f"Captured {len(offmsys.pairs)} OffMsys pair(s)")
        print(f"Sample: {sample_path}")
        print(f"\nNext: Use the response shape to update scanner/capture.py")
    else:
        print("No OffMsys data captured. Keyboard trigger not reliable.")
        print("Escalate to orchestrator.")


if __name__ == "__main__":
    main()
