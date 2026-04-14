from processor.utils import load_detection_preset


class TestLoadDetectionPreset:
    """Test suite for load_detection_preset function."""

    def test_load_detection_preset_explicit_values(self):
        """Test that preset contains expected explicit values."""
        preset = load_detection_preset()

        assert preset == {
            "params": {"imgsz": 480, "iou": 0.5},
            "class_thresholds": {"0": 0.8, "2": 0.9},
            "regions": [[194, 0, 674, 480]],
        }
