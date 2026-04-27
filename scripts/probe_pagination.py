#!/usr/bin/env python3
"""
Pagination Probe — Discover which interaction triggers IG's paginated GraphQL queries.

Phase A of Prompt 3.6. Navigates directly to bel's thread (skip inbox to avoid
preload contamination), then tests 6 scroll/interaction strategies one at a time.
Logs before/after IGDThreadDetailMainViewContainerQuery counts for each strategy.

Ref: CLAUDE.md guardrails — headed browser, human-like pacing, blocker detection.
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

import json
import os
import random
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs

try:
    import camoufox
except ImportError:
    print("ERROR: Camoufox is not installed!")
    print("Install with: pip install camoufox[geoip]")
    sys.exit(1)

# Reuse the capture class from scanner
sys.path.insert(0, str(Path(__file__).parent.parent))
from scanner.capture import ThreadMessagesCapture


EXPECTED_THREAD_FBID = "110975426965828"
THREAD_URL = f"https://www.instagram.com/direct/t/{EXPECTED_THREAD_FBID}/"
COOKIE_PATH = Path(__file__).parent.parent / "test-cookies" / "cookies.json"
ARTIFACTS_DIR = Path(__file__).parent.parent / "artifacts"


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
        checkpoint = page.locator("text=Check Your Information").count()
        if checkpoint > 0:
            return True, "Checkpoint/Verification required"
        suspicious = page.locator("text=suspicious login attempt").count()
        if suspicious > 0:
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


def count_bel_queries(capture: ThreadMessagesCapture) -> int:
    """Count how many IGDThreadDetailMainViewContainerQuery pairs we have for bel's thread."""
    extracted = capture.extract_messages()
    return len(extracted["messages"])


def get_latest_query_variables(capture: ThreadMessagesCapture):
    """Return variables dict from the most recent bel-query, or None."""
    # Pairs are (request, response). Last pair is most recent.
    for req, resp in reversed(capture._pairs):
        req_vars = req.get("variables") or {}
        if req_vars.get("thread_fbid") == EXPECTED_THREAD_FBID:
            return req_vars
    return None


def find_scrollable_container(page):
    """Strategy 2: walk up from a media image to find the actual scrollable container.

    Returns a dict with selector info, or None.
    """
    result = page.evaluate("""() => {
        const img = document.querySelector('img[src*="cdninstagram.com"]');
        if (!img) return null;

        const path = [];
        let el = img.parentElement;
        while (el && el !== document.body) {
            const style = window.getComputedStyle(el);
            const info = {
                tag: el.tagName.toLowerCase(),
                id: el.id || null,
                className: el.className || null,
                overflowY: style.overflowY,
                overflow: style.overflow,
                scrollHeight: el.scrollHeight,
                clientHeight: el.clientHeight,
                scrollTop: el.scrollTop,
                scrollTopMax: el.scrollHeight - el.clientHeight,
            };
            path.push(info);
            el = el.parentElement;
        }
        return path;
    }""")
    return result


def scroll_container_by_js(page, container_selector, delta_y, steps=3):
    """Scroll a container upward using JS scrollBy in steps."""
    for _ in range(steps):
        try:
            page.evaluate(f"""() => {{
                const el = document.querySelector('{container_selector}');
                if (el) el.scrollBy(0, {delta_y});
            }}""")
        except Exception:
            pass
        jitter(0.5, 1.0)


def dispatch_wheel_events(page, container_selector, delta_y, count=10):
    """Dispatch wheel events on a container."""
    for _ in range(count):
        try:
            page.evaluate(f"""() => {{
                const el = document.querySelector('{container_selector}');
                if (!el) return;
                const rect = el.getBoundingClientRect();
                const cx = rect.left + rect.width / 2;
                const cy = rect.top + rect.height / 2;
                el.dispatchEvent(new WheelEvent('wheel', {{
                    deltaY: {delta_y},
                    deltaMode: 0,
                    bubbles: true,
                    cancelable: true,
                    clientX: cx,
                    clientY: cy,
                }}));
            }}""")
        except Exception:
            pass
        jitter(0.3, 0.5)


def send_pageup_keys(page, count=10):
    """Send PageUp keyboard events."""
    for _ in range(count):
        try:
            page.keyboard.press("PageUp")
        except Exception:
            pass
        jitter(0.5, 0.8)


def playwright_mouse_wheel(page, delta_y):
    """Use Playwright's built-in mouse.wheel method."""
    try:
        page.mouse.wheel(0, delta_y)
    except Exception:
        pass


