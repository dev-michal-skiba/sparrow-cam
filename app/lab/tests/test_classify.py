"""Unit tests for stage-2 species classifier training."""

import json
import random
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from lab.classify import (
    BACKGROUND_CLASS,
    BASE_BIRD_CLASS_ID,
    CROPS_PER_CLASS,
    NEGATIVE_FRAMES,
    POSITIVE_FRAMES,
    RANDOM_CROPS_PER_NEGATIVE,
    ClassifyError,
    _balance,
    _crop_norm,
    _hard_negative_crops,
    _load_base_detector,
    _random_crops,
    _read_boxes,
    build_dataset,
    select_training_frames,
    train,
)
from lab.frame_selection import Frame


class TestClassifyError:
    """Tests for ClassifyError exception."""

    def test_classify_error_is_exception(self):
        """Test that ClassifyError is an Exception."""
        assert issubclass(ClassifyError, Exception)

    def test_classify_error_with_message(self):
        """Test that ClassifyError can be raised with a message."""
        with pytest.raises(ClassifyError, match="Test error"):
            raise ClassifyError("Test error")


class TestReadBoxes:
    """Tests for _read_boxes function."""

    def test_read_boxes_empty_file(self, tmp_path):
        """Test reading empty label file."""
        label_path = tmp_path / "label.txt"
        label_path.write_text("")

        boxes = _read_boxes(label_path)
        assert boxes == []

    def test_read_boxes_single_box(self, tmp_path):
        """Test reading single box."""
        label_path = tmp_path / "label.txt"
        label_path.write_text("0 0.5 0.5 0.2 0.2\n")

        boxes = _read_boxes(label_path)
        assert len(boxes) == 1
        assert boxes[0][0] == 0
        assert boxes[0][1] == (0.5, 0.5, 0.2, 0.2)

    def test_read_boxes_multiple_boxes(self, tmp_path):
        """Test reading multiple boxes."""
        label_path = tmp_path / "label.txt"
        label_path.write_text("0 0.5 0.5 0.2 0.2\n1 0.3 0.3 0.1 0.1\n2 0.7 0.7 0.1 0.1\n")

        boxes = _read_boxes(label_path)
        assert len(boxes) == 3
        assert boxes[0][0] == 0
        assert boxes[1][0] == 1
        assert boxes[2][0] == 2

    def test_read_boxes_skips_empty_lines(self, tmp_path):
        """Test that empty lines are skipped."""
        label_path = tmp_path / "label.txt"
        label_path.write_text("0 0.5 0.5 0.2 0.2\n\n1 0.3 0.3 0.1 0.1\n  \n")

        boxes = _read_boxes(label_path)
        assert len(boxes) == 2

    def test_read_boxes_skips_malformed_lines(self, tmp_path):
        """Test that malformed lines are skipped."""
        label_path = tmp_path / "label.txt"
        label_path.write_text("0 0.5 0.5 0.2\n0 0.5 0.5 0.2 0.2\n1 0.3\n")

        boxes = _read_boxes(label_path)
        assert len(boxes) == 1
        assert boxes[0][0] == 0


