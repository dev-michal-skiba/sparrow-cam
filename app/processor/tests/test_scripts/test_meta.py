import argparse
import json

import pytest

from processor.scripts import meta


@pytest.fixture
def archive_path(tmp_path, monkeypatch):
    """Point the meta script at an isolated, temporary archive path."""
    path = tmp_path / "archive"
    path.mkdir()
    monkeypatch.setattr(meta, "ARCHIVE_PATH", path)
    return path


@pytest.fixture
def sample_meta_file(archive_path):
    """Create a sample meta.json file with detections."""
    stream_dir = archive_path / "2024-01-15_10-30-45"
    stream_dir.mkdir(parents=True)

    meta_data = {
        "version": 1,
        "detections": {
            "segment-001.ts": [
                {"class": "Great Tit", "confidence": 0.95, "roi": {"x1": 10, "y1": 20, "x2": 100, "y2": 200}},
            ],
            "segment-002.ts": [
                {"class": "Pigeon", "confidence": 0.87, "roi": {"x1": 50, "y1": 60, "x2": 150, "y2": 260}},
            ],
        },
    }

    meta_path = stream_dir / "meta.json"
    with open(meta_path, "w") as f:
        json.dump(meta_data, f)

    return meta_path


@pytest.fixture
def multiple_meta_files(archive_path):
    """Create multiple meta.json files with detections for testing."""
    files = []

    # First archive
    stream_dir1 = archive_path / "2024-01-15_10-30-45"
    stream_dir1.mkdir(parents=True)
    meta_data1 = {
        "version": 1,
        "detections": {
            "segment-001.ts": [
                {"class": "Great Tit", "confidence": 0.95, "roi": {"x1": 10, "y1": 20, "x2": 100, "y2": 200}},
            ],
        },
    }
    meta_path1 = stream_dir1 / "meta.json"
    with open(meta_path1, "w") as f:
        json.dump(meta_data1, f)
    files.append(meta_path1)

    # Second archive
    stream_dir2 = archive_path / "2024-01-15_11-45-30"
    stream_dir2.mkdir(parents=True)
    meta_data2 = {
        "version": 1,
        "detections": {
            "segment-001.ts": [
                {"class": "Pigeon", "confidence": 0.87, "roi": {"x1": 50, "y1": 60, "x2": 150, "y2": 260}},
                {"class": "Great Tit", "confidence": 0.92, "roi": {"x1": 20, "y1": 30, "x2": 120, "y2": 210}},
            ],
        },
    }
    meta_path2 = stream_dir2 / "meta.json"
    with open(meta_path2, "w") as f:
        json.dump(meta_data2, f)
    files.append(meta_path2)

    return files


class TestGetStreamUrl:
    def test_get_stream_url(self, sample_meta_file):
        url = meta.get_stream_url(sample_meta_file)
        assert url == "http://rpi.local/archive/2024-01-15_10-30-45"

    def test_get_stream_url_nested(self, archive_path):
        nested_dir = archive_path / "year" / "month" / "day"
        nested_dir.mkdir(parents=True)
        meta_path = nested_dir / "meta.json"
        meta_path.touch()

        url = meta.get_stream_url(meta_path)
        assert url == "http://rpi.local/archive/year/month/day"


class TestFindMetaFiles:
    def test_find_meta_files_single(self, sample_meta_file):
        files = meta.find_meta_files()
        assert len(files) == 1
        assert files[0] == sample_meta_file

    def test_find_meta_files_multiple(self, multiple_meta_files):
        files = meta.find_meta_files()
        assert len(files) == 2
        assert all(f in files for f in multiple_meta_files)

    def test_find_meta_files_empty(self, archive_path):
        files = meta.find_meta_files()
        assert len(files) == 0

    def test_find_meta_files_sorted(self, archive_path):
        # Create files with different timestamps
        dir1 = archive_path / "2024-01-15_09-00-00"
        dir1.mkdir()
        (dir1 / "meta.json").write_text("{}")

        dir2 = archive_path / "2024-01-15_10-00-00"
        dir2.mkdir()
        (dir2 / "meta.json").write_text("{}")

        dir3 = archive_path / "2024-01-15_08-00-00"
        dir3.mkdir()
        (dir3 / "meta.json").write_text("{}")

        files = meta.find_meta_files()
        assert len(files) == 3
        # Files should be sorted
        assert files[0].parent.name == "2024-01-15_08-00-00"
        assert files[1].parent.name == "2024-01-15_09-00-00"
        assert files[2].parent.name == "2024-01-15_10-00-00"


