from unittest.mock import ANY, MagicMock, call

import pytest

from processor.hls_segment_processor import (
    ARCHIVE_SEGMENT_COUNT,
    HLSSegmentProcessor,
)


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
def mock_stream_archiver(monkeypatch):
    mock_archiver = MagicMock()
    monkeypatch.setattr("processor.hls_segment_processor.StreamArchiver", lambda: mock_archiver)
    return mock_archiver


def make_watchtower(segment_names):
    """Create a DummyWatchtower with specified segment names."""

    class DummyWatchtower:
        def __init__(self):
            self.seen_segments = set(segment_names)
            self.segments = [f"/watchtower/{name}" for name in segment_names]

        @property
        def segments_iterator(self):
            yield from self.segments

    return DummyWatchtower()


@pytest.fixture
def dummy_watchtower(monkeypatch):
    watchtower = make_watchtower(["segment_001.ts", "segment_002.ts"])
    monkeypatch.setattr("processor.hls_segment_processor.HLSWatchtower", lambda: watchtower)
    return watchtower


@pytest.fixture
def hls_processor(mock_bird_detector, mock_bird_annotator, mock_stream_archiver):
    """Provide an HLSSegmentProcessor with patched dependencies."""
    return HLSSegmentProcessor()


class TestHLSSegmentProcessor:
    """Test suite for HLSSegmentProcessor class."""

    class TestProcessSegment:
        """Tests for process_segment method."""

        @pytest.mark.parametrize("detect_return_value, annotate_call_value", [(True, True), (False, False)])
        def test_process_segment_detects_and_annotates(
            self,
            hls_processor,
            mock_bird_detector,
            mock_bird_annotator,
            setup_video_capture,
            no_bird_frame,
            detect_return_value,
            annotate_call_value,
        ):
            """Test that process_segment detects birds and annotates correctly."""
            mock_bird_detector.detect.return_value = detect_return_value
            capture = setup_video_capture(opened=True, read_return=(True, no_bird_frame))

            result = hls_processor.process_segment("/tmp/segment_001.ts", "segment_001.ts")

            mock_bird_detector.detect.assert_called_once_with(ANY, conf=0.05, imgsz=320, iou=0.5)
            mock_bird_annotator.annotate.assert_called_once_with("segment_001.ts", annotate_call_value)
            assert result == detect_return_value
            assert capture.release_called is True

        def test_process_segment_handles_failed_video_open(
            self, hls_processor, mock_bird_detector, mock_bird_annotator, setup_video_capture
        ):
            capture = setup_video_capture(opened=False, read_return=None)

            result = hls_processor.process_segment("/tmp/segment_002.ts", "segment_002.ts")

            mock_bird_detector.detect.assert_not_called()
            mock_bird_annotator.annotate.assert_not_called()
            assert result is False
            assert capture.release_called is True

        def test_process_segment_handles_failed_frame_read(
            self, hls_processor, mock_bird_detector, mock_bird_annotator, setup_video_capture
        ):
            capture = setup_video_capture(opened=True, read_return=(False, None))

            result = hls_processor.process_segment("/tmp/segment_003.ts", "segment_003.ts")

            mock_bird_detector.detect.assert_not_called()
            mock_bird_annotator.annotate.assert_not_called()
            assert result is False
            assert capture.release_called is True

    class TestDelayedArchive:
        """Tests for delayed archive behavior (archive triggers 7 segments after detection)."""

        def test_archive_triggered_after_delay(
            self,
            mock_bird_detector,
            mock_bird_annotator,
            mock_stream_archiver,
            monkeypatch,
            setup_video_capture,
            no_bird_frame,
        ):
            """Test that archive is triggered 7 segments after bird detection."""
            # Create 15 segments (enough to trigger archive after delay)
            segment_names = [f"segment_{i:03d}.ts" for i in range(15)]
            watchtower = make_watchtower(segment_names)
            monkeypatch.setattr("processor.hls_segment_processor.HLSWatchtower", lambda: watchtower)

            # Bird detected on segment 1 (index 0)
            mock_bird_detector.detect.side_effect = [True] + [False] * 14
            setup_video_capture(opened=True, read_return=(True, no_bird_frame))
            processor = HLSSegmentProcessor()

            processor.run()

            # Archive should be called once, 7 segments after detection (on segment 8, index 7)
            mock_stream_archiver.archive.assert_called_once_with(
                limit=ARCHIVE_SEGMENT_COUNT,
                prefix="auto",
                end_segment="segment_007.ts",
            )

        def test_no_archive_if_not_enough_segments_after_detection(
            self, mock_bird_detector, mock_bird_annotator, mock_stream_archiver, monkeypatch
        ):
            """Test that archive is not triggered if stream ends before delay completes."""
            # Only 5 segments after detection (not enough)
            segment_names = [f"segment_{i:03d}.ts" for i in range(6)]
            watchtower = make_watchtower(segment_names)
            monkeypatch.setattr("processor.hls_segment_processor.HLSWatchtower", lambda: watchtower)

            # Bird detected on segment 1 (index 0)
            mock_bird_detector.detect.side_effect = [True] + [False] * 5
            processor = HLSSegmentProcessor()

            processor.run()

            # Archive should not be called (only 5 segments after detection, need 7)
            mock_stream_archiver.archive.assert_not_called()

        def test_multiple_detections_only_one_archive(
            self,
            mock_bird_detector,
            mock_bird_annotator,
            mock_stream_archiver,
            monkeypatch,
            setup_video_capture,
            no_bird_frame,
        ):
            """Test that multiple detections during countdown don't trigger multiple archives."""
            segment_names = [f"segment_{i:03d}.ts" for i in range(15)]
            watchtower = make_watchtower(segment_names)
            monkeypatch.setattr("processor.hls_segment_processor.HLSWatchtower", lambda: watchtower)

            # Birds detected on segments 1, 2, 3 (within the same countdown period)
            mock_bird_detector.detect.side_effect = [True, True, True] + [False] * 12
            setup_video_capture(opened=True, read_return=(True, no_bird_frame))
            processor = HLSSegmentProcessor()

            processor.run()

            # Only one archive should be called (first detection starts countdown, others ignored)
            assert mock_stream_archiver.archive.call_count == 1

    class TestOverlapPrevention:
        """Tests for overlap prevention when bird detected near last archive."""

        def test_overlap_zone_detection_adjusts_countdown(
            self,
            mock_bird_detector,
            mock_bird_annotator,
            mock_stream_archiver,
            monkeypatch,
            setup_video_capture,
            no_bird_frame,
        ):
            """Test that detection in overlap zone starts archive from after last archived segment."""
            # Need enough segments for two archives with overlap scenario
            segment_names = [f"segment_{i:03d}.ts" for i in range(30)]
            watchtower = make_watchtower(segment_names)
            monkeypatch.setattr("processor.hls_segment_processor.HLSWatchtower", lambda: watchtower)

            # First detection on segment 1, second detection on segment 10 (within 7 of last archive at 8)
            # Detection pattern: True at index 0, True at index 9, rest False
            detect_results = [False] * 30
            detect_results[0] = True  # First detection at segment_000
            detect_results[9] = True  # Second detection at segment_009 (within 7 of last archive at segment_007)
            mock_bird_detector.detect.side_effect = detect_results
            setup_video_capture(opened=True, read_return=(True, no_bird_frame))
            processor = HLSSegmentProcessor()

            processor.run()

            # Should have two archive calls
            assert mock_stream_archiver.archive.call_count == 2
            calls = mock_stream_archiver.archive.call_args_list

            # First archive at segment_007 (7 segments after detection at 0)
            assert calls[0] == call(limit=ARCHIVE_SEGMENT_COUNT, prefix="auto", end_segment="segment_007.ts")

            # Second archive should NOT be centered on segment_009 + 7 = segment_016
            # Instead it should continue from last archive, ending at segment_022
            # (15 segments starting from segment_008, ending at segment_022)
            assert calls[1] == call(limit=ARCHIVE_SEGMENT_COUNT, prefix="auto", end_segment="segment_022.ts")

        def test_no_overlap_when_detection_outside_zone(
            self,
            mock_bird_detector,
            mock_bird_annotator,
            mock_stream_archiver,
            monkeypatch,
            setup_video_capture,
            no_bird_frame,
        ):
            """Test that detection outside overlap zone triggers normal centered archive."""
            segment_names = [f"segment_{i:03d}.ts" for i in range(30)]
            watchtower = make_watchtower(segment_names)
            monkeypatch.setattr("processor.hls_segment_processor.HLSWatchtower", lambda: watchtower)

            # First detection on segment 1, second detection on segment 20 (outside 7-segment overlap zone)
            detect_results = [False] * 30
            detect_results[0] = True  # First detection at segment_000
            detect_results[19] = True  # Second detection at segment_019 (outside overlap zone)
            mock_bird_detector.detect.side_effect = detect_results
            setup_video_capture(opened=True, read_return=(True, no_bird_frame))
            processor = HLSSegmentProcessor()

            processor.run()

            assert mock_stream_archiver.archive.call_count == 2
            calls = mock_stream_archiver.archive.call_args_list

            # First archive at segment_007
            assert calls[0] == call(limit=ARCHIVE_SEGMENT_COUNT, prefix="auto", end_segment="segment_007.ts")

            # Second archive centered on segment_019, so 7 segments later = segment_026
            assert calls[1] == call(limit=ARCHIVE_SEGMENT_COUNT, prefix="auto", end_segment="segment_026.ts")

    class TestRun:
        """Tests for the main run loop."""

        def test_run_processes_segments_and_prunes(self, hls_processor, mock_bird_annotator, dummy_watchtower):
            hls_processor.process_segment = MagicMock(return_value=False)

            hls_processor.run()

            expected_segment_calls = [
                call("/watchtower/segment_001.ts", "segment_001.ts"),
                call("/watchtower/segment_002.ts", "segment_002.ts"),
            ]
            hls_processor.process_segment.assert_has_calls(expected_segment_calls)
            expected_prune_calls = [call(dummy_watchtower.seen_segments) for _ in dummy_watchtower.segments]
            mock_bird_annotator.prune.assert_has_calls(expected_prune_calls)
