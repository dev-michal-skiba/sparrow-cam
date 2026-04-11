import argparse
import json
import re

import pytest
from freezegun import freeze_time

from processor.stream_archiver import CopyResult, PlaylistData, SegmentData, StreamArchiver, parse_limit


@pytest.fixture
def playlist_file_content(data_dir):
    """Playlist file content."""
    with open(data_dir / "playlist.m3u8") as f:
        return f.read()


@pytest.fixture
def populate_path(playlist_file_content):
    """Populate path with playlist and segment files."""

    def inner(path):
        playlist_file = path / "playlist.m3u8"
        playlist_file.touch()
        playlist_file.write_text(playlist_file_content)
        for i in range(4):
            segment_file = path / f"segment-{i}.ts"
            segment_file.touch()
            segment_file.write_text(f"Dummy segment data: {i}\n")

    return inner


@pytest.fixture
def stream_path(tmp_path, monkeypatch, populate_path):
    """Fixture for archive storage directory."""
    stream_dir = tmp_path / "stream"
    stream_dir.mkdir()
    populate_path(stream_dir)
    monkeypatch.setattr("processor.stream_archiver.STREAM_PATH", stream_dir)
    return stream_dir


@pytest.fixture
def archive_path(tmp_path, monkeypatch, populate_path):
    """Fixture for archive storage directory."""
    archive_dir = tmp_path / "archive"
    archive_dir.mkdir()
    playlist_dir = archive_dir / "test"
    playlist_dir.mkdir()
    populate_path(playlist_dir)
    monkeypatch.setattr("processor.stream_archiver.ARCHIVE_PATH", archive_dir)
    return archive_dir


@pytest.fixture
def empty_stream_path(tmp_path, monkeypatch):
    """Fixture for empty stream directory."""
    stream_dir = tmp_path / "stream"
    stream_dir.mkdir()

    monkeypatch.setattr("processor.stream_archiver.STREAM_PATH", stream_dir)
    return stream_dir


@pytest.fixture
def multiple_playlist_stream_path(tmp_path, monkeypatch, playlist_file_content):
    """Fixture for stream directory with multiple playlist files."""
    stream_dir = tmp_path / "stream"
    stream_dir.mkdir()
    playlist_file_1 = stream_dir / "playlist_1.m3u8"
    playlist_file_1.touch()
    playlist_file_1.write_text(playlist_file_content)
    playlist_file_2 = stream_dir / "playlist_2.m3u8"
    playlist_file_2.touch()
    playlist_file_2.write_text(playlist_file_content)
    monkeypatch.setattr("processor.stream_archiver.STREAM_PATH", stream_dir)
    return stream_dir


@pytest.fixture
def single_playlist_only_stream_path(tmp_path, monkeypatch, playlist_file_content):
    """Fixture for stream directory with single playlist file only."""
    stream_dir = tmp_path / "stream"
    stream_dir.mkdir()
    playlist_file = stream_dir / "playlist.m3u8"
    playlist_file.touch()
    playlist_file.write_text(playlist_file_content)
    monkeypatch.setattr("processor.stream_archiver.STREAM_PATH", stream_dir)
    return stream_dir


