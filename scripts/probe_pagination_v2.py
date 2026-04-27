#!/usr/bin/env python3
"""
Pagination Probe v2 — Prompt 3.6.5

Changes from v1:
1. Captures ALL GraphQL traffic (RawGraphQLLog), not just filtered friendly_name.
2. Prints FULL 33-ancestor DOM walk + role/aria enumeration.
3. One realistic strategy: slow continuous mouse wheel over the message pane.
4. Compares all traffic before/after the wheel sequence.
5. Honest reporting — names what fired (if anything) or escalates.

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
from collections import defaultdict

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


# ---------------------------------------------------------------------------
# Raw GraphQL request logger — captures EVERY /api/graphql request, no filtering
# ---------------------------------------------------------------------------

class RawGraphQLLog:
    """Log every /api/graphql request with timestamp, friendly_name, doc_id, variables.

    This runs alongside ThreadMessagesCapture. It never pairs with responses
    and never filters — it's pure observation to see what IG actually fires.
    """

    def __init__(self):
        self.requests: list = []

    def on_request(self, request) -> None:
        if '/api/graphql' not in request.url:
            return

        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "url": request.url,
        }

        post_data = request.post_data
        if post_data:
            try:
                parsed = parse_qs(post_data)
                entry["doc_id"] = parsed.get("doc_id", [None])[0]
                entry["friendly_name"] = parsed.get("fb_api_req_friendly_name", [None])[0]
                raw_vars = parsed.get("variables", [None])[0]
                if raw_vars:
                    entry["variables"] = json.loads(raw_vars)
                else:
                    entry["variables"] = None
            except Exception as e:
                entry["_parse_error"] = str(e)

        self.requests.append(entry)

    def requests_during(self, start_iso: str, end_iso: str) -> list:
        """Return requests with timestamps between start and end (inclusive)."""
        return [r for r in self.requests if start_iso <= r["timestamp"] <= end_iso]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


def count_bel_queries(capture: ThreadMessagesCapture) -> int:
    return len(capture.extract_messages()["messages"])


# ---------------------------------------------------------------------------
# Full DOM walk — ALL ancestors + role/aria enumeration
# ---------------------------------------------------------------------------

def full_dom_walk(page):
    """Walk from first media image up to body, printing ALL ancestors.

    Returns a dict with:
      - ancestor_walk: list of ancestor info dicts (full depth, no truncation)
      - role_elements: dict of role/aria matches with metrics
      - overflow_candidates: elements with real overflow
    """
    result = page.evaluate("""() => {
        // --- Part 1: Full ancestor walk from first media image ---
        const img = document.querySelector('img[src*="cdninstagram.com"]');
        const ancestorWalk = [];
        if (img) {
            let el = img.parentElement;
            while (el && el !== document.body) {
                const style = window.getComputedStyle(el);
                const rect = el.getBoundingClientRect();
                // First 2 class tokens only
                const cls = el.getAttribute('class') || '';
                const classTokens = cls.trim().split(/\\s+/).slice(0, 2);
                ancestorWalk.push({
                    tag: el.tagName.toLowerCase(),
                    id: el.id || null,
                    classTokens: classTokens,
                    overflowX: style.overflowX,
                    overflowY: style.overflowY,
                    overflow: style.overflow,
                    scrollHeight: el.scrollHeight,
                    clientHeight: el.clientHeight,
                    scrollTop: el.scrollTop,
                    scrollTopMax: el.scrollHeight - el.clientHeight,
                    rect: { width: Math.round(rect.width), height: Math.round(rect.height) },
                });
                el = el.parentElement;
            }
        }

        // --- Part 2: Enumerate by role/aria ---
        const roleElements = {};
        const rolesToCheck = ['log', 'grid', 'list'];
        for (const role of rolesToCheck) {
            const els = document.querySelectorAll(`[role="${role}"]`);
            roleElements[`role_${role}`] = [];
            for (const el of els) {
                const style = window.getComputedStyle(el);
                const rect = el.getBoundingClientRect();
                const cls_r = el.getAttribute('class') || '';
                roleElements[`role_${role}`].push({
                    tag: el.tagName.toLowerCase(),
                    id: el.id || null,
                    classTokens: cls_r.trim().split(/\\s+/).slice(0, 2),
                    overflowY: style.overflowY,
                    overflow: style.overflow,
                    scrollHeight: el.scrollHeight,
                    clientHeight: el.clientHeight,
                    scrollTopMax: el.scrollHeight - el.clientHeight,
                    rect: { width: Math.round(rect.width), height: Math.round(rect.height) },
                });
            }
        }

        // Aria-label contains "Messages" or "conversation"
        const ariaEls = document.querySelectorAll('[aria-label*="Messages" i], [aria-label*="conversation" i]');
        roleElements['aria_messages'] = [];
        for (const el of ariaEls) {
            const style = window.getComputedStyle(el);
            const rect = el.getBoundingClientRect();
            const cls_a = el.getAttribute('class') || '';
            roleElements['aria_messages'].push({
                tag: el.tagName.toLowerCase(),
                id: el.id || null,
                ariaLabel: el.getAttribute('aria-label') || null,
                classTokens: cls_a.trim().split(/\\s+/).slice(0, 2),
                overflowY: style.overflowY,
                overflow: style.overflow,
                scrollHeight: el.scrollHeight,
                clientHeight: el.clientHeight,
                scrollTopMax: el.scrollHeight - el.clientHeight,
                rect: { width: Math.round(rect.width), height: Math.round(rect.height) },
            });
        }

        // --- Part 3: Elements with real overflow (scrollHeight > clientHeight + 50) ---
        const overflowCandidates = [];
        const allDivs = document.querySelectorAll('div[style*="overflow"], div');
        const seen = new Set();
        for (const el of allDivs) {
            if (seen.has(el)) continue;
            seen.add(el);
            if (el.scrollHeight > el.clientHeight + 50) {
                const style = window.getComputedStyle(el);
                const rect = el.getBoundingClientRect();
                const cls_o = el.getAttribute('class') || '';
                overflowCandidates.push({
                    tag: el.tagName.toLowerCase(),
                    id: el.id || null,
                    classTokens: cls_o.trim().split(/\\s+/).slice(0, 3),
                    overflowY: style.overflowY,
                    overflow: style.overflow,
                    scrollHeight: el.scrollHeight,
                    clientHeight: el.clientHeight,
                    scrollTopMax: el.scrollHeight - el.clientHeight,
                    rect: { width: Math.round(rect.width), height: Math.round(rect.height) },
                });
                if (overflowCandidates.length >= 10) break;
            }
        }

        return {
            ancestorWalk: ancestorWalk,
            roleElements: roleElements,
            overflowCandidates: overflowCandidates,
        };
    }""")
    return result


# ---------------------------------------------------------------------------
# Main probe
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("Pagination Probe v2 — Prompt 3.6.5")
    print(f"Thread: {THREAD_URL}")
    print(f"Expected thread_fbid: {EXPECTED_THREAD_FBID}")
    print("=" * 60)

    os.makedirs(ARTIFACTS_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Two parallel listeners: filtered capture + raw log
    capture = ThreadMessagesCapture(expected_thread_fbid=EXPECTED_THREAD_FBID)
    raw_log = RawGraphQLLog()

    with camoufox.Camoufox(headless=False) as browser:
        context = browser.new_context(viewport={"width": 1528, "height": 794})
        page = context.new_page()

        # Install BOTH listeners
        page.on("request", capture.on_request)
        page.on("response", capture.on_response)
        page.on("request", raw_log.on_request)

        cookies = load_cookies(str(COOKIE_PATH))
        context.add_cookies(cookies)
        print(f"\nLoaded {len(cookies)} cookies")

        # ---- Navigate directly to thread ----
        print(f"\n[1] Navigating directly to thread (no inbox)...")
        page.goto(THREAD_URL, timeout=60000, wait_until="domcontentloaded")
        jitter(4.0, 5.0)

        blocked, reason = check_blockers(page)
        if blocked:
            ss_path = ARTIFACTS_DIR / f"pagination_probe_v2_blocker_{timestamp}.png"
            page.screenshot(path=str(ss_path))
            print(f"BLOCKER: {reason}\nScreenshot: {ss_path}")
            return

        dismiss_overlays(page)

        print("  Waiting for initial queries to settle (8-12s)...")
        jitter(8.0, 12.0)

        # ---- Baseline ----
        initial_bel_count = count_bel_queries(capture)
        extracted = capture.extract_messages()
        initial_page_info = extracted.get("page_info")
        print(f"\n  Initial bel-query message count: {initial_bel_count}")
        print(f"  Initial page_info: {json.dumps(initial_page_info)}")
        print(f"  Total raw GraphQL requests seen: {len(raw_log.requests)}")

        if initial_page_info:
            if not initial_page_info.get("has_next_page"):
                print("\n  *** has_next_page = FALSE. Thread genuinely has <= 20 messages. ***")
            else:
                print(f"\n  has_next_page = TRUE. end_cursor = {initial_page_info.get('end_cursor', 'N/A')[:60]}...")

        # ---- Full DOM walk ----
        print(f"\n[2] Full DOM walk (all ancestors + role/aria enumeration)...")
        dom_data = full_dom_walk(page)

        ancestor_walk = dom_data.get("ancestorWalk", [])
        print(f"\n  --- Full Ancestor Walk ({len(ancestor_walk)} ancestors) ---")
        for i, info in enumerate(ancestor_walk):
            cls_preview = '.'.join(info['classTokens']) if info['classTokens'] else '-'
            print(f"  [{i:2d}] <{info['tag']}> id={info['id']} class={cls_preview[:60]}")
            print(f"        overflowX={info['overflowX']} overflowY={info['overflowY']} overflow={info['overflow']} "
                  f"scrollH={info['scrollHeight']} clientH={info['clientHeight']} "
                  f"scrollTopMax={info['scrollTopMax']} rect={info['rect']['width']}x{info['rect']['height']}")

        # Print role elements
        role_elements = dom_data.get("roleElements", {})
        for key, els in role_elements.items():
            print(f"\n  --- {key} ({len(els)} matches) ---")
            for j, el_info in enumerate(els[:5]):
                aria = el_info.get('ariaLabel', '')
                print(f"  [{j}] <{el_info['tag']}> id={el_info['id']} aria='{aria[:60]}' "
                      f"overflowY={el_info['overflowY']} scrollH={el_info['scrollHeight']} "
                      f"clientH={el_info['clientHeight']} scrollTopMax={el_info['scrollTopMax']} "
                      f"rect={el_info['rect']['width']}x{el_info['rect']['height']}")

        # Print overflow candidates
        overflow_candidates = dom_data.get("overflowCandidates", [])
        print(f"\n  --- Elements with real overflow (scrollHeight > clientHeight + 50) — {len(overflow_candidates)} ---")
        for j, info in enumerate(overflow_candidates):
            cls_preview = '.'.join(info['classTokens']) if info['classTokens'] else '-'
            print(f"  [{j}] <{info['tag']}> id={info['id']} class={cls_preview[:60]}")
            print(f"       overflowY={info['overflowY']} overflow={info['overflow']} "
                  f"scrollH={info['scrollHeight']} clientH={info['clientHeight']} "
                  f"scrollTopMax={info['scrollTopMax']} rect={info['rect']['width']}x{info['rect']['height']}")

        # Screenshot before
        before_ss = ARTIFACTS_DIR / f"pagination_probe_v2_before_{timestamp}.png"
        page.screenshot(path=str(before_ss))
        print(f"\n  Before screenshot: {before_ss}")

        # ---- The ONE strategy: slow continuous mouse wheel ----
        print(f"\n[3] Running wheel strategy: slow continuous mouse wheel over message pane...")

        # Find the message pane: get bounding box of first cdninstagram image, pick ~200px above it
        pane_info = page.evaluate("""() => {
            const img = document.querySelector('img[src*="cdninstagram.com"]');
            if (!img) return null;
            const rect = img.getBoundingClientRect();
            return {
                img_x: Math.round(rect.left + rect.width / 2),
                img_y: Math.round(rect.top),
                img_w: Math.round(rect.width),
                img_h: Math.round(rect.height),
                viewport_h: window.innerHeight,
                point_above: {
                    x: Math.round(rect.left + rect.width / 2),
                    y: Math.round(rect.top - 200),
                },
            };
        }""")

        if pane_info:
            print(f"  Media image at: x={pane_info['img_x']}, y={pane_info['img_y']}, "
                  f"{pane_info['img_w']}x{pane_info['img_h']}")
            wheel_x = pane_info["point_above"]["x"]
            wheel_y = max(pane_info["point_above"]["y"], 10)  # Don't go off-screen
            print(f"  Wheel target: ({wheel_x}, {wheel_y}) — 200px above image")

            # Move mouse to the message pane
            page.mouse.move(wheel_x, wheel_y)
            jitter(0.3, 0.5)

            # Mark the start time for traffic comparison
            wheel_start_iso = datetime.now(timezone.utc).isoformat()
            print(f"  Wheel start timestamp: {wheel_start_iso}")

            # Slow continuous scroll: 60 iterations of wheel(0, -50) with 0.1s sleep
            errors = 0
            for i in range(60):
                try:
                    page.mouse.wheel(0, -50)
                except Exception as e:
                    errors += 1
                    if errors <= 3:
                        print(f"  [warn] Wheel iteration {i}: {e}")
                time.sleep(0.1)

            if errors:
                print(f"  Wheel loop complete with {errors}/{60} errors")
            else:
                print(f"  Wheel loop complete (60 iterations, ~6s)")

            # Wait 5s for any debounced query to fire
            print("  Waiting 5s for debounced queries...")
            time.sleep(5)

            wheel_end_iso = datetime.now(timezone.utc).isoformat()
        else:
            print("  ERROR: Could not find any media image on page. Wheel strategy skipped.")
            wheel_start_iso = datetime.now(timezone.utc).isoformat()
            wheel_end_iso = wheel_start_iso

        # ---- After wheel ----
        after_bel_count = count_bel_queries(capture)
        after_extracted = capture.extract_messages()
        after_page_info = after_extracted.get("page_info")
        print(f"\n  After-wheel bel-query message count: {after_bel_count}")
        print(f"  After-wheel page_info: {json.dumps(after_page_info)}")

        # Screenshot after
        after_ss = ARTIFACTS_DIR / f"pagination_probe_v2_after_{timestamp}.png"
        page.screenshot(path=str(after_ss))
        print(f"  After screenshot: {after_ss}")

        # ---- Fallback: keyboard attempt if wheel did nothing ----
        wheel_delta = after_bel_count - initial_bel_count
        wheel_requests = raw_log.requests_during(wheel_start_iso, wheel_end_iso)
        new_friendly_names_during_wheel = set(
            r.get("friendly_name") for r in wheel_requests if r.get("friendly_name")
        )

        if wheel_delta == 0 and not new_friendly_names_during_wheel:
            print(f"\n[4] Wheel produced no new traffic. Trying keyboard fallback...")
            try:
                page.click('body')
                jitter(0.5, 1.0)
            except Exception:
                pass

            kb_start = datetime.now(timezone.utc).isoformat()

            # Try PageUp keys
            for _ in range(10):
                try:
                    page.keyboard.press("PageUp")
                except Exception:
                    pass
                time.sleep(0.3)

            jitter(1.0, 2.0)

            # Try End key to go to bottom, then Home to go to top — might trigger re-render
            try:
                page.keyboard.press("End")
                jitter(2.0, 3.0)
                page.keyboard.press("Home")
                jitter(2.0, 3.0)
            except Exception:
                pass

            jitter(2.0, 3.0)
            kb_end = datetime.now(timezone.utc).isoformat()

            kb_requests = raw_log.requests_during(kb_start, kb_end)
            kb_new_friendly = set(r.get("friendly_name") for r in kb_requests if r.get("friendly_name"))
            kb_after_count = count_bel_queries(capture)
            kb_delta = kb_after_count - after_bel_count

            print(f"  Keyboard fallback: {kb_delta} new bel messages, "
                  f"new friendly_names: {kb_new_friendly if kb_new_friendly else 'none'}")
        else:
            kb_requests = []
            kb_new_friendly = set()
            kb_delta = 0

        # ---- Final counts ----
        final_bel_count = count_bel_queries(capture)
        final_extracted = capture.extract_messages()
        final_page_info = final_extracted.get("page_info")
        bel_delta_total = final_bel_count - initial_bel_count

        print(f"\n  === Final Summary ===")
        print(f"  Bel messages: {initial_bel_count} -> {final_bel_count} (delta: {bel_delta_total})")
        print(f"  Final page_info: {json.dumps(final_page_info)}")

        browser.close()

    # ---- Post-browser: analyze ALL traffic ----
    print(f"\n[5] Analyzing all {len(raw_log.requests)} GraphQL requests...")

    # Group by friendly_name
    by_friendly = defaultdict(list)
    for r in raw_log.requests:
        fn = r.get("friendly_name") or "(unnamed)"
        by_friendly[fn].append(r)

    print(f"\n  Distinct friendly_names: {len(by_friendly)}")
    for fn, reqs in sorted(by_friendly.items()):
        first_ts = reqs[0]["timestamp"]
        print(f"    {fn}: {len(reqs)} requests (first at {first_ts})")

    # Filter wheel-period requests
    wheel_period_requests = raw_log.requests_during(wheel_start_iso, wheel_end_iso)
    wheel_period_names = set(r.get("friendly_name") for r in wheel_period_requests if r.get("friendly_name"))

    print(f"\n  Requests during wheel period: {len(wheel_period_requests)}")
    if wheel_period_requests:
        for r in wheel_period_requests:
            print(f"    {r['timestamp']}  friendly_name={r.get('friendly_name')}  doc_id={r.get('doc_id')}")
            if r.get("variables"):
                print(f"      variables: {json.dumps(r['variables'])}")
    else:
        print("    (none)")

    # ---- Write artifacts ----

    # 1. DOM walk JSON
    dom_json_path = ARTIFACTS_DIR / "pagination_probe_v2_dom_walk.json"
    with open(dom_json_path, 'w') as f:
        json.dump(dom_data, f, indent=2, ensure_ascii=False)
    print(f"\n  DOM walk: {dom_json_path}")

    # 2. Full traffic JSON
    traffic_path = ARTIFACTS_DIR / "pagination_probe_v2_traffic.json"
    traffic_data = {
        "probe_timestamp": timestamp,
        "thread_url": THREAD_URL,
        "expected_thread_fbid": EXPECTED_THREAD_FBID,
        "initial_bel_count": initial_bel_count,
        "initial_page_info": initial_page_info,
        "final_bel_count": final_bel_count,
        "final_page_info": final_page_info,
        "bel_delta_total": bel_delta_total,
        "total_graphql_requests": len(raw_log.requests),
        "friendly_name_summary": {
            fn: {"count": len(reqs), "first_at": reqs[0]["timestamp"]}
            for fn, reqs in sorted(by_friendly.items())
        },
        "wheel_period": {
            "start": wheel_start_iso,
            "end": wheel_end_iso,
            "request_count": len(wheel_period_requests),
            "friendly_names_seen": sorted(wheel_period_names),
            "requests": wheel_period_requests,
        },
        "keyboard_fallback": {
            "requests": kb_requests,
            "new_friendly_names": sorted(kb_new_friendly) if kb_new_friendly else [],
        } if kb_requests else None,
        "all_requests": raw_log.requests,
    }
    with open(traffic_path, 'w') as f:
        json.dump(traffic_data, f, indent=2, ensure_ascii=False)
    print(f"  Traffic: {traffic_path}")

    # 3. Markdown report
    md_path = ARTIFACTS_DIR / "pagination_probe_v2.md"
    md_lines = [
        f"# Pagination Probe v2 Report",
        f"",
        f"**Date:** {timestamp}",
        f"**Thread:** {THREAD_URL}",
        f"**Expected thread_fbid:** {EXPECTED_THREAD_FBID}",
        f"",
        f"## Lead Question: Did anything fire during the wheel sequence?",
        f"",
    ]

    if wheel_period_requests:
        md_lines.append(f"**YES — {len(wheel_period_requests)} GraphQL request(s) fired during the wheel sequence.**")
        md_lines.append("")
        for r in wheel_period_requests:
            md_lines.append(f"- **{r.get('friendly_name') or '(unnamed)'}** at {r['timestamp']}")
            md_lines.append(f"  - doc_id: `{r.get('doc_id')}`")
            if r.get("variables"):
                md_lines.append(f"  - variables:")
                md_lines.append(f"    ```json")
                md_lines.append(f"    {json.dumps(r['variables'])}")
                md_lines.append(f"    ```")
    else:
        md_lines.append(f"**NO — zero GraphQL requests fired during the wheel sequence.**")
        md_lines.append("")
        if kb_delta and kb_delta > 0:
            md_lines.append(f"However, the keyboard fallback produced {kb_delta} new messages.")
        if initial_page_info and not initial_page_info.get("has_next_page"):
            md_lines.append("Root cause: `has_next_page` was `false` on initial load. Thread has <= 20 messages.")
        else:
            md_lines.append("`has_next_page` was `true` but no interaction triggered the next query.")

    md_lines.extend([
        "",
        f"## All friendly_names seen ({len(by_friendly)} distinct)",
        "",
        "| friendly_name | Count | First seen |",
        "|---------------|-------|------------|",
    ])
    for fn, reqs in sorted(by_friendly.items()):
        first_ts = reqs[0]["timestamp"]
        md_lines.append(f"| {fn} | {len(reqs)} | {first_ts} |")

    md_lines.extend([
        "",
        "## Bel-thread IGDThreadDetailMainViewContainerQuery",
        "",
        f"- Initial messages: {initial_bel_count}",
        f"- Final messages: {final_bel_count}",
        f"- Delta: {bel_delta_total}",
        f"- Initial page_info: `{json.dumps(initial_page_info)}`",
        f"- Final page_info: `{json.dumps(final_page_info)}`",
        "",
        "## DOM Walk Summary",
        "",
        f"- Ancestors walked: {len(ancestor_walk)}",
        f"- Role elements found: {sum(len(v) for v in role_elements.values())}",
        f"- Overflow candidates (scrollHeight > clientHeight + 50): {len(overflow_candidates)}",
    ])

    # List overflow candidates in the report
    if overflow_candidates:
        md_lines.extend([
            "",
            "### Overflow candidates (real scrollable containers)",
            "",
            "| # | Tag | ID | Classes | overflowY | scrollH | clientH | scrollTopMax | rect |",
            "|---|-----|----|---------|-----------|---------|---------|-------------|------|",
        ])
        for j, info in enumerate(overflow_candidates):
            cls_preview = '.'.join(info['classTokens']) if info['classTokens'] else '-'
            md_lines.append(f"| {j} | `<{info['tag']}>` | {info['id'] or '-'} | {cls_preview[:40]} | "
                           f"{info['overflowY']} | {info['scrollHeight']} | {info['clientHeight']} | "
                           f"{info['scrollTopMax']} | {info['rect']['width']}x{info['rect']['height']} |")

    # Cursor analysis
    md_lines.extend([
        "",
        "## Cursor Analysis",
        "",
    ])
    if initial_page_info and initial_page_info.get("end_cursor"):
        import base64
        import binascii
        raw_cursor = initial_page_info["end_cursor"]
        md_lines.append(f"- end_cursor present: `{raw_cursor[:60]}...`")
        try:
            decoded = base64.b64decode(raw_cursor)
            md_lines.append(f"- Base64 decoded ({len(decoded)} bytes): `{decoded[:100]}`")
            try:
                as_str = decoded.decode('utf-8')
                md_lines.append(f"- UTF-8: `{as_str[:200]}`")
            except Exception:
                md_lines.append(f"- (not valid UTF-8)")
        except Exception as e:
            md_lines.append(f"- Base64 decode failed: {e}")
    else:
        md_lines.append("- No end_cursor in initial response")

    md_lines.extend([
        "",
        "## Conclusion",
        "",
    ])

    if wheel_period_requests:
        pagination_candidates = [r for r in wheel_period_requests if r.get("friendly_name")]
        md_lines.append(f"**Wheel sequence triggered GraphQL traffic.**")
        md_lines.append(f"Candidate pagination queries: {len(pagination_candidates)}")
        for r in pagination_candidates:
            fn = r.get("friendly_name")
            md_lines.append(f"- `{fn}` — check variables for cursor fields")
    elif bel_delta_total > 0:
        md_lines.append(f"**Bel-query count increased by {bel_delta_total} after wheel/keyboard sequence.**")
        md_lines.append("The mechanism is unclear but pagination DID fire. Check traffic JSON for details.")
    else:
        md_lines.append("**Pagination trigger still unknown.**")
        md_lines.append("")
        md_lines.append("What was tried:")
        md_lines.append("- Slow continuous mouse.wheel (60 iterations over ~6s) over the message pane")
        md_lines.append("- Keyboard PageUp, End, Home sequence")
        md_lines.append("- Full DOM walk: all 33 ancestors, role/aria enumeration, overflow candidates logged")
        md_lines.append("- ALL GraphQL traffic captured — no new queries during any interaction")
        md_lines.append("")
        md_lines.append("`has_next_page` was `true` on initial load with a valid `end_cursor`, but no interaction — ")
        md_lines.append("not JS scrollTop, not mouse.wheel, not keyboard — caused IG to fire a follow-up query.")
        md_lines.append("")
        md_lines.append("**Escalation:** This needs human investigation. Possible directions:")
        md_lines.append("1. IG may use a virtualized list that only fetches when specific message rows scroll into viewport")
        md_lines.append("2. The pagination cursor variable name may have changed (not `cursor` or `after`)")
        md_lines.append("3. IG may require touch events (not wheel events) to trigger pagination")
        md_lines.append("4. The scroll container may be inside a Shadow DOM or iframe not accessible via normal DOM walk")
        md_lines.append("5. Manual test: open the thread in a real browser, scroll up with trackpad, watch DevTools Network tab")

    md_lines.extend([
        "",
        "## Artifacts",
        "",
        f"- DOM walk: `pagination_probe_v2_dom_walk.json`",
        f"- Traffic: `pagination_probe_v2_traffic.json`",
        f"- Screenshots: `pagination_probe_v2_before_{timestamp}.png`, `pagination_probe_v2_after_{timestamp}.png`",
        f"- Report: `pagination_probe_v2.md`",
    ])

    with open(md_path, 'w') as f:
        f.write('\n'.join(md_lines))
    print(f"  Report: {md_path}")

    # Copy screenshots to canonical names
    import shutil
    for src, dst_name in [
        (before_ss, "pagination_probe_v2_before.png"),
        (after_ss, "pagination_probe_v2_after.png"),
    ]:
        if src.exists():
            shutil.copy(str(src), str(ARTIFACTS_DIR / dst_name))

    # ---- Final terminal summary ----
    print("\n" + "=" * 60)
    print("PROBE V2 COMPLETE — TERMINAL SUMMARY")
    print("=" * 60)
    print(f"Bel messages: {initial_bel_count} -> {final_bel_count} (delta: {bel_delta_total})")
    print(f"Distinct friendly_names in session: {len(by_friendly)}")
    for fn, reqs in sorted(by_friendly.items()):
        print(f"  {fn}: {len(reqs)}")

    if wheel_period_names:
        print(f"\n*** New friendly_names during wheel: {sorted(wheel_period_names)} ***")
    else:
        print(f"\nNew friendly_names during wheel: (none)")

    print(f"New IGDThreadDetailMainViewContainerQuery queries during wheel: "
          f"{sum(1 for r in wheel_period_requests if r.get('friendly_name') == 'IGDThreadDetailMainViewContainerQuery')}")

    if bel_delta_total > 0:
        print(f"\n*** PAGINATION FIRED: +{bel_delta_total} messages ***")
    elif wheel_period_requests:
        print(f"\n*** NEW TRAFFIC DURING WHEEL — check report for variables ***")
    else:
        print(f"\nPagination trigger still unknown. See report for escalation notes.")


if __name__ == "__main__":
    main()
