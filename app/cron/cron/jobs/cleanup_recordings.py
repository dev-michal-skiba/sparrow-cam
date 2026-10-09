import argparse
import json
import logging
import random
import shutil
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

from cron import index_db
from cron.constants import ARCHIVE_PATH, LAST_CLEANED_UP_DAY_PATH, LOG_FORMAT

logger = logging.getLogger(__name__)

KEEP_COUNT = 10  # Target number of non-annotated recordings to keep per day
MAX_SEGMENTS = 60  # Recordings with this more segments are always removed
FREE_SPACE_THRESHOLD_BYTES = 15 * 1024**3  # Free space on ARCHIVE_PATH's disk below which pruning kicks in


def archive_day_path(day: date) -> Path:
    """Return the archive directory path for a calendar day."""
    return ARCHIVE_PATH / day.strftime("%Y") / day.strftime("%m") / day.strftime("%d")


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
    manually annotated recordings are kept: the time between the first and
    last recording is split into that many equal time intervals and one
    random recording is kept from each interval, so kept recordings are
    spread across the day instead of clustered together. Each empty
    interval's slot goes to one more random recording from a randomly
    chosen non-empty interval.
    """

    def cleanup_day(self, day: date) -> None:
        """Remove excess recordings archived on the given day.

        Args:
            day: The calendar day whose archived recordings should be pruned.
        """
        day_path = archive_day_path(day)
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
        groups = [group for group in self.group_by_time_interval(candidates, keep_budget) if group]
        to_keep = self.select_to_keep(groups, keep_budget)
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
        """Return True if the recording has manual annotations in the index database."""
        return index_db.is_manually_annotated(*self.recording_key(path))

    def recording_key(self, path: Path) -> tuple[str, str]:
        """Return the (date, stream) index database key for a recording directory."""
        year, month, day, stream = path.relative_to(ARCHIVE_PATH).parts
        return f"{year}-{month}-{day}", stream

    def group_by_time_interval(self, candidates: list[Recording], group_count: int) -> list[list[Recording]]:
        """Split candidates into group_count equal-length time intervals.

        The span between the earliest and latest candidate timestamp is divided
        into group_count equal intervals and each candidate is placed in the
        interval its timestamp falls in; the latest candidate goes into the last
        interval. Intervals with no candidates are returned as empty lists.
        """
        if group_count <= 0 or not candidates:
            return []
        times = [datetime.strptime(r.timestamp, "%Y-%m-%dT%H%M%SZ") for r in candidates]
        first, last = min(times), max(times)
        span = (last - first).total_seconds()
        groups: list[list[Recording]] = [[] for _ in range(group_count)]
        for recording, time in sorted(zip(candidates, times), key=lambda pair: pair[1]):
            if time == last:
                index = group_count - 1
            else:
                index = int((time - first).total_seconds() / span * group_count)
            groups[index].append(recording)
        return groups

    def select_to_keep(self, groups: list[list[Recording]], keep_budget: int) -> list[Recording]:
        """Pick keep_budget recordings: one random recording per group, then fill the rest.

        Each slot left over by an empty interval is filled with one more random
        recording from a randomly chosen group that still has unpicked recordings,
        so fewer than keep_budget recordings are kept only when fewer exist.
        """
        remaining = [random.sample(group, len(group)) for group in groups]  # nosec B311
        to_keep = [group.pop() for group in remaining if group]
        while len(to_keep) < keep_budget:
            non_empty = [group for group in remaining if group]
            if not non_empty:
                break
            to_keep.append(random.choice(non_empty).pop())  # nosec B311
        return to_keep

    def remove_recording(self, recording: Recording) -> None:
        """Delete a recording from the index database and its directory from the archive."""
        logger.info(f"Removing recording {recording.path} ({recording.segment_count} segments)")
        index_db.delete_recording(*self.recording_key(recording.path))
        shutil.rmtree(recording.path)


class CleanedDaysStore:
    """Persist the last calendar day cleaned up by the space-pressure sweep."""

    def read_last_cleaned_up_day(self) -> date | None:
        """Return the last cleaned up day, or None if the sweep has never run."""
        if not LAST_CLEANED_UP_DAY_PATH.exists():
            return None
        with open(LAST_CLEANED_UP_DAY_PATH) as f:
            data = json.load(f)
        return datetime.strptime(data["last_cleaned_up_day"], "%Y-%m-%d").date()

    def record(self, day: date) -> None:
        """Persist day as the last cleaned up day."""
        tmp_path = LAST_CLEANED_UP_DAY_PATH.with_name(LAST_CLEANED_UP_DAY_PATH.name + ".tmp")
        with open(tmp_path, "w") as f:
            json.dump({"last_cleaned_up_day": day.isoformat()}, f)
        tmp_path.replace(LAST_CLEANED_UP_DAY_PATH)


def get_free_space_bytes() -> int:
    """Return free space, in bytes, on the disk containing ARCHIVE_PATH."""
    return shutil.disk_usage(ARCHIVE_PATH).free


def find_earliest_archive_day() -> date | None:
    """Find the earliest calendar day present in the archive's year/month/day directories."""
    if not ARCHIVE_PATH.is_dir():
        return None
    year_dirs = [d for d in ARCHIVE_PATH.iterdir() if d.is_dir()]
    if not year_dirs:
        return None
    year_dir = min(year_dirs, key=lambda d: d.name)

    month_dirs = [d for d in year_dir.iterdir() if d.is_dir()]
    if not month_dirs:
        return None
    month_dir = min(month_dirs, key=lambda d: d.name)

    day_dirs = [d for d in month_dir.iterdir() if d.is_dir()]
    if not day_dirs:
        return None
    day_dir = min(day_dirs, key=lambda d: d.name)

    try:
        return date(int(year_dir.name), int(month_dir.name), int(day_dir.name))
    except ValueError:
        return None


