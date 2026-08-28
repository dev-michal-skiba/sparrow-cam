from datetime import datetime
from unittest.mock import patch

from processor.utils import is_maintenance_window, load_detection_preset


class TestLoadDetectionPreset:
    """Test suite for load_detection_preset function."""

    def test_load_detection_preset_explicit_values(self):
        """Test that preset contains expected explicit values."""
        preset = load_detection_preset()

        assert preset == {
            "params": {"imgsz": 640, "iou": 0.5},
            "class_thresholds": {"14": 0.1},
        }


class TestIsMaintenanceWindow:
    """Test suite for is_maintenance_window function."""

    @patch("processor.utils.MAINTENANCE_WINDOW_ENABLED", False)
    def test_disabled_returns_false_always(self):
        """When disabled via env var, always returns False regardless of time."""
        # Test various times when disabled
        result_midnight = is_maintenance_window(datetime(2024, 1, 1, 0, 0, 0))
        result_window_start = is_maintenance_window(datetime(2024, 1, 1, 23, 0, 0))
        result_window_end = is_maintenance_window(datetime(2024, 1, 2, 3, 0, 0))
        result_day = is_maintenance_window(datetime(2024, 1, 1, 12, 0, 0))

        assert result_midnight is False
        assert result_window_start is False
        assert result_window_end is False
        assert result_day is False

    @patch("processor.utils.MAINTENANCE_WINDOW_ENABLED", True)
    def test_within_window_evening_hours(self):
        """Time within maintenance window (evening hours) returns True."""
        # 23:30 is within 23:00-03:00 window
        result = is_maintenance_window(datetime(2024, 1, 1, 23, 30, 0))
        assert result is True

    @patch("processor.utils.MAINTENANCE_WINDOW_ENABLED", True)
    def test_within_window_after_midnight(self):
        """Time within maintenance window (after midnight) returns True."""
        # 02:00 is within 23:00-03:00 window (wraps past midnight)
        result = is_maintenance_window(datetime(2024, 1, 2, 2, 0, 0))
        assert result is True

    @patch("processor.utils.MAINTENANCE_WINDOW_ENABLED", True)
    def test_outside_window_day_hours(self):
        """Time outside maintenance window (day hours) returns False."""
        # 10:00 is outside 23:00-03:00 window
        result = is_maintenance_window(datetime(2024, 1, 1, 10, 0, 0))
        assert result is False

    @patch("processor.utils.MAINTENANCE_WINDOW_ENABLED", True)
    def test_outside_window_evening_hours(self):
        """Time outside maintenance window (early evening) returns False."""
        # 22:00 is outside 23:00-03:00 window
        result = is_maintenance_window(datetime(2024, 1, 1, 22, 0, 0))
        assert result is False

    @patch("processor.utils.MAINTENANCE_WINDOW_ENABLED", True)
    def test_boundary_start_time_inclusive(self):
        """Start time (23:00) is inclusive - returns True."""
        result = is_maintenance_window(datetime(2024, 1, 1, 23, 0, 0))
        assert result is True

    @patch("processor.utils.MAINTENANCE_WINDOW_ENABLED", True)
    def test_boundary_end_time_exclusive(self):
        """End time (03:00) is exclusive - returns False."""
        result = is_maintenance_window(datetime(2024, 1, 2, 3, 0, 0))
        assert result is False

    @patch("processor.utils.MAINTENANCE_WINDOW_ENABLED", True)
    def test_just_before_end_time(self):
        """One second before end time returns True."""
        result = is_maintenance_window(datetime(2024, 1, 2, 2, 59, 59))
        assert result is True

    @patch("processor.utils.MAINTENANCE_WINDOW_ENABLED", True)
    def test_just_after_end_time(self):
        """One second after end time returns False."""
        result = is_maintenance_window(datetime(2024, 1, 2, 3, 0, 1))
        assert result is False

    @patch("processor.utils.MAINTENANCE_WINDOW_ENABLED", True)
    @patch("processor.utils.datetime")
    def test_uses_current_time_when_not_provided(self, mock_datetime):
        """When now parameter is None, uses current local time."""
        current_time = datetime(2024, 1, 1, 23, 30, 0)
        mock_datetime.now.return_value = current_time
        mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)

        result = is_maintenance_window()
        assert result is True
        mock_datetime.now.assert_called_once()
