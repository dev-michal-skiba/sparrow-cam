from processor.bird_detector import BirdDetector


class TestBirdDetector:
    """Test suite for BirdDetector class."""

    def test_detect_frame_with_bird(self, bird_frame):
        """Test that detector returns True when bird is present in frame."""
        detector = BirdDetector()
        result = detector.detect(bird_frame)
        assert result is True

    def test_detect_frame_without_bird(self, no_bird_frame):
        """Test that detector returns False when no bird is present in frame."""
        detector = BirdDetector()
        result = detector.detect(no_bird_frame)
        assert result is False
