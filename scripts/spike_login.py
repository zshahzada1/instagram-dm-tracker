#!/usr/bin/env python3
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
"""
Instagram Login Spike - Authentication Testing

This script tests authenticated browser automation against Instagram.com
using either Camoufox (preferred) or Playwright with stealth as fallback.
"""

import json
import time
import os
from pathlib import Path
from datetime import datetime

# Try Camoufox first, fall back to Playwright
try:
    import camoufox
    CAMOUFOX_AVAILABLE = True
except ImportError:
    CAMOUFOX_AVAILABLE = False

try:
    from playwright.sync_api import sync_playwright
    from playwright_stealth import Stealth
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


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


def check_login_state(page, browser_type):
    """Detect if we're logged into Instagram by checking DOM elements."""
    logged_in = False
    evidence = []

    # Check for thread list (DM inbox)
    try:
        thread_list = page.query_selector('[role="main"]')
        if thread_list:
            logged_in = True
            evidence.append("Found main content area (likely inbox)")
    except:
        evidence.append("Could not check for thread list")

    # Check for user avatar in navigation
    try:
        avatar = page.query_selector('img[alt*="Profile picture"], img[alt*="profile"]')
        if avatar:
            logged_in = True
            evidence.append("Found user avatar in navigation")
    except:
        evidence.append("Could not check for user avatar")

    # Check URL for login redirect
    current_url = page.url
    if '/accounts/login' in current_url:
        logged_in = False
        evidence.append(f"Redirected to login page: {current_url}")
    elif current_url.startswith('https://www.instagram.com/'):
        evidence.append(f"Current URL: {current_url}")
    else:
        evidence.append(f"Unusual URL: {current_url}")

    # Check for checkpoint/suspicious login modal
    try:
        checkpoint = page.query_selector('text=Suspicious Login Attempt')
        if checkpoint:
            logged_in = False
            evidence.append("⚠️ Found 'Suspicious Login Attempt' checkpoint modal")
    except:
        pass

    return logged_in, evidence


def run_camoufox_test(cookies):
    """Run authentication test using Camoufox browser."""
    print("🦊 Using Camoufox browser...")

    with camoufox.Camoufox(headless=False) as browser:
        start_time = time.time()

        # Create context and inject cookies
        context = browser.new_context()
        context.add_cookies(cookies)

        # Create page and navigate
        page = context.new_page()
        page.goto('https://www.instagram.com/direct/inbox/')

        # Wait for network idle and settle
        try:
            page.wait_for_load_state('networkidle', timeout=10000)
        except:
            print("⚠️ Network idle timeout, proceeding anyway")

        time.sleep(3)  # Additional settle time

        load_time = time.time() - start_time

        # Check login state
        logged_in, evidence = check_login_state(page, 'camoufox')

        # Take screenshot
        screenshot_path = 'artifacts/spike_login.png'
        page.screenshot(path=screenshot_path)

        browser.close()

        return {
            'browser': 'Camoufox',
            'logged_in': logged_in,
            'evidence': evidence,
            'url': page.url,
            'load_time': f"{load_time:.2f}s",
            'screenshot': screenshot_path
        }


def run_playwright_test(cookies):
    """Run authentication test using Playwright with stealth."""
    print("🎭 Using Playwright with stealth...")

    with sync_playwright() as p:
        start_time = time.time()

        # Launch browser
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()

        # Apply stealth
        # Create page and apply stealth
        page = context.new_page()
        stealth = Stealth()
        stealth.apply_stealth_sync(page)


        # Create page and navigate
        page = context.new_page()
        page.goto('https://www.instagram.com/direct/inbox/')

        # Wait for network idle and settle
        try:
            page.wait_for_load_state('networkidle', timeout=10000)
        except:
            print("⚠️ Network idle timeout, proceeding anyway")

        time.sleep(3)  # Additional settle time

        load_time = time.time() - start_time

        # Check login state
        logged_in, evidence = check_login_state(page, 'playwright')

        # Take screenshot
        screenshot_path = 'artifacts/spike_login_playwright.png'
        page.screenshot(path=screenshot_path)

        browser.close()

        return {
            'browser': 'Playwright + playwright-stealth',
            'logged_in': logged_in,
            'evidence': evidence,
            'url': page.url,
            'load_time': f"{load_time:.2f}s",
            'screenshot': screenshot_path
        }


