import json
import re
from datetime import date, datetime
from pathlib import Path

ARCHIVE_PATH = Path("/var/www/html/storage/sparrow_cam/archive")
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MAX_RANGE_DAYS = 31


def parse_date(value: str | None, param_name: str) -> tuple[date | None, dict | None]:
    if value is None:
        return None, {"error": f"Missing required parameter: {param_name}"}
    if not DATE_PATTERN.match(value):
        return None, {"error": f"Invalid date format for '{param_name}': expected YYYY-MM-DD"}
    try:
        return datetime.strptime(value, "%Y-%m-%d").date(), None
    except ValueError:
        return None, {"error": f"Invalid date value for '{param_name}': {value}"}


def get_stream_birds(stream_path: Path) -> list[str]:
    meta_path = stream_path / "meta.json"
    try:
        with meta_path.open() as f:
            meta = json.load(f)
        birds: set[str] = set()
        manual_annotations = meta.get("manual_annotations")
        if manual_annotations is not None:
            for annotations in manual_annotations.values():
                for ann in annotations:
                    if "bird_class" in ann:
                        birds.add(ann["bird_class"])
        else:
            for detections in meta.get("detections", {}).values():
                for det in detections:
                    if "class" in det:
                        birds.add(det["class"])
        return sorted(birds)
    except (OSError, json.JSONDecodeError, KeyError):
        return []


def parse_bird_filter(birds_param: str | None) -> list[str]:
    if not birds_param:
        return []
    return [b.strip() for b in birds_param.split(",") if b.strip()]


def stream_matches_filter(stream_path: Path, bird_filter: list[str]) -> bool:
    if not bird_filter:
        return True
    birds = get_stream_birds(stream_path)
    return any(b in bird_filter for b in birds)


def parse_bool_filter(value: str | None) -> bool:
    return value in ("true", "1")


def parse_annotations_filter(
    include_false_positives_param: str | None,
    exclude_annotated_param: str | None,
) -> tuple[bool, bool, dict | None]:
    include_false_positives = parse_bool_filter(include_false_positives_param)
    exclude_annotated = parse_bool_filter(exclude_annotated_param)
    if include_false_positives and exclude_annotated:
        return False, False, {"error": "include_false_positives and exclude_annotated cannot both be set"}
    return include_false_positives, exclude_annotated, None


def get_stream_manual_annotations(stream_path: Path) -> dict | None:
    meta_path = stream_path / "meta.json"
    try:
        with meta_path.open() as f:
            meta = json.load(f)
        return meta.get("manual_annotations")
    except (OSError, json.JSONDecodeError):
        return None


def stream_matches_annotations_filter(
    stream_path: Path,
    include_false_positives: bool,
    exclude_annotated: bool,
) -> bool:
    if include_false_positives and not exclude_annotated:
        return True
    manual_annotations = get_stream_manual_annotations(stream_path)
    if exclude_annotated and manual_annotations is not None:
        return False
    if not include_false_positives and manual_annotations == {}:
        return False
    return True


def is_safe_path_component(component: str) -> bool:
    """Return True if component contains no path traversal sequences."""
    return Path(component).name == component and component not in (".", "..")


def resolve_stream_path(year: str, month: str, day: str, stream: str) -> Path | None:
    """Resolve stream path and return it only if it stays within ARCHIVE_PATH."""
    path = (ARCHIVE_PATH / year / month / day / stream).resolve()
    if path.is_relative_to(ARCHIVE_PATH.resolve()):
        return path
    return None
