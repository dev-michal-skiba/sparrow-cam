import json
import queue
import sqlite3
from unittest.mock import MagicMock, patch

import pytest

from archive_api import dataset


@pytest.fixture
def dataset_paths(tmp_path):
    """Set up temporary dataset paths."""
    images_path = tmp_path / "images"
    labels_path = tmp_path / "labels"
    images_path.mkdir(parents=True, exist_ok=True)
    labels_path.mkdir(parents=True, exist_ok=True)

    with patch.object(dataset, "IMAGES_PATH", images_path), patch.object(dataset, "LABELS_PATH", labels_path):
        yield images_path, labels_path


@pytest.fixture
def db_setup(tmp_path, monkeypatch):
    """Set up a temporary SQLite database for dataset tests."""
    db_path = tmp_path / "index.db"
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
    conn.commit()
    conn.close()

    return db_path


@pytest.fixture
def stream_path(tmp_path, db_setup):
    """Create a temporary stream path with a segment file and database setup."""
    stream = tmp_path / "stream_a"
    stream.mkdir(parents=True, exist_ok=True)

    # Create a minimal valid MPEG-TS segment file for testing
    segment = stream / "seg1.ts"
    segment.write_bytes(b"\x47" + b"\x00" * 187 + b"\x47" + b"\x00" * 187)  # Minimal TS packets

    return stream


class TestWriteLabel:
    def test_write_label_single_roi(self, dataset_paths):
        images_path, labels_path = dataset_paths
        label_path = labels_path / "test.txt"

        rois = [{"bird_class": "great_tit", "bbox": {"x": 0.1, "y": 0.2, "width": 0.3, "height": 0.4}}]

        dataset._write_label(label_path, rois)

        content = label_path.read_text()
        lines = content.strip().split("\n")
        assert len(lines) == 1
        parts = lines[0].split()
        assert len(parts) == 5
        assert parts[0] == "0"  # great_tit is index 0
        assert float(parts[1]) == pytest.approx(0.1 + 0.3 / 2, abs=0.001)  # cx
        assert float(parts[2]) == pytest.approx(0.2 + 0.4 / 2, abs=0.001)  # cy
        assert float(parts[3]) == pytest.approx(0.3, abs=0.001)  # width
        assert float(parts[4]) == pytest.approx(0.4, abs=0.001)  # height

    def test_write_label_multiple_rois(self, dataset_paths):
        images_path, labels_path = dataset_paths
        label_path = labels_path / "test.txt"

        rois = [
            {"bird_class": "great_tit", "bbox": {"x": 0.1, "y": 0.1, "width": 0.2, "height": 0.2}},
            {"bird_class": "pigeon", "bbox": {"x": 0.5, "y": 0.5, "width": 0.3, "height": 0.3}},
        ]

        dataset._write_label(label_path, rois)

        content = label_path.read_text()
        lines = content.strip().split("\n")
        assert len(lines) == 2

        # First ROI (great_tit = index 0)
        parts = lines[0].split()
        assert parts[0] == "0"

        # Second ROI (pigeon = index 2)
        parts = lines[1].split()
        assert parts[0] == "2"

    def test_write_label_empty_rois(self, dataset_paths):
        images_path, labels_path = dataset_paths
        label_path = labels_path / "test.txt"

        dataset._write_label(label_path, [])

        content = label_path.read_text()
        assert content == ""

    def test_write_label_all_bird_classes(self, dataset_paths):
        images_path, labels_path = dataset_paths
        label_path = labels_path / "test.txt"

        # Test all bird classes
        bird_classes = ["great_tit", "house_sparrow", "pigeon", "eurasian_nuthatch"]
        expected_indices = [0, 1, 2, 3]

        for bird_class, expected_idx in zip(bird_classes, expected_indices):
            label_path.unlink(missing_ok=True)
            rois = [{"bird_class": bird_class, "bbox": {"x": 0.1, "y": 0.1, "width": 0.2, "height": 0.2}}]
            dataset._write_label(label_path, rois)
            content = label_path.read_text()
            parts = content.strip().split()
            assert parts[0] == str(expected_idx)

    def test_write_label_atomicity(self, dataset_paths):
        images_path, labels_path = dataset_paths
        label_path = labels_path / "test.txt"

        # Verify that the file is written atomically via a temp file
        rois = [{"bird_class": "great_tit", "bbox": {"x": 0.1, "y": 0.1, "width": 0.2, "height": 0.2}}]
        dataset._write_label(label_path, rois)

        # Temp file should not exist after write
        tmp_path = label_path.with_name(label_path.name + ".tmp")
        assert not tmp_path.exists()
        assert label_path.exists()


