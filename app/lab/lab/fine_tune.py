"""Fine-tuning logic: dataset preparation and YOLOv8n model training."""

from __future__ import annotations

import json
import re
import shutil
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import cv2

from lab.constants import DATASET_DIR, FINE_TUNED_MODELS_DIR

_VERSION_PATTERN = re.compile(r"^v\d+\.\d+\.\d+$")
_DEFAULT_IMGSZ = 480
_DEFAULT_EPOCHS = 100
_DEFAULT_BATCH = 16
_BASE_MODEL = "yolov8n.pt"


def validate_version(version: str) -> bool:
    """Return True if version matches v<major>.<minor>.<patch> format."""
    return bool(_VERSION_PATTERN.match(version))


def get_available_models() -> list[dict]:
    """
    Scan FINE_TUNED_MODELS_DIR for available models.

    Returns a list of model dicts sorted by created_at descending (newest first).
    Each dict contains:
    - version: folder name
    - model_path: absolute path to model.pt
    - description: from meta.json
    - base_model: from meta.json
    - classes: dict from meta.json (e.g., {"0": "great_tit"})
    - created_at: ISO timestamp from meta.json
    - is_base: True if this is the yolov8n.pt base model

    Also includes a "yolov8n.pt" entry at the end with is_base=True.
    """
    models: list[dict] = []

    # Scan FINE_TUNED_MODELS_DIR for fine-tuned models
    if FINE_TUNED_MODELS_DIR.exists():
        for version_dir in FINE_TUNED_MODELS_DIR.iterdir():
            if not version_dir.is_dir():
                continue

            meta_path = version_dir / "meta.json"
            model_path = version_dir / "model.pt"

            if not meta_path.exists() or not model_path.exists():
                continue

            try:
                with open(meta_path) as f:
                    meta = json.load(f)

                models.append(
                    {
                        "version": version_dir.name,
                        "model_path": str(model_path),
                        "description": meta.get("description", ""),
                        "base_model": meta.get("base_model", ""),
                        "classes": meta.get("classes"),
                        "created_at": meta.get("created_at", ""),
                        "is_base": False,
                    }
                )
            except (json.JSONDecodeError, OSError):
                continue

    # Sort by created_at descending (newest first)
    models.sort(key=lambda m: m["created_at"], reverse=True)

    # Add base model entry
    models.append(
        {
            "version": "yolov8n.pt",
            "model_path": "yolov8n.pt",
            "description": "Base model",
            "base_model": "None",
            "classes": None,
            "created_at": "",
            "is_base": True,
        }
    )

    return models


def load_preset(preset_path: Path) -> dict:
    """
    Load and validate a preset JSON file.

    Raises ValueError if the preset does not contain exactly one region.
    """
    with open(preset_path) as f:
        preset = json.load(f)

    regions = preset.get("regions", [])
    if len(regions) != 1:
        raise ValueError(
            f"Preset must define exactly one detection region, " f"but '{preset_path.name}' has {len(regions)}."
        )
    return preset


def _parse_dataset_yaml(dataset_dir: Path) -> dict[str, str]:
    """
    Parse dataset.yaml and return the names mapping {str_id: class_name}.

    Supports simple YAML with 'names:' block using '  <id>: <name>' lines.
    """
    yaml_path = dataset_dir / "dataset.yaml"
    names: dict[str, str] = {}
    in_names = False
    for line in yaml_path.read_text().splitlines():
        if line.strip().startswith("names:"):
            in_names = True
            continue
        if in_names:
            if line and not line[0].isspace():
                break
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if ":" in stripped:
                key, _, val = stripped.partition(":")
                names[key.strip()] = val.strip()
    return names


def _remap_label_line(
    line: str,
    orig_w: int,
    orig_h: int,
    rx1: int,
    ry1: int,
    rx2: int,
    ry2: int,
) -> str | None:
    """
    Remap a single YOLO label line from full-image coords to cropped-region coords.

    Returns the remapped line, or None if the box center falls outside the crop.
    """
    parts = line.strip().split()
    if len(parts) != 5:
        return None

    class_id = parts[0]
    cx_norm = float(parts[1])
    cy_norm = float(parts[2])
    w_norm = float(parts[3])
    h_norm = float(parts[4])

    # Convert to absolute pixel coords in original image
    cx_abs = cx_norm * orig_w
    cy_abs = cy_norm * orig_h
    w_abs = w_norm * orig_w
    h_abs = h_norm * orig_h

    region_w = rx2 - rx1
    region_h = ry2 - ry1

    # Translate center to region-relative coords
    cx_rel = cx_abs - rx1
    cy_rel = cy_abs - ry1

    # Drop boxes whose center falls outside the crop
    if not (0 <= cx_rel <= region_w and 0 <= cy_rel <= region_h):
        return None

    # Normalize by region size
    cx_new = cx_rel / region_w
    cy_new = cy_rel / region_h
    w_new = w_abs / region_w
    h_new = h_abs / region_h

    # Clip to [0, 1]
    cx_new = max(0.0, min(1.0, cx_new))
    cy_new = max(0.0, min(1.0, cy_new))
    w_new = max(0.0, min(1.0, w_new))
    h_new = max(0.0, min(1.0, h_new))

    return f"{class_id} {cx_new:.6f} {cy_new:.6f} {w_new:.6f} {h_new:.6f}"


