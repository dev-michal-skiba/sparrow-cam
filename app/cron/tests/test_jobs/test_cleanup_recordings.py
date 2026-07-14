import argparse
import json
import logging
from datetime import date
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from cron.jobs.cleanup_recordings import (
    KEEP_COUNT,
    MAX_SEGMENTS,
    Recording,
    RecordingsCleaner,
    parse_date_arg,
)


class TestRecording:
    """Test suite for Recording dataclass."""

    def test_recording_creation(self):
        """Test that Recording dataclass can be created with all fields."""
        path = Path("/tmp/recording")
        recording = Recording(
            path=path,
            timestamp="2024-01-01T120000Z",
            segment_count=10,
            is_manually_annotated=False,
        )

        assert recording.path == path
        assert recording.timestamp == "2024-01-01T120000Z"
        assert recording.segment_count == 10
        assert recording.is_manually_annotated is False

    def test_recording_annotated(self):
        """Test Recording with annotation flag set."""
        path = Path("/tmp/recording_annotated")
        recording = Recording(
            path=path,
            timestamp="2024-01-01T120000Z",
            segment_count=5,
            is_manually_annotated=True,
        )

        assert recording.is_manually_annotated is True


class TestParseTimestamp:
    """Test suite for RecordingsCleaner.parse_timestamp method."""

    def test_parse_timestamp_standard_format(self):
        """Test parsing timestamp from standard archive directory name."""
        cleaner = RecordingsCleaner()
        directory_name = "sparrow_2024-01-15T143022Z_abc123"

        timestamp = cleaner.parse_timestamp(directory_name)

        assert timestamp == "2024-01-15T143022Z"

    def test_parse_timestamp_different_prefix(self):
        """Test parsing timestamp with different prefix."""
        cleaner = RecordingsCleaner()
        directory_name = "pigeon_2024-12-31T235959Z_xyz789"

        timestamp = cleaner.parse_timestamp(directory_name)

        assert timestamp == "2024-12-31T235959Z"

    def test_parse_timestamp_handles_single_digit_components(self):
        """Test parsing timestamp correctly extracts middle segment."""
        cleaner = RecordingsCleaner()
        directory_name = "bird_2024-01-01T000000Z_uuid"

        timestamp = cleaner.parse_timestamp(directory_name)

        assert timestamp == "2024-01-01T000000Z"


class TestIsManuallyAnnotated:
    """Test suite for RecordingsCleaner.is_manually_annotated method."""

    def test_is_manually_annotated_true_with_empty_dict(self):
        """Test recording is marked annotated even with empty dict."""
        cleaner = RecordingsCleaner()
        temp_dir = Path("/tmp/test_recording_annotated")
        temp_dir.mkdir(exist_ok=True)
        meta_file = temp_dir / "meta.json"
        meta_file.write_text(json.dumps({"manual_annotations": {}}))

        result = cleaner.is_manually_annotated(temp_dir)

        assert result is True
        meta_file.unlink()
        temp_dir.rmdir()

    def test_is_manually_annotated_true_with_annotations(self):
        """Test recording with actual annotations is marked annotated."""
        cleaner = RecordingsCleaner()
        temp_dir = Path("/tmp/test_recording_with_data")
        temp_dir.mkdir(exist_ok=True)
        meta_file = temp_dir / "meta.json"
        meta_file.write_text(json.dumps({"manual_annotations": {"0": {"type": "bird"}}}))

        result = cleaner.is_manually_annotated(temp_dir)

        assert result is True
        meta_file.unlink()
        temp_dir.rmdir()

    def test_is_manually_annotated_false_no_meta(self):
        """Test recording without meta.json is not marked annotated."""
        cleaner = RecordingsCleaner()
        temp_dir = Path("/tmp/test_recording_no_meta")
        temp_dir.mkdir(exist_ok=True)

        result = cleaner.is_manually_annotated(temp_dir)

        assert result is False
        temp_dir.rmdir()

    def test_is_manually_annotated_false_no_key(self):
        """Test recording without manual_annotations key is not marked annotated."""
        cleaner = RecordingsCleaner()
        temp_dir = Path("/tmp/test_recording_no_key")
        temp_dir.mkdir(exist_ok=True)
        meta_file = temp_dir / "meta.json"
        meta_file.write_text(json.dumps({"other_field": "value"}))

        result = cleaner.is_manually_annotated(temp_dir)

        assert result is False
        meta_file.unlink()
        temp_dir.rmdir()

    def test_is_manually_annotated_false_invalid_json(self):
        """Test recording with invalid JSON returns False."""
        cleaner = RecordingsCleaner()
        temp_dir = Path("/tmp/test_recording_invalid_json")
        temp_dir.mkdir(exist_ok=True)
        meta_file = temp_dir / "meta.json"
        meta_file.write_text("invalid json {]")

        result = cleaner.is_manually_annotated(temp_dir)

        assert result is False
        meta_file.unlink()
        temp_dir.rmdir()


