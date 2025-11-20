from unittest.mock import MagicMock, call

import pytest

from processor.hls_segment_processor import HLSSegmentProcessor


@pytest.fixture
def setup_video_capture(monkeypatch):
    """Configure a fake cv2.VideoCapture instance for the test."""

    def _setup_video_capture(*, opened, read_return):
        class DummyCapture:
            def __init__(self):
                self.release_called = False

            def isOpened(self):
                return opened

            def read(self):
                return read_return

            def release(self):
                self.release_called = True

        capture = DummyCapture()
        monkeypatch.setattr("processor.hls_segment_processor.cv2.VideoCapture", lambda _path: capture)
        return capture

    return _setup_video_capture


@pytest.fixture
def mock_bird_detector(monkeypatch):
    mock_detector = MagicMock()
    mock_detector.detect.return_value = False
    monkeypatch.setattr("processor.hls_segment_processor.BirdDetector", lambda: mock_detector)
    return mock_detector


@pytest.fixture
def mock_bird_annotator(monkeypatch):
    mock_annotator = MagicMock()
    monkeypatch.setattr("processor.hls_segment_processor.BirdAnnotator", lambda: mock_annotator)
    return mock_annotator


@pytest.fixture
def dummy_watchtower(monkeypatch):
    class DummyWatchtower:
        def __init__(self):
            self.seen_segments = {"segment_001.ts", "segment_002.ts"}
            self.segments = [
                "/watchtower/segment_001.ts",
                "/watchtower/segment_002.ts",
            ]

        @property
        def segments_iterator(self):
            yield from self.segments

    watchtower = DummyWatchtower()
    monkeypatch.setattr("processor.hls_segment_processor.HLSWatchtower", lambda: watchtower)
    return watchtower


@pytest.fixture
def hls_processor(mock_bird_detector, mock_bird_annotator):
    """Provide an HLSSegmentProcessor with patched dependencies."""
    return HLSSegmentProcessor()


class TestHLSSegmentProcessor:
    @pytest.mark.parametrize("detect_return_value, annotate_call_value", [(True, True), (False, False)])
    def test_process_segment_detects_and_annotates(
        self,
        hls_processor,
        mock_bird_detector,
        mock_bird_annotator,
        setup_video_capture,
        detect_return_value,
        annotate_call_value,
    ):
        mock_bird_detector.detect.return_value = detect_return_value
        capture = setup_video_capture(opened=True, read_return=(True, "frame"))

        hls_processor.process_segment("/tmp/segment_001.ts", "segment_001.ts")

        mock_bird_detector.detect.assert_called_once_with("frame")
        mock_bird_annotator.annotate.assert_called_once_with("segment_001.ts", annotate_call_value)
        assert capture.release_called is True

    def test_process_segment_handles_failed_video_open(
        self, hls_processor, mock_bird_detector, mock_bird_annotator, setup_video_capture
    ):
        capture = setup_video_capture(opened=False, read_return=None)

        hls_processor.process_segment("/tmp/segment_002.ts", "segment_002.ts")

        mock_bird_detector.detect.assert_not_called()
        mock_bird_annotator.annotate.assert_not_called()
        assert capture.release_called is True

    def test_process_segment_handles_failed_frame_read(
        self, hls_processor, mock_bird_detector, mock_bird_annotator, setup_video_capture
    ):
        capture = setup_video_capture(opened=False, read_return=(False, None))

        hls_processor.process_segment("/tmp/segment_003.ts", "segment_003.ts")

        mock_bird_detector.detect.assert_not_called()
        mock_bird_annotator.annotate.assert_not_called()
        assert capture.release_called is True

    def test_run_processes_segments_and_prunes(self, hls_processor, mock_bird_annotator, dummy_watchtower):
        hls_processor.process_segment = MagicMock()

        hls_processor.run()

        expected_segment_calls = [
            call("/watchtower/segment_001.ts", "segment_001.ts"),
            call("/watchtower/segment_002.ts", "segment_002.ts"),
        ]
        hls_processor.process_segment.assert_has_calls(expected_segment_calls)
        expected_prune_calls = [call(dummy_watchtower.seen_segments) for _ in dummy_watchtower.segments]
        mock_bird_annotator.prune.assert_has_calls(expected_prune_calls)
