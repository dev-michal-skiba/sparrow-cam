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

# Tkinter hex colors for the GUI legend per class_id
BIRD_CLASS_TK_COLORS: dict[int, str] = {
    0: "#00ff00",  # Great tit → green
    1: "#0000ff",  # House sparrow → blue
    2: "#ff0000",  # Pigeon → red
}
_DEFAULT_TK_COLOR: str = "#ffa500"  # Orange for unknown classes


def _hex_to_bgr(hex_color: str) -> tuple[int, int, int]:
    r = int(hex_color[1:3], 16)
    g = int(hex_color[3:5], 16)
    b = int(hex_color[5:7], 16)
    return (b, g, r)


_DEFAULT_BOX_COLOR: tuple[int, int, int] = _hex_to_bgr(_DEFAULT_TK_COLOR)


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


def annotate_frame(frame, boxes: list):
    annotated = frame.copy()
    for box in boxes:
        class_id = getattr(box, "class_id", None)
        tk_color = BIRD_CLASS_TK_COLORS.get(class_id, _DEFAULT_TK_COLOR)
        color = _hex_to_bgr(tk_color)
        cv2.rectangle(annotated, (box[0], box[1]), (box[2], box[3]), color=color, thickness=2)
    return annotated


def get_annotated_image_bytes(
    detector: BirdDetector,
    image_path: Path | None,
    *,
    regions: list[Region] | None = None,
    detected_classes_out: set[int] | None = None,
    **kwargs,
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
                DetectionBox(
                    box[0] + region.x1,
                    box[1] + region.y1,
                    box[2] + region.x1,
                    box[3] + region.y1,
                    getattr(box, "class_id", 0),
                )
                for box in region_boxes
            )
    else:
        boxes = detector.detect_boxes(frame, **kwargs)

    if not boxes:
        raise UserFacingError("No bird detected", "No birds were found in the selected image.", severity="info")

    if detected_classes_out is not None:
        detected_classes_out.update(getattr(box, "class_id", 0) for box in boxes)

    annotated = annotate_frame(frame, boxes)

    success, encoded = cv2.imencode(".png", annotated)
    if not success:
        raise UserFacingError("Preview error", "Could not render annotated preview.")

    return base64.b64encode(encoded.tobytes())
