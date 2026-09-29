import logging
from pathlib import Path
from unittest.mock import MagicMock

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
def caplog(caplog):
    """Configure caplog for all tests."""
    caplog.set_level(logging.INFO)
    return caplog


@pytest.fixture(autouse=True)
def mock_index_db(monkeypatch):
    """Mock index_db.write_recording to prevent database access in tests."""
    from processor import index_db

    mock_write = MagicMock()
    monkeypatch.setattr(index_db, "write_recording", mock_write)
    return mock_write
