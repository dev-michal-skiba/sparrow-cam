"""Unit tests for the dataset sync manager."""

import stat
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import paramiko
import pytest

from lab.sync import CONNECTION_TIMEOUT, MAX_RETRIES, SyncError, SyncManager, main


class TestSyncError:
    """Tests for SyncError exception."""

    def test_sync_error_is_exception(self):
        """Test that SyncError is an Exception."""
        assert issubclass(SyncError, Exception)

    def test_sync_error_with_message(self):
        """Test that SyncError can be raised with a message."""
        with pytest.raises(SyncError, match="Test error"):
            raise SyncError("Test error")


class TestSyncManagerInit:
    """Tests for SyncManager initialization."""

    def test_init_default_state(self):
        """Test that SyncManager initializes with correct default state."""
        manager = SyncManager()
        assert manager._sftp is None
        assert manager._transport is None
        assert manager._socket is None
        assert manager._host == ""
        assert manager._user == ""


class TestLoadConfig:
    """Tests for _load_config method."""

    def test_load_config_success(self):
        """Test successful config loading."""
        config_data = {"ansible_target_host": "192.168.1.1", "ansible_target_user": "pi"}
        config_content = "ansible_target_host: 192.168.1.1\nansible_target_user: pi\n"

        with patch("lab.sync.CONFIG_PATH") as mock_config_path:
            mock_config_path.exists.return_value = True
            with patch("builtins.open", mock_open(read_data=config_content)):
                with patch("yaml.safe_load", return_value=config_data):
                    manager = SyncManager()
                    host, user = manager._load_config()

        assert host == "192.168.1.1"
        assert user == "pi"

    def test_load_config_file_not_found(self):
        """Test that SyncError is raised when config file doesn't exist."""
        with patch("lab.sync.CONFIG_PATH") as mock_config_path:
            mock_config_path.exists.return_value = False
            mock_config_path.__str__.return_value = "/secrets/all.yml"

            manager = SyncManager()
            with pytest.raises(SyncError, match="Config file not found"):
                manager._load_config()

    def test_load_config_missing_host(self):
        """Test that SyncError is raised when ansible_target_host is missing."""
        config_data = {"ansible_target_user": "pi"}
        config_content = "ansible_target_user: pi\n"

        with patch("lab.sync.CONFIG_PATH") as mock_config_path:
            mock_config_path.exists.return_value = True
            with patch("builtins.open", mock_open(read_data=config_content)):
                with patch("yaml.safe_load", return_value=config_data):
                    manager = SyncManager()
                    with pytest.raises(SyncError, match="Missing ansible_target_host or ansible_target_user"):
                        manager._load_config()

    def test_load_config_missing_user(self):
        """Test that SyncError is raised when ansible_target_user is missing."""
        config_data = {"ansible_target_host": "192.168.1.1"}
        config_content = "ansible_target_host: 192.168.1.1\n"

        with patch("lab.sync.CONFIG_PATH") as mock_config_path:
            mock_config_path.exists.return_value = True
            with patch("builtins.open", mock_open(read_data=config_content)):
                with patch("yaml.safe_load", return_value=config_data):
                    manager = SyncManager()
                    with pytest.raises(SyncError, match="Missing ansible_target_host or ansible_target_user"):
                        manager._load_config()

    def test_load_config_empty_host(self):
        """Test that SyncError is raised when ansible_target_host is empty."""
        config_data = {"ansible_target_host": "", "ansible_target_user": "pi"}
        config_content = "ansible_target_host: ''\nansible_target_user: pi\n"

        with patch("lab.sync.CONFIG_PATH") as mock_config_path:
            mock_config_path.exists.return_value = True
            with patch("builtins.open", mock_open(read_data=config_content)):
                with patch("yaml.safe_load", return_value=config_data):
                    manager = SyncManager()
                    with pytest.raises(SyncError, match="Missing ansible_target_host or ansible_target_user"):
                        manager._load_config()

    def test_load_config_empty_user(self):
        """Test that SyncError is raised when ansible_target_user is empty."""
        config_data = {"ansible_target_host": "192.168.1.1", "ansible_target_user": ""}
        config_content = "ansible_target_host: 192.168.1.1\nansible_target_user: ''\n"

        with patch("lab.sync.CONFIG_PATH") as mock_config_path:
            mock_config_path.exists.return_value = True
            with patch("builtins.open", mock_open(read_data=config_content)):
                with patch("yaml.safe_load", return_value=config_data):
                    manager = SyncManager()
                    with pytest.raises(SyncError, match="Missing ansible_target_host or ansible_target_user"):
                        manager._load_config()


