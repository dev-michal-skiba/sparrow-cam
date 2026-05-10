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


def is_safe_path_component(component: str) -> bool:
    """Return True if component contains no path traversal sequences."""
    return Path(component).name == component and component not in (".", "..")


def resolve_stream_path(year: str, month: str, day: str, stream: str) -> Path | None:
    """Resolve stream path and return it only if it stays within ARCHIVE_PATH."""
    path = (ARCHIVE_PATH / year / month / day / stream).resolve()
    if path.is_relative_to(ARCHIVE_PATH.resolve()):
        return path
    return None
