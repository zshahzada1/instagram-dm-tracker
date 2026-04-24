#!/usr/bin/env python3
"""
Instagram DM Thread Reconnaissance v2 — Full Payload Capture

Fixes from v1:
- No truncation on response bodies
- Captures POST body (doc_id, fb_api_req_friendly_name, variables)
- Groups traffic by friendly_name
- Outputs recon_network_v2.json + recon_network_v2_summary.md

Guardrails: headed browser, read-only, 1.5-3s jittered delays.
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

import json
import time
import os
from pathlib import Path
from datetime import datetime
from urllib.parse import parse_qs, unquote_plus
from collections import defaultdict
import random

try:
    import camoufox
except ImportError:
    print("ERROR: Camoufox is not installed!")
    print("Install with: pip install camoufox[geoip]")
    sys.exit(1)


def load_cookies(cookie_path):
    """Load Cookie-Editor format cookies and convert for browser."""
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


class FullNetworkCapture:
    """Capture full GraphQL request + response bodies, grouped by friendly_name."""

    def __init__(self):
        self.captured = []          # list of dicts, each a full request+response pair
        self._pending = {}          # url -> list of request dicts awaiting response

    def on_request(self, request):
        """Capture outgoing request, extract POST body fields."""
        if '/api/graphql' not in request.url:
            return

        entry = {
            'url': request.url,
            'method': request.method,
            'timestamp': datetime.now().isoformat(),
            'doc_id': None,
            'friendly_name': None,
            'variables': None,
            'response_status': None,
            'response_body': None,
        }

        # Parse URL-encoded POST body
        post_data = request.post_data
        if post_data:
            try:
                parsed = parse_qs(post_data)
                if 'doc_id' in parsed:
                    entry['doc_id'] = parsed['doc_id'][0]
                if 'fb_api_req_friendly_name' in parsed:
                    entry['friendly_name'] = parsed['fb_api_req_friendly_name'][0]
                if 'variables' in parsed:
                    raw_vars = parsed['variables'][0]
                    entry['variables'] = json.loads(raw_vars)
            except Exception as e:
                entry['_post_parse_error'] = str(e)

        # Queue for response matching
        self._pending.setdefault(request.url, []).append(entry)

    def on_response(self, response):
        """Capture response body and match to queued request."""
        if '/api/graphql' not in response.url:
            return

        # Find the oldest pending request for this URL
        pending_list = self._pending.get(response.url, [])
        if not pending_list:
            # Orphan response — still capture it
            entry = {
                'url': response.url,
                'method': 'unknown',
                'timestamp': datetime.now().isoformat(),
                'doc_id': None,
                'friendly_name': None,
                'variables': None,
                'response_status': response.status,
                'response_body': None,
            }
            try:
                body = response.body()
                entry['response_body'] = json.loads(body.decode('utf-8', errors='replace'))
            except Exception:
                pass
            self.captured.append(entry)
            return

        # Pop the oldest pending request
        entry = pending_list.pop(0)
        entry['response_status'] = response.status

        # Get full response body — no truncation
        try:
            body = response.body()
            raw = body.decode('utf-8', errors='replace')
            entry['response_body'] = json.loads(raw)
        except json.JSONDecodeError:
            entry['response_body'] = raw  # store as string if not JSON
        except Exception as e:
            entry['_response_error'] = str(e)

        self.captured.append(entry)

    def to_json(self, output_path, thread_url):
        """Export to JSON."""
        output = {
            'captured_at': datetime.now().isoformat(),
            'thread_url': thread_url,
            'total_captured': len(self.captured),
            'requests': self.captured,
        }
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        return output_path

    def write_summary(self, output_path, thread_url):
        """Write human-readable summary grouped by friendly_name."""
        groups = defaultdict(list)
        unnamed = []
        for entry in self.captured:
            name = entry.get('friendly_name')
            if name:
                groups[name].append(entry)
            else:
                unnamed.append(entry)

        lines = [
            f"# Network Capture Summary",
            f"",
            f"**Captured:** {datetime.now().isoformat()}",
            f"**Thread:** {thread_url}",
            f"**Total requests:** {len(self.captured)}",
            f"",
            f"## Grouped by friendly_name",
            f"",
        ]

        for name, entries in sorted(groups.items()):
            lines.append(f"### {name} ({len(entries)} requests)")
            for i, e in enumerate(entries):
                doc_id = e.get('doc_id', 'N/A')
                status = e.get('response_status', 'N/A')
                has_body = e.get('response_body') is not None
                has_vars = e.get('variables') is not None
                lines.append(f"  #{i+1}: doc_id={doc_id}, status={status}, "
                             f"has_response_body={has_body}, has_variables={has_vars}")
            lines.append("")

        if unnamed:
            lines.append(f"### Unnamed GraphQL calls ({len(unnamed)})")
            for i, e in enumerate(unnamed):
                status = e.get('response_status', 'N/A')
                lines.append(f"  #{i+1}: status={status}")
            lines.append("")

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))


def jittered_sleep(lo, hi):
    delay = random.uniform(lo, hi)
    time.sleep(delay)
    return delay


def check_for_blockers(page):
    """Check for Instagram checkpoints, captchas, or security modals."""
    blockers = []

    checks = [
        ('text=Suspicious Login', 'Suspicious Login modal'),
        ('text=Checkpoint', 'Checkpoint/challenge detected'),
        ('iframe[src*="captcha"], iframe[src*="recaptcha"]', 'CAPTCHA detected'),
        ('text=unusual', 'Unusual activity message'),
        ('text=something went wrong', 'Error message'),
    ]

    for selector, label in checks:
        try:
            el = page.query_selector(selector)
            if el:
                blockers.append(label)
        except Exception:
            pass

    return blockers


def dismiss_notifications(page):
    """Dismiss notification/PWA popups."""
    try:
        btn = page.query_selector('button:has-text("Not Now")')
        if btn:
            btn.click()
            time.sleep(1)
    except Exception:
        pass
    try:
        page.keyboard.press('Escape')
        time.sleep(0.5)
    except Exception:
        pass


def handle_blockers(page, prefix='blocker'):
    """Screenshot and report blockers. Returns True if blockers found."""
    blockers = check_for_blockers(page)
    if not blockers:
        return False

    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    ss_path = f'artifacts/{prefix}_{ts}.png'
    page.screenshot(path=ss_path)

    report = (
        f"# Blocker Detected\n\n"
        f"**Time:** {datetime.now().isoformat()}\n"
        f"**Blockers:** {', '.join(blockers)}\n\n"
        f"**Screenshot:** {ss_path}\n\n"
        f"## Action Required\n"
        f"1. Complete any security challenge in the browser\n"
        f"2. Update cookies if session expired\n"
        f"3. Try from different network if needed\n"
    )
    report_path = f'artifacts/{prefix}_{ts}.md'
    with open(report_path, 'w') as f:
        f.write(report)

    print(f"BLOCKER: {', '.join(blockers)}")
    print(f"Screenshot: {ss_path}")
    print(f"Report: {report_path}")
    return True


def run_recon(thread_url, capture):
    """Run the full recon flow: inbox -> thread -> scroll 3x."""
    with camoufox.Camoufox(headless=False) as browser:
        context = browser.new_context(
            viewport={'width': 1528, 'height': 794},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                       'AppleWebKit/537.36 (KHTML, like Gecko) '
                       'Chrome/120.0.0.0 Safari/537.36',
        )

        cookie_path = 'test-cookies/cookies.json'
        cookies = load_cookies(cookie_path)
        context.add_cookies(cookies)
        print(f"Loaded {len(cookies)} cookies")

        page = context.new_page()

        # Install listeners BEFORE any navigation
        page.on('request', capture.on_request)
        page.on('response', capture.on_response)

        # Step 1: Inbox
        print("\nNavigating to inbox...")
        page.goto('https://www.instagram.com/direct/inbox/')
        jittered_sleep(3.5, 4.5)

        if handle_blockers(page, 'blocker_inbox'):
            browser.close()
            return False

        dismiss_notifications(page)
        print("Inbox loaded.")

        # Step 2: Navigate to thread
        print(f"\nNavigating to thread: {thread_url}")
        page.goto(thread_url)
        jittered_sleep(4, 5)

        if handle_blockers(page, 'blocker_thread'):
            browser.close()
            return False

        dismiss_notifications(page)

        # Let thread fully render
        print("Waiting for thread to render...")
        jittered_sleep(8, 12)

        # Screenshot initial state
        page.screenshot(path='artifacts/recon_v2_initial.png')
        print("Screenshot: artifacts/recon_v2_initial.png")

        # Step 3: Scroll up 3 times to trigger pagination
        print("\nScrolling message pane upward 3 times...")
        for i in range(3):
            page.evaluate('window.scrollBy(0, -800)')
            print(f"  Scroll {i+1}/3")
            jittered_sleep(2, 3)

        # Extra settle for pagination traffic
        jittered_sleep(2, 3)

        page.screenshot(path='artifacts/recon_v2_scrolled.png')
        print("Screenshot: artifacts/recon_v2_scrolled.png")

        print(f"\nCaptured {len(capture.captured)} GraphQL requests total.")
        browser.close()
        return True


def run_reaction_capture(thread_url, reaction_capture):
    """Relaunch browser for manual reaction capture."""
    with camoufox.Camoufox(headless=False) as browser:
        context = browser.new_context(
            viewport={'width': 1528, 'height': 794},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                       'AppleWebKit/537.36 (KHTML, like Gecko) '
                       'Chrome/120.0.0.0 Safari/537.36',
        )

        cookies = load_cookies('test-cookies/cookies.json')
        context.add_cookies(cookies)

        page = context.new_page()
        page.on('request', reaction_capture.on_request)
        page.on('response', reaction_capture.on_response)

        # Navigate directly to thread
        print(f"\nNavigating to thread for reaction capture...")
        page.goto(thread_url)
        jittered_sleep(4, 5)

        if handle_blockers(page, 'blocker_reaction'):
            browser.close()
            return False

        dismiss_notifications(page)
        jittered_sleep(3, 4)

        print("\n" + "=" * 60)
        print("MANUAL STEP: Hover over any ONE message in the thread,")
        print("click the smiley reaction icon, pick any emoji.")
        print("Then wait 5 seconds and press Enter in this terminal.")
        print("=" * 60)

        input("\nPress Enter after you've reacted and waited 5 seconds...")

        # Wait a moment for any late network calls
        jittered_sleep(2, 3)

        print(f"Captured {len(reaction_capture.captured)} requests during reaction step.")
        browser.close()
        return True


def main():
    print("=" * 60)
    print("Instagram DM Thread Reconnaissance v2")
    print("Full payload capture — no truncation")
    print("=" * 60)

    os.makedirs('artifacts', exist_ok=True)

    # Get thread URL from user
    print("\nPaste a DM thread URL that contains several shared reels/posts.")
    print("Example: https://www.instagram.com/direct/t/1234567890...")
    thread_url = input("DM thread URL: ").strip()

    if not thread_url or 'instagram.com/direct/t/' not in thread_url:
        print("Invalid thread URL. Must contain instagram.com/direct/t/")
        return

    # --- Phase 1: Full recon with scrolling ---
    print("\n--- Phase 1: Full thread capture + 3 scrolls ---")
    capture = FullNetworkCapture()

    if not run_recon(thread_url, capture):
        print("Recon aborted due to blocker.")
        return

    # Export recon results
    json_path = 'artifacts/recon_network_v2.json'
    capture.to_json(json_path, thread_url)
    print(f"\nNetwork data: {json_path}")

    summary_path = 'artifacts/recon_network_v2_summary.md'
    capture.write_summary(summary_path, thread_url)
    print(f"Summary: {summary_path}")

    # --- Phase 2: Manual reaction capture ---
    print("\n--- Phase 2: Manual reaction capture ---")
    reaction_capture = FullNetworkCapture()

    if not run_reaction_capture(thread_url, reaction_capture):
        print("Reaction capture aborted.")
        return

    reaction_path = 'artifacts/recon_reaction.json'
    reaction_capture.to_json(reaction_path, thread_url)
    print(f"Reaction data: {reaction_path}")

    # --- Done ---
    print("\n" + "=" * 60)
    print("RECONNAISSANCE v2 COMPLETE")
    print("=" * 60)
    print(f"Network capture: {json_path}")
    print(f"Summary: {summary_path}")
    print(f"Reaction capture: {reaction_path}")
    print(f"Screenshots: recon_v2_initial.png, recon_v2_scrolled.png")
    print("\nNext: Analyze artifacts and create docs/thread_recon_v2.md")


if __name__ == '__main__':
    main()