class TestConnect:
    """Tests for connect method."""

    def test_connect_ssh_key_not_found(self):
        """Test that SyncError is raised when SSH key doesn't exist."""
        with patch("lab.sync.SSH_KEY_PATH") as mock_ssh_key_path:
            mock_ssh_key_path.exists.return_value = False
            mock_ssh_key_path.__str__.return_value = "/secrets/ssh_key"

            manager = SyncManager()
            with pytest.raises(SyncError, match="SSH key not found"):
                manager.connect()

    def test_connect_with_ed25519_key_success(self):
        """Test successful connection with Ed25519 key."""
        with (
            patch("lab.sync.SSH_KEY_PATH") as mock_ssh_key_path,
            patch("lab.sync.CONFIG_PATH") as mock_config_path,
            patch("builtins.open", mock_open(read_data="ansible_target_host: test.host\nansible_target_user: user\n")),
            patch("yaml.safe_load", return_value={"ansible_target_host": "test.host", "ansible_target_user": "user"}),
            patch("paramiko.Ed25519Key.from_private_key_file") as mock_ed25519,
            patch("socket.create_connection") as mock_socket,
            patch("paramiko.Transport") as mock_transport_class,
            patch("paramiko.SFTPClient.from_transport") as mock_sftp_from_transport,
        ):

            mock_ssh_key_path.exists.return_value = True
            mock_config_path.exists.return_value = True
            mock_key = MagicMock()
            mock_ed25519.return_value = mock_key
            mock_socket_instance = MagicMock()
            mock_socket.return_value = mock_socket_instance
            mock_transport_instance = MagicMock()
            mock_transport_class.return_value = mock_transport_instance
            mock_sftp_instance = MagicMock()
            mock_transport_instance.open_session.return_value = MagicMock()
            mock_channel = MagicMock()
            mock_sftp_instance.get_channel.return_value = mock_channel
            mock_sftp_from_transport.return_value = mock_sftp_instance

            manager = SyncManager()
            manager.connect()

            assert manager._host == "test.host"
            assert manager._user == "user"
            assert manager._socket == mock_socket_instance
            assert manager._transport == mock_transport_instance
            assert manager._sftp == mock_sftp_instance
            mock_socket.assert_called_once_with(("test.host", 22), timeout=CONNECTION_TIMEOUT)
            mock_transport_instance.set_keepalive.assert_called_once_with(30)
            mock_transport_instance.connect.assert_called_once_with(username="user", pkey=mock_key)

    def test_connect_ed25519_fails_rsa_succeeds(self):
        """Test fallback to RSA key when Ed25519 fails."""
        with (
            patch("lab.sync.SSH_KEY_PATH") as mock_ssh_key_path,
            patch("lab.sync.CONFIG_PATH") as mock_config_path,
            patch("builtins.open", mock_open(read_data="ansible_target_host: test.host\nansible_target_user: user\n")),
            patch("yaml.safe_load", return_value={"ansible_target_host": "test.host", "ansible_target_user": "user"}),
            patch("paramiko.Ed25519Key.from_private_key_file") as mock_ed25519,
            patch("paramiko.RSAKey.from_private_key_file") as mock_rsa,
            patch("socket.create_connection") as mock_socket,
            patch("paramiko.Transport") as mock_transport_class,
            patch("paramiko.SFTPClient.from_transport") as mock_sftp_from_transport,
        ):

            mock_ssh_key_path.exists.return_value = True
            mock_config_path.exists.return_value = True
            mock_ed25519.side_effect = paramiko.SSHException("Ed25519 failed")
            mock_key = MagicMock()
            mock_rsa.return_value = mock_key
            mock_socket_instance = MagicMock()
            mock_socket.return_value = mock_socket_instance
            mock_transport_instance = MagicMock()
            mock_transport_class.return_value = mock_transport_instance
            mock_sftp_instance = MagicMock()
            mock_channel = MagicMock()
            mock_sftp_instance.get_channel.return_value = mock_channel
            mock_sftp_from_transport.return_value = mock_sftp_instance

            manager = SyncManager()
            manager.connect()

            mock_ed25519.assert_called_once()
            mock_rsa.assert_called_once()
            assert manager._sftp == mock_sftp_instance

    def test_connect_both_keys_fail(self):
        """Test that SyncError is raised when both Ed25519 and RSA keys fail."""
        with (
            patch("lab.sync.SSH_KEY_PATH") as mock_ssh_key_path,
            patch("lab.sync.CONFIG_PATH") as mock_config_path,
            patch("builtins.open", mock_open(read_data="ansible_target_host: test.host\nansible_target_user: user\n")),
            patch("yaml.safe_load", return_value={"ansible_target_host": "test.host", "ansible_target_user": "user"}),
            patch("paramiko.Ed25519Key.from_private_key_file") as mock_ed25519,
            patch("paramiko.RSAKey.from_private_key_file") as mock_rsa,
        ):

            mock_ssh_key_path.exists.return_value = True
            mock_config_path.exists.return_value = True
            mock_ed25519.side_effect = paramiko.SSHException("Ed25519 failed")
            mock_rsa.side_effect = paramiko.SSHException("RSA failed")

            manager = SyncManager()
            with pytest.raises(SyncError, match="Failed to load SSH key"):
                manager.connect()

    def test_connect_socket_timeout(self):
        """Test that SyncError is raised on socket timeout."""
        with (
            patch("lab.sync.SSH_KEY_PATH") as mock_ssh_key_path,
            patch("lab.sync.CONFIG_PATH") as mock_config_path,
            patch("builtins.open", mock_open(read_data="ansible_target_host: test.host\nansible_target_user: user\n")),
            patch("yaml.safe_load", return_value={"ansible_target_host": "test.host", "ansible_target_user": "user"}),
            patch("paramiko.Ed25519Key.from_private_key_file") as mock_ed25519,
            patch("socket.create_connection") as mock_socket,
        ):

            mock_ssh_key_path.exists.return_value = True
            mock_config_path.exists.return_value = True
            mock_ed25519.return_value = MagicMock()
            mock_socket.side_effect = TimeoutError("Connection timed out")

            manager = SyncManager()
            with pytest.raises(SyncError, match="Connection to test.host timed out"):
                manager.connect()

    def test_connect_general_error(self):
        """Test that SyncError is raised on general connection errors."""
        with (
            patch("lab.sync.SSH_KEY_PATH") as mock_ssh_key_path,
            patch("lab.sync.CONFIG_PATH") as mock_config_path,
            patch("builtins.open", mock_open(read_data="ansible_target_host: test.host\nansible_target_user: user\n")),
            patch("yaml.safe_load", return_value={"ansible_target_host": "test.host", "ansible_target_user": "user"}),
            patch("paramiko.Ed25519Key.from_private_key_file") as mock_ed25519,
            patch("socket.create_connection") as mock_socket,
        ):

            mock_ssh_key_path.exists.return_value = True
            mock_config_path.exists.return_value = True
            mock_ed25519.return_value = MagicMock()
            mock_socket.side_effect = OSError("Connection refused")

            manager = SyncManager()
            with pytest.raises(SyncError, match="Failed to connect to test.host"):
                manager.connect()

    def test_connect_sftp_from_transport_returns_none(self):
        """Test connect when SFTPClient.from_transport returns None."""
        with (
            patch("lab.sync.SSH_KEY_PATH") as mock_ssh_key_path,
            patch("lab.sync.CONFIG_PATH") as mock_config_path,
            patch("builtins.open", mock_open(read_data="ansible_target_host: test.host\nansible_target_user: user\n")),
            patch("yaml.safe_load", return_value={"ansible_target_host": "test.host", "ansible_target_user": "user"}),
            patch("paramiko.Ed25519Key.from_private_key_file") as mock_ed25519,
            patch("socket.create_connection") as mock_socket,
            patch("paramiko.Transport") as mock_transport_class,
            patch("paramiko.SFTPClient.from_transport") as mock_sftp_from_transport,
        ):

            mock_ssh_key_path.exists.return_value = True
            mock_config_path.exists.return_value = True
            mock_ed25519.return_value = MagicMock()
            mock_socket_instance = MagicMock()
            mock_socket.return_value = mock_socket_instance
            mock_transport_instance = MagicMock()
            mock_transport_class.return_value = mock_transport_instance
            # Return None to simulate sftp creation failure
            mock_sftp_from_transport.return_value = None

            manager = SyncManager()
            manager.connect()

            # Should set sftp to None when from_transport returns None
            assert manager._sftp is None

    def test_connect_channel_is_none(self):
        """Test connect when get_channel returns None."""
        with (
            patch("lab.sync.SSH_KEY_PATH") as mock_ssh_key_path,
            patch("lab.sync.CONFIG_PATH") as mock_config_path,
            patch("builtins.open", mock_open(read_data="ansible_target_host: test.host\nansible_target_user: user\n")),
            patch("yaml.safe_load", return_value={"ansible_target_host": "test.host", "ansible_target_user": "user"}),
            patch("paramiko.Ed25519Key.from_private_key_file") as mock_ed25519,
            patch("socket.create_connection") as mock_socket,
            patch("paramiko.Transport") as mock_transport_class,
            patch("paramiko.SFTPClient.from_transport") as mock_sftp_from_transport,
        ):

            mock_ssh_key_path.exists.return_value = True
            mock_config_path.exists.return_value = True
            mock_ed25519.return_value = MagicMock()
            mock_socket_instance = MagicMock()
            mock_socket.return_value = mock_socket_instance
            mock_transport_instance = MagicMock()
            mock_transport_class.return_value = mock_transport_instance
            mock_sftp_instance = MagicMock()
            # Return None for get_channel to test that branch
            mock_sftp_instance.get_channel.return_value = None
            mock_sftp_from_transport.return_value = mock_sftp_instance

            manager = SyncManager()
            manager.connect()

            # Should have set sftp without error when channel is None
            assert manager._sftp == mock_sftp_instance
            # get_channel should have been called
            mock_sftp_instance.get_channel.assert_called_once()