def scroll_into_view_topmost(page):
    """Find the topmost visible message node and scroll it into view."""
    result = page.evaluate("""() => {
        // Try to find message elements — look for elements containing media links
        const allNodes = document.querySelectorAll('a[href*="/reel/"], a[href*="/p/"]');
        if (allNodes.length === 0) return null;

        // Find the one with the smallest bounding rect top (topmost visible)
        let topmost = null;
        let minTop = Infinity;
        for (const node of allNodes) {
            const rect = node.getBoundingClientRect();
            if (rect.top < minTop && rect.top > -1000) {
                minTop = rect.top;
                topmost = node;
            }
        }
        if (topmost) {
            topmost.scrollIntoView({block: 'start', behavior: 'instant'});
            return {tag: topmost.tagName, top: minTop};
        }
        return null;
    }""")
    return result


def build_selector_from_path(ancestor_path):
    """From the DOM path, find the best scrollable container and return a CSS selector."""
    if not ancestor_path:
        return None
    for info in ancestor_path:
        if info["overflowY"] in ("auto", "scroll") and info["scrollHeight"] > info["clientHeight"]:
            if info["id"]:
                return f"#{info['id']}"
            # Build a class-based selector
            tag = info["tag"]
            if info["className"]:
                # Use first non-trivial class
                classes = [c for c in info["className"].split() if len(c) > 2 and not c.startswith("_")]
                if classes:
                    return f"{tag}.{classes[0]}"
            return tag
    return None