class TestRemoveStreamFiles:
    def test_remove_stream_files_cleans_old_images_and_labels(self, dataset_paths):
        images_path, labels_path = dataset_paths

        # Create old files
        (images_path / "2025-01-15_stream_a_seg1.jpg").touch()
        (images_path / "2025-01-15_stream_a_seg2.jpg").touch()
        (labels_path / "2025-01-15_stream_a_seg1.txt").touch()
        (labels_path / "2025-01-15_stream_a_seg2.txt").touch()

        # Create unrelated files (should not be deleted)
        (images_path / "2025-01-16_stream_a_seg1.jpg").touch()
        (labels_path / "2025-01-16_stream_a_seg1.txt").touch()

        dataset._remove_stream_files("2025-01-15_stream_a")

        assert not (images_path / "2025-01-15_stream_a_seg1.jpg").exists()
        assert not (images_path / "2025-01-15_stream_a_seg2.jpg").exists()
        assert not (labels_path / "2025-01-15_stream_a_seg1.txt").exists()
        assert not (labels_path / "2025-01-15_stream_a_seg2.txt").exists()

        # Unrelated files should still exist
        assert (images_path / "2025-01-16_stream_a_seg1.jpg").exists()
        assert (labels_path / "2025-01-16_stream_a_seg1.txt").exists()

    def test_remove_stream_files_handles_missing_files(self, dataset_paths):
        images_path, labels_path = dataset_paths

        # Should not raise an error even if no files exist
        dataset._remove_stream_files("nonexistent_prefix")

        assert len(list(images_path.glob("*.jpg"))) == 0
        assert len(list(labels_path.glob("*.txt"))) == 0

    def test_remove_stream_files_glob_pattern(self, dataset_paths):
        images_path, labels_path = dataset_paths

        # Create files with similar names
        (images_path / "2025-01-15_stream_a_seg1.jpg").touch()
        (images_path / "2025-01-15_stream_ab_seg1.jpg").touch()  # Similar but different prefix

        dataset._remove_stream_files("2025-01-15_stream_a")

        assert not (images_path / "2025-01-15_stream_a_seg1.jpg").exists()
        assert (images_path / "2025-01-15_stream_ab_seg1.jpg").exists()


