import logging
import os

import cv2
import pytest


@pytest.fixture
def bird_frame():
    """Load test image containing a bird."""
    test_data_dir = os.path.join(os.path.dirname(__file__), "data")
    image_path = os.path.join(test_data_dir, "bird.png")
    frame = cv2.imread(image_path)
    return frame


@pytest.fixture
def no_bird_frame():
    """Load test image without a bird."""
    test_data_dir = os.path.join(os.path.dirname(__file__), "data")
    image_path = os.path.join(test_data_dir, "no_bird.png")
    frame = cv2.imread(image_path)
    return frame


@pytest.fixture
def caplog(caplog):
    """Configure caplog for all tests."""
    caplog.set_level(logging.INFO)
    return caplog
