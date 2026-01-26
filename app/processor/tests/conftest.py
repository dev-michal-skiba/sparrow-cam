import logging
from pathlib import Path

import cv2
import pytest

from processor.utils import load_detection_preset


@pytest.fixture
def data_dir():
    """Return the path to the test data directory."""
    return Path(__file__).parent / "data"


@pytest.fixture
def bird_frame(data_dir):
    """Load test image containing a bird."""
    image_path = data_dir / "bird.png"
    frame = cv2.imread(image_path)
    return frame


@pytest.fixture
def no_bird_frame(data_dir):
    """Load test image without a bird."""
    image_path = data_dir / "no_bird.png"
    frame = cv2.imread(image_path)
    return frame


@pytest.fixture
def preset_detection_parameters():
    """Load detection parameters from preset."""
    preset = load_detection_preset()
    return preset["params"]


@pytest.fixture
def cropped_bird_frame(bird_frame):
    """Return bird frame cropped to first detection region from preset."""
    preset = load_detection_preset()
    x1, y1, x2, y2 = preset["regions"][0]
    return bird_frame[y1:y2, x1:x2]


@pytest.fixture
def caplog(caplog):
    """Configure caplog for all tests."""
    caplog.set_level(logging.INFO)
    return caplog
