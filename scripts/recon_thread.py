#!/usr/bin/env python3
"""
Instagram DM Thread Reconnaissance Script

This script performs read-only reconnaissance of an Instagram DM thread to understand
the data structure in both DOM and network traffic. It captures screenshots, DOM dumps,
and network API calls for analysis.

Stack: Python + Camoufox on Windows 11
Guardrails: Read-only, headed browser, no clicks on reactions/sends
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

import json
import time
import os
import re
from pathlib import Path
from datetime import datetime
import random

try:
    import camoufox
except ImportError:
    print("❌ ERROR: Camoufox is not installed!")
    print("Install with: pip install camoufox[geoip]")
    sys.exit(1)


def load_cookies(cookie_path):
    """Load and convert Cookie-Editor format to browser-compatible format."""
    if not os.path.exists(cookie_path):
        raise FileNotFoundError(
            f"Cookies file not found: {cookie_path}\n"
            "Please export your Instagram cookies using Cookie-Editor Chrome extension "
            "and save them as test-cookies/cookies.json"
        )

    with open(cookie_path, 'r') as f:
        cookies = json.load(f)

    # Convert Cookie-Editor format to browser-compatible format
    converted_cookies = []
    for cookie in cookies:
        converted = {
            'name': cookie['name'],
            'value': cookie['value'],
            'domain': cookie['domain'],
            'path': cookie['path'],
            'httpOnly': cookie.get('httpOnly', False),
            'secure': cookie.get('secure', True),
        }

        # Convert expirationDate to expires if present
        if 'expirationDate' in cookie and cookie['expirationDate']:
            converted['expires'] = int(cookie['expirationDate'])

        # Normalize sameSite values
        same_site = cookie.get('sameSite', 'unspecified')
        if same_site in ['no_restriction', 'none']:
            converted['sameSite'] = 'None'
        elif same_site in ['lax']:
            converted['sameSite'] = 'Lax'
        elif same_site in ['strict']:
            converted['sameSite'] = 'Strict'
        else:
            converted['sameSite'] = 'None'

        converted_cookies.append(converted)

    return converted_cookies


class NetworkCapture:
    """Capture and store network traffic for analysis."""

    def __init__(self):
        self.captured_requests = []
        self.full_responses = {}  # Store up to 20 most promising full responses
        self.max_response_size = 50 * 1024  # 50 KB truncated size
        self.max_full_responses = 20

    def should_capture_url(self, url):
        """Check if URL matches patterns we care about."""
        patterns = ['direct_v2', '/api/graphql', '/api/v1/', '/feed/']
        return any(pattern in url for pattern in patterns)

    def capture_request(self, request):
        """Capture incoming request."""
        if self.should_capture_url(request.url):
            self.captured_requests.append({
                'type': 'request',
                'method': request.method,
                'url': request.url,
                'timestamp': datetime.now().isoformat(),
                'post_data': None  # Will be filled in if POST
            })

    def capture_response(self, response):
        """Capture response and store data."""
        if self.should_capture_url(response.url):
            # Find corresponding request and update it
            for req in reversed(self.captured_requests):
                if req['url'] == response.url and 'status' not in req:
                    req['status'] = response.status
                    req['response_time'] = datetime.now().isoformat()
                    break
            else:
                # If no request found, create new entry
                self.captured_requests.append({
                    'type': 'response_only',
                    'url': response.url,
                    'status': response.status,
                    'timestamp': datetime.now().isoformat()
                })

            # Try to get response body
            try:
                # Store full response for promising endpoints
                body = response.body()

                # Determine if this is a "promising" response (likely contains message data)
                is_promising = any(pattern in response.url for pattern in [
                    'direct_v2/threads',
                    'direct_v2/inbox',
                    'graphql/query'
                ])

                if is_promising and len(self.full_responses) < self.max_full_responses:
                    self.full_responses[response.url] = body.decode('utf-8', errors='ignore')

                # Store truncated version in main capture
                truncated_body = body[:self.max_response_size].decode('utf-8', errors='ignore')

                # Find and update the request entry
                for req in reversed(self.captured_requests):
                    if req['url'] == response.url:
                        req['response_body'] = truncated_body
                        req['response_size'] = len(body)
                        if len(body) > self.max_response_size:
                            req['response_truncated'] = True
                        break
            except Exception as e:
                # Some responses can't be captured (binary, streaming, etc.)
                for req in reversed(self.captured_requests):
                    if req['url'] == response.url:
                        req['response_error'] = str(e)
                        break

    def to_json(self, output_path):
        """Export captured traffic to JSON file."""
        output = {
            'capture_session': datetime.now().isoformat(),
            'total_captured': len(self.captured_requests),
            'full_responses_stored': len(self.full_responses),
            'requests': self.captured_requests,
            'full_responses': self.full_responses
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        return output_path


def check_for_blockers(page):
    """Check for Instagram checkpoints, captchas, or security modals."""
    blockers = []

    # Check for suspicious login modal
    try:
        suspicious = page.query_selector('text=Suspicious Login')
        if suspicious:
            blockers.append('Suspicious Login modal detected')
    except:
        pass

    # Check for checkpoint/challenge
    try:
        checkpoint = page.query_selector('text=Checkpoint')
        if checkpoint:
            blockers.append('Checkpoint/challenge detected')
    except:
        pass

    # Check for captcha
    try:
        captcha = page.query_selector('iframe[src*="captcha"], iframe[src*="recaptcha"]')
        if captcha:
            blockers.append('CAPTCHA detected')
    except:
        pass

    # Check for "We noticed something unusual" type messages
    try:
        unusual = page.query_selector('text=unusual, text=something went wrong')
        if unusual:
            blockers.append('Unusual activity message detected')
    except:
        pass

    return blockers


def dismiss_notifications(page):
    """Try to dismiss any notification/PWA popups."""
    try:
        # Try clicking "Not Now" button
        not_now = page.query_selector('button:has-text("Not Now")')
        if not_now:
            not_now.click()
            time.sleep(1)
            print("📢 Dismissed 'Not Now' popup")
    except:
        pass

    try:
        # Try pressing Escape
        page.keyboard.press('Escape')
        time.sleep(0.5)
    except:
        pass


def dump_message_list_dom(page, output_path):
    """Dump the HTML of the message list container."""
    try:
        # Try multiple selectors for the message list
        selectors = [
            '[role="main"]',
            '[role="list"]',
            '.x1hc1fzr',  # Common Instagram class
            '.x1gryazu',  # Another common class
        ]

        message_list = None
        for selector in selectors:
            try:
                message_list = page.query_selector(selector)
                if message_list:
                    break
            except:
                continue

        if message_list:
            html = message_list.inner_html()
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(f'<!-- DOM Dump captured at {datetime.now().isoformat()} -->\n')
                f.write(f'<!-- Selector used: {message_list} -->\n')
                f.write(html)
            print(f"📄 Dumped message list DOM to {output_path}")
            return True
        else:
            print(f"⚠️ Could not find message list container, dumping full page instead")
            html = page.content()
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(f'<!-- Full page DOM dump (no message list found) -->\n')
                f.write(f'<!-- Captured at {datetime.now().isoformat()} -->\n')
                f.write(html)
            return True
    except Exception as e:
        print(f"⚠️ Error dumping DOM: {e}")
        return False


def jittered_sleep(min_seconds, max_seconds):
    """Sleep with random jitter for human-like pacing."""
    delay = random.uniform(min_seconds, max_seconds)
    time.sleep(delay)
    return delay


def main():
    """Main reconnaissance execution."""
    print("🔍 Instagram DM Thread Reconnaissance")
    print("=" * 60)
    print("⚠️  READ-ONLY MODE: No reactions, no sends, no edits")
    print("⚠️  HEADED BROWSER: Watch the window for any checkpoints")
    print("=" * 60)

    # Load cookies
    cookie_path = 'test-cookies/cookies.json'
    try:
        cookies = load_cookies(cookie_path)
        print(f"✅ Loaded {len(cookies)} cookies from {cookie_path}")
    except Exception as e:
        print(f"❌ {e}")
        return

    # Get thread URL from user
    print("\n📋 Paste your DM thread URL below")
    print("   Example: https://www.instagram.com/direct/t/1234567890...")
    thread_url = input("DM thread URL: ").strip()

    if not thread_url or 'instagram.com/direct/t/' not in thread_url:
        print("❌ Invalid thread URL. Must be an Instagram DM thread link.")
        return

    # Ensure artifacts directory exists
    os.makedirs('artifacts', exist_ok=True)

    # Initialize network capture
    network_capture = NetworkCapture()

    print(f"\n🚀 Starting reconnaissance...")
    print(f"📍 Target thread: {thread_url}")

    try:
        with camoufox.Camoufox(headless=False) as browser:
            # Create context and inject cookies
            context = browser.new_context(
                viewport={'width': 1528, 'height': 794},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            context.add_cookies(cookies)

            # Create page and setup network listeners
            page = context.new_page()

            # Setup network capture BEFORE navigation
            page.on('request', network_capture.capture_request)
            page.on('response', network_capture.capture_response)

            # Navigate to inbox first (more natural)
            print("\n📬 Step 1: Navigating to inbox...")
            page.goto('https://www.instagram.com/direct/inbox/')
            jittered_sleep(2.5, 3.5)

            # Check for blockers
            blockers = check_for_blockers(page)
            if blockers:
                print(f"⚠️  BLOCKERS DETECTED: {blockers}")
                screenshot_path = 'artifacts/blocker_' + datetime.now().strftime('%Y%m%d_%H%M%S') + '.png'
                page.screenshot(path=screenshot_path)

                blocker_report = f"""# Instagram Security Blocker Detected