class TestStreamArchiver:
    """Test suite for StreamArchiver class."""

    class TestArchive:
        """Test suite for Archive method."""

        @pytest.mark.usefixtures("stream_path")
        @freeze_time("2024-12-21T15:30:45")
        def test_archive_success_manual_prefix(self, archive_path, playlist_file_content, caplog):
            """Test successful archiving with default manual prefix."""
            archiver = StreamArchiver()

            archiver.archive(prefix="manual")

            # Verify year/month/day directory structure with manual prefix
            destination_path = next(archive_path.glob("2024/12/21/manual_2024-12-21T153045Z_*"))
            assert (destination_path / "playlist.m3u8").exists() is True
            assert (destination_path / "playlist.m3u8").read_text() == playlist_file_content
            assert (destination_path / "segment-0.ts").exists() is True
            assert (destination_path / "segment-1.ts").exists() is True
            assert (destination_path / "segment-2.ts").exists() is True
            assert (destination_path / "segment-3.ts").exists() is True
            assert f"Archived to {destination_path} with 4 segment(s)" in caplog.text

        @pytest.mark.usefixtures("stream_path")
        @freeze_time("2024-12-21T15:30:45")
        def test_archive_success_auto_prefix(self, archive_path, playlist_file_content, caplog):
            """Test successful archiving with auto prefix."""
            archiver = StreamArchiver()

            archiver.archive(prefix="auto")

            # Verify year/month/day directory structure with auto prefix
            destination_path = next(archive_path.glob("2024/12/21/auto_2024-12-21T153045Z_*"))
            assert (destination_path / "playlist.m3u8").exists() is True
            assert (destination_path / "playlist.m3u8").read_text() == playlist_file_content
            assert f"Archived to {destination_path} with 4 segment(s)" in caplog.text

        @pytest.mark.usefixtures("stream_path")
        @freeze_time("2024-12-21T15:30:45")
        def test_archive_success_with_limit(self, archive_path, caplog):
            """Test successful archiving with limit parameter."""
            archiver = StreamArchiver()

            archiver.archive(limit=1, prefix="manual")

            destination_path = next(archive_path.glob("2024/12/21/manual_2024-12-21T153045Z_*"))
            assert (destination_path / "playlist.m3u8").exists() is True
            assert (destination_path / "playlist.m3u8").read_text().splitlines() == [
                "#EXTM3U",
                "#EXT-X-VERSION:3",
                "#EXT-X-MEDIA-SEQUENCE:0",
                "#EXT-X-TARGETDURATION:2",
                "#EXT-X-DISCONTINUITY",
                "#EXTINF:1.668,",
                "segment-3.ts",
            ]
            assert (destination_path / "segment-0.ts").exists() is False
            assert (destination_path / "segment-1.ts").exists() is False
            assert (destination_path / "segment-2.ts").exists() is False
            assert (destination_path / "segment-3.ts").exists() is True
            assert f"Archived to {destination_path} with 1 segment(s)" in caplog.text

        @pytest.mark.usefixtures("stream_path")
        @freeze_time("2024-12-21T15:30:45")
        def test_archive_returns_path(self, archive_path):
            """Test that archive() returns the path to the created archive directory."""
            archiver = StreamArchiver()

            result = archiver.archive(prefix="manual")

            destination_path = next(archive_path.glob("2024/12/21/manual_2024-12-21T153045Z_*"))
            assert result == destination_path
            assert result.is_dir() is True
            assert (result / "playlist.m3u8").exists() is True

        @pytest.mark.usefixtures("stream_path")
        @freeze_time("2024-12-21T15:30:45")
        def test_archive_success_with_end_segment(self, archive_path, caplog):
            """Test archiving with end_segment parameter to prevent race conditions."""
            archiver = StreamArchiver()

            # Archive 2 segments ending with segment-2.ts
            archiver.archive(limit=2, prefix="manual", end_segment="segment-2.ts")

            destination_path = next(archive_path.glob("2024/12/21/manual_2024-12-21T153045Z_*"))
            assert (destination_path / "playlist.m3u8").exists() is True
            assert (destination_path / "playlist.m3u8").read_text().splitlines() == [
                "#EXTM3U",
                "#EXT-X-VERSION:3",
                "#EXT-X-MEDIA-SEQUENCE:0",
                "#EXT-X-TARGETDURATION:2",
                "#EXTINF:1.669,",
                "segment-1.ts",
                "#EXTINF:0.667,",
                "segment-2.ts",
            ]
            assert (destination_path / "segment-0.ts").exists() is False
            assert (destination_path / "segment-1.ts").exists() is True
            assert (destination_path / "segment-2.ts").exists() is True
            assert (destination_path / "segment-3.ts").exists() is False
            assert f"Archived to {destination_path} with 2 segment(s)" in caplog.text

    def test_archive_failure(self, tmp_path, monkeypatch, populate_path, caplog):
        """Test failed archiving of stream files to archive directory."""
        # Set up stream directory with files
        stream_dir = tmp_path / "stream"
        stream_dir.mkdir()
        populate_path(stream_dir)
        monkeypatch.setattr("processor.stream_archiver.STREAM_PATH", stream_dir)

        # Archive directory is NOT set up, should use a non-existent path
        non_existent_archive = tmp_path / "non_existent_archive"
        monkeypatch.setattr("processor.stream_archiver.ARCHIVE_PATH", non_existent_archive)

        archiver = StreamArchiver()

        result = archiver.archive(prefix="manual")

        assert "Archive directory does not exist" in caplog.text
        assert result is None

    class TestValidate:
        """Test suite for Validate method."""

        @pytest.mark.usefixtures("stream_path", "archive_path")
        def test_validate_success(self):
            """Test successful validation with valid stream and archive paths."""
            archiver = StreamArchiver()

            result = archiver.validate(limit=None)

            assert result.is_valid is True
            assert result.error_message is None
            assert result.playlist_filename == "playlist.m3u8"

        @pytest.mark.parametrize("limit", [0, -1])
        def test_validate_failure_invalid_limit(self, limit):
            """Test validation fails with invalid (non-positive) limit."""
            archiver = StreamArchiver()

            result = archiver.validate(limit=limit)

            assert result.is_valid is False
            assert f"Segment limit must be positive, got {limit}" in result.error_message

        @pytest.mark.usefixtures("archive_path")
        def test_validate_failure_invalid_stream_path(self, tmp_path, monkeypatch):
            """Test validation fails when stream path does not exist."""
            non_existent_path = tmp_path / "non_existent"
            monkeypatch.setattr("processor.stream_archiver.STREAM_PATH", non_existent_path)
            archiver = StreamArchiver()

            result = archiver.validate(limit=None)

            assert result.is_valid is False
            assert "Stream directory does not exist" in result.error_message

        @pytest.mark.usefixtures("stream_path")
        def test_validate_failure_invalid_archive_path(self, tmp_path, monkeypatch):
            """Test validation fails when archive path does not exist."""
            non_existent_path = tmp_path / "non_existent"
            monkeypatch.setattr("processor.stream_archiver.ARCHIVE_PATH", non_existent_path)
            archiver = StreamArchiver()

            result = archiver.validate(limit=None)

            assert result.is_valid is False
            assert "Archive directory does not exist" in result.error_message

        @pytest.mark.usefixtures("archive_path", "empty_stream_path")
        def test_validate_failure_no_playlist_file(self):
            """Test validation fails when no playlist file is found."""
            archiver = StreamArchiver()

            result = archiver.validate(limit=None)

            assert result.is_valid is False
            assert "No playlist file found in stream directory" in result.error_message

        @pytest.mark.usefixtures("archive_path", "multiple_playlist_stream_path")
        def test_validate_failure_multiple_playlist_files(self):
            """Test validation fails when multiple playlist files are found."""
            archiver = StreamArchiver()

            result = archiver.validate(limit=None)

            assert result.is_valid is False
            assert "Multiple playlist files found in stream directory" in result.error_message

        @pytest.mark.usefixtures("archive_path", "single_playlist_only_stream_path")
        def test_validate_failure_no_segment_files(self):
            """Test validation fails when no segment files are found."""
            archiver = StreamArchiver()

            result = archiver.validate(limit=None)

            assert result.is_valid is False
            assert "No segment files found in stream directory" in result.error_message

    class TestCopyStream:
        """Test suite for CopyStream method."""

        @freeze_time("2024-12-21T15:30:45")
        @pytest.mark.usefixtures("stream_path", "archive_path")
        def test_copy_stream_success_manual_prefix(self, stream_path, archive_path):
            """Test successful copying of stream files with manual prefix."""
            archiver = StreamArchiver()

            result = archiver.copy_stream("playlist.m3u8", prefix="manual")

            # Verify playlist filename
            assert result.playlist_filename == "playlist.m3u8"
            # Check directory name format: prefix_timestamp_uuid
            dir_name_pattern = r"^manual_\d{4}-\d{2}-\d{2}T\d{6}Z_"
            assert re.match(
                dir_name_pattern, result.destination_path.name
            ), f"Directory name doesn't match expected pattern: {result.destination_path.name}"
            # Extract UUID part and validate format (8-4-4-4-12 hex digits)
            uuid_part = result.destination_path.name.split("_", 2)[2]
            uuid_pattern = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
            assert re.match(uuid_pattern, uuid_part), f"UUID format is invalid: {uuid_part}"
            # Verify year/month/day directory structure
            assert result.destination_path.parent == archive_path / "2024" / "12" / "21"
            assert result.destination_path.is_dir()
            # Verify playlist file was copied
            assert (result.destination_path / "playlist.m3u8").exists()
            assert (result.destination_path / "playlist.m3u8").read_text() == (
                stream_path / "playlist.m3u8"
            ).read_text()
            # Verify all segment files were copied
            for i in range(4):
                segment_file = f"segment-{i}.ts"
                assert (result.destination_path / segment_file).exists()
                assert (result.destination_path / segment_file).read_text() == (stream_path / segment_file).read_text()

        @freeze_time("2024-12-21T15:30:45")
        @pytest.mark.usefixtures("stream_path", "archive_path")
        def test_copy_stream_sets_group_write_permissions(self, stream_path, archive_path):
            """Test that copy_stream sets group write permissions on created directories."""
            archiver = StreamArchiver()

            result = archiver.copy_stream("playlist.m3u8", prefix="manual")

            # Verify destination directory has group write permissions (0o775 = rwxrwxr-x)
            destination_perms = result.destination_path.stat().st_mode & 0o777
            assert destination_perms == 0o775, f"Expected 0o775, got {oct(destination_perms)}"

            # Verify parent date directory (day) has group write permissions
            day_dir = result.destination_path.parent
            day_perms = day_dir.stat().st_mode & 0o777
            assert day_perms == 0o775, f"Day directory expected 0o775, got {oct(day_perms)}"

            # Verify parent month directory has group write permissions
            month_dir = day_dir.parent
            month_perms = month_dir.stat().st_mode & 0o777
            assert month_perms == 0o775, f"Month directory expected 0o775, got {oct(month_perms)}"

            # Verify parent year directory has group write permissions
            year_dir = month_dir.parent
            year_perms = year_dir.stat().st_mode & 0o777
            assert year_perms == 0o775, f"Year directory expected 0o775, got {oct(year_perms)}"

            # Verify that ARCHIVE_PATH itself is not modified (should remain at original perms)
            # This ensures we only modify directories between destination and ARCHIVE_PATH
            assert year_dir.parent == archive_path

        @freeze_time("2024-12-21T15:30:45")
        @pytest.mark.usefixtures("stream_path", "archive_path")
        def test_copy_stream_success_auto_prefix(self, stream_path, archive_path):
            """Test successful copying of stream files with auto prefix."""
            archiver = StreamArchiver()

            result = archiver.copy_stream("playlist.m3u8", prefix="auto")

            # Check directory name starts with auto prefix
            assert result.destination_path.name.startswith("auto_2024-12-21T153045Z_")
            # Verify year/month/day directory structure
            assert result.destination_path.parent == archive_path / "2024" / "12" / "21"

    class TestGetPlaylistData:
        """Test suite for GetPlaylistData method."""

        def test_get_whole_playlist_data(self, archive_path):
            """Test successful getting of whole playlist data."""
            archiver = StreamArchiver()
            copy_result = CopyResult(
                destination_path=archive_path / "test",
                playlist_filename="playlist.m3u8",
            )

            playlist_data = archiver.get_playlist_data(copy_result, limit=None)

            assert playlist_data.filename == "playlist.m3u8"
            assert playlist_data.header_lines == [
                "#EXTM3U",
                "#EXT-X-VERSION:3",
                "#EXT-X-MEDIA-SEQUENCE:0",
                "#EXT-X-TARGETDURATION:2",
            ]
            assert playlist_data.segments_data == [
                SegmentData(
                    metadata=["#EXT-X-DISCONTINUITY", "#EXTINF:1.668,"],
                    name="segment-0.ts",
                ),
                SegmentData(
                    metadata=["#EXTINF:1.669,"],
                    name="segment-1.ts",
                ),
                SegmentData(
                    metadata=["#EXTINF:0.667,"],
                    name="segment-2.ts",
                ),
                SegmentData(
                    metadata=["#EXT-X-DISCONTINUITY", "#EXTINF:1.668,"],
                    name="segment-3.ts",
                ),
            ]

        def test_get_limited_playlist_data(self, archive_path):
            """Test successful getting of limited playlist data."""
            archiver = StreamArchiver()
            copy_result = CopyResult(
                destination_path=archive_path / "test",
                playlist_filename="playlist.m3u8",
            )

            playlist_data = archiver.get_playlist_data(copy_result, limit=2)

            assert playlist_data.filename == "playlist.m3u8"
            assert playlist_data.header_lines == [
                "#EXTM3U",
                "#EXT-X-VERSION:3",
                "#EXT-X-MEDIA-SEQUENCE:0",
                "#EXT-X-TARGETDURATION:2",
            ]
            assert playlist_data.segments_data == [
                SegmentData(
                    metadata=["#EXTINF:0.667,"],
                    name="segment-2.ts",
                ),
                SegmentData(
                    metadata=["#EXT-X-DISCONTINUITY", "#EXTINF:1.668,"],
                    name="segment-3.ts",
                ),
            ]

        def test_get_playlist_data_with_end_segment(self, archive_path):
            """Test getting playlist data with end_segment parameter."""
            archiver = StreamArchiver()
            copy_result = CopyResult(
                destination_path=archive_path / "test",
                playlist_filename="playlist.m3u8",
            )

            # Get 2 segments ending with segment-2.ts
            playlist_data = archiver.get_playlist_data(copy_result, limit=2, end_segment="segment-2.ts")

            assert playlist_data.filename == "playlist.m3u8"
            assert playlist_data.segments_data == [
                SegmentData(
                    metadata=["#EXTINF:1.669,"],
                    name="segment-1.ts",
                ),
                SegmentData(
                    metadata=["#EXTINF:0.667,"],
                    name="segment-2.ts",
                ),
            ]

        def test_get_playlist_data_with_end_segment_no_limit(self, archive_path):
            """Test getting playlist data with end_segment but no limit."""
            archiver = StreamArchiver()
            copy_result = CopyResult(
                destination_path=archive_path / "test",
                playlist_filename="playlist.m3u8",
            )

            # Get all segments up to and including segment-2.ts
            playlist_data = archiver.get_playlist_data(copy_result, limit=None, end_segment="segment-2.ts")

            assert len(playlist_data.segments_data) == 3
            assert playlist_data.segments_data[-1].name == "segment-2.ts"

        def test_get_playlist_data_with_end_segment_limit_exceeds_available(self, archive_path):
            """Test end_segment with limit larger than available segments before it."""
            archiver = StreamArchiver()
            copy_result = CopyResult(
                destination_path=archive_path / "test",
                playlist_filename="playlist.m3u8",
            )

            # Request 10 segments ending with segment-1.ts (only 2 available: segment-0 and segment-1)
            playlist_data = archiver.get_playlist_data(copy_result, limit=10, end_segment="segment-1.ts")

            assert len(playlist_data.segments_data) == 2
            assert playlist_data.segments_data[0].name == "segment-0.ts"
            assert playlist_data.segments_data[1].name == "segment-1.ts"

    class TestCleanArchive:
        """Test suite for CleanArchive method."""

        def test_clean_archive_success(self, archive_path, playlist_file_content):
            """Test successful cleaning of archive directory."""
            archiver = StreamArchiver()
            playlist_data = PlaylistData(
                filename="playlist.m3u8",
                header_lines=[
                    "#EXTM3U",
                    "#EXT-X-VERSION:3",
                    "#EXT-X-MEDIA-SEQUENCE:0",
                    "#EXT-X-TARGETDURATION:2",
                ],
                segments_data=[
                    SegmentData(
                        metadata=["#EXTINF:0.667,"],
                        name="segment-2.ts",
                    ),
                    SegmentData(
                        metadata=["#EXT-X-DISCONTINUITY", "#EXTINF:1.668,"],
                        name="segment-3.ts",
                    ),
                ],
            )
            assert (archive_path / "test" / "segment-0.ts").exists() is True
            assert (archive_path / "test" / "segment-1.ts").exists() is True
            assert (archive_path / "test" / "segment-2.ts").exists() is True
            assert (archive_path / "test" / "segment-3.ts").exists() is True
            assert (archive_path / "test" / "playlist.m3u8").read_text() == playlist_file_content

            archiver.clean_archive(archive_path / "test", playlist_data)

            assert (archive_path / "test" / "segment-0.ts").exists() is False
            assert (archive_path / "test" / "segment-1.ts").exists() is False
            assert (archive_path / "test" / "segment-2.ts").exists() is True
            assert (archive_path / "test" / "segment-3.ts").exists() is True
            assert (archive_path / "test" / "playlist.m3u8").read_text().splitlines() == [
                "#EXTM3U",
                "#EXT-X-VERSION:3",
                "#EXT-X-MEDIA-SEQUENCE:0",
                "#EXT-X-TARGETDURATION:2",
                "#EXTINF:0.667,",
                "segment-2.ts",
                "#EXT-X-DISCONTINUITY",
                "#EXTINF:1.668,",
                "segment-3.ts",
            ]

    class TestParsePlaylist:
        """Test suite for parse_playlist method."""

        def test_parse_playlist_success(self, archive_path):
            """Test successful parsing of HLS playlist file."""
            archiver = StreamArchiver()

            playlist_data = archiver.parse_playlist(archive_path / "test" / "playlist.m3u8")

            assert playlist_data.filename == "playlist.m3u8"
            assert playlist_data.header_lines == [
                "#EXTM3U",
                "#EXT-X-VERSION:3",
                "#EXT-X-MEDIA-SEQUENCE:0",
                "#EXT-X-TARGETDURATION:2",
            ]
            assert len(playlist_data.segments_data) == 4
            assert playlist_data.segments_data[0].name == "segment-0.ts"
            assert playlist_data.segments_data[1].name == "segment-1.ts"
            assert playlist_data.segments_data[2].name == "segment-2.ts"
            assert playlist_data.segments_data[3].name == "segment-3.ts"

    class TestExtendArchive:
        """Test suite for extend_archive method."""

        def test_extend_archive_success(self, stream_path, archive_path, caplog):
            """Test successful extension of archive with new segments."""
            # First create an initial archive with first 2 segments
            archiver = StreamArchiver()
            initial_result = archiver.archive(prefix="test", limit=2)

            # Add new segments to stream
            for i in range(4, 6):
                segment_file = stream_path / f"segment-{i}.ts"
                segment_file.write_text(f"Dummy segment data: {i}\n")

            # Update live playlist with new segments
            playlist_file = stream_path / "playlist.m3u8"
            original_content = playlist_file.read_text()
            new_content = original_content + "#EXTINF:1.5,\nsegment-4.ts\n#EXTINF:1.5,\nsegment-5.ts\n"
            playlist_file.write_text(new_content)

            # Extend archive
            archiver.extend_archive(archive_path=initial_result, end_segment="segment-5.ts")

            # Verify archive was extended
            extended_playlist = (initial_result / "playlist.m3u8").read_text()
            assert "segment-4.ts" in extended_playlist
            assert "segment-5.ts" in extended_playlist
            assert (initial_result / "segment-4.ts").exists() is True
            assert (initial_result / "segment-5.ts").exists() is True
            assert "Extended archive" in caplog.text

        def test_extend_archive_with_none_path(self, caplog):
            """Test extend_archive with None archive path."""
            archiver = StreamArchiver()

            archiver.extend_archive(archive_path=None, end_segment="segment-2.ts")

            assert "Cannot extend archive: no archive path available" in caplog.text

        def test_extend_archive_no_playlist_in_archive(self, tmp_path, monkeypatch, caplog, stream_path):
            """Test extend_archive when archive directory has no playlist file."""
            # Create empty archive directory
            empty_archive = tmp_path / "empty_archive"
            empty_archive.mkdir()
            monkeypatch.setattr("processor.stream_archiver.STREAM_PATH", stream_path)

            archiver = StreamArchiver()

            archiver.extend_archive(archive_path=empty_archive, end_segment="segment-2.ts")

            assert "No playlist file found in archive directory" in caplog.text

        def test_extend_archive_no_segments_in_archive_playlist(
            self, tmp_path, monkeypatch, caplog, stream_path, populate_path
        ):
            """Test extend_archive when archive playlist has no segments."""
            # Create archive with empty playlist
            archive_dir = tmp_path / "archive_empty"
            archive_dir.mkdir()
            empty_playlist = archive_dir / "playlist.m3u8"
            empty_playlist.write_text("#EXTM3U\n#EXT-X-VERSION:3\n")
            monkeypatch.setattr("processor.stream_archiver.STREAM_PATH", stream_path)

            archiver = StreamArchiver()

            archiver.extend_archive(archive_path=archive_dir, end_segment="segment-2.ts")

            assert "No segments found in archive playlist" in caplog.text

        def test_extend_archive_no_live_stream_playlist(self, archive_path, tmp_path, monkeypatch, caplog):
            """Test extend_archive when no live stream playlist is available."""
            # Set up empty stream directory
            empty_stream = tmp_path / "empty_stream"
            empty_stream.mkdir()
            monkeypatch.setattr("processor.stream_archiver.STREAM_PATH", empty_stream)

            archiver = StreamArchiver()
            archiver.extend_archive(archive_path=archive_path / "test", end_segment="segment-2.ts")

            assert "No live stream playlist found for archive extension" in caplog.text

        def test_extend_archive_no_new_segments(self, stream_path, archive_path, caplog):
            """Test extend_archive when there are no new segments to add."""
            # Create an initial archive with all available segments
            archiver = StreamArchiver()
            initial_result = archiver.archive(prefix="test")

            # Try to extend with a segment that's already archived
            archiver.extend_archive(archive_path=initial_result, end_segment="segment-3.ts")

            assert "No new segments to extend archive" in caplog.text

    class TestOnSegment:
        """Test suite for on_segment method and archive scheduling."""

        @pytest.mark.usefixtures("stream_path", "archive_path")
        def test_on_segment_disabled_archive(self, monkeypatch):
            """Test that on_segment does nothing when ARCHIVE_ENABLED=False."""
            monkeypatch.setattr("processor.stream_archiver.ARCHIVE_ENABLED", False)
            archiver = StreamArchiver()

            archiver.on_segment("segment-1.ts", True)

            # State should remain unchanged when archive disabled
            assert archiver._pending_archive_countdown is None
            assert archiver._overlap_countdown is None

        @pytest.mark.usefixtures("stream_path", "archive_path")
        def test_on_segment_no_detection(self, monkeypatch):
            """Test that on_segment handles no detection correctly."""
            monkeypatch.setattr("processor.stream_archiver.ARCHIVE_ENABLED", True)
            archiver = StreamArchiver()

            archiver.on_segment("segment-1.ts", False)

            # State should remain unchanged when no detection
            assert archiver._pending_archive_countdown is None
            assert archiver._overlap_countdown is None

        @pytest.mark.usefixtures("stream_path", "archive_path")
        def test_on_segment_bird_detection_schedules_archive(self, monkeypatch, caplog):
            """Test that bird detection schedules archive with delay."""
            monkeypatch.setattr("processor.stream_archiver.ARCHIVE_ENABLED", True)
            monkeypatch.setattr("processor.stream_archiver.SEGMENTS_AFTER_DETECTION", 3)
            archiver = StreamArchiver()

            archiver.on_segment("segment-0.ts", True)

            # Archive countdown is set to SEGMENTS_AFTER_DETECTION + 1 = 4, then decremented to 3 in same call
            assert archiver._pending_archive_countdown == 3
            assert archiver._pending_archive_is_extension is False
            assert "Bird detected, archive scheduled in 3 segments" in caplog.text

        @pytest.mark.usefixtures("stream_path", "archive_path")
        def test_on_segment_multiple_detections_during_countdown(self, monkeypatch):
            """Test that multiple detections during countdown don't reschedule archive."""
            monkeypatch.setattr("processor.stream_archiver.ARCHIVE_ENABLED", True)
            monkeypatch.setattr("processor.stream_archiver.SEGMENTS_AFTER_DETECTION", 3)
            archiver = StreamArchiver()

            archiver.on_segment("segment-0.ts", True)  # First detection, schedules
            first_countdown = archiver._pending_archive_countdown
            archiver.on_segment("segment-1.ts", True)  # Second detection, should be ignored
            second_countdown = archiver._pending_archive_countdown

            # Countdown should decrease but not be reset
            assert second_countdown == first_countdown - 1

        @pytest.mark.usefixtures("stream_path", "archive_path")
        def test_on_segment_countdown_execution(self, monkeypatch, caplog):
            """Test that archive is executed after countdown completes."""
            monkeypatch.setattr("processor.stream_archiver.ARCHIVE_ENABLED", True)
            monkeypatch.setattr("processor.stream_archiver.ARCHIVE_SEGMENT_COUNT", 15)
            monkeypatch.setattr("processor.stream_archiver.SEGMENTS_AFTER_DETECTION", 2)
            archiver = StreamArchiver()

            archiver.on_segment("segment-0.ts", True)  # Segment 1: schedules archive
            archiver.on_segment("segment-1.ts", False)  # Segment 2: countdown = 2
            archiver.on_segment("segment-2.ts", False)  # Segment 3: countdown = 1, countdown <= 0, execute archive

            # Archive should have been executed
            assert archiver._pending_archive_countdown is None
            assert archiver._overlap_countdown == 7  # SEGMENTS_BEFORE_DETECTION
            assert "Executing scheduled archive" in caplog.text

        @pytest.mark.usefixtures("stream_path", "archive_path")
        def test_on_segment_overlap_zone_extends_archive(self, monkeypatch, caplog):
            """Test that detection in overlap zone extends previous archive."""
            monkeypatch.setattr("processor.stream_archiver.ARCHIVE_ENABLED", True)
            monkeypatch.setattr("processor.stream_archiver.ARCHIVE_SEGMENT_COUNT", 15)
            monkeypatch.setattr("processor.stream_archiver.SEGMENTS_BEFORE_DETECTION", 7)
            monkeypatch.setattr("processor.stream_archiver.SEGMENTS_AFTER_DETECTION", 7)
            archiver = StreamArchiver()

            # First detection triggers archive at segment 8 (7 after + 1)
            archiver.on_segment("segment-0.ts", True)
            for i in range(1, 8):
                archiver.on_segment(f"segment-{i}.ts", False)
            # Now at segment 8, countdown should be 0 and archive executes
            archiver.on_segment("segment-8.ts", False)

            # Now detect again within overlap zone (within 7 segments of segment 8)
            # Second detection at segment 10 (within overlap zone)
            archiver.on_segment("segment-9.ts", False)
            archiver.on_segment("segment-10.ts", True)  # In overlap zone

            # Should schedule extension instead of new archive
            assert archiver._pending_archive_is_extension is True
            assert "Bird in overlap zone, extending previous archive" in caplog.text

        @pytest.mark.usefixtures("stream_path", "archive_path")
        def test_on_segment_outside_overlap_zone_new_archive(self, monkeypatch):
            """Test that detection outside overlap zone creates new archive."""
            monkeypatch.setattr("processor.stream_archiver.ARCHIVE_ENABLED", True)
            monkeypatch.setattr("processor.stream_archiver.ARCHIVE_SEGMENT_COUNT", 15)
            monkeypatch.setattr("processor.stream_archiver.SEGMENTS_BEFORE_DETECTION", 7)
            monkeypatch.setattr("processor.stream_archiver.SEGMENTS_AFTER_DETECTION", 7)
            archiver = StreamArchiver()

            # First detection
            archiver.on_segment("segment-0.ts", True)
            for i in range(1, 8):
                archiver.on_segment(f"segment-{i}.ts", False)
            archiver.on_segment("segment-8.ts", False)

            # Second detection outside overlap zone (more than 7 segments later)
            for i in range(9, 17):  # Segments 9-16
                archiver.on_segment(f"segment-{i}.ts", False)
            archiver.on_segment("segment-17.ts", True)  # Outside overlap zone

            # Should schedule new archive, not extension
            assert archiver._pending_archive_is_extension is False


