"""Sync manager for downloading archive files from production server via SFTP."""

from __future__ import annotations

import re
import shutil
import socket
import stat
import time
from collections.abc import Callable
from pathlib import Path

import paramiko
import yaml

from lab.constants import (
    ARCHIVE_DIR,
    ARCHIVE_FOLDER_PATTERN,
    CONFIG_PATH,
    IMAGES_DIR,
    REMOTE_ARCHIVE_PATH,
    SSH_KEY_PATH,
)

# Pattern for date folders: YYYY, MM, DD (numeric)
DATE_FOLDER_PATTERN = re.compile(r"^\d+$")


ProgressCallback = Callable[[int, int, str], None]

# Maximum retry attempts for reconnection
MAX_RETRIES = 15

# Connection timeout in seconds
CONNECTION_TIMEOUT = 10

# Delay between retry attempts (in seconds)
RETRY_DELAY = 2


class SyncError(Exception):
    """Raised when sync operation fails."""


class FileToSync:
    """Represents a file to be synced from remote to local."""

    def __init__(self, folder: str, filename: str) -> None:
        self.folder = folder
        self.filename = filename

    @property
    def remote_path(self) -> str:
        return f"{REMOTE_ARCHIVE_PATH}/{self.folder}/{self.filename}"

    @property
    def local_path(self) -> Path:
        return ARCHIVE_DIR / self.folder / self.filename

    def __repr__(self) -> str:
        return f"FileToSync({self.folder}/{self.filename})"


