from unittest.mock import MagicMock, patch

import pytest

from processor.bird_detector import BIRD_COCO_CLASS_ID, DEFAULT_DETECTION_PARAMS, BirdDetector


@pytest.fixture
def mock_detector():
    """Create a BirdDetector with mocked YOLO model."""
    with patch("processor.bird_detector.YOLO") as mock_yolo:
        mock_model = MagicMock()
        mock_yolo.return_value = mock_model
        mock_result = MagicMock()
        mock_result.boxes = None
        mock_model.return_value = [mock_result]
        detector = BirdDetector()
        yield detector, mock_model


class TestBirdDetector:
    """Test suite for BirdDetector class."""

    def test_detect_cropped_bird_frame_with_preset_params(self, cropped_bird_frame, preset_detection_parameters):
        """Test that detector returns True when bird is present in cropped frame with preset params."""
        detector = BirdDetector()
        result = detector.detect(cropped_bird_frame, **preset_detection_parameters)
        assert result is True

    def test_detect_frame_without_bird(self, no_bird_frame):
        """Test that detector returns False when no bird is present in frame."""
        detector = BirdDetector()
        result = detector.detect(no_bird_frame)
        assert result is False

    def test_detect_boxes_cropped_bird_frame_with_preset_params(self, cropped_bird_frame, preset_detection_parameters):
        """Test that detector returns boxes when bird is present in cropped frame with preset params."""
        detector = BirdDetector()
        result = detector.detect_boxes(cropped_bird_frame, **preset_detection_parameters)
        assert len(result) > 0

    def test_detect_boxes_frame_without_bird(self, no_bird_frame):
        """Test that detector returns empty list when no bird is present in frame."""
        detector = BirdDetector()
        result = detector.detect_boxes(no_bird_frame)
        assert result == []

    def test_detect_uses_default_params(self, mock_detector):
        """Test that detect passes default detection params to model."""
        detector, mock_model = mock_detector
        frame = MagicMock()

        detector.detect(frame)

        mock_model.assert_called_once_with(
            frame,
            classes=[BIRD_COCO_CLASS_ID],
            verbose=False,
            **DEFAULT_DETECTION_PARAMS,
        )

    def test_detect_allows_param_override(self, mock_detector):
        """Test that detect allows overriding default params via kwargs."""
        detector, mock_model = mock_detector
        frame = MagicMock()

        detector.detect(frame, conf=0.8, imgsz=640, iou=0.9)

        mock_model.assert_called_once_with(
            frame,
            classes=[BIRD_COCO_CLASS_ID],
            verbose=False,
            conf=0.8,
            imgsz=640,
            iou=0.9,
        )

    def test_detect_boxes_uses_default_params(self, mock_detector):
        """Test that detect_boxes passes default detection params to model."""
        detector, mock_model = mock_detector
        frame = MagicMock()

        detector.detect_boxes(frame)

        mock_model.assert_called_once_with(
            frame,
            classes=[BIRD_COCO_CLASS_ID],
            verbose=False,
            **DEFAULT_DETECTION_PARAMS,
        )

    def test_detect_boxes_allows_param_override(self, mock_detector):
        """Test that detect_boxes allows overriding default params via kwargs."""
        detector, mock_model = mock_detector
        frame = MagicMock()

        detector.detect_boxes(frame, conf=0.5, imgsz=320, iou=0.8)

        mock_model.assert_called_once_with(
            frame,
            classes=[BIRD_COCO_CLASS_ID],
            verbose=False,
            conf=0.5,
            imgsz=320,
            iou=0.8,
        )

    def test_init_with_custom_model_path(self):
        """Test that BirdDetector initializes with custom model path."""
        with patch("processor.bird_detector.YOLO") as mock_yolo:
            mock_model = MagicMock()
            mock_yolo.return_value = mock_model

            BirdDetector(model_path="/path/to/custom/model.pt")

            mock_yolo.assert_called_once_with("/path/to/custom/model.pt")
            mock_model.fuse.assert_called_once()

    def test_init_with_none_model_path_uses_default(self):
        """Test that BirdDetector uses default model when model_path is None."""
        with patch("processor.bird_detector.YOLO") as mock_yolo:
            mock_model = MagicMock()
            mock_yolo.return_value = mock_model

            BirdDetector(model_path=None)

            mock_yolo.assert_called_once_with("yolov8n.pt")
            mock_model.fuse.assert_called_once()

    def test_init_without_model_path_uses_default(self):
        """Test that BirdDetector uses default model when model_path is not provided."""
        with patch("processor.bird_detector.YOLO") as mock_yolo:
            mock_model = MagicMock()
            mock_yolo.return_value = mock_model

            BirdDetector()

            mock_yolo.assert_called_once_with("yolov8n.pt")
            mock_model.fuse.assert_called_once()

    def test_init_with_custom_classes(self):
        """Test that BirdDetector stores custom classes list."""
        with patch("processor.bird_detector.YOLO") as mock_yolo:
            mock_model = MagicMock()
            mock_yolo.return_value = mock_model

            custom_classes = [0, 1, 2]
            detector = BirdDetector(classes=custom_classes)

            assert detector._classes == custom_classes

    def test_init_with_none_classes_uses_default(self):
        """Test that BirdDetector uses default bird class when classes is None."""
        with patch("processor.bird_detector.YOLO") as mock_yolo:
            mock_model = MagicMock()
            mock_yolo.return_value = mock_model

            detector = BirdDetector(classes=None)

            assert detector._classes == [BIRD_COCO_CLASS_ID]

    def test_init_without_classes_uses_default(self):
        """Test that BirdDetector uses default bird class when classes is not provided."""
        with patch("processor.bird_detector.YOLO") as mock_yolo:
            mock_model = MagicMock()
            mock_yolo.return_value = mock_model

            detector = BirdDetector()

            assert detector._classes == [BIRD_COCO_CLASS_ID]

    def test_detect_uses_custom_classes(self):
        """Test that detect uses custom classes when provided."""
        with patch("processor.bird_detector.YOLO") as mock_yolo:
            mock_model = MagicMock()
            mock_yolo.return_value = mock_model
            mock_result = MagicMock()
            mock_result.boxes = None
            mock_model.return_value = [mock_result]

            custom_classes = [0, 1, 2]
            detector = BirdDetector(classes=custom_classes)
            frame = MagicMock()

            detector.detect(frame)

            mock_model.assert_called_once_with(
                frame,
                classes=custom_classes,
                verbose=False,
                **DEFAULT_DETECTION_PARAMS,
            )

    def test_detect_boxes_uses_custom_classes(self):
        """Test that detect_boxes uses custom classes when provided."""
        with patch("processor.bird_detector.YOLO") as mock_yolo:
            mock_model = MagicMock()
            mock_yolo.return_value = mock_model
            mock_result = MagicMock()
            mock_result.boxes = None
            mock_model.return_value = [mock_result]

            custom_classes = [5, 10, 15]
            detector = BirdDetector(classes=custom_classes)
            frame = MagicMock()

            detector.detect_boxes(frame)

            mock_model.assert_called_once_with(
                frame,
                classes=custom_classes,
                verbose=False,
                **DEFAULT_DETECTION_PARAMS,
            )

    def test_init_with_both_custom_model_and_classes(self):
        """Test that BirdDetector accepts both custom model_path and classes."""
        with patch("processor.bird_detector.YOLO") as mock_yolo:
            mock_model = MagicMock()
            mock_yolo.return_value = mock_model

            custom_classes = [0, 1, 2]
            detector = BirdDetector(model_path="/path/to/model.pt", classes=custom_classes)

            mock_yolo.assert_called_once_with("/path/to/model.pt")
            assert detector._classes == custom_classes
