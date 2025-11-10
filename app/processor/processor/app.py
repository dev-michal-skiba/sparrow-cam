import os
import time
import subprocess
import shutil
import logging
import cv2

from processor.hls_watchtower import HLSWatchtower
from processor.bird_detector import BirdDetector

# Configure logging for systemd journal
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Paths - using shared volumes
OUTPUT_HLS_DIR = "/var/www/html/processed_hls"
OUTPUT_PLAYLIST = os.path.join(OUTPUT_HLS_DIR, "sparrow_cam.m3u8")

# Ensure output directory exists
os.makedirs(OUTPUT_HLS_DIR, exist_ok=True)


class HLSSegmentProcessor:
    """Process HLS segments frame-by-frame with grayscale conversion and create output HLS playlist."""

    def __init__(self):
        self.last_playlist_seq = -1
        self.bird_detector = BirdDetector()
        self.detection_results = {}  # segment_name -> bool

    def process_segment(self, input_segment_path, output_segment_path):
        """Process a single segment: detect bird in first frame and copy stream."""
        start_time = time.time()
        cap = None
        temp_output_path = None
        segment_name = os.path.basename(input_segment_path)
        
        try:
            # Open input video to read first frame for detection
            cap = cv2.VideoCapture(input_segment_path)
            if not cap.isOpened():
                logger.error(f"{segment_name}: Failed to open video")
            
            # Read first frame for bird detection
            ret, frame = cap.read()
            if not ret:
                logger.error(f"{segment_name}: Failed to read first frame")
                cap.release()
            
            # Run bird detection on first frame
            bird_detected = self.bird_detector.detect(frame)
            self.detection_results[segment_name] = bird_detected
            logger.info(f"{segment_name}: {'Bird detected' if bird_detected else 'No bird detected'}")

            # Release video capture
            cap.release()
            cap = None
            
            # Use a temporary file first, then move to final location
            temp_output_path = output_segment_path + ".tmp"
            
            # Copy stream using FFmpeg with copy codec (no re-encoding)
            ffmpeg_cmd = [
                'ffmpeg',
                '-y',  # Overwrite output
                '-i', input_segment_path,  # Input file
                '-c:v', 'copy',  # Copy video codec (no re-encoding)
                '-an',  # No audio
                '-f', 'mpegts',  # Output format MPEG-TS
                '-loglevel', 'error',
                temp_output_path
            ]
            
            result = subprocess.run(
                ffmpeg_cmd,
                capture_output=True,
                timeout=30
            )
            
            if result.returncode != 0:
                stderr_output = result.stderr.decode() if result.stderr else ""
                logger.error(f"{segment_name}: FFmpeg copy failed: {stderr_output}")
                if os.path.exists(temp_output_path):
                    os.remove(temp_output_path)
            
            # Move temp file to final location
            shutil.move(temp_output_path, output_segment_path)
            os.chmod(output_segment_path, 0o664)

            # Calculate and print performance metrics
            processing_time = time.time() - start_time
            logger.info(f"{segment_name}: Performance: Processing time: {processing_time:.2f}s")

            self.generate_playlist()

        except Exception as e:
            logger.error(f"Error processing segment: {e}", exc_info=True)
            # Clean up on error
            if temp_output_path and os.path.exists(temp_output_path):
                try:
                    os.remove(temp_output_path)
                except:
                    pass

        finally:
            # Ensure resources are released
            if cap is not None:
                cap.release()

    def generate_playlist(self):
        """Generate HLS playlist with bird detection metadata."""
        try:
            # Read input playlist
            with open(HLSWatchtower.INPUT_PLAYLIST, 'r') as f:
                lines = f.readlines()

            # Rebuild playlist including only processed segments with metadata
            output_lines = []
            i = 0
            while i < len(lines):
                line = lines[i]

                # If this is an EXTINF line, check if next line is a processed segment
                if line.strip().startswith('#EXTINF:'):
                    if i + 1 < len(lines) and lines[i + 1].strip().endswith('.ts'):
                        segment_name = lines[i + 1].strip()

                        # Only include segment if we have detection results for it
                        if segment_name in self.detection_results:
                            output_lines.append(line)  # Add EXTINF line
                            bird_detected = self.detection_results[segment_name]
                            output_lines.append(f'# BIRD-DETECTED:{str(bird_detected).lower()}\n')
                            output_lines.append(lines[i + 1])  # Add segment line
                        # Skip both EXTINF and segment if not processed yet
                        i += 2
                        continue

                # Copy header lines and other non-segment content
                if not line.strip().endswith('.ts'):
                    output_lines.append(line)

                i += 1

            # Write output playlist
            with open(OUTPUT_PLAYLIST, 'w') as f:
                f.writelines(output_lines)
            os.chmod(OUTPUT_PLAYLIST, 0o664)

            logger.info(f"Generated playlist with bird detection metadata")
            return True

        except Exception as e:
            logger.error(f"Error generating playlist: {e}", exc_info=True)
            return False

    def run(self):
        """Main processing loop."""
        hls_watchtower = HLSWatchtower()
        for input_segment_path in hls_watchtower.segments_iterator:
            # Get segment filename and create output path
            segment_name = os.path.basename(input_segment_path)
            output_segment_path = os.path.join(OUTPUT_HLS_DIR, segment_name)
            self.process_segment(input_segment_path, output_segment_path)
            self._cleanup_old_segments(hls_watchtower)

    def _cleanup_old_segments(self, hls_watchtower):
        """Remove output segments that are no longer in the input playlist."""
        # Get current segments from the watchtower's tracking
        current_segments = hls_watchtower.seen_segments  # TODO Segments cleanup should be done based on the generated playlist segments

        # Get all output segment files
        output_files = set()
        if os.path.exists(OUTPUT_HLS_DIR):
            for file in os.listdir(OUTPUT_HLS_DIR):
                if file.endswith('.ts'):
                    output_files.add(file)

        # Remove output files that are no longer in the input playlist
        for output_file in output_files:
            if output_file not in current_segments:
                output_path = os.path.join(OUTPUT_HLS_DIR, output_file)
                os.remove(output_path)
                logger.info(f"Cleaned up old segment: {output_file}")


if __name__ == "__main__":
    processor = HLSSegmentProcessor()
    processor.run()
