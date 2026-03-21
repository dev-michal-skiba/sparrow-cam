import logging
import os
import time

import cv2

from processor.bird_annotator import BirdAnnotator
from processor.bird_detector import BirdDetector
from processor.hls_watchtower import HLSWatchtower
from processor.stream_archiver import StreamArchiver
from processor.utils import load_detection_preset

logger = logging.getLogger(__name__)

# Detection configuration
DETECTION_FRAME_COUNT = 2  # Number of frames to check for bird detection per segment


def _get_detection_frame_indices(total_frames: int, frame_count: int) -> list[int]:
    """Get frame indices for detection, evenly distributed across segment.

    For frame_count=2: first and middle frame (indices 0, total/2)
    For frame_count=3: first, 1/3, 2/3 (indices 0, total/3, 2*total/3)

    If frame_count >= total_frames, returns all frame indices.
    Ensures no duplicate indices.

    Args:
        total_frames: Total number of frames in the segment.
        frame_count: Number of frames to sample for detection.

    Returns:
        List of unique frame indices to check, in ascending order.
    """
    if frame_count >= total_frames:
        return list(range(total_frames))

    # Calculate evenly distributed indices
    indices = [i * total_frames // frame_count for i in range(frame_count)]

    # Remove duplicates while preserving order
    return list(dict.fromkeys(indices))


class HLSSegmentProcessor:
    """Process HLS segments to detect birds and log metadata."""

    def __init__(self):
        self.bird_detector = BirdDetector()
        self.bird_annotator = BirdAnnotator()
        self.stream_archiver = StreamArchiver()

        # Load detection preset
        preset = load_detection_preset()
        self.detection_params = preset["params"]
        self.detection_regions = preset["regions"]
        logger.info(f"Loaded preset: {len(self.detection_regions)} regions, params={self.detection_params}")

    def process_segment(self, input_segment_path, segment_name):
        """Process a single segment: detect bird across multiple frames and log result.

        Runs detection on DETECTION_FRAME_COUNT frames, evenly distributed across the segment.
        For each frame, detection runs on all configured regions.

        Returns:
            bool: True if bird was detected in any frame/region, False otherwise.
        """
        bird_detected = False
        cap = None

        try:
            cap = cv2.VideoCapture(input_segment_path)
            if not cap.isOpened():
                logger.error(f"{segment_name}: Failed to open video")
                return bird_detected

            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            if total_frames <= 0:
                logger.error(f"{segment_name}: Invalid frame count: {total_frames}")
                return bird_detected

            frame_indices = _get_detection_frame_indices(total_frames, DETECTION_FRAME_COUNT)

            for frame_index in frame_indices:
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
                ret, frame = cap.read()
                if not ret:
                    logger.error(f"{segment_name}: Failed to read frame {frame_index}")
                    continue

                for x1, y1, x2, y2 in self.detection_regions:
                    cropped = frame[y1:y2, x1:x2]
                    if self.bird_detector.detect(cropped, **self.detection_params):
                        bird_detected = True
                        # Early exit once bird is detected
                        break

                if bird_detected:
                    break

            self.bird_annotator.annotate(segment_name, bird_detected)
            if bird_detected:
                logger.info(f"{segment_name}: 'Bird detected'")
        except Exception as e:
            logger.error(f"{segment_name}: Error processing segment - {e}", exc_info=True)
        finally:
            if cap is not None:
                cap.release()

        return bird_detected

    def run(self):
        """Main processing loop."""
        hls_watchtower = HLSWatchtower()
        for input_segment_path in hls_watchtower.segments_iterator:
            segment_name = os.path.basename(input_segment_path)
            start_time = time.time()

            bird_detected = self.process_segment(input_segment_path, segment_name)
            self.stream_archiver.on_segment(segment_name, bird_detected)

            self.bird_annotator.prune(hls_watchtower.seen_segments)
            processing_time = time.time() - start_time
            logger.info(f"{segment_name}: Performance: Processing time: {processing_time:.2f}s")
