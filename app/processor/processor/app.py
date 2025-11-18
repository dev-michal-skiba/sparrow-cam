import os
import time
import logging
import cv2

from processor.hls_watchtower import HLSWatchtower
from processor.bird_detector import BirdDetector
from processor.bird_annotator import BirdAnnotator

# Configure logging for systemd journal
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)


class HLSSegmentProcessor:
    """Process HLS segments to detect birds and log metadata."""

    def __init__(self):
        self.bird_detector = BirdDetector()
        self.bird_annotator = BirdAnnotator()

    def process_segment(self, input_segment_path):
        """Process a single segment: detect bird in first frame and log result."""
        start_time = time.time()
        segment_name = os.path.basename(input_segment_path)
        bird_detected = False
        cap = None

        try:
            cap = cv2.VideoCapture(input_segment_path)
            if not cap.isOpened():
                logger.error(f"{segment_name}: Failed to open video")
                return

            ret, frame = cap.read()
            if not ret:
                logger.error(f"{segment_name}: Failed to read first frame")
                return

            bird_detected = self.bird_detector.detect(frame)
            self.bird_annotator.annotate(segment_name, bird_detected)
            logger.info(f"{segment_name}: {'Bird detected' if bird_detected else 'No bird detected'}")
            processing_time = time.time() - start_time
            logger.info(f"{segment_name}: Performance: Processing time: {processing_time:.2f}s")
        except Exception as e:
            logger.error(f"Error processing segment: {e}", exc_info=True)

        finally:
            if cap is not None:
                cap.release()

    def run(self):
        """Main processing loop."""
        hls_watchtower = HLSWatchtower()
        for input_segment_path in hls_watchtower.segments_iterator:
            self.process_segment(input_segment_path)
            self.bird_annotator.prune(hls_watchtower.seen_segments)


if __name__ == "__main__":
    processor = HLSSegmentProcessor()
    processor.run()
