"""Sync manager for downloading archive files from production server via SFTP."""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path

import paramiko
import yaml

from lab.constants import (
    ARCHIVE_DIR,
    CONFIG_PATH,
    REMOTE_ARCHIVE_PATH,
    SSH_KEY_PATH,
)

# Pattern for archive folder names: [{prefix}_]{ISO-timestamp}_{uuid}
# Example: auto_2026-01-15T06:45:57Z_5d83d036-3f12-4d9b-82f5-4d7eb1ab0d92
# Example without prefix: 2026-01-15T06:45:57Z_5d83d036-3f12-4d9b-82f5-4d7eb1ab0d92
ARCHIVE_FOLDER_PATTERN = re.compile(
    r"^(?:\w+_)?\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z_[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$",
    re.IGNORECASE,
)

# Pattern for date folders: YYYY, MM, DD (numeric)
DATE_FOLDER_PATTERN = re.compile(r"^\d+$")


ProgressCallback = Callable[[int, int, str], None]

# Maximum retry attempts for reconnection
MAX_RETRIES = 15


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
            pkey = paramiko.RSAKey.from_private_key_file(str(SSH_KEY_PATH))
        except paramiko.SSHException as e:
            raise SyncError(f"Failed to load SSH key: {e}") from e

        try:
            self._transport = paramiko.Transport((self._host, 22))
            self._transport.connect(username=self._user, pkey=pkey)
            self._sftp = paramiko.SFTPClient.from_transport(self._transport)
        except Exception as e:
            self.disconnect()
            raise SyncError(f"Failed to connect to {self._host}: {e}") from e

    def disconnect(self) -> None:
        """Close SFTP connection."""
        if self._sftp:
            self._sftp.close()
            self._sftp = None
        if self._transport:
            self._transport.close()
            self._transport = None

    def _is_dir(self, path: str) -> bool:
        """Check if remote path is a directory."""
        if self._sftp is None:
            raise SyncError("Not connected")
        try:
            return self._sftp.stat(path).st_mode is not None and (self._sftp.stat(path).st_mode & 0o40000 != 0)
        except OSError:
            return False

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
        self.disconnect()
        self.connect()

    def _download_file_with_retry(self, file: FileToSync) -> None:
        """
        Download a single file with retry logic.

        If download fails, reconnects and retries up to MAX_RETRIES times.
        """
        # Ensure local directory exists
        file.local_path.parent.mkdir(parents=True, exist_ok=True)

        for attempt in range(MAX_RETRIES):
            try:
                if self._sftp is None:
                    self._reconnect()

                self._sftp.get(file.remote_path, str(file.local_path))
                return  # Success
            except Exception as e:
                print(f"Download failed (attempt {attempt + 1}/{MAX_RETRIES}): {file.filename} - {e}")

                # Delete partial file if it exists
                if file.local_path.exists():
                    try:
                        file.local_path.unlink()
                    except OSError:
                        pass

                if attempt < MAX_RETRIES - 1:
                    # Reconnect and retry
                    try:
                        self._reconnect()
                    except Exception as reconnect_error:
                        print(f"Reconnect failed: {reconnect_error}")
                        # Continue to next attempt
                else:
                    raise SyncError(f"Failed to download {file.filename} after {MAX_RETRIES} attempts") from e

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
