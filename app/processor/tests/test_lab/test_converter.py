import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from lab.converter import convert_ts_frames_to_pngs, get_missing_archive_folders, main


class TestGetMissingArchiveFolders:
    """Tests for get_missing_archive_folders function."""

    def test_returns_folders_in_archive_but_not_in_images(self):
        """Should return folder names that exist in archive but not in images."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            archive_path = tmpdir_path / "archive"
            images_path = tmpdir_path / "images"

            archive_path.mkdir()
            images_path.mkdir()

            # Create folders in archive
            (archive_path / "folder1").mkdir()
            (archive_path / "folder2").mkdir()
            (archive_path / "folder3").mkdir()

            # Create folder in images
            (images_path / "folder1").mkdir()

            result = get_missing_archive_folders(archive_path, images_path)

            assert result == {"folder2", "folder3"}

    def test_returns_empty_set_when_all_folders_converted(self):
        """Should return empty set when all archive folders exist in images."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            archive_path = tmpdir_path / "archive"
            images_path = tmpdir_path / "images"

            archive_path.mkdir()
            images_path.mkdir()

            (archive_path / "folder1").mkdir()
            (images_path / "folder1").mkdir()

            result = get_missing_archive_folders(archive_path, images_path)

            assert result == set()

    def test_creates_images_directory_if_not_exists(self):
        """Should create images directory if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            archive_path = tmpdir_path / "archive"
            images_path = tmpdir_path / "images"

            archive_path.mkdir()
            assert not images_path.exists()

            get_missing_archive_folders(archive_path, images_path)

            assert images_path.exists()
            assert images_path.is_dir()

    def test_raises_file_not_found_error_when_archive_missing(self):
        """Should raise FileNotFoundError if archive directory doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            archive_path = tmpdir_path / "nonexistent"
            images_path = tmpdir_path / "images"

            with pytest.raises(FileNotFoundError) as excinfo:
                get_missing_archive_folders(archive_path, images_path)

            assert "Archive directory does not exist" in str(excinfo.value)
            assert str(archive_path) in str(excinfo.value)

    def test_raises_not_a_directory_error_when_archive_is_file(self):
        """Should raise NotADirectoryError if archive path is a file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            archive_path = tmpdir_path / "archive_file"
            images_path = tmpdir_path / "images"

            archive_path.write_text("content")

            with pytest.raises(NotADirectoryError) as excinfo:
                get_missing_archive_folders(archive_path, images_path)

            assert "Archive path is not a directory" in str(excinfo.value)
            assert str(archive_path) in str(excinfo.value)

    def test_ignores_files_in_archive_directory(self):
        """Should ignore files and only consider directories in archive."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            archive_path = tmpdir_path / "archive"
            images_path = tmpdir_path / "images"

            archive_path.mkdir()
            images_path.mkdir()

            (archive_path / "folder1").mkdir()
            (archive_path / "file.txt").write_text("content")

            result = get_missing_archive_folders(archive_path, images_path)

            assert result == {"folder1"}

    def test_ignores_files_in_images_directory(self):
        """Should ignore files and only consider directories in images."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            archive_path = tmpdir_path / "archive"
            images_path = tmpdir_path / "images"

            archive_path.mkdir()
            images_path.mkdir()

            (archive_path / "folder1").mkdir()
            (images_path / "file.txt").write_text("content")

            result = get_missing_archive_folders(archive_path, images_path)

            assert result == {"folder1"}


class TestConvertTsFramesToPngs:
    """Tests for convert_ts_frames_to_pngs function."""

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

                    convert_ts_frames_to_pngs(folder_path, images_path)

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

                    convert_ts_frames_to_pngs(folder_path, images_path)

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

                    convert_ts_frames_to_pngs(folder_path, images_path)

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

                    convert_ts_frames_to_pngs(folder_path, images_path)

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

                    convert_ts_frames_to_pngs(folder_path, images_path)

                    # Should be called twice (once for each file), in sorted order
                    assert mock_video_capture.call_count == 2
                    calls = mock_video_capture.call_args_list
                    assert "video1.ts" in calls[0][0][0]
                    assert "video2.ts" in calls[1][0][0]

    def test_prints_warning_when_no_ts_files_found(self, capsys):
        """Should print a warning when no .ts files are found."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            folder_path = tmpdir_path / "input"
            images_path = tmpdir_path / "images"

            folder_path.mkdir()

            convert_ts_frames_to_pngs(folder_path, images_path)

            captured = capsys.readouterr()
            assert "Warning: no .ts files found" in captured.out

    def test_prints_conversion_message(self, capsys):
        """Should print message with number of .ts files being converted."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            folder_path = tmpdir_path / "input"
            images_path = tmpdir_path / "images"

            folder_path.mkdir()

            mock_cap = MagicMock()
            mock_cap.isOpened.return_value = True
            mock_cap.read.side_effect = [(False, None)] * 10

            with patch("lab.converter.cv2.VideoCapture", return_value=mock_cap):
                with patch("lab.converter.cv2.imwrite"):
                    (folder_path / "video1.ts").write_text("dummy")
                    (folder_path / "video2.ts").write_text("dummy")

                    convert_ts_frames_to_pngs(folder_path, images_path)

                    captured = capsys.readouterr()
                    assert "Converting 2 .ts file(s) to .png file(s)" in captured.out

    def test_prints_warning_when_video_file_cannot_be_opened(self, capsys):
        """Should print warning and continue when a video file cannot be opened."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            folder_path = tmpdir_path / "input"
            images_path = tmpdir_path / "images"

            folder_path.mkdir()

            mock_cap = MagicMock()
            mock_cap.isOpened.return_value = False

            with patch("lab.converter.cv2.VideoCapture", return_value=mock_cap):
                (folder_path / "video.ts").write_text("dummy")

                convert_ts_frames_to_pngs(folder_path, images_path)

                captured = capsys.readouterr()
                assert "Warning: unable to open video file" in captured.out

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

                    convert_ts_frames_to_pngs(folder_path, images_path)

                    assert mock_cap.release.called

    def test_raises_file_not_found_error_when_folder_missing(self):
        """Should raise FileNotFoundError if folder doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            folder_path = tmpdir_path / "nonexistent"
            images_path = tmpdir_path / "images"

            with pytest.raises(FileNotFoundError) as excinfo:
                convert_ts_frames_to_pngs(folder_path, images_path)

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
                convert_ts_frames_to_pngs(folder_path, images_path)

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

                    convert_ts_frames_to_pngs(folder_path, images_path)

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

                    convert_ts_frames_to_pngs(folder_path, images_path)

                    assert images_path.exists()


class TestMain:
    """Tests for main function."""

    def test_main_converts_missing_folders(self):
        """Should convert all missing folders."""
        with patch("lab.converter.get_missing_archive_folders") as mock_get_missing:
            with patch("lab.converter.convert_ts_frames_to_pngs") as mock_convert:
                with patch("lab.converter.ARCHIVE_DIR", Path("/archive")):
                    mock_get_missing.return_value = {"folder1", "folder2"}

                    main()

                    assert mock_convert.call_count == 2

    def test_main_converts_folders_in_sorted_order(self):
        """Should convert folders in sorted order."""
        with patch("lab.converter.get_missing_archive_folders") as mock_get_missing:
            with patch("lab.converter.convert_ts_frames_to_pngs") as mock_convert:
                with patch("lab.converter.ARCHIVE_DIR", Path("/archive")):
                    mock_get_missing.return_value = {"folder2", "folder1", "folder3"}

                    main()

                    calls = mock_convert.call_args_list
                    assert "folder1" in str(calls[0])
                    assert "folder2" in str(calls[1])
                    assert "folder3" in str(calls[2])

    def test_main_prints_no_conversion_message_when_all_converted(self, capsys):
        """Should print message when all folders are already converted."""
        with patch("lab.converter.get_missing_archive_folders") as mock_get_missing:
            mock_get_missing.return_value = set()

            main()

            captured = capsys.readouterr()
            assert "All archive folders are already converted" in captured.out

    def test_main_prints_conversion_progress_for_each_folder(self, capsys):
        """Should print progress message for each folder being converted."""
        with patch("lab.converter.get_missing_archive_folders") as mock_get_missing:
            with patch("lab.converter.convert_ts_frames_to_pngs"):
                with patch("lab.converter.ARCHIVE_DIR", Path("/archive")):
                    mock_get_missing.return_value = {"folder1", "folder2"}

                    main()

                    captured = capsys.readouterr()
                    assert "Converting 1 of 2" in captured.out or "Converting 2 of 2" in captured.out

    def test_main_raises_exception_on_folder_failure(self):
        """Should raise exception if conversion of a folder fails."""
        with patch("lab.converter.get_missing_archive_folders") as mock_get_missing:
            with patch("lab.converter.convert_ts_frames_to_pngs") as mock_convert:
                with patch("lab.converter.ARCHIVE_DIR", Path("/archive")):
                    mock_get_missing.return_value = {"folder1"}
                    mock_convert.side_effect = ValueError("Test error")

                    with pytest.raises(ValueError):
                        main()

    def test_main_stops_on_first_error(self):
        """Should stop processing on first folder error."""
        with patch("lab.converter.get_missing_archive_folders") as mock_get_missing:
            with patch("lab.converter.convert_ts_frames_to_pngs") as mock_convert:
                with patch("lab.converter.ARCHIVE_DIR", Path("/archive")):
                    mock_get_missing.return_value = {"folder1", "folder2"}
                    mock_convert.side_effect = ValueError("Test error")

                    with pytest.raises(ValueError):
                        main()

                    # Should only be called once (first folder)
                    assert mock_convert.call_count == 1

    def test_main_prints_error_message_on_conversion_failure(self, capsys):
        """Should print error message when folder conversion fails."""
        with patch("lab.converter.get_missing_archive_folders") as mock_get_missing:
            with patch("lab.converter.convert_ts_frames_to_pngs") as mock_convert:
                with patch("lab.converter.ARCHIVE_DIR", Path("/archive")):
                    mock_get_missing.return_value = {"folder1"}
                    mock_convert.side_effect = ValueError("Test error")

                    with pytest.raises(ValueError):
                        main()

                    captured = capsys.readouterr()
                    assert "Error converting" in captured.out

    def test_main_continues_iteration_with_multiple_folders_before_error(self, capsys):
        """Should process folders sequentially and print progress even before error."""
        with patch("lab.converter.get_missing_archive_folders") as mock_get_missing:
            with patch("lab.converter.convert_ts_frames_to_pngs") as mock_convert:
                with patch("lab.converter.ARCHIVE_DIR", Path("/archive")):
                    mock_get_missing.return_value = {"folder1", "folder2", "folder3"}
                    # Fail on second folder
                    mock_convert.side_effect = [None, ValueError("Test error")]

                    with pytest.raises(ValueError):
                        main()

                    captured = capsys.readouterr()
                    # Should have printed for first and second folder
                    assert "Converting 1 of 3" in captured.out
                    assert "Converting 2 of 3" in captured.out