def main():
    print("=" * 60)
    print("Pagination Probe — Prompt 3.6 Phase A")
    print(f"Thread: {THREAD_URL}")
    print(f"Expected thread_fbid: {EXPECTED_THREAD_FBID}")
    print("=" * 60)

    os.makedirs(ARTIFACTS_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    capture = ThreadMessagesCapture(expected_thread_fbid=EXPECTED_THREAD_FBID)

    with camoufox.Camoufox(headless=False) as browser:
        context = browser.new_context(viewport={"width": 1528, "height": 794})
        page = context.new_page()

        page.on("request", capture.on_request)
        page.on("response", capture.on_response)

        cookies = load_cookies(str(COOKIE_PATH))
        context.add_cookies(cookies)
        print(f"\nLoaded {len(cookies)} cookies")

        # Navigate DIRECTLY to thread — skip inbox
        print(f"\n[1/7] Navigating directly to thread (no inbox)...")
        page.goto(THREAD_URL, timeout=60000, wait_until="domcontentloaded")
        jitter(4.0, 5.0)

        blocked, reason = check_blockers(page)
        if blocked:
            ss_path = ARTIFACTS_DIR / f"pagination_probe_blocker_{timestamp}.png"
            page.screenshot(path=str(ss_path))
            print(f"BLOCKER: {reason}")
            print(f"Screenshot: {ss_path}")
            return

        dismiss_overlays(page)

        # Settle — let initial queries fire
        print("  Waiting for initial queries to settle (8-12s)...")
        jitter(8.0, 12.0)

        initial_count = count_bel_queries(capture)
        print(f"  Initial bel-query messages: {initial_count}")

        # Extract page_info from initial load
        extracted = capture.extract_messages()
        initial_page_info = extracted["page_info"]
        print(f"  Initial page_info: {json.dumps(initial_page_info)}")

        if initial_page_info and not initial_page_info.get("has_next_page", True):
            print("\n*** has_next_page is FALSE on initial load. This thread genuinely has <= 20 messages. ***")
            print("Probe will still test strategies but pagination may not be possible.")

        # Find the scrollable container (Strategy 2 data collection)
        print(f"\n[2/7] Finding scrollable container (DOM walk from media image)...")
        dom_path = find_scrollable_container(page)
        container_selector = build_selector_from_path(dom_path)

        print(f"  DOM path depth: {len(dom_path) if dom_path else 0} ancestors")
        if dom_path:
            for i, info in enumerate(dom_path[:8]):
                print(f"    [{i}] <{info['tag']}> id={info['id']} class={info['className'][:60] if info['className'] else None}")
                print(f"        overflowY={info['overflowY']} overflow={info['overflow']} "
                      f"scrollHeight={info['scrollHeight']} clientHeight={info['clientHeight']} "
                      f"scrollTopMax={info['scrollTopMax']}")
        print(f"  Best scrollable container selector: {container_selector}")

        if not container_selector:
            print("  WARNING: Could not find scrollable container. Using fallback selectors.")
            container_selector = '[data-pagelet="IGDMessagesList"]'

        # Screenshot initial state
        initial_ss = ARTIFACTS_DIR / f"pagination_probe_initial_{timestamp}.png"
        page.screenshot(path=str(initial_ss))
        print(f"  Screenshot: {initial_ss}")

        # --- Strategy results accumulator ---
        strategy_results = []
        all_traffic_snapshots = []

        # Helper to run a strategy
        def run_strategy(name, action):
            nonlocal initial_count
            before = count_bel_queries(capture)
            print(f"\n--- Strategy: {name} ---")
            print(f"  Messages before: {before}")
            action()
            # Settle for network traffic
            jitter(3.0, 4.0)
            after = count_bel_queries(capture)
            delta = after - before

            new_vars = None
            if delta > 0:
                new_vars = get_latest_query_variables(capture)
                print(f"  *** NEW QUERIES FIRED! Delta: +{delta} ***")
                print(f"  Latest query variables: {json.dumps(new_vars)}")
            else:
                print(f"  No new queries. Delta: 0")

            strategy_results.append({
                "name": name,
                "before": before,
                "after": after,
                "delta": delta,
                "container_selector": container_selector,
                "new_query_variables": new_vars,
            })

            # Snapshot full capture state
            all_traffic_snapshots.append({
                "strategy": name,
                "message_count": after,
                "page_info": capture.extract_messages().get("page_info"),
                "new_variables": new_vars,
            })

            return delta

        # Strategy 1: JS scrollTop on data-pagelet container
        def s1():
            sel = '[data-pagelet="IGDMessagesList"]'
            try:
                page.evaluate(f"""() => {{
                    const el = document.querySelector('{sel}');
                    if (el) el.scrollTop = 0;
                }}""")
                jitter(1.0, 1.5)
                scroll_container_by_js(page, sel, -800, steps=5)
                jitter(2.0, 3.0)
            except Exception as e:
                print(f"  Error: {e}")

        run_strategy("1. JS scrollTop on [data-pagelet=IGDMessagesList]", s1)

        # Strategy 2: JS scrollTop on actual scrollable ancestor (the critical one)
        def s2():
            if not container_selector:
                print("  SKIP: no container selector found")
                return
            try:
                # Reset scroll to top first, then scroll up in chunks
                page.evaluate(f"""() => {{
                    const el = document.querySelector('{container_selector}');
                    if (el) el.scrollTop = 0;
                }}""")
                jitter(1.0, 1.5)
                scroll_container_by_js(page, container_selector, -800, steps=5)
                jitter(2.0, 3.0)
            except Exception as e:
                print(f"  Error: {e}")

        run_strategy("2. JS scrollTop on actual scrollable ancestor", s2)

        # Strategy 3: Mouse wheel events
        def s3():
            if not container_selector:
                print("  SKIP: no container selector found")
                return
            dispatch_wheel_events(page, container_selector, -300, count=10)
            jitter(2.0, 3.0)

        run_strategy("3. Wheel events on scrollable container", s3)

        # Strategy 4: Keyboard PageUp
        def s4():
            send_pageup_keys(page, count=10)
            jitter(2.0, 3.0)

        run_strategy("4. Keyboard PageUp", s4)

        # Strategy 5: Playwright mouse.wheel
        def s5():
            playwright_mouse_wheel(page, -300)
            jitter(1.0, 1.5)
            playwright_mouse_wheel(page, -300)
            jitter(1.0, 1.5)
            playwright_mouse_wheel(page, -300)
            jitter(2.0, 3.0)

        run_strategy("5. Playwright mouse.wheel", s5)

        # Strategy 6: scrollIntoView of topmost message
        def s6():
            result = scroll_into_view_topmost(page)
            if result:
                print(f"  Scrolled topmost element: {result}")
            else:
                print("  No media link elements found to scroll to")
            jitter(2.0, 3.0)

        run_strategy("6. scrollIntoView of topmost message", s6)

        # Final screenshot
        final_ss = ARTIFACTS_DIR / f"pagination_probe_final_{timestamp}.png"
        page.screenshot(path=str(final_ss))
        print(f"\nFinal screenshot: {final_ss}")

        # Final counts
        final_count = count_bel_queries(capture)
        final_extracted = capture.extract_messages()
        print(f"\nFinal bel-query message count: {final_count}")
        print(f"Final page_info: {json.dumps(final_extracted.get('page_info'))}")

        browser.close()

    # --- Write artifacts ---
    print("\n" + "=" * 60)
    print("Writing artifacts...")

    # 1. Markdown report
    md_path = ARTIFACTS_DIR / "pagination_probe.md"
    md_lines = [
        f"# Pagination Probe Report",
        f"",
        f"**Date:** {timestamp}",
        f"**Thread:** {THREAD_URL}",
        f"**Expected thread_fbid:** {EXPECTED_THREAD_FBID}",
        f"",
        f"## Initial State",
        f"",
        f"- Initial messages: {initial_count}",
        f"- Initial page_info: `{json.dumps(initial_page_info)}`",
        f"- Container selector found: `{container_selector}`",
        f"",
        f"## DOM Path (scrollable container discovery)",
        f"",
    ]
    if dom_path:
        md_lines.append("| Depth | Tag | ID | OverflowY | scrollHeight | clientHeight | scrollTopMax |")
        md_lines.append("|-------|-----|----|-----------|-------------|-------------|-------------|")
        for i, info in enumerate(dom_path[:15]):
            md_lines.append(f"| {i} | `<{info['tag']}>` | {info['id'] or '-'} | "
                           f"{info['overflowY']} ({info['overflow']}) | "
                           f"{info['scrollHeight']} | {info['clientHeight']} | {info['scrollTopMax']} |")
    else:
        md_lines.append("(No DOM path — no media images found)")

    md_lines.extend([
        "",
        "## Strategy Results",
        "",
        "| # | Strategy | Before | After | Delta |",
        "|---|----------|--------|-------|-------|",
    ])
    for r in strategy_results:
        md_lines.append(f"| {r['name']} | {r['before']} | {r['after']} | {r['delta']} |")

    md_lines.extend([
        "",
        "## Conclusion",
        "",
    ])

    any_worked = any(r["delta"] > 0 for r in strategy_results)
    if any_worked:
        working = [r for r in strategy_results if r["delta"] > 0]
        md_lines.append(f"**SUCCESS:** {len(working)} strategy(s) triggered paginated queries.")
        for w in working:
            md_lines.append(f"- {w['name']}: +{w['delta']} new messages")
            if w["new_query_variables"]:
                md_lines.append(f"  ```json")
                md_lines.append(f"  {json.dumps(w['new_query_variables'])}")
                md_lines.append(f"  ```")
    else:
        md_lines.append("**No strategy triggered paginated queries.**")
        if initial_page_info and not initial_page_info.get("has_next_page"):
            md_lines.append("`has_next_page` was `false` on initial load — this thread genuinely has <= 20 messages.")
        else:
            md_lines.append("`has_next_page` was `true` but no interaction triggered the next query. Further investigation needed.")

    md_lines.extend([
        "",
        f"## Artifacts",
        f"",
        f"- Screenshots: `pagination_probe_initial_{timestamp}.png`, `pagination_probe_final_{timestamp}.png`",
        f"- Traffic: `pagination_probe_traffic.json`",
    ])

    with open(md_path, 'w') as f:
        f.write('\n'.join(md_lines))
    print(f"  Report: {md_path}")

    # 2. Traffic JSON
    traffic_path = ARTIFACTS_DIR / "pagination_probe_traffic.json"
    traffic_data = {
        "probe_timestamp": timestamp,
        "thread_url": THREAD_URL,
        "expected_thread_fbid": EXPECTED_THREAD_FBID,
        "initial_message_count": initial_count,
        "initial_page_info": initial_page_info,
        "dom_path": dom_path,
        "container_selector": container_selector,
        "strategy_results": strategy_results,
        "final_message_count": final_count,
        "final_page_info": final_extracted.get("page_info"),
        "all_pairs_summary": [
            {
                "thread_fbid": r.get("variables", {}).get("thread_fbid"),
                "has_cursor": "cursor" in (r.get("variables", {}) or {}),
                "variables": r.get("variables"),
            }
            for r, _ in capture._pairs
        ],
    }
    with open(traffic_path, 'w') as f:
        json.dump(traffic_data, f, indent=2, ensure_ascii=False)
    print(f"  Traffic: {traffic_path}")

    # 3. Screenshot already saved above; copy to the canonical name
    import shutil
    final_copy = ARTIFACTS_DIR / "pagination_probe_screenshot.png"
    shutil.copy(str(final_ss), str(final_copy))
    print(f"  Screenshot: {final_copy}")

    print("\n" + "=" * 60)
    print("PROBE COMPLETE")
    print("=" * 60)
    if any_worked:
        print(f"Pagination TRIGGERED by: {', '.join(r['name'] for r in strategy_results if r['delta'] > 0)}")
        print("Proceed to Phase B: update handle_pagination() in scanner.py")
    else:
        print("No pagination strategy worked.")
        if initial_page_info and not initial_page_info.get("has_next_page"):
            print("Root cause: has_next_page=false. Bel's thread has <= 20 messages total.")
        else:
            print("Root cause unknown. has_next_page=true but no interaction triggers the next query.")


if __name__ == "__main__":
    main()
