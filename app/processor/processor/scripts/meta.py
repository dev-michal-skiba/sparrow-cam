import argparse
import json
import math
import random
import shutil
from collections import defaultdict
from pathlib import Path

from processor.index_db import get_birds, get_connection

ARCHIVE_PATH = Path("/var/www/html/storage/sparrow_cam/archive")
ARCHIVE_BASE_URL = "http://rpi.local/archive"


def get_stream_url(date: str, stream: str) -> str:
    return f"{ARCHIVE_BASE_URL}/{date.replace('-', '/')}/{stream}"


def find_recordings() -> list[tuple[str, str, dict]]:
    """Return (date, stream, detections) for every recording in the database."""
    conn = get_connection()
    try:
        rows = conn.execute("SELECT date, stream, detections FROM recordings ORDER BY date, stream").fetchall()
    finally:
        conn.close()
    return [(date, stream, json.loads(detections or "{}")) for date, stream, detections in rows]


def get_max_confidence_per_class(detections: dict) -> dict[str, float]:
    max_confidence: dict[str, float] = {}

    for segment_detections in detections.values():
        for detection in segment_detections:
            cls = detection["class"]
            confidence = detection["confidence"]
            if cls not in max_confidence or confidence > max_confidence[cls]:
                max_confidence[cls] = confidence

    return max_confidence


def cmd_summarize(args: argparse.Namespace) -> None:
    examples_count = args.examples
    filter_class: str | None = args.bird_class

    # bird_class -> percentage (int) -> list of stream URLs
    data: dict[str, dict[int, list[str]]] = defaultdict(lambda: defaultdict(list))

    for date, stream, detections in find_recordings():
        max_conf = get_max_confidence_per_class(detections)
        if not max_conf:
            continue
        stream_url = get_stream_url(date, stream)
        for cls, confidence in max_conf.items():
            if filter_class is not None and cls != filter_class:
                continue
            pct = math.floor(confidence * 100)
            data[cls][pct].append(stream_url)

    for bird_class in sorted(data.keys()):
        print(f"# {bird_class}")
        pct_data = data[bird_class]
        for pct in sorted(pct_data.keys()):
            streams = pct_data[pct]
            count = len(streams)
            sample_size = min(examples_count, count)
            samples = random.sample(streams, sample_size)  # nosec B311
            print(f"- {pct}% - {count}")
            for url in samples:
                print(f"\t- {url}")


def cmd_delete(args: argparse.Namespace) -> None:
    bird_class = args.bird_class
    threshold = args.threshold
    dry_run = args.dry_run

    conn = get_connection()
    try:
        for date, stream, detections in find_recordings():
            new_detections: dict[str, list[dict]] = {}
            modified = False

            for segment, segment_detections in detections.items():
                filtered = [
                    d for d in segment_detections if d["class"] != bird_class or d["confidence"] * 100 >= threshold
                ]
                if len(filtered) != len(segment_detections):
                    modified = True
                if filtered:
                    new_detections[segment] = filtered

            if not modified:
                continue

            stream_url = get_stream_url(date, stream)

            if new_detections:
                print(f"Removed detections from: {stream_url}")
                if not dry_run:
                    with conn:
                        conn.execute(
                            """
                            UPDATE recordings SET detections = ?,
                                birds = CASE WHEN manual_annotations IS NULL THEN ? ELSE birds END
                            WHERE date = ? AND stream = ?
                            """,
                            (json.dumps(new_detections), json.dumps(get_birds(new_detections)), date, stream),
                        )
            else:
                print(f"Removed stream: {stream_url}")
                if not dry_run:
                    with conn:
                        conn.execute("DELETE FROM recordings WHERE date = ? AND stream = ?", (date, stream))
                    shutil.rmtree(ARCHIVE_PATH / date.replace("-", "/") / stream)
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Meta data management for SparrowCam archives")
    subparsers = parser.add_subparsers(dest="command", required=True)

    summarize_parser = subparsers.add_parser("summarize", help="Print detection report for each bird class")
    summarize_parser.add_argument(
        "--examples",
        type=int,
        default=5,
        help="Number of example stream links to show per percentage (default: 5)",
    )
    summarize_parser.add_argument(
        "--class",
        dest="bird_class",
        default=None,
        help="Limit report to a single bird class",
    )

    delete_parser = subparsers.add_parser("delete", help="Delete detections below threshold for a given class")
    delete_parser.add_argument("--class", dest="bird_class", required=True, help="Bird class name")
    delete_parser.add_argument(
        "--threshold",
        type=float,
        required=True,
        help="Minimum confidence percentage (0-100). Detections strictly below this are removed.",
    )
    delete_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be done without making any changes",
    )

    args = parser.parse_args()

    if args.command == "summarize":
        cmd_summarize(args)
    elif args.command == "delete":
        cmd_delete(args)


if __name__ == "__main__":
    main()
