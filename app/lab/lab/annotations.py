"""Annotation business logic: YOLO dataset management, train/val split, save/load."""

from __future__ import annotations

import random
import shutil
from dataclasses import dataclass
from pathlib import Path

from lab.constants import DATASET_DIR

AVAILABLE_CLASSES: list[tuple[str, int]] = [
    ("Great tit", 0),
    ("House sparrow", 1),
    ("Pigeon", 2),
]


def class_name_for_id(class_id: int) -> str:
    """Return the display name for a class_id. Falls back to first class if not found."""
    for name, cid in AVAILABLE_CLASSES:
        if cid == class_id:
            return name
    return AVAILABLE_CLASSES[0][0]


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


@dataclass
class ClassStats:
    """Stats for a single bird class."""

    name: str
    class_id: int
    train_count: int
    val_count: int


@dataclass
class ExtendedDatasetStats:
    """Extended dataset stats including per-class information."""

    train_total: int
    train_positive: int
    train_negative: int
    val_total: int
    val_positive: int
    val_negative: int
    class_stats: list[ClassStats]


def ensure_dataset_structure() -> None:
    """Create dataset directory tree and always rewrite dataset.yaml with current classes."""
    for split in ("train", "val"):
        (DATASET_DIR / "images" / split).mkdir(parents=True, exist_ok=True)
        (DATASET_DIR / "labels" / split).mkdir(parents=True, exist_ok=True)

    yaml_path = DATASET_DIR / "dataset.yaml"
    names_section = "\n".join(f"  {cid}: {name.lower().replace(' ', '_')}" for name, cid in AVAILABLE_CLASSES)
    yaml_content = f"path: ../dataset\ntrain: images/train\nval: images/val\nnames:\n{names_section}\n"
    yaml_path.write_text(yaml_content)


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


def choose_split(class_ids: set[int]) -> str:
    """
    Randomly choose 'train' or 'val' weighted to maintain ~80/20 ratio.

    For negative samples (empty class_ids set): counts only the same category
    to adjust probability so each category independently corrects imbalances.

    For positive samples: counts per-class across train/val, finds the class
    with the worst imbalance, and uses that to decide the split.
    """
    if not class_ids:
        # Negative sample: use existing positive/negative balancing logic
        train_pos, train_neg = _count_split_stats("train")
        val_pos, val_neg = _count_split_stats("val")
        train_count, val_count = train_neg, val_neg
    else:
        # Positive sample: find the class with worst imbalance among class_ids
        train_stats = _count_class_stats("train")
        val_stats = _count_class_stats("val")

        worst_imbalance = -1
        worst_class_train_count = 0
        worst_class_val_count = 0

        for class_id in class_ids:
            train_count = train_stats.get(class_id, 0)
            val_count = val_stats.get(class_id, 0)
            total = train_count + val_count
            if total > 0:
                # Calculate how far from 80/20
                target_train = 0.8 * total
                imbalance = abs(train_count - target_train)
                if imbalance > worst_imbalance:
                    worst_imbalance = imbalance
                    worst_class_train_count = train_count
                    worst_class_val_count = val_count

        train_count = worst_class_train_count
        val_count = worst_class_val_count

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
        class_ids = {b.class_id for b in boxes}
        split = choose_split(class_ids)
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


def get_extended_dataset_stats() -> ExtendedDatasetStats:
    """Get dataset stats including per-class information."""
    train_pos, train_neg = _count_split_stats("train")
    val_pos, val_neg = _count_split_stats("val")

    train_class_counts = _count_class_stats("train")
    val_class_counts = _count_class_stats("val")

    class_stats_list = []
    for class_name, class_id in AVAILABLE_CLASSES:
        train_count = train_class_counts.get(class_id, 0)
        val_count = val_class_counts.get(class_id, 0)
        class_stats_list.append(
            ClassStats(
                name=class_name,
                class_id=class_id,
                train_count=train_count,
                val_count=val_count,
            )
        )

    return ExtendedDatasetStats(
        train_total=train_pos + train_neg,
        train_positive=train_pos,
        train_negative=train_neg,
        val_total=val_pos + val_neg,
        val_positive=val_pos,
        val_negative=val_neg,
        class_stats=class_stats_list,
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


def _count_class_stats(split: str) -> dict[int, int]:
    """Count how many label files contain each class_id."""
    labels_dir = DATASET_DIR / "labels" / split
    class_counts: dict[int, int] = {}
    if not labels_dir.exists():
        return class_counts
    for label_file in labels_dir.iterdir():
        if label_file.suffix != ".txt":
            continue
        content = label_file.read_text().strip()
        if not content:
            continue
        # Track which classes appear in this file
        classes_in_file: set[int] = set()
        for line in content.splitlines():
            parts = line.strip().split()
            if len(parts) >= 1:
                try:
                    class_id = int(parts[0])
                    classes_in_file.add(class_id)
                except ValueError:
                    pass
        # Increment count for each class found in this file
        for class_id in classes_in_file:
            class_counts[class_id] = class_counts.get(class_id, 0) + 1
    return class_counts


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
