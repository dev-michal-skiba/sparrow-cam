"""Unit tests for lab/utils.py business logic."""

import base64
from pathlib import Path
from unittest.mock import Mock, patch

import numpy as np
import pytest

from lab.exception import UserFacingError
from lab.utils import (
    Region,
    annotate_frame,
    get_annotated_image_bytes,
    is_outside_storage,
    load_frame,
    validate_selected_image,
)


class TestIsOutsideStorage:
    """Tests for is_outside_storage function."""

    def test_path_inside_storage_returns_false(self, tmp_path):
        boundary_dir = tmp_path / "images"
        boundary_dir.mkdir()
        file_path = boundary_dir / "file.png"

        assert is_outside_storage(boundary_dir, file_path) is False

    def test_path_outside_storage_returns_true(self, tmp_path):
        boundary_dir = tmp_path / "images"
        boundary_dir.mkdir()
        outside_path = tmp_path / "outside" / "file.png"

        assert is_outside_storage(boundary_dir, outside_path) is True

    def test_nested_path_inside_storage(self, tmp_path):
        boundary_dir = tmp_path / "images"
        boundary_dir.mkdir()
        nested_path = boundary_dir / "subdir" / "file.png"

        assert is_outside_storage(boundary_dir, nested_path) is False

    def test_sibling_directory_is_outside(self, tmp_path):
        boundary_dir = tmp_path / "images"
        boundary_dir.mkdir()
        sibling = tmp_path / "other_dir" / "file.png"

        assert is_outside_storage(boundary_dir, sibling) is True


class TestValidateSelectedImage:
    """Tests for validate_png_selection function."""

    def test_valid_png_inside_storage_passes(self, tmp_path):
        boundary_dir = tmp_path / "images"
        boundary_dir.mkdir()
        file_path = boundary_dir / "image.png"

        with patch("lab.utils.IMAGES_DIR", boundary_dir):
            result = validate_selected_image(file_path)

        assert result is None

    def test_file_outside_storage_raises_user_error(self, tmp_path):
        boundary_dir = tmp_path / "images"
        boundary_dir.mkdir()
        outside_path = tmp_path / "outside.png"

        with patch("lab.utils.IMAGES_DIR", boundary_dir):
            with pytest.raises(UserFacingError) as exc_info:
                validate_selected_image(outside_path)

        assert exc_info.value.title == "Invalid selection"
        assert exc_info.value.message == f"Please choose a file inside {boundary_dir}"

    def test_non_png_file_raises_user_error(self, tmp_path):
        boundary_dir = tmp_path / "storage"
        boundary_dir.mkdir()
        file_path = boundary_dir / "image.jpg"

        with patch("lab.utils.IMAGES_DIR", boundary_dir):
            with pytest.raises(UserFacingError) as exc_info:
                validate_selected_image(file_path)

        assert exc_info.value.title == "Invalid file"
        assert exc_info.value.message == "Only .png files are allowed."

    def test_uppercase_png_extension_passes(self, tmp_path):
        boundary_dir = tmp_path / "storage"
        boundary_dir.mkdir()
        file_path = boundary_dir / "image.PNG"

        with patch("lab.utils.IMAGES_DIR", boundary_dir):
            result = validate_selected_image(file_path)

        assert result is None

    def test_mixed_case_png_extension_passes(self, tmp_path):
        boundary_dir = tmp_path / "storage"
        boundary_dir.mkdir()
        file_path = boundary_dir / "image.Png"

        with patch("lab.utils.IMAGES_DIR", boundary_dir):
            result = validate_selected_image(file_path)

        assert result is None


