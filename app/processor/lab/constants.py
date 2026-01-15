from pathlib import Path

STORAGE_DIR = Path(__file__).resolve().parent / ".storage"
ARCHIVE_DIR = STORAGE_DIR / "archive"
IMAGES_DIR = STORAGE_DIR / "images"

# Secrets paths (mounted into container)
SECRETS_DIR = Path("/secrets")
SSH_KEY_PATH = SECRETS_DIR / "ssh_key"
CONFIG_PATH = SECRETS_DIR / "all.yml"

# Remote server paths
REMOTE_ARCHIVE_PATH = "/var/www/html/storage/sparrow_cam/archive"
