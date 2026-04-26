"""Settings API endpoints."""
import sqlite3
from fastapi import APIRouter, Depends, HTTPException
from api.db import get_db
from api.schemas import Setting, SettingUpdate

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_model=list[Setting])
def list_settings(conn: sqlite3.Connection = Depends(get_db)) -> list[Setting]:
    """
    List all application settings.

    Returns:
        List of all settings rows.
    """
    query = """
    SELECT key, value, description, updated_at
    FROM settings
    ORDER BY key
    """
    cursor = conn.execute(query)
    settings = []
    for row in cursor.fetchall():
        setting = Setting(
            key=row["key"],
            value=row["value"],
            description=row["description"],
            updated_at=row["updated_at"],
        )
        settings.append(setting)
    return settings


@router.patch("/{key}", response_model=Setting)
def update_setting(
    key: str, update: SettingUpdate, conn: sqlite3.Connection = Depends(get_db)
) -> Setting:
    """
    Update a setting value.

    Args:
        key: Setting key to update.
        update: New value.

    Returns:
        Updated setting.

    Raises:
        HTTPException: 404 if key doesn't exist, 422 if request malformed.
    """
    # Check if key exists
    check_query = "SELECT key FROM settings WHERE key = ?"
    if conn.execute(check_query, (key,)).fetchone() is None:
        raise HTTPException(status_code=404, detail="Setting not found")

    # Update setting
    update_query = """
    UPDATE settings
    SET value = ?, updated_at = CURRENT_TIMESTAMP
    WHERE key = ?
    """
    conn.execute(update_query, (update.value, key))
    conn.commit()

    # Return updated setting
    query = """
    SELECT key, value, description, updated_at
    FROM settings
    WHERE key = ?
    """
    cursor = conn.execute(query, (key,))
    row = cursor.fetchone()
    return Setting(
        key=row["key"],
        value=row["value"],
        description=row["description"],
        updated_at=row["updated_at"],
    )