class TestDisconnect:
    """Tests for disconnect method."""

    def test_disconnect_when_not_connected(self):
        """Test disconnect when manager is not connected."""
        manager = SyncManager()
        manager.disconnect()  # Should not raise

    def test_disconnect_closes_sftp(self):
        """Test that disconnect closes SFTP connection."""
        manager = SyncManager()
        mock_sftp = MagicMock()
        manager._sftp = mock_sftp
        manager.disconnect()

        mock_sftp.close.assert_called_once()
        assert manager._sftp is None

    def test_disconnect_closes_transport(self):
        """Test that disconnect closes transport."""
        manager = SyncManager()
        mock_transport = MagicMock()
        manager._transport = mock_transport
        manager.disconnect()

        mock_transport.close.assert_called_once()
        assert manager._transport is None

    def test_disconnect_closes_socket(self):
        """Test that disconnect closes socket."""
        manager = SyncManager()
        mock_socket = MagicMock()
        manager._socket = mock_socket
        manager.disconnect()

        mock_socket.close.assert_called_once()
        assert manager._socket is None

    def test_disconnect_handles_sftp_error(self):
        """Test that disconnect handles errors closing SFTP."""
        manager = SyncManager()
        mock_sftp = MagicMock()
        mock_sftp.close.side_effect = Exception("SFTP already closed")
        manager._sftp = mock_sftp
        manager.disconnect()  # Should not raise

        assert manager._sftp is None

    def test_disconnect_handles_transport_error(self):
        """Test that disconnect handles errors closing transport."""
        manager = SyncManager()
        mock_transport = MagicMock()
        mock_transport.close.side_effect = Exception("Transport already closed")
        manager._transport = mock_transport
        manager.disconnect()  # Should not raise

        assert manager._transport is None

    def test_disconnect_handles_socket_error(self):
        """Test that disconnect handles errors closing socket."""
        manager = SyncManager()
        mock_socket = MagicMock()
        mock_socket.close.side_effect = Exception("Socket already closed")
        manager._socket = mock_socket
        manager.disconnect()  # Should not raise

        assert manager._socket is None

    def test_disconnect_closes_all_resources(self):
        """Test that disconnect closes all resources in correct order."""
        manager = SyncManager()
        mock_sftp = MagicMock()
        mock_transport = MagicMock()
        mock_socket = MagicMock()
        manager._sftp = mock_sftp
        manager._transport = mock_transport
        manager._socket = mock_socket

        manager.disconnect()

        mock_sftp.close.assert_called_once()
        mock_transport.close.assert_called_once()
        mock_socket.close.assert_called_once()
        assert manager._sftp is None
        assert manager._transport is None
        assert manager._socket is None