def find_oldest_uncleaned_day(last_cleaned_up_day: date | None) -> date | None:
    """Find the oldest archived day that hasn't been cleaned up yet.

    Starts the day after last_cleaned_up_day (or the earliest archived day on first
    run) and steps forward one day at a time until an archived day is found, so only
    days that actually need checking are touched instead of listing the whole archive.
    """
    current = last_cleaned_up_day + timedelta(days=1) if last_cleaned_up_day else find_earliest_archive_day()
    if current is None:
        return None

    today = date.today()
    while current <= today:
        if archive_day_path(current).is_dir():
            return current
        current += timedelta(days=1)
    return None


def run_space_pressure_sweep() -> None:
    """Prune the oldest not-yet-cleaned days until free space reaches FREE_SPACE_THRESHOLD_BYTES.

    Days are pruned oldest first, one at a time, rechecking free space after each. The last
    day pruned is persisted so already-cleaned days are never reprocessed across runs.
    """
    cleaner = RecordingsCleaner()
    store = CleanedDaysStore()
    last_cleaned_up_day = store.read_last_cleaned_up_day()

    while get_free_space_bytes() < FREE_SPACE_THRESHOLD_BYTES:
        day = find_oldest_uncleaned_day(last_cleaned_up_day)
        if day is None:
            logger.info("Free space below threshold but no uncleaned days remain, stopping sweep")
            break

        cleaner.cleanup_day(day)
        store.record(day)
        last_cleaned_up_day = day


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
        help="First day to clean up (YYYY-MM-DD). Omit both this and --to-date to run the free-space sweep instead.",
    )
    parser.add_argument(
        "--to-date",
        type=parse_date_arg,
        default=None,
        help="Last day to clean up (YYYY-MM-DD). Defaults to --from-date.",
    )
    args = parser.parse_args()

    if args.from_date is None and args.to_date is None:
        run_space_pressure_sweep()
        return

    from_date = args.from_date or date.today()
    to_date = args.to_date or from_date

    cleaner = RecordingsCleaner()
    current = from_date
    while current <= to_date:
        cleaner.cleanup_day(current)
        current += timedelta(days=1)


if __name__ == "__main__":
    main()
