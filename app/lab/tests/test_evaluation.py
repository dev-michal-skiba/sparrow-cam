"""Unit tests for lab/evaluation.py."""

from __future__ import annotations

import json
import threading
from unittest.mock import MagicMock, patch

import pytest

from lab.evaluation import (
    EvaluationCancelledError,
    get_models_without_evaluation,
    run_evaluation,
)


class TestGetModelsWithoutEvaluation:
    @patch("lab.evaluation.FINE_TUNED_MODELS_DIR")
    def test_returns_empty_list_when_directory_not_exists(self, mock_models_dir):
        """Should return empty list if FINE_TUNED_MODELS_DIR doesn't exist."""
        mock_models_dir.exists.return_value = False

        result = get_models_without_evaluation()

        assert result == []

    @patch("lab.evaluation.FINE_TUNED_MODELS_DIR")
    def test_returns_empty_list_when_directory_empty(self, mock_models_dir):
        """Should return empty list if FINE_TUNED_MODELS_DIR is empty."""
        mock_models_dir.exists.return_value = True
        mock_models_dir.iterdir.return_value = []

        result = get_models_without_evaluation()

        assert result == []

    @patch("lab.evaluation.FINE_TUNED_MODELS_DIR")
    def test_skips_non_directory_entries(self, mock_models_dir, tmp_path):
        """Should skip non-directory entries."""
        # Create a fake file entry
        fake_file = tmp_path / "not_a_dir.txt"
        fake_file.write_text("fake")

        mock_models_dir.exists.return_value = True

        # Create a mock that behaves like a file (not a directory)
        mock_entry = MagicMock()
        mock_entry.is_dir.return_value = False
        mock_models_dir.iterdir.return_value = [mock_entry]

        result = get_models_without_evaluation()

        assert result == []

    @patch("lab.evaluation.FINE_TUNED_MODELS_DIR")
    def test_skips_models_missing_meta_file(self, mock_models_dir, tmp_path):
        """Should skip model directories without meta.json."""
        version_dir = tmp_path / "v1.0.0"
        version_dir.mkdir()
        (version_dir / "model.pt").write_bytes(b"fake")

        mock_models_dir.exists.return_value = True
        mock_models_dir.iterdir.return_value = [version_dir]

        result = get_models_without_evaluation()

        assert result == []

    @patch("lab.evaluation.FINE_TUNED_MODELS_DIR")
    def test_skips_models_missing_model_file(self, mock_models_dir, tmp_path):
        """Should skip model directories without model.pt."""
        version_dir = tmp_path / "v1.0.0"
        version_dir.mkdir()
        meta = {"description": "Test", "created_at": "2026-01-15T10:00:00Z"}
        (version_dir / "meta.json").write_text(json.dumps(meta))

        mock_models_dir.exists.return_value = True
        mock_models_dir.iterdir.return_value = [version_dir]

        result = get_models_without_evaluation()

        assert result == []

    @patch("lab.evaluation.FINE_TUNED_MODELS_DIR")
    def test_returns_models_without_evaluation(self, mock_models_dir, tmp_path):
        """Should return models that don't have evaluation results yet."""
        version_dir = tmp_path / "v1.0.0"
        version_dir.mkdir()
        meta = {
            "description": "Test model",
            "created_at": "2026-01-15T10:00:00Z",
        }
        (version_dir / "meta.json").write_text(json.dumps(meta))
        (version_dir / "model.pt").write_bytes(b"fake model")

        mock_models_dir.exists.return_value = True
        mock_models_dir.iterdir.return_value = [version_dir]

        result = get_models_without_evaluation()

        assert len(result) == 1
        assert result[0]["version"] == "v1.0.0"
        assert result[0]["description"] == "Test model"
        assert result[0]["created_at"] == "2026-01-15T10:00:00Z"
        assert "model_path" in result[0]

    @patch("lab.evaluation.FINE_TUNED_MODELS_DIR")
    def test_skips_models_with_evaluation(self, mock_models_dir, tmp_path):
        """Should skip models that already have evaluation results."""
        version_dir = tmp_path / "v1.0.0"
        version_dir.mkdir()
        meta = {
            "description": "Test model",
            "created_at": "2026-01-15T10:00:00Z",
        }
        (version_dir / "meta.json").write_text(json.dumps(meta))
        (version_dir / "model.pt").write_bytes(b"fake model")

        # Create evaluation directory with results
        eval_dir = version_dir / "evaluation"
        eval_dir.mkdir()
        (eval_dir / "results.json").write_text("{}")

        mock_models_dir.exists.return_value = True
        mock_models_dir.iterdir.return_value = [version_dir]

        result = get_models_without_evaluation()

        assert result == []

    @patch("lab.evaluation.FINE_TUNED_MODELS_DIR")
    def test_handles_invalid_meta_json(self, mock_models_dir, tmp_path):
        """Should skip models with invalid meta.json."""
        version_dir = tmp_path / "v1.0.0"
        version_dir.mkdir()
        (version_dir / "meta.json").write_text("invalid json {")
        (version_dir / "model.pt").write_bytes(b"fake model")

        mock_models_dir.exists.return_value = True
        mock_models_dir.iterdir.return_value = [version_dir]

        result = get_models_without_evaluation()

        assert result == []

    @patch("lab.evaluation.FINE_TUNED_MODELS_DIR")
    def test_sorts_by_created_at_descending(self, mock_models_dir, tmp_path):
        """Should sort models by created_at timestamp, newest first."""
        # Create two models with different timestamps
        v1_dir = tmp_path / "v1.0.0"
        v1_dir.mkdir()
        meta1 = {
            "description": "First model",
            "created_at": "2026-01-10T10:00:00Z",
        }
        (v1_dir / "meta.json").write_text(json.dumps(meta1))
        (v1_dir / "model.pt").write_bytes(b"fake1")

        v2_dir = tmp_path / "v1.0.1"
        v2_dir.mkdir()
        meta2 = {
            "description": "Second model",
            "created_at": "2026-01-20T10:00:00Z",
        }
        (v2_dir / "meta.json").write_text(json.dumps(meta2))
        (v2_dir / "model.pt").write_bytes(b"fake2")

        mock_models_dir.exists.return_value = True
        mock_models_dir.iterdir.return_value = [v1_dir, v2_dir]

        result = get_models_without_evaluation()

        assert len(result) == 2
        assert result[0]["version"] == "v1.0.1"  # newer first
        assert result[1]["version"] == "v1.0.0"

    @patch("lab.evaluation.FINE_TUNED_MODELS_DIR")
    def test_handles_missing_description(self, mock_models_dir, tmp_path):
        """Should handle models without description in meta.json."""
        version_dir = tmp_path / "v1.0.0"
        version_dir.mkdir()
        meta = {"created_at": "2026-01-15T10:00:00Z"}
        (version_dir / "meta.json").write_text(json.dumps(meta))
        (version_dir / "model.pt").write_bytes(b"fake model")

        mock_models_dir.exists.return_value = True
        mock_models_dir.iterdir.return_value = [version_dir]

        result = get_models_without_evaluation()

        assert len(result) == 1
        assert result[0]["description"] == ""