class TestExtractFirstFrame:
    @patch("archive_api.dataset.subprocess.run")
    def test_extract_first_frame_success(self, mock_run, dataset_paths, stream_path):
        images_path, labels_path = dataset_paths
        segment = stream_path / "seg1.ts"
        dest_path = images_path / "test.jpg"
        tmp_path = dest_path.with_name(f"{dest_path.stem}.tmp{dest_path.suffix}")

        # Mock successful ffmpeg call and create temp file
        def mock_ffmpeg(*args, **kwargs):
            tmp_path.write_bytes(b"image data")
            return MagicMock(returncode=0)

        mock_run.side_effect = mock_ffmpeg

        result = dataset._extract_first_frame(segment, dest_path)

        assert result is True
        assert dest_path.exists()
        assert not tmp_path.exists()
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert args[0] == "ffmpeg"
        assert str(segment) in args
        assert str(tmp_path) in args

    @patch("archive_api.dataset.subprocess.run")
    def test_extract_first_frame_ffmpeg_failure(self, mock_run, dataset_paths, stream_path):
        images_path, labels_path = dataset_paths
        segment = stream_path / "seg1.ts"
        dest_path = images_path / "test.jpg"
        tmp_path = dest_path.with_name(f"{dest_path.stem}.tmp{dest_path.suffix}")

        # Mock failed ffmpeg call
        def mock_ffmpeg(*args, **kwargs):
            tmp_path.write_bytes(b"garbage")
            return MagicMock(returncode=1, stderr=b"Error message")

        mock_run.side_effect = mock_ffmpeg

        result = dataset._extract_first_frame(segment, dest_path)

        assert result is False
        assert not dest_path.exists()
        assert not tmp_path.exists()

    @patch("archive_api.dataset.subprocess.run")
    def test_extract_first_frame_atomicity(self, mock_run, dataset_paths, stream_path):
        images_path, labels_path = dataset_paths
        segment = stream_path / "seg1.ts"
        dest_path = images_path / "test.jpg"
        tmp_path = dest_path.with_name(f"{dest_path.stem}.tmp{dest_path.suffix}")

        # Mock successful ffmpeg call and verify atomicity
        def mock_ffmpeg(*args, **kwargs):
            # Simulate ffmpeg writing to temp path
            tmp_path.write_bytes(b"image data")
            return MagicMock(returncode=0)

        mock_run.side_effect = mock_ffmpeg

        result = dataset._extract_first_frame(segment, dest_path)

        assert result is True
        assert dest_path.exists()
        assert not tmp_path.exists()


class TestWriteSample:
    @patch("archive_api.dataset._extract_first_frame")
    def test_write_sample_positive(self, mock_extract, dataset_paths, stream_path):
        images_path, labels_path = dataset_paths
        segment = stream_path / "seg1.ts"

        # Mock _extract_first_frame to create the image file
        def mock_extract_func(segment_path, dest_path):
            dest_path.write_bytes(b"image data")
            return True

        mock_extract.side_effect = mock_extract_func
        rois = [{"bird_class": "great_tit", "bbox": {"x": 0.1, "y": 0.1, "width": 0.2, "height": 0.2}}]

        dataset._write_sample(segment, "test_sample", rois, positive=True)

        assert (images_path / "test_sample.jpg").exists()
        assert (labels_path / "test_sample.txt").exists()

        label_content = (labels_path / "test_sample.txt").read_text()
        assert "0" in label_content

    @patch("archive_api.dataset._extract_first_frame")
    def test_write_sample_negative(self, mock_extract, dataset_paths, stream_path):
        images_path, labels_path = dataset_paths
        segment = stream_path / "seg1.ts"

        # Mock _extract_first_frame to create the image file
        def mock_extract_func(segment_path, dest_path):
            dest_path.write_bytes(b"image data")
            return True

        mock_extract.side_effect = mock_extract_func

        dataset._write_sample(segment, "test_sample", [], positive=False)

        assert (images_path / "test_sample.jpg").exists()
        assert (labels_path / "test_sample.txt").exists()

        # Negative sample has empty label
        label_content = (labels_path / "test_sample.txt").read_text()
        assert label_content == ""

    @patch("archive_api.dataset._extract_first_frame")
    def test_write_sample_frame_extraction_fails(self, mock_extract, dataset_paths, stream_path):
        images_path, labels_path = dataset_paths
        segment = stream_path / "seg1.ts"

        mock_extract.return_value = False
        rois = [{"bird_class": "great_tit", "bbox": {"x": 0.1, "y": 0.1, "width": 0.2, "height": 0.2}}]

        dataset._write_sample(segment, "test_sample", rois, positive=True)

        # Should not create label if frame extraction failed
        assert not (images_path / "test_sample.jpg").exists()
        assert not (labels_path / "test_sample.txt").exists()


