import argparse
import logging
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from processor.constants import LOG_FORMAT

logger = logging.getLogger(__name__)

STREAM_PATH = Path("/var/www/html/hls")
ARCHIVE_PATH = Path("/var/www/html/storage/sparrow_cam/archive")
M3U8_HEADER_TAGS = ["#EXTM3U", "#EXT-X-VERSION", "#EXT-X-MEDIA-SEQUENCE", "#EXT-X-TARGETDURATION", "#EXT-X-STREAM-INF"]


@dataclass
class ValidationResult:
    """Result of validation check for archiving."""

    is_valid: bool
    error_message: str | None = None
    playlist_filename: str | None = None


@dataclass
class CopyResult:
    """Result of copying stream files to archive directory."""

    destination_path: str
    playlist_filename: str


@dataclass
class SegmentData:
    """A segment of a stream."""

    metadata: list[str]
    name: str


@dataclass
class PlaylistData:
    filename: str
    header_lines: list[str]
    segments_data: list[SegmentData]


class StreamArchiver:
    """Archive current HLS segments to timestamped UUID directories."""

    def archive(self, prefix: str, limit: int | None = None, end_segment: str | None = None) -> None:
        """Copy playlist file and its referenced segment files to a timestamped UUID directory.

        Args:
            limit: Maximum number of segments to keep. If None, all segments are kept.
            prefix: Prefix for the archive directory name. Use "auto" for automatic bird detection,
                "manual" for manual archiving via script.
            end_segment: If provided, archive segments ending with this segment name.
                This prevents race conditions when new segments appear during archiving.
        """

        # Validate archive prerequisites
        validation_result = self.validate(limit)
        if not validation_result.is_valid:
            logger.error(validation_result.error_message)
            return
        # Copy stream files to archive directory
        copy_result = self.copy_stream(validation_result.playlist_filename, prefix)
        # Get playlist data
        playlist_data = self.get_playlist_data(copy_result, limit, end_segment)
        # Clean archive directory
        self.clean_archive(copy_result.destination_path, playlist_data)

        logger.info(f"Archived to {copy_result.destination_path} with {len(playlist_data.segments_data)} segment(s)")

    def validate(self, limit: int | None) -> ValidationResult:
        """Validate archive prerequisites.

        Args:
            limit: Maximum number of segments to archive.

        Returns:
            ValidationResult object.
        """

        if limit is not None and limit <= 0:
            return ValidationResult(is_valid=False, error_message=f"Segment limit must be positive, got {limit}")

        if not STREAM_PATH.is_dir():
            return ValidationResult(is_valid=False, error_message="Stream directory does not exist")

        if not ARCHIVE_PATH.is_dir():
            return ValidationResult(is_valid=False, error_message="Archive directory does not exist")

        # Check for required files
        playlist_files = list(STREAM_PATH.glob("*.m3u8"))
        if not playlist_files:
            return ValidationResult(is_valid=False, error_message="No playlist file found in stream directory")
        if len(playlist_files) > 1:
            return ValidationResult(is_valid=False, error_message="Multiple playlist files found in stream directory")

        ts_files = list(STREAM_PATH.glob("*.ts"))
        if not ts_files:
            return ValidationResult(is_valid=False, error_message="No segment files found in stream directory")

        return ValidationResult(
            is_valid=True,
            playlist_filename=playlist_files[0].name,
        )

    def copy_stream(self, playlist_filename: str, prefix: str) -> CopyResult:
        """Create archive directory with timestamped UUID name and copy all streamfiles from HLS directory.

        Args:
            playlist_filename: Name of the playlist file to copy.
            prefix: Prefix for the archive directory name (e.g., "auto" or "manual").

        Returns:
            CopyResult object.
        """

        now = datetime.now(UTC)
        year_month_day = now.strftime("%Y/%m/%d")
        timestamp = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        uuid = str(uuid4())
        directory_name = f"{prefix}_{timestamp}_{uuid}"
        destination_path = ARCHIVE_PATH / year_month_day / directory_name
        destination_path.mkdir(parents=True, exist_ok=True)

        # Ensure group write permission on created directories (archive dir and date-based parents)
        # Walk up from destination to ARCHIVE_PATH, setting permissions to rwxrwxr-x
        current = destination_path
        while current != ARCHIVE_PATH and current.is_relative_to(ARCHIVE_PATH):
            current.chmod(0o775)
            current = current.parent

        # Copy playlist file to archive directory
        shutil.copy2(STREAM_PATH / playlist_filename, destination_path / playlist_filename)

        # Copy all segments files to archive directory
        for file in STREAM_PATH.glob("*.ts"):
            shutil.copy2(file, destination_path / file.name)

        return CopyResult(
            destination_path=destination_path,
            playlist_filename=playlist_filename,
        )

    def get_playlist_data(
        self, copy_result: CopyResult, limit: int | None, end_segment: str | None = None
    ) -> PlaylistData:
        """Get data from playlist file.

        Args:
            copy_result: CopyResult object.
            limit: Maximum number of segments to keep. If None, all segments are kept.
            end_segment: If provided, select segments ending with this segment name.

        Returns:
            PlaylistData object.
        """

        with open(copy_result.destination_path / copy_result.playlist_filename) as f:
            playlist_lines = list(
                filter(
                    None,
                    [line.strip() for line in f.readlines()],
                ),
            )

        header_lines = []
        segment_lines = []

        for line in playlist_lines:
            for header_tag in M3U8_HEADER_TAGS:
                if line.startswith(header_tag):
                    header_lines.append(line)
                    break
            else:
                segment_lines.append(line)

        segments_data = []
        current_segment_data = SegmentData(metadata=[], name="")
        for line in segment_lines:
            if line.startswith("#"):
                current_segment_data.metadata.append(line)
            else:
                current_segment_data.name = line
                segments_data.append(current_segment_data)
                current_segment_data = SegmentData(metadata=[], name="")

        # Apply segment selection based on end_segment or limit
        if end_segment is not None:
            # Find index of end_segment and slice to get `limit` segments ending with it
            end_idx = next((i for i, s in enumerate(segments_data) if s.name == end_segment), None)
            if end_idx is not None:
                if limit is not None:
                    start_idx = max(0, end_idx - limit + 1)
                    segments_data = segments_data[start_idx : end_idx + 1]
                else:
                    segments_data = segments_data[: end_idx + 1]
        elif limit is not None and limit < len(segments_data):
            segments_data = segments_data[-limit:]

        return PlaylistData(
            filename=copy_result.playlist_filename,
            header_lines=header_lines,
            segments_data=segments_data,
        )

    def clean_archive(self, destination_path: str, playlist_data: PlaylistData):
        """Remove excess files from archive directory and update playlist file.

        Args:
            destination_path: Path to the archive directory.
            playlist_data: PlaylistData object.
        """

        # Get list of segment files
        segment_files = [segment.name for segment in playlist_data.segments_data]
        # Remove excess segments from archive directory
        destination = Path(destination_path)
        for file in destination.iterdir():
            if file.is_file() and file.name not in segment_files:
                file.unlink()
        # Update playlist file
        playlist_lines = playlist_data.header_lines
        for segment_data in playlist_data.segments_data:
            for metadata in segment_data.metadata:
                playlist_lines.append(metadata)
            playlist_lines.append(segment_data.name)
        playlist_lines.append("")
        with open(destination_path / playlist_data.filename, "w") as f:
            f.write("\n".join(playlist_lines))


def parse_limit(value: str | None) -> int | None:
    """Argparse helper to allow int or explicit None."""

    if value is None or value.strip().lower() == "none" or value.strip() == "":
        return None
    try:
        return int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Invalid limit '{value}', expected integer or None") from exc


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format=LOG_FORMAT,
        handlers=[logging.StreamHandler()],
    )

    parser = argparse.ArgumentParser(description="Archive HLS segments to timestamped UUID directories")
    parser.add_argument(
        "--limit",
        type=parse_limit,
        default=15,
        help="Maximum number of segments to archive. Must be positive. Defaults to 15.",
    )
    args = parser.parse_args()

    archiver = StreamArchiver()
    archiver.archive(limit=args.limit, prefix="manual")
