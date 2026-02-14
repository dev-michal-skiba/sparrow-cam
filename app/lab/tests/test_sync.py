"""Tests for lab.sync module."""

from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import paramiko
import pytest

from lab.constants import ARCHIVE_DIR, REMOTE_ARCHIVE_PATH
from lab.sync import (
    ARCHIVE_FOLDER_PATTERN,
    DATE_FOLDER_PATTERN,
    FileToSync,
    SyncError,
    SyncManager,
    remove_hls_files,
    remove_recording,
)


class TestArchiveFolderPattern:
    """Tests for ARCHIVE_FOLDER_PATTERN regex."""

    def test_matches_folder_with_prefix(self):
        """Should match archive folder with prefix."""
        name = "auto_2026-01-15T06:45:57Z_5d83d036-3f12-4d9b-82f5-4d7eb1ab0d92"
        assert ARCHIVE_FOLDER_PATTERN.match(name)

    def test_matches_folder_without_prefix(self):
        """Should match archive folder without prefix."""
        name = "2026-01-15T06:45:57Z_5d83d036-3f12-4d9b-82f5-4d7eb1ab0d92"
        assert ARCHIVE_FOLDER_PATTERN.match(name)

    def test_does_not_match_invalid_format(self):
        """Should not match invalid folder format."""
        name = "invalid_folder_name"
        assert not ARCHIVE_FOLDER_PATTERN.match(name)

    def test_case_insensitive_match(self):
        """Should match folder names with uppercase UUID."""
        name = "AUTO_2026-01-15T06:45:57Z_5D83D036-3F12-4D9B-82F5-4D7EB1AB0D92"
        assert ARCHIVE_FOLDER_PATTERN.match(name)


class TestDateFolderPattern:
    """Tests for DATE_FOLDER_PATTERN regex."""

    def test_matches_numeric_folder(self):
        """Should match numeric folder names."""
        assert DATE_FOLDER_PATTERN.match("2024")
        assert DATE_FOLDER_PATTERN.match("01")
        assert DATE_FOLDER_PATTERN.match("15")

    def test_does_not_match_non_numeric(self):
        """Should not match non-numeric folder names."""
        assert not DATE_FOLDER_PATTERN.match("january")
        assert not DATE_FOLDER_PATTERN.match("2024a")


class TestFileToSync:
    """Tests for FileToSync class."""

    def test_init_stores_folder_and_filename(self):
        """Should store folder and filename."""
        file = FileToSync("2024/01/15/playlist1", "video.ts")
        assert file.folder == "2024/01/15/playlist1"
        assert file.filename == "video.ts"

    def test_remote_path_property(self):
        """Should construct remote path correctly."""
        file = FileToSync("2024/01/15/playlist1", "video.ts")
        expected = f"{REMOTE_ARCHIVE_PATH}/2024/01/15/playlist1/video.ts"
        assert file.remote_path == expected

    def test_local_path_property(self):
        """Should construct local path correctly."""
        file = FileToSync("2024/01/15/playlist1", "video.ts")
        expected = ARCHIVE_DIR / "2024/01/15/playlist1" / "video.ts"
        assert file.local_path == expected

    def test_repr(self):
        """Should have useful string representation."""
        file = FileToSync("2024/01/15/playlist1", "video.ts")
        assert repr(file) == "FileToSync(2024/01/15/playlist1/video.ts)"


