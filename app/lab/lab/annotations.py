"""Annotation business logic: YOLO dataset management, train/val split, save/load."""

from __future__ import annotations

import random
import shutil
from dataclasses import dataclass
from pathlib import Path

from lab.constants import DATASET_DIR

AVAILABLE_CLASSES: list[tuple[str, int]] = [
    ("Great tit", 0),
]


@dataclass
class AnnotationBox:
    """A YOLO-format bounding box (all values normalized 0-1)."""

    class_id: int
    x_center: float
    y_center: float
    width: float
    height: float


@dataclass
class DatasetStats:
    train_total: int
    train_positive: int
    train_negative: int
    val_total: int
    val_positive: int
    val_negative: int


def ensure_dataset_structure() -> None:
    """Create dataset directory tree and dataset.yaml if they don't exist."""
    for split in ("train", "val"):
        (DATASET_DIR / "images" / split).mkdir(parents=True, exist_ok=True)
        (DATASET_DIR / "labels" / split).mkdir(parents=True, exist_ok=True)

    yaml_path = DATASET_DIR / "dataset.yaml"
    if not yaml_path.exists():
        yaml_path.write_text(
            "path: ../dataset\n" "train: images/train\n" "val: images/val\n" "names:\n" "  0: great_tit\n"
        )


def get_dataset_filename(image_path: Path, recording_path: Path) -> str:
    """
    Return a unique stem for dataset files.

    Format: {recording_folder_name}_{image_stem}
    Example: auto_2026-01-15T064557Z_5d83d036-..._sparrow_cam-1488-0
    """
    return f"{recording_path.name}_{image_path.stem}"


def find_existing(image_path: Path, recording_path: Path) -> tuple[str, list[AnnotationBox]] | None:
    """
    Search for an existing annotation for this image.

    Returns (split, boxes) if found, None otherwise.
    """
    stem = get_dataset_filename(image_path, recording_path)
    for split in ("train", "val"):
        label_path = DATASET_DIR / "labels" / split / f"{stem}.txt"
        if label_path.exists():
            boxes = _read_label_file(label_path)
            return split, boxes
    return None


def choose_split(is_positive: bool) -> str:
    """
    Randomly choose 'train' or 'val' weighted to maintain ~80/20 ratio.

    Counts only the same category (positive or negative) to adjust
    probability so each category independently corrects imbalances over time.
    """
    train_pos, train_neg = _count_split_stats("train")
    val_pos, val_neg = _count_split_stats("val")

    if is_positive:
        train_count, val_count = train_pos, val_pos
    else:
        train_count, val_count = train_neg, val_neg

    total = train_count + val_count
    if total == 0:
        prob_train = 0.8
    else:
        target_train = 0.8 * (total + 1)
        prob_train = max(0.0, min(1.0, target_train - train_count))
    return "train" if random.random() < prob_train else "val"  # nosec B311


def save_annotations(
    image_path: Path,
    recording_path: Path,
    boxes: list[AnnotationBox],
) -> None:
    """
    Save image and its YOLO label file into the dataset.

    If the image was previously annotated its split is preserved; otherwise
    a weighted random split is chosen. On edit, only the label file is overwritten.
    An empty boxes list produces a negative sample (empty .txt).
    """
    ensure_dataset_structure()

    stem = get_dataset_filename(image_path, recording_path)

    existing = find_existing(image_path, recording_path)
    if existing is not None:
        split = existing[0]
        # Image already in dataset, just overwrite the label
    else:
        split = choose_split(is_positive=bool(boxes))
        # New annotation, copy the image
        dest_image = DATASET_DIR / "images" / split / f"{stem}.png"
        shutil.copy2(image_path, dest_image)

    dest_label = DATASET_DIR / "labels" / split / f"{stem}.txt"
    _write_label_file(dest_label, boxes)


def get_annotation_status(image_path: Path, recording_path: Path) -> str:
    """
    Return annotation status for a frame.

    Returns one of:
        "False"           -- not yet annotated
        "True [positive]" -- annotated with at least one bounding box
        "True [negative]" -- annotated as negative (empty label file)
    """
    existing = find_existing(image_path, recording_path)
    if existing is None:
        return "False"
    _, boxes = existing
    return "True [positive]" if boxes else "True [negative]"


def load_annotations(image_path: Path, recording_path: Path) -> list[AnnotationBox]:
    """Load existing annotation boxes for a frame (empty list if negative or not found)."""
    existing = find_existing(image_path, recording_path)
    if existing is None:
        return []
    _, boxes = existing
    return boxes


def get_dataset_stats() -> DatasetStats:
    """Count images in dataset and classify each as positive or negative."""
    train_pos, train_neg = _count_split_stats("train")
    val_pos, val_neg = _count_split_stats("val")
    return DatasetStats(
        train_total=train_pos + train_neg,
        train_positive=train_pos,
        train_negative=train_neg,
        val_total=val_pos + val_neg,
        val_positive=val_pos,
        val_negative=val_neg,
    )


def pixels_to_yolo(
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    img_width: int,
    img_height: int,
    class_id: int = 0,
) -> AnnotationBox:
    """Convert pixel rectangle to a normalized YOLO AnnotationBox."""
    bx = ((x1 + x2) / 2) / img_width
    by = ((y1 + y2) / 2) / img_height
    bw = abs(x2 - x1) / img_width
    bh = abs(y2 - y1) / img_height
    return AnnotationBox(class_id=class_id, x_center=bx, y_center=by, width=bw, height=bh)


def yolo_to_pixels(box: AnnotationBox, img_width: int, img_height: int) -> tuple[int, int, int, int]:
    """Convert a normalized YOLO AnnotationBox back to pixel (x1, y1, x2, y2)."""
    cx = box.x_center * img_width
    cy = box.y_center * img_height
    w = box.width * img_width
    h = box.height * img_height
    x1 = int(cx - w / 2)
    y1 = int(cy - h / 2)
    x2 = int(cx + w / 2)
    y2 = int(cy + h / 2)
    return x1, y1, x2, y2


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _count_split_stats(split: str) -> tuple[int, int]:
    """Return (positive_count, negative_count) for a split."""
    labels_dir = DATASET_DIR / "labels" / split
    if not labels_dir.exists():
        return 0, 0
    positive = 0
    negative = 0
    for label_file in labels_dir.iterdir():
        if label_file.suffix != ".txt":
            continue
        content = label_file.read_text().strip()
        if content:
            positive += 1
        else:
            negative += 1
    return positive, negative


def _read_label_file(path: Path) -> list[AnnotationBox]:
    boxes: list[AnnotationBox] = []
    content = path.read_text().strip()
    if not content:
        return boxes
    for line in content.splitlines():
        parts = line.strip().split()
        if len(parts) != 5:
            continue
        class_id, x_center, y_center, width, height = parts
        boxes.append(
            AnnotationBox(
                class_id=int(class_id),
                x_center=float(x_center),
                y_center=float(y_center),
                width=float(width),
                height=float(height),
            )
        )
    return boxes


def _write_label_file(path: Path, boxes: list[AnnotationBox]) -> None:
    lines = [f"{b.class_id} {b.x_center:.6f} {b.y_center:.6f} {b.width:.6f} {b.height:.6f}" for b in boxes]
    path.write_text("\n".join(lines))
