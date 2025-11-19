from ultralytics import YOLO

BIRD_COCO_CLASS_ID = 14
IMAGE_SIZE_FOR_DETECTION = 480


class BirdDetector:

    def __init__(self):
        self.model = YOLO("yolov8n.pt")
        self.model.fuse()

    def detect(self, frame) -> bool:
        results = self.model(frame, classes=[BIRD_COCO_CLASS_ID], imgsz=IMAGE_SIZE_FOR_DETECTION, verbose=False)
        return results[0].boxes is not None and len(results[0].boxes) > 0
