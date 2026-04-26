"""Scans API endpoints."""
import re
import sqlite3
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from api.db import get_db
from api.schemas import ScanRequest, ScanResult, ScanRun, ConflictResponse

router = APIRouter(prefix="/scans", tags=["scans"])


@router.post("", response_model=ScanResult, status_code=200)
def create_scan(
    request: ScanRequest, conn: sqlite3.Connection = Depends(get_db)
) -> ScanResult:
    """
    Start a new scan of an Instagram DM thread.

    Args:
        request: Scan request with thread_url and optional max_messages.

    Returns:
        Scan result with inserted counts and pagination info.

    Raises:
        HTTPException: 409 if a scan is already running, 422 if URL malformed,
                       500 on scan failure.
    """
    # Validate thread URL format
    url_pattern = r"^https://www\.instagram\.com/direct/t/(\d+)/?$"
    match = re.match(url_pattern, request.thread_url)
    if not match:
        raise HTTPException(
            status_code=422,
            detail="Invalid thread URL format. Expected: https://www.instagram.com/direct/t/{numeric_id}/"
        )

    # Check for running scan
    running_scan = conn.execute(
        "SELECT id FROM scan_runs WHERE status = 'running'"
    ).fetchone()
    if running_scan:
        return JSONResponse(
            status_code=409,
            content={"detail": "Scan already in progress", "scan_run_id": running_scan["id"]},
        )

    # Import scanner here to avoid blocking on module load
    from scanner.scanner import run_scan

    # Run scan synchronously (blocks 30-60s)
    result = run_scan(request.thread_url, "instagram_dm_tracker.db", request.max_messages)

    # Convert to ScanResult model
    scan_result = ScanResult(**result)
    return scan_result


@router.get("", response_model=list[ScanRun])
def list_scans(
    thread_id: int | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    conn: sqlite3.Connection = Depends(get_db),
) -> list[ScanRun]:
    """
    List scan runs with optional filtering.

    Args:
        thread_id: Filter by thread ID.
        limit: Max runs to return (1-100).

    Returns:
        List of scan runs ordered by started_at DESC.
    """
    where_clauses = []
    params = []

    if thread_id is not None:
        where_clauses.append("thread_id = ?")
        params.append(thread_id)

    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

    query = f"""
    SELECT
        id,
        thread_id,
        started_at,
        completed_at,
        new_items_found,
        status,
        error_message
    FROM scan_runs
    WHERE {where_sql}
    ORDER BY started_at DESC
    LIMIT ?
    """
    params.append(limit)

    cursor = conn.execute(query, params)
    scans = []
    for row in cursor.fetchall():
        scan = ScanRun(
            id=row["id"],
            thread_id=row["thread_id"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
            new_items_found=row["new_items_found"] or 0,
            status=row["status"],
            error_message=row["error_message"],
        )
        scans.append(scan)

    return scans


@router.get("/{scan_id}", response_model=ScanRun)
def get_scan(scan_id: int, conn: sqlite3.Connection = Depends(get_db)) -> ScanRun:
    """
    Get a specific scan run by ID.

    Args:
        scan_id: Scan run database ID.

    Returns:
        Scan run details.

    Raises:
        HTTPException: 404 if scan not found.
    """
    query = """
    SELECT
        id,
        thread_id,
        started_at,
        completed_at,
        new_items_found,
        status,
        error_message
    FROM scan_runs
    WHERE id = ?
    """
    cursor = conn.execute(query, (scan_id,))
    row = cursor.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Scan run not found")

    return ScanRun(
        id=row["id"],
        thread_id=row["thread_id"],
        started_at=row["started_at"],
        completed_at=row["completed_at"],
        new_items_found=row["new_items_found"] or 0,
        status=row["status"],
        error_message=row["error_message"],
    )