def main():
    """Main execution function."""
    print("🚀 Instagram DM Tracker - Login Spike Test")
    print("=" * 50)

    # Check which browser automation tools are available
    if not CAMOUFOX_AVAILABLE and not PLAYWRIGHT_AVAILABLE:
        print("❌ ERROR: Neither Camoufox nor Playwright is installed!")
        print("\nInstall one of the following:")
        print("  Camoufox: pip install camoufox[geoip]")
        print("  Playwright: pip install playwright playwright-stealth && playwright install chromium")
        return

    # Load cookies
    cookie_path = 'test-cookies/cookies.json'
    try:
        cookies = load_cookies(cookie_path)
        print(f"✅ Loaded {len(cookies)} cookies from {cookie_path}")
    except Exception as e:
        print(f"❌ {e}")
        return

    # Ensure artifacts directory exists
    os.makedirs('artifacts', exist_ok=True)

    # Run test with preferred browser
    result = None
    try:
        if CAMOUFOX_AVAILABLE:
            result = run_camoufox_test(cookies)
        elif PLAYWRIGHT_AVAILABLE:
            result = run_playwright_test(cookies)
    except Exception as e:
        print(f"❌ Browser test failed: {e}")
        if CAMOUFOX_AVAILABLE and PLAYWRIGHT_AVAILABLE:
            print("🔄 Falling back to Playwright...")
            try:
                result = run_playwright_test(cookies)
            except Exception as e2:
                print(f"❌ Fallback also failed: {e2}")
                return

    if not result:
        print("❌ No successful browser test completed")
        return

    # Determine login status
    status = "✅ PASS" if result['logged_in'] else "❌ FAIL"
    if not result['logged_in'] and 'checkpoint' in str(result['evidence']):
        status = "⚠️ PARTIAL (checkpoint detected)"

    # Write results markdown
    report_path = 'artifacts/spike_login.md'
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(f"# Instagram Login Spike Test Results\n\n")
        f.write(f"**Test Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"## Overall Status\n\n")
        f.write(f"**{status}**\n\n")
        f.write(f"## Browser Used\n\n")
        f.write(f"{result['browser']}\n\n")
        f.write(f"## Login State\n\n")
        f.write(f"**Logged In:** {result['logged_in']}\n\n")
        f.write(f"## Evidence\n\n")
        for evidence in result['evidence']:
            f.write(f"- {evidence}\n")
        f.write(f"\n## Current URL\n\n")
        f.write(f"{result['url']}\n\n")
        f.write(f"## Performance\n\n")
        f.write(f"**Page Load Time:** {result['load_time']}\n\n")
        f.write(f"## Artifacts\n\n")
        f.write(f"**Screenshot:** {result['screenshot']}\n\n")
        f.write(f"## Observations\n\n")
        if not result['logged_in']:
            f.write("Authentication failed. Possible causes:\n")
            f.write("- Cookies expired or invalid\n")
            f.write("- Instagram detected automation (checkpoint)\n")
            f.write("- Cookie format incorrect\n")
            f.write("- IP/location change triggered security check\n")
        elif 'checkpoint' in str(result['evidence']):
            f.write("⚠️ **Checkpoint detected!** Instagram flagged this login attempt.\n")
            f.write("You may need to complete a security challenge manually.\n")
        else:
            f.write("✅ Authentication successful! Ready to proceed with full build.\n")

    print("\n" + "=" * 50)
    print(f"📊 Test complete: {status}")
    print(f"📄 Report: {report_path}")
    print(f"🖼️  Screenshot: {result['screenshot']}")
    print(f"🧭 Browser: {result['browser']}")
    print(f"⏱️  Load time: {result['load_time']}")


if __name__ == '__main__':
    main()
