from processor.utils import load_detection_preset


class TestLoadDetectionPreset:
    """Test suite for load_detection_preset function."""

    def test_load_detection_preset_explicit_values(self):
        """Test that preset contains expected explicit values."""
        preset = load_detection_preset()

        assert preset == {
            "params": {"imgsz": 640, "iou": 0.5},
            "class_thresholds": {"14": 0.01},
        }
