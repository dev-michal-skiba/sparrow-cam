import os
from pathlib import Path

LOG_FORMAT = "%(name)s - %(levelname)s - %(message)s"

DETECTION_PRESET_PATH = Path(__file__).parent / "detection_preset.json"
ARCHIVING_DISABLED_FLAG_PATH = Path("/var/www/html/storage/sparrow_cam/disable_archiving")

# Maintenance window is disabled locally; on the Raspberry Pi it spans civil dusk to dawn at the device location
MAINTENANCE_WINDOW_DISABLED = os.getenv("MAINTENANCE_WINDOW_DISABLED", "") == "1"
LATITUDE = os.getenv("LATITUDE")
LONGITUDE = os.getenv("LONGITUDE")
