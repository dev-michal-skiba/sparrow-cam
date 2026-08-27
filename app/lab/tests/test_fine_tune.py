"""Unit tests for fine tuning the YOLO model."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from lab.fine_tune import (
    BIRD_CLASS_ID,
    BIRD_CLASS_NAME,
    DESCRIPTION_MAX_LENGTH,
    FineTuneError,
    _generic_label,
    _write_metadata,
    build_dataset,
    parse_args,
    resolve_description,
    resolve_version,
    select_training_frames,
)
from lab.frame_selection import Frame


class TestFineTuneError:
    """Tests for FineTuneError exception."""

    def test_fine_tune_error_is_exception(self):
        """Test that FineTuneError is an Exception."""
        assert issubclass(FineTuneError, Exception)

    def test_fine_tune_error_with_message(self):
        """Test that FineTuneError can be raised with a message."""
        with pytest.raises(FineTuneError, match="Test error"):
            raise FineTuneError("Test error")


class TestParseArgs:
    """Tests for parse_args function."""

    def test_parse_args_no_arguments(self):
        """Test parsing with no arguments."""
        with patch("sys.argv", ["fine_tune.py"]):
            args = parse_args()
            assert args.version is None
            assert args.description is None

    def test_parse_args_with_version(self):
        """Test parsing with version argument."""
        with patch("sys.argv", ["fine_tune.py", "--version", "v1.0.0"]):
            args = parse_args()
            assert args.version == "v1.0.0"
            assert args.description is None

    def test_parse_args_with_description(self):
        """Test parsing with description argument."""
        with patch("sys.argv", ["fine_tune.py", "--description", "A great model"]):
            args = parse_args()
            assert args.version is None
            assert args.description == "A great model"

    def test_parse_args_with_both(self):
        """Test parsing with both version and description."""
        with patch("sys.argv", ["fine_tune.py", "--version", "v1.0.0", "--description", "A great model"]):
            args = parse_args()
            assert args.version == "v1.0.0"
            assert args.description == "A great model"


class TestResolveVersion:
    """Tests for resolve_version function."""

    def test_resolve_version_valid_format(self):
        """Test resolving valid version format."""
        version = resolve_version("v1.0.0")
        assert version == "v1.0.0"

    def test_resolve_version_another_valid_format(self):
        """Test resolving another valid version format."""
        version = resolve_version("v2.1.5")
        assert version == "v2.1.5"

    def test_resolve_version_invalid_format(self):
        """Test that invalid format raises error."""
        with pytest.raises(FineTuneError, match="Version must look like v1.0.0"):
            resolve_version("1.0.0")

    def test_resolve_version_missing_v_prefix(self):
        """Test that missing v prefix raises error."""
        with pytest.raises(FineTuneError):
            resolve_version("1.0.0")

    def test_resolve_version_too_many_parts(self):
        """Test that too many version parts raises error."""
        with pytest.raises(FineTuneError):
            resolve_version("v1.0.0.0")

    def test_resolve_version_none_prompts(self):
        """Test that None version triggers prompt."""
        with patch("lab.fine_tune.prompt_version", return_value="v1.0.0"):
            version = resolve_version(None)
            assert version == "v1.0.0"


class TestResolveDescription:
    """Tests for resolve_description function."""

    def test_resolve_description_valid(self):
        """Test resolving valid description."""
        description = resolve_description("A great model")
        assert description == "A great model"

    def test_resolve_description_single_character(self):
        """Test single character description is valid."""
        description = resolve_description("a")
        assert description == "a"

    def test_resolve_description_max_length(self):
        """Test description at max length."""
        max_desc = "x" * DESCRIPTION_MAX_LENGTH
        description = resolve_description(max_desc)
        assert description == max_desc

    def test_resolve_description_empty_string(self):
        """Test that empty string raises error."""
        with pytest.raises(FineTuneError, match="Description must be"):
            resolve_description("")

    def test_resolve_description_exceeds_max_length(self):
        """Test that exceeding max length raises error."""
        too_long = "x" * (DESCRIPTION_MAX_LENGTH + 1)
        with pytest.raises(FineTuneError, match="Description must be"):
            resolve_description(too_long)

    def test_resolve_description_none_prompts(self):
        """Test that None description triggers prompt."""
        with patch("lab.fine_tune.prompt_description", return_value="A great model"):
            description = resolve_description(None)
            assert description == "A great model"


class TestPromptVersion:
    """Tests for prompt_version function."""

    def test_prompt_version_accepts_valid(self):
        """Test that prompt accepts valid version."""
        with patch("builtins.input", return_value="v1.0.0"):
            version = __import__("lab.fine_tune", fromlist=["prompt_version"]).prompt_version()
            assert version == "v1.0.0"

    def test_prompt_version_rejects_invalid_then_accepts(self):
        """Test that prompt rejects invalid then accepts valid."""
        with patch("builtins.input", side_effect=["invalid", "v1.0.0"]), patch("builtins.print"):
            version = __import__("lab.fine_tune", fromlist=["prompt_version"]).prompt_version()
            assert version == "v1.0.0"

    def test_prompt_version_strips_whitespace(self):
        """Test that prompt strips whitespace."""
        with patch("builtins.input", return_value="  v1.0.0  "):
            version = __import__("lab.fine_tune", fromlist=["prompt_version"]).prompt_version()
            assert version == "v1.0.0"


class TestPromptDescription:
    """Tests for prompt_description function."""

    def test_prompt_description_accepts_valid(self):
        """Test that prompt accepts valid description."""
        with patch("builtins.input", return_value="A great model"):
            description = __import__("lab.fine_tune", fromlist=["prompt_description"]).prompt_description()
            assert description == "A great model"

    def test_prompt_description_rejects_empty_then_accepts(self):
        """Test that prompt rejects empty then accepts valid."""
        with patch("builtins.input", side_effect=["", "A great model"]), patch("builtins.print"):
            description = __import__("lab.fine_tune", fromlist=["prompt_description"]).prompt_description()
            assert description == "A great model"

    def test_prompt_description_strips_whitespace(self):
        """Test that prompt strips whitespace."""
        with patch("builtins.input", return_value="  A great model  "):
            description = __import__("lab.fine_tune", fromlist=["prompt_description"]).prompt_description()
            assert description == "A great model"


class TestGenericLabel:
    """Tests for _generic_label function."""

    def test_generic_label_empty_file(self, tmp_path):
        """Test converting empty label file."""
        label_path = tmp_path / "label.txt"
        label_path.write_text("")

        result = _generic_label(label_path)
        assert result == ""

    def test_generic_label_single_box(self, tmp_path):
        """Test converting single box."""
        label_path = tmp_path / "label.txt"
        label_path.write_text("0 0.5 0.5 0.2 0.2\n")

        result = _generic_label(label_path)
        assert result == f"{BIRD_CLASS_ID} 0.5 0.5 0.2 0.2\n"

    def test_generic_label_multiple_boxes(self, tmp_path):
        """Test converting multiple boxes."""
        label_path = tmp_path / "label.txt"
        label_path.write_text("0 0.5 0.5 0.2 0.2\n1 0.3 0.3 0.1 0.1\n")

        result = _generic_label(label_path)
        lines = result.split("\n")
        assert len([line for line in lines if line.strip()]) == 2
        assert all(line.startswith(str(BIRD_CLASS_ID)) for line in lines if line.strip())

    def test_generic_label_different_bird_types(self, tmp_path):
        """Test that all boxes become single class."""
        label_path = tmp_path / "label.txt"
        label_path.write_text("1 0.5 0.5 0.2 0.2\n2 0.3 0.3 0.1 0.1\n3 0.7 0.7 0.1 0.1\n")

        result = _generic_label(label_path)
        lines = result.split("\n")
        assert len([line for line in lines if line.strip()]) == 3
        assert all(line.startswith(str(BIRD_CLASS_ID)) for line in lines if line.strip())

    def test_generic_label_skips_empty_lines(self, tmp_path):
        """Test that empty lines are skipped."""
        label_path = tmp_path / "label.txt"
        label_path.write_text("0 0.5 0.5 0.2 0.2\n\n1 0.3 0.3 0.1 0.1\n  \n")

        result = _generic_label(label_path)
        lines = result.split("\n")
        assert len([line for line in lines if line.strip()]) == 2


class TestWriteMetadata:
    """Tests for _write_metadata function."""

    def test_write_metadata_creates_file(self, tmp_path):
        """Test that metadata file is created."""
        _write_metadata(tmp_path, "v1.0.0", "A great model")

        metadata_path = tmp_path / "metadata.json"
        assert metadata_path.is_file()

    def test_write_metadata_content(self, tmp_path):
        """Test metadata file content."""
        _write_metadata(tmp_path, "v1.0.0", "A great model")

        metadata_path = tmp_path / "metadata.json"
        metadata = json.loads(metadata_path.read_text())

        assert metadata["version"] == "v1.0.0"
        assert metadata["description"] == "A great model"
        assert "created_at" in metadata
        assert "T" in metadata["created_at"]  # ISO format includes T

    def test_write_metadata_timestamp_format(self, tmp_path):
        """Test that timestamp is ISO format."""
        _write_metadata(tmp_path, "v1.0.0", "Test")

        metadata_path = tmp_path / "metadata.json"
        metadata = json.loads(metadata_path.read_text())

        timestamp = metadata["created_at"]
        # Should be ISO format with Z suffix
        assert "+" in timestamp or "Z" in timestamp


class TestBuildDataset:
    """Tests for build_dataset function."""

    def test_build_dataset_creates_directories(self, tmp_path):
        """Test that dataset directories are created."""
        frames = [
            Frame(tmp_path / "orig_images" / "img.jpg", tmp_path / "orig_labels" / "img.txt", 2026, (6, 25), 8, (0,))
        ]
        # Create original files
        (tmp_path / "orig_images").mkdir()
        (tmp_path / "orig_labels").mkdir()
        (tmp_path / "orig_images" / "img.jpg").write_text("image")
        (tmp_path / "orig_labels" / "img.txt").write_text("0 0.5 0.5 0.2 0.2\n")

        dataset_dir = tmp_path / "dataset"
        build_dataset(frames, dataset_dir)

        assert (dataset_dir / "images").is_dir()
        assert (dataset_dir / "labels").is_dir()

    def test_build_dataset_copies_images(self, tmp_path):
        """Test that images are copied."""
        (tmp_path / "orig_images").mkdir()
        (tmp_path / "orig_labels").mkdir()
        (tmp_path / "orig_images" / "img.jpg").write_text("image data")
        (tmp_path / "orig_labels" / "img.txt").write_text("0 0.5 0.5 0.2 0.2\n")

        frames = [
            Frame(
                tmp_path / "orig_images" / "img.jpg",
                tmp_path / "orig_labels" / "img.txt",
                2026,
                (6, 25),
                8,
                (0,),
            )
        ]

        dataset_dir = tmp_path / "dataset"
        build_dataset(frames, dataset_dir)

        assert (dataset_dir / "images" / "img.jpg").is_file()
        assert (dataset_dir / "images" / "img.jpg").read_text() == "image data"

    def test_build_dataset_converts_labels(self, tmp_path):
        """Test that labels are converted to single class."""
        (tmp_path / "orig_images").mkdir()
        (tmp_path / "orig_labels").mkdir()
        (tmp_path / "orig_images" / "img.jpg").write_text("image")
        (tmp_path / "orig_labels" / "img.txt").write_text("1 0.5 0.5 0.2 0.2\n2 0.3 0.3 0.1 0.1\n")

        frames = [
            Frame(
                tmp_path / "orig_images" / "img.jpg",
                tmp_path / "orig_labels" / "img.txt",
                2026,
                (6, 25),
                8,
                (1, 2),
            )
        ]

        dataset_dir = tmp_path / "dataset"
        build_dataset(frames, dataset_dir)

        label_content = (dataset_dir / "labels" / "img.txt").read_text()
        lines = [line for line in label_content.split("\n") if line.strip()]
        assert len(lines) == 2
        assert all(line.startswith(str(BIRD_CLASS_ID)) for line in lines)

    def test_build_dataset_creates_yaml(self, tmp_path):
        """Test that dataset.yaml is created."""
        (tmp_path / "orig_images").mkdir()
        (tmp_path / "orig_labels").mkdir()
        (tmp_path / "orig_images" / "img.jpg").write_text("image")
        (tmp_path / "orig_labels" / "img.txt").write_text("0 0.5 0.5 0.2 0.2\n")

        frames = [
            Frame(
                tmp_path / "orig_images" / "img.jpg",
                tmp_path / "orig_labels" / "img.txt",
                2026,
                (6, 25),
                8,
                (0,),
            )
        ]

        dataset_dir = tmp_path / "dataset"
        yaml_path = build_dataset(frames, dataset_dir)

        assert yaml_path == dataset_dir / "dataset.yaml"
        assert yaml_path.is_file()

    def test_build_dataset_yaml_content(self, tmp_path):
        """Test dataset.yaml content."""
        (tmp_path / "orig_images").mkdir()
        (tmp_path / "orig_labels").mkdir()
        (tmp_path / "orig_images" / "img.jpg").write_text("image")
        (tmp_path / "orig_labels" / "img.txt").write_text("0 0.5 0.5 0.2 0.2\n")

        frames = [
            Frame(
                tmp_path / "orig_images" / "img.jpg",
                tmp_path / "orig_labels" / "img.txt",
                2026,
                (6, 25),
                8,
                (0,),
            )
        ]

        dataset_dir = tmp_path / "dataset"
        yaml_path = build_dataset(frames, dataset_dir)

        yaml_content = yaml_path.read_text()
        assert f"path: {dataset_dir}" in yaml_content
        assert "train: images" in yaml_content
        assert "val: images" in yaml_content
        assert f"{BIRD_CLASS_ID}: {BIRD_CLASS_NAME}" in yaml_content

    def test_build_dataset_multiple_frames(self, tmp_path):
        """Test building dataset with multiple frames."""
        (tmp_path / "orig_images").mkdir()
        (tmp_path / "orig_labels").mkdir()

        frames = []
        for i in range(5):
            img_path = tmp_path / "orig_images" / f"img{i}.jpg"
            label_path = tmp_path / "orig_labels" / f"img{i}.txt"
            img_path.write_text(f"image {i}")
            label_path.write_text(f"{i} 0.5 0.5 0.2 0.2\n")
            frames.append(Frame(img_path, label_path, 2026, (6, 25), 8, (i,)))

        dataset_dir = tmp_path / "dataset"
        build_dataset(frames, dataset_dir)

        assert len(list((dataset_dir / "images").glob("*.jpg"))) == 5
        assert len(list((dataset_dir / "labels").glob("*.txt"))) == 5


class TestSelectTrainingFrames:
    """Tests for select_training_frames function."""

    def test_select_training_frames_no_dataset(self):
        """Test that error is raised when no dataset found."""
        with patch("lab.fine_tune.DATASET_DIR", Path("/nonexistent")):
            with pytest.raises(FineTuneError, match="No dataset frames found"):
                select_training_frames()

    def test_select_training_frames_separates_positive_negative(self, tmp_path):
        """Test that positive and negative frames are separated."""
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

        with patch("lab.fine_tune.DATASET_DIR", tmp_path):
            frames = select_training_frames()

        # Should have both positive and negative frames
        positives = [f for f in frames if f.is_positive]
        negatives = [f for f in frames if not f.is_positive]
        assert len(positives) > 0
        assert len(negatives) > 0

    def test_select_training_frames_deterministic_seed(self, tmp_path):
        """Test that selection uses dataset seed for determinism."""
        images_dir = tmp_path / "images"
        labels_dir = tmp_path / "labels"
        images_dir.mkdir()
        labels_dir.mkdir()

        for i in range(50):
            img_path = images_dir / f"2026-06-25_auto_2026-06-25T{i:02d}0000Z_uuid{i}_sparrow_cam-4031.jpg"
            label_path = labels_dir / f"2026-06-25_auto_2026-06-25T{i:02d}0000Z_uuid{i}_sparrow_cam-4031.txt"
            img_path.write_text("image")
            label_path.write_text("0 0.5 0.5 0.2 0.2\n" if i % 3 != 0 else "")

        with patch("lab.fine_tune.DATASET_DIR", tmp_path):
            frames1 = select_training_frames()
            frames2 = select_training_frames()

        # Same dataset should produce same selection
        assert frames1 == frames2


class TestTrain:
    """Tests for train function (mocked YOLO training)."""

    def test_train_creates_best_weights(self, tmp_path):
        """Test that train function creates best weights file."""
        dataset_yaml = tmp_path / "dataset.yaml"
        dataset_yaml.write_text("test")
        output_dir = tmp_path / "output"

        # Create the expected structure
        runs_dir = output_dir / "runs" / "train" / "weights"
        runs_dir.mkdir(parents=True)
        (runs_dir / "best.pt").write_text("weights")

        with patch("lab.fine_tune.BASE_MODEL_PATH", Path("/fake/model.pt")), patch("ultralytics.YOLO") as mock_yolo:
            mock_model = MagicMock()
            mock_yolo.return_value = mock_model

            from lab.fine_tune import train

            result = train(dataset_yaml, output_dir)

            assert result == runs_dir / "best.pt"
            mock_model.train.assert_called_once()

    def test_train_raises_if_no_weights(self, tmp_path):
        """Test that train raises error if weights not found."""
        dataset_yaml = tmp_path / "dataset.yaml"
        dataset_yaml.write_text("test")
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        with patch("lab.fine_tune.BASE_MODEL_PATH", Path("/fake/model.pt")), patch("ultralytics.YOLO") as mock_yolo:
            mock_model = MagicMock()
            mock_yolo.return_value = mock_model

            from lab.fine_tune import train

            with pytest.raises(FineTuneError, match="Training produced no weights"):
                train(dataset_yaml, output_dir)

    def test_train_calls_yolo_with_correct_params(self, tmp_path):
        """Test that train calls YOLO with correct parameters."""
        dataset_yaml = tmp_path / "dataset.yaml"
        dataset_yaml.write_text("test")
        output_dir = tmp_path / "output"

        runs_dir = output_dir / "runs" / "train" / "weights"
        runs_dir.mkdir(parents=True)
        (runs_dir / "best.pt").write_text("weights")

        with patch("lab.fine_tune.BASE_MODEL_PATH", Path("/fake/model.pt")), patch("ultralytics.YOLO") as mock_yolo:
            mock_model = MagicMock()
            mock_yolo.return_value = mock_model

            from lab.fine_tune import train

            train(dataset_yaml, output_dir)

            # Verify train was called with expected parameters
            call_kwargs = mock_model.train.call_args[1]
            assert str(dataset_yaml) in call_kwargs["data"]
            assert call_kwargs["epochs"] == 100
            assert call_kwargs["batch"] == 16
            assert call_kwargs["imgsz"] == 640


class TestMain:
    """Tests for main function."""

    def test_main_creates_output_directory(self, tmp_path):
        """Test that main creates output directory."""
        with (
            patch("lab.fine_tune.parse_args") as mock_parse,
            patch("lab.fine_tune.resolve_version", return_value="v1.0.0"),
            patch("lab.fine_tune.resolve_description", return_value="Test model"),
            patch("lab.fine_tune.FINE_TUNED_DIR", tmp_path / "fine_tuned"),
            patch("lab.fine_tune.BASE_MODEL_NAME", "yolo26n"),
            patch("lab.fine_tune.select_training_frames") as mock_select,
            patch("lab.fine_tune.build_dataset") as mock_build,
            patch("lab.fine_tune.train") as mock_train,
            patch("lab.fine_tune.shutil.copy2"),
            patch("lab.fine_tune._write_metadata"),
            patch("logging.basicConfig"),
        ):
            mock_parse.return_value = MagicMock(version="v1.0.0", description="Test model")
            mock_select.return_value = []
            mock_build.return_value = Path("/fake/dataset.yaml")
            mock_train.return_value = Path("/fake/weights.pt")

            from lab.fine_tune import main

            main()

            # Should have called the main functions
            mock_select.assert_called_once()

    def test_main_raises_if_output_dir_exists(self, tmp_path):
        """Test that main raises error if output directory already exists."""
        fine_tuned_dir = tmp_path / "fine_tuned"
        model_dir = fine_tuned_dir / "yolo26n_v1.0.0"
        model_dir.mkdir(parents=True)

        with (
            patch("lab.fine_tune.parse_args") as mock_parse,
            patch("lab.fine_tune.resolve_version", return_value="v1.0.0"),
            patch("lab.fine_tune.resolve_description", return_value="Test model"),
            patch("lab.fine_tune.FINE_TUNED_DIR", fine_tuned_dir),
            patch("lab.fine_tune.BASE_MODEL_NAME", "yolo26n"),
        ):
            mock_parse.return_value = MagicMock(version="v1.0.0", description="Test model")

            from lab.fine_tune import main

            with pytest.raises(FineTuneError, match="Model directory already exists"):
                main()

    def test_main_calls_all_steps(self, tmp_path):
        """Test that main calls all workflow steps."""
        with (
            patch("lab.fine_tune.parse_args") as mock_parse,
            patch("lab.fine_tune.resolve_version", return_value="v1.0.0") as mock_resolve_version,
            patch("lab.fine_tune.resolve_description", return_value="Test") as mock_resolve_desc,
            patch("lab.fine_tune.FINE_TUNED_DIR", tmp_path / "fine_tuned"),
            patch("lab.fine_tune.BASE_MODEL_NAME", "yolo26n"),
            patch("lab.fine_tune.select_training_frames", return_value=[]) as mock_select,
            patch("lab.fine_tune.build_dataset") as mock_build,
            patch("lab.fine_tune.train") as mock_train,
            patch("lab.fine_tune.shutil.copy2") as mock_copy,
            patch("lab.fine_tune._write_metadata") as mock_metadata,
            patch("logging.basicConfig"),
        ):
            mock_parse.return_value = MagicMock(version="v1.0.0", description="Test")
            mock_build.return_value = Path("/fake/dataset.yaml")
            mock_train.return_value = Path("/fake/best.pt")

            from lab.fine_tune import main

            main()

            mock_resolve_version.assert_called_once_with("v1.0.0")
            mock_resolve_desc.assert_called_once_with("Test")
            mock_select.assert_called_once()
            mock_build.assert_called_once()
            mock_train.assert_called_once()
            mock_copy.assert_called_once()
            mock_metadata.assert_called_once()
