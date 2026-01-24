import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from lab.converter import convert_all_playlists, convert_playlist_to_pngs, get_unconverted_playlists


class TestGetUnconvertedPlaylists:
    """Tests for get_unconverted_playlists function."""

    def test_returns_playlists_in_archive_but_not_in_images(self):
        """Should return playlist paths that exist in archive but not in images."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            archive_path = tmpdir_path / "archive"
            images_path = tmpdir_path / "images"

            archive_path.mkdir()
            images_path.mkdir()

            # Create nested structure: year/month/day/playlist
            (archive_path / "2024" / "01" / "15" / "playlist1").mkdir(parents=True)
            (archive_path / "2024" / "01" / "15" / "playlist2").mkdir(parents=True)
            (archive_path / "2024" / "01" / "15" / "playlist3").mkdir(parents=True)

            # Create .ts files in playlists
            (archive_path / "2024" / "01" / "15" / "playlist1" / "video.ts").write_text("")
            (archive_path / "2024" / "01" / "15" / "playlist2" / "video.ts").write_text("")
            (archive_path / "2024" / "01" / "15" / "playlist3" / "video.ts").write_text("")

            # Create converted folder for playlist1
            (images_path / "2024" / "01" / "15" / "playlist1").mkdir(parents=True)

            result = get_unconverted_playlists(archive_path, images_path)

            assert "2024/01/15/playlist2" in result
            assert "2024/01/15/playlist3" in result
            assert "2024/01/15/playlist1" not in result

    def test_returns_empty_list_when_all_playlists_converted(self):
        """Should return empty list when all archive playlists exist in images."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            archive_path = tmpdir_path / "archive"
            images_path = tmpdir_path / "images"

            archive_path.mkdir()
            images_path.mkdir()

            (archive_path / "2024" / "01" / "15" / "playlist1").mkdir(parents=True)
            (archive_path / "2024" / "01" / "15" / "playlist1" / "video.ts").write_text("")
            (images_path / "2024" / "01" / "15" / "playlist1").mkdir(parents=True)

            result = get_unconverted_playlists(archive_path, images_path)

            assert result == []

    def test_creates_images_directory_if_not_exists(self):
        """Should create images directory if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            archive_path = tmpdir_path / "archive"
            images_path = tmpdir_path / "images"

            archive_path.mkdir()
            assert not images_path.exists()

            get_unconverted_playlists(archive_path, images_path)

            assert images_path.exists()
            assert images_path.is_dir()

    def test_returns_empty_list_when_archive_missing(self):
        """Should return empty list if archive directory doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            archive_path = tmpdir_path / "nonexistent"
            images_path = tmpdir_path / "images"

            result = get_unconverted_playlists(archive_path, images_path)

            assert result == []

    def test_ignores_non_numeric_year_folders(self):
        """Should ignore non-numeric year folders."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            archive_path = tmpdir_path / "archive"
            images_path = tmpdir_path / "images"

            archive_path.mkdir()
            images_path.mkdir()

            (archive_path / "not_a_year").mkdir()
            (archive_path / "2024" / "01" / "15" / "playlist1").mkdir(parents=True)
            (archive_path / "2024" / "01" / "15" / "playlist1" / "video.ts").write_text("")

            result = get_unconverted_playlists(archive_path, images_path)

            assert "2024/01/15/playlist1" in result
            assert len(result) == 1

    def test_returns_only_playlists_with_ts_files(self):
        """Should only return playlists that contain .ts files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            archive_path = tmpdir_path / "archive"
            images_path = tmpdir_path / "images"

            archive_path.mkdir()
            images_path.mkdir()

            # Create playlist1 with .ts file
            (archive_path / "2024" / "01" / "15" / "playlist1").mkdir(parents=True)
            (archive_path / "2024" / "01" / "15" / "playlist1" / "video.ts").write_text("")

            # Create playlist2 without .ts file
            (archive_path / "2024" / "01" / "15" / "playlist2").mkdir(parents=True)

            result = get_unconverted_playlists(archive_path, images_path)

            assert "2024/01/15/playlist1" in result
            assert "2024/01/15/playlist2" not in result

    def test_ignores_non_numeric_month_folders(self):
        """Should ignore non-numeric month folders."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            archive_path = tmpdir_path / "archive"
            images_path = tmpdir_path / "images"

            archive_path.mkdir()
            images_path.mkdir()

            # Create month with non-numeric name
            (archive_path / "2024" / "january" / "15" / "playlist1").mkdir(parents=True)
            (archive_path / "2024" / "january" / "15" / "playlist1" / "video.ts").write_text("")

            # Create valid month with numeric name
            (archive_path / "2024" / "01" / "15" / "playlist2").mkdir(parents=True)
            (archive_path / "2024" / "01" / "15" / "playlist2" / "video.ts").write_text("")

            result = get_unconverted_playlists(archive_path, images_path)

            assert "2024/01/15/playlist2" in result
            assert len([p for p in result if "january" in p]) == 0

    def test_ignores_non_numeric_day_folders(self):
        """Should ignore non-numeric day folders."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            archive_path = tmpdir_path / "archive"
            images_path = tmpdir_path / "images"

            archive_path.mkdir()
            images_path.mkdir()

            # Create day with non-numeric name
            (archive_path / "2024" / "01" / "monday" / "playlist1").mkdir(parents=True)
            (archive_path / "2024" / "01" / "monday" / "playlist1" / "video.ts").write_text("")

            # Create valid day with numeric name
            (archive_path / "2024" / "01" / "15" / "playlist2").mkdir(parents=True)
            (archive_path / "2024" / "01" / "15" / "playlist2" / "video.ts").write_text("")

            result = get_unconverted_playlists(archive_path, images_path)

            assert "2024/01/15/playlist2" in result
            assert len([p for p in result if "monday" in p]) == 0

    def test_ignores_files_in_day_directories(self):
        """Should ignore files in day directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            archive_path = tmpdir_path / "archive"
            images_path = tmpdir_path / "images"

            archive_path.mkdir()
            images_path.mkdir()

            # Create file in day directory
            day_dir = archive_path / "2024" / "01" / "15"
            day_dir.mkdir(parents=True)
            (day_dir / "readme.txt").write_text("content")

            # Create valid playlist
            (day_dir / "playlist1").mkdir()
            (day_dir / "playlist1" / "video.ts").write_text("")

            result = get_unconverted_playlists(archive_path, images_path)

            assert "2024/01/15/playlist1" in result
            assert len(result) == 1


class TestConvertPlaylistToPngs:
    """Tests for convert_playlist_to_pngs function."""

    def test_converts_single_ts_file_to_pngs(self):
        """Should convert a single .ts file to PNG frames."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            folder_path = tmpdir_path / "input"
            images_path = tmpdir_path / "images"

            folder_path.mkdir()

            # Mock cv2.VideoCapture
            mock_cap = MagicMock()
            mock_cap.isOpened.return_value = True
            mock_cap.read.side_effect = [
                (True, b"frame1"),
                (True, b"frame2"),
                (False, None),
            ]

            with patch("lab.converter.cv2.VideoCapture", return_value=mock_cap):
                with patch("lab.converter.cv2.imwrite") as mock_imwrite:
                    (folder_path / "video.ts").write_text("dummy")

                    convert_playlist_to_pngs(folder_path, images_path)

                    assert mock_imwrite.call_count == 2
                    assert mock_cap.release.called

    def test_creates_target_folder_with_same_name(self):
        """Should create target folder with the same name as input folder."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            folder_path = tmpdir_path / "input" / "my_folder"
            images_path = tmpdir_path / "images"

            folder_path.mkdir(parents=True)

            mock_cap = MagicMock()
            mock_cap.isOpened.return_value = True
            mock_cap.read.side_effect = [(False, None)]

            with patch("lab.converter.cv2.VideoCapture", return_value=mock_cap):
                with patch("lab.converter.cv2.imwrite"):
                    (folder_path / "video.ts").write_text("dummy")

                    convert_playlist_to_pngs(folder_path, images_path)

                    expected_target = images_path / "my_folder"
                    assert expected_target.exists()

    def test_names_output_files_with_stem_and_index(self):
        """Should name PNG files as '<ts-file-stem>-<frame_index>.png'."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            folder_path = tmpdir_path / "input"
            images_path = tmpdir_path / "images"

            folder_path.mkdir()

            mock_cap = MagicMock()
            mock_cap.isOpened.return_value = True
            mock_cap.read.side_effect = [
                (True, b"frame1"),
                (True, b"frame2"),
                (False, None),
            ]

            with patch("lab.converter.cv2.VideoCapture", return_value=mock_cap):
                with patch("lab.converter.cv2.imwrite") as mock_imwrite:
                    (folder_path / "video.ts").write_text("dummy")

                    convert_playlist_to_pngs(folder_path, images_path)

                    calls = mock_imwrite.call_args_list
                    assert "video-0.png" in calls[0][0][0]
                    assert "video-1.png" in calls[1][0][0]

    def test_starts_frame_index_at_zero(self):
        """Should start frame indexing at 0."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            folder_path = tmpdir_path / "input"
            images_path = tmpdir_path / "images"

            folder_path.mkdir()

            mock_cap = MagicMock()
            mock_cap.isOpened.return_value = True
            mock_cap.read.side_effect = [(True, b"frame1"), (False, None)]

            with patch("lab.converter.cv2.VideoCapture", return_value=mock_cap):
                with patch("lab.converter.cv2.imwrite") as mock_imwrite:
                    (folder_path / "video.ts").write_text("dummy")

                    convert_playlist_to_pngs(folder_path, images_path)

                    calls = mock_imwrite.call_args_list
                    assert "video-0.png" in calls[0][0][0]

    def test_converts_multiple_ts_files(self):
        """Should convert multiple .ts files in sorted order."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            folder_path = tmpdir_path / "input"
            images_path = tmpdir_path / "images"

            folder_path.mkdir()

            mock_cap = MagicMock()
            mock_cap.isOpened.return_value = True
            mock_cap.read.side_effect = [(False, None)] * 10

            with patch("lab.converter.cv2.VideoCapture", return_value=mock_cap) as mock_video_capture:
                with patch("lab.converter.cv2.imwrite"):
                    (folder_path / "video2.ts").write_text("dummy")
                    (folder_path / "video1.ts").write_text("dummy")

                    convert_playlist_to_pngs(folder_path, images_path)

                    # Should be called twice (once for each file), in sorted order
                    assert mock_video_capture.call_count == 2
                    calls = mock_video_capture.call_args_list
                    assert "video1.ts" in calls[0][0][0]
                    assert "video2.ts" in calls[1][0][0]

    def test_returns_zero_frames_when_no_ts_files_found(self):
        """Should return 0 frames when no .ts files are found."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            folder_path = tmpdir_path / "input"
            images_path = tmpdir_path / "images"

            folder_path.mkdir()

            frames = convert_playlist_to_pngs(folder_path, images_path)

            assert frames == 0

    def test_continues_when_video_file_cannot_be_opened(self):
        """Should continue processing when a video file cannot be opened."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            folder_path = tmpdir_path / "input"
            images_path = tmpdir_path / "images"

            folder_path.mkdir()

            mock_cap = MagicMock()
            mock_cap.isOpened.return_value = False

            with patch("lab.converter.cv2.VideoCapture", return_value=mock_cap):
                (folder_path / "video.ts").write_text("dummy")

                # Should not raise an exception
                frames = convert_playlist_to_pngs(folder_path, images_path)

                assert frames == 0

    def test_releases_video_capture(self):
        """Should release video capture after processing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            folder_path = tmpdir_path / "input"
            images_path = tmpdir_path / "images"

            folder_path.mkdir()

            mock_cap = MagicMock()
            mock_cap.isOpened.return_value = True
            mock_cap.read.side_effect = [(True, b"frame"), (False, None)]

            with patch("lab.converter.cv2.VideoCapture", return_value=mock_cap):
                with patch("lab.converter.cv2.imwrite"):
                    (folder_path / "video.ts").write_text("dummy")

                    convert_playlist_to_pngs(folder_path, images_path)

                    assert mock_cap.release.called

    def test_raises_file_not_found_error_when_folder_missing(self):
        """Should raise FileNotFoundError if folder doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            folder_path = tmpdir_path / "nonexistent"
            images_path = tmpdir_path / "images"

            with pytest.raises(FileNotFoundError) as excinfo:
                convert_playlist_to_pngs(folder_path, images_path)

            assert "Folder does not exist" in str(excinfo.value)
            assert str(folder_path) in str(excinfo.value)

    def test_raises_not_a_directory_error_when_folder_is_file(self):
        """Should raise NotADirectoryError if folder path is a file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            folder_path = tmpdir_path / "file.txt"
            images_path = tmpdir_path / "images"

            folder_path.write_text("content")

            with pytest.raises(NotADirectoryError) as excinfo:
                convert_playlist_to_pngs(folder_path, images_path)

            assert "Path is not a directory" in str(excinfo.value)
            assert str(folder_path) in str(excinfo.value)

    def test_creates_images_base_path_if_not_exists(self):
        """Should create images_base_path if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            folder_path = tmpdir_path / "input"
            images_path = tmpdir_path / "images"

            folder_path.mkdir()

            mock_cap = MagicMock()
            mock_cap.isOpened.return_value = True
            mock_cap.read.side_effect = [(False, None)]

            assert not images_path.exists()

            with patch("lab.converter.cv2.VideoCapture", return_value=mock_cap):
                with patch("lab.converter.cv2.imwrite"):
                    (folder_path / "video.ts").write_text("dummy")

                    convert_playlist_to_pngs(folder_path, images_path)

                    assert images_path.exists()

    def test_creates_nested_images_base_path(self):
        """Should create nested images_base_path directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            folder_path = tmpdir_path / "input"
            images_path = tmpdir_path / "a" / "b" / "c" / "images"

            folder_path.mkdir()

            mock_cap = MagicMock()
            mock_cap.isOpened.return_value = True
            mock_cap.read.side_effect = [(False, None)]

            with patch("lab.converter.cv2.VideoCapture", return_value=mock_cap):
                with patch("lab.converter.cv2.imwrite"):
                    (folder_path / "video.ts").write_text("dummy")

                    convert_playlist_to_pngs(folder_path, images_path)

                    assert images_path.exists()

    def test_calls_on_file_progress_callback(self):
        """Should call on_file_progress callback for each file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            folder_path = tmpdir_path / "input"
            images_path = tmpdir_path / "images"

            folder_path.mkdir()

            mock_cap = MagicMock()
            mock_cap.isOpened.return_value = True
            mock_cap.read.side_effect = [(False, None)] * 10

            progress_callback = MagicMock()

            with patch("lab.converter.cv2.VideoCapture", return_value=mock_cap):
                with patch("lab.converter.cv2.imwrite"):
                    (folder_path / "video1.ts").write_text("dummy")
                    (folder_path / "video2.ts").write_text("dummy")

                    convert_playlist_to_pngs(folder_path, images_path, on_file_progress=progress_callback)

                    # Should be called twice (once for each file)
                    assert progress_callback.call_count == 2
                    # Check the arguments passed
                    calls = progress_callback.call_args_list
                    assert calls[0][0] == (1, 2, "video1.ts")
                    assert calls[1][0] == (2, 2, "video2.ts")

    def test_returns_total_frames_count(self):
        """Should return total number of frames converted."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            folder_path = tmpdir_path / "input"
            images_path = tmpdir_path / "images"

            folder_path.mkdir()

            mock_cap = MagicMock()
            mock_cap.isOpened.return_value = True
            # First file: 2 frames, second file: 3 frames
            mock_cap.read.side_effect = [
                (True, b"frame1"),
                (True, b"frame2"),
                (False, None),
                (True, b"frame1"),
                (True, b"frame2"),
                (True, b"frame3"),
                (False, None),
            ]

            with patch("lab.converter.cv2.VideoCapture", return_value=mock_cap):
                with patch("lab.converter.cv2.imwrite"):
                    (folder_path / "video1.ts").write_text("dummy")
                    (folder_path / "video2.ts").write_text("dummy")

                    total_frames = convert_playlist_to_pngs(folder_path, images_path)

                    assert total_frames == 5

    def test_handles_folder_path_not_under_archive_dir(self):
        """Should handle folder paths not under ARCHIVE_DIR."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            folder_path = tmpdir_path / "input"
            images_path = tmpdir_path / "images"

            folder_path.mkdir()

            mock_cap = MagicMock()
            mock_cap.isOpened.return_value = True
            mock_cap.read.side_effect = [(False, None)]

            with patch("lab.converter.cv2.VideoCapture", return_value=mock_cap):
                with patch("lab.converter.cv2.imwrite"):
                    (folder_path / "video.ts").write_text("dummy")

                    # Folder path is not under ARCHIVE_DIR, so it should use just the folder name
                    convert_playlist_to_pngs(folder_path, images_path)

                    # Should create images folder with just the folder name
                    assert (images_path / "input").exists()


