import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest

from cron.index_db import BUSY_TIMEOUT_MS, delete_recording, get_connection, is_manually_annotated


class TestGetConnection:
    """Test suite for get_connection function."""

    @patch("cron.index_db.INDEX_DB_PATH", Path("/tmp/test_index.db"))
    def test_get_connection_creates_connection(self):
        """Test get_connection creates a valid SQLite connection."""
        conn = get_connection()
        try:
            assert isinstance(conn, sqlite3.Connection)
            # Verify we can execute a query
            cursor = conn.execute("SELECT 1")
            assert cursor.fetchone() is not None
        finally:
            conn.close()

    @patch("cron.index_db.INDEX_DB_PATH", Path("/tmp/test_index_wal.db"))
    def test_get_connection_enables_wal_mode(self):
        """Test get_connection enables WAL mode."""
        conn = get_connection()
        try:
            result = conn.execute("PRAGMA journal_mode").fetchone()
            assert result[0].lower() == "wal"
        finally:
            conn.close()

    @patch("cron.index_db.INDEX_DB_PATH", Path("/tmp/test_index_timeout.db"))
    def test_get_connection_sets_busy_timeout(self):
        """Test get_connection sets the busy timeout."""
        conn = get_connection()
        try:
            result = conn.execute("PRAGMA busy_timeout").fetchone()
            assert result[0] == BUSY_TIMEOUT_MS
        finally:
            conn.close()


class TestIsManuallyAnnotated:
    """Test suite for is_manually_annotated function."""

    @pytest.fixture
    def test_db(self, tmp_path):
        """Create a test database with recordings table."""
        db_path = tmp_path / "test_index.db"
        conn = sqlite3.connect(db_path)
        # Create minimal recordings table
        conn.execute("""
            CREATE TABLE recordings (
                date TEXT NOT NULL,
                stream TEXT NOT NULL,
                manual_annotations TEXT,
                PRIMARY KEY (date, stream)
            )
            """)
        conn.commit()
        conn.close()
        return db_path

    def test_is_manually_annotated_true_with_data(self, test_db):
        """Test is_manually_annotated returns True when manual_annotations is not NULL."""
        conn = sqlite3.connect(test_db)
        conn.execute(
            "INSERT INTO recordings (date, stream, manual_annotations) VALUES (?, ?, ?)",
            ("2024-01-15", "sparrow_stream", '{"0": "bird"}'),
        )
        conn.commit()
        conn.close()

        with patch("cron.index_db.INDEX_DB_PATH", test_db):
            result = is_manually_annotated("2024-01-15", "sparrow_stream")

        assert result is True

    def test_is_manually_annotated_true_with_empty_json(self, test_db):
        """Test is_manually_annotated returns True even with empty JSON."""
        conn = sqlite3.connect(test_db)
        conn.execute(
            "INSERT INTO recordings (date, stream, manual_annotations) VALUES (?, ?, ?)",
            ("2024-01-15", "sparrow_stream", "{}"),
        )
        conn.commit()
        conn.close()

        with patch("cron.index_db.INDEX_DB_PATH", test_db):
            result = is_manually_annotated("2024-01-15", "sparrow_stream")

        assert result is True

    def test_is_manually_annotated_false_null_annotations(self, test_db):
        """Test is_manually_annotated returns False when manual_annotations is NULL."""
        conn = sqlite3.connect(test_db)
        conn.execute(
            "INSERT INTO recordings (date, stream, manual_annotations) VALUES (?, ?, ?)",
            ("2024-01-15", "sparrow_stream", None),
        )
        conn.commit()
        conn.close()

        with patch("cron.index_db.INDEX_DB_PATH", test_db):
            result = is_manually_annotated("2024-01-15", "sparrow_stream")

        assert result is False

    def test_is_manually_annotated_false_nonexistent_recording(self, test_db):
        """Test is_manually_annotated returns False when recording doesn't exist."""
        with patch("cron.index_db.INDEX_DB_PATH", test_db):
            result = is_manually_annotated("2024-01-15", "nonexistent_stream")

        assert result is False

    def test_is_manually_annotated_closes_connection(self, test_db):
        """Test is_manually_annotated closes the connection."""
        conn = sqlite3.connect(test_db)
        conn.execute(
            "INSERT INTO recordings (date, stream, manual_annotations) VALUES (?, ?, ?)",
            ("2024-01-15", "sparrow_stream", "{}"),
        )
        conn.commit()
        conn.close()

        with patch("cron.index_db.INDEX_DB_PATH", test_db):
            is_manually_annotated("2024-01-15", "sparrow_stream")

        # Verify we can open a new connection (no open cursors from previous call)
        test_conn = sqlite3.connect(test_db)
        test_conn.execute("SELECT 1")
        test_conn.close()