class TestSyncManager:
    """Tests for SyncManager class."""

    def test_init(self):
        """Should initialize with no connection."""
        manager = SyncManager()
        assert manager._sftp is None
        assert manager._transport is None
        assert manager._host == ""
        assert manager._user == ""

    def test_load_config_success(self):
        """Should load config successfully."""
        config_yaml = "ansible_target_host: 192.168.1.100\nansible_target_user: pi\n"

        with patch("lab.sync.CONFIG_PATH") as mock_config_path:
            mock_config_path.exists.return_value = True
            with patch("builtins.open", mock_open(read_data=config_yaml)):
                manager = SyncManager()
                host, user = manager._load_config()

                assert host == "192.168.1.100"
                assert user == "pi"

    def test_load_config_missing_file(self):
        """Should raise SyncError when config file is missing."""
        with patch("lab.sync.CONFIG_PATH") as mock_config_path:
            mock_config_path.exists.return_value = False
            manager = SyncManager()

            with pytest.raises(SyncError) as excinfo:
                manager._load_config()

            assert "Config file not found" in str(excinfo.value)

    def test_load_config_missing_host(self):
        """Should raise SyncError when host is missing from config."""
        config_yaml = "ansible_target_user: pi\n"

        with patch("lab.sync.CONFIG_PATH") as mock_config_path:
            mock_config_path.exists.return_value = True
            with patch("builtins.open", mock_open(read_data=config_yaml)):
                manager = SyncManager()

                with pytest.raises(SyncError) as excinfo:
                    manager._load_config()

                assert "Missing ansible_target_host" in str(excinfo.value)

    def test_load_config_missing_user(self):
        """Should raise SyncError when user is missing from config."""
        config_yaml = "ansible_target_host: 192.168.1.100\n"

        with patch("lab.sync.CONFIG_PATH") as mock_config_path:
            mock_config_path.exists.return_value = True
            with patch("builtins.open", mock_open(read_data=config_yaml)):
                manager = SyncManager()

                with pytest.raises(SyncError) as excinfo:
                    manager._load_config()

                assert "Missing ansible_target_host or ansible_target_user" in str(excinfo.value)

    def test_disconnect_with_no_connection(self):
        """Should handle disconnect with no connection gracefully."""
        manager = SyncManager()
        manager.disconnect()
        assert manager._sftp is None
        assert manager._transport is None

    def test_disconnect_closes_sftp(self):
        """Should close SFTP connection."""
        manager = SyncManager()
        mock_sftp = MagicMock()
        manager._sftp = mock_sftp

        manager.disconnect()

        mock_sftp.close.assert_called_once()
        assert manager._sftp is None

    def test_disconnect_closes_transport(self):
        """Should close transport connection."""
        manager = SyncManager()
        mock_transport = MagicMock()
        manager._transport = mock_transport

        manager.disconnect()

        mock_transport.close.assert_called_once()
        assert manager._transport is None

    def test_is_dir_not_connected(self):
        """Should raise SyncError when not connected."""
        manager = SyncManager()

        with pytest.raises(SyncError) as excinfo:
            manager._is_dir("/some/path")

        assert "Not connected" in str(excinfo.value)

    def test_is_dir_directory(self):
        """Should identify directories correctly."""
        manager = SyncManager()
        mock_sftp = MagicMock()
        manager._sftp = mock_sftp

        # Mock stat result for a directory (mode & 0o40000 != 0)
        mock_stat = MagicMock()
        mock_stat.st_mode = 0o40755  # Directory with permissions
        mock_sftp.stat.return_value = mock_stat

        result = manager._is_dir("/some/path")

        assert result is True

    def test_is_dir_file(self):
        """Should identify files correctly."""
        manager = SyncManager()
        mock_sftp = MagicMock()
        manager._sftp = mock_sftp

        # Mock stat result for a file (mode & 0o40000 == 0)
        mock_stat = MagicMock()
        mock_stat.st_mode = 0o100644  # Regular file
        mock_sftp.stat.return_value = mock_stat

        result = manager._is_dir("/some/path")

        assert result is False

    def test_is_dir_path_not_found(self):
        """Should return False when path is not found."""
        manager = SyncManager()
        mock_sftp = MagicMock()
        manager._sftp = mock_sftp
        mock_sftp.stat.side_effect = OSError("File not found")

        result = manager._is_dir("/nonexistent/path")

        assert result is False

    def test_connect_ssh_key_not_found(self):
        """Should raise SyncError when SSH key is not found."""
        with patch("lab.sync.SSH_KEY_PATH") as mock_key_path:
            mock_key_path.exists.return_value = False
            manager = SyncManager()

            with pytest.raises(SyncError) as excinfo:
                manager.connect()

            assert "SSH key not found" in str(excinfo.value)

    def test_connect_invalid_ssh_key(self):
        """Should raise SyncError when SSH key is invalid."""
        with patch("lab.sync.SSH_KEY_PATH") as mock_key_path:
            mock_key_path.exists.return_value = True
            with patch("lab.sync.paramiko.Ed25519Key.from_private_key_file") as mock_ed25519:
                mock_ed25519.side_effect = paramiko.SSHException("Invalid key")
                with patch("lab.sync.paramiko.RSAKey.from_private_key_file") as mock_rsa:
                    mock_rsa.side_effect = paramiko.SSHException("Invalid key")
                    with patch("lab.sync.CONFIG_PATH") as mock_config_path:
                        mock_config_path.exists.return_value = True
                        with patch(
                            "builtins.open",
                            mock_open(read_data="ansible_target_host: host\nansible_target_user: user\n"),
                        ):
                            manager = SyncManager()

                            with pytest.raises(SyncError) as excinfo:
                                manager.connect()

                            assert "Failed to load SSH key" in str(excinfo.value)

    def test_connect_connection_failed(self):
        """Should raise SyncError when connection fails."""
        with patch("lab.sync.SSH_KEY_PATH") as mock_key_path:
            mock_key_path.exists.return_value = True
            with patch("lab.sync.paramiko.Ed25519Key.from_private_key_file"):
                with patch("lab.sync.paramiko.Transport") as mock_transport:
                    mock_transport.return_value.connect.side_effect = Exception("Connection refused")
                    with patch("lab.sync.CONFIG_PATH") as mock_config_path:
                        mock_config_path.exists.return_value = True
                        with patch(
                            "builtins.open",
                            mock_open(read_data="ansible_target_host: host\nansible_target_user: user\n"),
                        ):
                            manager = SyncManager()

                            with pytest.raises(SyncError) as excinfo:
                                manager.connect()

                            assert "Failed to connect" in str(excinfo.value)

    def test_connect_success(self):
        """Should establish connection successfully."""
        with patch("lab.sync.SSH_KEY_PATH") as mock_key_path:
            mock_key_path.exists.return_value = True
            with patch("lab.sync.paramiko.Ed25519Key.from_private_key_file") as mock_ed25519:
                with patch("lab.sync.socket.create_connection") as mock_socket:
                    with patch("lab.sync.paramiko.Transport") as mock_transport_class:
                        with patch("lab.sync.paramiko.SFTPClient.from_transport") as mock_sftp_from_transport:
                            with patch("lab.sync.CONFIG_PATH") as mock_config_path:
                                mock_config_path.exists.return_value = True

                                # Setup mocks
                                mock_pkey = MagicMock()
                                mock_ed25519.return_value = mock_pkey
                                mock_sock = MagicMock()
                                mock_socket.return_value = mock_sock
                                mock_transport = MagicMock()
                                mock_transport_class.return_value = mock_transport
                                mock_sftp = MagicMock()
                                mock_sftp_from_transport.return_value = mock_sftp
                                mock_channel = MagicMock()
                                mock_sftp.get_channel.return_value = mock_channel

                                with patch(
                                    "builtins.open",
                                    mock_open(
                                        read_data="ansible_target_host: testhost\nansible_target_user: testuser\n"
                                    ),
                                ):
                                    manager = SyncManager()
                                    manager.connect()

                                    # Verify connection was established
                                    assert manager._sftp == mock_sftp
                                    assert manager._transport == mock_transport
                                    assert manager._socket == mock_sock
                                    assert manager._host == "testhost"
                                    assert manager._user == "testuser"

    def test_list_remote_archive_folders_not_connected(self):
        """Should raise SyncError when not connected."""
        manager = SyncManager()

        with pytest.raises(SyncError) as excinfo:
            manager._list_remote_archive_folders()

        assert "Not connected" in str(excinfo.value)

    def test_list_remote_archive_folders_cannot_list(self):
        """Should raise SyncError when cannot list remote archive."""
        manager = SyncManager()
        mock_sftp = MagicMock()
        manager._sftp = mock_sftp
        mock_sftp.listdir.side_effect = OSError("Permission denied")

        with pytest.raises(SyncError) as excinfo:
            manager._list_remote_archive_folders()

        assert "Cannot list remote archive" in str(excinfo.value)

    def test_list_remote_archive_folders_success(self):
        """Should list remote archive folders successfully."""
        manager = SyncManager()
        mock_sftp = MagicMock()
        manager._sftp = mock_sftp

        # Mock the nested directory structure
        mock_sftp.listdir.side_effect = [
            ["2024"],  # years
            ["01"],  # months in 2024
            ["15"],  # days in 01/2024
            [  # folders in 15/01/2024
                "auto_2024-01-15T06:45:57Z_5d83d036-3f12-4d9b-82f5-4d7eb1ab0d92",
                "sync_2024-01-15T12:30:00Z_1a2b3c4d-5e6f-4d9b-82f5-1a2b3c4d5e6f",
            ],
        ]

        # Mock _is_dir to return True for directories
        manager._is_dir = MagicMock(return_value=True)

        folders = manager._list_remote_archive_folders()

        assert len(folders) == 2
        assert "2024/01/15/auto_2024-01-15T06:45:57Z_5d83d036-3f12-4d9b-82f5-4d7eb1ab0d92" in folders
        assert "2024/01/15/sync_2024-01-15T12:30:00Z_1a2b3c4d-5e6f-4d9b-82f5-1a2b3c4d5e6f" in folders

    def test_list_remote_archive_folders_filters_non_numeric(self):
        """Should filter out non-numeric year/month/day folders."""
        manager = SyncManager()
        mock_sftp = MagicMock()
        manager._sftp = mock_sftp

        # Mock with some non-numeric directories
        mock_sftp.listdir.side_effect = [
            ["2024", "backup"],  # "backup" should be filtered
            ["01", "february"],  # "february" should be filtered
            ["15"],  # valid day
            ["2024-01-15T06:45:57Z_5d83d036-3f12-4d9b-82f5-4d7eb1ab0d92"],
        ]

        manager._is_dir = MagicMock(return_value=True)

        folders = manager._list_remote_archive_folders()

        # Should only include valid path
        assert len(folders) == 1
        assert "2024/01/15/2024-01-15T06:45:57Z_5d83d036-3f12-4d9b-82f5-4d7eb1ab0d92" in folders

    def test_list_remote_archive_folders_filters_non_archives(self):
        """Should filter out folders that don't match archive pattern."""
        manager = SyncManager()
        mock_sftp = MagicMock()
        manager._sftp = mock_sftp

        # Mock with valid directory structure but invalid archive folder names
        mock_sftp.listdir.side_effect = [
            ["2024"],
            ["01"],
            ["15"],
            ["not_an_archive", "2024-01-15T06:45:57Z_5d83d036-3f12-4d9b-82f5-4d7eb1ab0d92"],
        ]

        manager._is_dir = MagicMock(return_value=True)

        folders = manager._list_remote_archive_folders()

        # Should only include valid archive folder
        assert len(folders) == 1
        assert "2024/01/15/2024-01-15T06:45:57Z_5d83d036-3f12-4d9b-82f5-4d7eb1ab0d92" in folders

    def test_list_remote_archive_folders_skips_files(self):
        """Should skip files and only process directories."""
        manager = SyncManager()
        mock_sftp = MagicMock()
        manager._sftp = mock_sftp

        mock_sftp.listdir.side_effect = [
            ["2024"],
            ["01"],
            ["15"],
            ["2024-01-15T06:45:57Z_5d83d036-3f12-4d9b-82f5-4d7eb1ab0d92", "readme.txt"],
        ]

        # Mock _is_dir to return True for archive, False for readme.txt
        def is_dir_side_effect(path):
            return "readme.txt" not in path

        manager._is_dir = MagicMock(side_effect=is_dir_side_effect)

        folders = manager._list_remote_archive_folders()

        # Should only include directory, not file
        assert len(folders) == 1
        assert "2024/01/15/2024-01-15T06:45:57Z_5d83d036-3f12-4d9b-82f5-4d7eb1ab0d92" in folders

    def test_get_files_to_sync_not_connected(self):
        """Should raise SyncError when not connected."""
        manager = SyncManager()

        with pytest.raises(SyncError) as excinfo:
            manager._get_files_to_sync("2024/01/15/playlist1")

        assert "Not connected" in str(excinfo.value)

    def test_get_files_to_sync_returns_ts_and_m3u8_files(self):
        """Should return .ts and .m3u8 files only."""
        manager = SyncManager()
        mock_sftp = MagicMock()
        manager._sftp = mock_sftp

        mock_sftp.listdir.return_value = [
            "video.ts",
            "playlist.m3u8",
            "readme.txt",
            "index.html",
            "segment1.ts",
        ]

        files = manager._get_files_to_sync("2024/01/15/playlist1")

        assert len(files) == 3
        assert "video.ts" in files
        assert "playlist.m3u8" in files
        assert "segment1.ts" in files
        assert "readme.txt" not in files

    def test_get_files_to_sync_handles_error(self):
        """Should return empty list when listdir fails."""
        manager = SyncManager()
        mock_sftp = MagicMock()
        manager._sftp = mock_sftp
        mock_sftp.listdir.side_effect = OSError("Permission denied")

        files = manager._get_files_to_sync("2024/01/15/playlist1")

        assert files == []

    def test_get_missing_folders(self):
        """Should find folders that don't exist locally."""
        manager = SyncManager()

        # Setup list_remote_archive_folders to return two folders
        with patch.object(manager, "_list_remote_archive_folders") as mock_list:
            mock_list.return_value = [
                "2024/01/15/playlist1",
                "2024/01/16/playlist2",
            ]

            # Mock Path objects: playlist1 exists, playlist2 doesn't
            mock_path1 = MagicMock()
            mock_path1.exists.return_value = True

            mock_path2 = MagicMock()
            mock_path2.exists.return_value = False

            with patch("lab.sync.ARCHIVE_DIR") as mock_archive_dir:
                mock_archive_dir.__truediv__.side_effect = [mock_path1, mock_path2]

                missing = manager.get_missing_folders()

                assert len(missing) == 1
                assert "2024/01/16/playlist2" in missing

    def test_sync_folder_not_connected(self):
        """Should raise SyncError when not connected."""
        manager = SyncManager()

        with pytest.raises(SyncError) as excinfo:
            manager.sync_folder("2024/01/15/playlist1")

        assert "Not connected" in str(excinfo.value)

    def test_sync_folder_no_files(self):
        """Should return 0 when no files to sync."""
        manager = SyncManager()
        mock_sftp = MagicMock()
        manager._sftp = mock_sftp

        with patch.object(manager, "_get_files_to_sync") as mock_get_files:
            mock_get_files.return_value = []

            files_synced = manager.sync_folder("2024/01/15/playlist1")

            assert files_synced == 0

    def test_sync_folder_calls_callback(self):
        """Should call progress callback for each file."""
        manager = SyncManager()
        mock_sftp = MagicMock()
        manager._sftp = mock_sftp

        progress_callback = MagicMock()

        with patch.object(manager, "_get_files_to_sync") as mock_get_files:
            mock_get_files.return_value = ["video1.ts", "video2.ts"]
            with patch("lab.sync.ARCHIVE_DIR") as mock_archive_dir:
                mock_local_folder = MagicMock()
                mock_archive_dir.__truediv__.return_value = mock_local_folder

                files_synced = manager.sync_folder(
                    "2024/01/15/playlist1",
                    on_file_progress=progress_callback,
                )

                assert files_synced == 2
                assert progress_callback.call_count == 2

    def test_sync_folder_download_failure(self):
        """Should raise SyncError when download fails."""
        manager = SyncManager()
        mock_sftp = MagicMock()
        manager._sftp = mock_sftp
        mock_sftp.get.side_effect = OSError("Connection lost")

        with patch.object(manager, "_get_files_to_sync") as mock_get_files:
            mock_get_files.return_value = ["video.ts"]
            with patch("lab.sync.ARCHIVE_DIR") as mock_archive_dir:
                mock_local_folder = MagicMock()
                mock_archive_dir.__truediv__.return_value = mock_local_folder

                with pytest.raises(SyncError) as excinfo:
                    manager.sync_folder("2024/01/15/playlist1")

                assert "Failed to download" in str(excinfo.value)

    def test_gather_files_to_sync(self):
        """Should gather all files to sync from missing folders."""
        manager = SyncManager()

        with patch.object(manager, "get_missing_folders") as mock_get_missing:
            with patch.object(manager, "_get_files_to_sync") as mock_get_files:
                mock_get_missing.return_value = ["2024/01/15/playlist1", "2024/01/16/playlist2"]

                def get_files_side_effect(folder):
                    if "playlist1" in folder:
                        return ["video1.ts", "playlist.m3u8"]
                    else:
                        return ["video2.ts"]

                mock_get_files.side_effect = get_files_side_effect

                files = manager._gather_files_to_sync()

                assert len(files) == 3
                assert any(f.filename == "video1.ts" for f in files)
                assert any(f.filename == "video2.ts" for f in files)
                assert any(f.filename == "playlist.m3u8" for f in files)

    def test_reconnect(self):
        """Should disconnect and reconnect to server."""
        manager = SyncManager()

        with patch.object(manager, "disconnect") as mock_disconnect:
            with patch.object(manager, "connect") as mock_connect:
                with patch("builtins.print"):
                    manager._reconnect()

                    mock_disconnect.assert_called_once()
                    mock_connect.assert_called_once()

    def test_download_file_with_retry_success(self):
        """Should successfully download file on first attempt."""
        manager = SyncManager()
        mock_sftp = MagicMock()
        manager._sftp = mock_sftp

        file = FileToSync("2024/01/15/playlist1", "video.ts")

        with patch("lab.sync.ARCHIVE_DIR") as mock_archive_dir:
            mock_local_path = MagicMock()
            mock_local_path.parent = MagicMock()
            mock_archive_dir.__truediv__.return_value = mock_local_path

            manager._download_file_with_retry(file)

            assert mock_sftp.get.called

    def test_download_file_with_retry_fails_and_reconnects(self):
        """Should reconnect and retry on download failure."""
        manager = SyncManager()
        mock_sftp = MagicMock()
        manager._sftp = mock_sftp

        # First call fails, second succeeds
        mock_sftp.get.side_effect = [Exception("Connection lost"), None]

        file = FileToSync("2024/01/15/playlist1", "video.ts")

        with patch("lab.sync.ARCHIVE_DIR") as mock_archive_dir:
            mock_local_path = MagicMock()
            mock_local_path.parent = MagicMock()
            mock_archive_dir.__truediv__.return_value = mock_local_path

            with patch.object(manager, "_reconnect") as mock_reconnect:
                # After reconnect, update sftp
                def reconnect_side_effect():
                    manager._sftp = mock_sftp

                mock_reconnect.side_effect = reconnect_side_effect

                manager._download_file_with_retry(file)

                mock_reconnect.assert_called_once()
                assert mock_sftp.get.call_count == 2

    def test_sync_all_no_files(self):
        """Should return empty result when no files to sync."""
        manager = SyncManager()

        with patch.object(manager, "_gather_files_to_sync") as mock_gather:
            mock_gather.return_value = []

            synced_folders, total_files = manager.sync_all()

            assert synced_folders == []
            assert total_files == 0

    def test_sync_all_with_files(self):
        """Should sync multiple files and return results."""
        manager = SyncManager()

        with patch.object(manager, "_gather_files_to_sync") as mock_gather:
            with patch.object(manager, "_download_file_with_retry") as mock_download:
                files_to_sync = [
                    FileToSync("2024/01/15/playlist1", "video1.ts"),
                    FileToSync("2024/01/15/playlist1", "video2.ts"),
                    FileToSync("2024/01/16/playlist2", "video3.ts"),
                ]
                mock_gather.return_value = files_to_sync

                synced_folders, total_files = manager.sync_all()

                assert len(synced_folders) == 2
                assert "2024/01/15/playlist1" in synced_folders
                assert "2024/01/16/playlist2" in synced_folders
                assert total_files == 3
                assert mock_download.call_count == 3

    def test_sync_all_calls_folder_callback(self):
        """Should call folder_start callback for each new folder."""
        manager = SyncManager()
        folder_callback = MagicMock()

        with patch.object(manager, "_gather_files_to_sync") as mock_gather:
            with patch.object(manager, "_download_file_with_retry"):
                files_to_sync = [
                    FileToSync("2024/01/15/playlist1", "video1.ts"),
                    FileToSync("2024/01/15/playlist1", "video2.ts"),
                    FileToSync("2024/01/16/playlist2", "video3.ts"),
                ]
                mock_gather.return_value = files_to_sync

                manager.sync_all(on_folder_start=folder_callback)

                assert folder_callback.call_count == 2
                calls = folder_callback.call_args_list
                assert calls[0][0][0] == "2024/01/15/playlist1"
                assert calls[1][0][0] == "2024/01/16/playlist2"

    def test_context_manager(self):
        """Should work as context manager for connection."""
        with patch.object(SyncManager, "connect") as mock_connect:
            with patch.object(SyncManager, "disconnect") as mock_disconnect:
                with SyncManager() as manager:
                    assert manager is not None

                mock_connect.assert_called_once()
                mock_disconnect.assert_called_once()

    def test_list_remote_archive_folders_handles_listdir_errors(self):
        """Should continue on listdir errors in nested directories."""
        manager = SyncManager()
        mock_sftp = MagicMock()
        manager._sftp = mock_sftp

        # First listdir call (years) succeeds, month listdir fails
        mock_sftp.listdir.side_effect = [
            ["2024"],  # years - success
            OSError("Permission denied"),  # months - fail
        ]

        manager._is_dir = MagicMock(return_value=True)

        folders = manager._list_remote_archive_folders()

        # Should handle error gracefully and return empty list
        assert folders == []

    def test_list_remote_archive_folders_skips_non_dirs_at_year_level(self):
        """Should skip non-directory entries at year level."""
        manager = SyncManager()
        mock_sftp = MagicMock()
        manager._sftp = mock_sftp

        mock_sftp.listdir.side_effect = [
            ["2024"],  # years
        ]

        # _is_dir returns False for year_path to skip it
        manager._is_dir = MagicMock(return_value=False)

        folders = manager._list_remote_archive_folders()

        assert folders == []

    def test_sync_all_calls_download_progress_callback(self):
        """Should call download_progress callback for each file."""
        manager = SyncManager()
        progress_callback = MagicMock()

        with patch.object(manager, "_gather_files_to_sync") as mock_gather:
            with patch.object(manager, "_download_file_with_retry"):
                files_to_sync = [
                    FileToSync("2024/01/15/playlist1", "video1.ts"),
                    FileToSync("2024/01/15/playlist1", "video2.ts"),
                ]
                mock_gather.return_value = files_to_sync

                manager.sync_all(on_download_progress=progress_callback)

                assert progress_callback.call_count == 2
                calls = progress_callback.call_args_list
                assert calls[0][0] == (1, 2, "video1.ts")
                assert calls[1][0] == (2, 2, "video2.ts")