class TestConvertAllPlaylists:
    """Tests for convert_all_playlists function."""

    def test_returns_zero_when_no_unconverted_playlists(self):
        """Should return (0, 0) when there are no unconverted playlists."""
        with patch("lab.converter.get_unconverted_playlists") as mock_get_unconverted:
            mock_get_unconverted.return_value = []

            playlists_converted, total_frames = convert_all_playlists()

            assert playlists_converted == 0
            assert total_frames == 0

    def test_converts_all_unconverted_playlists(self):
        """Should convert all unconverted playlists."""
        with patch("lab.converter.get_unconverted_playlists") as mock_get_unconverted:
            with patch("lab.converter.convert_playlist_to_pngs") as mock_convert:
                with patch("lab.converter.ARCHIVE_DIR", Path("/archive")):
                    mock_get_unconverted.return_value = ["2024/01/15/playlist1", "2024/01/15/playlist2"]
                    mock_convert.return_value = 10

                    playlists_converted, total_frames = convert_all_playlists()

                    assert playlists_converted == 2
                    assert total_frames == 20
                    assert mock_convert.call_count == 2

    def test_calls_callbacks_with_progress(self):
        """Should call callbacks with progress information."""
        with patch("lab.converter.get_unconverted_playlists") as mock_get_unconverted:
            with patch("lab.converter.convert_playlist_to_pngs") as mock_convert:
                with patch("lab.converter.ARCHIVE_DIR", Path("/archive")):
                    mock_get_unconverted.return_value = ["2024/01/15/playlist1", "2024/01/15/playlist2"]
                    mock_convert.return_value = 10

                    playlist_callback = MagicMock()
                    file_callback = MagicMock()

                    playlists_converted, total_frames = convert_all_playlists(
                        on_playlist_progress=playlist_callback,
                        on_file_progress=file_callback,
                    )

                    # Should be called twice (once for each playlist)
                    assert playlist_callback.call_count == 2
                    # Check the arguments
                    calls = playlist_callback.call_args_list
                    assert calls[0][0] == (1, 2, "2024/01/15/playlist1")
                    assert calls[1][0] == (2, 2, "2024/01/15/playlist2")

    def test_accumulates_frames_from_multiple_playlists(self):
        """Should accumulate frame counts from multiple playlists."""
        with patch("lab.converter.get_unconverted_playlists") as mock_get_unconverted:
            with patch("lab.converter.convert_playlist_to_pngs") as mock_convert:
                with patch("lab.converter.ARCHIVE_DIR", Path("/archive")):
                    mock_get_unconverted.return_value = [
                        "2024/01/15/playlist1",
                        "2024/01/15/playlist2",
                        "2024/01/15/playlist3",
                    ]
                    # Different frame counts for each playlist
                    mock_convert.side_effect = [5, 10, 15]

                    playlists_converted, total_frames = convert_all_playlists()

                    assert playlists_converted == 3
                    assert total_frames == 30

    def test_passes_file_callback_to_convert_playlist(self):
        """Should pass file_callback to convert_playlist_to_pngs."""
        with patch("lab.converter.get_unconverted_playlists") as mock_get_unconverted:
            with patch("lab.converter.convert_playlist_to_pngs") as mock_convert:
                with patch("lab.converter.ARCHIVE_DIR", Path("/archive")):
                    mock_get_unconverted.return_value = ["2024/01/15/playlist1"]
                    mock_convert.return_value = 10

                    file_callback = MagicMock()

                    convert_all_playlists(on_file_progress=file_callback)

                    # Check that file_callback was passed to convert_playlist_to_pngs
                    mock_convert.assert_called_once()
                    call_kwargs = mock_convert.call_args[1]
                    assert call_kwargs["on_file_progress"] == file_callback
