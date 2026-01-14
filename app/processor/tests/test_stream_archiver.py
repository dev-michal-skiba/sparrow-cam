import argparse
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
            destination_path = next(archive_path.glob("2024/12/21/manual_2024-12-21T15:30:45Z_*"))
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
            destination_path = next(archive_path.glob("2024/12/21/auto_2024-12-21T15:30:45Z_*"))
            assert (destination_path / "playlist.m3u8").exists() is True
            assert (destination_path / "playlist.m3u8").read_text() == playlist_file_content
            assert f"Archived to {destination_path} with 4 segment(s)" in caplog.text

        @pytest.mark.usefixtures("stream_path")
        @freeze_time("2024-12-21T15:30:45")
        def test_archive_success_with_limit(self, archive_path, caplog):
            """Test successful archiving with limit parameter."""
            archiver = StreamArchiver()

            archiver.archive(limit=1, prefix="manual")

            destination_path = next(archive_path.glob("2024/12/21/manual_2024-12-21T15:30:45Z_*"))
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
        def test_archive_success_with_end_segment(self, archive_path, caplog):
            """Test archiving with end_segment parameter to prevent race conditions."""
            archiver = StreamArchiver()

            # Archive 2 segments ending with segment-2.ts
            archiver.archive(limit=2, prefix="manual", end_segment="segment-2.ts")

            destination_path = next(archive_path.glob("2024/12/21/manual_2024-12-21T15:30:45Z_*"))
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

        archiver.archive(prefix="manual")

        assert "Archive directory does not exist" in caplog.text

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
            dir_name_pattern = r"^manual_\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z_"
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
        def test_copy_stream_success_auto_prefix(self, stream_path, archive_path):
            """Test successful copying of stream files with auto prefix."""
            archiver = StreamArchiver()

            result = archiver.copy_stream("playlist.m3u8", prefix="auto")

            # Check directory name starts with auto prefix
            assert result.destination_path.name.startswith("auto_2024-12-21T15:30:45Z_")
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
