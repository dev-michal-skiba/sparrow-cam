import argparse
import json
import logging
import random
import shutil
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

from cron.constants import ARCHIVE_PATH, LOG_FORMAT

logger = logging.getLogger(__name__)

KEEP_COUNT = 10  # Target number of non-annotated recordings to keep per day
MAX_SEGMENTS = 60  # Recordings with this more segments are always removed


@dataclass
class Recording:
    """A single archived recording directory."""

    path: Path
    timestamp: str
    segment_count: int
    is_manually_annotated: bool


class RecordingsCleaner:
    """Prune archived recordings for a day to bound storage usage.

    Manually annotated recordings are never removed. Recordings with
    more segments than MAX_SEGMENTS are always removed (unless manually
    annotated), even if fewer than KEEP_COUNT recordings remain afterwards.
    Of the remaining recordings, up to KEEP_COUNT minus the number of
    manually annotated recordings are kept: the recordings are split into
    that many time-ordered groups and one random recording is kept from
    each group, so kept recordings are spread across the day instead of
    clustered together.
    """

    def cleanup_day(self, day: date) -> None:
        """Remove excess recordings archived on the given day.

        Args:
            day: The calendar day whose archived recordings should be pruned.
        """
        day_path = ARCHIVE_PATH / day.strftime("%Y") / day.strftime("%m") / day.strftime("%d")
        if not day_path.is_dir():
            logger.info(f"No archive directory for {day.isoformat()}, skipping")
            return

        recordings = [self.load_recording(d) for d in sorted(day_path.iterdir()) if d.is_dir()]
        annotated = [r for r in recordings if r.is_manually_annotated]
        unannotated = [r for r in recordings if not r.is_manually_annotated]

        oversized = [r for r in unannotated if r.segment_count > MAX_SEGMENTS]
        for recording in oversized:
            self.remove_recording(recording)

        candidates = [r for r in unannotated if r.segment_count <= MAX_SEGMENTS]
        keep_budget = max(0, KEEP_COUNT - len(annotated))
        groups = self.group_by_timestamp(candidates, keep_budget)
        to_keep = [random.choice(group) for group in groups]  # nosec B311
        for recording in candidates:
            if recording not in to_keep:
                self.remove_recording(recording)

        logger.info(
            f"Cleaned up {day.isoformat()}: {len(annotated)} annotated kept, "
            f"{len(oversized)} oversized removed, {len(to_keep)} kept from {len(groups)} group(s)"
        )

    def load_recording(self, path: Path) -> Recording:
        """Read a recording directory's timestamp, segment count and annotation status."""
        return Recording(
            path=path,
            timestamp=self.parse_timestamp(path.name),
            segment_count=len(list(path.glob("*.ts"))),
            is_manually_annotated=self.is_manually_annotated(path),
        )

    def parse_timestamp(self, directory_name: str) -> str:
        """Extract the sortable timestamp segment from an archive directory name.

        Archive directories are named "{prefix}_{timestamp}_{uuid}" by the
        processor's stream archiver, where timestamp is a fixed-width, lexically
        sortable "%Y-%m-%dT%H%M%SZ" string.
        """
        return directory_name.split("_")[1]

    def is_manually_annotated(self, path: Path) -> bool:
        """Return True if the recording's meta.json has manual annotations."""
        meta_path = path / "meta.json"
        if not meta_path.exists():
            return False
        try:
            with open(meta_path) as f:
                meta = json.load(f)
        except (OSError, json.JSONDecodeError):
            return False
        return meta.get("manual_annotations") is not None

    def group_by_timestamp(self, candidates: list[Recording], group_count: int) -> list[list[Recording]]:
        """Split candidates into group_count contiguous, time-ordered groups.

        Candidates are sorted by timestamp, then split into as-equal-as-possible
        contiguous chunks so each group spans a distinct slice of the day.
        """
        if group_count <= 0:
            return []
        ordered = sorted(candidates, key=lambda r: r.timestamp)
        base_size, remainder = divmod(len(ordered), group_count)
        groups = []
        start = 0
        for i in range(group_count):
            size = base_size + (1 if i < remainder else 0)
            if size == 0:
                continue
            groups.append(ordered[start : start + size])
            start += size
        return groups

    def remove_recording(self, recording: Recording) -> None:
        """Delete a recording directory from the archive."""
        logger.info(f"Removing recording {recording.path} ({recording.segment_count} segments)")
        shutil.rmtree(recording.path)


def parse_date_arg(value: str) -> date:
    """Argparse helper to parse a YYYY-MM-DD date string."""
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Invalid date '{value}', expected YYYY-MM-DD") from exc


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format=LOG_FORMAT,
        handlers=[logging.StreamHandler()],
    )

    parser = argparse.ArgumentParser(description="Cleanup old archived recordings")
    parser.add_argument(
        "--from-date",
        type=parse_date_arg,
        default=None,
        help="First day to clean up (YYYY-MM-DD). Defaults to today.",
    )
    parser.add_argument(
        "--to-date",
        type=parse_date_arg,
        default=None,
        help="Last day to clean up (YYYY-MM-DD). Defaults to --from-date, or today if omitted.",
    )
    args = parser.parse_args()

    from_date = args.from_date or date.today()
    to_date = args.to_date or from_date

    cleaner = RecordingsCleaner()
    current = from_date
    while current <= to_date:
        cleaner.cleanup_day(current)
        current += timedelta(days=1)


if __name__ == "__main__":
    main()
