import logging
import os
import re
import time

logger = logging.getLogger(__name__)


class HLSWatchtower:
    """Monitor HLS playlist and discover new segments."""

    INPUT_HLS_DIR = "/var/www/html/hls"
    INPUT_PLAYLIST = os.path.join(INPUT_HLS_DIR, "sparrow_cam.m3u8")

    INITIAL_RETRY_DELAY = 1.0  # seconds
    MAX_RETRY_DELAY = 10.0  # seconds
    POLL_INTERVAL = 1.0  # seconds

    def __init__(self):
        self.seen_segments = set()
        self.retry_delay = self.INITIAL_RETRY_DELAY

    def read_playlist(self, playlist_path):
        """Read HLS playlist and extract segment filenames.

        Returns None if playlist is not ready yet (doesn't exist or has no segments).
        Returns list of segment filenames when successfully read.
        """
        # Return None if playlist doesn't exist
        if not os.path.exists(playlist_path):
            logger.info(f"Waiting for playlist: {playlist_path}")
            time.sleep(self.retry_delay)
            self.retry_delay = min(self.retry_delay * 1.5, self.MAX_RETRY_DELAY)
            return None
        # Read input playlist
        with open(playlist_path) as f:
            content = f.read()
        # Extract segment filenames
        segments = re.findall(r"^([a-z0-9_-]+\.ts)$", content, re.MULTILINE)
        # Return None if no segments are found
        if not segments:
            logger.debug("No segments in playlist yet")
            time.sleep(self.POLL_INTERVAL)
            return None
        # Reset retry delay on successful read
        self.retry_delay = self.INITIAL_RETRY_DELAY
        return segments

    @property
    def segments_iterator(self):
        """Iterator that yields new segments as they appear in the playlist.

        Each segment is yielded only once. Returns full path to the segment file.
        """
        while True:
            # Read input playlist and extract segments paths
            segments = self.read_playlist(self.INPUT_PLAYLIST)
            # Continue if no segments are found
            if not segments:
                continue
            # Filter out segments that have already been seen
            new_segments = [segment for segment in segments if segment not in self.seen_segments]
            # Yield new segments
            for segment in new_segments:
                self.seen_segments.add(segment)
                segment_path = os.path.join(self.INPUT_HLS_DIR, segment)
                # Check if segment file exists before yielding
                if os.path.exists(segment_path):
                    yield segment_path
                else:
                    logger.warning(f"Input segment not found: {segment_path}")
            # Clean up old segments from tracking
            self.seen_segments &= set(segments)
            # Sleep for polling interval
            time.sleep(self.POLL_INTERVAL)
