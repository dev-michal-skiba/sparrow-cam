import os
import time
import subprocess
import shutil
import logging
import cv2

from processor.hls_watchtower import HLSWatchtower

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

    def process_segment(self, input_segment_path, output_segment_path):
        """Process a single segment file frame-by-frame with grayscale conversion."""
        start_time = time.time()
        cap = None
        ffmpeg_process = None
        temp_output_path = None
        
        try:
            logger.info(f"Processing segment: {os.path.basename(input_segment_path)}")
            
            # Open input video
            cap = cv2.VideoCapture(input_segment_path)
            if not cap.isOpened():
                logger.error(f"Failed to open video: {input_segment_path}")
                return False
            
            # Get video properties
            fps = cap.get(cv2.CAP_PROP_FPS)
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            
            if fps <= 0 or width <= 0 or height <= 0:
                logger.error(f"Invalid video properties: fps={fps}, width={width}, height={height}")
                return False
            
            logger.info(f"  Properties: {width}x{height} @ {fps:.2f} fps, {total_frames} frames")
            
            # Use a temporary file first, then move to final location
            temp_output_path = output_segment_path + ".tmp"
            
            # Start FFmpeg process to encode output video
            # Pipe raw BGR frames to FFmpeg stdin, encode with libx264
            ffmpeg_cmd = [
                'ffmpeg',
                '-y',  # Overwrite output
                '-f', 'rawvideo',
                '-vcodec', 'rawvideo',
                '-pix_fmt', 'bgr24',
                '-s', f'{width}x{height}',
                '-r', str(fps),
                '-i', '-',  # Read from stdin
                '-c:v', 'libx264',  # Use H.264 codec
                '-preset', 'ultrafast',  # Fast encoding for real-time processing
                '-pix_fmt', 'yuv420p',  # Standard pixel format for compatibility
                '-an',  # No audio
                '-f', 'mpegts',  # Explicitly set output format to MPEG-TS
                '-loglevel', 'error',
                temp_output_path
            ]
            
            ffmpeg_process = subprocess.Popen(
                ffmpeg_cmd,
                stdin=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # Process frames
            frame_count = 0
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                # Convert to grayscale
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                
                # Convert back to BGR (3-channel) for video encoding
                gray_bgr = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
                
                # Write frame to FFmpeg stdin
                try:
                    ffmpeg_process.stdin.write(gray_bgr.tobytes())
                except BrokenPipeError:
                    logger.error(f"FFmpeg pipe broken while writing frame {frame_count}")
                    break
                    
                frame_count += 1
            
            # Clean up resources
            cap.release()
            cap = None
            
            # Close FFmpeg stdin and wait for it to finish
            if ffmpeg_process.stdin:
                ffmpeg_process.stdin.close()
            
            ffmpeg_process.wait(timeout=30)
            
            if ffmpeg_process.returncode != 0:
                stderr_output = ffmpeg_process.stderr.read().decode() if ffmpeg_process.stderr else ""
                logger.error(f"FFmpeg encoding failed: {stderr_output}")
                ffmpeg_process = None
                if os.path.exists(temp_output_path):
                    os.remove(temp_output_path)
                return False
            
            ffmpeg_process = None
            
            if frame_count == 0:
                logger.error(f"No frames processed from {input_segment_path}")
                if os.path.exists(temp_output_path):
                    os.remove(temp_output_path)
                return False
            
            # Move temp file to final location
            shutil.move(temp_output_path, output_segment_path)
            os.chmod(output_segment_path, 0o664)
            
            logger.info(f"Successfully processed: {os.path.basename(output_segment_path)} ({frame_count} frames)")

            # Calculate and print performance metrics
            processing_time = time.time() - start_time
            segment_duration = total_frames / fps
            ratio = processing_time / segment_duration if segment_duration > 0 else 0
            logger.info(f"Performance: Processing time: {processing_time:.2f}s vs Segment duration: {segment_duration:.2f}s (ratio: {ratio:.2f}x)")

            return True
            
        except Exception as e:
            logger.error(f"Error processing segment: {e}", exc_info=True)
            # Clean up on error
            if temp_output_path and os.path.exists(temp_output_path):
                try:
                    os.remove(temp_output_path)
                except:
                    pass
            return False
            
        finally:
            # Ensure resources are released
            if cap is not None:
                cap.release()
            if ffmpeg_process is not None:
                try:
                    if ffmpeg_process.stdin:
                        ffmpeg_process.stdin.close()
                    ffmpeg_process.terminate()
                    ffmpeg_process.wait(timeout=5)
                except:
                    pass

    def copy_playlist(self):
        """Copy HLS playlist from input to output."""
        shutil.copy2(HLSWatchtower.INPUT_PLAYLIST, OUTPUT_PLAYLIST)
        os.chmod(OUTPUT_PLAYLIST, 0o664)
        logger.info(f"Copied playlist: {os.path.basename(HLSWatchtower.INPUT_PLAYLIST)}")
        return True

    def run(self):
        """Main processing loop."""
        hls_watchtower = HLSWatchtower()
        for input_segment_path in hls_watchtower.segments_iterator:
            # Get segment filename and create output path
            segment_name = os.path.basename(input_segment_path)
            output_segment_path = os.path.join(OUTPUT_HLS_DIR, segment_name)

            # Process the segment
            if self.process_segment(input_segment_path, output_segment_path):
                # Copy playlist after successful processing
                self.copy_playlist()  # TODO Playlist should be generated, not copied
            else:
                logger.error(f"Failed to process {segment_name}, skipping")

            # Clean up old output segments that are no longer in the input playlist
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
