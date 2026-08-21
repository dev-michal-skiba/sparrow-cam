"""Sync manager for downloading the YOLO dataset from the Raspberry Pi via SFTP."""

from __future__ import annotations

import logging
import socket
import stat
import time

import paramiko
import yaml

from lab.constants import CONFIG_PATH, DATASET_DIR, REMOTE_DATASET_PATH, SSH_KEY_PATH

logger = logging.getLogger(__name__)

# Maximum retry attempts for reconnection
MAX_RETRIES = 15

# Connection timeout in seconds
CONNECTION_TIMEOUT = 10

# Delay between retry attempts (in seconds)
RETRY_DELAY = 2


class SyncError(Exception):
    """Raised when sync operation fails."""


class SyncManager:
    """Manages syncing the dataset directory from the Raspberry Pi via SFTP."""

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

    def _reconnect(self) -> None:
        """Disconnect and reconnect to the server."""
        logger.info("Reconnecting to server...")
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

    def _list_remote_files(self) -> dict[str, int]:
        """
        Recursively list all files under the remote dataset directory.

        Returns:
            Dict mapping file paths (relative to REMOTE_DATASET_PATH) to their size in bytes.
        """
        if self._sftp is None:
            raise SyncError("Not connected")

        files: dict[str, int] = {}

        def _walk(remote_dir: str, relative_prefix: str) -> None:
            try:
                entries = self._sftp.listdir_attr(remote_dir)
            except OSError as e:
                raise SyncError(f"Cannot list remote directory {remote_dir}: {e}") from e

            for entry in entries:
                entry_path = f"{remote_dir}/{entry.filename}"
                relative_path = f"{relative_prefix}{entry.filename}"
                if entry.st_mode is not None and stat.S_ISDIR(entry.st_mode):
                    _walk(entry_path, f"{relative_path}/")
                else:
                    files[relative_path] = entry.st_size or 0

        _walk(REMOTE_DATASET_PATH, "")
        return files

    def _download_file_with_retry(self, relative_path: str) -> None:
        """
        Download a single dataset file with retry logic.

        If download fails, reconnects and retries up to MAX_RETRIES times.
        """
        remote_path = f"{REMOTE_DATASET_PATH}/{relative_path}"
        local_path = DATASET_DIR / relative_path
        local_path.parent.mkdir(parents=True, exist_ok=True)

        last_error: Exception | None = None

        for attempt in range(MAX_RETRIES):
            try:
                if self._sftp is None:
                    self._reconnect()

                self._sftp.get(remote_path, str(local_path))
                return  # Success
            except Exception as e:
                last_error = e
                logger.warning(f"Download failed (attempt {attempt + 1}/{MAX_RETRIES}): {relative_path} - {e}")

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
                if local_path.exists():
                    try:
                        local_path.unlink()
                    except OSError:
                        pass

                if attempt < MAX_RETRIES - 1:
                    # Wait before retrying to give the network/server time to recover
                    logger.info(f"Waiting {RETRY_DELAY}s before retry...")
                    time.sleep(RETRY_DELAY)

                    # Reconnect and retry
                    try:
                        self._reconnect()
                    except Exception as reconnect_error:
                        logger.warning(f"Reconnect failed: {reconnect_error}")
                        # Continue to next attempt, will try reconnect again

        # All retries exhausted - ensure cleanup before raising
        try:
            self.disconnect()
        except Exception:  # nosec B110
            pass
        raise SyncError(f"Failed to download {relative_path} after {MAX_RETRIES} attempts") from last_error

    def sync_dataset(self) -> int:
        """
        Download new or changed dataset files from the Raspberry Pi.

        A remote file is downloaded if it doesn't exist locally, or if its size
        differs from the local copy (e.g. re-annotated samples that were rewritten
        on the Pi). Local-only files are left untouched.

        Returns:
            Number of files downloaded.
        """
        remote_files = self._list_remote_files()

        downloaded = 0
        for relative_path, remote_size in remote_files.items():
            local_path = DATASET_DIR / relative_path
            if local_path.exists() and local_path.stat().st_size == remote_size:
                continue
            self._download_file_with_retry(relative_path)
            downloaded += 1

        return downloaded

    def __enter__(self) -> SyncManager:
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.disconnect()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler()],
    )

    DATASET_DIR.mkdir(parents=True, exist_ok=True)

    with SyncManager() as sync:
        downloaded = sync.sync_dataset()

    logger.info(f"Dataset sync complete: {downloaded} file(s) downloaded")


if __name__ == "__main__":
    main()
