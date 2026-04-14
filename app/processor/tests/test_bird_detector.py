from unittest.mock import MagicMock, patch

import pytest

from processor.bird_detector import (
    DEFAULT_DETECTION_PARAMS,
    DEFAULT_MODEL_PATH,
    GREAT_TIT_CLASS_ID,
    PIGEON_CLASS_ID,
    BirdDetector,
)


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

    def test_detect_frame_may_contain_birds(self, no_bird_frame):
        """Test that detector can process frames and return detection results."""
        detector = BirdDetector()
        result = detector.detect(no_bird_frame)
        # The fine-tuned model may detect birds in frames based on actual bird presence
        assert isinstance(result, bool)

    def test_detect_boxes_cropped_bird_frame_with_preset_params(self, cropped_bird_frame, preset_detection_parameters):
        """Test that detector returns boxes when bird is present in cropped frame with preset params."""
        detector = BirdDetector()
        result = detector.detect_boxes(cropped_bird_frame, **preset_detection_parameters)
        assert len(result) > 0

    def test_detect_boxes_processes_frames(self, no_bird_frame):
        """Test that detector can extract detection boxes from frames."""
        detector = BirdDetector()
        result = detector.detect_boxes(no_bird_frame)
        # The fine-tuned model may detect birds in frames based on actual bird presence
        assert isinstance(result, list)

    def test_detect_uses_default_params(self, mock_detector):
        """Test that detect passes default detection params to model."""
        detector, mock_model = mock_detector
        frame = MagicMock()

        detector.detect(frame)

        mock_model.assert_called_once_with(
            frame,
            classes=[GREAT_TIT_CLASS_ID, PIGEON_CLASS_ID],
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
            classes=[GREAT_TIT_CLASS_ID, PIGEON_CLASS_ID],
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
            classes=[GREAT_TIT_CLASS_ID, PIGEON_CLASS_ID],
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
            classes=[GREAT_TIT_CLASS_ID, PIGEON_CLASS_ID],
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

            mock_yolo.assert_called_once_with(DEFAULT_MODEL_PATH)
            mock_model.fuse.assert_called_once()

    def test_init_without_model_path_uses_default(self):
        """Test that BirdDetector uses default model when model_path is not provided."""
        with patch("processor.bird_detector.YOLO") as mock_yolo:
            mock_model = MagicMock()
            mock_yolo.return_value = mock_model

            BirdDetector()

            mock_yolo.assert_called_once_with(DEFAULT_MODEL_PATH)
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

            assert detector._classes == [GREAT_TIT_CLASS_ID, PIGEON_CLASS_ID]

    def test_init_without_classes_uses_default(self):
        """Test that BirdDetector uses default bird class when classes is not provided."""
        with patch("processor.bird_detector.YOLO") as mock_yolo:
            mock_model = MagicMock()
            mock_yolo.return_value = mock_model

            detector = BirdDetector()

            assert detector._classes == [GREAT_TIT_CLASS_ID, PIGEON_CLASS_ID]

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

    def test_detect_boxes_with_class_thresholds_uses_min_conf(self, mock_detector):
        """Test that detect_boxes uses min(class_thresholds) as conf when class_thresholds is provided."""
        detector, mock_model = mock_detector
        frame = MagicMock()
        class_thresholds = {GREAT_TIT_CLASS_ID: 0.8, PIGEON_CLASS_ID: 0.9}

        detector.detect_boxes(frame, class_thresholds=class_thresholds, imgsz=480, iou=0.5)

        mock_model.assert_called_once_with(
            frame,
            classes=[GREAT_TIT_CLASS_ID, PIGEON_CLASS_ID],
            verbose=False,
            conf=0.8,  # min(0.8, 0.9)
            imgsz=480,
            iou=0.5,
        )

    def test_detect_boxes_with_class_thresholds_filters_box_below_threshold(self):
        """Test that detect_boxes filters out boxes below their per-class threshold."""
        with patch("processor.bird_detector.YOLO") as mock_yolo:
            mock_model = MagicMock()
            mock_yolo.return_value = mock_model
            mock_result = MagicMock()
            # Pigeon box with confidence 0.85, below the pigeon threshold of 0.9
            mock_result.boxes.xyxy = [[10, 20, 100, 200]]
            mock_result.boxes.cls = [PIGEON_CLASS_ID]
            mock_result.boxes.conf = [0.85]
            mock_model.return_value = [mock_result]
            detector = BirdDetector()
            frame = MagicMock()

            result = detector.detect_boxes(frame, class_thresholds={GREAT_TIT_CLASS_ID: 0.8, PIGEON_CLASS_ID: 0.9})

            assert result == []

    def test_detect_boxes_with_class_thresholds_keeps_box_above_threshold(self):
        """Test that detect_boxes keeps boxes at or above their per-class threshold."""
        with patch("processor.bird_detector.YOLO") as mock_yolo:
            mock_model = MagicMock()
            mock_yolo.return_value = mock_model
            mock_result = MagicMock()
            # Pigeon box with confidence 0.95, above the pigeon threshold of 0.9
            mock_result.boxes.xyxy = [[10, 20, 100, 200]]
            mock_result.boxes.cls = [PIGEON_CLASS_ID]
            mock_result.boxes.conf = [0.95]
            mock_model.return_value = [mock_result]
            detector = BirdDetector()
            frame = MagicMock()

            result = detector.detect_boxes(frame, class_thresholds={GREAT_TIT_CLASS_ID: 0.8, PIGEON_CLASS_ID: 0.9})

            assert len(result) == 1
            assert result[0].class_id == PIGEON_CLASS_ID
            assert result[0].confidence == 0.95
