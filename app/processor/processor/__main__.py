import logging

from processor.constants import LOG_FORMAT
from processor.hls_segment_processor import HLSSegmentProcessor
from processor.maintenance_window import validate_config

logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT,
    handlers=[logging.StreamHandler()],
)

validate_config()
processor = HLSSegmentProcessor()
processor.run()
