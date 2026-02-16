import re
from pathlib import Path

STORAGE_DIR = Path("/.storage")
ARCHIVE_DIR = STORAGE_DIR / "archive"
IMAGES_DIR = STORAGE_DIR / "images"
PRESETS_DIR = STORAGE_DIR / "presets"

# Secrets paths (mounted into container)
SECRETS_DIR = Path("/secrets")
SSH_KEY_PATH = SECRETS_DIR / "ssh_key"
CONFIG_PATH = SECRETS_DIR / "all.yml"

# Remote server paths
REMOTE_ARCHIVE_PATH = "/var/www/html/storage/sparrow_cam/archive"

# Pattern for archive folder names: [{prefix}_]{ISO-timestamp}_{uuid}
# Example: auto_2026-01-15T064557Z_5d83d036-3f12-4d9b-82f5-4d7eb1ab0d92
# Example without prefix: 2026-01-15T064557Z_5d83d036-3f12-4d9b-82f5-4d7eb1ab0d92
ARCHIVE_FOLDER_PATTERN = re.compile(
    r"^(?:\w+_)?\d{4}-\d{2}-\d{2}T\d{6}Z_[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$",
    re.IGNORECASE,
)

# Pattern for image filenames: {prefix}-{segment}-{frame}.png
# Example: sparrow_cam-1488-0.png (segment 1488, frame 0)
# Groups: (1) prefix, (2) segment number, (3) frame index
IMAGE_FILENAME_PATTERN = re.compile(r"^(.+)-(\d+)-(\d+)\.png$")