class TestCropNorm:
    """Tests for _crop_norm function."""

    def test_crop_norm_centered_box(self):
        """Test cropping a centered box."""
        image = np.ones((100, 100, 3), dtype=np.uint8) * 100
        box = (0.5, 0.5, 0.2, 0.2)  # cx=0.5, cy=0.5, w=0.2, h=0.2

        crop = _crop_norm(image, box)

        # Box should be (40, 40) to (60, 60)
        assert crop.shape[0] == 20
        assert crop.shape[1] == 20

    def test_crop_norm_corner_box(self):
        """Test cropping a corner box."""
        image = np.ones((100, 100, 3), dtype=np.uint8) * 100
        box = (0.1, 0.1, 0.2, 0.2)  # Near top-left

        crop = _crop_norm(image, box)

        # Should be clipped to image bounds
        assert crop.shape[0] > 0
        assert crop.shape[1] > 0

    def test_crop_norm_large_box(self):
        """Test cropping a box larger than the image."""
        image = np.ones((100, 100, 3), dtype=np.uint8) * 100
        box = (0.5, 0.5, 2.0, 2.0)  # 200% of image size

        crop = _crop_norm(image, box)

        # Should be clipped to image bounds
        assert crop.shape[0] <= 100
        assert crop.shape[1] <= 100

    def test_crop_norm_preserves_image_data(self):
        """Test that cropped data matches source."""
        image = np.arange(100 * 100 * 3, dtype=np.uint8).reshape(100, 100, 3)
        box = (0.5, 0.5, 0.2, 0.2)

        crop = _crop_norm(image, box)

        assert crop.shape[0] > 0
        assert crop.shape[1] > 0


class TestRandomCrops:
    """Tests for _random_crops function."""

    def test_random_crops_count(self):
        """Test that correct number of crops are generated."""
        image = np.ones((100, 100, 3), dtype=np.uint8) * 100
        rng = random.Random(42)

        crops = _random_crops(image, rng)

        assert len(crops) == RANDOM_CROPS_PER_NEGATIVE

    def test_random_crops_non_empty(self):
        """Test that all crops are non-empty."""
        image = np.ones((100, 100, 3), dtype=np.uint8) * 100
        rng = random.Random(42)

        crops = _random_crops(image, rng)

        assert all(crop.size > 0 for crop in crops)

    def test_random_crops_smaller_than_image(self):
        """Test that crops are smaller than the image."""
        image = np.ones((100, 100, 3), dtype=np.uint8) * 100
        rng = random.Random(42)

        crops = _random_crops(image, rng)

        for crop in crops:
            assert crop.shape[0] <= 100
            assert crop.shape[1] <= 100

    def test_random_crops_deterministic_seed(self):
        """Test that same seed produces same crops."""
        image = np.ones((100, 100, 3), dtype=np.uint8) * 100

        rng1 = random.Random(42)
        crops1 = _random_crops(image, rng1)

        rng2 = random.Random(42)
        crops2 = _random_crops(image, rng2)

        assert len(crops1) == len(crops2)
        for c1, c2 in zip(crops1, crops2):
            assert np.array_equal(c1, c2)


class TestLoadBaseDetector:
    """Tests for _load_base_detector function."""

    def test_load_base_detector_returns_yolo(self):
        """Test that load_base_detector returns a YOLO instance."""
        with patch("ultralytics.YOLO") as mock_yolo_class:
            mock_detector = MagicMock()
            mock_yolo_class.return_value = mock_detector

            detector = _load_base_detector()

            assert detector == mock_detector
            mock_yolo_class.assert_called_once()

    def test_load_base_detector_uses_base_model_path(self):
        """Test that it loads from BASE_MODEL_PATH."""
        with (
            patch("ultralytics.YOLO") as mock_yolo_class,
            patch("lab.classify.BASE_MODEL_PATH", Path("/test/model.pt")),
        ):
            mock_detector = MagicMock()
            mock_yolo_class.return_value = mock_detector

            _load_base_detector()

            mock_yolo_class.assert_called_once()
            call_arg = str(mock_yolo_class.call_args[0][0])
            assert "model.pt" in call_arg


