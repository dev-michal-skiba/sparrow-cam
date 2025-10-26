import os
import time
import subprocess
import re
import shutil
import logging
from pathlib import Path
import cv2

# Configure logging for systemd journal
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Paths - using shared volumes
INPUT_HLS_DIR = "/var/www/html/hls"
OUTPUT_HLS_DIR = "/var/www/html/processed_hls"
INPUT_PLAYLIST = os.path.join(INPUT_HLS_DIR, "sparrow_cam.m3u8")
OUTPUT_PLAYLIST = os.path.join(OUTPUT_HLS_DIR, "sparrow_cam.m3u8")

# Ensure output directory exists
os.makedirs(OUTPUT_HLS_DIR, exist_ok=True)


class HLSSegmentProcessor:
    """Process HLS segments frame-by-frame with grayscale conversion and create output HLS playlist."""

    INITIAL_RETRY_DELAY = 1  # seconds
    MAX_RETRY_DELAY = 10  # seconds

    def __init__(self):
        self.processed_segments = set()
        self.last_playlist_seq = -1

    def read_playlist(self, playlist_path):
        """Read HLS playlist and extract segment filenames and media sequence."""
        try:
            with open(playlist_path, 'r') as f:
                content = f.read()

            # Extract media sequence
            media_seq_match = re.search(r'#EXT-X-MEDIA-SEQUENCE:(\d+)', content)
            media_seq = int(media_seq_match.group(1)) if media_seq_match else 0

            # Extract segment filenames
            segments = re.findall(r'^([a-z0-9_-]+\.ts)$', content, re.MULTILINE)
            return segments, media_seq

        except Exception as e:
            logger.error(f"Error reading playlist: {e}")
            return [], -1

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
        try:
            shutil.copy2(INPUT_PLAYLIST, OUTPUT_PLAYLIST)
            os.chmod(OUTPUT_PLAYLIST, 0o664)
            logger.info(f"Copied playlist: {os.path.basename(INPUT_PLAYLIST)}")
            return True

        except Exception as e:
            logger.error(f"Error copying playlist: {e}")
            return False

    def run(self):
        """Main processing loop."""
        retry_delay = self.INITIAL_RETRY_DELAY

        logger.info(f"HLS Segment Processor started")
        logger.info(f"Input HLS directory: {INPUT_HLS_DIR}")
        logger.info(f"Output HLS directory: {OUTPUT_HLS_DIR}")
        logger.info(f"Processing .ts segments with grayscale conversion and copying .m3u8 playlist")

        while True:
            try:
                # Check if input playlist exists
                if not os.path.exists(INPUT_PLAYLIST):
                    logger.warning(f"Waiting for playlist: {INPUT_PLAYLIST}")
                    time.sleep(retry_delay)
                    retry_delay = min(retry_delay * 1.5, self.MAX_RETRY_DELAY)
                    continue

                # Read input playlist
                segments, media_seq = self.read_playlist(INPUT_PLAYLIST)

                if not segments:
                    logger.debug("No segments in playlist yet")
                    time.sleep(1)
                    continue

                retry_delay = self.INITIAL_RETRY_DELAY

                # Process new segments
                processed_any = False
                for segment in segments:
                    if segment not in self.processed_segments:
                        input_path = os.path.join(INPUT_HLS_DIR, segment)
                        output_path = os.path.join(OUTPUT_HLS_DIR, segment)

                        if os.path.exists(input_path):
                            if self.process_segment(input_path, output_path):
                                self.processed_segments.add(segment)
                                processed_any = True
                            else:
                                logger.warning(f"Failed to process {segment}, will retry")
                                # Don't add to processed_segments so we retry
                        else:
                            logger.warning(f"Input segment not found: {input_path}")

                # Copy playlist if we processed segments
                if processed_any or media_seq != self.last_playlist_seq:
                    self.copy_playlist()
                    self.last_playlist_seq = media_seq

                # Clean up old segments we're no longer tracking
                # Keep only the segments currently in the playlist
                current_segment_set = set(segments)
                old_segments = self.processed_segments - current_segment_set
                for old_segment in old_segments:
                    output_path = os.path.join(OUTPUT_HLS_DIR, old_segment)
                    try:
                        if os.path.exists(output_path):
                            os.remove(output_path)
                            logger.info(f"Cleaned up old segment: {old_segment}")
                    except Exception as e:
                        logger.error(f"Error cleaning up {old_segment}: {e}")

                self.processed_segments &= current_segment_set

                time.sleep(1)

            except KeyboardInterrupt:
                logger.info("Shutting down gracefully...")
                break
            except Exception as e:
                logger.error(f"Error in segment processing loop: {e}", exc_info=True)
                time.sleep(retry_delay)
                retry_delay = min(retry_delay * 1.5, self.MAX_RETRY_DELAY)


if __name__ == "__main__":
    processor = HLSSegmentProcessor()
    processor.run()
