import logging
import os
import shutil
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from processor.constants import LOG_FORMAT

logger = logging.getLogger(__name__)

HLS_SEGMENTS_PATH = "/var/www/html/hls"
ARCHIVE_STORAGE_PATH = "/var/www/html/storage/sparrow_cam/archive"


class StreamArchiver:
    """Archive current HLS segments to timestamped UUID directories."""

    def archive(self) -> None:
        """Copy all files from the stream directory to a timestamped UUID directory."""
        if not self._check_root_directory():
            logger.error(f"Root archive storage directory does not exist: {ARCHIVE_STORAGE_PATH}")
            return

        files = [p for p in Path(HLS_SEGMENTS_PATH).iterdir() if p.is_file()]
        if not files:
            logger.info("No files found to archive.")
            return

        timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        uuid = str(uuid4())
        directory_name = f"{timestamp}_{uuid}"
        destination_path = os.path.join(ARCHIVE_STORAGE_PATH, directory_name)
        os.makedirs(destination_path, exist_ok=True)

        for file_path in files:
            shutil.copy2(file_path, destination_path)

        logger.info(f"Archived {len(files)} files to {destination_path}")

    def _check_root_directory(self) -> bool:
        """Check if the root archive storage directory exists."""
        if not os.path.isdir(ARCHIVE_STORAGE_PATH):
            return False
        return True


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format=LOG_FORMAT,
        handlers=[logging.StreamHandler()],
    )
    archiver = StreamArchiver()
    archiver.archive()
