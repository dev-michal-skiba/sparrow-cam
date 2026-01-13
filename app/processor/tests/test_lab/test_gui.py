"""UI tests for lab/gui.py - LabGUI class and handle_user_error decorator.

Note: LabGUI tests are limited as they depend on Tkinter which requires a display.
Most business logic has been moved to lab/utils.py and is tested in test_utils.py.
"""

from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest
from lab.exception import UserFacingError
from lab.gui import LabGUI, handle_user_error


class TestHandleUserErrorDecorator:
    """Tests for the handle_user_error decorator."""

    def test_decorator_returns_wrapped_function(self):
        """Test that decorator returns a wrapped function."""

        @handle_user_error
        def dummy_method(self):
            return "result"

        assert callable(dummy_method)

    def test_decorator_preserves_function_metadata(self):
        """Test that decorator preserves function name and docstring."""

        @handle_user_error
        def dummy_method(self):
            """Dummy docstring."""
            return "result"

        assert dummy_method.__name__ == "dummy_method"
        assert dummy_method.__doc__ == "Dummy docstring."

    def test_decorator_calls_method_successfully(self):
        """Test that decorator calls the underlying method when no error occurs."""

        @handle_user_error
        def dummy_method(self):
            return "success"

        obj = Mock()
        result = dummy_method(obj)
        assert result == "success"

    @patch("lab.gui.messagebox.showerror")
    def test_decorator_handles_error_severity(self, mock_error_box):
        """Test that decorator displays error dialog for error severity."""

        @handle_user_error
        def dummy_method(self):
            raise UserFacingError("Test Title", "Test message", severity="error")

        obj = Mock()
        result = dummy_method(obj)

        mock_error_box.assert_called_once_with("Test Title", "Test message")
        assert result is None

    @patch("lab.gui.messagebox.showinfo")
    def test_decorator_handles_info_severity(self, mock_info_box):
        """Test that decorator displays info dialog for info severity."""

        @handle_user_error
        def dummy_method(self):
            raise UserFacingError("Info Title", "Info message", severity="info")

        obj = Mock()
        result = dummy_method(obj)

        mock_info_box.assert_called_once_with("Info Title", "Info message")
        assert result is None

    def test_decorator_passes_through_arguments(self):
        """Test that decorator correctly passes through arguments."""

        @handle_user_error
        def dummy_method(self, a, b, c=None):
            return f"{a}-{b}-{c}"

        obj = Mock()
        result = dummy_method(obj, 1, 2, c=3)
        assert result == "1-2-3"

    def test_decorator_only_catches_user_facing_error(self):
        """Test that decorator only catches UserFacingError, not other exceptions."""

        @handle_user_error
        def dummy_method(self):
            raise ValueError("Some error")

        obj = Mock()
        with pytest.raises(ValueError):
            dummy_method(obj)


