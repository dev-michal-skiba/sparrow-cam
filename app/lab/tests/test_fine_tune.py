"""Unit tests for lab/fine_tune.py."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import cv2
import numpy as np
import pytest

from lab.fine_tune import (
    _parse_dataset_yaml,
    _remap_label_line,
    get_available_models,
    load_preset,
    prepare_cropped_dataset,
    run_fine_tune,
    validate_version,
)


class TestGetAvailableModels:
    @patch("lab.fine_tune.FINE_TUNED_MODELS_DIR")
    def test_returns_empty_list_when_directory_not_exists(self, mock_models_dir, tmp_path):
        mock_models_dir.exists.return_value = False

        result = get_available_models()

        assert len(result) == 1  # Only base model
        assert result[0]["is_base"] is True
        assert result[0]["version"] == "yolov8n.pt"

    @patch("lab.fine_tune.FINE_TUNED_MODELS_DIR")
    def test_returns_base_model_when_directory_empty(self, mock_models_dir, tmp_path):
        mock_models_dir.exists.return_value = True
        mock_models_dir.iterdir.return_value = []

        result = get_available_models()

        assert len(result) == 1
        assert result[0]["is_base"] is True
        assert result[0]["version"] == "yolov8n.pt"

    @patch("lab.fine_tune.FINE_TUNED_MODELS_DIR")
    def test_includes_fine_tuned_models(self, mock_models_dir, tmp_path):
        models_dir = tmp_path / "models"
        models_dir.mkdir()

        # Create a fine-tuned model
        v1_dir = models_dir / "v1.0.0"
        v1_dir.mkdir()
        meta = {
            "version": "v1.0.0",
            "description": "First model",
            "base_model": "yolov8n.pt",
            "classes": {"0": "robin", "1": "sparrow"},
            "created_at": "2026-01-15T10:00:00Z",
        }
        (v1_dir / "meta.json").write_text(json.dumps(meta))
        (v1_dir / "model.pt").write_bytes(b"fake model")

        mock_models_dir.exists.return_value = True
        mock_models_dir.iterdir.return_value = [v1_dir]

        result = get_available_models()

        # Should have fine-tuned model + base model
        assert len(result) == 2
        assert result[0]["version"] == "v1.0.0"
        assert result[0]["is_base"] is False
        assert result[0]["description"] == "First model"
        assert result[0]["classes"] == {"0": "robin", "1": "sparrow"}
        assert result[1]["is_base"] is True

    @patch("lab.fine_tune.FINE_TUNED_MODELS_DIR")
    def test_sorts_by_created_at_descending(self, mock_models_dir, tmp_path):
        models_dir = tmp_path / "models"
        models_dir.mkdir()

        # Create two fine-tuned models
        v1_dir = models_dir / "v1.0.0"
        v1_dir.mkdir()
        meta1 = {
            "version": "v1.0.0",
            "description": "First",
            "base_model": "yolov8n.pt",
            "classes": None,
            "created_at": "2026-01-15T10:00:00Z",
        }
        (v1_dir / "meta.json").write_text(json.dumps(meta1))
        (v1_dir / "model.pt").write_bytes(b"fake model1")

        v2_dir = models_dir / "v1.0.1"
        v2_dir.mkdir()
        meta2 = {
            "version": "v1.0.1",
            "description": "Second",
            "base_model": "yolov8n.pt",
            "classes": None,
            "created_at": "2026-01-20T10:00:00Z",
        }
        (v2_dir / "meta.json").write_text(json.dumps(meta2))
        (v2_dir / "model.pt").write_bytes(b"fake model2")

        mock_models_dir.exists.return_value = True
        mock_models_dir.iterdir.return_value = [v1_dir, v2_dir]

        result = get_available_models()

        # Newer model (v1.0.1) should be first
        assert result[0]["version"] == "v1.0.1"
        assert result[1]["version"] == "v1.0.0"
        assert result[2]["is_base"] is True

    @patch("lab.fine_tune.FINE_TUNED_MODELS_DIR")
    def test_skips_directories_without_meta_or_model(self, mock_models_dir, tmp_path):
        models_dir = tmp_path / "models"
        models_dir.mkdir()

        # Create a directory with only meta.json (missing model.pt)
        bad_dir = models_dir / "bad"
        bad_dir.mkdir()
        meta = {
            "version": "bad",
            "description": "Missing model",
            "base_model": "yolov8n.pt",
            "classes": None,
            "created_at": "2026-01-15T10:00:00Z",
        }
        (bad_dir / "meta.json").write_text(json.dumps(meta))

        mock_models_dir.exists.return_value = True
        mock_models_dir.iterdir.return_value = [bad_dir]

        result = get_available_models()

        # Should only have base model
        assert len(result) == 1
        assert result[0]["is_base"] is True

    @patch("lab.fine_tune.FINE_TUNED_MODELS_DIR")
    def test_skips_non_directories(self, mock_models_dir, tmp_path):
        models_dir = tmp_path / "models"
        models_dir.mkdir()

        # Create a file (not a directory)
        file_path = models_dir / "not_a_dir.txt"
        file_path.write_text("not a model")

        mock_models_dir.exists.return_value = True
        mock_models_dir.iterdir.return_value = [file_path]

        result = get_available_models()

        # Should only have base model
        assert len(result) == 1
        assert result[0]["is_base"] is True

    @patch("lab.fine_tune.FINE_TUNED_MODELS_DIR")
    def test_skips_invalid_json(self, mock_models_dir, tmp_path):
        models_dir = tmp_path / "models"
        models_dir.mkdir()

        # Create a model with invalid JSON
        bad_dir = models_dir / "bad_json"
        bad_dir.mkdir()
        (bad_dir / "meta.json").write_text("invalid json {")
        (bad_dir / "model.pt").write_bytes(b"fake model")

        mock_models_dir.exists.return_value = True
        mock_models_dir.iterdir.return_value = [bad_dir]

        result = get_available_models()

        # Should only have base model
        assert len(result) == 1
        assert result[0]["is_base"] is True

    @patch("lab.fine_tune.FINE_TUNED_MODELS_DIR")
    def test_model_dict_has_all_required_fields(self, mock_models_dir, tmp_path):
        models_dir = tmp_path / "models"
        models_dir.mkdir()

        v1_dir = models_dir / "v1.0.0"
        v1_dir.mkdir()
        meta = {
            "version": "v1.0.0",
            "description": "Test",
            "base_model": "yolov8n.pt",
            "classes": {"0": "bird"},
            "created_at": "2026-01-15T10:00:00Z",
        }
        (v1_dir / "meta.json").write_text(json.dumps(meta))
        (v1_dir / "model.pt").write_bytes(b"fake model")

        mock_models_dir.exists.return_value = True
        mock_models_dir.iterdir.return_value = [v1_dir]

        result = get_available_models()

        fine_tuned = result[0]
        assert "version" in fine_tuned
        assert "model_path" in fine_tuned
        assert "description" in fine_tuned
        assert "base_model" in fine_tuned
        assert "classes" in fine_tuned
        assert "created_at" in fine_tuned
        assert "is_base" in fine_tuned

        base = result[1]
        assert "version" in base
        assert "model_path" in base
        assert "description" in base
        assert "base_model" in base
        assert "classes" in base
        assert "created_at" in base
        assert "is_base" in base

    @patch("lab.fine_tune.FINE_TUNED_MODELS_DIR")
    def test_base_model_entry_at_end(self, mock_models_dir, tmp_path):
        models_dir = tmp_path / "models"
        models_dir.mkdir()

        v1_dir = models_dir / "v1.0.0"
        v1_dir.mkdir()
        meta = {
            "version": "v1.0.0",
            "description": "Test",
            "base_model": "yolov8n.pt",
            "classes": None,
            "created_at": "2026-01-15T10:00:00Z",
        }
        (v1_dir / "meta.json").write_text(json.dumps(meta))
        (v1_dir / "model.pt").write_bytes(b"fake model")

        mock_models_dir.exists.return_value = True
        mock_models_dir.iterdir.return_value = [v1_dir]

        result = get_available_models()

        # Base model should always be last
        assert result[-1]["is_base"] is True
        assert result[-1]["version"] == "yolov8n.pt"


class TestValidateVersion:
    def test_valid_version_returns_true(self):
        assert validate_version("v1.0.0") is True

    def test_valid_large_numbers(self):
        assert validate_version("v10.20.300") is True

    def test_missing_v_prefix_returns_false(self):
        assert validate_version("1.0.0") is False

    def test_missing_patch_returns_false(self):
        assert validate_version("v1.0") is False

    def test_extra_segment_returns_false(self):
        assert validate_version("v1.0.0.0") is False

    def test_non_numeric_returns_false(self):
        assert validate_version("v1.a.0") is False

    def test_empty_string_returns_false(self):
        assert validate_version("") is False


class TestLoadPreset:
    def test_valid_preset_with_one_region_returns_dict(self, tmp_path):
        preset = {"regions": [[10, 20, 100, 200]], "params": {"imgsz": 320}}
        preset_path = tmp_path / "preset.json"
        preset_path.write_text(json.dumps(preset))

        result = load_preset(preset_path)

        assert result["regions"] == [[10, 20, 100, 200]]

    def test_preset_with_zero_regions_raises_value_error(self, tmp_path):
        preset = {"regions": []}
        preset_path = tmp_path / "preset.json"
        preset_path.write_text(json.dumps(preset))

        with pytest.raises(ValueError, match="exactly one detection region"):
            load_preset(preset_path)

    def test_preset_with_multiple_regions_raises_value_error(self, tmp_path):
        preset = {"regions": [[0, 0, 50, 50], [60, 60, 110, 110]]}
        preset_path = tmp_path / "preset.json"
        preset_path.write_text(json.dumps(preset))

        with pytest.raises(ValueError, match="exactly one detection region"):
            load_preset(preset_path)

    def test_error_message_includes_filename(self, tmp_path):
        preset = {"regions": []}
        preset_path = tmp_path / "my_preset.json"
        preset_path.write_text(json.dumps(preset))

        with pytest.raises(ValueError, match="my_preset.json"):
            load_preset(preset_path)


class TestParseDatasetYaml:
    def test_parses_names_correctly(self, tmp_path):
        yaml = "path: /some/path\ntrain: images/train\nval: images/val\nnames:\n  0: bird\n  1: cat\n"
        (tmp_path / "dataset.yaml").write_text(yaml)

        result = _parse_dataset_yaml(tmp_path)

        assert result == {"0": "bird", "1": "cat"}

    def test_stops_at_non_indented_line_after_names(self, tmp_path):
        yaml = "names:\n  0: bird\nother: value\n"
        (tmp_path / "dataset.yaml").write_text(yaml)

        result = _parse_dataset_yaml(tmp_path)

        assert result == {"0": "bird"}
        assert "other" not in result

    def test_skips_comments_and_blank_lines_in_names(self, tmp_path):
        yaml = "names:\n\n  # comment\n  0: sparrow\n"
        (tmp_path / "dataset.yaml").write_text(yaml)

        result = _parse_dataset_yaml(tmp_path)

        assert result == {"0": "sparrow"}

    def test_no_names_block_returns_empty(self, tmp_path):
        yaml = "path: /some/path\ntrain: images/train\n"
        (tmp_path / "dataset.yaml").write_text(yaml)

        result = _parse_dataset_yaml(tmp_path)

        assert result == {}


class TestRemapLabelLine:
    def test_center_inside_crop_returns_remapped_line(self):
        # Image 200x200, crop [50,50,150,150], box centered at (100,100)
        result = _remap_label_line("0 0.5 0.5 0.1 0.1", 200, 200, 50, 50, 150, 150)

        assert result is not None
        parts = result.split()
        assert parts[0] == "0"
        cx = float(parts[1])
        cy = float(parts[2])
        assert abs(cx - 0.5) < 1e-5
        assert abs(cy - 0.5) < 1e-5

    def test_center_outside_crop_returns_none(self):
        # Center at (20,20) is outside crop [50,50,150,150]
        result = _remap_label_line("0 0.1 0.1 0.05 0.05", 200, 200, 50, 50, 150, 150)

        assert result is None

    def test_invalid_line_format_returns_none(self):
        result = _remap_label_line("0 0.5 0.5 0.1", 200, 200, 0, 0, 200, 200)

        assert result is None

    def test_empty_line_returns_none(self):
        result = _remap_label_line("", 200, 200, 0, 0, 200, 200)

        assert result is None

    def test_coords_clipped_to_zero_one(self):
        # Box that extends well beyond region, but center inside
        result = _remap_label_line("0 0.5 0.5 2.0 2.0", 100, 100, 0, 0, 100, 100)

        assert result is not None
        parts = result.split()
        w = float(parts[3])
        h = float(parts[4])
        assert w <= 1.0
        assert h <= 1.0

    def test_class_id_preserved(self):
        result = _remap_label_line("3 0.5 0.5 0.1 0.1", 200, 200, 0, 0, 200, 200)

        assert result is not None
        assert result.startswith("3 ")


class TestPrepareCroppedDataset:
    def _write_yaml(self, dataset_dir: Path) -> None:
        dataset_dir.mkdir(parents=True, exist_ok=True)
        (dataset_dir / "dataset.yaml").write_text("names:\n  0: bird\n")

    def _make_image(self, path: Path, w: int = 100, h: int = 100) -> None:
        frame = np.zeros((h, w, 3), dtype=np.uint8)
        cv2.imwrite(str(path), frame)

    def test_creates_output_directories(self, tmp_path):
        src = tmp_path / "src"
        dst = tmp_path / "dst"
        self._write_yaml(src)

        prepare_cropped_dataset(src, dst, (0, 0, 50, 50))

        assert (dst / "images" / "train").exists()
        assert (dst / "images" / "val").exists()
        assert (dst / "labels" / "train").exists()
        assert (dst / "labels" / "val").exists()

    def test_writes_dataset_yaml(self, tmp_path):
        src = tmp_path / "src"
        dst = tmp_path / "dst"
        self._write_yaml(src)

        prepare_cropped_dataset(src, dst, (0, 0, 50, 50))

        yaml_text = (dst / "dataset.yaml").read_text()
        assert "bird" in yaml_text
        assert str(dst) in yaml_text

    def test_crops_image_to_region(self, tmp_path):
        src = tmp_path / "src"
        dst = tmp_path / "dst"
        self._write_yaml(src)
        src_images = src / "images" / "train"
        src_images.mkdir(parents=True)
        (src / "labels" / "train").mkdir(parents=True)
        self._make_image(src_images / "frame.png", w=200, h=200)

        prepare_cropped_dataset(src, dst, (10, 10, 60, 60))

        cropped = cv2.imread(str(dst / "images" / "train" / "frame.png"))
        assert cropped.shape[:2] == (50, 50)

    def test_remaps_labels_when_label_file_exists(self, tmp_path):
        src = tmp_path / "src"
        dst = tmp_path / "dst"
        self._write_yaml(src)
        src_images = src / "images" / "train"
        src_images.mkdir(parents=True)
        src_labels = src / "labels" / "train"
        src_labels.mkdir(parents=True)
        self._make_image(src_images / "frame.png", w=200, h=200)
        # Box centered at (100,100) in 200x200 image — inside [50,50,150,150]
        (src_labels / "frame.txt").write_text("0 0.5 0.5 0.1 0.1\n")

        prepare_cropped_dataset(src, dst, (50, 50, 150, 150))

        label_text = (dst / "labels" / "train" / "frame.txt").read_text()
        assert label_text.strip() != ""

    def test_writes_empty_label_when_no_label_file(self, tmp_path):
        src = tmp_path / "src"
        dst = tmp_path / "dst"
        self._write_yaml(src)
        src_images = src / "images" / "train"
        src_images.mkdir(parents=True)
        (src / "labels" / "train").mkdir(parents=True)
        self._make_image(src_images / "frame.png")

        prepare_cropped_dataset(src, dst, (0, 0, 50, 50))

        label_file = dst / "labels" / "train" / "frame.txt"
        assert label_file.read_text() == ""

    def test_skips_when_source_images_dir_missing(self, tmp_path):
        src = tmp_path / "src"
        dst = tmp_path / "dst"
        self._write_yaml(src)
        # Only create val, not train
        (src / "images" / "val").mkdir(parents=True)
        (src / "labels" / "val").mkdir(parents=True)

        prepare_cropped_dataset(src, dst, (0, 0, 50, 50))

        # val dir should exist, but train should still be created (mkdir)
        assert (dst / "images" / "train").exists()

    def test_skips_unreadable_image(self, tmp_path):
        src = tmp_path / "src"
        dst = tmp_path / "dst"
        self._write_yaml(src)
        src_images = src / "images" / "train"
        src_images.mkdir(parents=True)
        (src / "labels" / "train").mkdir(parents=True)
        # Write a corrupt PNG
        (src_images / "bad.png").write_bytes(b"not an image")

        prepare_cropped_dataset(src, dst, (0, 0, 50, 50))

        # Should not crash; no output image created for the bad file
        assert not (dst / "images" / "train" / "bad.png").exists()

    def test_skips_label_lines_outside_crop(self, tmp_path):
        src = tmp_path / "src"
        dst = tmp_path / "dst"
        self._write_yaml(src)
        src_images = src / "images" / "train"
        src_images.mkdir(parents=True)
        src_labels = src / "labels" / "train"
        src_labels.mkdir(parents=True)
        self._make_image(src_images / "frame.png", w=200, h=200)
        # Box center at (20,20) — outside crop [50,50,150,150]
        (src_labels / "frame.txt").write_text("0 0.1 0.1 0.05 0.05\n")

        prepare_cropped_dataset(src, dst, (50, 50, 150, 150))

        label_text = (dst / "labels" / "train" / "frame.txt").read_text()
        assert label_text.strip() == ""

    def test_skips_empty_label_lines(self, tmp_path):
        src = tmp_path / "src"
        dst = tmp_path / "dst"
        self._write_yaml(src)
        src_images = src / "images" / "train"
        src_images.mkdir(parents=True)
        src_labels = src / "labels" / "train"
        src_labels.mkdir(parents=True)
        self._make_image(src_images / "frame.png", w=200, h=200)
        (src_labels / "frame.txt").write_text("0 0.5 0.5 0.1 0.1\n\n  \n")

        prepare_cropped_dataset(src, dst, (0, 0, 200, 200))

        label_text = (dst / "labels" / "train" / "frame.txt").read_text()
        assert label_text.strip() != ""


class TestRunFineTune:
    def _make_dataset(self, base: Path) -> None:
        (base / "dataset.yaml").write_text("names:\n  0: bird\n")

    @patch("lab.fine_tune.DATASET_DIR")
    @patch("lab.fine_tune.FINE_TUNED_MODELS_DIR")
    def test_run_without_preset_uses_dataset_dir(self, mock_models_dir, mock_dataset_dir, tmp_path):
        output_dir = tmp_path / "models" / "v1.0.0"
        mock_models_dir.__truediv__ = lambda self, other: output_dir
        mock_dataset_dir.__truediv__ = lambda self, other: tmp_path / "dataset" / other

        dataset_dir = tmp_path / "dataset"
        dataset_dir.mkdir()
        self._make_dataset(dataset_dir)

        mock_results = MagicMock()
        mock_results.results_dict = {
            "metrics/mAP50(B)": 0.85,
            "metrics/precision(B)": 0.9,
            "metrics/recall(B)": 0.8,
        }
        mock_yolo_instance = MagicMock()
        mock_yolo_instance.train.return_value = mock_results
        mock_yolo_class = MagicMock(return_value=mock_yolo_instance)

        with (
            patch("lab.fine_tune.FINE_TUNED_MODELS_DIR", tmp_path / "models"),
            patch("lab.fine_tune.DATASET_DIR", dataset_dir),
            patch.dict("sys.modules", {"ultralytics": MagicMock(YOLO=mock_yolo_class)}),
        ):
            result = run_fine_tune("v1.0.0", "test run")

        assert result == tmp_path / "models" / "v1.0.0"
        meta = json.loads((result / "meta.json").read_text())
        assert meta["version"] == "v1.0.0"
        assert meta["description"] == "test run"
        assert meta["preset"] is None

    @patch("lab.fine_tune.prepare_cropped_dataset")
    def test_run_with_preset_uses_cropped_dataset(self, mock_prepare, tmp_path):
        preset = {"regions": [[10, 20, 110, 120]], "params": {"imgsz": 320}}
        preset_path = tmp_path / "preset.json"
        preset_path.write_text(json.dumps(preset))

        dataset_dir = tmp_path / "orig_dataset"
        dataset_dir.mkdir()
        self._make_dataset(dataset_dir)

        def fake_prepare(src, dst, region):
            dst.mkdir(parents=True, exist_ok=True)
            self._make_dataset(dst)

        mock_prepare.side_effect = fake_prepare

        mock_results = MagicMock()
        mock_results.results_dict = {}
        mock_yolo_instance = MagicMock()
        mock_yolo_instance.train.return_value = mock_results
        mock_yolo_class = MagicMock(return_value=mock_yolo_instance)

        with (
            patch("lab.fine_tune.FINE_TUNED_MODELS_DIR", tmp_path / "models"),
            patch("lab.fine_tune.DATASET_DIR", dataset_dir),
            patch.dict("sys.modules", {"ultralytics": MagicMock(YOLO=mock_yolo_class)}),
        ):
            result = run_fine_tune("v1.0.0", "with preset", preset_path=preset_path)

        meta = json.loads((result / "meta.json").read_text())
        assert meta["preset"] == "preset.json"
        assert meta["training"]["imgsz"] == 320
        mock_prepare.assert_called_once()

    def test_on_epoch_callback_is_registered_and_called(self, tmp_path):
        dataset_dir = tmp_path / "dataset"
        dataset_dir.mkdir()
        self._make_dataset(dataset_dir)

        mock_results = MagicMock()
        mock_results.results_dict = {}
        mock_yolo_instance = MagicMock()
        mock_yolo_instance.train.return_value = mock_results

        callbacks: list = []

        def capture_callback(event, fn):
            callbacks.append((event, fn))

        mock_yolo_instance.add_callback.side_effect = capture_callback
        mock_yolo_class = MagicMock(return_value=mock_yolo_instance)

        epoch_calls: list[tuple[int, int]] = []

        def on_epoch(current, total):
            epoch_calls.append((current, total))

        with (
            patch("lab.fine_tune.FINE_TUNED_MODELS_DIR", tmp_path / "models"),
            patch("lab.fine_tune.DATASET_DIR", dataset_dir),
            patch.dict("sys.modules", {"ultralytics": MagicMock(YOLO=mock_yolo_class)}),
        ):
            run_fine_tune("v1.0.0", "epoch test", on_epoch=on_epoch)

        assert len(callbacks) == 1
        assert callbacks[0][0] == "on_train_epoch_end"

        # Simulate the callback being triggered
        fake_trainer = MagicMock()
        fake_trainer.epoch = 4
        callbacks[0][1](fake_trainer)
        assert epoch_calls == [(5, 100)]

    def test_best_weights_copied_when_present(self, tmp_path):
        dataset_dir = tmp_path / "dataset"
        dataset_dir.mkdir()
        self._make_dataset(dataset_dir)

        mock_results = MagicMock()
        mock_results.results_dict = {}
        mock_yolo_instance = MagicMock()
        mock_yolo_instance.train.return_value = mock_results
        mock_yolo_class = MagicMock(return_value=mock_yolo_instance)

        with (
            patch("lab.fine_tune.FINE_TUNED_MODELS_DIR", tmp_path / "models"),
            patch("lab.fine_tune.DATASET_DIR", dataset_dir),
            patch.dict("sys.modules", {"ultralytics": MagicMock(YOLO=mock_yolo_class)}),
        ):
            # Create best.pt before training runs
            def create_weights(data, epochs, batch, imgsz, project, name, exist_ok):
                weights_dir = Path(project) / name / "weights"
                weights_dir.mkdir(parents=True, exist_ok=True)
                (weights_dir / "best.pt").write_bytes(b"fake weights")
                return mock_results

            mock_yolo_instance.train.side_effect = create_weights
            result = run_fine_tune("v1.0.0", "weights test")

        assert (result / "model.pt").exists()

    def test_results_none_produces_empty_metrics(self, tmp_path):
        dataset_dir = tmp_path / "dataset"
        dataset_dir.mkdir()
        self._make_dataset(dataset_dir)

        mock_yolo_instance = MagicMock()
        mock_yolo_instance.train.return_value = None
        mock_yolo_class = MagicMock(return_value=mock_yolo_instance)

        with (
            patch("lab.fine_tune.FINE_TUNED_MODELS_DIR", tmp_path / "models"),
            patch("lab.fine_tune.DATASET_DIR", dataset_dir),
            patch.dict("sys.modules", {"ultralytics": MagicMock(YOLO=mock_yolo_class)}),
        ):
            result = run_fine_tune("v1.0.0", "no results")

        meta = json.loads((result / "meta.json").read_text())
        assert meta["metrics"] == {}

    def test_attribute_error_in_metrics_produces_empty_metrics(self, tmp_path):
        dataset_dir = tmp_path / "dataset"
        dataset_dir.mkdir()
        self._make_dataset(dataset_dir)

        mock_results = MagicMock()
        del mock_results.results_dict  # AttributeError on access
        mock_yolo_instance = MagicMock()
        mock_yolo_instance.train.return_value = mock_results
        mock_yolo_class = MagicMock(return_value=mock_yolo_instance)

        with (
            patch("lab.fine_tune.FINE_TUNED_MODELS_DIR", tmp_path / "models"),
            patch("lab.fine_tune.DATASET_DIR", dataset_dir),
            patch.dict("sys.modules", {"ultralytics": MagicMock(YOLO=mock_yolo_class)}),
        ):
            result = run_fine_tune("v1.0.0", "attr error")

        meta = json.loads((result / "meta.json").read_text())
        assert meta["metrics"] == {}

    def test_runs_dir_cleaned_up_after_training(self, tmp_path):
        dataset_dir = tmp_path / "dataset"
        dataset_dir.mkdir()
        self._make_dataset(dataset_dir)

        mock_results = MagicMock()
        mock_results.results_dict = {}
        mock_yolo_instance = MagicMock()
        mock_yolo_instance.train.return_value = mock_results
        mock_yolo_class = MagicMock(return_value=mock_yolo_instance)

        with (
            patch("lab.fine_tune.FINE_TUNED_MODELS_DIR", tmp_path / "models"),
            patch("lab.fine_tune.DATASET_DIR", dataset_dir),
            patch.dict("sys.modules", {"ultralytics": MagicMock(YOLO=mock_yolo_class)}),
        ):
            result = run_fine_tune("v1.0.0", "cleanup test")

        assert not (result / "runs").exists()

    def test_run_without_preset_uses_default_imgsz(self, tmp_path):
        dataset_dir = tmp_path / "dataset"
        dataset_dir.mkdir()
        self._make_dataset(dataset_dir)

        mock_results = MagicMock()
        mock_results.results_dict = {}
        mock_yolo_instance = MagicMock()
        mock_yolo_instance.train.return_value = mock_results
        mock_yolo_class = MagicMock(return_value=mock_yolo_instance)

        with (
            patch("lab.fine_tune.FINE_TUNED_MODELS_DIR", tmp_path / "models"),
            patch("lab.fine_tune.DATASET_DIR", dataset_dir),
            patch.dict("sys.modules", {"ultralytics": MagicMock(YOLO=mock_yolo_class)}),
        ):
            result = run_fine_tune("v1.0.0", "default imgsz")

        meta = json.loads((result / "meta.json").read_text())
        assert meta["training"]["imgsz"] == 480

    def test_preset_without_params_uses_default_imgsz(self, tmp_path):
        preset = {"regions": [[0, 0, 100, 100]]}
        preset_path = tmp_path / "preset.json"
        preset_path.write_text(json.dumps(preset))

        dataset_dir = tmp_path / "orig_dataset"
        dataset_dir.mkdir()
        self._make_dataset(dataset_dir)

        def fake_prepare(src, dst, region):
            dst.mkdir(parents=True, exist_ok=True)
            self._make_dataset(dst)

        mock_results = MagicMock()
        mock_results.results_dict = {}
        mock_yolo_instance = MagicMock()
        mock_yolo_instance.train.return_value = mock_results
        mock_yolo_class = MagicMock(return_value=mock_yolo_instance)

        with (
            patch("lab.fine_tune.FINE_TUNED_MODELS_DIR", tmp_path / "models"),
            patch("lab.fine_tune.DATASET_DIR", dataset_dir),
            patch("lab.fine_tune.prepare_cropped_dataset", side_effect=fake_prepare),
            patch.dict("sys.modules", {"ultralytics": MagicMock(YOLO=mock_yolo_class)}),
        ):
            result = run_fine_tune("v1.0.0", "no params preset", preset_path=preset_path)

        meta = json.loads((result / "meta.json").read_text())
        assert meta["training"]["imgsz"] == 480
