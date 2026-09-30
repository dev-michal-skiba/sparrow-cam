import argparse
import json
import logging
from datetime import date
from pathlib import Path
from unittest.mock import Mock, call, patch

import pytest

from cron.jobs.cleanup_recordings import (
    FREE_SPACE_THRESHOLD_BYTES,
    KEEP_COUNT,
    MAX_SEGMENTS,
    CleanedDaysStore,
    Recording,
    RecordingsCleaner,
    find_earliest_archive_day,
    find_oldest_uncleaned_day,
    get_free_space_bytes,
    parse_date_arg,
    run_space_pressure_sweep,
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

    @patch("cron.jobs.cleanup_recordings.index_db.is_manually_annotated")
    @patch("cron.jobs.cleanup_recordings.ARCHIVE_PATH", Path("/archive"))
    def test_is_manually_annotated_true(self, mock_db_is_annotated):
        """Test recording is marked annotated when database indicates so."""
        mock_db_is_annotated.return_value = True
        cleaner = RecordingsCleaner()
        recording_path = Path("/archive/2024/01/15/sparrow_stream")

        result = cleaner.is_manually_annotated(recording_path)

        assert result is True
        mock_db_is_annotated.assert_called_once_with("2024-01-15", "sparrow_stream")

    @patch("cron.jobs.cleanup_recordings.index_db.is_manually_annotated")
    @patch("cron.jobs.cleanup_recordings.ARCHIVE_PATH", Path("/archive"))
    def test_is_manually_annotated_false(self, mock_db_is_annotated):
        """Test recording is not marked annotated when database indicates so."""
        mock_db_is_annotated.return_value = False
        cleaner = RecordingsCleaner()
        recording_path = Path("/archive/2024/01/15/sparrow_stream")

        result = cleaner.is_manually_annotated(recording_path)

        assert result is False
        mock_db_is_annotated.assert_called_once_with("2024-01-15", "sparrow_stream")


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

    @patch("cron.jobs.cleanup_recordings.index_db.is_manually_annotated")
    def test_load_recording_basic(self, mock_db_is_annotated, tmp_path, monkeypatch):
        """Test loading recording info from path."""
        archive_path = tmp_path / "archive"
        temp_dir = archive_path / "2024" / "01" / "15" / "sparrow_2024-01-15T143022Z_uuid"
        temp_dir.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr("cron.jobs.cleanup_recordings.ARCHIVE_PATH", archive_path)

        mock_db_is_annotated.return_value = False
        cleaner = RecordingsCleaner()

        # Create some segment files
        (temp_dir / "segment1.ts").touch()
        (temp_dir / "segment2.ts").touch()

        recording = cleaner.load_recording(temp_dir)

        assert recording.path == temp_dir
        assert recording.timestamp == "2024-01-15T143022Z"
        assert recording.segment_count == 2
        assert recording.is_manually_annotated is False

    @patch("cron.jobs.cleanup_recordings.index_db.is_manually_annotated")
    def test_load_recording_with_annotation(self, mock_db_is_annotated, tmp_path, monkeypatch):
        """Test loading recording that is manually annotated."""
        archive_path = tmp_path / "archive"
        temp_dir = archive_path / "2024" / "01" / "15" / "sparrow_2024-01-15T143022Z_abc123"
        temp_dir.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr("cron.jobs.cleanup_recordings.ARCHIVE_PATH", archive_path)

        mock_db_is_annotated.return_value = True
        cleaner = RecordingsCleaner()

        # Create segments
        (temp_dir / "segment1.ts").touch()

        recording = cleaner.load_recording(temp_dir)

        assert recording.is_manually_annotated is True
        assert recording.segment_count == 1

    @patch("cron.jobs.cleanup_recordings.index_db.is_manually_annotated")
    def test_load_recording_no_segments(self, mock_db_is_annotated, tmp_path, monkeypatch):
        """Test loading recording with no segments."""
        archive_path = tmp_path / "archive"
        temp_dir = archive_path / "2024" / "01" / "15" / "sparrow_2024-01-15T143022Z_xyz789"
        temp_dir.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr("cron.jobs.cleanup_recordings.ARCHIVE_PATH", archive_path)

        mock_db_is_annotated.return_value = False
        cleaner = RecordingsCleaner()

        recording = cleaner.load_recording(temp_dir)

        assert recording.segment_count == 0


class TestRemoveRecording:
    """Test suite for RecordingsCleaner.remove_recording method."""

    @patch("cron.jobs.cleanup_recordings.index_db.delete_recording")
    def test_remove_recording_deletes_directory_and_db_row(self, mock_delete_db, tmp_path, caplog):
        """Test remove_recording deletes the recording directory and database row."""
        archive_path = tmp_path / "archive" / "2024" / "01" / "15" / "sparrow_stream"
        archive_path.mkdir(parents=True, exist_ok=True)
        (archive_path / "segment.ts").touch()

        recording = Recording(archive_path, "2024-01-15T143022Z", 1, False)

        cleaner = RecordingsCleaner()
        with caplog.at_level(logging.INFO):
            with patch("cron.jobs.cleanup_recordings.ARCHIVE_PATH", tmp_path / "archive"):
                cleaner.remove_recording(recording)

        # Verify database row was deleted
        mock_delete_db.assert_called_once_with("2024-01-15", "sparrow_stream")
        # Verify directory was deleted
        assert not archive_path.exists()
        # Verify logging
        assert "Removing recording" in caplog.text
        assert "1 segments" in caplog.text

    @patch("cron.jobs.cleanup_recordings.index_db.delete_recording")
    def test_remove_recording_logs_info(self, mock_delete_db, tmp_path, caplog):
        """Test remove_recording logs the removal with segment count."""
        archive_path = tmp_path / "archive" / "2024" / "01" / "15" / "pigeon_stream"
        archive_path.mkdir(parents=True, exist_ok=True)

        recording = Recording(archive_path, "2024-01-15T143022Z", 5, False)

        cleaner = RecordingsCleaner()
        with caplog.at_level(logging.INFO):
            with patch("cron.jobs.cleanup_recordings.ARCHIVE_PATH", tmp_path / "archive"):
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

    @patch("cron.jobs.cleanup_recordings.index_db.is_manually_annotated")
    @patch("cron.jobs.cleanup_recordings.index_db.delete_recording")
    def test_cleanup_day_with_actual_files(self, mock_delete_db, mock_is_annotated):
        """Test cleanup_day with actual archive structure."""
        import shutil

        # Mock all recordings as not annotated
        mock_is_annotated.return_value = False

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

    @patch("cron.jobs.cleanup_recordings.index_db.is_manually_annotated")
    @patch("cron.jobs.cleanup_recordings.index_db.delete_recording")
    def test_cleanup_day_preserves_annotated_recordings(self, mock_delete_db, mock_is_annotated):
        """Test cleanup_day never removes manually annotated recordings."""
        import shutil

        # Mock the first recording as annotated, all others as not annotated
        def is_annotated_side_effect(date_str, stream):
            return stream == "sparrow_2024-01-15T000000Z_annotated"

        mock_is_annotated.side_effect = is_annotated_side_effect

        cleaner = RecordingsCleaner()
        archive_path = Path("/tmp/test_archive_annotated/2024/01/15")
        archive_path.mkdir(parents=True, exist_ok=True)

        # Create one annotated recording with oversized segments (would normally be removed)
        annotated_dir = archive_path / "sparrow_2024-01-15T000000Z_annotated"
        annotated_dir.mkdir()
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

    @patch("cron.jobs.cleanup_recordings.index_db.is_manually_annotated")
    @patch("cron.jobs.cleanup_recordings.index_db.delete_recording")
    def test_cleanup_day_reduces_keep_budget_by_annotated_count(self, mock_delete_db, mock_is_annotated):
        """Test cleanup_day reduces keep budget by annotated recording count."""
        import shutil

        # Mock the first 3 recordings as annotated, all others as not annotated
        def is_annotated_side_effect(date_str, stream):
            return "annotated" in stream

        mock_is_annotated.side_effect = is_annotated_side_effect

        cleaner = RecordingsCleaner()
        archive_path = Path("/tmp/test_archive_budget/2024/01/15")
        archive_path.mkdir(parents=True, exist_ok=True)

        # Create 3 annotated recordings
        for i in range(3):
            annotated_dir = archive_path / f"sparrow_2024-01-15T{i:02d}0000Z_annotated{i}"
            annotated_dir.mkdir()
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


class TestCleanedDaysStore:
    """Test suite for CleanedDaysStore."""

    def test_read_last_cleaned_up_day_missing_file(self, tmp_path, monkeypatch):
        """Test read_last_cleaned_up_day returns None when no history file exists."""
        monkeypatch.setattr(
            "cron.jobs.cleanup_recordings.LAST_CLEANED_UP_DAY_PATH", tmp_path / "cron_last_cleaned_up_day.json"
        )
        store = CleanedDaysStore()

        assert store.read_last_cleaned_up_day() is None

    def test_read_last_cleaned_up_day_existing_file(self, tmp_path, monkeypatch):
        """Test read_last_cleaned_up_day parses the persisted date."""
        path = tmp_path / "cron_last_cleaned_up_day.json"
        path.write_text(json.dumps({"last_cleaned_up_day": "2024-01-15"}))
        monkeypatch.setattr("cron.jobs.cleanup_recordings.LAST_CLEANED_UP_DAY_PATH", path)
        store = CleanedDaysStore()

        assert store.read_last_cleaned_up_day() == date(2024, 1, 15)

    def test_record_writes_and_replaces_file(self, tmp_path, monkeypatch):
        """Test record persists the day and cleans up the tmp file."""
        path = tmp_path / "cron_last_cleaned_up_day.json"
        monkeypatch.setattr("cron.jobs.cleanup_recordings.LAST_CLEANED_UP_DAY_PATH", path)
        store = CleanedDaysStore()

        store.record(date(2024, 1, 15))

        assert json.loads(path.read_text()) == {"last_cleaned_up_day": "2024-01-15"}
        assert not path.with_name(path.name + ".tmp").exists()

    def test_record_overwrites_previous_value(self, tmp_path, monkeypatch):
        """Test record overwrites a previously persisted day."""
        path = tmp_path / "cron_last_cleaned_up_day.json"
        monkeypatch.setattr("cron.jobs.cleanup_recordings.LAST_CLEANED_UP_DAY_PATH", path)
        store = CleanedDaysStore()

        store.record(date(2024, 1, 15))
        store.record(date(2024, 1, 16))

        assert store.read_last_cleaned_up_day() == date(2024, 1, 16)


class TestGetFreeSpaceBytes:
    """Test suite for get_free_space_bytes function."""

    def test_get_free_space_bytes_returns_disk_usage_free(self, monkeypatch):
        """Test get_free_space_bytes returns the free field from shutil.disk_usage."""
        usage = Mock(total=100, used=40, free=60)
        monkeypatch.setattr("cron.jobs.cleanup_recordings.shutil.disk_usage", Mock(return_value=usage))

        assert get_free_space_bytes() == 60


class TestFindEarliestArchiveDay:
    """Test suite for find_earliest_archive_day function."""

    def test_find_earliest_archive_day_no_archive_dir(self, tmp_path, monkeypatch):
        """Test returns None when ARCHIVE_PATH does not exist."""
        monkeypatch.setattr("cron.jobs.cleanup_recordings.ARCHIVE_PATH", tmp_path / "missing")

        assert find_earliest_archive_day() is None

    def test_find_earliest_archive_day_empty_archive_dir(self, tmp_path, monkeypatch):
        """Test returns None when ARCHIVE_PATH has no year directories."""
        monkeypatch.setattr("cron.jobs.cleanup_recordings.ARCHIVE_PATH", tmp_path)

        assert find_earliest_archive_day() is None

    def test_find_earliest_archive_day_empty_year_dir(self, tmp_path, monkeypatch):
        """Test returns None when the earliest year has no month directories."""
        (tmp_path / "2024").mkdir()
        monkeypatch.setattr("cron.jobs.cleanup_recordings.ARCHIVE_PATH", tmp_path)

        assert find_earliest_archive_day() is None

    def test_find_earliest_archive_day_empty_month_dir(self, tmp_path, monkeypatch):
        """Test returns None when the earliest month has no day directories."""
        (tmp_path / "2024" / "01").mkdir(parents=True)
        monkeypatch.setattr("cron.jobs.cleanup_recordings.ARCHIVE_PATH", tmp_path)

        assert find_earliest_archive_day() is None

    def test_find_earliest_archive_day_picks_earliest(self, tmp_path, monkeypatch):
        """Test returns the earliest year/month/day combination present."""
        for year, month, day in [("2024", "03", "10"), ("2024", "01", "20"), ("2023", "12", "31")]:
            (tmp_path / year / month / day).mkdir(parents=True)
        monkeypatch.setattr("cron.jobs.cleanup_recordings.ARCHIVE_PATH", tmp_path)

        assert find_earliest_archive_day() == date(2023, 12, 31)

    def test_find_earliest_archive_day_invalid_components(self, tmp_path, monkeypatch):
        """Test returns None when the directory names aren't a valid date."""
        (tmp_path / "2024" / "13" / "40").mkdir(parents=True)
        monkeypatch.setattr("cron.jobs.cleanup_recordings.ARCHIVE_PATH", tmp_path)

        assert find_earliest_archive_day() is None


class TestFindOldestUncleanedDay:
    """Test suite for find_oldest_uncleaned_day function."""

    def test_find_oldest_uncleaned_day_no_history_uses_earliest(self, tmp_path, monkeypatch):
        """Test starts from the earliest archived day when no history is given."""
        (tmp_path / "2024" / "01" / "15").mkdir(parents=True)
        monkeypatch.setattr("cron.jobs.cleanup_recordings.ARCHIVE_PATH", tmp_path)

        assert find_oldest_uncleaned_day(None) == date(2024, 1, 15)

    def test_find_oldest_uncleaned_day_no_history_and_no_archive(self, tmp_path, monkeypatch):
        """Test returns None when there is no history and nothing archived."""
        monkeypatch.setattr("cron.jobs.cleanup_recordings.ARCHIVE_PATH", tmp_path)

        assert find_oldest_uncleaned_day(None) is None

    def test_find_oldest_uncleaned_day_steps_forward_from_history(self, tmp_path, monkeypatch):
        """Test starts the day after last_cleaned_up_day and steps forward to the next archived day."""
        (tmp_path / "2024" / "01" / "17").mkdir(parents=True)
        monkeypatch.setattr("cron.jobs.cleanup_recordings.ARCHIVE_PATH", tmp_path)

        result = find_oldest_uncleaned_day(date(2024, 1, 15))

        assert result == date(2024, 1, 17)

    def test_find_oldest_uncleaned_day_none_left(self, tmp_path, monkeypatch):
        """Test returns None when stepping forward from history reaches today without finding a day."""
        monkeypatch.setattr("cron.jobs.cleanup_recordings.ARCHIVE_PATH", tmp_path)

        result = find_oldest_uncleaned_day(date.today())

        assert result is None


class TestRunSpacePressureSweep:
    """Test suite for run_space_pressure_sweep function."""

    @patch("cron.jobs.cleanup_recordings.get_free_space_bytes")
    def test_run_space_pressure_sweep_skips_when_above_threshold(self, mock_free_space):
        """Test the sweep does nothing when free space is already above the threshold."""
        mock_free_space.return_value = FREE_SPACE_THRESHOLD_BYTES

        with (
            patch.object(CleanedDaysStore, "read_last_cleaned_up_day") as mock_read,
            patch.object(RecordingsCleaner, "cleanup_day") as mock_cleanup_day,
            patch.object(CleanedDaysStore, "record") as mock_record,
        ):
            run_space_pressure_sweep()

        mock_read.assert_called_once_with()
        mock_cleanup_day.assert_not_called()
        mock_record.assert_not_called()

    @patch("cron.jobs.cleanup_recordings.find_oldest_uncleaned_day")
    @patch("cron.jobs.cleanup_recordings.get_free_space_bytes")
    def test_run_space_pressure_sweep_stops_when_no_days_left(self, mock_free_space, mock_find_day, caplog):
        """Test the sweep stops and logs when no uncleaned days remain despite low free space."""
        mock_free_space.return_value = FREE_SPACE_THRESHOLD_BYTES - 1
        mock_find_day.return_value = None

        with (
            patch.object(CleanedDaysStore, "read_last_cleaned_up_day", return_value=None),
            patch.object(RecordingsCleaner, "cleanup_day") as mock_cleanup_day,
            patch.object(CleanedDaysStore, "record") as mock_record,
            caplog.at_level(logging.INFO),
        ):
            run_space_pressure_sweep()

        mock_cleanup_day.assert_not_called()
        mock_record.assert_not_called()
        assert "no uncleaned days remain" in caplog.text

    @patch("cron.jobs.cleanup_recordings.find_oldest_uncleaned_day")
    @patch("cron.jobs.cleanup_recordings.get_free_space_bytes")
    def test_run_space_pressure_sweep_prunes_until_threshold_reached(self, mock_free_space, mock_find_day):
        """Test the sweep prunes days one at a time, persisting each, until free space clears the threshold."""
        mock_free_space.side_effect = [
            FREE_SPACE_THRESHOLD_BYTES - 1,
            FREE_SPACE_THRESHOLD_BYTES - 1,
            FREE_SPACE_THRESHOLD_BYTES,
        ]
        mock_find_day.side_effect = [date(2024, 1, 15), date(2024, 1, 16)]

        with (
            patch.object(CleanedDaysStore, "read_last_cleaned_up_day", return_value=None),
            patch.object(RecordingsCleaner, "cleanup_day") as mock_cleanup_day,
            patch.object(CleanedDaysStore, "record") as mock_record,
        ):
            run_space_pressure_sweep()

        assert mock_cleanup_day.call_args_list == [call(date(2024, 1, 15)), call(date(2024, 1, 16))]
        assert mock_record.call_args_list == [call(date(2024, 1, 15)), call(date(2024, 1, 16))]


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

    @patch("cron.jobs.cleanup_recordings.run_space_pressure_sweep")
    @patch("sys.argv", ["cleanup_recordings.py"])
    def test_main_default_runs_space_pressure_sweep(self, mock_sweep):
        """Test main runs the free-space sweep when no args provided."""
        from cron.jobs.cleanup_recordings import main

        main()

        mock_sweep.assert_called_once_with()

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