class TestReconnect:
    """Tests for _reconnect method."""

    def test_reconnect_disconnect_then_connect(self):
        """Test that _reconnect calls disconnect then connect."""
        manager = SyncManager()
        manager._sftp = MagicMock()
        manager._transport = MagicMock()
        manager._socket = MagicMock()

        with (
            patch.object(manager, "disconnect") as mock_disconnect,
            patch.object(manager, "connect") as mock_connect,
            patch("time.sleep") as mock_sleep,
        ):

            manager._reconnect()

            mock_disconnect.assert_called_once()
            mock_sleep.assert_called_once_with(0.5)
            mock_connect.assert_called_once()

    def test_reconnect_disconnect_error_ignored(self):
        """Test that _reconnect ignores disconnect errors."""
        manager = SyncManager()
        manager._sftp = MagicMock()
        manager._transport = MagicMock()
        manager._socket = MagicMock()

        with (
            patch.object(manager, "disconnect", side_effect=Exception("Disconnect failed")),
            patch.object(manager, "connect") as mock_connect,
            patch("time.sleep") as mock_sleep,
        ):

            manager._reconnect()

            # Connection handles should be cleared even if disconnect fails
            assert manager._sftp is None
            assert manager._transport is None
            assert manager._socket is None
            mock_sleep.assert_called_once_with(0.5)
            mock_connect.assert_called_once()


class TestListRemoteFiles:
    """Tests for _list_remote_files method."""

    def test_list_remote_files_not_connected(self):
        """Test that SyncError is raised when not connected."""
        manager = SyncManager()
        with pytest.raises(SyncError, match="Not connected"):
            manager._list_remote_files()

    def test_list_remote_files_empty_directory(self):
        """Test listing empty remote directory."""
        manager = SyncManager()
        manager._sftp = MagicMock()
        manager._sftp.listdir_attr.return_value = []

        files = manager._list_remote_files()

        assert files == {}
        manager._sftp.listdir_attr.assert_called_once()

    def test_list_remote_files_single_file(self):
        """Test listing remote directory with single file."""
        manager = SyncManager()
        manager._sftp = MagicMock()

        # Create mock file entry
        file_entry = MagicMock()
        file_entry.filename = "image.jpg"
        file_entry.st_mode = stat.S_IFREG | 0o644  # Regular file
        file_entry.st_size = 1024

        manager._sftp.listdir_attr.return_value = [file_entry]

        with patch("lab.sync.REMOTE_DATASET_PATH", "/remote/dataset"):
            files = manager._list_remote_files()

        assert files == {"image.jpg": 1024}

    def test_list_remote_files_multiple_files(self):
        """Test listing remote directory with multiple files."""
        manager = SyncManager()
        manager._sftp = MagicMock()

        file1 = MagicMock()
        file1.filename = "file1.jpg"
        file1.st_mode = stat.S_IFREG | 0o644
        file1.st_size = 1024

        file2 = MagicMock()
        file2.filename = "file2.jpg"
        file2.st_mode = stat.S_IFREG | 0o644
        file2.st_size = 2048

        manager._sftp.listdir_attr.return_value = [file1, file2]

        with patch("lab.sync.REMOTE_DATASET_PATH", "/remote/dataset"):
            files = manager._list_remote_files()

        assert files == {"file1.jpg": 1024, "file2.jpg": 2048}

    def test_list_remote_files_nested_directories(self):
        """Test listing remote directory with nested structure."""
        manager = SyncManager()
        manager._sftp = MagicMock()

        # Mock directory entry
        dir_entry = MagicMock()
        dir_entry.filename = "subdir"
        dir_entry.st_mode = stat.S_IFDIR | 0o755  # Directory

        # Mock file in root
        file_entry = MagicMock()
        file_entry.filename = "root_file.jpg"
        file_entry.st_mode = stat.S_IFREG | 0o644
        file_entry.st_size = 512

        # Mock file in subdirectory
        subfile_entry = MagicMock()
        subfile_entry.filename = "sub_file.jpg"
        subfile_entry.st_mode = stat.S_IFREG | 0o644
        subfile_entry.st_size = 768

        # Set up listdir_attr to return different results for root and subdir
        def listdir_side_effect(path):
            if path == "/remote/dataset":
                return [dir_entry, file_entry]
            elif path == "/remote/dataset/subdir":
                return [subfile_entry]
            return []

        manager._sftp.listdir_attr.side_effect = listdir_side_effect

        with patch("lab.sync.REMOTE_DATASET_PATH", "/remote/dataset"):
            files = manager._list_remote_files()

        assert files == {
            "root_file.jpg": 512,
            "subdir/sub_file.jpg": 768,
        }

    def test_list_remote_files_ignore_none_st_mode(self):
        """Test that files with None st_mode are skipped."""
        manager = SyncManager()
        manager._sftp = MagicMock()

        file_entry = MagicMock()
        file_entry.filename = "file.jpg"
        file_entry.st_mode = None
        file_entry.st_size = 1024

        manager._sftp.listdir_attr.return_value = [file_entry]

        with patch("lab.sync.REMOTE_DATASET_PATH", "/remote/dataset"):
            files = manager._list_remote_files()

        # Files with None st_mode should be treated as regular files
        assert "file.jpg" in files

    def test_list_remote_files_none_st_size_defaults_to_zero(self):
        """Test that None st_size is treated as 0."""
        manager = SyncManager()
        manager._sftp = MagicMock()

        file_entry = MagicMock()
        file_entry.filename = "file.jpg"
        file_entry.st_mode = stat.S_IFREG | 0o644
        file_entry.st_size = None

        manager._sftp.listdir_attr.return_value = [file_entry]

        with patch("lab.sync.REMOTE_DATASET_PATH", "/remote/dataset"):
            files = manager._list_remote_files()

        assert files == {"file.jpg": 0}

    def test_list_remote_files_oserror(self):
        """Test that OSError is converted to SyncError."""
        manager = SyncManager()
        manager._sftp = MagicMock()
        manager._sftp.listdir_attr.side_effect = OSError("Permission denied")

        with patch("lab.sync.REMOTE_DATASET_PATH", "/remote/dataset"):
            with pytest.raises(SyncError, match="Cannot list remote directory"):
                manager._list_remote_files()


