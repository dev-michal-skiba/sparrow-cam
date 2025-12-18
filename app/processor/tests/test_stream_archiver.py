from pathlib import Path

import pytest

from processor.stream_archiver import StreamArchiver


@pytest.fixture
def temp_hls_path(tmp_path):
    """Create a temporary HLS segments directory."""
    hls_path = tmp_path / "hls"
    hls_path.mkdir()
    return str(hls_path)


@pytest.fixture
def temp_archive_path(tmp_path):
    """Create a temporary archive storage directory."""
    archive_path = tmp_path / "storage" / "sparrow_cam" / "archive"
    archive_path.mkdir(parents=True)
    return str(archive_path)


@pytest.fixture
def sample_files(temp_hls_path):
    """Create sample files in the HLS directory."""
    files = []
    for i in range(3):
        file_path = Path(temp_hls_path) / f"segment_{i:03d}.ts"
        file_path.write_text(f"test segment {i} content")
        files.append(file_path)
    return files


@pytest.fixture
def archiver_with_mocked_paths(monkeypatch, temp_hls_path, temp_archive_path):
    """Create a StreamArchiver instance with mocked paths."""
    monkeypatch.setattr("processor.stream_archiver.HLS_SEGMENTS_PATH", temp_hls_path)
    monkeypatch.setattr("processor.stream_archiver.ARCHIVE_STORAGE_PATH", temp_archive_path)
    return StreamArchiver()


class TestStreamArchiver:
    """Test suite for StreamArchiver class."""

    def test_archive_copies_files_to_timestamped_directory(
        self, archiver_with_mocked_paths, sample_files, temp_archive_path, caplog
    ):
        """Test that archive creates timestamped UUID directory and copies files."""
        archiver_with_mocked_paths.archive()

        # Check that a directory was created
        archived_dirs = list(Path(temp_archive_path).iterdir())
        assert len(archived_dirs) == 1
        archived_dir = archived_dirs[0]
        assert f"Archived 3 files to {archived_dir}" in caplog.text

        # Check that all files were copied
        archived_files = list(archived_dir.iterdir())
        assert len(archived_files) == 3

        # Verify file content
        for original_file in sample_files:
            archived_file = archived_dir / original_file.name
            assert archived_file.exists()
            assert archived_file.read_text() == original_file.read_text()

    def test_archive_with_no_files(self, archiver_with_mocked_paths, temp_archive_path, caplog):
        """Test that archive handles empty HLS directory gracefully."""
        archiver_with_mocked_paths.archive()

        # An empty archive directory is created but contains no files
        archived_dirs = list(Path(temp_archive_path).iterdir())
        assert len(archived_dirs) == 0
        assert "No files found to archive." in caplog.text

    def test_archive_returns_early_if_root_directory_missing(self, monkeypatch, caplog):
        """Test that archive returns early when root directory doesn't exist."""
        monkeypatch.setattr("processor.stream_archiver.ARCHIVE_STORAGE_PATH", "/nonexistent/path")
        archiver = StreamArchiver()

        archiver.archive()

        assert "Root archive storage directory does not exist: /nonexistent/path" in caplog.text