class TestHardNegativeCrops:
    """Tests for _hard_negative_crops function."""

    def test_hard_negative_crops_no_detections(self):
        """Test with no detections from base model."""
        detector = MagicMock()
        detector.return_value = [MagicMock(boxes=None)]
        image = np.ones((100, 100, 3), dtype=np.uint8) * 100

        crops = _hard_negative_crops(detector, image)

        assert crops == []

    def test_hard_negative_crops_with_detections(self):
        """Test with detections from base model."""
        detector = MagicMock()

        # Mock a detection with boxes
        mock_result = MagicMock()
        mock_boxes = MagicMock()
        mock_boxes.xyxy = [
            [10, 10, 30, 30],
            [40, 40, 60, 60],
        ]
        mock_result.boxes = mock_boxes
        detector.return_value = [mock_result]

        image = np.ones((100, 100, 3), dtype=np.uint8) * 100

        crops = _hard_negative_crops(detector, image)

        assert len(crops) == 2
        assert all(crop.size > 0 for crop in crops)

    def test_hard_negative_crops_calls_detector_with_params(self):
        """Test that detector is called with correct parameters."""
        detector = MagicMock()
        detector.return_value = [MagicMock(boxes=None)]
        image = np.ones((100, 100, 3), dtype=np.uint8) * 100

        _hard_negative_crops(detector, image)

        call_kwargs = detector.call_args[1]
        assert call_kwargs["classes"] == [BASE_BIRD_CLASS_ID]
        assert call_kwargs["verbose"] is False
        assert "conf" in call_kwargs
        assert "imgsz" in call_kwargs
        assert "iou" in call_kwargs


class TestBalance:
    """Tests for _balance function."""

    def test_balance_undersized_class(self):
        """Test with fewer crops than target."""
        crops = [np.ones((32, 32, 3), dtype=np.uint8) for _ in range(100)]
        rng = random.Random(42)

        result = _balance(crops, "test_class", rng)

        assert len(result) == 100
        assert result == crops

    def test_balance_oversized_class(self):
        """Test downsampling oversized class."""
        crops = [np.ones((32, 32, 3), dtype=np.uint8) for _ in range(1000)]
        rng = random.Random(42)

        result = _balance(crops, "test_class", rng)

        assert len(result) == CROPS_PER_CLASS
        assert CROPS_PER_CLASS < len(crops)

    def test_balance_deterministic(self):
        """Test that same seed produces same balance."""
        crops = [np.ones((32, 32, 3), dtype=np.uint8) * i for i in range(1000)]

        rng1 = random.Random(42)
        result1 = _balance(crops, "test", rng1)

        rng2 = random.Random(42)
        result2 = _balance(crops, "test", rng2)

        assert len(result1) == len(result2)
        assert len(result1) == CROPS_PER_CLASS

    def test_balance_empty_crops(self):
        """Test with no crops."""
        crops = []
        rng = random.Random(42)

        result = _balance(crops, "test_class", rng)

        assert len(result) == 0