class TestRemoteRemovalMethods:
    """Tests for remote folder removal functionality."""

    def test_remove_remote_folder_recursive_not_connected(self):
        """Should raise SyncError when not connected."""
        manager = SyncManager()

        with pytest.raises(SyncError) as excinfo:
            manager._remove_remote_folder_recursive("/remote/path")

        assert "Not connected" in str(excinfo.value)

    def test_remove_remote_folder_recursive_single_file(self):
        """Should remove a single file in a folder."""
        manager = SyncManager()
        mock_sftp = MagicMock()
        manager._sftp = mock_sftp

        # Mock listdir_attr to return one file
        mock_attr = MagicMock()
        mock_attr.filename = "file.txt"
        mock_attr.st_mode = 0o100644  # Regular file
        mock_sftp.listdir_attr.return_value = [mock_attr]

        manager._remove_remote_folder_recursive("/remote/path")

        mock_sftp.remove.assert_called_once_with("/remote/path/file.txt")
        mock_sftp.rmdir.assert_called_once_with("/remote/path")

    def test_remove_remote_folder_recursive_with_subdirectory(self):
        """Should recursively remove folders and files."""
        manager = SyncManager()
        mock_sftp = MagicMock()
        manager._sftp = mock_sftp

        # First call returns a subdirectory
        subdir_attr = MagicMock()
        subdir_attr.filename = "subdir"
        subdir_attr.st_mode = 0o40755  # Directory

        # Second call returns a file in the subdirectory
        file_attr = MagicMock()
        file_attr.filename = "file.txt"
        file_attr.st_mode = 0o100644  # Regular file

        mock_sftp.listdir_attr.side_effect = [
            [subdir_attr],  # Root has subdirectory
            [file_attr],  # Subdirectory has file
        ]

        manager._remove_remote_folder_recursive("/remote/path")

        # Should remove file, rmdir subdir, then rmdir root
        assert mock_sftp.remove.call_count == 1
        assert mock_sftp.rmdir.call_count == 2

    def test_remove_remote_folder_recursive_handles_os_error(self):
        """Should raise SyncError on OS error."""
        manager = SyncManager()
        mock_sftp = MagicMock()
        manager._sftp = mock_sftp
        mock_sftp.listdir_attr.side_effect = OSError("Permission denied")

        with pytest.raises(SyncError) as excinfo:
            manager._remove_remote_folder_recursive("/remote/path")

        assert "Failed to remove remote folder" in str(excinfo.value)

    def test_remove_remote_folder_not_connected(self):
        """Should raise SyncError when not connected."""
        manager = SyncManager()

        with pytest.raises(SyncError) as excinfo:
            manager.remove_remote_folder("2024/01/15/playlist1")

        assert "Not connected" in str(excinfo.value)

    def test_remove_remote_folder_folder_not_found(self):
        """Should raise SyncError when folder doesn't exist."""
        manager = SyncManager()
        mock_sftp = MagicMock()
        manager._sftp = mock_sftp

        with patch.object(manager, "_is_dir", return_value=False):
            with pytest.raises(SyncError) as excinfo:
                manager.remove_remote_folder("2024/01/15/playlist1")

            assert "Remote folder does not exist" in str(excinfo.value)

    def test_remove_remote_folder_success(self):
        """Should remove remote folder successfully."""
        manager = SyncManager()
        mock_sftp = MagicMock()
        manager._sftp = mock_sftp

        with patch.object(manager, "_is_dir", return_value=True):
            with patch.object(manager, "_remove_remote_folder_recursive") as mock_recursive:
                manager.remove_remote_folder("2024/01/15/playlist1")

                mock_recursive.assert_called_once()
                # Should be called with full path
                call_args = mock_recursive.call_args[0][0]
                assert "2024/01/15/playlist1" in call_args
                assert call_args.startswith(REMOTE_ARCHIVE_PATH)


