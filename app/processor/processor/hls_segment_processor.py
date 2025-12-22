import logging
import os
import time

import cv2

from processor.bird_annotator import BirdAnnotator
from processor.bird_detector import BirdDetector
from processor.hls_watchtower import HLSWatchtower
from processor.stream_archiver import StreamArchiver

logger = logging.getLogger(__name__)


class HLSSegmentProcessor:
    """Process HLS segments to detect birds and log metadata."""

    def __init__(self):
        self.bird_detector = BirdDetector()
        self.bird_annotator = BirdAnnotator()
        self.stream_archiver = StreamArchiver()

    def process_segment(self, input_segment_path, segment_name):
        """Process a single segment: detect bird in first frame and log result."""
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
            if bird_detected:
                self.stream_archiver.archive(limit=1)
            self.bird_annotator.annotate(segment_name, bird_detected)
            logger.info(f"{segment_name}: {'Bird detected' if bird_detected else 'No bird detected'}")
        except Exception as e:
            logger.error(f"{segment_name}: Error processing segment - {e}", exc_info=True)
        finally:
            if cap is not None:
                cap.release()

    def run(self):
        """Main processing loop."""
        hls_watchtower = HLSWatchtower()
        for input_segment_path in hls_watchtower.segments_iterator:
            segment_name = os.path.basename(input_segment_path)
            start_time = time.time()
            self.process_segment(input_segment_path, segment_name)
            self.bird_annotator.prune(hls_watchtower.seen_segments)
            processing_time = time.time() - start_time
            logger.info(f"{segment_name}: Performance: Processing time: {processing_time:.2f}s")