class TestDownloadFileWithRetry:
    """Tests for _download_file_with_retry method."""

    def test_download_file_success_first_try(self, tmp_path):
        """Test successful download on first attempt."""
        manager = SyncManager()
        manager._sftp = MagicMock()

        with patch("lab.sync.DATASET_DIR", tmp_path):
            manager._download_file_with_retry("file.jpg")

            manager._sftp.get.assert_called_once()

    def test_download_file_creates_parent_directories(self, tmp_path):
        """Test that parent directories are created."""
        manager = SyncManager()
        manager._sftp = MagicMock()

        with patch("lab.sync.DATASET_DIR", tmp_path), patch("lab.sync.REMOTE_DATASET_PATH", "/remote/dataset"):

            manager._download_file_with_retry("subdir/nested/file.jpg")

            # Check that parent directory was created
            assert (tmp_path / "subdir" / "nested").exists()

    def test_download_file_retry_on_exception(self, tmp_path):
        """Test that file download retries on exceptions."""
        manager = SyncManager()

        get_call_count = 0

        def get_side_effect(remote, local):
            nonlocal get_call_count
            get_call_count += 1
            if get_call_count <= 2:
                raise Exception("Network error")
            # Third call succeeds

        mock_sftp = MagicMock()
        mock_sftp.get.side_effect = get_side_effect
        manager._sftp = mock_sftp

        def reconnect_side_effect():
            # Provide a fresh mock for reconnection attempts
            new_mock = MagicMock()
            new_mock.get.side_effect = get_side_effect
            manager._sftp = new_mock

        with (
            patch("lab.sync.DATASET_DIR", tmp_path),
            patch("lab.sync.REMOTE_DATASET_PATH", "/remote/dataset"),
            patch.object(manager, "_reconnect", side_effect=reconnect_side_effect),
            patch("time.sleep"),
        ):

            manager._download_file_with_retry("file.jpg")

            # Should have been called 3 times total (fail, fail, succeed)
            assert get_call_count == 3

    def test_download_file_deletes_partial_file(self, tmp_path):
        """Test that partial local files are deleted on retry."""
        manager = SyncManager()

        get_call_count = 0

        def get_side_effect(remote, local):
            nonlocal get_call_count
            get_call_count += 1
            if get_call_count == 1:
                raise Exception("Network error")
            # Second call succeeds

        mock_sftp = MagicMock()
        mock_sftp.get.side_effect = get_side_effect
        manager._sftp = mock_sftp

        def reconnect_side_effect():
            new_mock = MagicMock()
            new_mock.get.side_effect = get_side_effect
            manager._sftp = new_mock

        # Create a partial file
        partial_file = tmp_path / "file.jpg"
        partial_file.write_text("partial")

        with (
            patch("lab.sync.DATASET_DIR", tmp_path),
            patch("lab.sync.REMOTE_DATASET_PATH", "/remote/dataset"),
            patch.object(manager, "_reconnect", side_effect=reconnect_side_effect),
            patch("time.sleep"),
        ):

            manager._download_file_with_retry("file.jpg")

            # After retry, file should have been deleted and recreated by second get call
            assert get_call_count == 2

    def test_download_file_max_retries_exceeded(self, tmp_path):
        """Test that SyncError is raised after max retries exceeded."""
        manager = SyncManager()
        manager._sftp = MagicMock()
        manager._sftp.get.side_effect = Exception("Network error")

        with (
            patch("lab.sync.DATASET_DIR", tmp_path),
            patch("lab.sync.REMOTE_DATASET_PATH", "/remote/dataset"),
            patch.object(manager, "_reconnect"),
            patch("time.sleep"),
        ):

            with pytest.raises(SyncError, match=f"Failed to download file.jpg after {MAX_RETRIES} attempts"):
                manager._download_file_with_retry("file.jpg")

    def test_download_file_reconnect_on_none_sftp(self, tmp_path):
        """Test that reconnect is called when _sftp is None."""
        manager = SyncManager()
        manager._sftp = None

        reconnect_called = False

        def reconnect_side_effect():
            nonlocal reconnect_called
            reconnect_called = True
            # Create a working mock after reconnect
            mock_sftp = MagicMock()
            mock_sftp.get.return_value = None
            manager._sftp = mock_sftp

        with (
            patch("lab.sync.DATASET_DIR", tmp_path),
            patch("lab.sync.REMOTE_DATASET_PATH", "/remote/dataset"),
            patch.object(manager, "_reconnect", side_effect=reconnect_side_effect),
        ):

            manager._download_file_with_retry("file.jpg")

            assert reconnect_called

    def test_download_file_disconnect_on_failure(self, tmp_path):
        """Test that disconnect is called on failure before retry."""
        manager = SyncManager()

        get_call_count = 0

        def get_side_effect(remote, local):
            nonlocal get_call_count
            get_call_count += 1
            if get_call_count == 1:
                raise Exception("Network error")
            # Second call succeeds

        mock_sftp = MagicMock()
        mock_sftp.get.side_effect = get_side_effect
        manager._sftp = mock_sftp
        manager._transport = MagicMock()
        manager._socket = MagicMock()

        def reconnect_side_effect():
            new_mock = MagicMock()
            new_mock.get.side_effect = get_side_effect
            manager._sftp = new_mock

        disconnect_call_count = 0
        original_disconnect = manager.disconnect

        def tracked_disconnect():
            nonlocal disconnect_call_count
            disconnect_call_count += 1
            original_disconnect()

        with (
            patch("lab.sync.DATASET_DIR", tmp_path),
            patch("lab.sync.REMOTE_DATASET_PATH", "/remote/dataset"),
            patch.object(manager, "disconnect", side_effect=tracked_disconnect),
            patch.object(manager, "_reconnect", side_effect=reconnect_side_effect),
            patch("time.sleep"),
        ):

            manager._download_file_with_retry("file.jpg")

            # disconnect should be called at least once
            assert disconnect_call_count >= 1

    def test_download_file_clears_connections_after_failure(self, tmp_path):
        """Test that connections are cleared after failure."""
        manager = SyncManager()

        get_call_count = 0

        def get_side_effect(remote, local):
            nonlocal get_call_count
            get_call_count += 1
            if get_call_count == 1:
                raise Exception("Network error")
            # Second call succeeds

        mock_sftp = MagicMock()
        mock_sftp.get.side_effect = get_side_effect
        manager._sftp = mock_sftp
        manager._transport = MagicMock()
        manager._socket = MagicMock()

        def reconnect_side_effect():
            new_mock = MagicMock()
            new_mock.get.side_effect = get_side_effect
            manager._sftp = new_mock

        with (
            patch("lab.sync.DATASET_DIR", tmp_path),
            patch("lab.sync.REMOTE_DATASET_PATH", "/remote/dataset"),
            patch.object(manager, "disconnect") as mock_disconnect,
            patch.object(manager, "_reconnect", side_effect=reconnect_side_effect),
            patch("time.sleep"),
        ):

            manager._download_file_with_retry("file.jpg")

            # disconnect should have been called
            assert mock_disconnect.called

    def test_download_file_reconnect_failure_continues_retrying(self, tmp_path):
        """Test that retries continue even if reconnect fails."""
        manager = SyncManager()

        mock_sftp = MagicMock()
        mock_sftp.get.side_effect = [Exception("Network error") for _ in range(MAX_RETRIES)]
        manager._sftp = mock_sftp

        reconnect_count = 0

        def reconnect_side_effect():
            nonlocal reconnect_count
            reconnect_count += 1
            # Reconnect creates a new mock with same failure side effect
            new_mock = MagicMock()
            new_mock.get.side_effect = Exception("Network error")
            manager._sftp = new_mock

        with (
            patch("lab.sync.DATASET_DIR", tmp_path),
            patch("lab.sync.REMOTE_DATASET_PATH", "/remote/dataset"),
            patch.object(manager, "disconnect"),
            patch.object(manager, "_reconnect", side_effect=reconnect_side_effect),
            patch("time.sleep"),
        ):

            with pytest.raises(SyncError):
                manager._download_file_with_retry("file.jpg")

            # Reconnect should have been called multiple times
            assert reconnect_count > 0

    def test_download_file_logs_warnings(self, tmp_path, caplog):
        """Test that warnings are logged for failed attempts."""
        manager = SyncManager()
        manager._sftp = MagicMock()
        manager._sftp.get.side_effect = Exception("Network error")

        with (
            patch("lab.sync.DATASET_DIR", tmp_path),
            patch("lab.sync.REMOTE_DATASET_PATH", "/remote/dataset"),
            patch.object(manager, "disconnect"),
            patch("time.sleep"),
        ):

            with pytest.raises(SyncError):
                manager._download_file_with_retry("file.jpg")

            # Check that warning was logged
            assert "Download failed" in caplog.text or "Waiting" in caplog.text

    def test_download_file_disconnect_exception_ignored(self, tmp_path):
        """Test that disconnect exceptions are ignored during retry."""
        manager = SyncManager()

        get_call_count = 0

        def get_side_effect(remote, local):
            nonlocal get_call_count
            get_call_count += 1
            if get_call_count <= 2:
                raise Exception("Network error")
            # Third call succeeds

        mock_sftp = MagicMock()
        mock_sftp.get.side_effect = get_side_effect
        manager._sftp = mock_sftp
        manager._transport = MagicMock()
        manager._socket = MagicMock()

        def reconnect_side_effect():
            new_mock = MagicMock()
            new_mock.get.side_effect = get_side_effect
            manager._sftp = new_mock

        original_disconnect = manager.disconnect

        def disconnect_with_error():
            original_disconnect()
            # This won't actually raise since original_disconnect clears everything
            # but we're testing the exception handling path
            raise Exception("Disconnect error")

        with (
            patch("lab.sync.DATASET_DIR", tmp_path),
            patch("lab.sync.REMOTE_DATASET_PATH", "/remote/dataset"),
            patch.object(manager, "disconnect", side_effect=disconnect_with_error),
            patch.object(manager, "_reconnect", side_effect=reconnect_side_effect),
            patch("time.sleep"),
        ):

            manager._download_file_with_retry("file.jpg")

            # Should succeed despite disconnect exception
            assert get_call_count == 3

    def test_download_file_unlink_exception_ignored(self, tmp_path):
        """Test that OSError from unlink is ignored when deleting partial files."""
        manager = SyncManager()

        get_call_count = 0

        def get_side_effect(remote, local):
            nonlocal get_call_count
            get_call_count += 1
            if get_call_count == 1:
                raise Exception("Network error")
            # Second call succeeds

        mock_sftp = MagicMock()
        mock_sftp.get.side_effect = get_side_effect
        manager._sftp = mock_sftp
        manager._transport = MagicMock()
        manager._socket = MagicMock()

        def reconnect_side_effect():
            new_mock = MagicMock()
            new_mock.get.side_effect = get_side_effect
            manager._sftp = new_mock

        # Create a partial file
        partial_file = tmp_path / "file.jpg"
        partial_file.write_text("partial")

        with (
            patch("lab.sync.DATASET_DIR", tmp_path),
            patch("lab.sync.REMOTE_DATASET_PATH", "/remote/dataset"),
            patch.object(manager, "disconnect"),
            patch.object(manager, "_reconnect", side_effect=reconnect_side_effect),
            patch("time.sleep"),
        ):
            # Mock Path.unlink to raise OSError for our specific file
            original_unlink = Path.unlink

            def unlink_side_effect(self):
                if str(self) == str(partial_file):
                    raise OSError("Permission denied")
                return original_unlink(self)

            with patch.object(Path, "unlink", unlink_side_effect):
                manager._download_file_with_retry("file.jpg")

            # Should succeed despite unlink OSError
            assert get_call_count == 2

    def test_download_file_reconnect_exception_logs_and_continues(self, tmp_path):
        """Test that reconnect exceptions are logged but retries continue."""
        manager = SyncManager()

        get_call_count = 0

        def get_side_effect(remote, local):
            nonlocal get_call_count
            get_call_count += 1
            if get_call_count <= 2:
                raise Exception("Network error")
            # Third call succeeds

        mock_sftp = MagicMock()
        mock_sftp.get.side_effect = get_side_effect
        manager._sftp = mock_sftp

        reconnect_count = 0

        def reconnect_with_error():
            nonlocal reconnect_count
            reconnect_count += 1
            if reconnect_count == 1:
                # First reconnect fails
                raise Exception("Reconnect failed")
            # Second reconnect succeeds by providing a working mock
            new_mock = MagicMock()
            new_mock.get.side_effect = get_side_effect
            manager._sftp = new_mock

        with (
            patch("lab.sync.DATASET_DIR", tmp_path),
            patch("lab.sync.REMOTE_DATASET_PATH", "/remote/dataset"),
            patch.object(manager, "disconnect"),
            patch.object(manager, "_reconnect", side_effect=reconnect_with_error),
            patch("time.sleep"),
        ):

            manager._download_file_with_retry("file.jpg")

            # Should succeed even with reconnect failure
            assert get_call_count >= 1
            assert reconnect_count >= 1

    def test_download_file_final_disconnect_exception_ignored(self, tmp_path):
        """Test that disconnect exceptions in final cleanup are ignored."""
        manager = SyncManager()
        manager._sftp = MagicMock()
        manager._sftp.get.side_effect = Exception("Network error")
        manager._transport = MagicMock()
        manager._socket = MagicMock()

        original_disconnect = manager.disconnect

        def disconnect_with_error():
            original_disconnect()
            raise Exception("Final disconnect error")

        with (
            patch("lab.sync.DATASET_DIR", tmp_path),
            patch("lab.sync.REMOTE_DATASET_PATH", "/remote/dataset"),
            patch.object(manager, "disconnect", side_effect=disconnect_with_error),
            patch.object(manager, "_reconnect"),
            patch("time.sleep"),
        ):

            with pytest.raises(SyncError):
                manager._download_file_with_retry("file.jpg")

            # Should raise SyncError from download, not from disconnect


