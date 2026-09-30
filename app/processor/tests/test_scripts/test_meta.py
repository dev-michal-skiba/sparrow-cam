import argparse
import json
import sqlite3

import pytest

from processor.scripts import meta


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    """Create a temporary SQLite database for testing."""
    db_path = tmp_path / "test.db"
    monkeypatch.setattr("processor.scripts.meta.get_connection", lambda: sqlite3.connect(str(db_path)))

    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE recordings (
            date TEXT,
            stream TEXT,
            detections TEXT,
            birds TEXT,
            manual_annotations TEXT,
            PRIMARY KEY (date, stream)
        )
    """)
    conn.commit()
    conn.close()

    return db_path


@pytest.fixture
def archive_path(tmp_path, monkeypatch):
    """Point the meta script at an isolated, temporary archive path."""
    path = tmp_path / "archive"
    path.mkdir()
    monkeypatch.setattr(meta, "ARCHIVE_PATH", path)
    return path


@pytest.fixture
def sample_detections():
    """Sample detection data."""
    return {
        "segment-001.ts": [
            {"class": "Great Tit", "confidence": 0.95, "roi": {"x1": 10, "y1": 20, "x2": 100, "y2": 200}},
        ],
        "segment-002.ts": [
            {"class": "Pigeon", "confidence": 0.87, "roi": {"x1": 50, "y1": 60, "x2": 150, "y2": 260}},
        ],
    }


@pytest.fixture
def multiple_detections_in_db(tmp_db):
    """Insert multiple recordings into the test database."""
    conn = sqlite3.connect(str(tmp_db))

    detections1 = {
        "segment-001.ts": [
            {"class": "Great Tit", "confidence": 0.95, "roi": {"x1": 10, "y1": 20, "x2": 100, "y2": 200}},
        ],
    }

    detections2 = {
        "segment-001.ts": [
            {"class": "Pigeon", "confidence": 0.87, "roi": {"x1": 50, "y1": 60, "x2": 150, "y2": 260}},
            {"class": "Great Tit", "confidence": 0.92, "roi": {"x1": 20, "y1": 30, "x2": 120, "y2": 210}},
        ],
    }

    conn.execute(
        "INSERT INTO recordings (date, stream, detections) VALUES (?, ?, ?)",
        ("2024-01-15", "stream1", json.dumps(detections1)),
    )
    conn.execute(
        "INSERT INTO recordings (date, stream, detections) VALUES (?, ?, ?)",
        ("2024-01-15", "stream2", json.dumps(detections2)),
    )
    conn.commit()
    conn.close()

    return tmp_db


class TestGetStreamUrl:
    def test_get_stream_url(self):
        url = meta.get_stream_url("2024-01-15", "stream-name")
        assert url == "http://rpi.local/archive/2024/01/15/stream-name"

    def test_get_stream_url_different_date(self):
        url = meta.get_stream_url("2025-12-31", "another-stream")
        assert url == "http://rpi.local/archive/2025/12/31/another-stream"


class TestFindRecordings:
    def test_find_recordings_single(self, tmp_db, monkeypatch):
        """Test finding a single recording in the database."""
        monkeypatch.setattr("processor.scripts.meta.get_connection", lambda: sqlite3.connect(str(tmp_db)))

        conn = sqlite3.connect(str(tmp_db))
        detections = {"segment-001.ts": [{"class": "Great Tit", "confidence": 0.95, "roi": {}}]}
        conn.execute(
            "INSERT INTO recordings (date, stream, detections) VALUES (?, ?, ?)",
            ("2024-01-15", "stream1", json.dumps(detections)),
        )
        conn.commit()
        conn.close()

        recordings = meta.find_recordings()
        assert len(recordings) == 1
        date, stream, dets = recordings[0]
        assert date == "2024-01-15"
        assert stream == "stream1"
        assert dets == detections

    def test_find_recordings_multiple(self, tmp_db, monkeypatch):
        """Test finding multiple recordings in the database."""
        monkeypatch.setattr("processor.scripts.meta.get_connection", lambda: sqlite3.connect(str(tmp_db)))

        conn = sqlite3.connect(str(tmp_db))
        detections1 = {"segment-001.ts": [{"class": "Great Tit", "confidence": 0.95, "roi": {}}]}
        detections2 = {"segment-001.ts": [{"class": "Pigeon", "confidence": 0.87, "roi": {}}]}
        conn.execute(
            "INSERT INTO recordings (date, stream, detections) VALUES (?, ?, ?)",
            ("2024-01-15", "stream1", json.dumps(detections1)),
        )
        conn.execute(
            "INSERT INTO recordings (date, stream, detections) VALUES (?, ?, ?)",
            ("2024-01-15", "stream2", json.dumps(detections2)),
        )
        conn.commit()
        conn.close()

        recordings = meta.find_recordings()
        assert len(recordings) == 2

    def test_find_recordings_empty(self, tmp_db, monkeypatch):
        """Test finding recordings when database is empty."""
        monkeypatch.setattr("processor.scripts.meta.get_connection", lambda: sqlite3.connect(str(tmp_db)))

        recordings = meta.find_recordings()
        assert len(recordings) == 0

    def test_find_recordings_sorted(self, tmp_db, monkeypatch):
        """Test that recordings are returned in date/stream order."""
        monkeypatch.setattr("processor.scripts.meta.get_connection", lambda: sqlite3.connect(str(tmp_db)))

        conn = sqlite3.connect(str(tmp_db))
        detections = {"segment-001.ts": [{"class": "Great Tit", "confidence": 0.95, "roi": {}}]}

        # Insert in non-sorted order
        conn.execute(
            "INSERT INTO recordings (date, stream, detections) VALUES (?, ?, ?)",
            ("2024-01-15", "stream-c", json.dumps(detections)),
        )
        conn.execute(
            "INSERT INTO recordings (date, stream, detections) VALUES (?, ?, ?)",
            ("2024-01-14", "stream-b", json.dumps(detections)),
        )
        conn.execute(
            "INSERT INTO recordings (date, stream, detections) VALUES (?, ?, ?)",
            ("2024-01-14", "stream-a", json.dumps(detections)),
        )
        conn.commit()
        conn.close()

        recordings = meta.find_recordings()
        dates_streams = [(date, stream) for date, stream, _ in recordings]

        assert dates_streams == [
            ("2024-01-14", "stream-a"),
            ("2024-01-14", "stream-b"),
            ("2024-01-15", "stream-c"),
        ]


class TestGetMaxConfidencePerClass:
    def test_get_max_confidence_per_class(self, sample_detections):
        result = meta.get_max_confidence_per_class(sample_detections)
        assert result == {
            "Great Tit": 0.95,
            "Pigeon": 0.87,
        }

    def test_get_max_confidence_per_class_multiple_detections_same_class(self):
        detections = {
            "segment-001.ts": [
                {"class": "Great Tit", "confidence": 0.85, "roi": {}},
            ],
            "segment-002.ts": [
                {"class": "Great Tit", "confidence": 0.92, "roi": {}},
            ],
            "segment-003.ts": [
                {"class": "Great Tit", "confidence": 0.88, "roi": {}},
            ],
        }

        result = meta.get_max_confidence_per_class(detections)
        assert result == {"Great Tit": 0.92}

    def test_get_max_confidence_per_class_no_detections(self):
        detections = {}

        result = meta.get_max_confidence_per_class(detections)
        assert result == {}

    def test_get_max_confidence_per_class_empty_segments(self):
        detections = {
            "segment-001.ts": [],
            "segment-002.ts": [],
        }

        result = meta.get_max_confidence_per_class(detections)
        assert result == {}


class TestCmdSummarize:
    def test_cmd_summarize(self, tmp_db, monkeypatch, capsys):
        """Test summarize command with multiple recordings."""
        monkeypatch.setattr("processor.scripts.meta.get_connection", lambda: sqlite3.connect(str(tmp_db)))

        conn = sqlite3.connect(str(tmp_db))
        detections1 = {
            "segment-001.ts": [
                {"class": "Great Tit", "confidence": 0.95, "roi": {}},
            ],
        }
        detections2 = {
            "segment-001.ts": [
                {"class": "Pigeon", "confidence": 0.87, "roi": {}},
                {"class": "Great Tit", "confidence": 0.92, "roi": {}},
            ],
        }

        conn.execute(
            "INSERT INTO recordings (date, stream, detections) VALUES (?, ?, ?)",
            ("2024-01-15", "stream1", json.dumps(detections1)),
        )
        conn.execute(
            "INSERT INTO recordings (date, stream, detections) VALUES (?, ?, ?)",
            ("2024-01-15", "stream2", json.dumps(detections2)),
        )
        conn.commit()
        conn.close()

        args = argparse.Namespace(examples=5, bird_class=None)
        meta.cmd_summarize(args)

        captured = capsys.readouterr()
        output = captured.out

        # Check that output contains bird classes
        assert "# Great Tit" in output
        assert "# Pigeon" in output

        # Check that output contains confidence percentages
        assert "92%" in output
        assert "95%" in output
        assert "87%" in output

    def test_cmd_summarize_with_examples_limit(self, tmp_db, monkeypatch, capsys):
        """Test summarize with examples limit."""
        monkeypatch.setattr("processor.scripts.meta.get_connection", lambda: sqlite3.connect(str(tmp_db)))

        conn = sqlite3.connect(str(tmp_db))
        detections = {"segment-001.ts": [{"class": "Great Tit", "confidence": 0.85, "roi": {}}]}

        for i in range(3):
            conn.execute(
                "INSERT INTO recordings (date, stream, detections) VALUES (?, ?, ?)",
                (f"2024-01-{15+i:02d}", f"stream_{i}", json.dumps(detections)),
            )
        conn.commit()
        conn.close()

        args = argparse.Namespace(examples=2, bird_class=None)
        meta.cmd_summarize(args)

        captured = capsys.readouterr()
        output = captured.out

        # Should show class and percentage
        assert "# Great Tit" in output
        assert "85%" in output

    def test_cmd_summarize_empty_archive(self, tmp_db, monkeypatch, capsys):
        """Test summarize with no recordings."""
        monkeypatch.setattr("processor.scripts.meta.get_connection", lambda: sqlite3.connect(str(tmp_db)))

        args = argparse.Namespace(examples=5, bird_class=None)
        meta.cmd_summarize(args)

        captured = capsys.readouterr()
        assert captured.out == ""

    def test_cmd_summarize_filter_by_class(self, tmp_db, monkeypatch, capsys):
        """Test summarize filtered by bird class."""
        monkeypatch.setattr("processor.scripts.meta.get_connection", lambda: sqlite3.connect(str(tmp_db)))

        conn = sqlite3.connect(str(tmp_db))
        detections1 = {"segment-001.ts": [{"class": "Great Tit", "confidence": 0.95, "roi": {}}]}
        detections2 = {"segment-001.ts": [{"class": "Pigeon", "confidence": 0.87, "roi": {}}]}

        conn.execute(
            "INSERT INTO recordings (date, stream, detections) VALUES (?, ?, ?)",
            ("2024-01-15", "stream1", json.dumps(detections1)),
        )
        conn.execute(
            "INSERT INTO recordings (date, stream, detections) VALUES (?, ?, ?)",
            ("2024-01-15", "stream2", json.dumps(detections2)),
        )
        conn.commit()
        conn.close()

        args = argparse.Namespace(examples=5, bird_class="Pigeon")
        meta.cmd_summarize(args)

        captured = capsys.readouterr()
        output = captured.out

        assert "# Pigeon" in output
        assert "# Great Tit" not in output

    def test_cmd_summarize_filter_by_class_no_match(self, tmp_db, monkeypatch, capsys):
        """Test summarize with no matching class."""
        monkeypatch.setattr("processor.scripts.meta.get_connection", lambda: sqlite3.connect(str(tmp_db)))

        conn = sqlite3.connect(str(tmp_db))
        detections = {"segment-001.ts": [{"class": "Great Tit", "confidence": 0.95, "roi": {}}]}
        conn.execute(
            "INSERT INTO recordings (date, stream, detections) VALUES (?, ?, ?)",
            ("2024-01-15", "stream1", json.dumps(detections)),
        )
        conn.commit()
        conn.close()

        args = argparse.Namespace(examples=5, bird_class="NonExistent")
        meta.cmd_summarize(args)

        captured = capsys.readouterr()
        assert captured.out == ""

    def test_cmd_summarize_skip_empty_detections(self, tmp_db, monkeypatch, capsys):
        """Test summarize skips recordings with empty detections."""
        monkeypatch.setattr("processor.scripts.meta.get_connection", lambda: sqlite3.connect(str(tmp_db)))

        conn = sqlite3.connect(str(tmp_db))
        conn.execute(
            "INSERT INTO recordings (date, stream, detections) VALUES (?, ?, ?)",
            ("2024-01-15", "empty_stream", json.dumps({})),
        )
        conn.commit()
        conn.close()

        args = argparse.Namespace(examples=5, bird_class=None)
        meta.cmd_summarize(args)

        captured = capsys.readouterr()
        assert captured.out == ""


class TestCmdDelete:
    def test_cmd_delete_below_threshold(self, tmp_db, archive_path, monkeypatch, capsys):
        """Test deleting detections below a confidence threshold."""
        monkeypatch.setattr("processor.scripts.meta.get_connection", lambda: sqlite3.connect(str(tmp_db)))

        conn = sqlite3.connect(str(tmp_db))
        detections = {
            "segment-001.ts": [
                {"class": "Great Tit", "confidence": 0.95, "roi": {}},
            ],
            "segment-002.ts": [
                {"class": "Pigeon", "confidence": 0.87, "roi": {}},
            ],
        }

        conn.execute(
            "INSERT INTO recordings (date, stream, detections) VALUES (?, ?, ?)",
            ("2024-01-15", "test_stream", json.dumps(detections)),
        )
        conn.commit()
        conn.close()

        args = argparse.Namespace(bird_class="Pigeon", threshold=90, dry_run=False)
        meta.cmd_delete(args)

        captured = capsys.readouterr()
        assert "Removed detections from:" in captured.out

        # Verify database was updated
        conn = sqlite3.connect(str(tmp_db))
        row = conn.execute(
            "SELECT detections FROM recordings WHERE date = ? AND stream = ?", ("2024-01-15", "test_stream")
        ).fetchone()
        updated = json.loads(row[0]) if row else {}
        conn.close()

        # Pigeon at 87% confidence should be removed (below 90 threshold)
        assert "segment-002.ts" not in updated
        # Great Tit at 95% should remain
        assert "segment-001.ts" in updated

    def test_cmd_delete_exact_threshold(self, tmp_db, monkeypatch, capsys):
        """Test delete at exact threshold (should be kept)."""
        monkeypatch.setattr("processor.scripts.meta.get_connection", lambda: sqlite3.connect(str(tmp_db)))

        conn = sqlite3.connect(str(tmp_db))
        detections = {
            "segment-001.ts": [
                {"class": "Great Tit", "confidence": 0.90, "roi": {}},
            ],
        }

        conn.execute(
            "INSERT INTO recordings (date, stream, detections) VALUES (?, ?, ?)",
            ("2024-01-15", "test_stream", json.dumps(detections)),
        )
        conn.commit()
        conn.close()

        args = argparse.Namespace(bird_class="Great Tit", threshold=90, dry_run=False)
        meta.cmd_delete(args)

        # At exactly threshold, detection should be kept
        conn = sqlite3.connect(str(tmp_db))
        row = conn.execute(
            "SELECT detections FROM recordings WHERE date = ? AND stream = ?", ("2024-01-15", "test_stream")
        ).fetchone()
        updated = json.loads(row[0]) if row else {}
        conn.close()

        assert "segment-001.ts" in updated

    def test_cmd_delete_remove_entire_stream(self, tmp_db, archive_path, monkeypatch, capsys):
        """Test deleting an entire stream when all detections are removed."""
        monkeypatch.setattr("processor.scripts.meta.get_connection", lambda: sqlite3.connect(str(tmp_db)))

        # Create archive directory structure
        stream_path = archive_path / "2024" / "01" / "15" / "test_stream"
        stream_path.mkdir(parents=True)
        (stream_path / "segment.ts").touch()

        conn = sqlite3.connect(str(tmp_db))
        detections = {
            "segment-001.ts": [
                {"class": "Pigeon", "confidence": 0.85, "roi": {}},
            ],
        }

        conn.execute(
            "INSERT INTO recordings (date, stream, detections) VALUES (?, ?, ?)",
            ("2024-01-15", "test_stream", json.dumps(detections)),
        )
        conn.commit()
        conn.close()

        args = argparse.Namespace(bird_class="Pigeon", threshold=90, dry_run=False)
        meta.cmd_delete(args)

        captured = capsys.readouterr()
        assert "Removed stream:" in captured.out

        # Stream directory should be deleted
        assert not stream_path.exists()

        # Record should be deleted from database
        conn = sqlite3.connect(str(tmp_db))
        row = conn.execute(
            "SELECT * FROM recordings WHERE date = ? AND stream = ?", ("2024-01-15", "test_stream")
        ).fetchone()
        conn.close()
        assert row is None

    def test_cmd_delete_dry_run(self, tmp_db, monkeypatch, capsys):
        """Test delete in dry-run mode (no actual changes)."""
        monkeypatch.setattr("processor.scripts.meta.get_connection", lambda: sqlite3.connect(str(tmp_db)))

        conn = sqlite3.connect(str(tmp_db))
        original_detections = {
            "segment-001.ts": [
                {"class": "Great Tit", "confidence": 0.95, "roi": {}},
            ],
            "segment-002.ts": [
                {"class": "Pigeon", "confidence": 0.87, "roi": {}},
            ],
        }

        conn.execute(
            "INSERT INTO recordings (date, stream, detections) VALUES (?, ?, ?)",
            ("2024-01-15", "test_stream", json.dumps(original_detections)),
        )
        conn.commit()
        conn.close()

        args = argparse.Namespace(bird_class="Pigeon", threshold=90, dry_run=True)
        meta.cmd_delete(args)

        captured = capsys.readouterr()
        assert "Removed detections from:" in captured.out

        # Database should NOT be modified in dry-run
        conn = sqlite3.connect(str(tmp_db))
        row = conn.execute(
            "SELECT detections FROM recordings WHERE date = ? AND stream = ?", ("2024-01-15", "test_stream")
        ).fetchone()
        current = json.loads(row[0]) if row else {}
        conn.close()

        assert current == original_detections

    def test_cmd_delete_multiple_detections_per_segment(self, tmp_db, monkeypatch, capsys):
        """Test delete when a segment has multiple detections."""
        monkeypatch.setattr("processor.scripts.meta.get_connection", lambda: sqlite3.connect(str(tmp_db)))

        conn = sqlite3.connect(str(tmp_db))
        detections = {
            "segment-001.ts": [
                {"class": "Great Tit", "confidence": 0.95, "roi": {}},
                {"class": "Pigeon", "confidence": 0.85, "roi": {}},
            ],
        }

        conn.execute(
            "INSERT INTO recordings (date, stream, detections) VALUES (?, ?, ?)",
            ("2024-01-15", "test_stream", json.dumps(detections)),
        )
        conn.commit()
        conn.close()

        # Remove Pigeon detections with 90% threshold
        args = argparse.Namespace(bird_class="Pigeon", threshold=90, dry_run=False)
        meta.cmd_delete(args)

        conn = sqlite3.connect(str(tmp_db))
        row = conn.execute(
            "SELECT detections FROM recordings WHERE date = ? AND stream = ?", ("2024-01-15", "test_stream")
        ).fetchone()
        updated = json.loads(row[0]) if row else {}
        conn.close()

        # Segment should still exist with only Great Tit detection
        assert "segment-001.ts" in updated
        assert len(updated["segment-001.ts"]) == 1
        assert updated["segment-001.ts"][0]["class"] == "Great Tit"

    def test_cmd_delete_no_detections_modified(self, tmp_db, monkeypatch, capsys):
        """Test delete when no detections match the criteria."""
        monkeypatch.setattr("processor.scripts.meta.get_connection", lambda: sqlite3.connect(str(tmp_db)))

        conn = sqlite3.connect(str(tmp_db))
        detections = {"segment-001.ts": [{"class": "Great Tit", "confidence": 0.95, "roi": {}}]}
        conn.execute(
            "INSERT INTO recordings (date, stream, detections) VALUES (?, ?, ?)",
            ("2024-01-15", "test_stream", json.dumps(detections)),
        )
        conn.commit()
        conn.close()

        args = argparse.Namespace(bird_class="NonExistent", threshold=50, dry_run=False)
        meta.cmd_delete(args)

        captured = capsys.readouterr()
        # Should not print anything if no files were modified
        assert captured.out == ""

    def test_cmd_delete_multiple_segments_partial_removal(self, tmp_db, monkeypatch, capsys):
        """Test delete removing detections from multiple segments."""
        monkeypatch.setattr("processor.scripts.meta.get_connection", lambda: sqlite3.connect(str(tmp_db)))

        conn = sqlite3.connect(str(tmp_db))
        detections = {
            "segment-001.ts": [
                {"class": "Great Tit", "confidence": 0.95, "roi": {}},
            ],
            "segment-002.ts": [
                {"class": "Pigeon", "confidence": 0.85, "roi": {}},
            ],
            "segment-003.ts": [
                {"class": "Pigeon", "confidence": 0.92, "roi": {}},
            ],
        }

        conn.execute(
            "INSERT INTO recordings (date, stream, detections) VALUES (?, ?, ?)",
            ("2024-01-15", "test_stream", json.dumps(detections)),
        )
        conn.commit()
        conn.close()

        # Remove Pigeon detections below 90%
        args = argparse.Namespace(bird_class="Pigeon", threshold=90, dry_run=False)
        meta.cmd_delete(args)

        captured = capsys.readouterr()
        assert "Removed detections from:" in captured.out

        conn = sqlite3.connect(str(tmp_db))
        row = conn.execute(
            "SELECT detections FROM recordings WHERE date = ? AND stream = ?", ("2024-01-15", "test_stream")
        ).fetchone()
        updated = json.loads(row[0]) if row else {}
        conn.close()

        # segment-001 and segment-003 should remain
        assert "segment-001.ts" in updated
        assert "segment-002.ts" not in updated
        assert "segment-003.ts" in updated


class TestMain:
    def test_main_requires_command(self):
        # Should fail when no command provided
        with pytest.raises(SystemExit):
            meta.main()