class TestLoadFrame:
    """Tests for load_frame function."""

    def test_load_valid_png_returns_frame(self, data_dir):
        frame = load_frame(data_dir / "bird.png")

        assert frame is not None
        assert isinstance(frame, np.ndarray)
        assert frame.shape[2] == 3  # BGR

    def test_load_nonexistent_file_raises_error(self, data_dir):
        nonexistent = data_dir / "nonexistent.png"

        with pytest.raises(UserFacingError) as exc_info:
            load_frame(nonexistent)

        assert exc_info.value.title == "Load error"
        assert exc_info.value.message == f"Could not read image at {nonexistent}"

    def test_load_error_message_includes_path(self, data_dir):
        nonexistent = data_dir / "nonexistent.png"

        with pytest.raises(UserFacingError) as exc_info:
            load_frame(nonexistent)

        assert exc_info.value.title == "Load error"
        assert exc_info.value.message == f"Could not read image at {nonexistent}"


class TestAnnotateFrame:
    """Tests for annotate_frame function."""

    def test_no_boxes_returns_copy_of_frame(self, bird_frame):
        result = annotate_frame(bird_frame, [])

        assert result is not bird_frame  # Should be a copy
        assert np.array_equal(result, bird_frame)

    def test_single_box_annotation(self, bird_frame):
        boxes = [(10, 10, 50, 50)]
        result = annotate_frame(bird_frame, boxes)

        # Check that the result has rectangles drawn (pixels changed)
        assert not np.array_equal(result, bird_frame)

    def test_multiple_boxes_annotation(self, bird_frame):
        boxes = [(10, 10, 50, 50), (100, 100, 150, 150), (200, 200, 250, 250)]
        result = annotate_frame(bird_frame, boxes)

        # Check that the result has rectangles drawn
        assert not np.array_equal(result, bird_frame)

    def test_boxes_with_negative_coords(self):
        # Create a small test frame
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        boxes = [(-10, -10, 30, 30)]  # Partially out of bounds

        # Should not raise
        result = annotate_frame(frame, boxes)
        assert result is not None

    def test_annotate_does_not_modify_original_frame(self, bird_frame):
        original_copy = bird_frame.copy()
        boxes = [(10, 10, 50, 50)]

        annotate_frame(bird_frame, boxes)

        assert np.array_equal(bird_frame, original_copy)


