"""Database connection helper for FastAPI."""
import sqlite3
from typing import Generator
from fastapi import Depends


def get_db() -> Generator[sqlite3.Connection, None, None]:
    """
    Get a database connection for the current request.

    Yields:
        sqlite3.Connection: Database connection with row_factory enabled.

    The connection is automatically closed when the request completes.
    """
    conn = sqlite3.connect("instagram_dm_tracker.db")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    finally:
        conn.close()
