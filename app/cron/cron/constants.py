from pathlib import Path

LOG_FORMAT = "%(name)s - %(levelname)s - %(message)s"

ARCHIVE_PATH = Path("/var/www/html/storage/sparrow_cam/archive")
LAST_CLEANED_UP_DAY_PATH = Path("/var/www/html/storage/sparrow_cam/cron_last_cleaned_up_day.json")
