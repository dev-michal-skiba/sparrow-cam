from pathlib import Path

LOG_FORMAT = "%(name)s - %(levelname)s - %(message)s"

DETECTION_PRESET_PATH = Path(__file__).parent / "detection_preset.json"
ARCHIVING_DISABLED_FLAG_PATH = Path("/var/www/html/storage/sparrow_cam/disable_archiving")
