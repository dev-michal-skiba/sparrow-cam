import sqlite3

from cron.constants import INDEX_DB_PATH

BUSY_TIMEOUT_MS = 5000


def get_connection() -> sqlite3.Connection:
    """Open a connection to the index database in WAL mode with a busy timeout."""
    conn = sqlite3.connect(INDEX_DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS}")
    return conn


def is_manually_annotated(date: str, stream: str) -> bool:
    """Return True if the recording has manual annotations (an empty object counts)."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT manual_annotations IS NOT NULL FROM recordings WHERE date = ? AND stream = ?", (date, stream)
        ).fetchone()
    finally:
        conn.close()
    return bool(row and row[0])


def delete_recording(date: str, stream: str) -> None:
    """Delete a recording's row from the database."""
    conn = get_connection()
    try:
        with conn:
            conn.execute("DELETE FROM recordings WHERE date = ? AND stream = ?", (date, stream))
    finally:
        conn.close()
