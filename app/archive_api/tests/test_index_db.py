import json
import sqlite3

import pytest

from archive_api import index_db


@pytest.fixture
def db_connection(tmp_path, monkeypatch):
    """Create a temporary SQLite database and return connection."""
    db_path = tmp_path / "test.db"
    monkeypatch.setattr("archive_api.index_db.INDEX_DB_PATH", db_path)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE recordings (
            date TEXT NOT NULL,
            stream TEXT NOT NULL,
            detections TEXT,
            manual_annotations TEXT,
            birds TEXT,
            PRIMARY KEY (date, stream)
        )
        """)
    conn.commit()
    return conn


class TestListRecordings:
    def test_empty_database(self, db_connection):
        rows = index_db.list_recordings(db_connection, "2025-01-01", "2025-01-31", [], False, False)
        assert rows == []

    def test_single_recording(self, db_connection):
        db_connection.execute(
            "INSERT INTO recordings (date, stream, detections, birds) VALUES (?, ?, ?, ?)",
            ("2025-01-15", "stream_a", json.dumps({}), json.dumps(["sparrow"])),
        )
        db_connection.commit()

        rows = index_db.list_recordings(db_connection, "2025-01-01", "2025-01-31", [], False, False)
        assert len(rows) == 1
        assert rows[0]["date"] == "2025-01-15"
        assert rows[0]["stream"] == "stream_a"

    def test_date_range_filtering(self, db_connection):
        db_connection.execute(
            "INSERT INTO recordings (date, stream, detections, birds) VALUES (?, ?, ?, ?)",
            ("2025-01-10", "stream_a", json.dumps({}), json.dumps([])),
        )
        db_connection.execute(
            "INSERT INTO recordings (date, stream, detections, birds) VALUES (?, ?, ?, ?)",
            ("2025-01-15", "stream_b", json.dumps({}), json.dumps([])),
        )
        db_connection.execute(
            "INSERT INTO recordings (date, stream, detections, birds) VALUES (?, ?, ?, ?)",
            ("2025-01-20", "stream_c", json.dumps({}), json.dumps([])),
        )
        db_connection.commit()

        rows = index_db.list_recordings(db_connection, "2025-01-12", "2025-01-18", [], False, False)
        assert len(rows) == 1
        assert rows[0]["stream"] == "stream_b"

    def test_bird_filter(self, db_connection):
        db_connection.execute(
            "INSERT INTO recordings (date, stream, detections, birds) VALUES (?, ?, ?, ?)",
            ("2025-01-15", "stream_sparrow", json.dumps({}), json.dumps(["sparrow"])),
        )
        db_connection.execute(
            "INSERT INTO recordings (date, stream, detections, birds) VALUES (?, ?, ?, ?)",
            ("2025-01-15", "stream_cardinal", json.dumps({}), json.dumps(["cardinal"])),
        )
        db_connection.commit()

        rows = index_db.list_recordings(db_connection, "2025-01-01", "2025-01-31", ["sparrow"], False, False)
        assert len(rows) == 1
        assert rows[0]["stream"] == "stream_sparrow"

    def test_exclude_annotated_filter(self, db_connection):
        db_connection.execute(
            "INSERT INTO recordings (date, stream, detections, manual_annotations, birds) VALUES (?, ?, ?, ?, ?)",
            ("2025-01-15", "stream_annotated", json.dumps({}), json.dumps({"seg.ts": []}), json.dumps(["sparrow"])),
        )
        db_connection.execute(
            "INSERT INTO recordings (date, stream, detections, birds) VALUES (?, ?, ?, ?)",
            ("2025-01-15", "stream_unannotated", json.dumps({}), json.dumps(["cardinal"])),
        )
        db_connection.commit()

        rows = index_db.list_recordings(db_connection, "2025-01-01", "2025-01-31", [], False, True)
        assert len(rows) == 1
        assert rows[0]["stream"] == "stream_unannotated"

    def test_exclude_false_positives_filter(self, db_connection):
        db_connection.execute(
            "INSERT INTO recordings (date, stream, detections, manual_annotations, birds) VALUES (?, ?, ?, ?, ?)",
            ("2025-01-15", "stream_empty", json.dumps({}), json.dumps({}), json.dumps([])),
        )
        db_connection.execute(
            "INSERT INTO recordings (date, stream, detections, manual_annotations, birds) VALUES (?, ?, ?, ?, ?)",
            ("2025-01-15", "stream_annotated", json.dumps({}), json.dumps({"seg.ts": []}), json.dumps(["sparrow"])),
        )
        db_connection.commit()

        rows = index_db.list_recordings(db_connection, "2025-01-01", "2025-01-31", [], True, False)
        assert len(rows) == 1
        assert rows[0]["stream"] == "stream_annotated"

    def test_ordered_by_date_then_stream(self, db_connection):
        db_connection.execute(
            "INSERT INTO recordings (date, stream, detections, birds) VALUES (?, ?, ?, ?)",
            ("2025-01-15", "stream_z", json.dumps({}), json.dumps([])),
        )
        db_connection.execute(
            "INSERT INTO recordings (date, stream, detections, birds) VALUES (?, ?, ?, ?)",
            ("2025-01-15", "stream_a", json.dumps({}), json.dumps([])),
        )
        db_connection.execute(
            "INSERT INTO recordings (date, stream, detections, birds) VALUES (?, ?, ?, ?)",
            ("2025-01-10", "stream_m", json.dumps({}), json.dumps([])),
        )
        db_connection.commit()

        rows = index_db.list_recordings(db_connection, "2025-01-01", "2025-01-31", [], False, False)
        assert len(rows) == 3
        assert rows[0]["date"] == "2025-01-10"
        assert rows[1]["stream"] == "stream_a"
        assert rows[2]["stream"] == "stream_z"


class TestRecordingExists:
    def test_recording_exists_true(self, db_connection):
        db_connection.execute(
            "INSERT INTO recordings (date, stream, detections, birds) VALUES (?, ?, ?, ?)",
            ("2025-01-15", "stream_a", json.dumps({}), json.dumps([])),
        )
        db_connection.commit()

        assert index_db.recording_exists(db_connection, "2025-01-15", "stream_a") is True

    def test_recording_exists_false(self, db_connection):
        assert index_db.recording_exists(db_connection, "2025-01-15", "stream_a") is False


class TestFindAdjacent:
    def test_no_adjacent_for_single_recording(self, db_connection):
        db_connection.execute(
            "INSERT INTO recordings (date, stream, detections, birds) VALUES (?, ?, ?, ?)",
            ("2025-01-15", "stream_a", json.dumps({}), json.dumps([])),
        )
        db_connection.commit()

        prev_row, next_row = index_db.find_adjacent(db_connection, "2025-01-15", "stream_a", [], False, False)
        assert prev_row is None
        assert next_row is None

    def test_adjacent_same_day(self, db_connection):
        db_connection.execute(
            "INSERT INTO recordings (date, stream, detections, birds) VALUES (?, ?, ?, ?)",
            ("2025-01-15", "stream_a", json.dumps({}), json.dumps([])),
        )
        db_connection.execute(
            "INSERT INTO recordings (date, stream, detections, birds) VALUES (?, ?, ?, ?)",
            ("2025-01-15", "stream_b", json.dumps({}), json.dumps([])),
        )
        db_connection.commit()

        prev_row, next_row = index_db.find_adjacent(db_connection, "2025-01-15", "stream_a", [], False, False)
        assert prev_row is None
        assert next_row["stream"] == "stream_b"

    def test_adjacent_across_dates(self, db_connection):
        db_connection.execute(
            "INSERT INTO recordings (date, stream, detections, birds) VALUES (?, ?, ?, ?)",
            ("2025-01-14", "stream_a", json.dumps({}), json.dumps([])),
        )
        db_connection.execute(
            "INSERT INTO recordings (date, stream, detections, birds) VALUES (?, ?, ?, ?)",
            ("2025-01-15", "stream_b", json.dumps({}), json.dumps([])),
        )
        db_connection.execute(
            "INSERT INTO recordings (date, stream, detections, birds) VALUES (?, ?, ?, ?)",
            ("2025-01-16", "stream_c", json.dumps({}), json.dumps([])),
        )
        db_connection.commit()

        prev_row, next_row = index_db.find_adjacent(db_connection, "2025-01-15", "stream_b", [], False, False)
        assert prev_row["date"] == "2025-01-14"
        assert next_row["date"] == "2025-01-16"

    def test_adjacent_with_bird_filter(self, db_connection):
        db_connection.execute(
            "INSERT INTO recordings (date, stream, detections, birds) VALUES (?, ?, ?, ?)",
            ("2025-01-14", "stream_a", json.dumps({}), json.dumps(["sparrow"])),
        )
        db_connection.execute(
            "INSERT INTO recordings (date, stream, detections, birds) VALUES (?, ?, ?, ?)",
            ("2025-01-15", "stream_b", json.dumps({}), json.dumps(["cardinal"])),
        )
        db_connection.execute(
            "INSERT INTO recordings (date, stream, detections, birds) VALUES (?, ?, ?, ?)",
            ("2025-01-16", "stream_c", json.dumps({}), json.dumps(["sparrow"])),
        )
        db_connection.commit()

        prev_row, next_row = index_db.find_adjacent(db_connection, "2025-01-15", "stream_b", ["sparrow"], False, False)
        assert prev_row["date"] == "2025-01-14"
        assert next_row["date"] == "2025-01-16"


class TestGetMeta:
    def test_recording_not_found(self, db_connection):
        result = index_db.get_meta(db_connection, "2025-01-15", "stream_a")
        assert result is None

    def test_get_detections_only(self, db_connection):
        detections = {"seg1.ts": [{"class": "sparrow"}]}
        db_connection.execute(
            "INSERT INTO recordings (date, stream, detections, birds) VALUES (?, ?, ?, ?)",
            ("2025-01-15", "stream_a", json.dumps(detections), json.dumps(["sparrow"])),
        )
        db_connection.commit()

        result = index_db.get_meta(db_connection, "2025-01-15", "stream_a")
        assert result is not None
        assert result["detections"] == detections
        assert "manual_annotations" not in result

    def test_get_with_manual_annotations(self, db_connection):
        detections = {"seg1.ts": [{"class": "sparrow"}]}
        annotations = {"seg1.ts": [{"bird_class": "sparrow"}]}
        db_connection.execute(
            "INSERT INTO recordings (date, stream, detections, manual_annotations, birds) VALUES (?, ?, ?, ?, ?)",
            ("2025-01-15", "stream_a", json.dumps(detections), json.dumps(annotations), json.dumps(["sparrow"])),
        )
        db_connection.commit()

        result = index_db.get_meta(db_connection, "2025-01-15", "stream_a")
        assert result["detections"] == detections
        assert result["manual_annotations"] == annotations

    def test_get_empty_detections(self, db_connection):
        db_connection.execute(
            "INSERT INTO recordings (date, stream, detections, birds) VALUES (?, ?, ?, ?)",
            ("2025-01-15", "stream_a", None, json.dumps([])),
        )
        db_connection.commit()

        result = index_db.get_meta(db_connection, "2025-01-15", "stream_a")
        assert result["detections"] == {}


class TestGetManualAnnotations:
    def test_no_annotations(self, tmp_path, monkeypatch):
        db_path = tmp_path / "test.db"
        monkeypatch.setattr("archive_api.index_db.INDEX_DB_PATH", db_path)

        conn = sqlite3.connect(db_path)
        conn.execute("""
            CREATE TABLE recordings (
                date TEXT NOT NULL,
                stream TEXT NOT NULL,
                detections TEXT,
                manual_annotations TEXT,
                birds TEXT,
                PRIMARY KEY (date, stream)
            )
            """)
        conn.execute(
            "INSERT INTO recordings (date, stream, detections, birds) VALUES (?, ?, ?, ?)",
            ("2025-01-15", "stream_a", json.dumps({}), json.dumps([])),
        )
        conn.commit()
        conn.close()

        result = index_db.get_manual_annotations("2025-01-15", "stream_a")
        assert result is None

    def test_get_annotations(self, tmp_path, monkeypatch):
        db_path = tmp_path / "test.db"
        monkeypatch.setattr("archive_api.index_db.INDEX_DB_PATH", db_path)

        annotations = {"seg1.ts": [{"bird_class": "sparrow"}]}
        conn = sqlite3.connect(db_path)
        conn.execute("""
            CREATE TABLE recordings (
                date TEXT NOT NULL,
                stream TEXT NOT NULL,
                detections TEXT,
                manual_annotations TEXT,
                birds TEXT,
                PRIMARY KEY (date, stream)
            )
            """)
        conn.execute(
            "INSERT INTO recordings (date, stream, detections, manual_annotations, birds) VALUES (?, ?, ?, ?, ?)",
            ("2025-01-15", "stream_a", json.dumps({}), json.dumps(annotations), json.dumps(["sparrow"])),
        )
        conn.commit()
        conn.close()

        result = index_db.get_manual_annotations("2025-01-15", "stream_a")
        assert result == annotations


class TestBirdsFromAnnotations:
    def test_empty_annotations(self):
        result = index_db.birds_from_annotations({})
        assert result == []

    def test_single_bird(self):
        annotations = {"seg1.ts": [{"bird_class": "sparrow"}]}
        result = index_db.birds_from_annotations(annotations)
        assert result == ["sparrow"]

    def test_multiple_birds_same_segment(self):
        annotations = {"seg1.ts": [{"bird_class": "sparrow"}, {"bird_class": "cardinal"}]}
        result = index_db.birds_from_annotations(annotations)
        assert set(result) == {"sparrow", "cardinal"}

    def test_multiple_birds_multiple_segments(self):
        annotations = {
            "seg1.ts": [{"bird_class": "sparrow"}],
            "seg2.ts": [{"bird_class": "cardinal"}],
            "seg3.ts": [{"bird_class": "sparrow"}],
        }
        result = index_db.birds_from_annotations(annotations)
        assert set(result) == {"sparrow", "cardinal"}

    def test_sorted_output(self):
        annotations = {"seg1.ts": [{"bird_class": "zebra"}, {"bird_class": "apple"}]}
        result = index_db.birds_from_annotations(annotations)
        assert result == ["apple", "zebra"]