**Time:** {datetime.now().isoformat()}
**Blockers:** {', '.join(blockers)}

## Screenshot
{creenshot_path}

## Action Required
Instagram has flagged this session. Please:
1. Manually complete any security challenge in the browser
2. Update cookies if session expired
3. Try again from a different IP/network if needed
"""
                blocker_path = 'artifacts/blocker_' + datetime.now().strftime('%Y%m%d_%H%M%S') + '.md'
                with open(blocker_path, 'w') as f:
                    f.write(blocker_report)

                print(f"🚨 STOPPING: Saved blocker report to {blocker_path}")
                print(f"🖼️  Screenshot: {screenshot_path}")
                browser.close()
                return

            # Dismiss any notifications
            dismiss_notifications(page)

            print("✅ Inbox loaded, navigating to thread...")

            # Navigate to thread
            page.goto(thread_url)
            jittered_sleep(3, 5)

            # Check for blockers again after thread navigation
            blockers = check_for_blockers(page)
            if blockers:
                print(f"⚠️  BLOCKERS DETECTED: {blockers}")
                screenshot_path = 'artifacts/blocker_thread_' + datetime.now().strftime('%Y%m%d_%H%M%S') + '.png'
                page.screenshot(path=screenshot_path)

                blocker_report = f"""# Instagram Security Blocker Detected (Thread)

