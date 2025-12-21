import re

import pytest
from freezegun import freeze_time

from processor.stream_archiver import CopyResult, PlaylistData, SegmentData, StreamArchiver


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
        def test_archive_success(self, archive_path, playlist_file_content, caplog):
            """Test successful archiving of stream files to archive directory."""
            archiver = StreamArchiver()

            archiver.archive()

            destination_path = next(archive_path.glob("2024-12-21T15:30:45Z_*"))
            assert (destination_path / "playlist.m3u8").exists() is True
            assert (destination_path / "playlist.m3u8").read_text() == playlist_file_content.strip()
            assert (destination_path / "segment-0.ts").exists() is True
            assert (destination_path / "segment-1.ts").exists() is True
            assert (destination_path / "segment-2.ts").exists() is True
            assert (destination_path / "segment-3.ts").exists() is True
            assert f"Archived to {destination_path} with 4 segment(s)" in caplog.text

        @pytest.mark.usefixtures("stream_path")
        @freeze_time("2024-12-21T15:30:45")
        def test_archive_success_with_limit(self, archive_path, caplog):
            """Test successful archiving of stream files to archive directory."""
            archiver = StreamArchiver()

            archiver.archive(limit=1)

            destination_path = next(archive_path.glob("2024-12-21T15:30:45Z_*"))
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

    def test_archive_failure(self, caplog):
        """Test failed archiving of stream files to archive directory."""
        archiver = StreamArchiver()

        archiver.archive()

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
        def test_copy_stream_success(self, stream_path, archive_path):
            """Test successful copying of stream files to archive directory."""
            archiver = StreamArchiver()

            result = archiver.copy_stream("playlist.m3u8")

            # Verify playlist filename
            assert result.playlist_filename == "playlist.m3u8"
            # Check directory name format: timestamp_uuid
            timestamp_pattern = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z_"
            assert re.match(
                timestamp_pattern, result.destination_path.name
            ), f"Directory name doesn't match timestamp pattern: {result.destination_path.name}"
            # Extract UUID part and validate format (8-4-4-4-12 hex digits)
            uuid_part = result.destination_path.name.split("_", 1)[1]
            uuid_pattern = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
            assert re.match(uuid_pattern, uuid_part), f"UUID format is invalid: {uuid_part}"
            # Verify directory was created in archive path
            assert result.destination_path.parent == archive_path
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
