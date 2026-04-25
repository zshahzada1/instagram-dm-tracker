"""Database initialization and migration system."""
import sqlite3
import os
from pathlib import Path


def get_current_version(conn):
    """Get the current schema version from the database."""
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT MAX(version) FROM schema_version")
        result = cursor.fetchone()
        return result[0] if result and result[0] is not None else 0
    except sqlite3.OperationalError:
        return 0


def apply_migration(conn, migration_path):
    """Apply a single migration file."""
    with open(migration_path, 'r') as f:
        sql = f.read()

    conn.executescript(sql)
    conn.commit()


def get_migration_files(migrations_dir):
    """Get sorted list of migration files."""
    if not os.path.exists(migrations_dir):
        return []

    files = []
    for f in os.listdir(migrations_dir):
        if f.endswith('.sql'):
            try:
                version = int(f.split('_')[0])
                files.append((version, os.path.join(migrations_dir, f)))
            except (ValueError, IndexError):
                continue

    files.sort(key=lambda x: x[0])
    return files


def initialize_database(db_path: str = "instagram_dm_tracker.db") -> None:
    """
    Initialize the database, applying any pending migrations.

    Args:
        db_path: Path to the SQLite database file.
    """
    migrations_dir = Path(__file__).parent.parent / "migrations"

    # Create database if it doesn't exist
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")

    try:
        current_version = get_current_version(conn)
        migrations = get_migration_files(migrations_dir)

        for version, migration_path in migrations:
            if version > current_version:
                print(f"Applying migration {version}: {Path(migration_path).name}")
                apply_migration(conn, migration_path)
                current_version = version
            else:
                # Migration already applied, verify it exists
                if version == current_version:
                    pass

        print(f"Database initialized at {db_path}")
        print(f"Schema version: {current_version}")

    finally:
        conn.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Initialize Instagram DM Tracker database")
    parser.add_argument(
        "--db",
        default="instagram_dm_tracker.db",
        help="Path to the database file (default: instagram_dm_tracker.db)"
    )

    args = parser.parse_args()
    initialize_database(args.db)