**Time:** {datetime.now().isoformat()}
**Thread URL:** {thread_url}
**Blockers:** {', '.join(blockers)}

## Screenshot
{creenshot_path}

## Action Required
Instagram has flagged this session. Please:
1. Manually complete any security challenge in the browser
2. Update cookies if session expired
3. Try again from a different IP/network if needed
"""
                blocker_path = 'artifacts/blocker_thread_' + datetime.now().strftime('%Y%m%d_%H%M%S') + '.md'
                with open(blocker_path, 'w') as f:
                    f.write(blocker_report)

                print(f"🚨 STOPPING: Saved blocker report to {blocker_path}")
                print(f"🖼️  Screenshot: {screenshot_path}")
                browser.close()
                return

            # Dismiss notifications again
            dismiss_notifications(page)

            # Let thread render
            print("⏳ Waiting for thread to render...")
            jittered_sleep(8, 12)

            # Capture initial state
            print("\n📸 Capturing initial state...")

            # Screenshot
            initial_screenshot = 'artifacts/recon_thread_initial.png'
            page.screenshot(path=initial_screenshot, full_page=True)
            print(f"   Screenshot: {initial_screenshot}")

            # DOM dump
            initial_dom = 'artifacts/recon_thread_dom.html'
            dump_message_list_dom(page, initial_dom)

            # Scroll up twice to trigger lazy-load
            print("\n📜 Scrolling to trigger lazy-load...")

            # First scroll
            page.evaluate('window.scrollBy(0, -800)')
            jittered_sleep(1.5, 3)

            # Second scroll
            page.evaluate('window.scrollBy(0, -800)')
            jittered_sleep(1.5, 3)

            # Capture scrolled state
            print("📸 Capturing scrolled state...")

            # Screenshot after scroll
            scrolled_screenshot = 'artifacts/recon_thread_scrolled.png'
            page.screenshot(path=scrolled_screenshot, full_page=True)
            print(f"   Screenshot: {scrolled_screenshot}")

            # DOM dump after scroll
            scrolled_dom = 'artifacts/recon_thread_dom_after_scroll.html'
            dump_message_list_dom(page, scrolled_dom)

            # Wait a bit more for any lazy-loaded network calls
            jittered_sleep(2, 3)

            # Export network capture
            print("\n🌐 Exporting network capture...")
            network_json = 'artifacts/recon_network.json'
            network_capture.to_json(network_json)
            print(f"   Network data: {network_json}")
            print(f"   Captured {len(network_capture.captured_requests)} requests/responses")
            print(f"   Stored {len(network_capture.full_responses)} full responses")

            browser.close()

    except Exception as e:
        print(f"❌ Error during reconnaissance: {e}")
        import traceback
        traceback.print_exc()
        return

    # Summary
    print("\n" + "=" * 60)
    print("✅ RECONNAISSANCE COMPLETE")
    print("=" * 60)
    print("📁 Artifacts created:")
    print(f"   - {initial_screenshot}")
    print(f"   - {scrolled_screenshot}")
    print(f"   - {initial_dom}")
    print(f"   - {scrolled_dom}")
    print(f"   - {network_json}")
    print("\n📊 Next step: Analyze artifacts and create documentation")
    print("   Run analysis to generate docs/thread_recon.md")


if __name__ == '__main__':
    main()