class TestGroupByTimestamp:
    """Test suite for RecordingsCleaner.group_by_timestamp method."""

    def test_group_by_timestamp_empty_list(self):
        """Test grouping empty list returns empty list."""
        cleaner = RecordingsCleaner()
        candidates = []

        groups = cleaner.group_by_timestamp(candidates, 5)

        assert groups == []

    def test_group_by_timestamp_zero_groups(self):
        """Test grouping with zero target groups returns empty list."""
        cleaner = RecordingsCleaner()
        recordings = [
            Recording(Path("/tmp/1"), "2024-01-01T000000Z", 5, False),
            Recording(Path("/tmp/2"), "2024-01-01T010000Z", 5, False),
        ]

        groups = cleaner.group_by_timestamp(recordings, 0)

        assert groups == []

    def test_group_by_timestamp_single_group(self):
        """Test grouping into single group returns all recordings."""
        cleaner = RecordingsCleaner()
        recordings = [
            Recording(Path("/tmp/1"), "2024-01-01T000000Z", 5, False),
            Recording(Path("/tmp/2"), "2024-01-01T120000Z", 5, False),
            Recording(Path("/tmp/3"), "2024-01-01T230000Z", 5, False),
        ]

        groups = cleaner.group_by_timestamp(recordings, 1)

        assert len(groups) == 1
        assert groups[0] == recordings

    def test_group_by_timestamp_equal_division(self):
        """Test grouping evenly divides recordings."""
        cleaner = RecordingsCleaner()
        recordings = [Recording(Path(f"/tmp/{i}"), f"2024-01-01T{i:02d}0000Z", 5, False) for i in range(4)]

        groups = cleaner.group_by_timestamp(recordings, 2)

        assert len(groups) == 2
        assert len(groups[0]) == 2
        assert len(groups[1]) == 2

    def test_group_by_timestamp_unequal_division(self):
        """Test grouping with unequal division distributes remainder."""
        cleaner = RecordingsCleaner()
        recordings = [Recording(Path(f"/tmp/{i}"), f"2024-01-01T{i:02d}0000Z", 5, False) for i in range(5)]

        groups = cleaner.group_by_timestamp(recordings, 2)

        assert len(groups) == 2
        assert len(groups[0]) == 3
        assert len(groups[1]) == 2

    def test_group_by_timestamp_many_groups(self):
        """Test grouping with more groups than recordings."""
        cleaner = RecordingsCleaner()
        recordings = [
            Recording(Path("/tmp/1"), "2024-01-01T000000Z", 5, False),
            Recording(Path("/tmp/2"), "2024-01-01T010000Z", 5, False),
        ]

        groups = cleaner.group_by_timestamp(recordings, 10)

        # Should create as many groups as recordings, skipping empty ones
        assert len(groups) == 2
        assert groups[0] == [recordings[0]]
        assert groups[1] == [recordings[1]]

    def test_group_by_timestamp_ordering(self):
        """Test groups are ordered by timestamp."""
        cleaner = RecordingsCleaner()
        recordings = [
            Recording(Path("/tmp/3"), "2024-01-01T200000Z", 5, False),
            Recording(Path("/tmp/1"), "2024-01-01T000000Z", 5, False),
            Recording(Path("/tmp/2"), "2024-01-01T100000Z", 5, False),
        ]

        groups = cleaner.group_by_timestamp(recordings, 3)

        # Verify recordings are sorted by timestamp across groups
        all_sorted = [r for group in groups for r in group]
        assert all_sorted[0].timestamp == "2024-01-01T000000Z"
        assert all_sorted[1].timestamp == "2024-01-01T100000Z"
        assert all_sorted[2].timestamp == "2024-01-01T200000Z"


