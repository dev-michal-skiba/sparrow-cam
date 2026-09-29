import json
import logging

import pytest

from processor.index_db import get_connection
from processor.scripts import backfill_index_db


@pytest.fixture
def archive_path(tmp_path, monkeypatch):
    """Point the backfill script at an isolated, temporary archive path."""
    path = tmp_path / "archive"
    path.mkdir()
    monkeypatch.setattr(backfill_index_db, "ARCHIVE_PATH", path)
    return path


@pytest.fixture
def test_db(tmp_path, monkeypatch):
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
            birds TEXT,
            UNIQUE(date, stream)
        )
        """)
    conn.commit()
    conn.close()

    return db_path


class TestGetBirds:
    """Test suite for get_birds function."""

    def test_get_birds_from_detections_only(self):
        """Test extracting birds from detections when no manual_annotations."""
        meta = {
            "version": 1,
            "detections": {
                "segment-001.ts": [
                    {"class": "Great Tit", "confidence": 0.95},
                    {"class": "Pigeon", "confidence": 0.87},
                ],
                "segment-002.ts": [
                    {"class": "Great Tit", "confidence": 0.92},
                ],
            },
        }

        birds = backfill_index_db.get_birds(meta)

        assert birds == ["Great Tit", "Pigeon"]

    def test_get_birds_from_manual_annotations_only(self):
        """Test extracting birds from manual_annotations (precedence over detections)."""
        meta = {
            "version": 1,
            "detections": {
                "segment-001.ts": [
                    {"class": "Sparrow", "confidence": 0.85},
                ],
            },
            "manual_annotations": {
                "segment-001.ts": [
                    {"bird_class": "Great Tit", "is_false_positive": False},
                    {"bird_class": "Pigeon", "is_false_positive": False},
                ],
            },
        }

        birds = backfill_index_db.get_birds(meta)

        # Manual annotations take precedence, so Sparrow should not be included
        assert birds == ["Great Tit", "Pigeon"]

    def test_get_birds_manual_annotations_take_precedence(self):
        """Test that manual_annotations take precedence over detections."""
        meta = {
            "version": 1,
            "detections": {
                "segment-001.ts": [
                    {"class": "Sparrow", "confidence": 0.85},
                    {"class": "Robin", "confidence": 0.80},
                ],
            },
            "manual_annotations": {
                "segment-001.ts": [
                    {"bird_class": "Great Tit"},
                ],
            },
        }

        birds = backfill_index_db.get_birds(meta)

        assert birds == ["Great Tit"]

    def test_get_birds_empty_detections(self):
        """Test extracting birds from empty detections."""
        meta = {
            "version": 1,
            "detections": {},
        }

        birds = backfill_index_db.get_birds(meta)

        assert birds == []

    def test_get_birds_no_detections_key(self):
        """Test extracting birds when detections key is missing."""
        meta = {
            "version": 1,
        }

        birds = backfill_index_db.get_birds(meta)

        assert birds == []

    def test_get_birds_missing_class_field(self):
        """Test that detections without class field are skipped."""
        meta = {
            "version": 1,
            "detections": {
                "segment-001.ts": [
                    {"confidence": 0.95},  # Missing 'class' field
                    {"class": "Great Tit", "confidence": 0.92},
                ],
            },
        }

        birds = backfill_index_db.get_birds(meta)

        assert birds == ["Great Tit"]

    def test_get_birds_missing_bird_class_field_in_annotations(self):
        """Test that annotations without bird_class field are skipped."""
        meta = {
            "version": 1,
            "manual_annotations": {
                "segment-001.ts": [
                    {"is_false_positive": True},  # Missing 'bird_class' field
                    {"bird_class": "Great Tit"},
                ],
            },
        }

        birds = backfill_index_db.get_birds(meta)

        assert birds == ["Great Tit"]

    def test_get_birds_deduplicates_and_sorts(self):
        """Test that birds are deduplicated and sorted alphabetically."""
        meta = {
            "version": 1,
            "detections": {
                "segment-001.ts": [
                    {"class": "Zebra Finch", "confidence": 0.95},
                    {"class": "Great Tit", "confidence": 0.92},
                ],
                "segment-002.ts": [
                    {"class": "Pigeon", "confidence": 0.88},
                    {"class": "Great Tit", "confidence": 0.91},  # Duplicate
                ],
            },
        }

        birds = backfill_index_db.get_birds(meta)

        assert birds == ["Great Tit", "Pigeon", "Zebra Finch"]

    def test_get_birds_multiple_annotations_per_segment(self):
        """Test extracting birds from multiple annotations per segment."""
        meta = {
            "version": 1,
            "manual_annotations": {
                "segment-001.ts": [
                    {"bird_class": "Great Tit"},
                    {"bird_class": "Pigeon"},
                    {"bird_class": "Sparrow"},
                ],
            },
        }

        birds = backfill_index_db.get_birds(meta)

        assert birds == ["Great Tit", "Pigeon", "Sparrow"]


class TestBackfill:
    """Test suite for backfill function."""

    def test_backfill_inserts_new_recording(self, archive_path, test_db, caplog):
        """Test that backfill inserts a new recording into the database."""
        # Create a test archive
        stream_dir = archive_path / "2024" / "01" / "15" / "backyard"
        stream_dir.mkdir(parents=True)

        meta_data = {
            "version": 1,
            "detections": {
                "segment-001.ts": [
                    {"class": "Great Tit", "confidence": 0.95},
                ],
            },
        }
        meta_path = stream_dir / "meta.json"
        with open(meta_path, "w") as f:
            json.dump(meta_data, f)

        with caplog.at_level(logging.INFO):
            backfill_index_db.backfill()

        # Verify the row was inserted
        conn = get_connection()
        row = conn.execute(
            "SELECT date, stream, detections, birds FROM recordings WHERE date = ? AND stream = ?",
            ("2024-01-15", "backyard"),
        ).fetchone()
        conn.close()

        assert row is not None
        assert row[0] == "2024-01-15"
        assert row[1] == "backyard"
        assert json.loads(row[2]) == meta_data["detections"]
        assert json.loads(row[3]) == ["Great Tit"]

        # Verify log message
        assert "Inserted: 1" in caplog.text
        assert "skipped (already present): 0" in caplog.text
        assert "skipped (corrupt): 0" in caplog.text

    def test_backfill_skips_existing_recording(self, archive_path, test_db, caplog):
        """Test that backfill skips recording if one already exists."""
        # Create a test archive
        stream_dir = archive_path / "2024" / "01" / "15" / "backyard"
        stream_dir.mkdir(parents=True)

        meta_data = {
            "version": 1,
            "detections": {
                "segment-001.ts": [
                    {"class": "Great Tit", "confidence": 0.95},
                ],
            },
        }
        meta_path = stream_dir / "meta.json"
        with open(meta_path, "w") as f:
            json.dump(meta_data, f)

        # Insert existing record
        conn = get_connection()
        conn.execute(
            """
            INSERT INTO recordings (date, stream, detections, manual_annotations, birds)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("2024-01-15", "backyard", "{}", None, "[]"),
        )
        conn.commit()
        conn.close()

        with caplog.at_level(logging.INFO):
            backfill_index_db.backfill()

        # Verify log message
        assert "Inserted: 0" in caplog.text
        assert "skipped (already present): 1" in caplog.text
        assert "skipped (corrupt): 0" in caplog.text

    def test_backfill_skips_corrupt_json(self, archive_path, test_db, caplog):
        """Test that backfill skips corrupt meta.json files."""
        # Create a corrupt meta.json
        stream_dir = archive_path / "2024" / "01" / "15" / "backyard"
        stream_dir.mkdir(parents=True)

        meta_path = stream_dir / "meta.json"
        with open(meta_path, "w") as f:
            f.write("{invalid json")

        with caplog.at_level(logging.DEBUG):
            backfill_index_db.backfill()

        # Verify the corrupt file was logged and skipped
        assert "Skipping corrupt meta.json" in caplog.text
        assert str(meta_path) in caplog.text

        # Verify log message
        caplog_info = [r for r in caplog.records if r.levelno == logging.INFO]
        assert len(caplog_info) > 0
        assert "Inserted: 0" in caplog_info[-1].message
        assert "skipped (already present): 0" in caplog_info[-1].message
        assert "skipped (corrupt): 1" in caplog_info[-1].message

    def test_backfill_skips_unreadable_meta_json(self, archive_path, test_db, caplog):
        """Test that backfill handles file read errors gracefully."""
        # Create a directory instead of file to trigger OSError
        stream_dir = archive_path / "2024" / "01" / "15" / "backyard"
        stream_dir.mkdir(parents=True)

        meta_path = stream_dir / "meta.json"
        meta_path.mkdir()  # Create as directory, not file

        with caplog.at_level(logging.DEBUG):
            backfill_index_db.backfill()

        # Verify the file error was logged
        assert "Skipping corrupt meta.json" in caplog.text

        caplog_info = [r for r in caplog.records if r.levelno == logging.INFO]
        assert "skipped (corrupt): 1" in caplog_info[-1].message

    def test_backfill_multiple_archives(self, archive_path, test_db, caplog):
        """Test that backfill processes multiple archives."""
        # Create multiple archives
        for i in range(3):
            stream_dir = archive_path / "2024" / "01" / "15" / f"backyard_{i}"
            stream_dir.mkdir(parents=True)

            meta_data = {
                "version": 1,
                "detections": {
                    "segment-001.ts": [
                        {"class": "Great Tit", "confidence": 0.95},
                    ],
                },
            }
            meta_path = stream_dir / "meta.json"
            with open(meta_path, "w") as f:
                json.dump(meta_data, f)

        with caplog.at_level(logging.INFO):
            backfill_index_db.backfill()

        caplog_info = [r for r in caplog.records if r.levelno == logging.INFO]
        assert "Inserted: 3" in caplog_info[-1].message
        assert "skipped (already present): 0" in caplog_info[-1].message

    def test_backfill_preserves_manual_annotations_on_conflict(self, archive_path, test_db, caplog):
        """Test that backfill does not touch manual_annotations on INSERT OR IGNORE."""
        # Create a test archive
        stream_dir = archive_path / "2024" / "01" / "15" / "backyard"
        stream_dir.mkdir(parents=True)

        meta_data = {
            "version": 1,
            "detections": {
                "segment-002.ts": [
                    {"class": "Great Tit", "confidence": 0.95},
                ],
            },
        }
        meta_path = stream_dir / "meta.json"
        with open(meta_path, "w") as f:
            json.dump(meta_data, f)

        # Insert existing record with manual_annotations
        existing_annotations = [{"bird_class": "Sparrow"}]
        conn = get_connection()
        conn.execute(
            """
            INSERT INTO recordings (date, stream, detections, manual_annotations, birds)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                "2024-01-15",
                "backyard",
                json.dumps({"segment-001.ts": [{"class": "Pigeon"}]}),
                json.dumps(existing_annotations),
                json.dumps(["Pigeon"]),
            ),
        )
        conn.commit()
        conn.close()

        backfill_index_db.backfill()

        # Verify manual_annotations is preserved and detections are NOT updated
        conn = get_connection()
        row = conn.execute(
            "SELECT detections, manual_annotations, birds FROM recordings WHERE date = ? AND stream = ?",
            ("2024-01-15", "backyard"),
        ).fetchone()
        conn.close()

        assert row is not None
        # Should still have old detections (INSERT OR IGNORE)
        assert json.loads(row[0]) == {"segment-001.ts": [{"class": "Pigeon"}]}
        # Manual annotations should be preserved
        assert json.loads(row[1]) == existing_annotations
        assert json.loads(row[2]) == ["Pigeon"]

    def test_backfill_handles_manual_annotations_in_meta(self, archive_path, test_db, caplog):
        """Test that backfill stores manual_annotations from meta.json."""
        # Create a test archive with manual_annotations
        stream_dir = archive_path / "2024" / "01" / "15" / "backyard"
        stream_dir.mkdir(parents=True)

        meta_data = {
            "version": 1,
            "detections": {
                "segment-001.ts": [
                    {"class": "Sparrow", "confidence": 0.85},
                ],
            },
            "manual_annotations": {
                "segment-001.ts": [
                    {"bird_class": "Great Tit"},
                ],
            },
        }
        meta_path = stream_dir / "meta.json"
        with open(meta_path, "w") as f:
            json.dump(meta_data, f)

        backfill_index_db.backfill()

        # Verify manual_annotations were stored
        conn = get_connection()
        row = conn.execute(
            "SELECT manual_annotations, birds FROM recordings WHERE date = ? AND stream = ?",
            ("2024-01-15", "backyard"),
        ).fetchone()
        conn.close()

        assert row is not None
        assert json.loads(row[0]) == meta_data["manual_annotations"]
        # Birds should be from manual_annotations (precedence)
        assert json.loads(row[1]) == ["Great Tit"]

    def test_backfill_handles_null_manual_annotations(self, archive_path, test_db, caplog):
        """Test that backfill stores NULL for missing manual_annotations."""
        # Create a test archive without manual_annotations
        stream_dir = archive_path / "2024" / "01" / "15" / "backyard"
        stream_dir.mkdir(parents=True)

        meta_data = {
            "version": 1,
            "detections": {
                "segment-001.ts": [
                    {"class": "Great Tit", "confidence": 0.95},
                ],
            },
        }
        meta_path = stream_dir / "meta.json"
        with open(meta_path, "w") as f:
            json.dump(meta_data, f)

        backfill_index_db.backfill()

        # Verify manual_annotations is NULL
        conn = get_connection()
        row = conn.execute(
            "SELECT manual_annotations FROM recordings WHERE date = ? AND stream = ?",
            ("2024-01-15", "backyard"),
        ).fetchone()
        conn.close()

        assert row is not None
        assert row[0] is None

    def test_backfill_counts_correctly_mixed_scenarios(self, archive_path, test_db, caplog):
        """Test backfill counting in a scenario with inserted, existing, and corrupt files."""
        # Create new archive
        new_dir = archive_path / "2024" / "01" / "15" / "new_stream"
        new_dir.mkdir(parents=True)
        meta_data = {
            "version": 1,
            "detections": {"segment-001.ts": [{"class": "Great Tit", "confidence": 0.95}]},
        }
        with open(new_dir / "meta.json", "w") as f:
            json.dump(meta_data, f)

        # Create existing record
        existing_dir = archive_path / "2024" / "01" / "16" / "existing_stream"
        existing_dir.mkdir(parents=True)
        meta_data_existing = {
            "version": 1,
            "detections": {"segment-001.ts": [{"class": "Pigeon", "confidence": 0.88}]},
        }
        with open(existing_dir / "meta.json", "w") as f:
            json.dump(meta_data_existing, f)

        # Pre-insert the existing record
        conn = get_connection()
        conn.execute(
            """
            INSERT INTO recordings (date, stream, detections, manual_annotations, birds)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("2024-01-16", "existing_stream", json.dumps({}), None, "[]"),
        )
        conn.commit()
        conn.close()

        # Create corrupt archive
        corrupt_dir = archive_path / "2024" / "01" / "17" / "corrupt_stream"
        corrupt_dir.mkdir(parents=True)
        with open(corrupt_dir / "meta.json", "w") as f:
            f.write("{invalid")

        with caplog.at_level(logging.INFO):
            backfill_index_db.backfill()

        caplog_info = [r for r in caplog.records if r.levelno == logging.INFO]
        assert "Inserted: 1" in caplog_info[-1].message
        assert "skipped (already present): 1" in caplog_info[-1].message
        assert "skipped (corrupt): 1" in caplog_info[-1].message

    def test_backfill_processes_nested_archive_structure(self, archive_path, test_db, caplog):
        """Test that backfill correctly extracts date and stream from nested paths."""
        # Create archive with year/month/day/stream structure
        stream_dir = archive_path / "2024" / "12" / "25" / "frontyard"
        stream_dir.mkdir(parents=True)

        meta_data = {
            "version": 1,
            "detections": {
                "segment-001.ts": [
                    {"class": "Cardinal", "confidence": 0.95},
                ],
            },
        }
        meta_path = stream_dir / "meta.json"
        with open(meta_path, "w") as f:
            json.dump(meta_data, f)

        backfill_index_db.backfill()

        # Verify date and stream are correct
        conn = get_connection()
        row = conn.execute(
            "SELECT date, stream FROM recordings WHERE date = ? AND stream = ?",
            ("2024-12-25", "frontyard"),
        ).fetchone()
        conn.close()

        assert row is not None
        assert row[0] == "2024-12-25"
        assert row[1] == "frontyard"

    def test_backfill_handles_empty_archive_path(self, archive_path, test_db, caplog):
        """Test that backfill handles empty archive gracefully."""
        with caplog.at_level(logging.INFO):
            backfill_index_db.backfill()

        caplog_info = [r for r in caplog.records if r.levelno == logging.INFO]
        assert "Inserted: 0" in caplog_info[-1].message
        assert "skipped (already present): 0" in caplog_info[-1].message
        assert "skipped (corrupt): 0" in caplog_info[-1].message

    def test_backfill_is_idempotent(self, archive_path, test_db, caplog):
        """Test that running backfill twice produces the same result."""
        # Create a test archive
        stream_dir = archive_path / "2024" / "01" / "15" / "backyard"
        stream_dir.mkdir(parents=True)

        meta_data = {
            "version": 1,
            "detections": {
                "segment-001.ts": [
                    {"class": "Great Tit", "confidence": 0.95},
                ],
            },
        }
        meta_path = stream_dir / "meta.json"
        with open(meta_path, "w") as f:
            json.dump(meta_data, f)

        # Run backfill twice
        caplog.clear()
        with caplog.at_level(logging.INFO):
            backfill_index_db.backfill()

        caplog_info_1 = [r for r in caplog.records if r.levelno == logging.INFO]
        assert "Inserted: 1" in caplog_info_1[-1].message

        caplog.clear()
        with caplog.at_level(logging.INFO):
            backfill_index_db.backfill()

        caplog_info_2 = [r for r in caplog.records if r.levelno == logging.INFO]
        # Second run should skip the existing record
        assert "Inserted: 0" in caplog_info_2[-1].message
        assert "skipped (already present): 1" in caplog_info_2[-1].message