class TestGetMaxConfidencePerClass:
    def test_get_max_confidence_per_class(self, sample_meta_file):
        result = meta.get_max_confidence_per_class(sample_meta_file)
        assert result == {
            "Great Tit": 0.95,
            "Pigeon": 0.87,
        }

    def test_get_max_confidence_per_class_multiple_detections_same_class(self, archive_path):
        stream_dir = archive_path / "test_stream"
        stream_dir.mkdir(parents=True)

        meta_data = {
            "version": 1,
            "detections": {
                "segment-001.ts": [
                    {"class": "Great Tit", "confidence": 0.85, "roi": {}},
                ],
                "segment-002.ts": [
                    {"class": "Great Tit", "confidence": 0.92, "roi": {}},
                ],
                "segment-003.ts": [
                    {"class": "Great Tit", "confidence": 0.88, "roi": {}},
                ],
            },
        }

        meta_path = stream_dir / "meta.json"
        with open(meta_path, "w") as f:
            json.dump(meta_data, f)

        result = meta.get_max_confidence_per_class(meta_path)
        assert result == {"Great Tit": 0.92}

    def test_get_max_confidence_per_class_no_detections(self, archive_path):
        stream_dir = archive_path / "empty_stream"
        stream_dir.mkdir(parents=True)

        meta_data = {
            "version": 1,
            "detections": {},
        }

        meta_path = stream_dir / "meta.json"
        with open(meta_path, "w") as f:
            json.dump(meta_data, f)

        result = meta.get_max_confidence_per_class(meta_path)
        assert result == {}

    def test_get_max_confidence_per_class_missing_detections_key(self, archive_path):
        stream_dir = archive_path / "no_key_stream"
        stream_dir.mkdir(parents=True)

        meta_data = {
            "version": 1,
        }

        meta_path = stream_dir / "meta.json"
        with open(meta_path, "w") as f:
            json.dump(meta_data, f)

        result = meta.get_max_confidence_per_class(meta_path)
        assert result == {}


class TestCmdSummarize:
    def test_cmd_summarize(self, multiple_meta_files, capsys):
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

    def test_cmd_summarize_with_examples_limit(self, archive_path, capsys):
        # Create multiple meta files with same class and percentage
        for i in range(3):
            stream_dir = archive_path / f"stream_{i}"
            stream_dir.mkdir(parents=True)
            meta_data = {
                "version": 1,
                "detections": {
                    "segment-001.ts": [
                        {"class": "Great Tit", "confidence": 0.85, "roi": {}},
                    ],
                },
            }
            meta_path = stream_dir / "meta.json"
            with open(meta_path, "w") as f:
                json.dump(meta_data, f)

        args = argparse.Namespace(examples=2, bird_class=None)
        meta.cmd_summarize(args)

        captured = capsys.readouterr()
        output = captured.out

        # Should show class and percentage
        assert "# Great Tit" in output
        assert "85%" in output

    def test_cmd_summarize_empty_archive(self, archive_path, capsys):
        args = argparse.Namespace(examples=5, bird_class=None)
        meta.cmd_summarize(args)

        captured = capsys.readouterr()
        assert captured.out == ""

    def test_cmd_summarize_filter_by_class(self, multiple_meta_files, capsys):
        args = argparse.Namespace(examples=5, bird_class="Pigeon")
        meta.cmd_summarize(args)

        captured = capsys.readouterr()
        output = captured.out

        assert "# Pigeon" in output
        assert "# Great Tit" not in output

    def test_cmd_summarize_filter_by_class_no_match(self, multiple_meta_files, capsys):
        args = argparse.Namespace(examples=5, bird_class="NonExistent")
        meta.cmd_summarize(args)

        captured = capsys.readouterr()
        assert captured.out == ""

    def test_cmd_summarize_skip_empty_detections(self, archive_path, capsys):
        # Create archive with no detections
        stream_dir = archive_path / "empty_stream"
        stream_dir.mkdir(parents=True)
        meta_data = {
            "version": 1,
            "detections": {},
        }
        meta_path = stream_dir / "meta.json"
        with open(meta_path, "w") as f:
            json.dump(meta_data, f)

        args = argparse.Namespace(examples=5, bird_class=None)
        meta.cmd_summarize(args)

        captured = capsys.readouterr()
        assert captured.out == ""


