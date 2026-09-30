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


def parse_bird_filter(birds_param: str | None) -> list[str]:
    if not birds_param:
        return []
    return [b.strip() for b in birds_param.split(",") if b.strip()]


def parse_bool_filter(value: str | None) -> bool:
    return value in ("true", "1")


def parse_annotations_filter(
    exclude_false_positives_param: str | None,
    exclude_annotated_param: str | None,
) -> tuple[bool, bool, dict | None]:
    exclude_false_positives = parse_bool_filter(exclude_false_positives_param)
    exclude_annotated = parse_bool_filter(exclude_annotated_param)
    if exclude_false_positives and exclude_annotated:
        return False, False, {"error": "exclude_false_positives and exclude_annotated cannot both be set"}
    return exclude_false_positives, exclude_annotated, None


def is_safe_path_component(component: str) -> bool:
    """Return True if component contains no path traversal sequences."""
    return Path(component).name == component and component not in (".", "..")


def resolve_stream_path(year: str, month: str, day: str, stream: str) -> Path | None:
    """Resolve stream path and return it only if it stays within ARCHIVE_PATH."""
    path = (ARCHIVE_PATH / year / month / day / stream).resolve()
    if path.is_relative_to(ARCHIVE_PATH.resolve()):
        return path
    return None