class TestRemoveRecording:
    """Tests for remove_recording function."""

    def test_remove_recording_remote_fails(self):
        """Should raise SyncError if remote removal fails without local deletion."""
        relative_path = "2026/01/15/auto_2026-01-15T06:45:57Z_uuid"

        with patch("lab.sync.SyncManager") as mock_sync_class:
            mock_sync_instance = MagicMock()
            mock_sync_class.return_value.__enter__.return_value = mock_sync_instance
            mock_sync_instance.remove_remote_folder.side_effect = SyncError("Remote deletion failed")

            with pytest.raises(SyncError) as excinfo:
                remove_recording(relative_path)

            assert "Remote deletion failed" in str(excinfo.value)

    def test_remove_recording_removes_archive_locally(self):
        """Should remove local archive folder after remote removal."""
        relative_path = "2026/01/15/auto_2026-01-15T06:45:57Z_uuid"

        with patch("lab.sync.SyncManager") as mock_sync_class:
            mock_sync_instance = MagicMock()
            mock_sync_class.return_value.__enter__.return_value = mock_sync_instance

            with patch("lab.sync.shutil.rmtree") as mock_rmtree:
                with patch.object(Path, "exists", return_value=True):
                    remove_recording(relative_path)

                    # Should call rmtree for both archive and images
                    assert mock_rmtree.call_count == 2

    def test_remove_recording_removes_images_locally(self):
        """Should remove local images folder after remote removal."""
        relative_path = "2026/01/15/auto_2026-01-15T06:45:57Z_uuid"

        with patch("lab.sync.SyncManager") as mock_sync_class:
            mock_sync_instance = MagicMock()
            mock_sync_class.return_value.__enter__.return_value = mock_sync_instance

            with patch("lab.sync.shutil.rmtree") as mock_rmtree:
                with patch.object(Path, "exists", return_value=True):
                    remove_recording(relative_path)

                    # Should attempt to remove both paths
                    called_paths = [call[0][0] for call in mock_rmtree.call_args_list]
                    assert len(called_paths) == 2

    def test_remove_recording_skips_nonexistent_local_paths(self):
        """Should gracefully skip removal if local paths don't exist."""
        relative_path = "2026/01/15/auto_2026-01-15T06:45:57Z_uuid"

        with patch("lab.sync.SyncManager") as mock_sync_class:
            mock_sync_instance = MagicMock()
            mock_sync_class.return_value.__enter__.return_value = mock_sync_instance

            with patch("lab.sync.shutil.rmtree") as mock_rmtree:
                with patch.object(Path, "exists", return_value=False):
                    # Should not raise, even if local paths don't exist
                    remove_recording(relative_path)

                    # rmtree should never be called since paths don't exist
                    mock_rmtree.assert_not_called()

    def test_remove_recording_calls_sync_manager_as_context(self):
        """Should use SyncManager as context manager."""
        relative_path = "2026/01/15/auto_2026-01-15T06:45:57Z_uuid"

        with patch("lab.sync.SyncManager") as mock_sync_class:
            mock_sync_instance = MagicMock()
            mock_sync_class.return_value.__enter__ = MagicMock(return_value=mock_sync_instance)
            mock_sync_class.return_value.__exit__ = MagicMock(return_value=None)

            with patch.object(Path, "exists", return_value=False):
                remove_recording(relative_path)

                # Should enter and exit context
                mock_sync_class.return_value.__enter__.assert_called_once()
                mock_sync_class.return_value.__exit__.assert_called_once()

    def test_remove_recording_sequence(self):
        """Should remove remote first, then local archive, then images."""
        relative_path = "2026/01/15/auto_2026-01-15T06:45:57Z_uuid"
        call_sequence = []

        with patch("lab.sync.SyncManager") as mock_sync_class:
            mock_sync_instance = MagicMock()
            mock_sync_class.return_value.__enter__.return_value = mock_sync_instance

            def track_remove_remote(path):
                call_sequence.append(("remove_remote", path))

            mock_sync_instance.remove_remote_folder.side_effect = track_remove_remote

            with patch("lab.sync.shutil.rmtree") as mock_rmtree:

                def track_rmtree(path):
                    call_sequence.append(("rmtree", str(path)))

                mock_rmtree.side_effect = track_rmtree

                with patch.object(Path, "exists", return_value=True):
                    remove_recording(relative_path)

                    # First call should be remove_remote
                    assert call_sequence[0][0] == "remove_remote"
                    # Then local operations
                    assert call_sequence[1][0] == "rmtree"
                    assert call_sequence[2][0] == "rmtree"