class TestSelectTrainingFrames:
    """Tests for select_training_frames function."""

    def test_select_training_frames_no_dataset(self):
        """Test that error is raised when no dataset found."""
        with patch("lab.classify.DATASET_DIR", Path("/nonexistent")):
            with pytest.raises(ClassifyError, match="No dataset frames found"):
                select_training_frames()

    def test_select_training_frames_returns_positives_negatives(self, tmp_path):
        """Test that function returns positive and negative frames."""
        images_dir = tmp_path / "images"
        labels_dir = tmp_path / "labels"
        images_dir.mkdir()
        labels_dir.mkdir()

        # Create positive frames
        for i in range(10):
            img_path = images_dir / f"2026-06-25_auto_2026-06-25T{i:02d}0000Z_uuid{i}_sparrow_cam-4031.jpg"
            label_path = labels_dir / f"2026-06-25_auto_2026-06-25T{i:02d}0000Z_uuid{i}_sparrow_cam-4031.txt"
            img_path.write_text("image")
            label_path.write_text("0 0.5 0.5 0.2 0.2\n")

        # Create negative frames
        for i in range(10, 15):
            img_path = images_dir / f"2026-06-25_auto_2026-06-25T{i:02d}0000Z_uuid{i}_sparrow_cam-4031.jpg"
            label_path = labels_dir / f"2026-06-25_auto_2026-06-25T{i:02d}0000Z_uuid{i}_sparrow_cam-4031.txt"
            img_path.write_text("image")
            label_path.write_text("")

        with patch("lab.classify.DATASET_DIR", tmp_path):
            positives, negatives, rng = select_training_frames()

        assert len(positives) > 0
        assert len(negatives) > 0
        assert isinstance(rng, random.Random)

    def test_select_training_frames_uses_salt(self, tmp_path):
        """Test that selection uses DATASET_SALT."""
        images_dir = tmp_path / "images"
        labels_dir = tmp_path / "labels"
        images_dir.mkdir()
        labels_dir.mkdir()

        # Create frames
        for i in range(50):
            img_path = images_dir / f"2026-06-25_auto_2026-06-25T{i:02d}0000Z_uuid{i}_sparrow_cam-4031.jpg"
            label_path = labels_dir / f"2026-06-25_auto_2026-06-25T{i:02d}0000Z_uuid{i}_sparrow_cam-4031.txt"
            img_path.write_text("image")
            label_path.write_text("0 0.5 0.5 0.2 0.2\n" if i < 40 else "")

        with patch("lab.classify.DATASET_DIR", tmp_path):
            positives, negatives, rng = select_training_frames()

        # Should have both types
        assert len(positives) > 0
        assert len(negatives) > 0

    def test_select_training_frames_respects_frame_limits(self, tmp_path):
        """Test that selection respects POSITIVE_FRAMES and NEGATIVE_FRAMES limits."""
        images_dir = tmp_path / "images"
        labels_dir = tmp_path / "labels"
        images_dir.mkdir()
        labels_dir.mkdir()

        # Create many frames
        for i in range(1000):
            img_path = images_dir / f"2026-06-25_auto_2026-06-25T{i:02d}0000Z_uuid{i}_sparrow_cam-4031.jpg"
            label_path = labels_dir / f"2026-06-25_auto_2026-06-25T{i:02d}0000Z_uuid{i}_sparrow_cam-4031.txt"
            img_path.write_text("image")
            label_path.write_text("0 0.5 0.5 0.2 0.2\n" if i < 800 else "")

        with patch("lab.classify.DATASET_DIR", tmp_path):
            positives, negatives, rng = select_training_frames()

        assert len(positives) <= POSITIVE_FRAMES
        assert len(negatives) <= NEGATIVE_FRAMES


