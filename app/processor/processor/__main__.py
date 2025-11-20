import logging

from processor.hls_segment_processor import HLSSegmentProcessor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)

processor = HLSSegmentProcessor()
processor.run()