class TestSyncSingleFolder:
    """Tests for sync_single_folder method."""

    def test_sync_single_folder_no_files(self):
        """Should return 0 when no files to sync."""
        manager = SyncManager()
        folder = "2024/01/15/playlist1"

        with patch.object(manager, "_get_files_to_sync") as mock_get_files:
            mock_get_files.return_value = []

            result = manager.sync_single_folder(folder)

            assert result == 0
            mock_get_files.assert_called_once_with(folder)

    def test_sync_single_folder_with_files(self):
        """Should download all files from folder and return count."""
        manager = SyncManager()
        folder = "2024/01/15/playlist1"

        with patch.object(manager, "_get_files_to_sync") as mock_get_files:
            with patch.object(manager, "_download_file_with_retry") as mock_download:
                mock_get_files.return_value = ["video1.ts", "video2.ts", "video3.ts"]

                result = manager.sync_single_folder(folder)

                assert result == 3
                assert mock_download.call_count == 3
                # Verify the files were created correctly
                calls = mock_download.call_args_list
                assert calls[0][0][0].folder == folder
                assert calls[0][0][0].filename == "video1.ts"
                assert calls[1][0][0].folder == folder
                assert calls[1][0][0].filename == "video2.ts"
                assert calls[2][0][0].folder == folder
                assert calls[2][0][0].filename == "video3.ts"

    def test_sync_single_folder_calls_progress_callback(self):
        """Should call progress callback for each file."""
        manager = SyncManager()
        folder = "2024/01/15/playlist1"
        progress_callback = MagicMock()

        with patch.object(manager, "_get_files_to_sync") as mock_get_files:
            with patch.object(manager, "_download_file_with_retry"):
                mock_get_files.return_value = ["video1.ts", "video2.ts"]

                manager.sync_single_folder(folder, on_file_progress=progress_callback)

                assert progress_callback.call_count == 2
                calls = progress_callback.call_args_list
                assert calls[0][0] == (1, 2, "video1.ts")
                assert calls[1][0] == (2, 2, "video2.ts")

    def test_sync_single_folder_no_callback(self):
        """Should work without progress callback."""
        manager = SyncManager()
        folder = "2024/01/15/playlist1"

        with patch.object(manager, "_get_files_to_sync") as mock_get_files:
            with patch.object(manager, "_download_file_with_retry"):
                mock_get_files.return_value = ["video1.ts"]

                result = manager.sync_single_folder(folder, on_file_progress=None)

                assert result == 1

    def test_sync_single_folder_propagates_sync_error(self):
        """Should propagate SyncError from download."""
        manager = SyncManager()
        folder = "2024/01/15/playlist1"

        with patch.object(manager, "_get_files_to_sync") as mock_get_files:
            with patch.object(manager, "_download_file_with_retry") as mock_download:
                mock_get_files.return_value = ["video1.ts"]
                mock_download.side_effect = SyncError("Download failed")

                with pytest.raises(SyncError, match="Download failed"):
                    manager.sync_single_folder(folder)


