import os
from datetime import time
from pathlib import Path

LOG_FORMAT = "%(name)s - %(levelname)s - %(message)s"

DETECTION_PRESET_PATH = Path(__file__).parent / "detection_preset.json"
ARCHIVING_DISABLED_FLAG_PATH = Path("/var/www/html/storage/sparrow_cam/disable_archiving")

# Maintenance window only applies on the Raspberry Pi deployment, gated via env var set in the systemd unit
MAINTENANCE_WINDOW_ENABLED = os.getenv("MAINTENANCE_WINDOW_ENABLED", "") == "1"
MAINTENANCE_WINDOW_START = time(23, 0)  # 11 PM local time
MAINTENANCE_WINDOW_END = time(3, 0)  # 3 AM local time
