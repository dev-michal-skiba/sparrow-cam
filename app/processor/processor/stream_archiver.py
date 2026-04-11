import argparse
import json
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

ARCHIVE_ENABLED = True  # Set to True to enable archiving bird detections
ARCHIVE_SEGMENT_COUNT = 15  # Total segments to archive
SEGMENTS_BEFORE_DETECTION = (ARCHIVE_SEGMENT_COUNT - 1) // 2
SEGMENTS_AFTER_DETECTION = ARCHIVE_SEGMENT_COUNT - 1 - SEGMENTS_BEFORE_DETECTION


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
    """Archive current HLS segments to timestamped UUID directories.

    Also manages archive scheduling state: call on_segment() once per processed
    segment to drive delayed and overlap-aware archive triggering.
    """

    def __init__(self):
        # Archive scheduling state
        self._overlap_countdown: int | None = (
            None  # Counts down from SEGMENTS_BEFORE_DETECTION after each archive; None = no archive yet
        )
        self._last_archive_path: Path | None = None
        self._pending_archive_countdown: int | None = None
        self._pending_archive_is_extension = False
        # Per-segment detection data for meta.json
        self._segment_detections: dict[str, list[dict]] = {}

    def on_segment(self, segment_name: str, bird_detected: bool) -> None:
        """Process a segment for archive scheduling and execution.

        Called once per segment after bird detection. Handles delayed triggering
        and overlap-aware extension of previous archives.

        Args:
            segment_name: Name of the current segment.
            bird_detected: Whether a bird was detected in this segment.
        """
        if not ARCHIVE_ENABLED:
            return

        if bird_detected:
            if self._pending_archive_countdown is None:
                in_overlap_zone = self._overlap_countdown is not None and self._overlap_countdown > 0
                if in_overlap_zone:
                    # Extend previous archive instead of creating a new one.
                    # remaining = segments until _overlap_countdown reaches 0 + SEGMENTS_AFTER_DETECTION + 1
                    remaining = ARCHIVE_SEGMENT_COUNT - SEGMENTS_BEFORE_DETECTION + self._overlap_countdown
                    self._pending_archive_countdown = remaining
                    self._pending_archive_is_extension = True
                    logger.info(
                        f"{segment_name}: Bird in overlap zone, extending previous archive "
                        f"in {remaining - 1} segments"
                    )
                else:
                    self.schedule_archive(segment_name)

        # Decrement overlap countdown (bounded at 0, never grows unbounded)
        if self._overlap_countdown is not None and self._overlap_countdown > 0:
            self._overlap_countdown -= 1

        self.check_and_execute_archive(segment_name)

    def schedule_archive(self, segment_name: str) -> None:
        """Schedule an archive to trigger after SEGMENTS_AFTER_DETECTION more segments.

        Args:
            segment_name: Name of the segment where bird was detected.
        """
        if self._pending_archive_countdown is not None:
            logger.debug(f"{segment_name}: Archive already scheduled, ignoring detection")
            return

        # Add 1 to account for decrement happening on this same segment in check_and_execute_archive
        self._pending_archive_countdown = SEGMENTS_AFTER_DETECTION + 1
        self._pending_archive_is_extension = False
        logger.info(f"{segment_name}: Bird detected, archive scheduled in {SEGMENTS_AFTER_DETECTION} segments")

    def check_and_execute_archive(self, segment_name: str) -> None:
        """Check if archive should be triggered and execute if so.

        Args:
            segment_name: Name of the current segment (will be the end segment of archive).
        """
        if self._pending_archive_countdown is None:
            return

        self._pending_archive_countdown -= 1

        if self._pending_archive_countdown <= 0:
            if self._pending_archive_is_extension:
                logger.info(
                    f"{segment_name}: Executing archive extension: "
                    f"archive_path={self._last_archive_path}, end_segment={segment_name}"
                )
                self.extend_archive(
                    archive_path=self._last_archive_path,
                    end_segment=segment_name,
                )
            else:
                logger.info(
                    f"{segment_name}: Executing scheduled archive: "
                    f"limit={ARCHIVE_SEGMENT_COUNT}, prefix=auto, end_segment={segment_name}"
                )
                self._last_archive_path = self.archive(
                    limit=ARCHIVE_SEGMENT_COUNT,
                    prefix="auto",
                    end_segment=segment_name,
                )
            self._overlap_countdown = SEGMENTS_BEFORE_DETECTION
            self._pending_archive_countdown = None
            self._pending_archive_is_extension = False

    def record_detections(self, segment_name: str, detections: list[dict]) -> None:
        """Store detection data for a segment to be included in meta.json on archiving.

        Args:
            segment_name: Name of the segment.
            detections: List of detection dicts with class, confidence, and roi fields.
        """
        if detections:
            self._segment_detections[segment_name] = detections

    def prune_detections(self, valid_segments: set[str]) -> None:
        """Remove stored detections for segments no longer in the live HLS playlist.

        Args:
            valid_segments: Set of segment names currently tracked by the HLS watchtower.
        """
        for segment in list(self._segment_detections):
            if segment not in valid_segments:
                del self._segment_detections[segment]

    def archive(self, prefix: str, limit: int | None = None, end_segment: str | None = None) -> Path | None:
        """Copy playlist file and its referenced segment files to a timestamped UUID directory.

        Args:
            limit: Maximum number of segments to keep. If None, all segments are kept.
            prefix: Prefix for the archive directory name. Use "auto" for automatic bird detection,
                "manual" for manual archiving via script.
            end_segment: If provided, archive segments ending with this segment name.
                This prevents race conditions when new segments appear during archiving.

        Returns:
            Path to the created archive directory, or None if archiving failed.
        """

        # Validate archive prerequisites
        validation_result = self.validate(limit)
        if not validation_result.is_valid:
            logger.error(validation_result.error_message)
            return None
        # Copy stream files to archive directory
        copy_result = self.copy_stream(validation_result.playlist_filename, prefix)
        # Get playlist data
        playlist_data = self.get_playlist_data(copy_result, limit, end_segment)
        # Clean archive directory
        self.clean_archive(copy_result.destination_path, playlist_data)
        self.write_meta(copy_result.destination_path, playlist_data)

        logger.info(f"Archived to {copy_result.destination_path} with {len(playlist_data.segments_data)} segment(s)")
        return copy_result.destination_path

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
        timestamp = now.strftime("%Y-%m-%dT%H%M%SZ")
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

    def parse_playlist(self, playlist_path: Path) -> PlaylistData:
        """Parse an HLS playlist file into structured data.

        Args:
            playlist_path: Path to the .m3u8 playlist file.

        Returns:
            PlaylistData object with all segments (no filtering applied).
        """
        with open(playlist_path) as f:
            playlist_lines = list(filter(None, [line.strip() for line in f.readlines()]))

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

        return PlaylistData(
            filename=playlist_path.name,
            header_lines=header_lines,
            segments_data=segments_data,
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
        playlist_data = self.parse_playlist(copy_result.destination_path / copy_result.playlist_filename)
        segments_data = playlist_data.segments_data

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
            filename=playlist_data.filename,
            header_lines=playlist_data.header_lines,
            segments_data=segments_data,
        )

    def extend_archive(self, archive_path: Path | None, end_segment: str) -> None:
        """Extend an existing archive with additional segments from the live stream.

        Reads the existing archive playlist to find the last archived segment, then
        copies all live stream segments that appear after it up to end_segment into
        the archive directory and updates the archive playlist.

        Args:
            archive_path: Path to the existing archive directory to extend.
            end_segment: Name of the last new segment to include in the extension.
        """
        if archive_path is None:
            logger.error("Cannot extend archive: no archive path available")
            return

        archive_path = Path(archive_path)

        # Read existing archive playlist
        playlist_files = list(archive_path.glob("*.m3u8"))
        if not playlist_files:
            logger.error(f"No playlist file found in archive directory {archive_path}")
            return

        existing_playlist = self.parse_playlist(archive_path / playlist_files[0].name)
        if not existing_playlist.segments_data:
            logger.error(f"No segments found in archive playlist at {archive_path}")
            return

        last_archived_segment = existing_playlist.segments_data[-1].name

        # Get live stream playlist
        live_playlist_files = list(STREAM_PATH.glob("*.m3u8"))
        if not live_playlist_files:
            logger.error("No live stream playlist found for archive extension")
            return

        live_playlist = self.parse_playlist(STREAM_PATH / live_playlist_files[0].name)

        # Find new segments: from after last_archived_segment up to end_segment (inclusive)
        new_segments: list[SegmentData] = []
        found_last = False
        for segment in live_playlist.segments_data:
            if segment.name == last_archived_segment:
                found_last = True
                continue
            if found_last:
                new_segments.append(segment)
                if segment.name == end_segment:
                    break

        if not new_segments:
            logger.warning(f"No new segments to extend archive at {archive_path}")
            return

        # Copy new segment files to archive directory
        for segment in new_segments:
            src = STREAM_PATH / segment.name
            if src.exists():
                shutil.copy2(src, archive_path / segment.name)

        # Update archive playlist with all segments
        updated_playlist = PlaylistData(
            filename=existing_playlist.filename,
            header_lines=existing_playlist.header_lines,
            segments_data=existing_playlist.segments_data + new_segments,
        )
        self.clean_archive(archive_path, updated_playlist)
        self.write_meta(archive_path, updated_playlist)

        logger.info(f"Extended archive {archive_path} with {len(new_segments)} new segment(s)")

    def write_meta(self, destination_path: str | Path, playlist_data: PlaylistData) -> None:
        """Write meta.json alongside archive files with detection info for each segment.

        Args:
            destination_path: Path to the archive directory.
            playlist_data: PlaylistData object describing the archived segments.
        """
        segment_names = {s.name for s in playlist_data.segments_data}
        detections = {name: dets for name, dets in self._segment_detections.items() if name in segment_names}
        meta = {"version": 1, "detections": detections}
        with open(Path(destination_path) / "meta.json", "w") as f:
            json.dump(meta, f, indent=2)

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