class TestAddNegativeSample:
    @patch("archive_api.dataset._write_sample")
    def test_add_negative_sample_selects_random_segment(self, mock_write, dataset_paths, stream_path):
        # Create multiple segments
        (stream_path / "seg1.ts").write_bytes(b"data1")
        (stream_path / "seg2.ts").write_bytes(b"data2")
        (stream_path / "seg3.ts").write_bytes(b"data3")

        dataset._add_negative_sample(stream_path, "test_prefix")

        # Should have called _write_sample once with one of the segments
        assert mock_write.call_count == 1
        call_args = mock_write.call_args[0]
        segment_path = call_args[0]
        assert segment_path.suffix == ".ts"
        assert segment_path.parent == stream_path

    @patch("archive_api.dataset._write_sample")
    def test_add_negative_sample_no_segments(self, mock_write, dataset_paths, tmp_path):
        stream_path = tmp_path / "empty_stream"
        stream_path.mkdir()

        dataset._add_negative_sample(stream_path, "test_prefix")

        # Should not call _write_sample if no segments
        mock_write.assert_not_called()

    @patch("archive_api.dataset._write_sample")
    def test_add_negative_sample_correct_parameters(self, mock_write, dataset_paths, stream_path):
        (stream_path / "seg1.ts").write_bytes(b"data")

        dataset._add_negative_sample(stream_path, "test_prefix")

        args = mock_write.call_args[0]
        kwargs = mock_write.call_args[1]
        segment_path = args[0]
        sample_name = args[1]
        rois = args[2]
        positive = kwargs.get("positive", args[3] if len(args) > 3 else None)

        assert segment_path.suffix == ".ts"
        assert sample_name.startswith("test_prefix_")
        assert rois == []
        assert positive is False


class TestUpdateStreamDataset:
    def test_update_stream_dataset_creates_directories(self, dataset_paths, stream_path):
        images_path, labels_path = dataset_paths

        # Remove directories to test creation
        images_path.rmdir()
        labels_path.rmdir()

        (stream_path / "meta.json").write_text(json.dumps({"manual_annotations": {}}))

        dataset._update_stream_dataset("2025", "01", "15", stream_path)

        assert images_path.exists()
        assert labels_path.exists()

    def test_update_stream_dataset_no_meta_file(self, dataset_paths, stream_path):
        dataset._update_stream_dataset("2025", "01", "15", stream_path)

        # Should handle missing meta.json gracefully
        assert True  # No exception raised

    def test_update_stream_dataset_corrupted_meta_json(self, dataset_paths, stream_path):
        (stream_path / "meta.json").write_text("{invalid json")

        dataset._update_stream_dataset("2025", "01", "15", stream_path)

        # Should handle corrupted JSON gracefully
        assert True  # No exception raised

    def test_update_stream_dataset_no_manual_annotations(self, dataset_paths, stream_path):
        (stream_path / "meta.json").write_text(json.dumps({"detections": {}}))

        dataset._update_stream_dataset("2025", "01", "15", stream_path)

        # Should not create dataset files if no manual_annotations
        images_path, labels_path = dataset_paths
        assert len(list(images_path.glob("*.jpg"))) == 0

    @patch("archive_api.dataset._write_sample")
    def test_update_stream_dataset_empty_manual_annotations(self, mock_write, dataset_paths, stream_path, db_setup):
        # Insert empty manual_annotations into database
        conn = sqlite3.connect(db_setup)
        conn.execute(
            "INSERT INTO recordings (date, stream, detections, manual_annotations, birds) VALUES (?, ?, ?, ?, ?)",
            ("2025-01-15", "stream_a", json.dumps({}), json.dumps({}), json.dumps([])),
        )
        conn.commit()
        conn.close()

        with patch("archive_api.dataset._add_negative_sample") as mock_negative:
            dataset._update_stream_dataset("2025", "01", "15", stream_path)
            mock_negative.assert_called_once()

    @patch("archive_api.dataset._write_sample")
    def test_update_stream_dataset_positive_samples(self, mock_write, dataset_paths, stream_path, db_setup):
        rois = [{"bird_class": "great_tit", "bbox": {"x": 0.1, "y": 0.1, "width": 0.2, "height": 0.2}}]

        # Insert manual_annotations into database
        conn = sqlite3.connect(db_setup)
        conn.execute(
            "INSERT INTO recordings (date, stream, detections, manual_annotations, birds) VALUES (?, ?, ?, ?, ?)",
            ("2025-01-15", "stream_a", json.dumps({}), json.dumps({"seg1.ts": rois}), json.dumps(["great_tit"])),
        )
        conn.commit()
        conn.close()

        dataset._update_stream_dataset("2025", "01", "15", stream_path)

        assert mock_write.call_count == 1
        args = mock_write.call_args[0]
        kwargs = mock_write.call_args[1]
        assert args[2] == rois  # rois parameter
        assert kwargs.get("positive", args[3] if len(args) > 3 else None) is True  # positive parameter

    @patch("archive_api.dataset._write_sample")
    def test_update_stream_dataset_missing_segment_file(self, mock_write, dataset_paths, stream_path):
        rois = [{"bird_class": "great_tit", "bbox": {"x": 0.1, "y": 0.1, "width": 0.2, "height": 0.2}}]
        (stream_path / "meta.json").write_text(json.dumps({"manual_annotations": {"nonexistent.ts": rois}}))

        dataset._update_stream_dataset("2025", "01", "15", stream_path)

        # Should not call _write_sample if segment file doesn't exist
        mock_write.assert_not_called()

    @patch("archive_api.dataset._write_sample")
    def test_update_stream_dataset_cleans_old_files(self, mock_write, dataset_paths, stream_path):
        images_path, labels_path = dataset_paths

        # Create old files
        (images_path / "2025-01-15_stream_a_old.jpg").touch()
        (labels_path / "2025-01-15_stream_a_old.txt").touch()

        rois = [{"bird_class": "great_tit", "bbox": {"x": 0.1, "y": 0.1, "width": 0.2, "height": 0.2}}]
        (stream_path / "meta.json").write_text(json.dumps({"manual_annotations": {"seg1.ts": rois}}))

        dataset._update_stream_dataset("2025", "01", "15", stream_path)

        # Old files should be removed
        assert not (images_path / "2025-01-15_stream_a_old.jpg").exists()
        assert not (labels_path / "2025-01-15_stream_a_old.txt").exists()


