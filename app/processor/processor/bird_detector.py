from __future__ import annotations

import logging
from pathlib import Path

from ultralytics import YOLO

from processor.types import DetectionBox

logger = logging.getLogger(__name__)

DEFAULT_MODEL_PATH = str(Path(__file__).parent / "model.pt")

# Class IDs in the fine-tuned model
GREAT_TIT_CLASS_ID = 0
PIGEON_CLASS_ID = 2

DEFAULT_DETECTION_PARAMS = {
    "conf": 0.25,
    "imgsz": 480,
    "iou": 0.7,
}


class BirdDetector:
    """Wrapper around YOLO model specialised for bird detection."""

    def __init__(self, model_path: str | None = None, classes: list[int] | None = None) -> None:
        if model_path is None:
            model_path = DEFAULT_MODEL_PATH
        self.model = YOLO(model_path)
        self.model.fuse()
        self._classes = classes if classes is not None else [GREAT_TIT_CLASS_ID, PIGEON_CLASS_ID]

    def detect(self, frame, **kwargs) -> bool:
        """Return True if at least one bird is detected in the frame."""
        return bool(self.detect_boxes(frame, **kwargs))

    def detect_boxes(self, frame, class_thresholds: dict[int, float] | None = None, **kwargs) -> list[DetectionBox]:
        """Return bounding boxes for detected birds in xyxy integer format.

        Args:
            class_thresholds: Optional per-class confidence thresholds. When provided, the minimum
                threshold is used for the YOLO model call, and results are filtered per-class after.
        """
        params = {**DEFAULT_DETECTION_PARAMS, **kwargs}
        if class_thresholds:
            params["conf"] = min(class_thresholds.values())
        results = self.model(frame, classes=self._classes, verbose=False, **params)
        if not results or results[0].boxes is None:
            return []

        boxes = [
            DetectionBox(int(box[0]), int(box[1]), int(box[2]), int(box[3]), int(cls), float(conf))
            for box, cls, conf in zip(results[0].boxes.xyxy, results[0].boxes.cls, results[0].boxes.conf)
        ]

        if class_thresholds:
            boxes = [b for b in boxes if b.confidence >= class_thresholds.get(b.class_id, 0.0)]

        return boxes

    def class_name(self, class_id: int) -> str:
        """Return the human-readable class name for a given class ID."""
        return str(self.model.names.get(class_id, class_id))
