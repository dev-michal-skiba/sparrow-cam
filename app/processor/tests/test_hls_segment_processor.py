from unittest.mock import MagicMock, call

import pytest

from processor.hls_segment_processor import (
    ARCHIVE_SEGMENT_COUNT,
    HLSSegmentProcessor,
    _get_detection_frame_indices,
)


@pytest.fixture
def setup_video_capture(monkeypatch):
    """Configure a fake cv2.VideoCapture instance for the test."""

    def _setup_video_capture(*, opened, read_return, total_frames=30):
        class DummyCapture:
            def __init__(self):
                self.release_called = False
                self._frame_pos = 0
                self._total_frames = total_frames

            def isOpened(self):
                return opened

            def read(self):
                return read_return

            def release(self):
                self.release_called = True

            def get(self, prop_id):
                if prop_id == 7:  # cv2.CAP_PROP_FRAME_COUNT
                    return float(self._total_frames)
                return 0.0

            def set(self, prop_id, value):
                if prop_id == 1:  # cv2.CAP_PROP_POS_FRAMES
                    self._frame_pos = int(value)
                return True

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


class TestGetDetectionFrameIndices:
    """Test suite for _get_detection_frame_indices function."""

    def test_frame_count_less_than_total(self):
        """Test sampling 2 frames from 30 total frames."""
        result = _get_detection_frame_indices(30, 2)
        assert result == [0, 15]

    def test_frame_count_equals_total(self):
        """Test when frame_count equals total_frames."""
        result = _get_detection_frame_indices(5, 5)
        assert result == [0, 1, 2, 3, 4]

    def test_frame_count_greater_than_total(self):
        """Test when frame_count is greater than total_frames."""
        result = _get_detection_frame_indices(3, 5)
        assert result == [0, 1, 2]

    def test_three_frames_from_30(self):
        """Test sampling 3 frames from 30 total frames."""
        result = _get_detection_frame_indices(30, 3)
        assert result == [0, 10, 20]

    def test_no_duplicate_indices(self):
        """Test that duplicate indices are removed."""
        result = _get_detection_frame_indices(5, 10)
        assert len(result) == len(set(result))

    def test_indices_sorted(self):
        """Test that returned indices are sorted."""
        result = _get_detection_frame_indices(100, 4)
        assert result == sorted(result)

    def test_single_frame(self):
        """Test sampling 1 frame."""
        result = _get_detection_frame_indices(30, 1)
        assert result == [0]

    def test_zero_total_frames(self):
        """Test with zero total frames."""
        result = _get_detection_frame_indices(0, 2)
        assert result == []


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
            capture = setup_video_capture(opened=True, read_return=(True, no_bird_frame), total_frames=30)

            result = hls_processor.process_segment("/tmp/segment_001.ts", "segment_001.ts")

            # With DETECTION_FRAME_COUNT=2 and 30 frames, detects at indices [0, 15]
            # Each frame has detection_regions, so detect is called multiple times
            assert mock_bird_detector.detect.call_count > 0
            mock_bird_annotator.annotate.assert_called_once_with("segment_001.ts", annotate_call_value)
            assert result == detect_return_value
            assert capture.release_called is True

        def test_process_segment_handles_failed_video_open(
            self, hls_processor, mock_bird_detector, mock_bird_annotator, setup_video_capture
        ):
            capture = setup_video_capture(opened=False, read_return=None, total_frames=30)

            result = hls_processor.process_segment("/tmp/segment_002.ts", "segment_002.ts")

            mock_bird_detector.detect.assert_not_called()
            mock_bird_annotator.annotate.assert_not_called()
            assert result is False
            assert capture.release_called is True

        def test_process_segment_handles_failed_frame_read(
            self, hls_processor, mock_bird_detector, mock_bird_annotator, setup_video_capture
        ):
            """Test that failed frame reads are handled gracefully and annotation still happens."""
            capture = setup_video_capture(opened=True, read_return=(False, None), total_frames=30)

            result = hls_processor.process_segment("/tmp/segment_003.ts", "segment_003.ts")

            # When frame reads fail, detect is not called, but annotation still happens with False
            mock_bird_detector.detect.assert_not_called()
            mock_bird_annotator.annotate.assert_called_once_with("segment_003.ts", False)
            assert result is False
            assert capture.release_called is True

        def test_process_segment_handles_invalid_frame_count(
            self, hls_processor, mock_bird_detector, mock_bird_annotator, setup_video_capture
        ):
            """Test that invalid frame count (<=0) is handled gracefully."""
            capture = setup_video_capture(opened=True, read_return=(True, None), total_frames=0)

            result = hls_processor.process_segment("/tmp/segment_004.ts", "segment_004.ts")

            mock_bird_detector.detect.assert_not_called()
            mock_bird_annotator.annotate.assert_not_called()
            assert result is False
            assert capture.release_called is True

        def test_process_segment_detects_bird_in_first_frame(
            self,
            hls_processor,
            mock_bird_detector,
            mock_bird_annotator,
            setup_video_capture,
            no_bird_frame,
        ):
            """Test that detection stops once a bird is detected in an earlier frame."""
            capture = setup_video_capture(opened=True, read_return=(True, no_bird_frame), total_frames=30)
            # Bird detected on first frame (frame 0)
            mock_bird_detector.detect.side_effect = [True]

            result = hls_processor.process_segment("/tmp/segment_005.ts", "segment_005.ts")

            # Should only call detect once (early exit after finding bird)
            assert mock_bird_detector.detect.call_count == 1
            mock_bird_annotator.annotate.assert_called_once_with("segment_005.ts", True)
            assert result is True
            assert capture.release_called is True

        def test_process_segment_checks_multiple_frames(
            self,
            hls_processor,
            mock_bird_detector,
            mock_bird_annotator,
            setup_video_capture,
            no_bird_frame,
        ):
            """Test that detection checks multiple frames (DETECTION_FRAME_COUNT)."""
            capture = setup_video_capture(opened=True, read_return=(True, no_bird_frame), total_frames=30)
            # No bird detected in any frame
            mock_bird_detector.detect.return_value = False

            result = hls_processor.process_segment("/tmp/segment_006.ts", "segment_006.ts")

            # With DETECTION_FRAME_COUNT=2 and default detection regions, should check multiple frames
            # Each frame has detection_regions applied, so calls increase
            assert mock_bird_detector.detect.call_count > 1
            mock_bird_annotator.annotate.assert_called_once_with("segment_006.ts", False)
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

            # With DETECTION_FRAME_COUNT=2, each segment calls detect() twice (2 frames * 1 region)
            # 15 segments * 2 calls = 30 calls needed
            # Bird detected on first segment (first 2 calls), rest are False
            mock_bird_detector.detect.side_effect = [True, False] + [False] * 28
            setup_video_capture(opened=True, read_return=(True, no_bird_frame), total_frames=30)
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

            # With DETECTION_FRAME_COUNT=2, each segment calls detect() twice
            # 15 segments * 2 calls = 30 calls needed
            # Birds detected on segments 1, 2, 3 (early exit, so 2 calls per segment first 3)
            # After early exit: segment 0: [True, False], segment 1: [True], segment 2: [True], rest all False
            mock_bird_detector.detect.side_effect = [True, False, True, True] + [False] * 26
            setup_video_capture(opened=True, read_return=(True, no_bird_frame), total_frames=30)
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

            # With DETECTION_FRAME_COUNT=2, each segment calls detect() twice
            # 30 segments * 2 calls = 60 calls needed
            # First detection on segment 0 (early exit after first True)
            # Second detection on segment 9 (within 7 of last archive at segment 7)
            detect_results = [True, False]  # segment 0: early exit
            detect_results += [False] * 18  # segments 1-9 (before second detection)
            detect_results += [True, False]  # segment 9: early exit
            detect_results += [False] * 40  # remaining segments
            mock_bird_detector.detect.side_effect = detect_results
            setup_video_capture(opened=True, read_return=(True, no_bird_frame), total_frames=30)
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

            # With DETECTION_FRAME_COUNT=2, each segment calls detect() twice
            # 30 segments * 2 calls = 60 calls needed
            # First detection on segment 0 (early exit after first True)
            # Second detection on segment 19 (outside 7-segment overlap zone)
            detect_results = [True, False]  # segment 0: early exit
            detect_results += [False] * 38  # segments 1-19 (before second detection)
            detect_results += [True, False]  # segment 19: early exit
            detect_results += [False] * 20  # remaining segments
            mock_bird_detector.detect.side_effect = detect_results
            setup_video_capture(opened=True, read_return=(True, no_bird_frame), total_frames=30)
            processor = HLSSegmentProcessor()

            processor.run()

            assert mock_stream_archiver.archive.call_count == 2
            calls = mock_stream_archiver.archive.call_args_list

            # First archive at segment_007
            assert calls[0] == call(limit=ARCHIVE_SEGMENT_COUNT, prefix="auto", end_segment="segment_007.ts")

            # Second archive centered on segment_019, so 7 segments later = segment_026
            # (but segment indices are 0-based, so segment 19 + 8 = 27)
            assert calls[1] == call(limit=ARCHIVE_SEGMENT_COUNT, prefix="auto", end_segment="segment_027.ts")

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
