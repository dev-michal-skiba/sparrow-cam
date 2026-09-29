import json
import sqlite3

import pytest

from processor.index_db import get_connection, write_recording


class TestGetConnection:
    """Test suite for get_connection function."""

    def test_get_connection_returns_connection_object(self, tmp_path, monkeypatch):
        """Test that get_connection returns a valid sqlite3.Connection object."""
        db_path = tmp_path / "test.db"
        monkeypatch.setattr("processor.index_db.INDEX_DB_PATH", db_path)

        conn = get_connection()

        assert isinstance(conn, sqlite3.Connection)
        conn.close()

    def test_get_connection_sets_wal_mode(self, tmp_path, monkeypatch):
        """Test that get_connection sets WAL mode."""
        db_path = tmp_path / "test.db"
        monkeypatch.setattr("processor.index_db.INDEX_DB_PATH", db_path)

        conn = get_connection()
        journal_mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        conn.close()

        assert journal_mode.upper() == "WAL"

    def test_get_connection_sets_busy_timeout(self, tmp_path, monkeypatch):
        """Test that get_connection sets busy timeout."""
        db_path = tmp_path / "test.db"
        monkeypatch.setattr("processor.index_db.INDEX_DB_PATH", db_path)

        conn = get_connection()
        busy_timeout = conn.execute("PRAGMA busy_timeout").fetchone()[0]
        conn.close()

        assert busy_timeout == 5000

    def test_get_connection_creates_database_file(self, tmp_path, monkeypatch):
        """Test that get_connection creates the database file."""
        db_path = tmp_path / "test.db"
        monkeypatch.setattr("processor.index_db.INDEX_DB_PATH", db_path)

        conn = get_connection()
        conn.close()

        assert db_path.exists()


class TestWriteRecording:
    """Test suite for write_recording function."""

    @pytest.fixture
    def test_db(self, tmp_path, monkeypatch):
        """Create a test database with recordings table."""
        db_path = tmp_path / "test.db"
        monkeypatch.setattr("processor.index_db.INDEX_DB_PATH", db_path)

        # Create the recordings table
        conn = get_connection()
        conn.execute("""
            CREATE TABLE recordings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                stream TEXT NOT NULL,
                detections TEXT NOT NULL,
                manual_annotations TEXT,
                UNIQUE(date, stream)
            )
            """)
        conn.commit()
        conn.close()

        return db_path

    def test_write_recording_inserts_new_row(self, test_db):
        """Test that write_recording inserts a new row into the database."""
        date = "2024-12-21"
        stream = "test_stream"
        detections = {"segment-1.ts": [{"class": "bird", "confidence": 0.95}]}

        write_recording(date, stream, detections)

        conn = get_connection()
        row = conn.execute(
            "SELECT date, stream, detections FROM recordings WHERE date = ? AND stream = ?",
            (date, stream),
        ).fetchone()
        conn.close()

        assert row is not None
        assert row[0] == date
        assert row[1] == stream
        assert json.loads(row[2]) == detections

    def test_write_recording_upserts_existing_row(self, test_db):
        """Test that write_recording updates detections on conflict."""
        date = "2024-12-21"
        stream = "test_stream"
        detections1 = {"segment-1.ts": [{"class": "bird", "confidence": 0.90}]}
        detections2 = {"segment-2.ts": [{"class": "bird", "confidence": 0.95}]}

        write_recording(date, stream, detections1)
        write_recording(date, stream, detections2)

        conn = get_connection()
        row = conn.execute(
            "SELECT detections FROM recordings WHERE date = ? AND stream = ?",
            (date, stream),
        ).fetchone()
        conn.close()

        assert row is not None
        stored_detections = json.loads(row[0])
        assert stored_detections == detections2

    def test_write_recording_with_empty_detections(self, test_db):
        """Test that write_recording handles empty detection dict."""
        date = "2024-12-21"
        stream = "test_stream"
        detections = {}

        write_recording(date, stream, detections)

        conn = get_connection()
        row = conn.execute(
            "SELECT detections FROM recordings WHERE date = ? AND stream = ?",
            (date, stream),
        ).fetchone()
        conn.close()

        assert row is not None
        assert json.loads(row[0]) == {}

    def test_write_recording_with_multiple_segments(self, test_db):
        """Test that write_recording stores multiple segment detections."""
        date = "2024-12-21"
        stream = "test_stream"
        detections = {
            "segment-1.ts": [{"class": "bird", "confidence": 0.90}],
            "segment-2.ts": [{"class": "bird", "confidence": 0.95}, {"class": "bird", "confidence": 0.88}],
            "segment-3.ts": [],
        }

        write_recording(date, stream, detections)

        conn = get_connection()
        row = conn.execute(
            "SELECT detections FROM recordings WHERE date = ? AND stream = ?",
            (date, stream),
        ).fetchone()
        conn.close()

        assert row is not None
        stored_detections = json.loads(row[0])
        assert stored_detections == detections

    def test_write_recording_handles_json_serialization(self, test_db):
        """Test that write_recording correctly serializes complex detection objects."""
        date = "2024-12-21"
        stream = "test_stream"
        detections = {
            "segment-1.ts": [{"class": "bird", "confidence": 0.95, "roi": {"x1": 10, "y1": 20, "x2": 100, "y2": 200}}]
        }

        write_recording(date, stream, detections)

        conn = get_connection()
        row = conn.execute(
            "SELECT detections FROM recordings WHERE date = ? AND stream = ?",
            (date, stream),
        ).fetchone()
        conn.close()

        assert row is not None
        stored_detections = json.loads(row[0])
        assert stored_detections == detections
        assert stored_detections["segment-1.ts"][0]["roi"]["x1"] == 10

    def test_write_recording_preserves_manual_annotations_on_upsert(self, test_db):
        """Test that write_recording does not update manual_annotations on upsert."""
        date = "2024-12-21"
        stream = "test_stream"

        # Insert initial row with manual annotations
        conn = get_connection()
        conn.execute(
            """
            INSERT INTO recordings (date, stream, detections, manual_annotations)
            VALUES (?, ?, ?, ?)
            """,
            (date, stream, json.dumps({}), "user_annotation"),
        )
        conn.commit()
        conn.close()

        # Update detections
        detections = {"segment-1.ts": [{"class": "bird", "confidence": 0.95}]}
        write_recording(date, stream, detections)

        # Verify manual_annotations is preserved
        conn = get_connection()
        row = conn.execute(
            "SELECT detections, manual_annotations FROM recordings WHERE date = ? AND stream = ?",
            (date, stream),
        ).fetchone()
        conn.close()

        assert row is not None
        assert json.loads(row[0]) == detections
        assert row[1] == "user_annotation"