class TestEvaluationCancelledError:
    def test_is_exception(self):
        """Should be an Exception subclass."""
        assert issubclass(EvaluationCancelledError, Exception)

    def test_can_be_raised_and_caught(self):
        """Should be raisable and catchable."""
        with pytest.raises(EvaluationCancelledError):
            raise EvaluationCancelledError("test message")


class TestRunEvaluation:
    @patch("lab.evaluation.FINE_TUNED_MODELS_DIR")
    def test_raises_filenotfound_when_model_missing(self, mock_models_dir, tmp_path):
        """Should raise FileNotFoundError when model.pt doesn't exist."""
        version_dir = tmp_path / "v1.0.0"
        version_dir.mkdir()
        (version_dir / "meta.json").write_text(json.dumps({"classes": {}}))

        mock_models_dir.__truediv__ = lambda self, x: version_dir

        with pytest.raises(FileNotFoundError, match="Model not found"):
            run_evaluation("v1.0.0")

    @patch("lab.evaluation.FINE_TUNED_MODELS_DIR")
    def test_raises_filenotfound_when_meta_missing(self, mock_models_dir, tmp_path):
        """Should raise FileNotFoundError when meta.json doesn't exist."""
        version_dir = tmp_path / "v1.0.0"
        version_dir.mkdir()
        (version_dir / "model.pt").write_bytes(b"fake")

        mock_models_dir.__truediv__ = lambda self, x: version_dir

        with pytest.raises(FileNotFoundError, match="Meta file not found"):
            run_evaluation("v1.0.0")

    @patch("lab.evaluation.FINE_TUNED_MODELS_DIR")
    def test_raises_filenotfound_when_dataset_missing(self, mock_models_dir, tmp_path):
        """Should raise FileNotFoundError when dataset.yaml doesn't exist."""
        version_dir = tmp_path / "v1.0.0"
        version_dir.mkdir()
        (version_dir / "model.pt").write_bytes(b"fake")
        (version_dir / "meta.json").write_text(json.dumps({"classes": {}}))

        mock_models_dir.__truediv__ = lambda self, x: version_dir

        with pytest.raises(FileNotFoundError, match="Dataset not found"):
            run_evaluation("v1.0.0")

    @patch("ultralytics.YOLO")
    @patch("lab.evaluation.FINE_TUNED_MODELS_DIR")
    def test_raises_cancelled_when_cancel_event_set_before_yolo_load(self, mock_models_dir, mock_yolo, tmp_path):
        """Should raise EvaluationCancelledError when cancel_event is set before YOLO loads."""
        version_dir = tmp_path / "v1.0.0"
        version_dir.mkdir()
        (version_dir / "model.pt").write_bytes(b"fake")
        meta = {"classes": {}}
        (version_dir / "meta.json").write_text(json.dumps(meta))
        dataset_dir = version_dir / "dataset"
        dataset_dir.mkdir()
        (dataset_dir / "dataset.yaml").write_text("dummy")

        mock_models_dir.__truediv__ = lambda self, x: version_dir

        cancel_event = threading.Event()
        cancel_event.set()

        with pytest.raises(EvaluationCancelledError):
            run_evaluation("v1.0.0", cancel_event=cancel_event)

    @patch("ultralytics.YOLO")
    @patch("lab.evaluation.FINE_TUNED_MODELS_DIR")
    def test_raises_cancelled_when_cancel_event_set_after_yolo_load(self, mock_models_dir, mock_yolo, tmp_path):
        """Should raise EvaluationCancelledError when cancel_event is set after YOLO loads."""
        version_dir = tmp_path / "v1.0.0"
        version_dir.mkdir()
        (version_dir / "model.pt").write_bytes(b"fake")
        meta = {"classes": {}}
        (version_dir / "meta.json").write_text(json.dumps(meta))
        dataset_dir = version_dir / "dataset"
        dataset_dir.mkdir()
        (dataset_dir / "dataset.yaml").write_text("dummy")

        mock_models_dir.__truediv__ = lambda self, x: version_dir

        cancel_event = threading.Event()

        # Mock YOLO to set cancel_event when called
        def mock_yolo_init(*args, **kwargs):
            cancel_event.set()
            return MagicMock()

        mock_yolo.side_effect = mock_yolo_init

        with pytest.raises(EvaluationCancelledError):
            run_evaluation("v1.0.0", cancel_event=cancel_event)

    @patch("lab.evaluation.shutil.rmtree")
    @patch("lab.evaluation.shutil.copy2")
    @patch("ultralytics.YOLO")
    @patch("lab.evaluation.FINE_TUNED_MODELS_DIR")
    def test_runs_evaluation_successfully(self, mock_models_dir, mock_yolo, mock_copy2, mock_rmtree, tmp_path):
        """Should successfully run evaluation and save results."""
        version_dir = tmp_path / "v1.0.0"
        version_dir.mkdir()
        (version_dir / "model.pt").write_bytes(b"fake")
        meta = {"classes": {"0": "bird"}}
        (version_dir / "meta.json").write_text(json.dumps(meta))
        dataset_dir = version_dir / "dataset"
        dataset_dir.mkdir()
        (dataset_dir / "dataset.yaml").write_text("dummy")

        mock_models_dir.__truediv__ = lambda self, x: version_dir

        # Mock YOLO results
        mock_model = MagicMock()
        mock_results = MagicMock()
        mock_results.results_dict = {
            "metrics/mAP50(B)": 0.85,
            "metrics/mAP50-95(B)": 0.75,
            "metrics/precision(B)": 0.90,
            "metrics/recall(B)": 0.80,
        }
        mock_results.box = MagicMock(ap50=[0.85], ap=[0.75], p=[0.90], r=[0.80])
        mock_model.val.return_value = mock_results
        mock_yolo.return_value = mock_model

        result = run_evaluation("v1.0.0")

        assert result == version_dir / "evaluation"
        assert (version_dir / "evaluation" / "results.json").exists()

        # Verify results.json contains expected data
        results_data = json.loads((version_dir / "evaluation" / "results.json").read_text())
        assert results_data["version"] == "v1.0.0"
        assert "evaluated_at" in results_data
        assert results_data["metrics"]["mAP50"] == 0.85
        assert results_data["metrics"]["mAP50-95"] == 0.75
        assert len(results_data["class_metrics"]) == 1
        assert results_data["class_metrics"][0]["class_name"] == "bird"

    @patch("lab.evaluation.shutil.rmtree")
    @patch("lab.evaluation.shutil.copy2")
    @patch("ultralytics.YOLO")
    @patch("lab.evaluation.FINE_TUNED_MODELS_DIR")
    def test_handles_missing_results_dict_attributes(
        self, mock_models_dir, mock_yolo, mock_copy2, mock_rmtree, tmp_path
    ):
        """Should handle cases where results don't have expected attributes."""
        version_dir = tmp_path / "v1.0.0"
        version_dir.mkdir()
        (version_dir / "model.pt").write_bytes(b"fake")
        meta = {"classes": {"0": "bird"}}
        (version_dir / "meta.json").write_text(json.dumps(meta))
        dataset_dir = version_dir / "dataset"
        dataset_dir.mkdir()
        (dataset_dir / "dataset.yaml").write_text("dummy")

        mock_models_dir.__truediv__ = lambda self, x: version_dir

        # Mock YOLO with minimal results
        mock_model = MagicMock()
        mock_results = MagicMock()
        mock_results.results_dict = {}
        mock_results.box = None
        mock_model.val.return_value = mock_results
        mock_yolo.return_value = mock_model

        result = run_evaluation("v1.0.0")

        assert result == version_dir / "evaluation"
        results_data = json.loads((version_dir / "evaluation" / "results.json").read_text())
        assert results_data["metrics"]["mAP50"] == 0
        assert results_data["class_metrics"] == []

    @patch("lab.evaluation.shutil.rmtree")
    @patch("lab.evaluation.shutil.copy2")
    @patch("ultralytics.YOLO")
    @patch("lab.evaluation.FINE_TUNED_MODELS_DIR")
    def test_handles_none_results(self, mock_models_dir, mock_yolo, mock_copy2, mock_rmtree, tmp_path):
        """Should handle case when model.val() returns None."""
        version_dir = tmp_path / "v1.0.0"
        version_dir.mkdir()
        (version_dir / "model.pt").write_bytes(b"fake")
        meta = {"classes": {}}
        (version_dir / "meta.json").write_text(json.dumps(meta))
        dataset_dir = version_dir / "dataset"
        dataset_dir.mkdir()
        (dataset_dir / "dataset.yaml").write_text("dummy")

        mock_models_dir.__truediv__ = lambda self, x: version_dir

        # Mock YOLO to return None
        mock_model = MagicMock()
        mock_model.val.return_value = None
        mock_yolo.return_value = mock_model

        result = run_evaluation("v1.0.0")

        assert result == version_dir / "evaluation"
        results_data = json.loads((version_dir / "evaluation" / "results.json").read_text())
        assert results_data["metrics"] == {}
        assert results_data["class_metrics"] == []

    @patch("lab.evaluation.shutil.rmtree")
    @patch("lab.evaluation.shutil.copy2")
    @patch("ultralytics.YOLO")
    @patch("lab.evaluation.FINE_TUNED_MODELS_DIR")
    def test_copies_plot_files_to_eval_dir(self, mock_models_dir, mock_yolo, mock_copy2, mock_rmtree, tmp_path):
        """Should copy plot PNG and CSV files from runs dir to eval dir."""
        version_dir = tmp_path / "v1.0.0"
        version_dir.mkdir()
        (version_dir / "model.pt").write_bytes(b"fake")
        meta = {"classes": {}}
        (version_dir / "meta.json").write_text(json.dumps(meta))
        dataset_dir = version_dir / "dataset"
        dataset_dir.mkdir()
        (dataset_dir / "dataset.yaml").write_text("dummy")

        # Create fake plot files
        eval_dir = version_dir / "evaluation"
        runs_dir = eval_dir / "runs" / "eval"
        runs_dir.mkdir(parents=True)
        (runs_dir / "confusion_matrix.png").write_bytes(b"png")
        (runs_dir / "results.csv").write_bytes(b"csv")

        mock_models_dir.__truediv__ = lambda self, x: version_dir

        mock_model = MagicMock()
        mock_results = MagicMock()
        mock_results.results_dict = {}
        mock_results.box = None
        mock_model.val.return_value = mock_results
        mock_yolo.return_value = mock_model

        result = run_evaluation("v1.0.0")

        assert result == eval_dir
        # copy2 should have been called for plot files
        assert mock_copy2.call_count >= 2

    @patch("lab.evaluation.shutil.rmtree")
    @patch("lab.evaluation.shutil.copy2")
    @patch("ultralytics.YOLO")
    @patch("lab.evaluation.FINE_TUNED_MODELS_DIR")
    def test_cleans_up_runs_directory(self, mock_models_dir, mock_yolo, mock_copy2, mock_rmtree, tmp_path):
        """Should clean up the temporary runs directory."""
        version_dir = tmp_path / "v1.0.0"
        version_dir.mkdir()
        (version_dir / "model.pt").write_bytes(b"fake")
        meta = {"classes": {}}
        (version_dir / "meta.json").write_text(json.dumps(meta))
        dataset_dir = version_dir / "dataset"
        dataset_dir.mkdir()
        (dataset_dir / "dataset.yaml").write_text("dummy")

        mock_models_dir.__truediv__ = lambda self, x: version_dir

        mock_model = MagicMock()
        mock_results = MagicMock()
        mock_results.results_dict = {}
        mock_results.box = None
        mock_model.val.return_value = mock_results
        mock_yolo.return_value = mock_model

        run_evaluation("v1.0.0")

        # rmtree should have been called to clean up runs dir
        assert mock_rmtree.called

    @patch("lab.evaluation.shutil.rmtree")
    @patch("lab.evaluation.shutil.copy2")
    @patch("ultralytics.YOLO")
    @patch("lab.evaluation.FINE_TUNED_MODELS_DIR")
    def test_creates_evaluation_directory(self, mock_models_dir, mock_yolo, mock_copy2, mock_rmtree, tmp_path):
        """Should create the evaluation directory."""
        version_dir = tmp_path / "v1.0.0"
        version_dir.mkdir()
        (version_dir / "model.pt").write_bytes(b"fake")
        meta = {"classes": {}}
        (version_dir / "meta.json").write_text(json.dumps(meta))
        dataset_dir = version_dir / "dataset"
        dataset_dir.mkdir()
        (dataset_dir / "dataset.yaml").write_text("dummy")

        mock_models_dir.__truediv__ = lambda self, x: version_dir

        mock_model = MagicMock()
        mock_results = MagicMock()
        mock_results.results_dict = {}
        mock_results.box = None
        mock_model.val.return_value = mock_results
        mock_yolo.return_value = mock_model

        result = run_evaluation("v1.0.0")

        assert (version_dir / "evaluation").exists()
        assert result == version_dir / "evaluation"

    @patch("lab.evaluation.shutil.rmtree")
    @patch("lab.evaluation.shutil.copy2")
    @patch("ultralytics.YOLO")
    @patch("lab.evaluation.FINE_TUNED_MODELS_DIR")
    def test_saves_evaluated_at_timestamp(self, mock_models_dir, mock_yolo, mock_copy2, mock_rmtree, tmp_path):
        """Should include a valid evaluated_at timestamp in results."""
        version_dir = tmp_path / "v1.0.0"
        version_dir.mkdir()
        (version_dir / "model.pt").write_bytes(b"fake")
        meta = {"classes": {}}
        (version_dir / "meta.json").write_text(json.dumps(meta))
        dataset_dir = version_dir / "dataset"
        dataset_dir.mkdir()
        (dataset_dir / "dataset.yaml").write_text("dummy")

        mock_models_dir.__truediv__ = lambda self, x: version_dir

        mock_model = MagicMock()
        mock_results = MagicMock()
        mock_results.results_dict = {}
        mock_results.box = None
        mock_model.val.return_value = mock_results
        mock_yolo.return_value = mock_model

        run_evaluation("v1.0.0")

        results_data = json.loads((version_dir / "evaluation" / "results.json").read_text())
        evaluated_at = results_data["evaluated_at"]
        assert evaluated_at.endswith("Z")
        assert "T" in evaluated_at
        assert len(evaluated_at) == 20  # ISO format with Z

    @patch("lab.evaluation.shutil.rmtree")
    @patch("lab.evaluation.shutil.copy2")
    @patch("ultralytics.YOLO")
    @patch("lab.evaluation.FINE_TUNED_MODELS_DIR")
    def test_passes_correct_parameters_to_model_val(
        self, mock_models_dir, mock_yolo, mock_copy2, mock_rmtree, tmp_path
    ):
        """Should call model.val() with correct parameters."""
        version_dir = tmp_path / "v1.0.0"
        version_dir.mkdir()
        (version_dir / "model.pt").write_bytes(b"fake")
        meta = {"classes": {}}
        (version_dir / "meta.json").write_text(json.dumps(meta))
        dataset_dir = version_dir / "dataset"
        dataset_dir.mkdir()
        (dataset_dir / "dataset.yaml").write_text("dummy")

        mock_models_dir.__truediv__ = lambda self, x: version_dir

        mock_model = MagicMock()
        mock_results = MagicMock()
        mock_results.results_dict = {}
        mock_results.box = None
        mock_model.val.return_value = mock_results
        mock_yolo.return_value = mock_model

        run_evaluation("v1.0.0")

        # Verify val() was called with split="val"
        mock_model.val.assert_called_once()
        call_kwargs = mock_model.val.call_args[1]
        assert call_kwargs["split"] == "val"
        assert "data" in call_kwargs
        assert "project" in call_kwargs
        assert "name" in call_kwargs

    @patch("lab.evaluation.shutil.rmtree")
    @patch("lab.evaluation.shutil.copy2")
    @patch("ultralytics.YOLO")
    @patch("lab.evaluation.FINE_TUNED_MODELS_DIR")
    def test_raises_cancelled_after_val_call(self, mock_models_dir, mock_yolo, mock_copy2, mock_rmtree, tmp_path):
        """Should raise EvaluationCancelledError when cancel_event is set after val()."""
        version_dir = tmp_path / "v1.0.0"
        version_dir.mkdir()
        (version_dir / "model.pt").write_bytes(b"fake")
        meta = {"classes": {}}
        (version_dir / "meta.json").write_text(json.dumps(meta))
        dataset_dir = version_dir / "dataset"
        dataset_dir.mkdir()
        (dataset_dir / "dataset.yaml").write_text("dummy")

        mock_models_dir.__truediv__ = lambda self, x: version_dir

        cancel_event = threading.Event()

        mock_model = MagicMock()
        mock_results = MagicMock()
        mock_results.results_dict = {}
        mock_results.box = None

        def val_side_effect(*args, **kwargs):
            cancel_event.set()
            return mock_results

        mock_model.val.side_effect = val_side_effect
        mock_yolo.return_value = mock_model

        with pytest.raises(EvaluationCancelledError):
            run_evaluation("v1.0.0", cancel_event=cancel_event)

    @patch("lab.evaluation.shutil.rmtree")
    @patch("lab.evaluation.shutil.copy2")
    @patch("ultralytics.YOLO")
    @patch("lab.evaluation.FINE_TUNED_MODELS_DIR")
    def test_handles_per_class_metrics_with_multiple_classes(
        self, mock_models_dir, mock_yolo, mock_copy2, mock_rmtree, tmp_path
    ):
        """Should correctly process per-class metrics for multiple classes."""
        version_dir = tmp_path / "v1.0.0"
        version_dir.mkdir()
        (version_dir / "model.pt").write_bytes(b"fake")
        meta = {
            "classes": {
                "0": "robin",
                "1": "sparrow",
                "2": "cardinal",
            }
        }
        (version_dir / "meta.json").write_text(json.dumps(meta))
        dataset_dir = version_dir / "dataset"
        dataset_dir.mkdir()
        (dataset_dir / "dataset.yaml").write_text("dummy")

        mock_models_dir.__truediv__ = lambda self, x: version_dir

        mock_model = MagicMock()
        mock_results = MagicMock()
        mock_results.results_dict = {
            "metrics/mAP50(B)": 0.85,
            "metrics/mAP50-95(B)": 0.75,
            "metrics/precision(B)": 0.90,
            "metrics/recall(B)": 0.80,
        }
        mock_results.box = MagicMock(
            ap50=[0.85, 0.88, 0.82],
            ap=[0.75, 0.78, 0.72],
            p=[0.90, 0.92, 0.88],
            r=[0.80, 0.83, 0.77],
        )
        mock_model.val.return_value = mock_results
        mock_yolo.return_value = mock_model

        run_evaluation("v1.0.0")

        results_data = json.loads((version_dir / "evaluation" / "results.json").read_text())
        assert len(results_data["class_metrics"]) == 3
        assert results_data["class_metrics"][0]["class_name"] == "robin"
        assert results_data["class_metrics"][1]["class_name"] == "sparrow"
        assert results_data["class_metrics"][2]["class_name"] == "cardinal"
        assert results_data["class_metrics"][0]["AP50"] == 0.85
