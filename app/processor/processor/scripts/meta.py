import argparse
import json
import math
import random
import shutil
from collections import defaultdict
from pathlib import Path

ARCHIVE_PATH = Path("/var/www/html/storage/sparrow_cam/archive")
ARCHIVE_BASE_URL = "http://rpi.local/archive"


def get_stream_url(meta_path: Path) -> str:
    relative = meta_path.parent.relative_to(ARCHIVE_PATH)
    return f"{ARCHIVE_BASE_URL}/{relative}"


def find_meta_files() -> list[Path]:
    return sorted(ARCHIVE_PATH.rglob("meta.json"))


def get_max_confidence_per_class(meta_path: Path) -> dict[str, float]:
    with open(meta_path) as f:
        meta = json.load(f)

    detections = meta.get("detections", {})
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

    for meta_path in find_meta_files():
        max_conf = get_max_confidence_per_class(meta_path)
        if not max_conf:
            continue
        stream_url = get_stream_url(meta_path)
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

    for meta_path in find_meta_files():
        with open(meta_path) as f:
            meta = json.load(f)

        detections = meta.get("detections", {})
        modified = False
        new_detections: dict[str, list[dict]] = {}

        for segment, segment_detections in detections.items():
            filtered = [d for d in segment_detections if d["class"] != bird_class or d["confidence"] * 100 >= threshold]
            if len(filtered) != len(segment_detections):
                modified = True
            if filtered:
                new_detections[segment] = filtered

        if not modified:
            continue

        stream_url = get_stream_url(meta_path)

        if new_detections:
            print(f"Removed detections from: {stream_url}")
            if not dry_run:
                meta["detections"] = new_detections
                with open(meta_path, "w") as f:
                    json.dump(meta, f, indent=2)
        else:
            print(f"Removed stream: {stream_url}")
            if not dry_run:
                shutil.rmtree(meta_path.parent)


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
