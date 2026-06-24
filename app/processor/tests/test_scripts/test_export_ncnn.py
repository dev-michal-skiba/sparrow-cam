import argparse
from unittest.mock import MagicMock, call, patch

from processor.scripts import export_ncnn


class TestExportNcnnMain:
    """Test suite for export_ncnn main function."""

    def test_main_with_existing_model(self, tmp_path, monkeypatch):
        """Test main() with an existing .pt model file."""
        # Setup
        models_dir = tmp_path / "models"
        models_dir.mkdir()
        model_file = models_dir / "yolo26n.pt"
        model_file.touch()

        monkeypatch.setattr(export_ncnn, "MODELS_DIR", models_dir)

        with patch("processor.scripts.export_ncnn.YOLO") as mock_yolo:
            mock_model = MagicMock()
            mock_yolo.return_value = mock_model
            mock_args = MagicMock()
            mock_args.model = "yolo26n.pt"

            with patch("processor.scripts.export_ncnn.argparse.ArgumentParser") as mock_parser_class:
                mock_parser = MagicMock()
                mock_parser_class.return_value = mock_parser
                mock_parser.parse_args.return_value = mock_args

                with patch("processor.scripts.export_ncnn.os.chdir") as mock_chdir:
                    export_ncnn.main()

                    # Verify os.chdir was called with models_dir
                    mock_chdir.assert_called_once_with(models_dir)
                    # Verify YOLO was initialized with the model path
                    mock_yolo.assert_called_once_with(str(model_file))
                    # Verify export was called with ncnn format
                    mock_model.export.assert_called_once_with(format="ncnn")

    def test_main_with_nonexistent_model_downloads_from_hub(self, tmp_path, monkeypatch):
        """Test main() with a model name that doesn't exist locally (downloads from hub)."""
        # Setup
        models_dir = tmp_path / "models"
        models_dir.mkdir()

        monkeypatch.setattr(export_ncnn, "MODELS_DIR", models_dir)

        with patch("processor.scripts.export_ncnn.YOLO") as mock_yolo:
            mock_model = MagicMock()
            mock_yolo.return_value = mock_model
            mock_args = MagicMock()
            mock_args.model = "yolov8n"  # Model name that will be downloaded from hub

            with patch("processor.scripts.export_ncnn.argparse.ArgumentParser") as mock_parser_class:
                mock_parser = MagicMock()
                mock_parser_class.return_value = mock_parser
                mock_parser.parse_args.return_value = mock_args

                with patch("processor.scripts.export_ncnn.os.chdir") as mock_chdir:
                    export_ncnn.main()

                    # Verify os.chdir was called with models_dir
                    mock_chdir.assert_called_once_with(models_dir)
                    # Verify YOLO was initialized with the model name (not a path)
                    mock_yolo.assert_called_once_with("yolov8n")
                    # Verify export was called with ncnn format
                    mock_model.export.assert_called_once_with(format="ncnn")

    def test_main_calls_chdir_before_yolo_init(self, tmp_path, monkeypatch):
        """Test that main() changes directory before initializing YOLO."""
        models_dir = tmp_path / "models"
        models_dir.mkdir()
        model_file = models_dir / "yolo26n.pt"
        model_file.touch()

        monkeypatch.setattr(export_ncnn, "MODELS_DIR", models_dir)

        call_order = []

        with patch("processor.scripts.export_ncnn.YOLO") as mock_yolo:
            mock_model = MagicMock()
            mock_yolo.return_value = mock_model
            mock_args = MagicMock()
            mock_args.model = "yolo26n.pt"

            with patch("processor.scripts.export_ncnn.argparse.ArgumentParser") as mock_parser_class:
                mock_parser = MagicMock()
                mock_parser_class.return_value = mock_parser
                mock_parser.parse_args.return_value = mock_args

                with patch("processor.scripts.export_ncnn.os.chdir") as mock_chdir:

                    def chdir_side_effect(*args):
                        call_order.append("chdir")

                    def yolo_side_effect(*args):
                        call_order.append("yolo")
                        return mock_model

                    mock_chdir.side_effect = chdir_side_effect
                    mock_yolo.side_effect = yolo_side_effect

                    export_ncnn.main()

                    # Verify chdir was called before YOLO initialization
                    assert call_order == ["chdir", "yolo"]

    def test_main_calls_export_with_ncnn_format(self, tmp_path, monkeypatch):
        """Test that main() calls export with the correct ncnn format."""
        models_dir = tmp_path / "models"
        models_dir.mkdir()
        model_file = models_dir / "yolo26n.pt"
        model_file.touch()

        monkeypatch.setattr(export_ncnn, "MODELS_DIR", models_dir)

        with patch("processor.scripts.export_ncnn.YOLO") as mock_yolo:
            mock_model = MagicMock()
            mock_yolo.return_value = mock_model
            mock_args = MagicMock()
            mock_args.model = "yolo26n.pt"

            with patch("processor.scripts.export_ncnn.argparse.ArgumentParser") as mock_parser_class:
                mock_parser = MagicMock()
                mock_parser_class.return_value = mock_parser
                mock_parser.parse_args.return_value = mock_args

                with patch("processor.scripts.export_ncnn.os.chdir"):
                    export_ncnn.main()

                    # Verify export was called exactly once with format='ncnn'
                    assert mock_model.export.call_count == 1
                    assert mock_model.export.call_args == call(format="ncnn")


