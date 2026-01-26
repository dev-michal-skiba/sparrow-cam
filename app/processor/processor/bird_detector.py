from __future__ import annotations

from ultralytics import YOLO

from processor.types import DetectionBox

BIRD_COCO_CLASS_ID = 14

DEFAULT_DETECTION_PARAMS = {
    "conf": 0.25,
    "imgsz": 480,
    "iou": 0.7,
}


class BirdDetector:
    """Wrapper around YOLO model specialised for bird detection."""

    def __init__(self) -> None:
        self.model = YOLO("yolov8n.pt")
        self.model.fuse()

    def detect(self, frame, **kwargs) -> bool:
        """Return True if at least one bird is detected in the frame."""
        return bool(self.detect_boxes(frame, **kwargs))

    def detect_boxes(self, frame, **kwargs) -> list[DetectionBox]:
        """Return bounding boxes for detected birds in xyxy integer format."""
        params = {**DEFAULT_DETECTION_PARAMS, **kwargs}
        results = self.model(frame, classes=[BIRD_COCO_CLASS_ID], verbose=False, **params)
        if not results or results[0].boxes is None:
            return []

        return [DetectionBox(map(int, box.tolist())) for box in results[0].boxes.xyxy]