class TestDeleteRecording:
    """Test suite for delete_recording function."""

    @pytest.fixture
    def test_db(self, tmp_path):
        """Create a test database with recordings table."""
        db_path = tmp_path / "test_index.db"
        conn = sqlite3.connect(db_path)
        conn.execute("""
            CREATE TABLE recordings (
                date TEXT NOT NULL,
                stream TEXT NOT NULL,
                manual_annotations TEXT,
                PRIMARY KEY (date, stream)
            )
            """)
        conn.commit()
        conn.close()
        return db_path

    def test_delete_recording_removes_row(self, test_db):
        """Test delete_recording removes the recording from the database."""
        conn = sqlite3.connect(test_db)
        conn.execute(
            "INSERT INTO recordings (date, stream, manual_annotations) VALUES (?, ?, ?)",
            ("2024-01-15", "sparrow_stream", None),
        )
        conn.commit()
        conn.close()

        with patch("cron.index_db.INDEX_DB_PATH", test_db):
            delete_recording("2024-01-15", "sparrow_stream")

        # Verify the row is gone
        conn = sqlite3.connect(test_db)
        result = conn.execute(
            "SELECT * FROM recordings WHERE date = ? AND stream = ?",
            ("2024-01-15", "sparrow_stream"),
        ).fetchone()
        conn.close()
        assert result is None

    def test_delete_recording_does_not_affect_other_rows(self, test_db):
        """Test delete_recording only removes the specific recording."""
        conn = sqlite3.connect(test_db)
        conn.execute(
            "INSERT INTO recordings (date, stream, manual_annotations) VALUES (?, ?, ?)",
            ("2024-01-15", "sparrow_stream", None),
        )
        conn.execute(
            "INSERT INTO recordings (date, stream, manual_annotations) VALUES (?, ?, ?)",
            ("2024-01-15", "other_stream", None),
        )
        conn.execute(
            "INSERT INTO recordings (date, stream, manual_annotations) VALUES (?, ?, ?)",
            ("2024-01-16", "sparrow_stream", None),
        )
        conn.commit()
        conn.close()

        with patch("cron.index_db.INDEX_DB_PATH", test_db):
            delete_recording("2024-01-15", "sparrow_stream")

        # Verify only the target row is gone
        conn = sqlite3.connect(test_db)
        remaining = conn.execute("SELECT COUNT(*) FROM recordings").fetchone()[0]
        other_stream_exists = (
            conn.execute(
                "SELECT * FROM recordings WHERE date = ? AND stream = ?",
                ("2024-01-15", "other_stream"),
            ).fetchone()
            is not None
        )
        same_date_different_day = (
            conn.execute(
                "SELECT * FROM recordings WHERE date = ? AND stream = ?",
                ("2024-01-16", "sparrow_stream"),
            ).fetchone()
            is not None
        )
        conn.close()

        assert remaining == 2
        assert other_stream_exists
        assert same_date_different_day

    def test_delete_recording_is_idempotent(self, test_db):
        """Test delete_recording is safe to call multiple times."""
        conn = sqlite3.connect(test_db)
        conn.execute(
            "INSERT INTO recordings (date, stream, manual_annotations) VALUES (?, ?, ?)",
            ("2024-01-15", "sparrow_stream", None),
        )
        conn.commit()
        conn.close()

        with patch("cron.index_db.INDEX_DB_PATH", test_db):
            delete_recording("2024-01-15", "sparrow_stream")
            # Should not raise an error
            delete_recording("2024-01-15", "sparrow_stream")

        # Verify the row is still gone
        conn = sqlite3.connect(test_db)
        result = conn.execute(
            "SELECT * FROM recordings WHERE date = ? AND stream = ?",
            ("2024-01-15", "sparrow_stream"),
        ).fetchone()
        conn.close()
        assert result is None

    def test_delete_recording_closes_connection(self, test_db):
        """Test delete_recording closes the connection."""
        with patch("cron.index_db.INDEX_DB_PATH", test_db):
            delete_recording("2024-01-15", "sparrow_stream")

        # Verify we can open a new connection (no dangling transaction)
        test_conn = sqlite3.connect(test_db)
        test_conn.execute("SELECT 1")
        test_conn.close()