class TestPruneDetections:
    """Test suite for prune_detections method."""

    def test_removes_stale_detections(self):
        """Test that detections for segments no longer in valid_segments are removed."""
        archiver = StreamArchiver()
        archiver._segment_detections = {
            "segment-1.ts": [{"class": "Pigeon"}],
            "segment-2.ts": [{"class": "Great tit"}],
            "segment-3.ts": [{"class": "Pigeon"}],
        }

        archiver.prune_detections({"segment-2.ts", "segment-3.ts"})

        assert "segment-1.ts" not in archiver._segment_detections
        assert "segment-2.ts" in archiver._segment_detections
        assert "segment-3.ts" in archiver._segment_detections

    def test_no_op_when_all_segments_valid(self):
        """Test that nothing is removed when all stored segments are still valid."""
        archiver = StreamArchiver()
        archiver._segment_detections = {"segment-1.ts": [{"class": "Pigeon"}]}

        archiver.prune_detections({"segment-1.ts", "segment-2.ts"})

        assert "segment-1.ts" in archiver._segment_detections

    def test_clears_all_when_valid_set_empty(self):
        """Test that all detections are removed when valid_segments is empty."""
        archiver = StreamArchiver()
        archiver._segment_detections = {"segment-1.ts": [{"class": "Pigeon"}]}

        archiver.prune_detections(set())

        assert archiver._segment_detections == {}


