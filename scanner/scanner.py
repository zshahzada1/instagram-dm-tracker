"""Main scanner for Instagram DM thread messages."""
import json
import os
import random
import re
import sys
import time
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any

try:
    import camoufox
except ImportError:
    print("ERROR: Camoufox is not installed!")
    print("Install with: pip install camoufox[geoip]")
    sys.exit(1)

import sqlite3

from .capture import ThreadMessagesCapture
from .parser import parse_message_node


def load_cookies(cookie_path: str) -> list:
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


def check_blockers(page, timestamp: str) -> bool:
    """Check for Instagram blockers (checkpoints, captchas, suspicious login)."""
    try:
        checkpoint = page.locator("text=Check Your Information").count()
        if checkpoint > 0:
            screenshot_path = f"artifacts/blocker_{timestamp}.png"
            page.screenshot(path=screenshot_path)

            report_path = f"artifacts/blocker_{timestamp}.md"
            with open(report_path, 'w') as f:
                f.write(f"# Instagram Blocker Detected\n\n")
                f.write(f"**Timestamp:** {timestamp}\n")
                f.write(f"**Type:** Checkpoint/Verification required\n")
                f.write(f"**Screenshot:** {screenshot_path}\n\n")
                f.write("Action required: Please complete verification in browser, then re-export cookies.\n")

            print(f"\n[!] BLOCKER DETECTED: Checkpoint/Verification required")
            print(f"    Screenshot saved to: {screenshot_path}")
            print(f"    Report saved to: {report_path}")
            return True

        suspicious = page.locator("text=suspicious login attempt").count()
        if suspicious > 0:
            screenshot_path = f"artifacts/blocker_{timestamp}.png"
            page.screenshot(path=screenshot_path)

            report_path = f"artifacts/blocker_{timestamp}.md"
            with open(report_path, 'w') as f:
                f.write(f"# Instagram Blocker Detected\n\n")
                f.write(f"**Timestamp:** {timestamp}\n")
                f.write(f"**Type:** Suspicious login attempt\n")
                f.write(f"**Screenshot:** {screenshot_path}\n\n")
                f.write("Action required: Please complete verification in browser, then re-export cookies.\n")

            print(f"\n[!] BLOCKER DETECTED: Suspicious login attempt")
            print(f"    Screenshot saved to: {screenshot_path}")
            print(f"    Report saved to: {report_path}")
            return True

    except Exception:
        pass

    return False


def dismiss_overlays(page):
    """Dismiss 'Not Now' buttons and other overlays."""
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


def handle_pagination(page, capture: ThreadMessagesCapture, max_messages: int) -> Dict[str, Any]:
    """
    Trigger pagination via keyboard bursts on the focused conversation pane.

    IG fires IGDMessageListOffMsysQuery when the message list is scrolled with
    keyboard input. A burst of PageUp + ArrowUp + End/Home is needed to reliably
    trigger the paginated query — a single keypress is not enough.

    Returns:
        Dict with pagination results.
    """
    initial_count = len(capture.extract_messages()["messages"])

    # Focus the page — exact sequence from v2 probe keyboard fallback
    try:
        page.click('body')
    except Exception:
        pass
    time.sleep(random.uniform(0.5, 1.0))

    consecutive_misses = 0
    max_consecutive_misses = 2
    total_messages = initial_count
    attempts = 0

    while total_messages < max_messages and consecutive_misses < max_consecutive_misses:
        attempts += 1

        # Sequence matching the v2 probe keyboard fallback that works:
        # body click → PageUp × 10 → wait → End → wait → Home → wait
        for _ in range(10):
            try:
                page.keyboard.press("PageUp")
            except Exception:
                pass
            time.sleep(0.3)

        time.sleep(random.uniform(1.0, 2.0))

        try:
            page.keyboard.press("End")
            time.sleep(random.uniform(2.0, 3.0))
            page.keyboard.press("Home")
            time.sleep(random.uniform(2.0, 3.0))
        except Exception:
            pass

        # Settle time for the OffMsys query to fire
        time.sleep(random.uniform(3.0, 4.0))

        current_messages = len(capture.extract_messages()["messages"])
        if current_messages > total_messages:
            total_messages = current_messages
            consecutive_misses = 0
        else:
            consecutive_misses += 1

        page_info = capture.extract_messages()["page_info"]
        if page_info and not page_info.get("has_next_page", True):
            break

    stop_reason = None
    if consecutive_misses >= max_consecutive_misses:
        stop_reason = f"No new queries after {max_consecutive_misses} consecutive misses"
    elif total_messages >= max_messages:
        stop_reason = f"Reached max_messages ({max_messages})"
    elif capture.extract_messages()["page_info"] and not capture.extract_messages()["page_info"].get("has_next_page", True):
        stop_reason = "has_next_page is false"

    return {
        "success": consecutive_misses < max_consecutive_misses,
        "reason": stop_reason,
        "messages_found": total_messages,
        "attempts": attempts,
    }


