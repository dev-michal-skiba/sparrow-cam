import json
import logging
import os
import tempfile
from typing import Dict, Iterable


logger = logging.getLogger(__name__)

ANNOTATIONS_PATH = "/var/www/html/annotations/bird.json"


class BirdAnnotator:
    """Persist bird detection annotations to a JSON sidecar file."""

    def annotate(self, segment_name: str, bird_detected: bool) -> None:
        """Update the annotation store for a given segment."""
        annotations = self._load()
        annotations[segment_name] = {"bird_detected": bool(bird_detected)}
        self._write(annotations)

    def prune(self, valid_segments: Iterable[str]) -> None:
        """Remove annotations for segments that are no longer relevant."""
        annotations = self._load()
        valid_set = set(valid_segments)
        removed = False

        for segment in list(annotations.keys()):
            if segment not in valid_set:
                annotations.pop(segment, None)
                removed = True

        if removed:
            self._write(annotations)

    def _load(self) -> Dict[str, Dict[str, bool]]:
        try:
            with open(ANNOTATIONS_PATH, "r") as f:
                return json.load(f)
        except FileNotFoundError:
            logger.warning("Annotations file missing; recreating.")
        except json.JSONDecodeError:
            logger.warning("Annotations file corrupt; resetting.")
        return {}

    def _write(self, annotations: Dict[str, Dict[str, bool]]) -> None:
        with open(ANNOTATIONS_PATH, "w") as f:
            json.dump(annotations, f)
            os.chmod(ANNOTATIONS_PATH, 0o664)