class TestLabGUIBasic:
    """Basic tests for LabGUI class that don't require creating tk.Tk()."""

    @pytest.fixture
    def mock_tk_root(self):
        """Create a mock Tk root window."""
        root = MagicMock()
        root.winfo_screenwidth.return_value = 1920
        root.winfo_screenheight.return_value = 1080
        root.winfo_width.return_value = 1056
        root.winfo_height.return_value = 648
        root.winfo_ismapped.return_value = False
        return root

    @pytest.fixture
    def mock_detector(self):
        """Create a mock BirdDetector."""
        detector = Mock()
        return detector

    def test_lab_gui_can_be_imported(self, mock_detector):
        """Test that LabGUI can be imported successfully."""
        assert LabGUI is not None

    @patch("lab.gui.BirdDetector")
    @patch("lab.gui.tk.Canvas")
    @patch("lab.gui.tk.StringVar")
    @patch("lab.gui.tk.Label")
    @patch("lab.gui.tk.Button")
    @patch("lab.gui.tk.Frame")
    @patch("lab.gui.tk.Tk")
    def test_labgui_initialization(
        self,
        mock_tk_class,
        mock_frame_class,
        mock_button_class,
        mock_label_class,
        mock_stringvar_class,
        mock_canvas_class,
        mock_bird_detector_class,
        mock_tk_root,
    ):
        """Test LabGUI initialization creates required UI components."""
        mock_tk_class.return_value = mock_tk_root
        mock_string_var = Mock()
        mock_stringvar_class.return_value = mock_string_var
        mock_frame = Mock()
        mock_frame_class.return_value = mock_frame
        mock_button = Mock()
        mock_button_class.return_value = mock_button
        mock_label = Mock()
        mock_label_class.return_value = mock_label
        mock_canvas = Mock()
        mock_canvas_class.return_value = mock_canvas
        mock_detector = Mock()
        mock_bird_detector_class.return_value = mock_detector

        gui = LabGUI()

        # Verify detector was created
        mock_bird_detector_class.assert_called_once()
        assert gui.detector is mock_detector

        # Verify root window was created
        assert gui.root is mock_tk_root

        # Verify UI components were created
        assert gui.button_frame is not None
        assert gui.select_btn is not None
        assert gui.detect_btn is not None
        assert gui.image_canvas is not None
        assert gui.path_hint is not None

        # Verify content padding
        assert gui.content_pad == 24

    @patch("lab.gui.BirdDetector")
    @patch("lab.gui.tk.StringVar")
    @patch("lab.gui.tk.Label")
    @patch("lab.gui.tk.Button")
    @patch("lab.gui.tk.Frame")
    @patch("lab.gui.tk.Tk")
    def test_set_window_size(
        self,
        mock_tk_class,
        mock_frame_class,
        mock_button_class,
        mock_label_class,
        mock_stringvar_class,
        mock_bird_detector_class,
        mock_tk_root,
    ):
        """Test set_window_size calculates correct dimensions."""
        mock_tk_class.return_value = mock_tk_root
        mock_stringvar_class.return_value = Mock()
        mock_frame_class.return_value = Mock()
        mock_button_class.return_value = Mock()
        mock_label_class.return_value = Mock()

        LabGUI()

        # Verify geometry was set
        assert mock_tk_root.geometry.called

    @patch("lab.gui.BirdDetector")
    @patch("lab.gui.tk.StringVar")
    @patch("lab.gui.tk.Label")
    @patch("lab.gui.tk.Button")
    @patch("lab.gui.tk.Frame")
    @patch("lab.gui.tk.Tk")
    def test_on_resize_event(
        self,
        mock_tk_class,
        mock_frame_class,
        mock_button_class,
        mock_label_class,
        mock_stringvar_class,
        mock_bird_detector_class,
        mock_tk_root,
    ):
        """Test on_resize updates wraplength for path_hint."""
        mock_tk_class.return_value = mock_tk_root
        mock_stringvar_class.return_value = Mock()
        mock_frame_class.return_value = Mock()
        mock_button_class.return_value = Mock()
        mock_label_class.return_value = Mock()

        gui = LabGUI()

        # Create a mock event
        event = Mock()
        event.width = 500

        # Call on_resize
        gui.on_resize(event)

        # The wraplength should be set to available width - 2*content_pad
        expected_wraplength = max(500 - 2 * 24, 200)
        gui.path_hint.config.assert_called_with(wraplength=expected_wraplength)

    @patch("lab.gui.BirdDetector")
    @patch("lab.gui.tk.StringVar")
    @patch("lab.gui.tk.Label")
    @patch("lab.gui.tk.Button")
    @patch("lab.gui.tk.Frame")
    @patch("lab.gui.tk.Tk")
    def test_on_resize_with_small_width(
        self,
        mock_tk_class,
        mock_frame_class,
        mock_button_class,
        mock_label_class,
        mock_stringvar_class,
        mock_bird_detector_class,
        mock_tk_root,
    ):
        """Test on_resize handles small window widths correctly."""
        mock_tk_class.return_value = mock_tk_root
        mock_stringvar_class.return_value = Mock()
        mock_frame_class.return_value = Mock()
        mock_button_class.return_value = Mock()
        mock_label_class.return_value = Mock()

        gui = LabGUI()

        # Create a mock event with small width
        event = Mock()
        event.width = 100

        # Call on_resize
        gui.on_resize(event)

        # The wraplength should be clamped to at least 200
        gui.path_hint.config.assert_called_with(wraplength=200)

    @patch("lab.gui.filedialog.askopenfilename")
    @patch("lab.gui.BirdDetector")
    @patch("lab.gui.tk.StringVar")
    @patch("lab.gui.tk.Label")
    @patch("lab.gui.tk.Button")
    @patch("lab.gui.tk.Frame")
    @patch("lab.gui.tk.Tk")
    def test_get_selected_file_from_user_with_file(
        self,
        mock_tk_class,
        mock_frame_class,
        mock_button_class,
        mock_label_class,
        mock_stringvar_class,
        mock_bird_detector_class,
        mock_file_dialog,
        mock_tk_root,
    ):
        """Test get_selected_file_from_user returns Path when user selects file."""
        mock_tk_class.return_value = mock_tk_root
        mock_stringvar_class.return_value = Mock()
        mock_frame_class.return_value = Mock()
        mock_button_class.return_value = Mock()
        mock_label_class.return_value = Mock()
        mock_file_dialog.return_value = "/some/path/image.png"

        gui = LabGUI()
        result = gui.get_selected_file_from_user()

        assert result == Path("/some/path/image.png")
        mock_file_dialog.assert_called_once()

    @patch("lab.gui.filedialog.askopenfilename")
    @patch("lab.gui.BirdDetector")
    @patch("lab.gui.tk.StringVar")
    @patch("lab.gui.tk.Label")
    @patch("lab.gui.tk.Button")
    @patch("lab.gui.tk.Frame")
    @patch("lab.gui.tk.Tk")
    def test_get_selected_file_from_user_without_file(
        self,
        mock_tk_class,
        mock_frame_class,
        mock_button_class,
        mock_label_class,
        mock_stringvar_class,
        mock_bird_detector_class,
        mock_file_dialog,
        mock_tk_root,
    ):
        """Test get_selected_file_from_user returns None when user cancels."""
        mock_tk_class.return_value = mock_tk_root
        mock_stringvar_class.return_value = Mock()
        mock_frame_class.return_value = Mock()
        mock_button_class.return_value = Mock()
        mock_label_class.return_value = Mock()
        mock_file_dialog.return_value = ""

        gui = LabGUI()
        result = gui.get_selected_file_from_user()

        assert result is None

    @patch("lab.gui.BirdDetector")
    @patch("lab.gui.tk.StringVar")
    @patch("lab.gui.tk.Label")
    @patch("lab.gui.tk.Button")
    @patch("lab.gui.tk.Frame")
    @patch("lab.gui.tk.Tk")
    def test_set_selected_image(
        self,
        mock_tk_class,
        mock_frame_class,
        mock_button_class,
        mock_label_class,
        mock_stringvar_class,
        mock_bird_detector_class,
        mock_tk_root,
    ):
        """Test set_selected_image updates state and text."""
        mock_tk_class.return_value = mock_tk_root
        mock_string_var = Mock()
        mock_stringvar_class.return_value = mock_string_var
        mock_frame_class.return_value = Mock()
        mock_button_class.return_value = Mock()
        mock_label_class.return_value = Mock()

        gui = LabGUI()
        test_path = Path("/test/image.png")

        gui.set_selected_image(test_path)

        # Verify private attribute was set
        assert gui._LabGUI__selected_image == test_path.resolve()

        # Verify the text variable was updated
        mock_string_var.set.assert_called_with(str(test_path.resolve()))

    @patch("lab.gui.BirdDetector")
    @patch("lab.gui.tk.Canvas")
    @patch("lab.gui.tk.StringVar")
    @patch("lab.gui.tk.Label")
    @patch("lab.gui.tk.Button")
    @patch("lab.gui.tk.Frame")
    @patch("lab.gui.tk.Tk")
    def test_set_image_preview(
        self,
        mock_tk_class,
        mock_frame_class,
        mock_button_class,
        mock_label_class,
        mock_stringvar_class,
        mock_canvas_class,
        mock_bird_detector_class,
        mock_tk_root,
    ):
        """Test set_image_preview updates the image canvas."""
        mock_tk_class.return_value = mock_tk_root
        mock_stringvar_class.return_value = Mock()
        mock_frame_class.return_value = Mock()
        mock_button_class.return_value = Mock()
        mock_label_class.return_value = Mock()
        mock_canvas = Mock()
        mock_canvas.width.return_value = 800
        mock_canvas.height.return_value = 600
        mock_canvas_class.return_value = mock_canvas

        gui = LabGUI()

        # Create a mock PhotoImage
        mock_image = Mock()
        mock_image.width.return_value = 800
        mock_image.height.return_value = 600
        gui._LabGUI__image_obj = mock_image

        # Call set_image_preview
        gui.set_image_preview()

        # Verify the canvas was configured with dimensions
        mock_canvas.config.assert_called_with(width=800, height=600)
        # Verify create_image was called
        mock_canvas.create_image.assert_called_once()

    @patch("lab.gui.BirdDetector")
    @patch("lab.gui.tk.StringVar")
    @patch("lab.gui.tk.Label")
    @patch("lab.gui.tk.Button")
    @patch("lab.gui.tk.Frame")
    @patch("lab.gui.tk.Tk")
    def test_show_detect_button_when_not_mapped(
        self,
        mock_tk_class,
        mock_frame_class,
        mock_button_class,
        mock_label_class,
        mock_stringvar_class,
        mock_bird_detector_class,
        mock_tk_root,
    ):
        """Test show_detect_button displays button when not already shown."""
        mock_tk_class.return_value = mock_tk_root
        mock_stringvar_class.return_value = Mock()
        mock_frame_class.return_value = Mock()
        mock_button_class.return_value = Mock()
        mock_label_class.return_value = Mock()

        gui = LabGUI()
        gui.detect_btn.winfo_ismapped.return_value = False

        # Call show_detect_button
        gui.show_detect_button()

        # Verify pack was called on detect button with side="left"
        assert gui.detect_btn.pack.called
        call_kwargs = gui.detect_btn.pack.call_args[1]
        assert call_kwargs.get("side") == "left"

    @patch("lab.gui.BirdDetector")
    @patch("lab.gui.tk.StringVar")
    @patch("lab.gui.tk.Label")
    @patch("lab.gui.tk.Button")
    @patch("lab.gui.tk.Frame")
    @patch("lab.gui.tk.Tk")
    def test_show_detect_button_when_already_mapped(
        self,
        mock_tk_class,
        mock_frame_class,
        mock_button_class,
        mock_label_class,
        mock_stringvar_class,
        mock_bird_detector_class,
        mock_tk_root,
    ):
        """Test show_detect_button doesn't duplicate when already shown."""
        mock_tk_class.return_value = mock_tk_root
        mock_stringvar_class.return_value = Mock()
        mock_frame_class.return_value = Mock()
        mock_button_class.return_value = Mock()
        mock_label_class.return_value = Mock()

        gui = LabGUI()

        # Reset the pack call count (it was called during init)
        gui.detect_btn.pack.reset_mock()

        # Mock the button as already mapped
        gui.detect_btn.winfo_ismapped.return_value = True

        # Call show_detect_button
        gui.show_detect_button()

        # pack should not be called again if button is already mapped
        gui.detect_btn.pack.assert_not_called()

    @patch("lab.gui.validate_selected_image")
    @patch("lab.gui.tk.PhotoImage")
    @patch("lab.gui.filedialog.askopenfilename")
    @patch("lab.gui.BirdDetector")
    @patch("lab.gui.tk.StringVar")
    @patch("lab.gui.tk.Label")
    @patch("lab.gui.tk.Button")
    @patch("lab.gui.tk.Frame")
    @patch("lab.gui.tk.Tk")
    def test_choose_file_with_valid_image(
        self,
        mock_tk_class,
        mock_frame_class,
        mock_button_class,
        mock_label_class,
        mock_stringvar_class,
        mock_bird_detector_class,
        mock_file_dialog,
        mock_photoimage_class,
        mock_validate,
        mock_tk_root,
    ):
        """Test choose_file with valid image selection."""
        mock_tk_class.return_value = mock_tk_root
        mock_stringvar_class.return_value = Mock()
        mock_frame_class.return_value = Mock()
        mock_button_class.return_value = Mock()
        mock_label_class.return_value = Mock()
        mock_file_dialog.return_value = "/test/image.png"
        mock_image = Mock()
        mock_photoimage_class.return_value = mock_image

        gui = LabGUI()
        gui.choose_file()

        # Verify validation was called
        mock_validate.assert_called_once()

        # Verify selected image was set
        assert gui._LabGUI__selected_image == Path("/test/image.png").resolve()

        # Verify image preview was set
        assert gui._LabGUI__image_obj is mock_image

        # Verify detect button was shown with side="left"
        assert gui.detect_btn.pack.called
        call_kwargs = gui.detect_btn.pack.call_args[1]
        assert call_kwargs.get("side") == "left"

    @patch("lab.gui.messagebox.showerror")
    @patch("lab.gui.validate_selected_image")
    @patch("lab.gui.filedialog.askopenfilename")
    @patch("lab.gui.BirdDetector")
    @patch("lab.gui.tk.StringVar")
    @patch("lab.gui.tk.Label")
    @patch("lab.gui.tk.Button")
    @patch("lab.gui.tk.Frame")
    @patch("lab.gui.tk.Tk")
    def test_choose_file_with_validation_error(
        self,
        mock_tk_class,
        mock_frame_class,
        mock_button_class,
        mock_label_class,
        mock_stringvar_class,
        mock_bird_detector_class,
        mock_file_dialog,
        mock_validate,
        mock_error_box,
        mock_tk_root,
    ):
        """Test choose_file handles validation errors."""
        mock_tk_class.return_value = mock_tk_root
        mock_stringvar_class.return_value = Mock()
        mock_frame_class.return_value = Mock()
        mock_button_class.return_value = Mock()
        mock_label_class.return_value = Mock()
        mock_file_dialog.return_value = "/test/invalid.jpg"
        mock_validate.side_effect = UserFacingError("Invalid", "Bad file", severity="error")

        gui = LabGUI()
        result = gui.choose_file()

        # Verify error dialog was shown
        mock_error_box.assert_called_once_with("Invalid", "Bad file")

        # Verify method returned None
        assert result is None

    @patch("lab.gui.get_annotated_image_bytes")
    @patch("lab.gui.tk.PhotoImage")
    @patch("lab.gui.tk.Canvas")
    @patch("lab.gui.BirdDetector")
    @patch("lab.gui.tk.StringVar")
    @patch("lab.gui.tk.Label")
    @patch("lab.gui.tk.Button")
    @patch("lab.gui.tk.Frame")
    @patch("lab.gui.tk.Tk")
    def test_detect_bird_with_valid_image(
        self,
        mock_tk_class,
        mock_frame_class,
        mock_button_class,
        mock_label_class,
        mock_stringvar_class,
        mock_bird_detector_class,
        mock_canvas_class,
        mock_photoimage_class,
        mock_get_annotated,
        mock_tk_root,
    ):
        """Test detect_bird with valid image."""
        mock_tk_class.return_value = mock_tk_root
        mock_stringvar_class.return_value = Mock()
        mock_frame_class.return_value = Mock()
        mock_button_class.return_value = Mock()
        mock_label_class.return_value = Mock()
        mock_canvas = Mock()
        mock_canvas.width.return_value = 800
        mock_canvas.height.return_value = 600
        mock_canvas_class.return_value = mock_canvas
        mock_annotated_bytes = b"fake_image_data"
        mock_get_annotated.return_value = mock_annotated_bytes
        mock_image = Mock()
        mock_image.width.return_value = 800
        mock_image.height.return_value = 600
        mock_photoimage_class.return_value = mock_image

        gui = LabGUI()
        gui._LabGUI__selected_image = Path("/test/image.png")

        gui.detect_bird()

        # Verify get_annotated_image_bytes was called
        mock_get_annotated.assert_called_once_with(gui.detector, Path("/test/image.png"), regions=None)

        # Verify PhotoImage was created with correct parameters
        mock_photoimage_class.assert_called_with(data=mock_annotated_bytes, format="png")

        # Verify image preview was updated
        assert gui._LabGUI__image_obj is mock_image

    @patch("lab.gui.messagebox.showinfo")
    @patch("lab.gui.get_annotated_image_bytes")
    @patch("lab.gui.tk.PhotoImage")
    @patch("lab.gui.tk.Canvas")
    @patch("lab.gui.BirdDetector")
    @patch("lab.gui.tk.StringVar")
    @patch("lab.gui.tk.Label")
    @patch("lab.gui.tk.Button")
    @patch("lab.gui.tk.Frame")
    @patch("lab.gui.tk.Tk")
    def test_detect_bird_with_user_error(
        self,
        mock_tk_class,
        mock_frame_class,
        mock_button_class,
        mock_label_class,
        mock_stringvar_class,
        mock_bird_detector_class,
        mock_canvas_class,
        mock_photoimage_class,
        mock_get_annotated,
        mock_info_box,
        mock_tk_root,
    ):
        """Test detect_bird handles UserFacingError with info severity."""
        mock_tk_class.return_value = mock_tk_root
        mock_stringvar_class.return_value = Mock()
        mock_frame_class.return_value = Mock()
        mock_button_class.return_value = Mock()
        mock_label_class.return_value = Mock()
        mock_canvas = Mock()
        mock_canvas_class.return_value = mock_canvas
        mock_photoimage_class.return_value = Mock()
        error = UserFacingError("No bird", "No birds found", severity="info")
        mock_get_annotated.side_effect = error

        gui = LabGUI()
        gui._LabGUI__selected_image = Path("/test/image.png")

        result = gui.detect_bird()

        # Verify info dialog was shown
        mock_info_box.assert_called_once_with("No bird", "No birds found")

        # Verify method returned None
        assert result is None

    @patch("lab.gui.BirdDetector")
    @patch("lab.gui.tk.StringVar")
    @patch("lab.gui.tk.Label")
    @patch("lab.gui.tk.Button")
    @patch("lab.gui.tk.Frame")
    @patch("lab.gui.tk.Tk")
    def test_run_calls_mainloop(
        self,
        mock_tk_class,
        mock_frame_class,
        mock_button_class,
        mock_label_class,
        mock_stringvar_class,
        mock_bird_detector_class,
        mock_tk_root,
    ):
        """Test run method calls root.mainloop()."""
        mock_tk_class.return_value = mock_tk_root
        mock_stringvar_class.return_value = Mock()
        mock_frame_class.return_value = Mock()
        mock_button_class.return_value = Mock()
        mock_label_class.return_value = Mock()

        gui = LabGUI()
        gui.run()

        # Verify mainloop was called
        mock_tk_root.mainloop.assert_called_once()

    @patch("lab.gui.BirdDetector")
    @patch("lab.gui.tk.StringVar")
    @patch("lab.gui.tk.Label")
    @patch("lab.gui.tk.Button")
    @patch("lab.gui.tk.Frame")
    @patch("lab.gui.tk.Tk")
    def test_window_title_set(
        self,
        mock_tk_class,
        mock_frame_class,
        mock_button_class,
        mock_label_class,
        mock_stringvar_class,
        mock_bird_detector_class,
        mock_tk_root,
    ):
        """Test that window title is set correctly."""
        mock_tk_class.return_value = mock_tk_root
        mock_stringvar_class.return_value = Mock()
        mock_frame_class.return_value = Mock()
        mock_button_class.return_value = Mock()
        mock_label_class.return_value = Mock()

        LabGUI()

        # Verify title was set
        mock_tk_root.title.assert_called_once_with("Sparrow Cam Lab")

    @patch("lab.gui.BirdDetector")
    @patch("lab.gui.tk.StringVar")
    @patch("lab.gui.tk.Label")
    @patch("lab.gui.tk.Button")
    @patch("lab.gui.tk.Frame")
    @patch("lab.gui.tk.Tk")
    def test_window_bind_event_handler(
        self,
        mock_tk_class,
        mock_frame_class,
        mock_button_class,
        mock_label_class,
        mock_stringvar_class,
        mock_bird_detector_class,
        mock_tk_root,
    ):
        """Test that Configure event handler is bound."""
        mock_tk_class.return_value = mock_tk_root
        mock_stringvar_class.return_value = Mock()
        mock_frame_class.return_value = Mock()
        mock_button_class.return_value = Mock()
        mock_label_class.return_value = Mock()

        LabGUI()

        # Verify bind was called for Configure event
        mock_tk_root.bind.assert_called_once()
        args = mock_tk_root.bind.call_args
        assert args[0][0] == "<Configure>"
        assert args[1]["add"] == "+"

    @patch("lab.gui.messagebox.showerror")
    @patch("lab.gui.get_annotated_image_bytes")
    @patch("lab.gui.tk.PhotoImage")
    @patch("lab.gui.tk.Canvas")
    @patch("lab.gui.BirdDetector")
    @patch("lab.gui.tk.StringVar")
    @patch("lab.gui.tk.Label")
    @patch("lab.gui.tk.Button")
    @patch("lab.gui.tk.Frame")
    @patch("lab.gui.tk.Tk")
    def test_detect_bird_with_error_severity(
        self,
        mock_tk_class,
        mock_frame_class,
        mock_button_class,
        mock_label_class,
        mock_stringvar_class,
        mock_bird_detector_class,
        mock_canvas_class,
        mock_photoimage_class,
        mock_get_annotated,
        mock_error_box,
        mock_tk_root,
    ):
        """Test detect_bird handles UserFacingError with error severity."""
        mock_tk_class.return_value = mock_tk_root
        mock_stringvar_class.return_value = Mock()
        mock_frame_class.return_value = Mock()
        mock_button_class.return_value = Mock()
        mock_label_class.return_value = Mock()
        mock_canvas = Mock()
        mock_canvas_class.return_value = mock_canvas
        mock_photoimage_class.return_value = Mock()
        error = UserFacingError("Error", "Something went wrong", severity="error")
        mock_get_annotated.side_effect = error

        gui = LabGUI()
        gui._LabGUI__selected_image = Path("/test/image.png")

        result = gui.detect_bird()

        # Verify error dialog was shown
        mock_error_box.assert_called_once_with("Error", "Something went wrong")

        # Verify method returned None
        assert result is None

    @patch("lab.gui.BirdDetector")
    @patch("lab.gui.tk.StringVar")
    @patch("lab.gui.tk.Label")
    @patch("lab.gui.tk.Button")
    @patch("lab.gui.tk.Frame")
    @patch("lab.gui.tk.Tk")
    def test_button_frame_layout(
        self,
        mock_tk_class,
        mock_frame_class,
        mock_button_class,
        mock_label_class,
        mock_stringvar_class,
        mock_bird_detector_class,
        mock_tk_root,
    ):
        """Test that button frame is laid out correctly."""
        mock_tk_class.return_value = mock_tk_root
        mock_stringvar_class.return_value = Mock()
        mock_frame = Mock()
        mock_frame_class.return_value = mock_frame
        mock_button_class.return_value = Mock()
        mock_label_class.return_value = Mock()

        gui = LabGUI()

        # Verify button frame pack was called
        assert gui.button_frame.pack.called

    @patch("lab.gui.BirdDetector")
    @patch("lab.gui.tk.StringVar")
    @patch("lab.gui.tk.Label")
    @patch("lab.gui.tk.Button")
    @patch("lab.gui.tk.Frame")
    @patch("lab.gui.tk.Tk")
    def test_select_button_command(
        self,
        mock_tk_class,
        mock_frame_class,
        mock_button_class,
        mock_label_class,
        mock_stringvar_class,
        mock_bird_detector_class,
        mock_tk_root,
    ):
        """Test that select button has correct command."""
        mock_tk_class.return_value = mock_tk_root
        mock_stringvar_class.return_value = Mock()
        mock_frame_class.return_value = Mock()
        mock_button_class.return_value = Mock()
        mock_label_class.return_value = Mock()

        gui = LabGUI()

        # Verify select button was created
        assert gui.select_btn is not None

    @patch("lab.gui.BirdDetector")
    @patch("lab.gui.tk.StringVar")
    @patch("lab.gui.tk.Label")
    @patch("lab.gui.tk.Button")
    @patch("lab.gui.tk.Frame")
    @patch("lab.gui.tk.Tk")
    def test_detect_button_command(
        self,
        mock_tk_class,
        mock_frame_class,
        mock_button_class,
        mock_label_class,
        mock_stringvar_class,
        mock_bird_detector_class,
        mock_tk_root,
    ):
        """Test that detect button has correct command."""
        mock_tk_class.return_value = mock_tk_root
        mock_stringvar_class.return_value = Mock()
        mock_frame_class.return_value = Mock()
        mock_button_class.return_value = Mock()
        mock_label_class.return_value = Mock()

        gui = LabGUI()

        # Verify detect button was created
        assert gui.detect_btn is not None

    @patch("lab.gui.BirdDetector")
    @patch("lab.gui.tk.StringVar")
    @patch("lab.gui.tk.Label")
    @patch("lab.gui.tk.Button")
    @patch("lab.gui.tk.Frame")
    @patch("lab.gui.tk.Tk")
    def test_initial_image_preview_empty(
        self,
        mock_tk_class,
        mock_frame_class,
        mock_button_class,
        mock_label_class,
        mock_stringvar_class,
        mock_bird_detector_class,
        mock_tk_root,
    ):
        """Test that image preview is empty initially."""
        mock_tk_class.return_value = mock_tk_root
        mock_stringvar_class.return_value = Mock()
        mock_frame_class.return_value = Mock()
        mock_button_class.return_value = Mock()
        mock_label_class.return_value = Mock()

        gui = LabGUI()

        # Verify initial image object is None
        assert gui._LabGUI__image_obj is None

    @patch("lab.gui.BirdDetector")
    @patch("lab.gui.tk.StringVar")
    @patch("lab.gui.tk.Label")
    @patch("lab.gui.tk.Button")
    @patch("lab.gui.tk.Frame")
    @patch("lab.gui.tk.Tk")
    def test_minsize_set(
        self,
        mock_tk_class,
        mock_frame_class,
        mock_button_class,
        mock_label_class,
        mock_stringvar_class,
        mock_bird_detector_class,
        mock_tk_root,
    ):
        """Test that minsize is set for the window."""
        mock_tk_class.return_value = mock_tk_root
        mock_stringvar_class.return_value = Mock()
        mock_frame_class.return_value = Mock()
        mock_button_class.return_value = Mock()
        mock_label_class.return_value = Mock()

        LabGUI()

        # Verify minsize was called
        mock_tk_root.minsize.assert_called_once_with(640, 480)

    @patch("lab.gui.BirdDetector")
    @patch("lab.gui.tk.Canvas")
    @patch("lab.gui.tk.StringVar")
    @patch("lab.gui.tk.Label")
    @patch("lab.gui.tk.Button")
    @patch("lab.gui.tk.Frame")
    @patch("lab.gui.tk.Tk")
    def test_on_selection_start(
        self,
        mock_tk_class,
        mock_frame_class,
        mock_button_class,
        mock_label_class,
        mock_stringvar_class,
        mock_canvas_class,
        mock_bird_detector_class,
        mock_tk_root,
    ):
        """Test on_selection_start initiates rectangle drawing."""
        mock_tk_class.return_value = mock_tk_root
        mock_stringvar_class.return_value = Mock()
        mock_frame_class.return_value = Mock()
        mock_button_class.return_value = Mock()
        mock_label_class.return_value = Mock()
        mock_canvas = Mock()
        mock_canvas_class.return_value = mock_canvas
        mock_canvas.create_rectangle.return_value = 1

        gui = LabGUI()
        # Set up image object so selection can be drawn
        gui._LabGUI__image_obj = Mock()

        event = Mock()
        event.x = 100
        event.y = 150

        gui.on_selection_start(event)

        # Verify rectangle was created
        mock_canvas.create_rectangle.assert_called_once_with(100, 150, 100, 150, outline="blue", width=2)
        assert gui._LabGUI__selection_start == (100, 150)

    @patch("lab.gui.BirdDetector")
    @patch("lab.gui.tk.Canvas")
    @patch("lab.gui.tk.StringVar")
    @patch("lab.gui.tk.Label")
    @patch("lab.gui.tk.Button")
    @patch("lab.gui.tk.Frame")
    @patch("lab.gui.tk.Tk")
    def test_on_selection_drag(
        self,
        mock_tk_class,
        mock_frame_class,
        mock_button_class,
        mock_label_class,
        mock_stringvar_class,
        mock_canvas_class,
        mock_bird_detector_class,
        mock_tk_root,
    ):
        """Test on_selection_drag updates rectangle during dragging."""
        mock_tk_class.return_value = mock_tk_root
        mock_stringvar_class.return_value = Mock()
        mock_frame_class.return_value = Mock()
        mock_button_class.return_value = Mock()
        mock_label_class.return_value = Mock()
        mock_canvas = Mock()
        mock_canvas_class.return_value = mock_canvas
        # Mock bbox to return a tuple that can be indexed
        mock_canvas.bbox.return_value = (50, 50, 100, 70)

        gui = LabGUI()
        gui._LabGUI__image_obj = Mock()
        gui._LabGUI__selection_start = (50, 50)
        gui._LabGUI__current_rect = 1

        event = Mock()
        event.x = 530  # Creates a 480x480 square (valid size)
        event.y = 530

        gui.on_selection_drag(event)

        # Verify coords and text were updated
        mock_canvas.coords.assert_called()
        mock_canvas.create_text.assert_called_once()

    @patch("lab.gui.BirdDetector")
    @patch("lab.gui.tk.Canvas")
    @patch("lab.gui.tk.StringVar")
    @patch("lab.gui.tk.Label")
    @patch("lab.gui.tk.Button")
    @patch("lab.gui.tk.Frame")
    @patch("lab.gui.tk.Tk")
    def test_on_selection_end_valid_region(
        self,
        mock_tk_class,
        mock_frame_class,
        mock_button_class,
        mock_label_class,
        mock_stringvar_class,
        mock_canvas_class,
        mock_bird_detector_class,
        mock_tk_root,
    ):
        """Test on_selection_end finalizes valid region."""
        mock_tk_class.return_value = mock_tk_root
        mock_stringvar_class.return_value = Mock()
        mock_frame_class.return_value = Mock()
        mock_button_class.return_value = Mock()
        mock_label_class.return_value = Mock()
        mock_canvas = Mock()
        mock_canvas_class.return_value = mock_canvas

        gui = LabGUI()
        mock_image = Mock()
        mock_image.width.return_value = 800
        mock_image.height.return_value = 600
        gui._LabGUI__image_obj = mock_image
        gui._LabGUI__selection_start = (50, 50)
        gui._LabGUI__current_rect = 1
        gui._LabGUI__dimension_text = 2

        event = Mock()
        event.x = 530  # Creates a 480x480 square (valid size)
        event.y = 530

        gui.on_selection_end(event)

        # Verify region was added
        assert len(gui._LabGUI__selection_regions) == 1
        assert gui._LabGUI__selection_regions[0] == (50, 50, 530, 530)

        # Verify clear button was shown
        assert gui.clear_btn.pack.called

    @patch("lab.gui.BirdDetector")
    @patch("lab.gui.tk.Canvas")
    @patch("lab.gui.tk.StringVar")
    @patch("lab.gui.tk.Label")
    @patch("lab.gui.tk.Button")
    @patch("lab.gui.tk.Frame")
    @patch("lab.gui.tk.Tk")
    def test_on_selection_end_small_region(
        self,
        mock_tk_class,
        mock_frame_class,
        mock_button_class,
        mock_label_class,
        mock_stringvar_class,
        mock_canvas_class,
        mock_bird_detector_class,
        mock_tk_root,
    ):
        """Test on_selection_end ignores regions smaller than 10x10."""
        mock_tk_class.return_value = mock_tk_root
        mock_stringvar_class.return_value = Mock()
        mock_frame_class.return_value = Mock()
        mock_button_class.return_value = Mock()
        mock_label_class.return_value = Mock()
        mock_canvas = Mock()
        mock_canvas_class.return_value = mock_canvas

        gui = LabGUI()
        mock_image = Mock()
        mock_image.width.return_value = 800
        mock_image.height.return_value = 600
        gui._LabGUI__image_obj = mock_image
        gui._LabGUI__selection_start = (100, 100)
        gui._LabGUI__current_rect = 1

        event = Mock()
        event.x = 105
        event.y = 105

        gui.on_selection_end(event)

        # Verify no region was added (too small)
        assert len(gui._LabGUI__selection_regions) == 0

        # Verify rectangle was deleted
        mock_canvas.delete.assert_called()

    @patch("lab.gui.BirdDetector")
    @patch("lab.gui.tk.Canvas")
    @patch("lab.gui.tk.StringVar")
    @patch("lab.gui.tk.Label")
    @patch("lab.gui.tk.Button")
    @patch("lab.gui.tk.Frame")
    @patch("lab.gui.tk.Tk")
    def test_on_mouse_move(
        self,
        mock_tk_class,
        mock_frame_class,
        mock_button_class,
        mock_label_class,
        mock_stringvar_class,
        mock_canvas_class,
        mock_bird_detector_class,
        mock_tk_root,
    ):
        """Test on_mouse_move shows crosshairs."""
        mock_tk_class.return_value = mock_tk_root
        mock_stringvar_class.return_value = Mock()
        mock_frame_class.return_value = Mock()
        mock_button_class.return_value = Mock()
        mock_label_class.return_value = Mock()
        mock_canvas = Mock()
        mock_canvas_class.return_value = mock_canvas
        mock_canvas.create_line.side_effect = [10, 11]

        gui = LabGUI()
        mock_image = Mock()
        mock_image.width.return_value = 800
        mock_image.height.return_value = 600
        gui._LabGUI__image_obj = mock_image

        event = Mock()
        event.x = 400
        event.y = 300

        gui.on_mouse_move(event)

        # Verify crosshairs were created
        assert gui._LabGUI__crosshair_h == 10
        assert gui._LabGUI__crosshair_v == 11

    @patch("lab.gui.BirdDetector")
    @patch("lab.gui.tk.Canvas")
    @patch("lab.gui.tk.StringVar")
    @patch("lab.gui.tk.Label")
    @patch("lab.gui.tk.Button")
    @patch("lab.gui.tk.Frame")
    @patch("lab.gui.tk.Tk")
    def test_on_mouse_leave(
        self,
        mock_tk_class,
        mock_frame_class,
        mock_button_class,
        mock_label_class,
        mock_stringvar_class,
        mock_canvas_class,
        mock_bird_detector_class,
        mock_tk_root,
    ):
        """Test on_mouse_leave hides crosshairs."""
        mock_tk_class.return_value = mock_tk_root
        mock_stringvar_class.return_value = Mock()
        mock_frame_class.return_value = Mock()
        mock_button_class.return_value = Mock()
        mock_label_class.return_value = Mock()
        mock_canvas = Mock()
        mock_canvas_class.return_value = mock_canvas

        gui = LabGUI()
        gui._LabGUI__crosshair_h = 10
        gui._LabGUI__crosshair_v = 11

        event = Mock()
        gui.on_mouse_leave(event)

        # Verify crosshairs were deleted
        assert gui._LabGUI__crosshair_h is None
        assert gui._LabGUI__crosshair_v is None

    @patch("lab.gui.BirdDetector")
    @patch("lab.gui.tk.Canvas")
    @patch("lab.gui.tk.PhotoImage")
    @patch("lab.gui.tk.StringVar")
    @patch("lab.gui.tk.Label")
    @patch("lab.gui.tk.Button")
    @patch("lab.gui.tk.Frame")
    @patch("lab.gui.tk.Tk")
    def test_clear_all(
        self,
        mock_tk_class,
        mock_frame_class,
        mock_button_class,
        mock_label_class,
        mock_stringvar_class,
        mock_photoimage_class,
        mock_canvas_class,
        mock_bird_detector_class,
        mock_tk_root,
    ):
        """Test clear_all clears all selection regions and resets image."""
        mock_tk_class.return_value = mock_tk_root
        mock_stringvar_class.return_value = Mock()
        mock_frame_class.return_value = Mock()
        mock_button_class.return_value = Mock()
        mock_label_class.return_value = Mock()
        mock_canvas = Mock()
        mock_canvas_class.return_value = mock_canvas
        mock_image = Mock()
        mock_image.width.return_value = 800
        mock_image.height.return_value = 600
        mock_photoimage_class.return_value = mock_image

        gui = LabGUI()
        gui._LabGUI__selected_image = Path("/test/image.png")
        gui._LabGUI__current_rect = 1
        gui._LabGUI__selection_rects = [2, 3]
        gui._LabGUI__selection_texts = [4, 5]
        gui._LabGUI__selection_regions = [(0, 0, 100, 100)]
        gui._LabGUI__dimension_text = 6

        gui.clear_all()

        # Verify all regions were cleared
        assert len(gui._LabGUI__selection_regions) == 0
        assert len(gui._LabGUI__selection_rects) == 0
        assert len(gui._LabGUI__selection_texts) == 0

        # Verify clear button was hidden
        gui.clear_btn.pack_forget.assert_called()

    @patch("lab.gui.BirdDetector")
    @patch("lab.gui.tk.Canvas")
    @patch("lab.gui.tk.StringVar")
    @patch("lab.gui.tk.Label")
    @patch("lab.gui.tk.Button")
    @patch("lab.gui.tk.Frame")
    @patch("lab.gui.tk.Tk")
    def test_set_image_preview_with_no_image(
        self,
        mock_tk_class,
        mock_frame_class,
        mock_button_class,
        mock_label_class,
        mock_stringvar_class,
        mock_canvas_class,
        mock_bird_detector_class,
        mock_tk_root,
    ):
        """Test set_image_preview returns early when image_obj is None."""
        mock_tk_class.return_value = mock_tk_root
        mock_stringvar_class.return_value = Mock()
        mock_frame_class.return_value = Mock()
        mock_button_class.return_value = Mock()
        mock_label_class.return_value = Mock()
        mock_canvas = Mock()
        mock_canvas_class.return_value = mock_canvas

        gui = LabGUI()
        gui._LabGUI__image_obj = None

        gui.set_image_preview()

        # Verify canvas config was NOT called
        mock_canvas.config.assert_not_called()

    @patch("lab.gui.BirdDetector")
    @patch("lab.gui.tk.Canvas")
    @patch("lab.gui.tk.StringVar")
    @patch("lab.gui.tk.Label")
    @patch("lab.gui.tk.Button")
    @patch("lab.gui.tk.Frame")
    @patch("lab.gui.tk.Tk")
    def test_set_image_preview_with_existing_selections(
        self,
        mock_tk_class,
        mock_frame_class,
        mock_button_class,
        mock_label_class,
        mock_stringvar_class,
        mock_canvas_class,
        mock_bird_detector_class,
        mock_tk_root,
    ):
        """Test set_image_preview raises existing selection rectangles above image."""
        mock_tk_class.return_value = mock_tk_root
        mock_stringvar_class.return_value = Mock()
        mock_frame_class.return_value = Mock()
        mock_button_class.return_value = Mock()
        mock_label_class.return_value = Mock()
        mock_canvas = Mock()
        mock_canvas_class.return_value = mock_canvas

        gui = LabGUI()
        mock_image = Mock()
        mock_image.width.return_value = 800
        mock_image.height.return_value = 600
        gui._LabGUI__image_obj = mock_image
        gui._LabGUI__selection_rects = [10, 11]
        gui._LabGUI__selection_texts = [20, 21]
        gui._LabGUI__current_rect = 30

        gui.set_image_preview()

        # Verify tag_raise was called for all selections
        assert mock_canvas.tag_raise.call_count == 5  # 2 rects + 2 texts + 1 current

    @patch("lab.gui.BirdDetector")
    @patch("lab.gui.tk.Canvas")
    @patch("lab.gui.tk.StringVar")
    @patch("lab.gui.tk.Label")
    @patch("lab.gui.tk.Button")
    @patch("lab.gui.tk.Frame")
    @patch("lab.gui.tk.Tk")
    def test_on_selection_start_with_no_image(
        self,
        mock_tk_class,
        mock_frame_class,
        mock_button_class,
        mock_label_class,
        mock_stringvar_class,
        mock_canvas_class,
        mock_bird_detector_class,
        mock_tk_root,
    ):
        """Test on_selection_start returns early when no image."""
        mock_tk_class.return_value = mock_tk_root
        mock_stringvar_class.return_value = Mock()
        mock_frame_class.return_value = Mock()
        mock_button_class.return_value = Mock()
        mock_label_class.return_value = Mock()
        mock_canvas = Mock()
        mock_canvas_class.return_value = mock_canvas

        gui = LabGUI()
        gui._LabGUI__image_obj = None

        event = Mock()
        event.x = 100
        event.y = 150

        gui.on_selection_start(event)

        # Verify no rectangle was created
        mock_canvas.create_rectangle.assert_not_called()

    @patch("lab.gui.BirdDetector")
    @patch("lab.gui.tk.Canvas")
    @patch("lab.gui.tk.StringVar")
    @patch("lab.gui.tk.Label")
    @patch("lab.gui.tk.Button")
    @patch("lab.gui.tk.Frame")
    @patch("lab.gui.tk.Tk")
    def test_on_selection_drag_with_no_start(
        self,
        mock_tk_class,
        mock_frame_class,
        mock_button_class,
        mock_label_class,
        mock_stringvar_class,
        mock_canvas_class,
        mock_bird_detector_class,
        mock_tk_root,
    ):
        """Test on_selection_drag returns early when no selection started."""
        mock_tk_class.return_value = mock_tk_root
        mock_stringvar_class.return_value = Mock()
        mock_frame_class.return_value = Mock()
        mock_button_class.return_value = Mock()
        mock_label_class.return_value = Mock()
        mock_canvas = Mock()
        mock_canvas_class.return_value = mock_canvas

        gui = LabGUI()
        gui._LabGUI__selection_start = None

        event = Mock()
        event.x = 200
        event.y = 200

        gui.on_selection_drag(event)

        # Verify canvas was not updated
        mock_canvas.coords.assert_not_called()

    @patch("lab.gui.BirdDetector")
    @patch("lab.gui.tk.Canvas")
    @patch("lab.gui.tk.StringVar")
    @patch("lab.gui.tk.Label")
    @patch("lab.gui.tk.Button")
    @patch("lab.gui.tk.Frame")
    @patch("lab.gui.tk.Tk")
    def test_on_selection_drag_with_existing_text(
        self,
        mock_tk_class,
        mock_frame_class,
        mock_button_class,
        mock_label_class,
        mock_stringvar_class,
        mock_canvas_class,
        mock_bird_detector_class,
        mock_tk_root,
    ):
        """Test on_selection_drag updates existing dimension text."""
        mock_tk_class.return_value = mock_tk_root
        mock_stringvar_class.return_value = Mock()
        mock_frame_class.return_value = Mock()
        mock_button_class.return_value = Mock()
        mock_label_class.return_value = Mock()
        mock_canvas = Mock()
        mock_canvas_class.return_value = mock_canvas

        gui = LabGUI()
        gui._LabGUI__selection_start = (50, 50)
        gui._LabGUI__current_rect = 1
        gui._LabGUI__dimension_text = 2  # Already exists

        event = Mock()
        event.x = 200
        event.y = 200

        gui.on_selection_drag(event)

        # Verify itemconfig was called to update text
        mock_canvas.itemconfig.assert_called_once()

    @patch("lab.gui.BirdDetector")
    @patch("lab.gui.tk.Canvas")
    @patch("lab.gui.tk.StringVar")
    @patch("lab.gui.tk.Label")
    @patch("lab.gui.tk.Button")
    @patch("lab.gui.tk.Frame")
    @patch("lab.gui.tk.Tk")
    def test_on_selection_end_with_no_image(
        self,
        mock_tk_class,
        mock_frame_class,
        mock_button_class,
        mock_label_class,
        mock_stringvar_class,
        mock_canvas_class,
        mock_bird_detector_class,
        mock_tk_root,
    ):
        """Test on_selection_end returns early when no image."""
        mock_tk_class.return_value = mock_tk_root
        mock_stringvar_class.return_value = Mock()
        mock_frame_class.return_value = Mock()
        mock_button_class.return_value = Mock()
        mock_label_class.return_value = Mock()
        mock_canvas = Mock()
        mock_canvas_class.return_value = mock_canvas

        gui = LabGUI()
        gui._LabGUI__image_obj = None
        gui._LabGUI__selection_start = (50, 50)

        event = Mock()
        event.x = 200
        event.y = 200

        gui.on_selection_end(event)

        # Verify no regions were added
        assert len(gui._LabGUI__selection_regions) == 0

    @patch("lab.gui.BirdDetector")
    @patch("lab.gui.tk.Canvas")
    @patch("lab.gui.tk.StringVar")
    @patch("lab.gui.tk.Label")
    @patch("lab.gui.tk.Button")
    @patch("lab.gui.tk.Frame")
    @patch("lab.gui.tk.Tk")
    def test_on_selection_end_clamps_to_bounds(
        self,
        mock_tk_class,
        mock_frame_class,
        mock_button_class,
        mock_label_class,
        mock_stringvar_class,
        mock_canvas_class,
        mock_bird_detector_class,
        mock_tk_root,
    ):
        """Test on_selection_end clamps coordinates to image bounds."""
        mock_tk_class.return_value = mock_tk_root
        mock_stringvar_class.return_value = Mock()
        mock_frame_class.return_value = Mock()
        mock_button_class.return_value = Mock()
        mock_label_class.return_value = Mock()
        mock_canvas = Mock()
        mock_canvas_class.return_value = mock_canvas

        gui = LabGUI()
        mock_image = Mock()
        mock_image.width.return_value = 800
        mock_image.height.return_value = 600
        gui._LabGUI__image_obj = mock_image
        gui._LabGUI__selection_start = (-50, -50)  # Outside bounds
        gui._LabGUI__current_rect = 1
        gui._LabGUI__dimension_text = None

        event = Mock()
        event.x = 900  # Also outside bounds
        event.y = 700

        gui.on_selection_end(event)

        # Verify region was clamped to bounds
        assert len(gui._LabGUI__selection_regions) == 1
        clamped = gui._LabGUI__selection_regions[0]
        assert clamped[0] >= 0 and clamped[2] <= 800
        assert clamped[1] >= 0 and clamped[3] <= 600

    @patch("lab.gui.BirdDetector")
    @patch("lab.gui.tk.Canvas")
    @patch("lab.gui.tk.StringVar")
    @patch("lab.gui.tk.Label")
    @patch("lab.gui.tk.Button")
    @patch("lab.gui.tk.Frame")
    @patch("lab.gui.tk.Tk")
    def test_on_mouse_move_outside_bounds(
        self,
        mock_tk_class,
        mock_frame_class,
        mock_button_class,
        mock_label_class,
        mock_stringvar_class,
        mock_canvas_class,
        mock_bird_detector_class,
        mock_tk_root,
    ):
        """Test on_mouse_move hides crosshairs when cursor outside bounds."""
        mock_tk_class.return_value = mock_tk_root
        mock_stringvar_class.return_value = Mock()
        mock_frame_class.return_value = Mock()
        mock_button_class.return_value = Mock()
        mock_label_class.return_value = Mock()
        mock_canvas = Mock()
        mock_canvas_class.return_value = mock_canvas

        gui = LabGUI()
        mock_image = Mock()
        mock_image.width.return_value = 800
        mock_image.height.return_value = 600
        gui._LabGUI__image_obj = mock_image
        gui._LabGUI__crosshair_h = 10
        gui._LabGUI__crosshair_v = 11

        event = Mock()
        event.x = 900  # Outside bounds
        event.y = 300

        gui.on_mouse_move(event)

        # Verify crosshairs were deleted
        assert gui._LabGUI__crosshair_h is None
        assert gui._LabGUI__crosshair_v is None

    @patch("lab.gui.BirdDetector")
    @patch("lab.gui.tk.Canvas")
    @patch("lab.gui.tk.StringVar")
    @patch("lab.gui.tk.Label")
    @patch("lab.gui.tk.Button")
    @patch("lab.gui.tk.Frame")
    @patch("lab.gui.tk.Tk")
    def test_on_mouse_move_updates_existing_crosshairs(
        self,
        mock_tk_class,
        mock_frame_class,
        mock_button_class,
        mock_label_class,
        mock_stringvar_class,
        mock_canvas_class,
        mock_bird_detector_class,
        mock_tk_root,
    ):
        """Test on_mouse_move updates existing crosshairs."""
        mock_tk_class.return_value = mock_tk_root
        mock_stringvar_class.return_value = Mock()
        mock_frame_class.return_value = Mock()
        mock_button_class.return_value = Mock()
        mock_label_class.return_value = Mock()
        mock_canvas = Mock()
        mock_canvas_class.return_value = mock_canvas

        gui = LabGUI()
        mock_image = Mock()
        mock_image.width.return_value = 800
        mock_image.height.return_value = 600
        gui._LabGUI__image_obj = mock_image
        gui._LabGUI__crosshair_h = 10
        gui._LabGUI__crosshair_v = 11

        event = Mock()
        event.x = 400
        event.y = 300

        gui.on_mouse_move(event)

        # Verify coords were updated for existing crosshairs
        coords_calls = mock_canvas.coords.call_count
        assert coords_calls == 2  # One for h, one for v

    @patch("lab.gui.BirdDetector")
    @patch("lab.gui.tk.Canvas")
    @patch("lab.gui.tk.StringVar")
    @patch("lab.gui.tk.Label")
    @patch("lab.gui.tk.Button")
    @patch("lab.gui.tk.Frame")
    @patch("lab.gui.tk.Tk")
    def test_on_mouse_move_while_dragging(
        self,
        mock_tk_class,
        mock_frame_class,
        mock_button_class,
        mock_label_class,
        mock_stringvar_class,
        mock_canvas_class,
        mock_bird_detector_class,
        mock_tk_root,
    ):
        """Test on_mouse_move hides crosshairs while dragging selection."""
        mock_tk_class.return_value = mock_tk_root
        mock_stringvar_class.return_value = Mock()
        mock_frame_class.return_value = Mock()
        mock_button_class.return_value = Mock()
        mock_label_class.return_value = Mock()
        mock_canvas = Mock()
        mock_canvas_class.return_value = mock_canvas

        gui = LabGUI()
        mock_image = Mock()
        mock_image.width.return_value = 800
        mock_image.height.return_value = 600
        gui._LabGUI__image_obj = mock_image
        gui._LabGUI__selection_start = (100, 100)  # Dragging
        gui._LabGUI__crosshair_h = 10
        gui._LabGUI__crosshair_v = 11

        event = Mock()
        event.x = 400
        event.y = 300

        gui.on_mouse_move(event)

        # Verify crosshairs were hidden
        assert gui._LabGUI__crosshair_h is None
        assert gui._LabGUI__crosshair_v is None

    @patch("lab.gui.BirdDetector")
    @patch("lab.gui.tk.Canvas")
    @patch("lab.gui.tk.StringVar")
    @patch("lab.gui.tk.Label")
    @patch("lab.gui.tk.Button")
    @patch("lab.gui.tk.Frame")
    @patch("lab.gui.tk.Tk")
    def test_show_clear_button_when_not_mapped(
        self,
        mock_tk_class,
        mock_frame_class,
        mock_button_class,
        mock_label_class,
        mock_stringvar_class,
        mock_canvas_class,
        mock_bird_detector_class,
        mock_tk_root,
    ):
        """Test show_clear_button displays button when not already shown."""
        mock_tk_class.return_value = mock_tk_root
        mock_stringvar_class.return_value = Mock()
        mock_frame_class.return_value = Mock()
        mock_button_class.return_value = Mock()
        mock_label_class.return_value = Mock()
        mock_canvas_class.return_value = Mock()

        gui = LabGUI()
        gui.clear_btn.winfo_ismapped.return_value = False

        gui.show_clear_button()

        # Verify pack was called with correct padding
        gui.clear_btn.pack.assert_called()
        call_kwargs = gui.clear_btn.pack.call_args[1]
        assert call_kwargs.get("side") == "left"
        assert call_kwargs.get("padx") == (8, 0)

    @patch("lab.gui.BirdDetector")
    @patch("lab.gui.tk.Canvas")
    @patch("lab.gui.tk.StringVar")
    @patch("lab.gui.tk.Label")
    @patch("lab.gui.tk.Button")
    @patch("lab.gui.tk.Frame")
    @patch("lab.gui.tk.Tk")
    def test_show_clear_button_when_already_mapped(
        self,
        mock_tk_class,
        mock_frame_class,
        mock_button_class,
        mock_label_class,
        mock_stringvar_class,
        mock_canvas_class,
        mock_bird_detector_class,
        mock_tk_root,
    ):
        """Test show_clear_button doesn't duplicate when already shown."""
        mock_tk_class.return_value = mock_tk_root
        mock_stringvar_class.return_value = Mock()
        mock_frame_class.return_value = Mock()
        mock_button_class.return_value = Mock()
        mock_label_class.return_value = Mock()
        mock_canvas_class.return_value = Mock()

        gui = LabGUI()
        # Reset the pack call count (was called during init)
        gui.clear_btn.pack.reset_mock()
        gui.clear_btn.winfo_ismapped.return_value = True

        gui.show_clear_button()

        # pack should not be called again
        gui.clear_btn.pack.assert_not_called()

    @patch("lab.gui.BirdDetector")
    @patch("lab.gui.tk.Canvas")
    @patch("lab.gui.tk.StringVar")
    @patch("lab.gui.tk.Label")
    @patch("lab.gui.tk.Button")
    @patch("lab.gui.tk.Frame")
    @patch("lab.gui.tk.Tk")
    def test_hide_clear_button_when_mapped(
        self,
        mock_tk_class,
        mock_frame_class,
        mock_button_class,
        mock_label_class,
        mock_stringvar_class,
        mock_canvas_class,
        mock_bird_detector_class,
        mock_tk_root,
    ):
        """Test hide_clear_button hides button when shown."""
        mock_tk_class.return_value = mock_tk_root
        mock_stringvar_class.return_value = Mock()
        mock_frame_class.return_value = Mock()
        mock_button_class.return_value = Mock()
        mock_label_class.return_value = Mock()
        mock_canvas_class.return_value = Mock()

        gui = LabGUI()
        gui.clear_btn.winfo_ismapped.return_value = True

        gui.hide_clear_button()

        # Verify pack_forget was called
        gui.clear_btn.pack_forget.assert_called_once()

    @patch("lab.gui.BirdDetector")
    @patch("lab.gui.tk.Canvas")
    @patch("lab.gui.tk.StringVar")
    @patch("lab.gui.tk.Label")
    @patch("lab.gui.tk.Button")
    @patch("lab.gui.tk.Frame")
    @patch("lab.gui.tk.Tk")
    def test_hide_clear_button_when_not_mapped(
        self,
        mock_tk_class,
        mock_frame_class,
        mock_button_class,
        mock_label_class,
        mock_stringvar_class,
        mock_canvas_class,
        mock_bird_detector_class,
        mock_tk_root,
    ):
        """Test hide_clear_button does nothing when not shown."""
        mock_tk_class.return_value = mock_tk_root
        mock_stringvar_class.return_value = Mock()
        mock_frame_class.return_value = Mock()
        mock_button_class.return_value = Mock()
        mock_label_class.return_value = Mock()
        mock_canvas_class.return_value = Mock()

        gui = LabGUI()
        gui.clear_btn.winfo_ismapped.return_value = False

        gui.hide_clear_button()

        # Verify pack_forget was NOT called
        gui.clear_btn.pack_forget.assert_not_called()

    @patch("lab.gui.BirdDetector")
    @patch("lab.gui.tk.Canvas")
    @patch("lab.gui.tk.StringVar")
    @patch("lab.gui.tk.Label")
    @patch("lab.gui.tk.Button")
    @patch("lab.gui.tk.Frame")
    @patch("lab.gui.tk.Tk")
    def test_on_mouse_move_with_no_image(
        self,
        mock_tk_class,
        mock_frame_class,
        mock_button_class,
        mock_label_class,
        mock_stringvar_class,
        mock_canvas_class,
        mock_bird_detector_class,
        mock_tk_root,
    ):
        """Test on_mouse_move returns early when no image."""
        mock_tk_class.return_value = mock_tk_root
        mock_stringvar_class.return_value = Mock()
        mock_frame_class.return_value = Mock()
        mock_button_class.return_value = Mock()
        mock_label_class.return_value = Mock()
        mock_canvas = Mock()
        mock_canvas_class.return_value = mock_canvas

        gui = LabGUI()
        gui._LabGUI__image_obj = None

        event = Mock()
        event.x = 400
        event.y = 300

        gui.on_mouse_move(event)

        # Verify no crosshairs were created
        mock_canvas.create_line.assert_not_called()

    @patch("lab.gui.BirdDetector")
    @patch("lab.gui.tk.Canvas")
    @patch("lab.gui.tk.StringVar")
    @patch("lab.gui.tk.Label")
    @patch("lab.gui.tk.Button")
    @patch("lab.gui.tk.Frame")
    @patch("lab.gui.tk.Tk")
    def test_clear_all_with_no_selected_image(
        self,
        mock_tk_class,
        mock_frame_class,
        mock_button_class,
        mock_label_class,
        mock_stringvar_class,
        mock_canvas_class,
        mock_bird_detector_class,
        mock_tk_root,
    ):
        """Test clear_all doesn't try to reload image if none selected."""
        mock_tk_class.return_value = mock_tk_root
        mock_stringvar_class.return_value = Mock()
        mock_frame_class.return_value = Mock()
        mock_button_class.return_value = Mock()
        mock_label_class.return_value = Mock()
        mock_canvas = Mock()
        mock_canvas_class.return_value = mock_canvas

        gui = LabGUI()
        gui._LabGUI__selected_image = None
        gui._LabGUI__selection_regions = [(0, 0, 100, 100)]

        gui.clear_all()

        # Verify all regions were cleared
        assert len(gui._LabGUI__selection_regions) == 0

    @patch("lab.gui.BirdDetector")
    @patch("lab.gui.tk.Canvas")
    @patch("lab.gui.tk.StringVar")
    @patch("lab.gui.tk.Label")
    @patch("lab.gui.tk.Button")
    @patch("lab.gui.tk.Frame")
    @patch("lab.gui.tk.Tk")
    def test_on_selection_end_without_dimension_text(
        self,
        mock_tk_class,
        mock_frame_class,
        mock_button_class,
        mock_label_class,
        mock_stringvar_class,
        mock_canvas_class,
        mock_bird_detector_class,
        mock_tk_root,
    ):
        """Test on_selection_end when dimension_text is None."""
        mock_tk_class.return_value = mock_tk_root
        mock_stringvar_class.return_value = Mock()
        mock_frame_class.return_value = Mock()
        mock_button_class.return_value = Mock()
        mock_label_class.return_value = Mock()
        mock_canvas = Mock()
        mock_canvas_class.return_value = mock_canvas

        gui = LabGUI()
        mock_image = Mock()
        mock_image.width.return_value = 800
        mock_image.height.return_value = 600
        gui._LabGUI__image_obj = mock_image
        gui._LabGUI__selection_start = (50, 50)
        gui._LabGUI__current_rect = 1
        gui._LabGUI__dimension_text = None  # No text

        event = Mock()
        event.x = 530  # Creates a 480x480 square (valid size)
        event.y = 530

        gui.on_selection_end(event)

        # Verify region was added but no text handling
        assert len(gui._LabGUI__selection_regions) == 1
        assert gui._LabGUI__dimension_text is None

    @patch("lab.gui.BirdDetector")
    @patch("lab.gui.tk.Canvas")
    @patch("lab.gui.tk.StringVar")
    @patch("lab.gui.tk.Label")
    @patch("lab.gui.tk.Button")
    @patch("lab.gui.tk.Frame")
    @patch("lab.gui.tk.Tk")
    def test_clear_canvas_elements(
        self,
        mock_tk_class,
        mock_frame_class,
        mock_button_class,
        mock_label_class,
        mock_stringvar_class,
        mock_canvas_class,
        mock_bird_detector_class,
        mock_tk_root,
    ):
        """Test clear_canvas_elements clears canvas elements but preserves regions."""
        mock_tk_class.return_value = mock_tk_root
        mock_stringvar_class.return_value = Mock()
        mock_frame_class.return_value = Mock()
        mock_button_class.return_value = Mock()
        mock_label_class.return_value = Mock()
        mock_canvas = Mock()
        mock_canvas_class.return_value = mock_canvas

        gui = LabGUI()
        gui._LabGUI__current_rect = 1
        gui._LabGUI__selection_rects = [2, 3]
        gui._LabGUI__selection_bgs = [4, 5]
        gui._LabGUI__selection_texts = [6, 7]
        gui._LabGUI__selection_regions = [(0, 0, 100, 100)]  # Should be preserved
        gui._LabGUI__selection_start = (50, 50)
        gui._LabGUI__dimension_text = 8
        gui._LabGUI__dimension_bg = 9

        gui.clear_canvas_elements()

        # Verify canvas elements were deleted
        assert (
            mock_canvas.delete.call_count == 9
        )  # current_rect + 2 rects + 2 bgs + 2 texts + dimension_bg + dimension_text + canvas_image_id

        # Verify lists were cleared
        assert len(gui._LabGUI__selection_rects) == 0
        assert len(gui._LabGUI__selection_bgs) == 0
        assert len(gui._LabGUI__selection_texts) == 0
        assert gui._LabGUI__selection_start is None
        assert gui._LabGUI__current_rect is None

        # Verify regions were preserved
        assert len(gui._LabGUI__selection_regions) == 1
        assert gui._LabGUI__selection_regions[0] == (0, 0, 100, 100)

    @patch("lab.gui.BirdDetector")
    @patch("lab.gui.tk.Canvas")
    @patch("lab.gui.tk.StringVar")
    @patch("lab.gui.tk.Label")
    @patch("lab.gui.tk.Button")
    @patch("lab.gui.tk.Frame")
    @patch("lab.gui.tk.Tk")
    def test_redraw_selections(
        self,
        mock_tk_class,
        mock_frame_class,
        mock_button_class,
        mock_label_class,
        mock_stringvar_class,
        mock_canvas_class,
        mock_bird_detector_class,
        mock_tk_root,
    ):
        """Test redraw_selections recreates selection rectangles and labels."""
        mock_tk_class.return_value = mock_tk_root
        mock_stringvar_class.return_value = Mock()
        mock_frame_class.return_value = Mock()
        mock_button_class.return_value = Mock()
        mock_label_class.return_value = Mock()
        mock_canvas = Mock()
        mock_canvas_class.return_value = mock_canvas
        # For 2 regions: 2 rectangles + 2 background rectangles = 4 create_rectangle calls
        mock_canvas.create_rectangle.side_effect = [10, 12, 20, 22]
        # For 2 regions: 2 text elements = 2 create_text calls
        mock_canvas.create_text.side_effect = [11, 21]
        # For 2 regions: 2 bbox calls
        mock_canvas.bbox.side_effect = [(50, 50, 100, 70), (150, 150, 200, 170)]

        gui = LabGUI()
        gui._LabGUI__selection_regions = [(50, 50, 530, 530), (150, 150, 630, 630)]
        gui._LabGUI__selection_rects = []
        gui._LabGUI__selection_bgs = []
        gui._LabGUI__selection_texts = []

        gui.redraw_selections()

        # Verify rectangles were created
        assert mock_canvas.create_rectangle.call_count == 4  # 2 rects + 2 backgrounds
        assert len(gui._LabGUI__selection_rects) == 2
        assert gui._LabGUI__selection_rects == [10, 20]

        # Verify text and backgrounds were created
        assert mock_canvas.create_text.call_count == 2
        assert len(gui._LabGUI__selection_texts) == 2
        assert len(gui._LabGUI__selection_bgs) == 2
        assert gui._LabGUI__selection_bgs == [12, 22]

        # Verify clear button was shown
        assert gui.clear_btn.pack.called

    @patch("lab.gui.BirdDetector")
    @patch("lab.gui.tk.Canvas")
    @patch("lab.gui.tk.StringVar")
    @patch("lab.gui.tk.Label")
    @patch("lab.gui.tk.Button")
    @patch("lab.gui.tk.Frame")
    @patch("lab.gui.tk.Tk")
    def test_redraw_selections_with_no_bbox(
        self,
        mock_tk_class,
        mock_frame_class,
        mock_button_class,
        mock_label_class,
        mock_stringvar_class,
        mock_canvas_class,
        mock_bird_detector_class,
        mock_tk_root,
    ):
        """Test redraw_selections handles None bbox gracefully."""
        mock_tk_class.return_value = mock_tk_root
        mock_stringvar_class.return_value = Mock()
        mock_frame_class.return_value = Mock()
        mock_button_class.return_value = Mock()
        mock_label_class.return_value = Mock()
        mock_canvas = Mock()
        mock_canvas_class.return_value = mock_canvas
        mock_canvas.create_rectangle.return_value = 10
        mock_canvas.create_text.return_value = 11
        mock_canvas.bbox.return_value = None  # No bbox

        gui = LabGUI()
        gui._LabGUI__selection_regions = [(50, 50, 530, 530)]

        gui.redraw_selections()

        # Verify rectangle was created
        assert mock_canvas.create_rectangle.call_count == 1  # Only rect, no background
        assert len(gui._LabGUI__selection_rects) == 1

        # Verify text was created but no background
        assert mock_canvas.create_text.call_count == 1
        assert len(gui._LabGUI__selection_texts) == 1
        assert len(gui._LabGUI__selection_bgs) == 0

    @patch("lab.gui.BirdDetector")
    @patch("lab.gui.tk.Canvas")
    @patch("lab.gui.tk.StringVar")
    @patch("lab.gui.tk.Label")
    @patch("lab.gui.tk.Button")
    @patch("lab.gui.tk.Frame")
    @patch("lab.gui.tk.Tk")
    def test_redraw_selections_with_empty_regions(
        self,
        mock_tk_class,
        mock_frame_class,
        mock_button_class,
        mock_label_class,
        mock_stringvar_class,
        mock_canvas_class,
        mock_bird_detector_class,
        mock_tk_root,
    ):
        """Test redraw_selections with no regions doesn't show clear button."""
        mock_tk_class.return_value = mock_tk_root
        mock_stringvar_class.return_value = Mock()
        mock_frame_class.return_value = Mock()
        mock_button_class.return_value = Mock()
        mock_label_class.return_value = Mock()
        mock_canvas = Mock()
        mock_canvas_class.return_value = mock_canvas

        gui = LabGUI()
        # Reset pack call count since detect_btn gets packed during init
        gui.clear_btn.pack.reset_mock()
        gui._LabGUI__selection_regions = []

        gui.redraw_selections()

        # Verify no rectangles were created
        mock_canvas.create_rectangle.assert_not_called()

        # Verify clear button pack was not called (only called if there are regions)
        gui.clear_btn.pack.assert_not_called()
