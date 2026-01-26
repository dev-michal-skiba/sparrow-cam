from processor.utils import load_detection_preset


class TestLoadDetectionPreset:
    """Test suite for load_detection_preset function."""

    def test_load_detection_preset_explicit_values(self):
        """Test that preset contains expected explicit values."""
        preset = load_detection_preset()

        assert preset == {
            "params": {"conf": 0.01, "imgsz": 320, "iou": 0.5},
            "regions": [[302, 98, 622, 418]],
        }