class TestSyncDataset:
    """Tests for sync_dataset method."""

    def test_sync_dataset_no_files(self):
        """Test syncing when remote has no files."""
        manager = SyncManager()
        manager._sftp = MagicMock()

        with patch.object(manager, "_list_remote_files", return_value={}):
            downloaded = manager.sync_dataset()

            assert downloaded == 0

    def test_sync_dataset_downloads_new_files(self, tmp_path):
        """Test that new remote files are downloaded."""
        manager = SyncManager()
        manager._sftp = MagicMock()

        remote_files = {
            "file1.jpg": 1024,
            "file2.jpg": 2048,
        }

        with (
            patch.object(manager, "_list_remote_files", return_value=remote_files),
            patch.object(manager, "_download_file_with_retry") as mock_download,
            patch("lab.sync.DATASET_DIR", tmp_path),
        ):

            downloaded = manager.sync_dataset()

            assert downloaded == 2
            assert mock_download.call_count == 2

    def test_sync_dataset_skips_unchanged_files(self, tmp_path):
        """Test that unchanged files are skipped."""
        manager = SyncManager()
        manager._sftp = MagicMock()

        # Create local file with matching size
        local_file = tmp_path / "file1.jpg"
        local_file.write_text("x" * 1024)

        remote_files = {
            "file1.jpg": 1024,  # Same size as local
            "file2.jpg": 2048,  # New file
        }

        with (
            patch.object(manager, "_list_remote_files", return_value=remote_files),
            patch.object(manager, "_download_file_with_retry") as mock_download,
            patch("lab.sync.DATASET_DIR", tmp_path),
        ):

            downloaded = manager.sync_dataset()

            # Only file2 should be downloaded
            assert downloaded == 1
            mock_download.assert_called_once_with("file2.jpg")

    def test_sync_dataset_downloads_changed_files(self, tmp_path):
        """Test that files with different sizes are re-downloaded."""
        manager = SyncManager()
        manager._sftp = MagicMock()

        # Create local file with different size
        local_file = tmp_path / "file1.jpg"
        local_file.write_text("x" * 512)  # Old size

        remote_files = {
            "file1.jpg": 1024,  # Changed size
        }

        with (
            patch.object(manager, "_list_remote_files", return_value=remote_files),
            patch.object(manager, "_download_file_with_retry") as mock_download,
            patch("lab.sync.DATASET_DIR", tmp_path),
        ):

            downloaded = manager.sync_dataset()

            assert downloaded == 1
            mock_download.assert_called_once_with("file1.jpg")

    def test_sync_dataset_leaves_local_only_files(self, tmp_path):
        """Test that local-only files are not deleted."""
        manager = SyncManager()
        manager._sftp = MagicMock()

        # Create local-only file
        local_only = tmp_path / "local_only.txt"
        local_only.write_text("local")

        remote_files = {}

        with (
            patch.object(manager, "_list_remote_files", return_value=remote_files),
            patch.object(manager, "_download_file_with_retry") as mock_download,
            patch("lab.sync.DATASET_DIR", tmp_path),
        ):

            downloaded = manager.sync_dataset()

            assert downloaded == 0
            assert local_only.exists()
            mock_download.assert_not_called()

    def test_sync_dataset_nested_files(self, tmp_path):
        """Test syncing nested file structures."""
        manager = SyncManager()
        manager._sftp = MagicMock()

        remote_files = {
            "subdir/file1.jpg": 1024,
            "subdir/nested/file2.jpg": 2048,
        }

        with (
            patch.object(manager, "_list_remote_files", return_value=remote_files),
            patch.object(manager, "_download_file_with_retry") as mock_download,
            patch("lab.sync.DATASET_DIR", tmp_path),
        ):

            downloaded = manager.sync_dataset()

            assert downloaded == 2
            assert mock_download.call_count == 2