class TestRemoveHlsFiles:
    """Tests for remove_hls_files function."""

    def test_remove_hls_files_nonexistent_folder(self):
        """Should return 0 when folder doesn't exist."""
        relative_path = "2024/01/15/playlist1"

        with patch.object(Path, "exists", return_value=False):
            result = remove_hls_files(relative_path)

            assert result == 0

    def test_remove_hls_files_empty_folder(self):
        """Should return 0 when folder is empty."""
        relative_path = "2024/01/15/playlist1"

        with patch.object(Path, "exists", return_value=True):
            with patch.object(Path, "iterdir", return_value=[]):
                result = remove_hls_files(relative_path)

                assert result == 0

    def test_remove_hls_files_removes_ts_and_m3u8(self):
        """Should remove .ts and .m3u8 files and return count."""
        relative_path = "2024/01/15/playlist1"

        # Create mock files
        mock_ts1 = MagicMock(spec=Path)
        mock_ts1.suffix = ".ts"
        mock_ts2 = MagicMock(spec=Path)
        mock_ts2.suffix = ".ts"
        mock_m3u8 = MagicMock(spec=Path)
        mock_m3u8.suffix = ".m3u8"

        with patch.object(Path, "exists", return_value=True):
            with patch.object(Path, "iterdir", return_value=[mock_ts1, mock_ts2, mock_m3u8]):
                result = remove_hls_files(relative_path)

                assert result == 3
                mock_ts1.unlink.assert_called_once()
                mock_ts2.unlink.assert_called_once()
                mock_m3u8.unlink.assert_called_once()

    def test_remove_hls_files_preserves_other_files(self):
        """Should not remove non-HLS files."""
        relative_path = "2024/01/15/playlist1"

        # Create mock files
        mock_ts = MagicMock(spec=Path)
        mock_ts.suffix = ".ts"
        mock_png = MagicMock(spec=Path)
        mock_png.suffix = ".png"
        mock_txt = MagicMock(spec=Path)
        mock_txt.suffix = ".txt"

        with patch.object(Path, "exists", return_value=True):
            with patch.object(Path, "iterdir", return_value=[mock_ts, mock_png, mock_txt]):
                result = remove_hls_files(relative_path)

                assert result == 1
                mock_ts.unlink.assert_called_once()
                mock_png.unlink.assert_not_called()
                mock_txt.unlink.assert_not_called()

    def test_remove_hls_files_constructs_correct_path(self):
        """Should construct path relative to ARCHIVE_DIR."""
        relative_path = "2024/01/15/playlist1"

        with patch.object(Path, "exists") as mock_exists:
            mock_exists.return_value = False

            remove_hls_files(relative_path)

            # The exists() call should be on the constructed path
            # We need to verify the path was constructed correctly
            mock_exists.assert_called_once()

    def test_remove_hls_files_only_removes_exact_extensions(self):
        """Should only remove files with exact .ts or .m3u8 extensions."""
        relative_path = "2024/01/15/playlist1"

        # Create mock files with various extensions
        mock_ts = MagicMock(spec=Path)
        mock_ts.suffix = ".ts"
        mock_tss = MagicMock(spec=Path)
        mock_tss.suffix = ".tss"  # Similar but not exact
        mock_m3u8 = MagicMock(spec=Path)
        mock_m3u8.suffix = ".m3u8"
        mock_m3u = MagicMock(spec=Path)
        mock_m3u.suffix = ".m3u"  # Similar but not exact

        with patch.object(Path, "exists", return_value=True):
            with patch.object(Path, "iterdir", return_value=[mock_ts, mock_tss, mock_m3u8, mock_m3u]):
                result = remove_hls_files(relative_path)

                assert result == 2
                mock_ts.unlink.assert_called_once()
                mock_m3u8.unlink.assert_called_once()
                mock_tss.unlink.assert_not_called()
                mock_m3u.unlink.assert_not_called()