class TestRecordDetections:
    """Test suite for record_detections method."""

    def test_stores_non_empty_detections(self):
        """Test that non-empty detections are stored keyed by segment name."""
        archiver = StreamArchiver()
        detections = [{"class": "Pigeon", "confidence": 0.87, "roi": {"x1": 10, "y1": 20, "x2": 100, "y2": 200}}]

        archiver.record_detections("segment-1.ts", detections)

        assert archiver._segment_detections["segment-1.ts"] == detections

    def test_ignores_empty_detections(self):
        """Test that empty detection lists are not stored."""
        archiver = StreamArchiver()

        archiver.record_detections("segment-1.ts", [])

        assert "segment-1.ts" not in archiver._segment_detections


class TestWriteMeta:
    """Test suite for write_meta method."""

    def test_write_meta_creates_json_with_matching_segments(self, archive_path):
        """Test that meta.json is created with only detections for archived segments."""
        archiver = StreamArchiver()
        detection = {"class": "Pigeon", "confidence": 0.87, "roi": {"x1": 10, "y1": 20, "x2": 100, "y2": 200}}
        archiver._segment_detections = {
            "segment-1.ts": [detection],
            "segment-9.ts": [detection],  # not in playlist
        }
        playlist_data = PlaylistData(
            filename="playlist.m3u8",
            header_lines=[],
            segments_data=[SegmentData(metadata=[], name="segment-1.ts")],
        )

        archiver.write_meta(archive_path / "test", playlist_data)

        meta = json.loads((archive_path / "test" / "meta.json").read_text())
        assert meta["version"] == 1
        assert meta["detections"] == {"segment-1.ts": [detection]}

    def test_write_meta_creates_empty_detections_when_no_match(self, archive_path):
        """Test that meta.json has empty detections when no recorded segments are in the archive."""
        archiver = StreamArchiver()
        playlist_data = PlaylistData(
            filename="playlist.m3u8",
            header_lines=[],
            segments_data=[SegmentData(metadata=[], name="segment-1.ts")],
        )

        archiver.write_meta(archive_path / "test", playlist_data)

        meta = json.loads((archive_path / "test" / "meta.json").read_text())
        assert meta == {"version": 1, "detections": {}}