def run_scan(thread_url: str, db_path: str, max_messages: int = 200) -> Dict[str, Any]:
    """
    Run a scan of an Instagram DM thread and store media items in the database.

    Args:
        thread_url: The Instagram DM thread URL
        db_path: Path to the SQLite database
        max_messages: Maximum number of messages to scan

    Returns:
        Dict with scan results.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    cookie_path = Path(__file__).parent.parent / "test-cookies" / "cookies.json"

    m = re.search(r'/direct/t/(\d+)', thread_url)
    if not m:
        raise ValueError(f"Cannot extract thread_fbid from URL: {thread_url}")
    expected_thread_fbid = m.group(1)

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    cursor = conn.cursor()

    scan_run_id = None

    try:
        cursor.execute(
            "INSERT INTO scan_runs (thread_id, started_at, status) VALUES (NULL, ?, 'running')",
            (datetime.now(timezone.utc).isoformat(),)
        )
        scan_run_id = cursor.lastrowid
        conn.commit()

        capture = ThreadMessagesCapture(expected_thread_fbid)

        with camoufox.Camoufox(headless=False) as browser:
            context = browser.new_context(viewport={"width": 1528, "height": 794})
            page = context.new_page()

            page.on("request", capture.on_request)
            page.on("response", capture.on_response)

            cookies = load_cookies(str(cookie_path))
            context.add_cookies(cookies)

            page.goto(thread_url, timeout=60000, wait_until="domcontentloaded")
            time.sleep(random.uniform(4.0, 5.0))

            if check_blockers(page, timestamp):
                raise Exception("Blocker detected at thread")

            dismiss_overlays(page)

            time.sleep(random.uniform(8.0, 12.0))

            # Set thread_internal_id on capture so OffMsys responses are matched
            initial_extracted = capture.extract_messages()
            if initial_extracted.get("thread_internal_id"):
                capture.expected_thread_internal_id = initial_extracted["thread_internal_id"]

            pagination_result = handle_pagination(page, capture, max_messages)

            if not pagination_result["success"]:
                debug_path = "artifacts/scanner_pagination_debug.md"
                with open(debug_path, 'w') as f:
                    f.write(f"# Pagination Debug Report\n\n")
                    f.write(f"**Timestamp:** {timestamp}\n")
                    f.write(f"**Thread URL:** {thread_url}\n")
                    f.write(f"**Reason:** {pagination_result['reason']}\n")
                    f.write(f"**Messages found:** {pagination_result['messages_found']}\n")
                    f.write(f"**Attempts:** {pagination_result['attempts']}\n\n")

                    extracted = capture.extract_messages()
                    page_info = extracted["page_info"]
                    if page_info:
                        f.write(f"**Page Info:**\n")
                        f.write(f"```json\n{json.dumps(page_info, indent=2)}\n```\n\n")

                screenshot_path = "artifacts/scanner_pagination_state.png"
                page.screenshot(path=screenshot_path)

                print(f"\n[i] Pagination did not trigger after {pagination_result['attempts']} attempts")
                print(f"    Captured {pagination_result['messages_found']} messages from initial load")
                print(f"    See {debug_path} for details")

            extracted = capture.extract_messages()
            viewer_interop_id = extracted["viewer_interop_id"]
            thread_key = extracted["thread_key"]
            thread_internal_id = extracted["thread_internal_id"]
            display_name = extracted["display_name"]
            participant_handle = extracted["participant_handle"]
            messages = extracted["messages"]

            if not thread_key:
                raise Exception("Could not extract thread_key from responses")

            if thread_key != expected_thread_fbid:
                raise Exception(
                    f"Thread key mismatch: expected {expected_thread_fbid} (from URL), "
                    f"got {thread_key}. The scanner captured responses for a different thread. "
                    "This may happen if the inbox preload fires queries for another thread."
                )

            cursor.execute("""
                INSERT OR IGNORE INTO threads (ig_thread_id, thread_internal_id, display_name, participant_handle, thread_url, last_scanned_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                thread_key,
                thread_internal_id,
                display_name or "Unknown",
                participant_handle,
                thread_url,
                datetime.now(timezone.utc).isoformat(),
                datetime.now(timezone.utc).isoformat(),
            ))

            cursor.execute("""
                UPDATE threads
                SET thread_internal_id = ?, display_name = ?, participant_handle = ?,
                    last_scanned_at = ?, updated_at = ?
                WHERE ig_thread_id = ?
            """, (
                thread_internal_id,
                display_name or "Unknown",
                participant_handle,
                datetime.now(timezone.utc).isoformat(),
                datetime.now(timezone.utc).isoformat(),
                thread_key,
            ))

            cursor.execute("SELECT id FROM threads WHERE ig_thread_id = ?", (thread_key,))
            thread_id = cursor.fetchone()[0]

            inserted_count = 0
            ignored_count = 0
            item_type_parsed_counts = {"reel": 0, "post": 0, "carousel": 0, "story": 0}
            item_type_inserted_counts = {"reel": 0, "post": 0, "carousel": 0, "story": 0}

            for message in messages:
                parsed = parse_message_node(message, viewer_interop_id or "")

                if parsed:
                    item_type = parsed["item_type"]
                    item_type_parsed_counts[item_type] += 1

                    cursor.execute("""
                        INSERT OR IGNORE INTO items (
                            thread_id, ig_message_id, item_type, media_shortcode, media_url,
                            poster_handle, caption, sent_at, sender, my_existing_reaction, dom_fingerprint
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        thread_id,
                        parsed["ig_message_id"],
                        parsed["item_type"],
                        parsed["media_shortcode"],
                        parsed["media_url"],
                        parsed["poster_handle"],
                        parsed["caption"],
                        parsed["sent_at"],
                        parsed["sender"],
                        parsed["my_existing_reaction"],
                        parsed["dom_fingerprint"],
                    ))

                    if cursor.rowcount > 0:
                        inserted_count += 1
                        item_type_inserted_counts[item_type] += 1
                    else:
                        ignored_count += 1

            conn.commit()

            cursor.execute("""
                UPDATE scan_runs
                SET thread_id = ?, completed_at = ?, status = 'completed', new_items_found = ?
                WHERE id = ?
            """, (thread_id, datetime.now(timezone.utc).isoformat(), inserted_count, scan_run_id))

            conn.commit()

            return {
                "success": True,
                "scan_run_id": scan_run_id,
                "thread_key": thread_key,
                "thread_internal_id": thread_internal_id,
                "display_name": display_name,
                "participant_handle": participant_handle,
                "messages_parsed": len(messages),
                "items_inserted": inserted_count,
                "items_ignored": ignored_count,
                "item_type_inserted_counts": item_type_inserted_counts,
                "pagination": pagination_result,
            }

    except Exception as e:
        if scan_run_id is not None:
            cursor.execute("""
                UPDATE scan_runs
                SET completed_at = ?, status = 'failed', error_message = ?
                WHERE id = ?
            """, (datetime.now(timezone.utc).isoformat(), str(e), scan_run_id))
            conn.commit()

        return {
            "success": False,
            "scan_run_id": scan_run_id,
            "error": str(e),
        }

    finally:
        conn.close()