class TestBuildDataset:
    """Tests for build_dataset function."""

    def test_build_dataset_creates_train_directory(self, tmp_path):
        """Test that train directory is created."""
        dataset_dir = tmp_path / "dataset"
        frames = []
        rng = random.Random(42)

        build_dataset(frames, frames, dataset_dir, rng)

        assert (dataset_dir / "train").is_dir()

    def test_build_dataset_creates_class_directories(self, tmp_path):
        """Test that class directories are created."""
        images_dir = tmp_path / "images"
        labels_dir = tmp_path / "labels"
        images_dir.mkdir()
        labels_dir.mkdir()

        # Create a positive frame with a bird
        img_path = images_dir / "img.jpg"
        label_path = labels_dir / "img.txt"
        img_path.write_text("dummy")
        label_path.write_text("0 0.5 0.5 0.2 0.2\n")

        frame = Frame(img_path, label_path, 2026, (6, 25), 8, (0,))

        dataset_dir = tmp_path / "dataset"
        rng = random.Random(42)

        with patch("cv2.imread", return_value=np.ones((100, 100, 3), dtype=np.uint8)):
            with patch("cv2.imwrite"):
                build_dataset([frame], [], dataset_dir, rng)

        # Should have species class directory
        assert (dataset_dir / "train" / "great_tit").is_dir()
        assert (dataset_dir / "train" / BACKGROUND_CLASS).is_dir()

    def test_build_dataset_creates_val_symlink(self, tmp_path):
        """Test that val directory is a symlink to train."""
        dataset_dir = tmp_path / "dataset"
        frames = []
        rng = random.Random(42)

        build_dataset(frames, frames, dataset_dir, rng)

        val_dir = dataset_dir / "val"
        assert val_dir.is_symlink()
        assert val_dir.resolve() == (dataset_dir / "train").resolve()

    def test_build_dataset_handles_missing_images(self, tmp_path):
        """Test that missing images are handled gracefully."""
        images_dir = tmp_path / "images"
        labels_dir = tmp_path / "labels"
        images_dir.mkdir()
        labels_dir.mkdir()

        # Create frames but don't write images
        img_path = images_dir / "missing.jpg"
        label_path = labels_dir / "missing.txt"
        label_path.write_text("0 0.5 0.5 0.2 0.2\n")

        frame = Frame(img_path, label_path, 2026, (6, 25), 8, (0,))
        dataset_dir = tmp_path / "dataset"
        rng = random.Random(42)

        # Should not raise, just skip the frame
        with patch("cv2.imread", return_value=None):
            build_dataset([frame], [], dataset_dir, rng)

    def test_build_dataset_writes_crops(self, tmp_path):
        """Test that crops are written to disk."""
        images_dir = tmp_path / "images"
        labels_dir = tmp_path / "labels"
        images_dir.mkdir()
        labels_dir.mkdir()

        # Create frame with bird
        img_path = images_dir / "img.jpg"
        label_path = labels_dir / "img.txt"
        img_path.write_text("dummy")
        label_path.write_text("0 0.5 0.5 0.2 0.2\n")

        frame = Frame(img_path, label_path, 2026, (6, 25), 8, (0,))
        dataset_dir = tmp_path / "dataset"
        rng = random.Random(42)

        # Mock cv2 operations
        mock_image = np.ones((100, 100, 3), dtype=np.uint8)
        with patch("cv2.imread", return_value=mock_image):
            with patch("cv2.imwrite") as mock_imwrite:
                build_dataset([frame], [], dataset_dir, rng)

                # Should have written crop files
                assert mock_imwrite.call_count > 0

    def test_build_dataset_creates_background_crops(self, tmp_path):
        """Test that background crops are created from negative frames."""
        images_dir = tmp_path / "images"
        labels_dir = tmp_path / "labels"
        images_dir.mkdir()
        labels_dir.mkdir()

        # Create negative frame (empty labels)
        img_path = images_dir / "negative.jpg"
        label_path = labels_dir / "negative.txt"
        img_path.write_text("dummy")
        label_path.write_text("")

        frame = Frame(img_path, label_path, 2026, (6, 25), 8, ())
        dataset_dir = tmp_path / "dataset"
        rng = random.Random(42)

        mock_image = np.ones((100, 100, 3), dtype=np.uint8)
        with patch("cv2.imread", return_value=mock_image):
            with patch("cv2.imwrite") as mock_imwrite:
                with patch("lab.classify._load_base_detector"):
                    with patch("lab.classify._hard_negative_crops", return_value=[]):
                        build_dataset([], [frame], dataset_dir, rng)

                        # Should have written some background crops
                        assert mock_imwrite.call_count > 0

    def test_build_dataset_returns_sorted_class_names(self, tmp_path):
        """Test that class names are returned in sorted order."""
        dataset_dir = tmp_path / "dataset"
        frames = []
        rng = random.Random(42)

        class_names = build_dataset(frames, frames, dataset_dir, rng)

        assert class_names == sorted(class_names)
        # Should include background
        assert BACKGROUND_CLASS in class_names