class TestArchiveMeta:
    """Test suite for meta.json creation during archive."""

    @pytest.mark.usefixtures("stream_path")
    @freeze_time("2024-12-21T15:30:45")
    def test_archive_creates_meta_json(self, archive_path):
        """Test that archive() creates a meta.json file with detection info."""
        archiver = StreamArchiver()
        detection = {"class": "Pigeon", "confidence": 0.87, "roi": {"x1": 10, "y1": 20, "x2": 100, "y2": 200}}
        archiver.record_detections("segment-2.ts", [detection])

        archiver.archive(prefix="manual")

        destination_path = next(archive_path.glob("2024/12/21/manual_2024-12-21T153045Z_*"))
        assert (destination_path / "meta.json").exists() is True
        meta = json.loads((destination_path / "meta.json").read_text())
        assert meta["version"] == 1
        assert "segment-2.ts" in meta["detections"]

    @pytest.mark.usefixtures("stream_path")
    @freeze_time("2024-12-21T15:30:45")
    def test_archive_meta_json_excludes_non_archived_segments(self, archive_path):
        """Test that meta.json only includes segments present in the archive."""
        archiver = StreamArchiver()
        detection = {"class": "Pigeon", "confidence": 0.87, "roi": {"x1": 10, "y1": 20, "x2": 100, "y2": 200}}
        archiver.record_detections("segment-3.ts", [detection])  # Will be in archive (last segment)
        archiver.record_detections("segment-2.ts", [detection])  # Will NOT be in archive (limit=1 takes last)

        archiver.archive(prefix="manual", limit=1)

        destination_path = next(archive_path.glob("2024/12/21/manual_2024-12-21T153045Z_*"))
        meta = json.loads((destination_path / "meta.json").read_text())
        assert "segment-3.ts" in meta["detections"]
        assert "segment-2.ts" not in meta["detections"]

    @pytest.mark.usefixtures("stream_path")
    @freeze_time("2024-12-21T15:30:45")
    def test_archive_meta_json_empty_when_no_detections(self, archive_path):
        """Test that meta.json has empty detections when no birds were detected."""
        archiver = StreamArchiver()

        archiver.archive(prefix="manual")

        destination_path = next(archive_path.glob("2024/12/21/manual_2024-12-21T153045Z_*"))
        meta = json.loads((destination_path / "meta.json").read_text())
        assert meta == {"version": 1, "detections": {}}

    def test_extend_archive_updates_meta_json(self, stream_path, archive_path):
        """Test that extend_archive() updates meta.json with detections from new segments."""
        archiver = StreamArchiver()
        initial_result = archiver.archive(prefix="test", limit=2)

        # Add new segments to stream
        for i in range(4, 6):
            (stream_path / f"segment-{i}.ts").write_text(f"Dummy segment data: {i}\n")
        original_content = (stream_path / "playlist.m3u8").read_text()
        (stream_path / "playlist.m3u8").write_text(
            original_content + "#EXTINF:1.5,\nsegment-4.ts\n#EXTINF:1.5,\nsegment-5.ts\n"
        )

        detection = {"class": "Pigeon", "confidence": 0.9, "roi": {"x1": 0, "y1": 0, "x2": 10, "y2": 10}}
        archiver.record_detections("segment-5.ts", [detection])

        archiver.extend_archive(archive_path=initial_result, end_segment="segment-5.ts")

        meta = json.loads((initial_result / "meta.json").read_text())
        assert meta["version"] == 1
        assert "segment-5.ts" in meta["detections"]


class TestParseLimit:
    """Test suite for parse_limit function."""

    @pytest.mark.parametrize(
        "value, expected",
        [
            ("-1", -1),
            ("0", 0),
            ("10", 10),
            ("None", None),
            ("none", None),
            ("nOnE", None),
            ("", None),
        ],
    )
    def test_parse_limit_success(self, value, expected):
        """Test successful parsing of limit."""
        assert parse_limit(value) == expected

    @pytest.mark.parametrize("value", ["abc", "10.5"])
    def test_parse_limit_failure(self, value):
        """Test failed parsing of limit."""
        with pytest.raises(argparse.ArgumentTypeError) as e:
            parse_limit(value)

        assert str(e.value) == f"Invalid limit '{value}', expected integer or None"