class TestLoadRecording:
    """Test suite for RecordingsCleaner.load_recording method."""

    def test_load_recording_basic(self):
        """Test loading recording info from path."""
        cleaner = RecordingsCleaner()
        temp_dir = Path("/tmp/sparrow_2024-01-15T143022Z_uuid")
        temp_dir.mkdir(exist_ok=True)

        # Create some segment files
        (temp_dir / "segment1.ts").touch()
        (temp_dir / "segment2.ts").touch()

        recording = cleaner.load_recording(temp_dir)

        assert recording.path == temp_dir
        assert recording.timestamp == "2024-01-15T143022Z"
        assert recording.segment_count == 2
        assert recording.is_manually_annotated is False

        # Cleanup
        (temp_dir / "segment1.ts").unlink()
        (temp_dir / "segment2.ts").unlink()
        temp_dir.rmdir()

    def test_load_recording_with_annotation(self):
        """Test loading recording that is manually annotated."""
        cleaner = RecordingsCleaner()
        temp_dir = Path("/tmp/sparrow_2024-01-15T143022Z_abc123")
        temp_dir.mkdir(exist_ok=True)

        # Create meta file with manual annotations
        meta_file = temp_dir / "meta.json"
        meta_file.write_text(json.dumps({"manual_annotations": {}}))

        # Create segments
        (temp_dir / "segment1.ts").touch()

        recording = cleaner.load_recording(temp_dir)

        assert recording.is_manually_annotated is True
        assert recording.segment_count == 1

        # Cleanup
        meta_file.unlink()
        (temp_dir / "segment1.ts").unlink()
        temp_dir.rmdir()

    def test_load_recording_no_segments(self):
        """Test loading recording with no segments."""
        cleaner = RecordingsCleaner()
        temp_dir = Path("/tmp/sparrow_2024-01-15T143022Z_xyz789")
        temp_dir.mkdir(exist_ok=True)

        recording = cleaner.load_recording(temp_dir)

        assert recording.segment_count == 0

        temp_dir.rmdir()


class TestRemoveRecording:
    """Test suite for RecordingsCleaner.remove_recording method."""

    def test_remove_recording_deletes_directory(self):
        """Test remove_recording deletes the recording directory."""
        cleaner = RecordingsCleaner()
        temp_dir = Path("/tmp/test_remove_2024-01-15T143022Z_uuid")
        temp_dir.mkdir(exist_ok=True)
        (temp_dir / "segment.ts").touch()

        recording = Recording(temp_dir, "2024-01-15T143022Z", 1, False)

        cleaner.remove_recording(recording)

        assert not temp_dir.exists()

    def test_remove_recording_logs_info(self, caplog):
        """Test remove_recording logs the removal."""
        cleaner = RecordingsCleaner()
        temp_dir = Path("/tmp/test_remove_log_2024-01-15T143022Z_uuid")
        temp_dir.mkdir(exist_ok=True)

        recording = Recording(temp_dir, "2024-01-15T143022Z", 5, False)

        with caplog.at_level(logging.INFO):
            cleaner.remove_recording(recording)

        assert "Removing recording" in caplog.text
        assert "5 segments" in caplog.text