class SyncManager:
    """Manages syncing archive files from remote server via SFTP."""

    def __init__(self) -> None:
        self._sftp: paramiko.SFTPClient | None = None
        self._transport: paramiko.Transport | None = None
        self._socket: socket.socket | None = None
        self._host: str = ""
        self._user: str = ""

    def _load_config(self) -> tuple[str, str]:
        """Load SSH host and user from config file."""
        if not CONFIG_PATH.exists():
            raise SyncError(f"Config file not found: {CONFIG_PATH}")

        with open(CONFIG_PATH) as f:
            config = yaml.safe_load(f)

        host = config.get("ansible_target_host")
        user = config.get("ansible_target_user")

        if not host or not user:
            raise SyncError("Missing ansible_target_host or ansible_target_user in config")

        return host, user

    def connect(self) -> None:
        """Establish SFTP connection to remote server."""
        if not SSH_KEY_PATH.exists():
            raise SyncError(f"SSH key not found: {SSH_KEY_PATH}")

        self._host, self._user = self._load_config()

        try:
            pkey = paramiko.Ed25519Key.from_private_key_file(str(SSH_KEY_PATH))
        except paramiko.SSHException:
            # Fall back to RSA if Ed25519 fails
            try:
                pkey = paramiko.RSAKey.from_private_key_file(str(SSH_KEY_PATH))
            except paramiko.SSHException as e:
                raise SyncError(f"Failed to load SSH key: {e}") from e

        try:
            # Create socket with timeout to avoid hanging on unresponsive servers
            self._socket = socket.create_connection((self._host, 22), timeout=CONNECTION_TIMEOUT)
            self._transport = paramiko.Transport(self._socket)
            self._transport.set_keepalive(30)  # Send keepalive every 30 seconds
            self._transport.connect(username=self._user, pkey=pkey)
            self._sftp = paramiko.SFTPClient.from_transport(self._transport)
            # Set a longer timeout for file operations (30s for large files)
            if self._sftp:
                channel = self._sftp.get_channel()
                if channel:
                    channel.settimeout(30)
        except TimeoutError as e:
            self.disconnect()
            raise SyncError(f"Connection to {self._host} timed out") from e
        except Exception as e:
            self.disconnect()
            raise SyncError(f"Failed to connect to {self._host}: {e}") from e

    def disconnect(self) -> None:
        """Close SFTP connection and underlying socket."""
        if self._sftp:
            try:
                self._sftp.close()
            except Exception:  # nosec B110
                pass  # Ignore errors if already closed/broken
            self._sftp = None
        if self._transport:
            try:
                self._transport.close()
            except Exception:  # nosec B110
                pass  # Ignore errors if already closed/broken
            self._transport = None
        # Explicitly close socket - paramiko doesn't close passed-in sockets
        if self._socket:
            try:
                self._socket.close()
            except Exception:  # nosec B110
                pass  # Ignore errors if already closed/broken
            self._socket = None

    def _is_dir(self, path: str) -> bool:
        """Check if remote path is a directory."""
        if self._sftp is None:
            raise SyncError("Not connected")
        try:
            stat_result = self._sftp.stat(path)
            return stat_result.st_mode is not None and (stat_result.st_mode & 0o40000 != 0)
        except OSError:
            return False

    def _remove_remote_folder_recursive(self, path: str) -> None:
        """
        Recursively remove a remote folder and all its contents.

        Args:
            path: Full remote path to the folder to remove.

        Raises:
            SyncError: If not connected or removal fails.
        """
        if self._sftp is None:
            raise SyncError("Not connected")

        try:
            for entry in self._sftp.listdir_attr(path):
                entry_path = f"{path}/{entry.filename}"
                if entry.st_mode is not None and stat.S_ISDIR(entry.st_mode):
                    self._remove_remote_folder_recursive(entry_path)
                else:
                    self._sftp.remove(entry_path)
            self._sftp.rmdir(path)
        except OSError as e:
            raise SyncError(f"Failed to remove remote folder {path}: {e}") from e

    def remove_remote_folder(self, relative_path: str) -> None:
        """
        Remove a folder and its contents from the remote server.

        Args:
            relative_path: Path relative to REMOTE_ARCHIVE_PATH
                          (e.g., "2026/01/15/auto_2026-01-15T06:45:57Z_uuid")

        Raises:
            SyncError: If not connected or removal fails.
        """
        if self._sftp is None:
            raise SyncError("Not connected")

        full_path = f"{REMOTE_ARCHIVE_PATH}/{relative_path}"

        # Verify the folder exists before attempting removal
        if not self._is_dir(full_path):
            raise SyncError(f"Remote folder does not exist: {relative_path}")

        self._remove_remote_folder_recursive(full_path)

    def _list_remote_archive_folders(self) -> list[str]:
        """
        List all archive folders on remote server.

        Returns paths relative to REMOTE_ARCHIVE_PATH in format:
        {year}/{month}/{day}/{folder_name}
        """
        if self._sftp is None:
            raise SyncError("Not connected")

        folders: list[str] = []

        try:
            years = self._sftp.listdir(REMOTE_ARCHIVE_PATH)
        except OSError as e:
            raise SyncError(f"Cannot list remote archive: {e}") from e

        for year in years:
            if not DATE_FOLDER_PATTERN.match(year):
                continue
            year_path = f"{REMOTE_ARCHIVE_PATH}/{year}"
            if not self._is_dir(year_path):
                continue

            try:
                months = self._sftp.listdir(year_path)
            except OSError:
                continue

            for month in months:
                if not DATE_FOLDER_PATTERN.match(month):
                    continue
                month_path = f"{year_path}/{month}"
                if not self._is_dir(month_path):
                    continue

                try:
                    days = self._sftp.listdir(month_path)
                except OSError:
                    continue

                for day in days:
                    if not DATE_FOLDER_PATTERN.match(day):
                        continue
                    day_path = f"{month_path}/{day}"
                    if not self._is_dir(day_path):
                        continue

                    try:
                        archive_folders = self._sftp.listdir(day_path)
                    except OSError:
                        continue

                    for folder in archive_folders:
                        if ARCHIVE_FOLDER_PATTERN.match(folder):
                            folder_path = f"{day_path}/{folder}"
                            if self._is_dir(folder_path):
                                # Return relative path
                                folders.append(f"{year}/{month}/{day}/{folder}")

        return folders

    def _get_files_to_sync(self, remote_folder: str) -> list[str]:
        """
        Get list of .ts and .m3u8 files in a remote folder.

        Returns filenames (not full paths).
        """
        if self._sftp is None:
            raise SyncError("Not connected")

        full_path = f"{REMOTE_ARCHIVE_PATH}/{remote_folder}"
        files: list[str] = []

        try:
            entries = self._sftp.listdir(full_path)
            for entry in entries:
                if entry.endswith(".ts") or entry.endswith(".m3u8"):
                    files.append(entry)
        except OSError:
            pass

        return files

    def get_missing_folders(self) -> list[str]:
        """
        Find remote folders that don't exist locally.

        Returns list of relative paths like: {year}/{month}/{day}/{folder}
        """
        remote_folders = self._list_remote_archive_folders()
        missing: list[str] = []

        for folder in remote_folders:
            local_path = ARCHIVE_DIR / folder
            if not local_path.exists():
                missing.append(folder)

        return missing

    def sync_folder(
        self,
        folder: str,
        on_file_progress: ProgressCallback | None = None,
    ) -> int:
        """
        Download all .ts and .m3u8 files from a remote folder.

        Args:
            folder: Relative path like {year}/{month}/{day}/{folder_name}
            on_file_progress: Callback(current_file, total_files, filename)

        Returns:
            Number of files downloaded.
        """
        if self._sftp is None:
            raise SyncError("Not connected")

        files = self._get_files_to_sync(folder)
        if not files:
            return 0

        local_folder = ARCHIVE_DIR / folder
        local_folder.mkdir(parents=True, exist_ok=True)

        remote_base = f"{REMOTE_ARCHIVE_PATH}/{folder}"

        for idx, filename in enumerate(files):
            remote_file = f"{remote_base}/{filename}"
            local_file = local_folder / filename

            if on_file_progress:
                on_file_progress(idx + 1, len(files), filename)

            try:
                self._sftp.get(remote_file, str(local_file))
            except OSError as e:
                raise SyncError(f"Failed to download {filename}: {e}") from e

        return len(files)

    def _gather_files_to_sync(self) -> list[FileToSync]:
        """
        Gather all files that need to be synced.

        Returns:
            List of FileToSync objects for all missing files.
        """
        missing_folders = self.get_missing_folders()

        files_to_sync: list[FileToSync] = []

        for folder in missing_folders:
            files = self._get_files_to_sync(folder)
            for filename in files:
                files_to_sync.append(FileToSync(folder, filename))

        return files_to_sync

    def _reconnect(self) -> None:
        """Disconnect and reconnect to the server."""
        print("Reconnecting to server...")
        # Force cleanup of any stale connections
        try:
            self.disconnect()
        except Exception:  # nosec B110
            # Ignore errors during disconnect - connection may already be dead
            pass
        finally:
            # Ensure all connections are cleared even if disconnect fails
            self._sftp = None
            self._transport = None
            self._socket = None
        # Small delay to let server release resources
        time.sleep(0.5)
        self.connect()

    def _download_file_with_retry(self, file: FileToSync) -> None:
        """
        Download a single file with retry logic.

        If download fails, reconnects and retries up to MAX_RETRIES times.
        """
        # Ensure local directory exists
        file.local_path.parent.mkdir(parents=True, exist_ok=True)

        last_error: Exception | None = None

        for attempt in range(MAX_RETRIES):
            try:
                if self._sftp is None:
                    self._reconnect()

                self._sftp.get(file.remote_path, str(file.local_path))
                return  # Success
            except Exception as e:
                last_error = e
                print(f"Download failed (attempt {attempt + 1}/{MAX_RETRIES}): {file.filename} - {e}")

                # Properly close all connections before retrying
                try:
                    self.disconnect()
                except Exception:  # nosec B110
                    pass
                finally:
                    # Ensure all handles are cleared
                    self._sftp = None
                    self._transport = None
                    self._socket = None

                # Delete partial file if it exists
                if file.local_path.exists():
                    try:
                        file.local_path.unlink()
                    except OSError:
                        pass

                if attempt < MAX_RETRIES - 1:
                    # Wait before retrying to give the network/server time to recover
                    print(f"Waiting {RETRY_DELAY}s before retry...")
                    time.sleep(RETRY_DELAY)

                    # Reconnect and retry
                    try:
                        self._reconnect()
                    except Exception as reconnect_error:
                        print(f"Reconnect failed: {reconnect_error}")
                        # Continue to next attempt, will try reconnect again

        # All retries exhausted - ensure cleanup before raising
        try:
            self.disconnect()
        except Exception:  # nosec B110
            pass
        raise SyncError(f"Failed to download {file.filename} after {MAX_RETRIES} attempts") from last_error

    def sync_all(
        self,
        on_download_progress: ProgressCallback | None = None,
        on_folder_start: Callable[[str], None] | None = None,
    ) -> tuple[list[str], int]:
        """
        Sync all missing folders from remote server.

        Downloads files one by one with retry logic. If a download fails,
        the connection is reset and download resumes from the failed file.

        Args:
            on_download_progress: Callback(current_file, total_files, filename)
            on_folder_start: Callback(folder_name) when starting a new folder

        Returns:
            Tuple of (list of synced folder paths, total files downloaded)
        """
        # First, gather all files to download
        files_to_sync = self._gather_files_to_sync()

        if not files_to_sync:
            return [], 0

        total_files = len(files_to_sync)
        synced_folders: set[str] = set()
        current_folder: str | None = None

        # Download files one by one
        for idx, file in enumerate(files_to_sync):
            # Notify when starting a new folder
            if file.folder != current_folder:
                current_folder = file.folder
                if on_folder_start:
                    on_folder_start(file.folder)

            # Update progress
            if on_download_progress:
                on_download_progress(idx + 1, total_files, file.filename)

            # Download with retry
            self._download_file_with_retry(file)
            synced_folders.add(file.folder)

        return list(synced_folders), total_files

    def __enter__(self) -> SyncManager:
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.disconnect()


def remove_recording(relative_path: str) -> None:
    """
    Remove a recording from remote server and local storage.

    Remote removal happens first. Local removal only proceeds if remote succeeds.
    Removes both the archive folder (HLS files) and images folder (PNG frames).

    Args:
        relative_path: Path relative to archive/images root
                      (e.g., "2026/01/15/auto_2026-01-15T06:45:57Z_uuid")

    Raises:
        SyncError: If remote removal fails (local data is preserved).
    """
    # Step 1: Remove from remote server first
    with SyncManager() as sync:
        sync.remove_remote_folder(relative_path)

    # Step 2: Remote removal succeeded, now remove local archive folder
    local_archive_path = ARCHIVE_DIR / relative_path
    if local_archive_path.exists():
        shutil.rmtree(local_archive_path)

    # Step 3: Remove local images folder
    local_images_path = IMAGES_DIR / relative_path
    if local_images_path.exists():
        shutil.rmtree(local_images_path)
