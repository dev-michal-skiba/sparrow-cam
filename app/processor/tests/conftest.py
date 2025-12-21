import logging
from pathlib import Path

import cv2
import pytest


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
def caplog(caplog):
    """Configure caplog for all tests."""
    caplog.set_level(logging.INFO)
    return caplog
