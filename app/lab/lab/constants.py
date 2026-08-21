from pathlib import Path

STORAGE_DIR = Path("/.storage")
DATASET_DIR = STORAGE_DIR / "dataset"

# Secrets paths (mounted into container)
SECRETS_DIR = Path("/secrets")
SSH_KEY_PATH = SECRETS_DIR / "ssh_key"
CONFIG_PATH = SECRETS_DIR / "all.yml"

# Remote server paths
REMOTE_DATASET_PATH = "/var/www/html/storage/sparrow_cam/dataset"
