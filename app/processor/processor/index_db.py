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


def get_birds(detections: dict) -> list[str]:
    """Return the sorted unique bird class slugs found in detections."""
    return sorted({det["class"] for segment in detections.values() for det in segment if "class" in det})


def get_detections(date: str, stream: str) -> dict:
    """Return the stored detections for a recording, or an empty dict if it has no row."""
    conn = get_connection()
    try:
        row = conn.execute("SELECT detections FROM recordings WHERE date = ? AND stream = ?", (date, stream)).fetchone()
    finally:
        conn.close()
    return json.loads(row[0] or "{}") if row else {}


def write_recording(date: str, stream: str, detections: dict) -> None:
    """Insert or update a recordings row with detections, in a single transaction.

    Uses an upsert keyed on (date, stream) so extending an archive updates the
    existing row's detections without touching manual_annotations. The birds column
    is derived from detections, unless manual_annotations exist (they take precedence).

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
                INSERT INTO recordings (date, stream, detections, birds)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(date, stream) DO UPDATE SET
                    detections = excluded.detections,
                    birds = CASE WHEN manual_annotations IS NULL THEN excluded.birds ELSE birds END
                """,
                (date, stream, json.dumps(detections), json.dumps(get_birds(detections))),
            )
    finally:
        conn.close()