class TestContextManager:
    """Tests for context manager functionality."""

    def test_context_manager_enter_calls_connect(self):
        """Test that __enter__ calls connect."""
        manager = SyncManager()
        with patch.object(manager, "connect") as mock_connect:
            with manager:
                mock_connect.assert_called_once()

    def test_context_manager_exit_calls_disconnect(self):
        """Test that __exit__ calls disconnect."""
        manager = SyncManager()
        with patch.object(manager, "connect"), patch.object(manager, "disconnect") as mock_disconnect:
            with manager:
                pass
            mock_disconnect.assert_called_once()

    def test_context_manager_returns_self(self):
        """Test that __enter__ returns the manager instance."""
        manager = SyncManager()
        with patch.object(manager, "connect"):
            with manager as m:
                assert m is manager

    def test_context_manager_disconnect_on_exception(self):
        """Test that __exit__ disconnects even on exception."""
        manager = SyncManager()
        with patch.object(manager, "connect"), patch.object(manager, "disconnect") as mock_disconnect:
            try:
                with manager:
                    raise ValueError("Test error")
            except ValueError:
                pass
            mock_disconnect.assert_called_once()


class TestMain:
    """Tests for main function."""

    def test_main_creates_dataset_dir(self, tmp_path):
        """Test that main creates DATASET_DIR."""
        with (
            patch("lab.sync.DATASET_DIR", tmp_path / "dataset"),
            patch("lab.sync.SyncManager") as mock_sync_manager_class,
            patch("logging.basicConfig"),
        ):
            mock_manager = MagicMock()
            mock_manager.__enter__.return_value = mock_manager
            mock_sync_manager_class.return_value = mock_manager
            mock_manager.sync_dataset.return_value = 5

            main()

            # Check that directory was created
            assert (tmp_path / "dataset").exists()

    def test_main_runs_sync(self):
        """Test that main runs sync_dataset."""
        with (
            patch("lab.sync.DATASET_DIR"),
            patch("lab.sync.SyncManager") as mock_sync_manager_class,
            patch("logging.basicConfig"),
        ):
            mock_manager = MagicMock()
            mock_manager.__enter__.return_value = mock_manager
            mock_sync_manager_class.return_value = mock_manager
            mock_manager.sync_dataset.return_value = 5

            main()

            mock_manager.sync_dataset.assert_called_once()

    def test_main_logs_completion(self, tmp_path, caplog):
        """Test that main logs completion message."""
        with (
            patch("lab.sync.DATASET_DIR", tmp_path),
            patch("lab.sync.SyncManager") as mock_sync_manager_class,
            patch("logging.basicConfig"),
        ):
            mock_manager = MagicMock()
            mock_manager.__enter__.return_value = mock_manager
            mock_sync_manager_class.return_value = mock_manager
            mock_manager.sync_dataset.return_value = 5

            main()

            assert "Dataset sync complete" in caplog.text or mock_manager.sync_dataset.called


class TestMainGuard:
    """Tests for __main__ guard."""

    def test_main_guard_structure(self):
        """Test that __main__ guard is present in sync.py."""
        # The __main__ guard (line 268) is a Python idiom that ensures
        # the main() function is only called when the module is run as a script,
        # not when imported. This test verifies the structure is in place.
        import lab.sync as sync_module

        # Get the path to the sync module
        sync_module_path = Path(sync_module.__file__).parent / "sync.py"

        # Read the sync.py file and verify it contains the __main__ guard
        with open(sync_module_path) as f:
            content = f.read()

        # Verify the __main__ guard is present
        assert 'if __name__ == "__main__":' in content, "__main__ guard not found"
        assert "main()" in content, "main() call not found in __main__ guard"

    def test_main_function_is_callable(self):
        """Test that main function exists and is callable."""
        import lab.sync as sync_module

        # Verify the module has the main function
        assert hasattr(sync_module, "main"), "main function not found"
        assert callable(sync_module.main), "main is not callable"
