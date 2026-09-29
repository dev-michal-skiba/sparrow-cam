import json
import sqlite3
from pathlib import Path

INDEX_DB_PATH = Path("/var/lib/sparrow_cam/index.db")
BUSY_TIMEOUT_MS = 5000


def get_connection() -> sqlite3.Connection:
    """Open a connection to the index database in WAL mode with a busy timeout."""
    conn = sqlite3.connect(INDEX_DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS}")
    return conn


def write_recording(date: str, stream: str, detections: dict) -> None:
    """Insert or update a recordings row with detections, in a single transaction.

    Uses an upsert keyed on (date, stream) so extending an archive updates the
    existing row's detections without touching manual_annotations.

    Args:
        date: Recording date in YYYY-MM-DD format.
        stream: Archive directory name.
        detections: Merged detection data, keyed by segment name.
    """
    conn = get_connection()
    try:
        with conn:
            conn.execute(
                """
                INSERT INTO recordings (date, stream, detections)
                VALUES (?, ?, ?)
                ON CONFLICT(date, stream) DO UPDATE SET detections = excluded.detections
                """,
                (date, stream, json.dumps(detections)),
            )
    finally:
        conn.close()
