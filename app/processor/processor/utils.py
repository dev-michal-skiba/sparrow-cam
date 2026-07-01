import json
from datetime import datetime

from processor.constants import (
    DETECTION_PRESET_PATH,
    MAINTENANCE_WINDOW_ENABLED,
    MAINTENANCE_WINDOW_END,
    MAINTENANCE_WINDOW_START,
)


def load_detection_preset() -> dict:
    """Load detection preset from JSON file.

    Returns:
        dict: Preset containing 'params' (detection parameters) and 'regions' (detection regions).
    """
    with open(DETECTION_PRESET_PATH) as f:
        return json.load(f)


def is_maintenance_window(now: datetime | None = None) -> bool:
    """Check whether the current local time falls within the maintenance window.

    The window spans MAINTENANCE_WINDOW_START to MAINTENANCE_WINDOW_END, wrapping past midnight.

    Args:
        now: Datetime to check against. Defaults to the current local time.

    Returns:
        bool: True if within the maintenance window.
    """
    if not MAINTENANCE_WINDOW_ENABLED:
        return False
    current_time = (now or datetime.now()).time()
    return current_time >= MAINTENANCE_WINDOW_START or current_time < MAINTENANCE_WINDOW_END
