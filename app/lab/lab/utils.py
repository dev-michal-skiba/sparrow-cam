"""Business logic utilities for bird detection and image processing."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from pathlib import Path

import cv2
from processor.bird_detector import BirdDetector
from processor.types import DetectionBox

from lab.constants import IMAGES_DIR
from lab.exception import UserFacingError


@dataclass
class Region:
    """A rectangular region defined by (x1, y1, x2, y2) coordinates."""

    x1: int
    y1: int
    x2: int
    y2: int


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


def get_annotated_image_bytes(
    detector: BirdDetector, image_path: Path | None, *, regions: list[Region] | None = None, **kwargs
) -> bytes:
    if image_path is None:
        raise UserFacingError("No image selected", "Please select an image first.")
    frame = load_frame(image_path)

    boxes: list[DetectionBox] = []
    if regions:
        # Run detection on each selected region
        for region in regions:
            cropped = frame[region.y1 : region.y2, region.x1 : region.x2]
            region_boxes = detector.detect_boxes(cropped, **kwargs)
            # Offset box coordinates back to full image coordinates
            boxes.extend(
                DetectionBox((box[0] + region.x1, box[1] + region.y1, box[2] + region.x1, box[3] + region.y1))
                for box in region_boxes
            )
    else:
        boxes = detector.detect_boxes(frame, **kwargs)

    if not boxes:
        raise UserFacingError("No bird detected", "No birds were found in the selected image.", severity="info")
    annotated = annotate_frame(frame, boxes)

    success, encoded = cv2.imencode(".png", annotated)
    if not success:
        raise UserFacingError("Preview error", "Could not render annotated preview.")

    return base64.b64encode(encoded.tobytes())