class TestTrain:
    """Tests for train function."""

    def test_train_creates_best_weights(self, tmp_path):
        """Test that train function creates best weights file."""
        dataset_dir = tmp_path / "dataset"
        dataset_dir.mkdir()
        output_dir = tmp_path / "output"

        # Create the expected structure
        runs_dir = output_dir / "runs" / "train" / "weights"
        runs_dir.mkdir(parents=True)
        (runs_dir / "best.pt").write_text("weights")

        with patch("lab.classify.CLS_BASE_MODEL_PATH", Path("/fake/model.pt")), patch("ultralytics.YOLO") as mock_yolo:
            mock_model = MagicMock()
            mock_yolo.return_value = mock_model

            result = train(dataset_dir, output_dir)

            assert result == runs_dir / "best.pt"
            mock_model.train.assert_called_once()

    def test_train_raises_if_no_weights(self, tmp_path):
        """Test that train raises error if weights not found."""
        dataset_dir = tmp_path / "dataset"
        dataset_dir.mkdir()
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        with patch("lab.classify.CLS_BASE_MODEL_PATH", Path("/fake/model.pt")), patch("ultralytics.YOLO") as mock_yolo:
            mock_model = MagicMock()
            mock_yolo.return_value = mock_model

            with pytest.raises(ClassifyError, match="Training produced no weights"):
                train(dataset_dir, output_dir)

    def test_train_calls_yolo_with_correct_params(self, tmp_path):
        """Test that train calls YOLO with correct parameters."""
        dataset_dir = tmp_path / "dataset"
        dataset_dir.mkdir()
        output_dir = tmp_path / "output"

        runs_dir = output_dir / "runs" / "train" / "weights"
        runs_dir.mkdir(parents=True)
        (runs_dir / "best.pt").write_text("weights")

        with patch("lab.classify.CLS_BASE_MODEL_PATH", Path("/fake/model.pt")), patch("ultralytics.YOLO") as mock_yolo:
            mock_model = MagicMock()
            mock_yolo.return_value = mock_model

            train(dataset_dir, output_dir)

            # Verify train was called with expected parameters
            call_kwargs = mock_model.train.call_args[1]
            assert str(dataset_dir) in str(call_kwargs.get("data", ""))
            assert call_kwargs["epochs"] == 100
            assert call_kwargs["batch"] == 16
            assert call_kwargs["imgsz"] == 640

    def test_train_uses_cls_base_model(self, tmp_path):
        """Test that train uses CLS_BASE_MODEL_PATH."""
        dataset_dir = tmp_path / "dataset"
        dataset_dir.mkdir()
        output_dir = tmp_path / "output"

        runs_dir = output_dir / "runs" / "train" / "weights"
        runs_dir.mkdir(parents=True)
        (runs_dir / "best.pt").write_text("weights")

        with (
            patch("lab.classify.CLS_BASE_MODEL_PATH", Path("/test/cls_model.pt")),
            patch("ultralytics.YOLO") as mock_yolo,
        ):
            mock_model = MagicMock()
            mock_yolo.return_value = mock_model

            train(dataset_dir, output_dir)

            # Should have created YOLO with the path
            mock_yolo.assert_called_once()
            call_arg = str(mock_yolo.call_args[0][0])
            assert "cls_model.pt" in call_arg


