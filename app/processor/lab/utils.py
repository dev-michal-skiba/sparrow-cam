"""Business logic utilities for bird detection and image processing."""

from __future__ import annotations

import base64
from pathlib import Path

import cv2

from lab.constants import IMAGES_DIR
from lab.exception import UserFacingError
from processor.bird_detector import BirdDetector
from processor.types import DetectionBox


def is_outside_storage(boundary_dir: Path, path: Path) -> bool:
    try:
        path.relative_to(boundary_dir)
        return False
    except ValueError:
        return True


def validate_selected_image(selected_path: Path) -> None:
    if is_outside_storage(IMAGES_DIR, selected_path):
        raise UserFacingError("Invalid selection", f"Please choose a file inside {IMAGES_DIR}")

    if selected_path.suffix.lower() != ".png":
        raise UserFacingError("Invalid file", "Only .png files are allowed.")


def load_frame(image_path: Path):
    frame = cv2.imread(str(image_path))
    if frame is None:
        raise UserFacingError("Load error", f"Could not read image at {image_path}")
    return frame


def annotate_frame(frame, boxes: list[DetectionBox]):
    annotated = frame.copy()
    for x1, y1, x2, y2 in boxes:
        cv2.rectangle(annotated, (x1, y1), (x2, y2), color=(0, 255, 0), thickness=2)
    return annotated


def get_annotated_image_bytes(detector: BirdDetector, image_path: Path | None) -> bytes:
    if image_path is None:
        raise UserFacingError("No image selected", "Please select an image first.")
    frame = load_frame(image_path)
    boxes = detector.detect_boxes(frame)
    if not boxes:
        raise UserFacingError("No bird detected", "No birds were found in the selected image.", severity="info")
    annotated = annotate_frame(frame, boxes)

    success, encoded = cv2.imencode(".png", annotated)
    if not success:
        raise UserFacingError("Preview error", "Could not render annotated preview.")

    return base64.b64encode(encoded.tobytes())
