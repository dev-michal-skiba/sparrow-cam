from __future__ import annotations

from ultralytics import YOLO

from processor.types import DetectionBox

BIRD_COCO_CLASS_ID = 14
IMAGE_SIZE_FOR_DETECTION = 480


class BirdDetector:
    """Wrapper around YOLO model specialised for bird detection."""

    def __init__(self) -> None:
        self.model = YOLO("yolov8n.pt")
        self.model.fuse()

    def detect(self, frame) -> bool:
        """Return True if at least one bird is detected in the frame."""
        return bool(self.detect_boxes(frame))

    def detect_boxes(self, frame) -> list[DetectionBox]:
        """Return bounding boxes for detected birds in xyxy integer format."""
        results = self.model(frame, classes=[BIRD_COCO_CLASS_ID], imgsz=IMAGE_SIZE_FOR_DETECTION, verbose=False)
        if not results or results[0].boxes is None:
            return []

        return [DetectionBox(map(int, box.tolist())) for box in results[0].boxes.xyxy]
