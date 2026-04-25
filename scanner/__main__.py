"""CLI entry point for Instagram DM scanner."""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

import argparse

from db.init_db import initialize_database
from .scanner import run_scan


def main():
    parser = argparse.ArgumentParser(
        description="Scan Instagram DM thread for media items"
    )
    parser.add_argument(
        "--thread-url",
        required=True,
        help="Instagram DM thread URL (e.g., https://www.instagram.com/direct/t/123456/)"
    )
    parser.add_argument(
        "--max-messages",
        type=int,
        default=200,
        help="Maximum number of messages to scan (default: 200)"
    )
    parser.add_argument(
        "--db",
        default="instagram_dm_tracker.db",
        help="Path to SQLite database (default: instagram_dm_tracker.db)"
    )

    args = parser.parse_args()

    print("Instagram DM Media Tracker - Scanner")
    print("=" * 40)
    print(f"Thread URL: {args.thread_url}")
    print(f"Max messages: {args.max_messages}")
    print(f"Database: {args.db}")
    print()

    initialize_database(args.db)

    print()
    print("Starting scan...")
    print()

    result = run_scan(args.thread_url, args.db, args.max_messages)

    print()
    print("=" * 40)
    print("SCAN RESULTS")
    print("=" * 40)

    if result["success"]:
        print(f"  Thread: {result.get('display_name', 'Unknown')} (interop={result.get('thread_key')}, internal={result.get('thread_internal_id')})")
        print(f"  Messages parsed: {result['messages_parsed']}")
        times = result['item_type_inserted_counts']
        print(f"  Items inserted: {result['items_inserted']} (reels: {times['reel']}, posts: {times['post']}, carousels: {times['carousel']}, stories: {times['story']})")
        print(f"  Items skipped (already in DB): {result['items_ignored']}")
        print(f"  Scan run: id={result['scan_run_id']} status=completed")
        print(f"  DB: {args.db}")

        if not result['pagination']['success']:
            print()
            print(f"  Note: {result['pagination']['reason']}")
    else:
        print(f"  Scan failed: {result.get('error', 'Unknown error')}")
        print(f"  Scan run: id={result['scan_run_id']} status=failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