class TestCmdDelete:
    def test_cmd_delete_below_threshold(self, sample_meta_file, capsys):
        args = argparse.Namespace(bird_class="Pigeon", threshold=90, dry_run=False)
        meta.cmd_delete(args)

        captured = capsys.readouterr()
        assert "Removed detections from:" in captured.out

        # Check that the file was updated
        with open(sample_meta_file) as f:
            updated_data = json.load(f)

        # Pigeon at 87% confidence should be removed (below 90 threshold)
        assert "segment-002.ts" not in updated_data["detections"]
        # Great Tit at 95% should remain
        assert "segment-001.ts" in updated_data["detections"]

    def test_cmd_delete_exact_threshold(self, archive_path, capsys):
        stream_dir = archive_path / "test_stream"
        stream_dir.mkdir(parents=True)

        meta_data = {
            "version": 1,
            "detections": {
                "segment-001.ts": [
                    {"class": "Great Tit", "confidence": 0.90, "roi": {}},
                ],
            },
        }

        meta_path = stream_dir / "meta.json"
        with open(meta_path, "w") as f:
            json.dump(meta_data, f)

        args = argparse.Namespace(bird_class="Great Tit", threshold=90, dry_run=False)
        meta.cmd_delete(args)

        # At exactly threshold, detection should be kept
        with open(meta_path) as f:
            updated_data = json.load(f)

        assert "segment-001.ts" in updated_data["detections"]

    def test_cmd_delete_remove_entire_stream(self, sample_meta_file, capsys):
        stream_dir = sample_meta_file.parent

        # Update to have only one detection that will be removed
        meta_data = {
            "version": 1,
            "detections": {
                "segment-001.ts": [
                    {"class": "Pigeon", "confidence": 0.85, "roi": {}},
                ],
            },
        }

        with open(sample_meta_file, "w") as f:
            json.dump(meta_data, f)

        args = argparse.Namespace(bird_class="Pigeon", threshold=90, dry_run=False)
        meta.cmd_delete(args)

        captured = capsys.readouterr()
        assert "Removed stream:" in captured.out

        # Stream directory should be deleted
        assert not stream_dir.exists()

    def test_cmd_delete_dry_run(self, sample_meta_file, capsys):
        # Store original content
        with open(sample_meta_file) as f:
            original_data = json.load(f)

        args = argparse.Namespace(bird_class="Pigeon", threshold=90, dry_run=True)
        meta.cmd_delete(args)

        captured = capsys.readouterr()
        assert "Removed detections from:" in captured.out

        # File should NOT be modified in dry-run
        with open(sample_meta_file) as f:
            current_data = json.load(f)

        assert current_data == original_data

    def test_cmd_delete_multiple_detections_per_segment(self, archive_path, capsys):
        stream_dir = archive_path / "test_stream"
        stream_dir.mkdir(parents=True)

        meta_data = {
            "version": 1,
            "detections": {
                "segment-001.ts": [
                    {"class": "Great Tit", "confidence": 0.95, "roi": {}},
                    {"class": "Pigeon", "confidence": 0.85, "roi": {}},
                ],
            },
        }

        meta_path = stream_dir / "meta.json"
        with open(meta_path, "w") as f:
            json.dump(meta_data, f)

        # Remove Pigeon detections with 90% threshold
        args = argparse.Namespace(bird_class="Pigeon", threshold=90, dry_run=False)
        meta.cmd_delete(args)

        with open(meta_path) as f:
            updated_data = json.load(f)

        # Segment should still exist with only Great Tit detection
        assert "segment-001.ts" in updated_data["detections"]
        assert len(updated_data["detections"]["segment-001.ts"]) == 1
        assert updated_data["detections"]["segment-001.ts"][0]["class"] == "Great Tit"

    def test_cmd_delete_no_detections_modified(self, multiple_meta_files, capsys):
        args = argparse.Namespace(bird_class="NonExistent", threshold=50, dry_run=False)
        meta.cmd_delete(args)

        captured = capsys.readouterr()
        # Should not print anything if no files were modified
        assert captured.out == ""

    def test_cmd_delete_multiple_segments_partial_removal(self, archive_path, capsys):
        stream_dir = archive_path / "test_stream"
        stream_dir.mkdir(parents=True)

        meta_data = {
            "version": 1,
            "detections": {
                "segment-001.ts": [
                    {"class": "Great Tit", "confidence": 0.95, "roi": {}},
                ],
                "segment-002.ts": [
                    {"class": "Pigeon", "confidence": 0.85, "roi": {}},
                ],
                "segment-003.ts": [
                    {"class": "Pigeon", "confidence": 0.92, "roi": {}},
                ],
            },
        }

        meta_path = stream_dir / "meta.json"
        with open(meta_path, "w") as f:
            json.dump(meta_data, f)

        # Remove Pigeon detections below 90%
        args = argparse.Namespace(bird_class="Pigeon", threshold=90, dry_run=False)
        meta.cmd_delete(args)

        captured = capsys.readouterr()
        assert "Removed detections from:" in captured.out

        with open(meta_path) as f:
            updated_data = json.load(f)

        # segment-001 and segment-003 should remain
        assert "segment-001.ts" in updated_data["detections"]
        assert "segment-002.ts" not in updated_data["detections"]
        assert "segment-003.ts" in updated_data["detections"]


class TestMain:
    def test_main_requires_command(self):
        # Should fail when no command provided
        with pytest.raises(SystemExit):
            meta.main()
