from pathlib import Path

STORAGE_DIR = Path("/.storage")
DATASET_DIR = STORAGE_DIR / "dataset"
FINE_TUNED_DIR = STORAGE_DIR / "fine_tuned"

# Secrets paths (mounted into container)
SECRETS_DIR = Path("/secrets")
SSH_KEY_PATH = SECRETS_DIR / "ssh_key"
CONFIG_PATH = SECRETS_DIR / "all.yml"

# Remote server paths
REMOTE_DATASET_PATH = "/var/www/html/storage/sparrow_cam/dataset"

# Base model to fine tune (processor package is mounted into the lab container)
BASE_MODEL_NAME = "yolo26n"
BASE_MODEL_PATH = Path("/app/processor/processor/models") / f"{BASE_MODEL_NAME}.pt"
