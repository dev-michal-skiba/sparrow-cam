"""Fine tune the base YOLO model into a generic bird detector, ignoring bird type."""

from __future__ import annotations

import argparse
import json
import logging
import random
import re
import shutil
from datetime import UTC, datetime
from pathlib import Path

from lab.constants import BASE_MODEL_NAME, BASE_MODEL_PATH, DATASET_DIR, FINE_TUNED_DIR
from lab.frame_selection import Frame, dataset_seed, load_frames, select_frames

logger = logging.getLogger(__name__)

# How many frames of each kind the training subset should hold
POSITIVE_FRAMES = 365
NEGATIVE_FRAMES = 55

# Training parameters; imgsz matches the processor's detection parameters
EPOCHS = 100
BATCH = 16
IMGSZ = 640

# This model is the first pipeline step, so every annotation collapses onto one class
BIRD_CLASS_ID = 0
BIRD_CLASS_NAME = "bird"

VERSION_PATTERN = re.compile(r"^v\d+\.\d+\.\d+$")
DESCRIPTION_MAX_LENGTH = 1024


class FineTuneError(Exception):
    """Raised when fine tuning cannot proceed."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", help="Model version, e.g. v1.0.0. Prompted for if omitted.")
    parser.add_argument("--description", help="Model description. Prompted for if omitted.")
    return parser.parse_args()


def resolve_version(version: str | None) -> str:
    if version is None:
        return prompt_version()
    if not VERSION_PATTERN.match(version):
        raise FineTuneError("Version must look like v1.0.0")
    return version


def resolve_description(description: str | None) -> str:
    if description is None:
        return prompt_description()
    if not 0 < len(description) <= DESCRIPTION_MAX_LENGTH:
        raise FineTuneError(f"Description must be 1 to {DESCRIPTION_MAX_LENGTH} characters")
    return description


def prompt_version() -> str:
    while True:
        version = input("Model version (e.g. v1.0.0): ").strip()
        if VERSION_PATTERN.match(version):
            return version
        print("Version must look like v1.0.0")


def prompt_description() -> str:
    while True:
        description = input(f"Model description (max {DESCRIPTION_MAX_LENGTH} characters): ").strip()
        if 0 < len(description) <= DESCRIPTION_MAX_LENGTH:
            return description
        print(f"Description must be 1 to {DESCRIPTION_MAX_LENGTH} characters")


def select_training_frames() -> list[Frame]:
    """Pick the balanced training subset from the synced dataset."""
    frames = load_frames(DATASET_DIR)
    if not frames:
        raise FineTuneError(f"No dataset frames found under {DATASET_DIR}")

    rng = random.Random(dataset_seed(frames))  # nosec B311
    positives = select_frames([frame for frame in frames if frame.is_positive], POSITIVE_FRAMES, rng)
    negatives = select_frames([frame for frame in frames if not frame.is_positive], NEGATIVE_FRAMES, rng)
    logger.info(f"Selected {len(positives)} positive and {len(negatives)} negative frame(s)")
    return positives + negatives


def build_dataset(frames: list[Frame], dataset_dir: Path) -> Path:
    """Copy the selected frames into the model directory and write its dataset.yaml."""
    images_dir = dataset_dir / "images"
    labels_dir = dataset_dir / "labels"
    images_dir.mkdir(parents=True)
    labels_dir.mkdir(parents=True)

    for frame in frames:
        shutil.copy2(frame.image_path, images_dir / frame.image_path.name)
        (labels_dir / frame.label_path.name).write_text(_generic_label(frame.label_path))

    yaml_path = dataset_dir / "dataset.yaml"
    yaml_path.write_text(
        f"path: {dataset_dir}\ntrain: images\nval: images\nnames:\n  {BIRD_CLASS_ID}: {BIRD_CLASS_NAME}\n"
    )
    return yaml_path


def train(dataset_yaml: Path, output_dir: Path) -> Path:
    """Fine tune the base model and return the path to the best weights."""
    from ultralytics import YOLO  # imported here to avoid a slow import when only selecting frames

    runs_dir = output_dir / "runs"
    YOLO(str(BASE_MODEL_PATH)).train(
        data=str(dataset_yaml),
        epochs=EPOCHS,
        batch=BATCH,
        imgsz=IMGSZ,
        project=str(runs_dir),
        name="train",
        exist_ok=True,
    )

    best_weights = runs_dir / "train" / "weights" / "best.pt"
    if not best_weights.is_file():
        raise FineTuneError(f"Training produced no weights at {best_weights}")
    return best_weights


def _generic_label(label_path: Path) -> str:
    """Rewrite a label file so every box belongs to the single bird class."""
    lines = [
        " ".join([str(BIRD_CLASS_ID), *line.split()[1:]])
        for line in label_path.read_text().splitlines()
        if line.strip()
    ]
    return "".join(f"{line}\n" for line in lines)


def _write_metadata(output_dir: Path, version: str, description: str) -> None:
    metadata = {
        "version": version,
        "description": description,
        "created_at": datetime.now(UTC).isoformat(),
    }
    (output_dir / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler()],
    )

    args = parse_args()
    version = resolve_version(args.version)
    description = resolve_description(args.description)

    model_name = f"{BASE_MODEL_NAME}_{version}"
    output_dir = FINE_TUNED_DIR / model_name
    if output_dir.exists():
        raise FineTuneError(f"Model directory already exists: {output_dir}")

    frames = select_training_frames()

    output_dir.mkdir(parents=True)
    dataset_yaml = build_dataset(frames, output_dir / "dataset")

    model_path = output_dir / f"{model_name}.pt"
    shutil.copy2(train(dataset_yaml, output_dir), model_path)
    _write_metadata(output_dir, version, description)

    logger.info(f"Fine tuned model saved to {model_path}")


if __name__ == "__main__":
    main()