class TestgetAnnotatedImageBytes:
    """Tests for get_annotated_image_bytes function."""

    @pytest.fixture
    def mock_detector(self):
        """Create a mock BirdDetector."""
        detector = Mock()
        return detector

    def test_get_annotated_image_bytes_with_detections(self, mock_detector, data_dir):
        # Setup
        boxes = [(10, 10, 50, 50), (100, 100, 150, 150)]
        mock_detector.detect_boxes.return_value = boxes

        # Execute
        result = get_annotated_image_bytes(mock_detector, data_dir / "bird.png")

        # Assert
        assert isinstance(result, bytes)
        assert len(result) > 0
        mock_detector.detect_boxes.assert_called_once()

    def test_get_annotated_image_bytes_no_detections_raises_error(self, mock_detector, data_dir):
        # Setup
        mock_detector.detect_boxes.return_value = []

        # Execute and assert
        with pytest.raises(UserFacingError) as exc_info:
            get_annotated_image_bytes(mock_detector, data_dir / "bird.png")

        assert exc_info.value.title == "No bird detected"
        assert exc_info.value.message == "No birds were found in the selected image."
        assert exc_info.value.severity == "info"

    def test_get_annotated_image_bytes_invalid_image_path(self, mock_detector):
        # Setup
        nonexistent_path = Path("/nonexistent/path/image.png")

        # Execute and assert
        with pytest.raises(UserFacingError) as exc_info:
            get_annotated_image_bytes(mock_detector, nonexistent_path)

        assert exc_info.value.title == "Load error"
        assert exc_info.value.message == f"Could not read image at {nonexistent_path}"

    def test_get_annotated_image_bytes_returns_b64_encoded_png(self, mock_detector, data_dir):
        # Setup
        boxes = [(10, 10, 50, 50)]
        mock_detector.detect_boxes.return_value = boxes

        # Execute
        result = get_annotated_image_bytes(mock_detector, data_dir / "bird.png")

        # Assert - verify it's valid base64
        try:
            decoded = base64.b64decode(result)
            assert len(decoded) > 0
        except Exception:
            pytest.fail("result is not valid base64")

    def test_get_annotated_image_bytes_with_single_box(self, mock_detector, data_dir):
        # Setup
        boxes = [(50, 50, 100, 100)]
        mock_detector.detect_boxes.return_value = boxes

        # Execute
        result = get_annotated_image_bytes(mock_detector, data_dir / "bird.png")

        # Assert
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_get_annotated_image_bytes_with_many_boxes(self, mock_detector, data_dir):
        # Setup
        boxes = [(i * 10, i * 10, i * 10 + 40, i * 10 + 40) for i in range(5)]
        mock_detector.detect_boxes.return_value = boxes

        # Execute
        result = get_annotated_image_bytes(mock_detector, data_dir / "bird.png")

        # Assert
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_get_annotated_image_bytes_none_image_path_raises_error(self, mock_detector):
        # Execute and assert
        with pytest.raises(UserFacingError) as exc_info:
            get_annotated_image_bytes(mock_detector, None)

        assert exc_info.value.title == "No image selected"
        assert exc_info.value.message == "Please select an image first."

    def test_get_annotated_image_bytes_encoding_failure_raises_error(self, mock_detector, data_dir):
        # Setup
        boxes = [(10, 10, 50, 50)]
        mock_detector.detect_boxes.return_value = boxes

        # Mock cv2.imencode to fail
        with patch("lab.utils.cv2.imencode", return_value=(False, None)):
            # Execute and assert
            with pytest.raises(UserFacingError) as exc_info:
                get_annotated_image_bytes(mock_detector, data_dir / "bird.png")

            assert exc_info.value.title == "Preview error"
            assert exc_info.value.message == "Could not render annotated preview."

    def test_get_annotated_image_bytes_with_regions(self, mock_detector, data_dir):
        """Test get_annotated_image_bytes with selected regions."""
        # Setup
        boxes = [(10, 10, 50, 50)]
        mock_detector.detect_boxes.return_value = boxes
        regions = [Region(20, 20, 100, 100)]

        # Execute
        result = get_annotated_image_bytes(mock_detector, data_dir / "bird.png", regions=regions)

        # Assert
        assert isinstance(result, bytes)
        assert len(result) > 0
        # Verify detector was called for the cropped region
        mock_detector.detect_boxes.assert_called_once()

    def test_get_annotated_image_bytes_with_multiple_regions_and_detections(self, mock_detector, data_dir):
        """Test get_annotated_image_bytes with multiple regions each having detections."""
        # Setup - detector returns boxes for each region call
        boxes_per_region = [(10, 10, 30, 30)]
        mock_detector.detect_boxes.return_value = boxes_per_region
        regions = [Region(20, 20, 100, 100), Region(150, 150, 250, 250)]

        # Execute
        result = get_annotated_image_bytes(mock_detector, data_dir / "bird.png", regions=regions)

        # Assert
        assert isinstance(result, bytes)
        assert len(result) > 0
        # Verify detector was called twice (once per region)
        assert mock_detector.detect_boxes.call_count == 2

    def test_get_annotated_image_bytes_with_regions_no_detections(self, mock_detector, data_dir):
        """Test get_annotated_image_bytes with regions but no detections raises error."""
        # Setup - detector returns no boxes
        mock_detector.detect_boxes.return_value = []
        regions = [Region(20, 20, 100, 100)]

        # Execute and assert
        with pytest.raises(UserFacingError) as exc_info:
            get_annotated_image_bytes(mock_detector, data_dir / "bird.png", regions=regions)

        assert exc_info.value.title == "No bird detected"
        assert exc_info.value.severity == "info"


class TestRegionDataclass:
    """Tests for Region dataclass."""

    def test_region_creation(self):
        """Test Region can be created with coordinates."""
        region = Region(10, 20, 100, 200)

        assert region.x1 == 10
        assert region.y1 == 20
        assert region.x2 == 100
        assert region.y2 == 200