def prepare_cropped_dataset(
    source_dir: Path,
    dest_dir: Path,
    region: tuple[int, int, int, int],
) -> None:
    """
    Build a cropped dataset at dest_dir from source_dir.

    For each image: read, crop to region, save to dest.
    For each label: read, remap boxes to cropped coords, save to dest.
    Writes a new dataset.yaml pointing to dest_dir.
    """
    rx1, ry1, rx2, ry2 = region

    for split in ("train", "val"):
        dest_images = dest_dir / "images" / split
        dest_labels = dest_dir / "labels" / split
        dest_images.mkdir(parents=True, exist_ok=True)
        dest_labels.mkdir(parents=True, exist_ok=True)

        src_images_dir = source_dir / "images" / split
        src_labels_dir = source_dir / "labels" / split

        if not src_images_dir.exists():
            continue

        for img_path in src_images_dir.glob("*.png"):
            frame = cv2.imread(str(img_path))
            if frame is None:
                continue

            orig_h, orig_w = frame.shape[:2]
            cropped = frame[ry1:ry2, rx1:rx2]
            cv2.imwrite(str(dest_images / img_path.name), cropped)

            # Remap corresponding label file
            src_label = src_labels_dir / (img_path.stem + ".txt")
            dest_label = dest_labels / (img_path.stem + ".txt")

            if src_label.exists():
                remapped_lines = []
                for raw_line in src_label.read_text().splitlines():
                    if not raw_line.strip():
                        continue
                    remapped = _remap_label_line(raw_line, orig_w, orig_h, rx1, ry1, rx2, ry2)
                    if remapped is not None:
                        remapped_lines.append(remapped)
                dest_label.write_text("\n".join(remapped_lines))
            else:
                dest_label.write_text("")

    # Write dataset.yaml with absolute path to dest_dir
    names = _parse_dataset_yaml(source_dir)
    names_lines = "\n".join(f"  {k}: {v}" for k, v in names.items())
    yaml_content = f"path: {dest_dir}\n" "train: images/train\n" "val: images/val\n" f"names:\n{names_lines}\n"
    (dest_dir / "dataset.yaml").write_text(yaml_content)


def run_fine_tune(
    version: str,
    description: str,
    preset_path: Path | None = None,
    on_epoch: Callable[[int, int], None] | None = None,
) -> Path:
    """
    Fine-tune YOLOv8n and save model + metadata to FINE_TUNED_MODELS_DIR/version/.

    If preset_path is given, the dataset is first cropped to the preset's single
    detection region and imgsz is taken from the preset. Otherwise the original
    DATASET_DIR is used with default imgsz.

    on_epoch, if provided, is called after each training epoch with
    (current_epoch: int, total_epochs: int) -- both 1-based / absolute count.

    Returns the output directory path.
    """
    from ultralytics import YOLO  # imported here to avoid slow startup at module load

    output_dir = FINE_TUNED_MODELS_DIR / version
    output_dir.mkdir(parents=True, exist_ok=True)

    imgsz = _DEFAULT_IMGSZ
    dataset_yaml: Path
    preset_name: str | None = None

    if preset_path is not None:
        preset = load_preset(preset_path)
        preset_name = preset_path.name
        region_list = preset["regions"][0]
        region = (int(region_list[0]), int(region_list[1]), int(region_list[2]), int(region_list[3]))
        imgsz = int(preset.get("params", {}).get("imgsz", _DEFAULT_IMGSZ))

        cropped_dataset_dir = output_dir / "dataset"
        prepare_cropped_dataset(DATASET_DIR, cropped_dataset_dir, region)
        dataset_yaml = cropped_dataset_dir / "dataset.yaml"
    else:
        dataset_yaml = DATASET_DIR / "dataset.yaml"

    # Use a temp runs dir inside output_dir to keep ultralytics artefacts contained
    runs_dir = output_dir / "runs"
    runs_dir.mkdir(exist_ok=True)

    model = YOLO(_BASE_MODEL)

    if on_epoch is not None:
        total = _DEFAULT_EPOCHS

        def _epoch_callback(trainer) -> None:
            on_epoch(trainer.epoch + 1, total)

        model.add_callback("on_train_epoch_end", _epoch_callback)

    results = model.train(
        data=str(dataset_yaml),
        epochs=_DEFAULT_EPOCHS,
        batch=_DEFAULT_BATCH,
        imgsz=imgsz,
        project=str(runs_dir),
        name="train",
        exist_ok=True,
    )

    # Copy best weights to output dir
    best_weights = runs_dir / "train" / "weights" / "best.pt"
    if best_weights.exists():
        shutil.copy2(best_weights, output_dir / "model.pt")

    # Extract metrics from results
    metrics: dict = {}
    if results is not None:
        try:
            metrics = {
                "mAP50": float(results.results_dict.get("metrics/mAP50(B)", 0)),
                "precision": float(results.results_dict.get("metrics/precision(B)", 0)),
                "recall": float(results.results_dict.get("metrics/recall(B)", 0)),
            }
        except (AttributeError, TypeError):
            pass

    # Parse class names from the dataset yaml that was actually used
    class_names = _parse_dataset_yaml(dataset_yaml.parent)

    meta = {
        "version": version,
        "description": description,
        "base_model": _BASE_MODEL,
        "created_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "classes": class_names,
        "preset": preset_name,
        "training": {
            "epochs": _DEFAULT_EPOCHS,
            "batch": _DEFAULT_BATCH,
            "imgsz": imgsz,
            "dataset": str(dataset_yaml),
        },
        "metrics": metrics,
    }

    (output_dir / "meta.json").write_text(json.dumps(meta, indent=2))

    # Clean up runs dir to save space (best.pt already copied)
    shutil.rmtree(runs_dir, ignore_errors=True)

    return output_dir
