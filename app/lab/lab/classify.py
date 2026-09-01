"""Train the stage-2 species classifier on crops taken from stage-1 detection frames.

Stage 1 is a high-recall generic bird detector that over-fires false positives. This
stage trains a YOLO classification model on crops of the stage-1 detections so the
pipeline can reject non-birds and name the species. It mirrors the fine-tune flow.
"""

from __future__ import annotations

import json
import logging
import random
import shutil
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np

from lab.constants import (
    BASE_MODEL_PATH,
    CLS_BASE_MODEL_NAME,
    CLS_BASE_MODEL_PATH,
    DATASET_DIR,
    FINE_TUNED_DIR,
)
from lab.fine_tune import (
    BATCH,
    EPOCHS,
    IMGSZ,
    _write_metadata,
    parse_args,
    resolve_description,
    resolve_version,
)
from lab.frame_selection import Frame, dataset_seed, load_frames, select_frames

logger = logging.getLogger(__name__)

# Salt for the frame seed so this stage picks a different subset than the stage-1 fine-tune.
DATASET_SALT = "stage2"

# Frame budget, larger than the stage-1 fine-tune: this stage trains on crops (roughly one
# per labelled box), so it needs more frames to gather enough samples per species.
POSITIVE_FRAMES = 730
NEGATIVE_FRAMES = 110

# Species class names, ordered so their index matches the class id archive_api writes into
# dataset label files (each species' position in archive_api's BirdClass enum).
SPECIES_CLASSES = ("great_tit", "house_sparrow", "pigeon", "eurasian_nuthatch")
BACKGROUND_CLASS = "background"

# COCO bird class id the stage-1 base model fires on; its boxes on bird-free frames are
# exactly the false positives this stage learns to reject, so they become hard negatives.
BASE_BIRD_CLASS_ID = 14
HARD_NEGATIVE_PARAMS = {"conf": 0.05, "imgsz": IMGSZ, "iou": 0.7}

# Background crops taken at random from each bird-free frame, sized as a fraction of the frame.
RANDOM_CROPS_PER_NEGATIVE = 4
RANDOM_CROP_MIN_FRAC = 0.15
RANDOM_CROP_MAX_FRAC = 0.5

# Target crop count per class; classes with fewer available crops are kept whole with a warning.
CROPS_PER_CLASS = 500


class ClassifyError(Exception):
    """Raised when classifier training cannot proceed."""


def select_training_frames() -> tuple[list[Frame], list[Frame], random.Random]:
    """Pick the stage-2 training subset, salted so it differs from the stage-1 selection."""
    frames = load_frames(DATASET_DIR)
    if not frames:
        raise ClassifyError(f"No dataset frames found under {DATASET_DIR}")

    rng = random.Random(dataset_seed(frames, salt=DATASET_SALT))  # nosec B311
    positives = select_frames([frame for frame in frames if frame.is_positive], POSITIVE_FRAMES, rng)
    negatives = select_frames([frame for frame in frames if not frame.is_positive], NEGATIVE_FRAMES, rng)
    logger.info(f"Selected {len(positives)} positive and {len(negatives)} negative frame(s)")
    return positives, negatives, rng


def build_dataset(positives: list[Frame], negatives: list[Frame], dataset_dir: Path, rng: random.Random) -> list[str]:
    """Write an ultralytics classification dataset (train/<class>/*.jpg) and return the class list."""
    crops_by_class: dict[str, list[np.ndarray]] = defaultdict(list)

    for frame in positives:
        image = cv2.imread(str(frame.image_path))
        if image is None:
            continue
        for class_id, box in _read_boxes(frame.label_path):
            crop = _crop_norm(image, box)
            if crop.size:
                crops_by_class[SPECIES_CLASSES[class_id]].append(crop)

    detector = _load_base_detector()
    for frame in negatives:
        image = cv2.imread(str(frame.image_path))
        if image is None:
            continue
        crops_by_class[BACKGROUND_CLASS].extend(_random_crops(image, rng))
        crops_by_class[BACKGROUND_CLASS].extend(_hard_negative_crops(detector, image))

    class_names = [*SPECIES_CLASSES, BACKGROUND_CLASS]
    train_dir = dataset_dir / "train"
    for class_name in class_names:
        crops = _balance(crops_by_class.get(class_name, []), class_name, rng)
        class_dir = train_dir / class_name
        class_dir.mkdir(parents=True)
        for index, crop in enumerate(crops):
            cv2.imwrite(str(class_dir / f"{index:05d}.jpg"), crop)
        logger.info(f"Wrote {len(crops)} {class_name} crop(s)")

    # Ultralytics classification needs a val split; mirror the fine-tune flow, which
    # evaluates on the training images rather than holding any data out.
    (dataset_dir / "val").symlink_to("train", target_is_directory=True)

    # Ultralytics indexes classes by sorted folder name, so store the class list the same way.
    return sorted(class_names)