class TestCleanupDay:
    """Test suite for RecordingsCleaner.cleanup_day method."""

    @patch("cron.jobs.cleanup_recordings.ARCHIVE_PATH", Path("/tmp/archive"))
    def test_cleanup_day_no_archive_directory(self, caplog):
        """Test cleanup_day when archive directory doesn't exist."""
        cleaner = RecordingsCleaner()
        test_day = date(2024, 1, 15)

        with caplog.at_level(logging.INFO):
            cleaner.cleanup_day(test_day)

        assert "No archive directory" in caplog.text
        assert "2024-01-15" in caplog.text

    @patch("cron.jobs.cleanup_recordings.ARCHIVE_PATH", Path("/tmp/archive"))
    @patch.object(RecordingsCleaner, "load_recording")
    @patch.object(RecordingsCleaner, "remove_recording")
    def test_cleanup_day_removes_oversized_recordings(self, mock_remove, mock_load, caplog):
        """Test cleanup_day removes recordings exceeding MAX_SEGMENTS."""
        cleaner = RecordingsCleaner()
        archive_path = Path("/tmp/archive/2024/01/15")
        archive_path.mkdir(parents=True, exist_ok=True)

        recording1 = Mock()
        recording1.path = archive_path / "rec1"
        recording1.segment_count = MAX_SEGMENTS + 1
        recording1.is_manually_annotated = False
        recording1.timestamp = "2024-01-15T000000Z"

        recording2 = Mock()
        recording2.path = archive_path / "rec2"
        recording2.segment_count = 10
        recording2.is_manually_annotated = False
        recording2.timestamp = "2024-01-15T120000Z"

        (recording1.path).mkdir(exist_ok=True)
        (recording2.path).mkdir(exist_ok=True)

        mock_load.side_effect = [recording1, recording2]

        with caplog.at_level(logging.INFO):
            cleaner.cleanup_day(date(2024, 1, 15))

        mock_remove.assert_called_once_with(recording1)

        # Cleanup
        import shutil

        shutil.rmtree(archive_path.parent.parent.parent)

    def test_cleanup_day_with_actual_files(self):
        """Test cleanup_day with actual archive structure."""
        import shutil

        cleaner = RecordingsCleaner()
        archive_path = Path("/tmp/test_archive/2024/01/15")
        archive_path.mkdir(parents=True, exist_ok=True)

        # Create 15 recordings (more than KEEP_COUNT)
        for i in range(15):
            rec_dir = archive_path / f"sparrow_2024-01-15T{i:02d}0000Z_uuid{i}"
            rec_dir.mkdir()
            # Add segments
            for j in range(5):
                (rec_dir / f"segment{j}.ts").touch()

        # Run cleanup
        with patch("cron.jobs.cleanup_recordings.ARCHIVE_PATH", archive_path.parent.parent.parent):
            cleaner.cleanup_day(date(2024, 1, 15))

        # Verify we kept approximately KEEP_COUNT recordings
        remaining_dirs = list(archive_path.glob("sparrow_*"))
        assert len(remaining_dirs) == KEEP_COUNT

        # Cleanup
        shutil.rmtree(archive_path.parent.parent.parent)

    def test_cleanup_day_preserves_annotated_recordings(self):
        """Test cleanup_day never removes manually annotated recordings."""
        import shutil

        cleaner = RecordingsCleaner()
        archive_path = Path("/tmp/test_archive_annotated/2024/01/15")
        archive_path.mkdir(parents=True, exist_ok=True)

        # Create one annotated recording with oversized segments (would normally be removed)
        annotated_dir = archive_path / "sparrow_2024-01-15T000000Z_annotated"
        annotated_dir.mkdir()
        meta_file = annotated_dir / "meta.json"
        meta_file.write_text(json.dumps({"manual_annotations": {"0": "bird"}}))
        # Create more than MAX_SEGMENTS files (would be oversized)
        for i in range(MAX_SEGMENTS + 5):
            (annotated_dir / f"segment{i}.ts").touch()

        # Create more unannotated recordings to trigger pruning
        for i in range(15):
            rec_dir = archive_path / f"sparrow_2024-01-15T{i+1:02d}0000Z_uuid{i}"
            rec_dir.mkdir()
            for j in range(5):
                (rec_dir / f"segment{j}.ts").touch()

        # Run cleanup
        with patch("cron.jobs.cleanup_recordings.ARCHIVE_PATH", archive_path.parent.parent.parent):
            cleaner.cleanup_day(date(2024, 1, 15))

        # Verify annotated recording was preserved (even with oversized segments)
        assert annotated_dir.exists()

        # Cleanup
        shutil.rmtree(archive_path.parent.parent.parent)

    def test_cleanup_day_reduces_keep_budget_by_annotated_count(self):
        """Test cleanup_day reduces keep budget by annotated recording count."""
        import shutil

        cleaner = RecordingsCleaner()
        archive_path = Path("/tmp/test_archive_budget/2024/01/15")
        archive_path.mkdir(parents=True, exist_ok=True)

        # Create 3 annotated recordings
        for i in range(3):
            annotated_dir = archive_path / f"sparrow_2024-01-15T{i:02d}0000Z_annotated{i}"
            annotated_dir.mkdir()
            meta_file = annotated_dir / "meta.json"
            meta_file.write_text(json.dumps({"manual_annotations": {}}))
            for j in range(5):
                (annotated_dir / f"segment{j}.ts").touch()

        # Create 20 unannotated recordings
        for i in range(20):
            rec_dir = archive_path / f"sparrow_2024-01-15T{i+3:02d}0000Z_uuid{i}"
            rec_dir.mkdir()
            for j in range(5):
                (rec_dir / f"segment{j}.ts").touch()

        # Run cleanup
        with patch("cron.jobs.cleanup_recordings.ARCHIVE_PATH", archive_path.parent.parent.parent):
            cleaner.cleanup_day(date(2024, 1, 15))

        # Verify all annotated recordings were preserved
        annotated_count = len(list(archive_path.glob("sparrow_*annotated*")))
        assert annotated_count == 3

        # Verify keep budget was reduced: should keep (KEEP_COUNT - 3) unannotated + 3 annotated
        # Total should be KEEP_COUNT
        total_remaining = len(list(archive_path.glob("sparrow_*")))
        assert total_remaining == KEEP_COUNT

        # Cleanup
        shutil.rmtree(archive_path.parent.parent.parent)


