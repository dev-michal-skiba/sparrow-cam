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

# Archive configuration
ARCHIVE_SEGMENT_COUNT = 15  # Total segments to archive
ARCHIVE_DELAY_SEGMENTS = 7  # Segments to wait after detection (bird in middle = 8th position)

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

        # Archive state tracking
        self.segment_counter = 0  # Increments with each segment processed
        self.last_archived_counter = None  # Counter value of last segment in previous archive
        self.pending_archive_countdown = None  # Countdown until archive trigger (None = no pending)

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
            logger.info(f"{segment_name}: {'Bird detected' if bird_detected else 'No bird detected'}")
        except Exception as e:
            logger.error(f"{segment_name}: Error processing segment - {e}", exc_info=True)
        finally:
            if cap is not None:
                cap.release()

        return bird_detected

    def schedule_archive(self, segment_name):
        """Schedule an archive to trigger after ARCHIVE_DELAY_SEGMENTS more segments.

        Handles overlap prevention: if detection is within 7 segments of last archive,
        the archive will start from the segment after the last archived segment.

        Args:
            segment_name: Name of the segment where bird was detected.
        """
        if self.pending_archive_countdown is not None:
            # Archive already scheduled, ignore additional detections
            logger.debug(f"{segment_name}: Archive already scheduled, ignoring detection")
            return

        # Add 1 to account for decrement happening on this same segment in check_and_execute_archive
        self.pending_archive_countdown = ARCHIVE_DELAY_SEGMENTS + 1
        logger.info(f"{segment_name}: Bird detected, archive scheduled in {ARCHIVE_DELAY_SEGMENTS} segments")

    def check_and_execute_archive(self, segment_name):
        """Check if archive should be triggered and execute if so.

        Args:
            segment_name: Name of the current segment (will be the end segment of archive).
        """
        if self.pending_archive_countdown is None:
            return

        self.pending_archive_countdown -= 1

        if self.pending_archive_countdown <= 0:
            logger.info(
                f"{segment_name}: Executing scheduled archive: "
                f"limit={ARCHIVE_SEGMENT_COUNT}, prefix=auto, end_segment={segment_name}"
            )
            self.stream_archiver.archive(
                limit=ARCHIVE_SEGMENT_COUNT,
                prefix="auto",
                end_segment=segment_name,
            )
            self.last_archived_counter = self.segment_counter
            self.pending_archive_countdown = None

    def run(self):
        """Main processing loop."""
        hls_watchtower = HLSWatchtower()
        for input_segment_path in hls_watchtower.segments_iterator:
            segment_name = os.path.basename(input_segment_path)
            self.segment_counter += 1
            start_time = time.time()

            bird_detected = self.process_segment(input_segment_path, segment_name)

            if bird_detected:
                # Check overlap: if within 7 segments of last archive, don't schedule new archive
                # (the countdown will continue from previous detection)
                if self.pending_archive_countdown is None:
                    # Check if we're in the overlap zone (within 7 segments of last archive)
                    in_overlap_zone = (
                        self.last_archived_counter is not None
                        and self.segment_counter <= self.last_archived_counter + ARCHIVE_DELAY_SEGMENTS
                    )
                    if in_overlap_zone:
                        # Start archive from segment after last archived (no centering)
                        # Calculate how many segments until we have 15 from last_archived_counter + 1
                        segments_since_last_archive = self.segment_counter - self.last_archived_counter
                        # Add 1 to account for decrement happening on this same segment
                        remaining = ARCHIVE_SEGMENT_COUNT - segments_since_last_archive + 1
                        self.pending_archive_countdown = remaining
                        logger.info(
                            f"{segment_name}: Bird in overlap zone, archive in {remaining - 1} segments "
                            f"(starting from segment after last archive)"
                        )
                    else:
                        self.schedule_archive(segment_name)

            self.check_and_execute_archive(segment_name)
            self.bird_annotator.prune(hls_watchtower.seen_segments)
            processing_time = time.time() - start_time
            logger.info(f"{segment_name}: Performance: Processing time: {processing_time:.2f}s")
