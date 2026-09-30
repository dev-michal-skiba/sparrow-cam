import json
import sqlite3
from pathlib import Path

INDEX_DB_PATH = Path("/var/lib/sparrow_cam/index.db")
BUSY_TIMEOUT_MS = 5000


def get_connection() -> sqlite3.Connection:
    """Open a connection to the index database in WAL mode with a busy timeout."""
    conn = sqlite3.connect(INDEX_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS}")
    return conn


def _filter_params(bird_filter: list[str], exclude_false_positives: bool, exclude_annotated: bool) -> tuple:
    """Parameters for the optional filter conditions shared by the listing queries."""
    return (
        int(bool(bird_filter)),
        json.dumps(bird_filter),
        int(exclude_annotated),
        int(exclude_false_positives),
    )


def list_recordings(
    conn: sqlite3.Connection,
    from_date: str,
    to_date: str,
    bird_filter: list[str],
    exclude_false_positives: bool,
    exclude_annotated: bool,
) -> list[sqlite3.Row]:
    """Return (date, stream, birds) rows in the date range, ordered by date then stream."""
    return conn.execute(
        """
        SELECT date, stream, birds FROM recordings
        WHERE date BETWEEN ? AND ?
        AND (? = 0 OR EXISTS (SELECT 1 FROM json_each(birds) WHERE value IN (SELECT value FROM json_each(?))))
        AND (? = 0 OR manual_annotations IS NULL)
        AND (? = 0 OR manual_annotations IS NULL OR manual_annotations != '{}')
        ORDER BY date, stream
        """,
        (from_date, to_date, *_filter_params(bird_filter, exclude_false_positives, exclude_annotated)),
    ).fetchall()


def recording_exists(conn: sqlite3.Connection, date: str, stream: str) -> bool:
    return conn.execute("SELECT 1 FROM recordings WHERE date = ? AND stream = ?", (date, stream)).fetchone() is not None


def find_adjacent(
    conn: sqlite3.Connection,
    date: str,
    stream: str,
    bird_filter: list[str],
    exclude_false_positives: bool,
    exclude_annotated: bool,
) -> tuple[sqlite3.Row | None, sqlite3.Row | None]:
    """Return the previous and next matching recordings around (date, stream)."""
    filters = _filter_params(bird_filter, exclude_false_positives, exclude_annotated)
    previous = conn.execute(
        """
        SELECT date, stream FROM recordings
        WHERE (date, stream) < (?, ?)
        AND (? = 0 OR EXISTS (SELECT 1 FROM json_each(birds) WHERE value IN (SELECT value FROM json_each(?))))
        AND (? = 0 OR manual_annotations IS NULL)
        AND (? = 0 OR manual_annotations IS NULL OR manual_annotations != '{}')
        ORDER BY date DESC, stream DESC LIMIT 1
        """,
        (date, stream, *filters),
    ).fetchone()
    following = conn.execute(
        """
        SELECT date, stream FROM recordings
        WHERE (date, stream) > (?, ?)
        AND (? = 0 OR EXISTS (SELECT 1 FROM json_each(birds) WHERE value IN (SELECT value FROM json_each(?))))
        AND (? = 0 OR manual_annotations IS NULL)
        AND (? = 0 OR manual_annotations IS NULL OR manual_annotations != '{}')
        ORDER BY date, stream LIMIT 1
        """,
        (date, stream, *filters),
    ).fetchone()

    return previous, following


def get_meta(conn: sqlite3.Connection, date: str, stream: str) -> dict | None:
    """Return the recording's meta dict (detections, plus manual_annotations when set), or None if absent."""
    row = conn.execute(
        "SELECT detections, manual_annotations FROM recordings WHERE date = ? AND stream = ?", (date, stream)
    ).fetchone()
    if row is None:
        return None
    meta = {"detections": json.loads(row["detections"] or "{}")}
    if row["manual_annotations"] is not None:
        meta["manual_annotations"] = json.loads(row["manual_annotations"])
    return meta


def get_manual_annotations(date: str, stream: str) -> dict | None:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT manual_annotations FROM recordings WHERE date = ? AND stream = ?", (date, stream)
        ).fetchone()
    finally:
        conn.close()
    if row is None or row["manual_annotations"] is None:
        return None
    return json.loads(row["manual_annotations"])


def birds_from_annotations(manual_annotations: dict) -> list[str]:
    return sorted({ann["bird_class"] for annotations in manual_annotations.values() for ann in annotations})
