import json
import sqlite3

import pytest

from processor.index_db import get_birds, get_connection, write_recording


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


class TestGetBirds:
    """Test suite for get_birds function."""

    def test_get_birds_empty_detections(self):
        """Test that get_birds returns empty list for empty detections."""
        detections = {}
        result = get_birds(detections)
        assert result == []

    def test_get_birds_single_detection(self):
        """Test that get_birds returns single bird class."""
        detections = {"segment-1.ts": [{"class": "bird", "confidence": 0.95}]}
        result = get_birds(detections)
        assert result == ["bird"]

    def test_get_birds_multiple_detections_same_class(self):
        """Test that get_birds deduplicates bird classes."""
        detections = {
            "segment-1.ts": [{"class": "bird", "confidence": 0.95}],
            "segment-2.ts": [{"class": "bird", "confidence": 0.90}],
        }
        result = get_birds(detections)
        assert result == ["bird"]

    def test_get_birds_multiple_segments_empty_detection(self):
        """Test that get_birds handles empty segment detections."""
        detections = {
            "segment-1.ts": [{"class": "bird", "confidence": 0.95}],
            "segment-2.ts": [],
        }
        result = get_birds(detections)
        assert result == ["bird"]

    def test_get_birds_detection_without_class(self):
        """Test that get_birds ignores detections without class key."""
        detections = {
            "segment-1.ts": [{"confidence": 0.95}],
            "segment-2.ts": [{"class": "bird", "confidence": 0.90}],
        }
        result = get_birds(detections)
        assert result == ["bird"]

    def test_get_birds_multiple_classes_sorted(self):
        """Test that get_birds returns sorted unique classes."""
        detections = {
            "segment-1.ts": [{"class": "zebra", "confidence": 0.95}],
            "segment-2.ts": [{"class": "bird", "confidence": 0.90}],
            "segment-3.ts": [{"class": "zebra", "confidence": 0.85}],
        }
        result = get_birds(detections)
        assert result == ["bird", "zebra"]

    def test_get_birds_complex_detection_objects(self):
        """Test that get_birds extracts class from complex detection objects."""
        detections = {
            "segment-1.ts": [
                {"class": "bird", "confidence": 0.95, "roi": {"x1": 10, "y1": 20, "x2": 100, "y2": 200}},
                {"class": "bird", "confidence": 0.90, "roi": {"x1": 50, "y1": 60, "x2": 150, "y2": 160}},
            ]
        }
        result = get_birds(detections)
        assert result == ["bird"]


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
                birds TEXT,
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
            "SELECT date, stream, detections, birds FROM recordings WHERE date = ? AND stream = ?",
            (date, stream),
        ).fetchone()
        conn.close()

        assert row is not None
        assert row[0] == date
        assert row[1] == stream
        assert json.loads(row[2]) == detections
        assert json.loads(row[3]) == ["bird"]

    def test_write_recording_upserts_existing_row(self, test_db):
        """Test that write_recording updates detections and birds on conflict."""
        date = "2024-12-21"
        stream = "test_stream"
        detections1 = {"segment-1.ts": [{"class": "bird", "confidence": 0.90}]}
        detections2 = {"segment-2.ts": [{"class": "bird", "confidence": 0.95}]}

        write_recording(date, stream, detections1)
        write_recording(date, stream, detections2)

        conn = get_connection()
        row = conn.execute(
            "SELECT detections, birds FROM recordings WHERE date = ? AND stream = ?",
            (date, stream),
        ).fetchone()
        conn.close()

        assert row is not None
        stored_detections = json.loads(row[0])
        stored_birds = json.loads(row[1])
        assert stored_detections == detections2
        assert stored_birds == ["bird"]

    def test_write_recording_with_empty_detections(self, test_db):
        """Test that write_recording handles empty detection dict."""
        date = "2024-12-21"
        stream = "test_stream"
        detections = {}

        write_recording(date, stream, detections)

        conn = get_connection()
        row = conn.execute(
            "SELECT detections, birds FROM recordings WHERE date = ? AND stream = ?",
            (date, stream),
        ).fetchone()
        conn.close()

        assert row is not None
        assert json.loads(row[0]) == {}
        assert json.loads(row[1]) == []

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
            "SELECT detections, birds FROM recordings WHERE date = ? AND stream = ?",
            (date, stream),
        ).fetchone()
        conn.close()

        assert row is not None
        stored_detections = json.loads(row[0])
        stored_birds = json.loads(row[1])
        assert stored_detections == detections
        assert stored_birds == ["bird"]

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
            "SELECT detections, birds FROM recordings WHERE date = ? AND stream = ?",
            (date, stream),
        ).fetchone()
        conn.close()

        assert row is not None
        stored_detections = json.loads(row[0])
        stored_birds = json.loads(row[1])
        assert stored_detections == detections
        assert stored_detections["segment-1.ts"][0]["roi"]["x1"] == 10
        assert stored_birds == ["bird"]

    def test_write_recording_preserves_manual_annotations_on_upsert(self, test_db):
        """Test that write_recording does not update manual_annotations on upsert."""
        date = "2024-12-21"
        stream = "test_stream"

        # Insert initial row with manual annotations
        conn = get_connection()
        conn.execute(
            """
            INSERT INTO recordings (date, stream, detections, manual_annotations, birds)
            VALUES (?, ?, ?, ?, ?)
            """,
            (date, stream, json.dumps({}), "user_annotation", json.dumps([])),
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

    def test_write_recording_birds_not_updated_when_manual_annotations_exist(self, test_db):
        """Test that birds column is NOT updated on upsert when manual_annotations exist."""
        date = "2024-12-21"
        stream = "test_stream"

        # Insert initial row with manual annotations and initial birds
        conn = get_connection()
        conn.execute(
            """
            INSERT INTO recordings (date, stream, detections, manual_annotations, birds)
            VALUES (?, ?, ?, ?, ?)
            """,
            (date, stream, json.dumps({}), "user_annotation", json.dumps(["finch"])),
        )
        conn.commit()
        conn.close()

        # Update detections with different bird type
        detections = {"segment-1.ts": [{"class": "hawk", "confidence": 0.95}]}
        write_recording(date, stream, detections)

        # Verify birds column is NOT updated (remains "finch")
        conn = get_connection()
        row = conn.execute(
            "SELECT birds FROM recordings WHERE date = ? AND stream = ?",
            (date, stream),
        ).fetchone()
        conn.close()

        assert row is not None
        stored_birds = json.loads(row[0])
        assert stored_birds == ["finch"]

    def test_write_recording_birds_updated_when_no_manual_annotations(self, test_db):
        """Test that birds column IS updated on upsert when manual_annotations is NULL."""
        date = "2024-12-21"
        stream = "test_stream"

        # Insert initial row without manual annotations
        conn = get_connection()
        conn.execute(
            """
            INSERT INTO recordings (date, stream, detections, birds)
            VALUES (?, ?, ?, ?)
            """,
            (date, stream, json.dumps({"segment-1.ts": [{"class": "bird", "confidence": 0.90}]}), json.dumps(["bird"])),
        )
        conn.commit()
        conn.close()

        # Update detections with different bird type
        detections = {"segment-1.ts": [{"class": "hawk", "confidence": 0.95}]}
        write_recording(date, stream, detections)

        # Verify birds column IS updated
        conn = get_connection()
        row = conn.execute(
            "SELECT birds FROM recordings WHERE date = ? AND stream = ?",
            (date, stream),
        ).fetchone()
        conn.close()

        assert row is not None
        stored_birds = json.loads(row[0])
        assert stored_birds == ["hawk"]
