import json
import logging
import os
from typing import TypedDict

logger = logging.getLogger(__name__)

ANNOTATIONS_PATH = "/var/www/html/annotations/bird.json"


class BirdAnnotations(TypedDict):
    version: int
    detections: dict[str, list[dict]]


class BirdAnnotator:
    """Persist bird detection annotations to a JSON sidecar file."""

    def annotate(self, segment_name: str, detections: list[dict]) -> None:
        """Update the annotation store for a given segment."""
        annotations = self._load()
        if detections:
            annotations["detections"][segment_name] = detections
        self._write(annotations)

    def prune(self, valid_segments: set[str]) -> None:
        """Remove annotations for segments that are no longer relevant."""
        annotations = self._load()
        removed = False

        for segment in list(annotations["detections"].keys()):
            if segment not in valid_segments:
                annotations["detections"].pop(segment, None)
                removed = True

        if removed:
            self._write(annotations)

    def _load(self) -> BirdAnnotations:
        try:
            with open(ANNOTATIONS_PATH) as f:
                data = json.load(f)
            if isinstance(data, dict) and "version" in data and "detections" in data:
                return data
        except FileNotFoundError:
            logger.info("Annotations file missing; recreating.")
        except json.JSONDecodeError:
            logger.warning("Annotations file corrupt; resetting.")
        return {"version": 1, "detections": {}}

    def _write(self, annotations: BirdAnnotations) -> None:
        with open(ANNOTATIONS_PATH, "w") as f:
            json.dump(annotations, f)
            os.chmod(ANNOTATIONS_PATH, 0o644)