class TestParseDateArg:
    """Test suite for parse_date_arg function."""

    def test_parse_date_arg_valid_format(self):
        """Test parsing valid YYYY-MM-DD format."""
        result = parse_date_arg("2024-01-15")

        assert result == date(2024, 1, 15)

    def test_parse_date_arg_different_date(self):
        """Test parsing different valid date."""
        result = parse_date_arg("2024-12-31")

        assert result == date(2024, 12, 31)

    def test_parse_date_arg_invalid_format(self):
        """Test parsing invalid format raises ArgumentTypeError."""
        with pytest.raises(argparse.ArgumentTypeError) as excinfo:
            parse_date_arg("2024/01/15")

        assert "Invalid date" in str(excinfo.value)
        assert "YYYY-MM-DD" in str(excinfo.value)

    def test_parse_date_arg_invalid_date(self):
        """Test parsing invalid date (like Feb 30) raises ArgumentTypeError."""
        with pytest.raises(argparse.ArgumentTypeError):
            parse_date_arg("2024-02-30")

    def test_parse_date_arg_missing_parts(self):
        """Test parsing incomplete date string raises ArgumentTypeError."""
        with pytest.raises(argparse.ArgumentTypeError):
            parse_date_arg("2024-01")


class TestMain:
    """Test suite for main CLI function."""

    @patch("cron.jobs.cleanup_recordings.RecordingsCleaner.cleanup_day")
    @patch("sys.argv", ["cleanup_recordings.py"])
    def test_main_default_today(self, mock_cleanup):
        """Test main uses today's date when no args provided."""
        from cron.jobs.cleanup_recordings import main

        main()

        # Should cleanup today's date
        assert len(mock_cleanup.call_args_list) == 1
        assert mock_cleanup.call_args_list[0][0][0] == date.today()

    @patch("cron.jobs.cleanup_recordings.RecordingsCleaner.cleanup_day")
    @patch("sys.argv", ["cleanup_recordings.py", "--from-date", "2024-01-15"])
    def test_main_with_from_date(self, mock_cleanup):
        """Test main with --from-date argument."""
        from cron.jobs.cleanup_recordings import main

        main()

        assert len(mock_cleanup.call_args_list) == 1
        assert mock_cleanup.call_args_list[0][0][0] == date(2024, 1, 15)

    @patch("cron.jobs.cleanup_recordings.RecordingsCleaner.cleanup_day")
    @patch("sys.argv", ["cleanup_recordings.py", "--from-date", "2024-01-15", "--to-date", "2024-01-17"])
    def test_main_with_date_range(self, mock_cleanup):
        """Test main with date range."""
        from cron.jobs.cleanup_recordings import main

        main()

        assert len(mock_cleanup.call_args_list) == 3
        assert mock_cleanup.call_args_list[0][0][0] == date(2024, 1, 15)
        assert mock_cleanup.call_args_list[1][0][0] == date(2024, 1, 16)
        assert mock_cleanup.call_args_list[2][0][0] == date(2024, 1, 17)

    @patch("cron.jobs.cleanup_recordings.RecordingsCleaner.cleanup_day")
    @patch("sys.argv", ["cleanup_recordings.py", "--from-date", "2024-01-15", "--to-date", "2024-01-15"])
    def test_main_single_day_range(self, mock_cleanup):
        """Test main with single day (from-date == to-date)."""
        from cron.jobs.cleanup_recordings import main

        main()

        assert len(mock_cleanup.call_args_list) == 1
        assert mock_cleanup.call_args_list[0][0][0] == date(2024, 1, 15)

    @patch("sys.argv", ["cleanup_recordings.py", "--from-date", "invalid"])
    def test_main_invalid_date_format(self):
        """Test main exits with error on invalid date format."""
        from cron.jobs.cleanup_recordings import main

        with pytest.raises(SystemExit):
            main()
