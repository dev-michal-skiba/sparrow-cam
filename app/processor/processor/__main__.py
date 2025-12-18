import logging

from processor.constants import LOG_FORMAT
from processor.hls_segment_processor import HLSSegmentProcessor

logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT,
    handlers=[logging.StreamHandler()],
)

processor = HLSSegmentProcessor()
processor.run()