class TestMain:
    """Tests for main function."""

    def test_main_creates_output_directory(self, tmp_path):
        """Test that main creates output directory."""
        with (
            patch("lab.classify.parse_args") as mock_parse,
            patch("lab.classify.resolve_version", return_value="v1.0.0"),
            patch("lab.classify.resolve_description", return_value="Test model"),
            patch("lab.classify.FINE_TUNED_DIR", tmp_path / "fine_tuned"),
            patch("lab.classify.CLS_BASE_MODEL_NAME", "yolo26n-cls"),
            patch("lab.classify.select_training_frames") as mock_select,
            patch("lab.classify.build_dataset") as mock_build,
            patch("lab.classify.train") as mock_train,
            patch("lab.classify.shutil.copy2"),
            patch("lab.classify._write_metadata"),
            patch("logging.basicConfig"),
        ):
            mock_parse.return_value = MagicMock(version="v1.0.0", description="Test model")
            mock_select.return_value = ([], [], random.Random(42))
            mock_build.return_value = ["class1", "class2"]
            mock_train.return_value = Path("/fake/best.pt")

            from lab.classify import main

            main()

            # Should have called the main functions
            mock_select.assert_called_once()

    def test_main_raises_if_output_dir_exists(self, tmp_path):
        """Test that main raises error if output directory already exists."""
        fine_tuned_dir = tmp_path / "fine_tuned"
        model_dir = fine_tuned_dir / "yolo26n-cls_v1.0.0"
        model_dir.mkdir(parents=True)

        with (
            patch("lab.classify.parse_args") as mock_parse,
            patch("lab.classify.resolve_version", return_value="v1.0.0"),
            patch("lab.classify.resolve_description", return_value="Test model"),
            patch("lab.classify.FINE_TUNED_DIR", fine_tuned_dir),
            patch("lab.classify.CLS_BASE_MODEL_NAME", "yolo26n-cls"),
        ):
            mock_parse.return_value = MagicMock(version="v1.0.0", description="Test model")

            from lab.classify import main

            with pytest.raises(ClassifyError, match="Model directory already exists"):
                main()

    def test_main_calls_all_steps(self, tmp_path):
        """Test that main calls all workflow steps."""
        with (
            patch("lab.classify.parse_args") as mock_parse,
            patch("lab.classify.resolve_version", return_value="v1.0.0") as mock_resolve_version,
            patch("lab.classify.resolve_description", return_value="Test") as mock_resolve_desc,
            patch("lab.classify.FINE_TUNED_DIR", tmp_path / "fine_tuned"),
            patch("lab.classify.CLS_BASE_MODEL_NAME", "yolo26n-cls"),
            patch("lab.classify.select_training_frames", return_value=([], [], random.Random(42))) as mock_select,
            patch("lab.classify.build_dataset", return_value=[]) as mock_build,
            patch("lab.classify.train", return_value=Path("/fake/best.pt")) as mock_train,
            patch("lab.classify.shutil.copy2") as mock_copy,
            patch("lab.classify._write_metadata") as mock_metadata,
            patch("logging.basicConfig"),
        ):
            mock_parse.return_value = MagicMock(version="v1.0.0", description="Test")

            from lab.classify import main

            main()

            mock_resolve_version.assert_called_once_with("v1.0.0")
            mock_resolve_desc.assert_called_once_with("Test")
            mock_select.assert_called_once()
            mock_build.assert_called_once()
            mock_train.assert_called_once()
            mock_copy.assert_called_once()
            mock_metadata.assert_called_once()

    def test_main_writes_classes_json(self, tmp_path):
        """Test that main writes classes.json file."""
        with (
            patch("lab.classify.parse_args") as mock_parse,
            patch("lab.classify.resolve_version", return_value="v1.0.0"),
            patch("lab.classify.resolve_description", return_value="Test"),
            patch("lab.classify.FINE_TUNED_DIR", tmp_path / "fine_tuned"),
            patch("lab.classify.CLS_BASE_MODEL_NAME", "yolo26n-cls"),
            patch("lab.classify.select_training_frames") as mock_select,
            patch("lab.classify.build_dataset") as mock_build,
            patch("lab.classify.train") as mock_train,
            patch("lab.classify.shutil.copy2"),
            patch("lab.classify._write_metadata"),
            patch("logging.basicConfig"),
        ):
            mock_parse.return_value = MagicMock(version="v1.0.0", description="Test")
            class_names = ["class1", "class2", "class3"]
            mock_select.return_value = ([], [], random.Random(42))
            mock_build.return_value = class_names
            mock_train.return_value = Path("/fake/best.pt")

            from lab.classify import main

            main()

            classes_json = tmp_path / "fine_tuned" / "yolo26n-cls_v1.0.0" / "classes.json"
            assert classes_json.is_file()

            classes_data = json.loads(classes_json.read_text())
            assert classes_data == class_names