def train(dataset_dir: Path, output_dir: Path) -> Path:
    """Train the classifier and return the path to the best weights."""
    from ultralytics import YOLO  # imported here to avoid a slow import when only selecting frames

    runs_dir = output_dir / "runs"
    YOLO(str(CLS_BASE_MODEL_PATH)).train(
        data=str(dataset_dir),
        epochs=EPOCHS,
        batch=BATCH,
        imgsz=IMGSZ,
        project=str(runs_dir),
        name="train",
        exist_ok=True,
    )

    best_weights = runs_dir / "train" / "weights" / "best.pt"
    if not best_weights.is_file():
        raise ClassifyError(f"Training produced no weights at {best_weights}")
    return best_weights


def _read_boxes(label_path: Path) -> list[tuple[int, tuple[float, float, float, float]]]:
    """Parse `class_id cx cy w h` label lines into (class id, normalised xywh) pairs."""
    boxes = []
    for line in label_path.read_text().splitlines():
        parts = line.split()
        if len(parts) != 5:
            continue
        class_id = int(parts[0])
        cx, cy, width, height = (float(part) for part in parts[1:])
        boxes.append((class_id, (cx, cy, width, height)))
    return boxes


def _crop_norm(image: np.ndarray, box: tuple[float, float, float, float]) -> np.ndarray:
    """Crop a normalised-xywh box out of an image, clamped to its bounds."""
    height, width = image.shape[:2]
    cx, cy, box_w, box_h = box
    x1 = max(0, int((cx - box_w / 2) * width))
    y1 = max(0, int((cy - box_h / 2) * height))
    x2 = min(width, int((cx + box_w / 2) * width))
    y2 = min(height, int((cy + box_h / 2) * height))
    return image[y1:y2, x1:x2]


def _random_crops(image: np.ndarray, rng: random.Random) -> list[np.ndarray]:
    """Take a few random sub-rectangles of the frame as easy background samples."""
    height, width = image.shape[:2]
    crops = []
    for _ in range(RANDOM_CROPS_PER_NEGATIVE):
        crop_w = int(width * rng.uniform(RANDOM_CROP_MIN_FRAC, RANDOM_CROP_MAX_FRAC))
        crop_h = int(height * rng.uniform(RANDOM_CROP_MIN_FRAC, RANDOM_CROP_MAX_FRAC))
        if crop_w == 0 or crop_h == 0:
            continue
        x = rng.randint(0, width - crop_w)
        y = rng.randint(0, height - crop_h)
        crops.append(image[y : y + crop_h, x : x + crop_w])
    return crops


def _load_base_detector():
    from ultralytics import YOLO  # imported here to avoid a slow import when only selecting frames

    return YOLO(str(BASE_MODEL_PATH))


def _hard_negative_crops(detector, image: np.ndarray) -> list[np.ndarray]:
    """Crop every box the stage-1 base model fires on a bird-free frame."""
    results = detector(image, classes=[BASE_BIRD_CLASS_ID], verbose=False, **HARD_NEGATIVE_PARAMS)
    if not results or results[0].boxes is None:
        return []
    crops = []
    for box in results[0].boxes.xyxy:
        x1, y1, x2, y2 = (int(value) for value in box)
        crop = image[y1:y2, x1:x2]
        if crop.size:
            crops.append(crop)
    return crops


def _balance(crops: list[np.ndarray], class_name: str, rng: random.Random) -> list[np.ndarray]:
    """Down-sample a class to the target crop count, or keep all with a warning if short."""
    if len(crops) <= CROPS_PER_CLASS:
        if len(crops) < CROPS_PER_CLASS:
            logger.warning(
                f"Only {len(crops)} of the {CROPS_PER_CLASS} requested {class_name} "
                "crop(s) available; using all of them"
            )
        return crops
    return rng.sample(crops, CROPS_PER_CLASS)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler()],
    )

    args = parse_args()
    version = resolve_version(args.version)
    description = resolve_description(args.description)

    model_name = f"{CLS_BASE_MODEL_NAME}_{version}"
    output_dir = FINE_TUNED_DIR / model_name
    if output_dir.exists():
        raise ClassifyError(f"Model directory already exists: {output_dir}")

    positives, negatives, rng = select_training_frames()

    output_dir.mkdir(parents=True)
    dataset_dir = output_dir / "dataset"
    class_names = build_dataset(positives, negatives, dataset_dir, rng)

    model_path = output_dir / f"{model_name}.pt"
    shutil.copy2(train(dataset_dir, output_dir), model_path)
    (output_dir / "classes.json").write_text(json.dumps(class_names, indent=2) + "\n")
    _write_metadata(output_dir, version, description)

    logger.info(f"Stage-2 classifier saved to {model_path}")


if __name__ == "__main__":
    main()
