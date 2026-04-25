"""One-off cleanup script for Prompt 3 bug — wrong thread_key cross-contamination.

The P3 scanner stored items under the wrong thread because the inbox preload
fired queries for other threads and the capture merged all responses together.
This script resets the database so we can re-scan with the fixed capture.

Keeps: settings, schema_version (schema structure).
Deletes: items, threads, scan_runs, carousel_slides (all data rows).
"""
import sqlite3
import sys
import os

DB_PATH = "instagram_dm_tracker.db"


def main():
    if not os.path.exists(DB_PATH):
        print(f"Database file not found: {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = OFF")
    cursor = conn.cursor()

    print("Current database state:")
    print()

    threads = cursor.execute("SELECT id, ig_thread_id, thread_internal_id, display_name, participant_handle FROM threads").fetchall()
    print("=== threads ===")
    if threads:
        for t in threads:
            print(f"  id={t[0]}  ig_thread_id={t[1]}  internal={t[2]}  display={t[3]}  handle={t[4]}")
    else:
        print("  (empty)")

    print()
    scan_runs = cursor.execute("SELECT id, thread_id, status, new_items_found, started_at FROM scan_runs ORDER BY id").fetchall()
    print("=== scan_runs ===")
    if scan_runs:
        for s in scan_runs:
            print(f"  id={s[0]}  thread_id={s[1]}  status={s[2]}  new_items={s[3]}  started={s[4]}")
    else:
        print("  (empty)")

    print()
    item_counts = cursor.execute("SELECT item_type, COUNT(*) FROM items GROUP BY item_type").fetchall()
    print("=== items ===")
    if item_counts:
        for ic in item_counts:
            print(f"  {ic[0]}: {ic[1]}")
    else:
        print("  (empty)")

    print()
    confirm = input("Type DELETE to confirm removal of all data rows: ")

    if confirm != "DELETE":
        print("Aborted.")
        conn.close()
        return

    cursor.execute("DELETE FROM carousel_slides")
    cursor.execute("DELETE FROM items")
    cursor.execute("DELETE FROM scan_runs")
    cursor.execute("DELETE FROM threads")
    cursor.execute("DELETE FROM sqlite_sequence")
    conn.commit()
    conn.execute("PRAGMA foreign_keys = ON")

    print()
    print("All data rows deleted. Schema and settings preserved.")
    print("Ready for re-scan.")

    conn.close()


if __name__ == "__main__":
    main()