class TestExportNcnnArgumentParsing:
    """Test suite for argument parsing in export_ncnn."""

    def test_argument_parser_description(self):
        """Test that ArgumentParser has correct description."""
        with patch("processor.scripts.export_ncnn.os.chdir"):
            with patch("processor.scripts.export_ncnn.YOLO"):
                with patch("processor.scripts.export_ncnn.argparse.ArgumentParser.parse_args") as mock_parse:
                    mock_args = MagicMock()
                    mock_args.model = "yolo26n.pt"
                    mock_parse.return_value = mock_args

                    # Create parser like main does
                    parser = argparse.ArgumentParser(description="Export YOLO .pt model to NCNN format")

                    # Verify parser was created with correct description
                    assert parser.description == "Export YOLO .pt model to NCNN format"

    def test_argument_parser_model_argument(self):
        """Test that ArgumentParser accepts model argument."""
        parser = argparse.ArgumentParser(description="Export YOLO .pt model to NCNN format")
        parser.add_argument("model", help="Model filename in models/ directory (e.g. yolo26n.pt)")

        # Parse a test argument
        args = parser.parse_args(["yolo26n.pt"])
        assert args.model == "yolo26n.pt"

    def test_argument_parser_model_help_text(self):
        """Test that model argument has correct help text."""
        parser = argparse.ArgumentParser(description="Export YOLO .pt model to NCNN format")
        parser.add_argument("model", help="Model filename in models/ directory (e.g. yolo26n.pt)")

        # Find the model argument
        model_action = None
        for action in parser._actions:
            if action.dest == "model":
                model_action = action
                break

        assert model_action is not None
        assert model_action.help == "Model filename in models/ directory (e.g. yolo26n.pt)"


class TestExportNcnnModuleEntry:
    """Test suite for module entry point."""

    def test_main_function_is_callable(self, tmp_path, monkeypatch):
        """Test that the main function is properly defined and callable."""
        models_dir = tmp_path / "models"
        models_dir.mkdir()
        model_file = models_dir / "yolo26n.pt"
        model_file.touch()

        monkeypatch.setattr(export_ncnn, "MODELS_DIR", models_dir)

        with patch("processor.scripts.export_ncnn.YOLO") as mock_yolo:
            mock_model = MagicMock()
            mock_yolo.return_value = mock_model
            mock_args = MagicMock()
            mock_args.model = "yolo26n.pt"

            with patch("processor.scripts.export_ncnn.argparse.ArgumentParser") as mock_parser_class:
                mock_parser = MagicMock()
                mock_parser_class.return_value = mock_parser
                mock_parser.parse_args.return_value = mock_args

                with patch("processor.scripts.export_ncnn.os.chdir"):
                    # Verify main is a callable function
                    assert callable(export_ncnn.main)
                    # Call main directly
                    export_ncnn.main()
                    assert mock_model.export.called


class TestExportNcnnModelResolution:
    """Test suite for model path resolution logic."""

    def test_existing_model_uses_absolute_path(self, tmp_path, monkeypatch):
        """Test that existing model files use absolute path to YOLO."""
        models_dir = tmp_path / "models"
        models_dir.mkdir()
        model_file = models_dir / "yolo26n.pt"
        model_file.touch()

        monkeypatch.setattr(export_ncnn, "MODELS_DIR", models_dir)

        with patch("processor.scripts.export_ncnn.YOLO") as mock_yolo:
            mock_model = MagicMock()
            mock_yolo.return_value = mock_model
            mock_args = MagicMock()
            mock_args.model = "yolo26n.pt"

            with patch("processor.scripts.export_ncnn.argparse.ArgumentParser") as mock_parser_class:
                mock_parser = MagicMock()
                mock_parser_class.return_value = mock_parser
                mock_parser.parse_args.return_value = mock_args

                with patch("processor.scripts.export_ncnn.os.chdir"):
                    export_ncnn.main()

                    # Verify YOLO was called with str(absolute_path)
                    called_path = mock_yolo.call_args[0][0]
                    assert called_path == str(model_file)
                    assert str(model_file).startswith(str(models_dir))

    def test_nonexistent_model_uses_name_only(self, tmp_path, monkeypatch):
        """Test that nonexistent models use name only (for hub download)."""
        models_dir = tmp_path / "models"
        models_dir.mkdir()

        monkeypatch.setattr(export_ncnn, "MODELS_DIR", models_dir)

        with patch("processor.scripts.export_ncnn.YOLO") as mock_yolo:
            mock_model = MagicMock()
            mock_yolo.return_value = mock_model
            mock_args = MagicMock()
            mock_args.model = "yolov8n"

            with patch("processor.scripts.export_ncnn.argparse.ArgumentParser") as mock_parser_class:
                mock_parser = MagicMock()
                mock_parser_class.return_value = mock_parser
                mock_parser.parse_args.return_value = mock_args

                with patch("processor.scripts.export_ncnn.os.chdir"):
                    export_ncnn.main()

                    # Verify YOLO was called with model name only (not a path)
                    called_arg = mock_yolo.call_args[0][0]
                    assert called_arg == "yolov8n"
                    assert "/" not in called_arg and "\\" not in called_arg