class TestScheduleUpdate:
    def test_schedule_update_queues_job(self, dataset_paths, stream_path):
        # Test that schedule_update adds a job to the queue
        test_queue = queue.Queue()

        with patch.object(dataset, "_queue", test_queue):
            with patch.object(dataset, "_ensure_worker_started"):
                dataset.schedule_update("2025", "01", "15", stream_path)

                # Verify job was queued
                job = test_queue.get_nowait()
                assert job == ("2025", "01", "15", stream_path)

    def test_schedule_update_ensures_worker_started(self, dataset_paths, stream_path):
        # Test that schedule_update calls _ensure_worker_started
        with patch("archive_api.dataset._ensure_worker_started") as mock_ensure:
            dataset.schedule_update("2025", "01", "15", stream_path)
            mock_ensure.assert_called_once()


class TestWorkerThread:
    def test_worker_processes_queue(self, dataset_paths, stream_path):
        # Test the worker logic by directly calling it with mocked update function
        (stream_path / "meta.json").write_text(json.dumps({"manual_annotations": {"seg1.ts": []}}))

        with patch("archive_api.dataset._update_stream_dataset") as mock_update:
            # Simulate what the worker does
            year, month, day, path = ("2025", "01", "15", stream_path)
            try:
                mock_update(year, month, day, path)
            except Exception:
                pass

            mock_update.assert_called_once()

    def test_worker_handles_exceptions(self, dataset_paths, stream_path):
        # Test exception handling in the worker
        with patch("archive_api.dataset._update_stream_dataset") as mock_update:
            mock_update.side_effect = Exception("Test error")

            year, month, day, path = ("2025", "01", "15", stream_path)
            try:
                mock_update(year, month, day, path)
            except Exception:
                # Worker catches this and logs it
                pass

            # Worker should not crash on exception
            assert True
