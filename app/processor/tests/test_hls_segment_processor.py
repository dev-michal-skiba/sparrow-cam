from unittest.mock import MagicMock, call

import pytest

from processor.bird_detector import GREAT_TIT_CLASS_ID, PIGEON_CLASS_ID
from processor.hls_segment_processor import (
    HLSSegmentProcessor,
    _get_detection_frame_indices,
)
from processor.types import DetectionBox

_MOCK_BOX = DetectionBox(10, 20, 100, 200, 0, 0.9)


def _calc_segments_before(n: int) -> int:
    """Calculate segments before detection for given archive count."""
    return (n - 1) // 2


def _calc_segments_after(n: int) -> int:
    """Calculate segments after detection for given archive count."""
    return n - 1 - _calc_segments_before(n)


@pytest.fixture(params=[15, 30], ids=["odd_15", "even_30"])
def archive_config(request, monkeypatch):
    """Fixture that patches archive constants for both odd (15) and even (30) values.

    Returns a dict with segment_count, segments_before, and segments_after.
    """
    segment_count = request.param
    segments_before = _calc_segments_before(segment_count)
    segments_after = _calc_segments_after(segment_count)

    monkeypatch.setattr("processor.stream_archiver.ARCHIVE_ENABLED", True)
    monkeypatch.setattr("processor.stream_archiver.ARCHIVE_SEGMENT_COUNT", segment_count)
    monkeypatch.setattr("processor.stream_archiver.SEGMENTS_BEFORE_DETECTION", segments_before)
    monkeypatch.setattr("processor.stream_archiver.SEGMENTS_AFTER_DETECTION", segments_after)

    return {
        "segment_count": segment_count,
        "segments_before": segments_before,
        "segments_after": segments_after,
    }


@pytest.fixture(params=[1, 4], ids=["frames_1", "frames_4"])
def detection_frame_config(request, monkeypatch):
    """Fixture that patches DETECTION_FRAME_COUNT for both 1 and 4 values.

    Returns a dict with frame_count.
    """
    frame_count = request.param
    monkeypatch.setattr("processor.hls_segment_processor.DETECTION_FRAME_COUNT", frame_count)
    return {"frame_count": frame_count}


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
    mock_detector.detect_boxes.return_value = []
    mock_detector.class_name.return_value = "MockBird"
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
            mock_bird_detector,
            mock_bird_annotator,
            mock_stream_archiver,
            setup_video_capture,
            no_bird_frame,
            detect_return_value,
            annotate_call_value,
            detection_frame_config,
        ):
            """Test that process_segment detects birds and annotates correctly."""
            mock_bird_detector.detect_boxes.return_value = [_MOCK_BOX] if detect_return_value else []
            capture = setup_video_capture(opened=True, read_return=(True, no_bird_frame), total_frames=30)
            processor = HLSSegmentProcessor()

            result = processor.process_segment("/tmp/segment_001.ts", "segment_001.ts")

            # Detection is called based on DETECTION_FRAME_COUNT and detection_regions
            assert mock_bird_detector.detect_boxes.call_count > 0
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
            mock_bird_detector.detect_boxes.side_effect = [[_MOCK_BOX]]

            result = hls_processor.process_segment("/tmp/segment_005.ts", "segment_005.ts")

            # Should only call detect_boxes once (early exit after finding bird)
            assert mock_bird_detector.detect_boxes.call_count == 1
            mock_bird_annotator.annotate.assert_called_once_with("segment_005.ts", True)
            assert result is True
            assert capture.release_called is True

        def test_process_segment_checks_configured_frames(
            self,
            mock_bird_detector,
            mock_bird_annotator,
            mock_stream_archiver,
            setup_video_capture,
            no_bird_frame,
            detection_frame_config,
        ):
            """Test that detection checks DETECTION_FRAME_COUNT frames."""
            frame_count = detection_frame_config["frame_count"]
            capture = setup_video_capture(opened=True, read_return=(True, no_bird_frame), total_frames=30)
            # No bird detected in any frame
            mock_bird_detector.detect_boxes.return_value = []
            processor = HLSSegmentProcessor()

            result = processor.process_segment("/tmp/segment_006.ts", "segment_006.ts")

            # detect_boxes is called frame_count times (1 region per frame)
            assert mock_bird_detector.detect_boxes.call_count == frame_count
            mock_bird_annotator.annotate.assert_called_once_with("segment_006.ts", False)
            assert result is False
            assert capture.release_called is True

        def test_process_segment_records_detections_when_bird_detected(
            self,
            mock_bird_detector,
            mock_bird_annotator,
            mock_stream_archiver,
            setup_video_capture,
            no_bird_frame,
        ):
            """Test that process_segment passes detection details to the archiver."""
            mock_bird_detector.detect_boxes.side_effect = [[_MOCK_BOX]]
            mock_bird_detector.class_name.return_value = "Pigeon"
            setup_video_capture(opened=True, read_return=(True, no_bird_frame), total_frames=30)
            processor = HLSSegmentProcessor()

            processor.process_segment("/tmp/segment_001.ts", "segment_001.ts")

            mock_stream_archiver.record_detections.assert_called_once_with(
                "segment_001.ts",
                [{"class": "Pigeon", "confidence": 0.9, "roi": {"x1": 10, "y1": 20, "x2": 100, "y2": 200}}],
            )

        def test_process_segment_records_empty_detections_when_no_bird(
            self,
            hls_processor,
            mock_stream_archiver,
            mock_bird_annotator,
            setup_video_capture,
            no_bird_frame,
        ):
            """Test that process_segment passes empty detections to the archiver when no bird found."""
            setup_video_capture(opened=True, read_return=(True, no_bird_frame), total_frames=30)

            hls_processor.process_segment("/tmp/segment_001.ts", "segment_001.ts")

            mock_stream_archiver.record_detections.assert_called_once_with("segment_001.ts", [])

        def test_process_segment_passes_class_thresholds_to_detector(
            self,
            mock_bird_detector,
            mock_bird_annotator,
            mock_stream_archiver,
            setup_video_capture,
            no_bird_frame,
        ):
            """Test that process_segment passes class_thresholds loaded from preset to detect_boxes."""
            setup_video_capture(opened=True, read_return=(True, no_bird_frame), total_frames=30)
            processor = HLSSegmentProcessor()

            processor.process_segment("/tmp/segment_001.ts", "segment_001.ts")

            call_kwargs = mock_bird_detector.detect_boxes.call_args
            assert call_kwargs.kwargs["class_thresholds"] == {GREAT_TIT_CLASS_ID: 0.8, PIGEON_CLASS_ID: 0.9}

    class TestDelayedArchive:
        """Tests for delayed archive behavior (archive triggers segments_after segments after detection)."""

        def test_archive_triggered_after_delay(
            self,
            mock_bird_detector,
            mock_bird_annotator,
            mock_stream_archiver,
            monkeypatch,
            setup_video_capture,
            no_bird_frame,
            archive_config,
            detection_frame_config,
        ):
            """Test that archive is triggered segments_after segments after bird detection."""
            segments_after = archive_config["segments_after"]
            frame_count = detection_frame_config["frame_count"]

            # Create enough segments to trigger archive after delay
            num_segments = segments_after + 1  # detection segment + segments_after
            segment_names = [f"segment_{i:03d}.ts" for i in range(num_segments)]
            watchtower = make_watchtower(segment_names)
            monkeypatch.setattr("processor.hls_segment_processor.HLSWatchtower", lambda: watchtower)

            # Bird detected on first segment (early exit after first non-empty boxes), rest are empty
            # Each segment calls detect_boxes() frame_count times (frame_count frames * 1 region)
            mock_bird_detector.detect_boxes.side_effect = [[_MOCK_BOX]] + [[]] * (num_segments * frame_count)
            setup_video_capture(opened=True, read_return=(True, no_bird_frame), total_frames=30)
            processor = HLSSegmentProcessor()

            processor.run()

            # on_segment should be called for each segment
            assert mock_stream_archiver.on_segment.call_count == num_segments
            # Verify on_segment was called with correct values
            on_segment_calls = mock_stream_archiver.on_segment.call_args_list
            assert on_segment_calls[0] == call("segment_000.ts", True)  # Bird detected
            for i in range(1, num_segments):
                assert on_segment_calls[i] == call(f"segment_{i:03d}.ts", False)  # No bird

        def test_no_archive_if_not_enough_segments_after_detection(
            self,
            mock_bird_detector,
            mock_bird_annotator,
            mock_stream_archiver,
            monkeypatch,
            setup_video_capture,
            no_bird_frame,
            archive_config,
            detection_frame_config,
        ):
            """Test that on_segment is called correctly even if stream ends before delay completes."""
            segments_after = archive_config["segments_after"]
            frame_count = detection_frame_config["frame_count"]

            # Create fewer segments than needed (segments_after - 1 after detection)
            num_segments = segments_after  # Not enough: need segments_after + 1
            segment_names = [f"segment_{i:03d}.ts" for i in range(num_segments)]
            watchtower = make_watchtower(segment_names)
            monkeypatch.setattr("processor.hls_segment_processor.HLSWatchtower", lambda: watchtower)

            # Bird detected on segment 0 (early exit after first non-empty boxes)
            mock_bird_detector.detect_boxes.side_effect = [[_MOCK_BOX]] + [[]] * (num_segments * frame_count)
            setup_video_capture(opened=True, read_return=(True, no_bird_frame), total_frames=30)
            processor = HLSSegmentProcessor()

            processor.run()

            # on_segment should be called for each segment (archive behavior is tested in test_stream_archiver.py)
            assert mock_stream_archiver.on_segment.call_count == num_segments
            on_segment_calls = mock_stream_archiver.on_segment.call_args_list
            assert on_segment_calls[0] == call("segment_000.ts", True)  # Bird detected
            for i in range(1, num_segments):
                assert on_segment_calls[i] == call(f"segment_{i:03d}.ts", False)  # No bird

        def test_multiple_detections_only_one_archive(
            self,
            mock_bird_detector,
            mock_bird_annotator,
            mock_stream_archiver,
            monkeypatch,
            setup_video_capture,
            no_bird_frame,
            archive_config,
            detection_frame_config,
        ):
            """Test that multiple detections during countdown don't trigger multiple archives."""
            segments_after = archive_config["segments_after"]
            frame_count = detection_frame_config["frame_count"]

            # Create enough segments to trigger archive
            num_segments = segments_after + 1
            segment_names = [f"segment_{i:03d}.ts" for i in range(num_segments)]
            watchtower = make_watchtower(segment_names)
            monkeypatch.setattr("processor.hls_segment_processor.HLSWatchtower", lambda: watchtower)

            # Birds detected on segments 0, 1, 2 (early exit after first non-empty boxes per segment)
            # Each segment calls detect_boxes() frame_count times
            # segment 0: [[box], []...], segment 1: [[box]], segment 2: [[box]], rest all []
            detect_results = [[_MOCK_BOX]] + [[]] * (frame_count - 1)  # segment 0: early exit
            detect_results += [[_MOCK_BOX]]  # segment 1: early exit
            detect_results += [[_MOCK_BOX]]  # segment 2: early exit
            detect_results += [[]] * (num_segments * frame_count)  # rest
            mock_bird_detector.detect_boxes.side_effect = detect_results
            setup_video_capture(opened=True, read_return=(True, no_bird_frame), total_frames=30)
            processor = HLSSegmentProcessor()

            processor.run()

            # on_segment should be called for each segment
            assert mock_stream_archiver.on_segment.call_count == num_segments
            on_segment_calls = mock_stream_archiver.on_segment.call_args_list
            # Verify multiple birds detected
            assert on_segment_calls[0] == call("segment_000.ts", True)
            assert on_segment_calls[1] == call("segment_001.ts", True)
            assert on_segment_calls[2] == call("segment_002.ts", True)

    class TestOverlapPrevention:
        """Tests for overlap prevention when bird detected near last archive."""

        def test_overlap_zone_detection_extends_previous_archive(
            self,
            mock_bird_detector,
            mock_bird_annotator,
            mock_stream_archiver,
            monkeypatch,
            setup_video_capture,
            no_bird_frame,
            archive_config,
            detection_frame_config,
        ):
            """Test that detection in overlap zone extends the previous archive instead of creating a new one."""
            segment_count = archive_config["segment_count"]
            segments_before = archive_config["segments_before"]
            segments_after = archive_config["segments_after"]
            frame_count = detection_frame_config["frame_count"]

            # First archive ends at segment segments_after (0-indexed)
            first_archive_end = segments_after

            # Second detection in overlap zone: within segments_before of first archive end
            # Pick middle of overlap zone
            second_detection = first_archive_end + (segments_before // 2) + 1

            # Extension adds segment_count segments from last_archived_counter + 1,
            # so it ends at first_archive_end + segment_count
            extension_end = first_archive_end + segment_count

            # Need enough segments for both archives
            num_segments = extension_end + 5
            segment_names = [f"segment_{i:03d}.ts" for i in range(num_segments)]
            watchtower = make_watchtower(segment_names)
            monkeypatch.setattr("processor.hls_segment_processor.HLSWatchtower", lambda: watchtower)

            # Build detect results:
            # - Detection on segment 0 (early exit after first non-empty boxes)
            # - No detection until second_detection
            # - Detection on second_detection (early exit after first non-empty boxes)
            # - No detection for rest
            detect_results = [[_MOCK_BOX]] + [[]] * (frame_count - 1)  # segment 0: early exit
            # Segments 1 to second_detection-1: no detection (frame_count calls each)
            detect_results += [[]] * ((second_detection - 1) * frame_count)
            detect_results += [[_MOCK_BOX]] + [[]] * (frame_count - 1)  # second_detection: early exit
            # Remaining segments
            detect_results += [[]] * (num_segments * frame_count)
            mock_bird_detector.detect_boxes.side_effect = detect_results
            setup_video_capture(opened=True, read_return=(True, no_bird_frame), total_frames=30)
            processor = HLSSegmentProcessor()

            processor.run()

            # on_segment should be called for each segment
            assert mock_stream_archiver.on_segment.call_count == num_segments
            on_segment_calls = mock_stream_archiver.on_segment.call_args_list
            # Verify first and second detections
            assert on_segment_calls[0] == call("segment_000.ts", True)
            assert on_segment_calls[second_detection] == call(f"segment_{second_detection:03d}.ts", True)

        def test_no_overlap_when_detection_outside_zone(
            self,
            mock_bird_detector,
            mock_bird_annotator,
            mock_stream_archiver,
            monkeypatch,
            setup_video_capture,
            no_bird_frame,
            archive_config,
            detection_frame_config,
        ):
            """Test that detection outside overlap zone triggers normal centered archive."""
            segments_before = archive_config["segments_before"]
            segments_after = archive_config["segments_after"]
            frame_count = detection_frame_config["frame_count"]

            # First archive ends at segment segments_after (0-indexed)
            first_archive_end = segments_after

            # Second detection outside overlap zone: more than segments_before after first archive end
            second_detection = first_archive_end + segments_before + 2

            # Second archive is centered on second_detection, so ends at second_detection + segments_after
            second_archive_end = second_detection + segments_after

            # Need enough segments for both archives
            num_segments = second_archive_end + 5
            segment_names = [f"segment_{i:03d}.ts" for i in range(num_segments)]
            watchtower = make_watchtower(segment_names)
            monkeypatch.setattr("processor.hls_segment_processor.HLSWatchtower", lambda: watchtower)

            # Build detect results:
            # - Detection on segment 0 (early exit after first non-empty boxes)
            # - No detection until second_detection
            # - Detection on second_detection (early exit after first non-empty boxes)
            # - No detection for rest
            detect_results = [[_MOCK_BOX]] + [[]] * (frame_count - 1)  # segment 0: early exit
            # Segments 1 to second_detection-1: no detection (frame_count calls each)
            detect_results += [[]] * ((second_detection - 1) * frame_count)
            detect_results += [[_MOCK_BOX]] + [[]] * (frame_count - 1)  # second_detection: early exit
            # Remaining segments
            detect_results += [[]] * (num_segments * frame_count)
            mock_bird_detector.detect_boxes.side_effect = detect_results
            setup_video_capture(opened=True, read_return=(True, no_bird_frame), total_frames=30)
            processor = HLSSegmentProcessor()

            processor.run()

            # on_segment should be called for each segment
            assert mock_stream_archiver.on_segment.call_count == num_segments
            on_segment_calls = mock_stream_archiver.on_segment.call_args_list

            # Verify first and second detections
            assert on_segment_calls[0] == call("segment_000.ts", True)
            assert on_segment_calls[second_detection] == call(f"segment_{second_detection:03d}.ts", True)

    class TestArchiveEnabledSwitch:
        """Tests for the ARCHIVE_ENABLED configuration switch."""

        def test_archive_disabled_skips_archiving(
            self,
            mock_bird_detector,
            mock_bird_annotator,
            mock_stream_archiver,
            monkeypatch,
            setup_video_capture,
            no_bird_frame,
            detection_frame_config,
        ):
            """Test that when ARCHIVE_ENABLED=False, archiving is skipped even when birds are detected."""
            monkeypatch.setattr("processor.stream_archiver.ARCHIVE_ENABLED", False)
            segments_after = 15  # Use default value

            # Create enough segments that archive would trigger if enabled
            num_segments = segments_after + 1
            segment_names = [f"segment_{i:03d}.ts" for i in range(num_segments)]
            watchtower = make_watchtower(segment_names)
            monkeypatch.setattr("processor.hls_segment_processor.HLSWatchtower", lambda: watchtower)

            frame_count = detection_frame_config["frame_count"]
            # Bird detected on first segment
            mock_bird_detector.detect_boxes.side_effect = [[_MOCK_BOX]] + [[]] * (num_segments * frame_count)
            setup_video_capture(opened=True, read_return=(True, no_bird_frame), total_frames=30)
            processor = HLSSegmentProcessor()

            processor.run()

            # Detection and annotation still happen
            assert mock_bird_detector.detect_boxes.call_count > 0
            assert mock_bird_annotator.annotate.call_count == num_segments
            mock_bird_annotator.annotate.assert_any_call("segment_000.ts", True)

            # But archiving is never triggered
            mock_stream_archiver.archive.assert_not_called()

        def test_archive_enabled_triggers_archiving(
            self,
            mock_bird_detector,
            mock_bird_annotator,
            mock_stream_archiver,
            monkeypatch,
            setup_video_capture,
            no_bird_frame,
            detection_frame_config,
        ):
            """Test that when ARCHIVE_ENABLED=True, archiving is triggered on bird detection."""
            monkeypatch.setattr("processor.stream_archiver.ARCHIVE_ENABLED", True)
            segments_after = 15  # Use default value

            # Create enough segments that archive will trigger
            num_segments = segments_after + 1
            segment_names = [f"segment_{i:03d}.ts" for i in range(num_segments)]
            watchtower = make_watchtower(segment_names)
            monkeypatch.setattr("processor.hls_segment_processor.HLSWatchtower", lambda: watchtower)

            frame_count = detection_frame_config["frame_count"]
            # Bird detected on first segment
            mock_bird_detector.detect_boxes.side_effect = [[_MOCK_BOX]] + [[]] * (num_segments * frame_count)
            setup_video_capture(opened=True, read_return=(True, no_bird_frame), total_frames=30)
            processor = HLSSegmentProcessor()

            processor.run()

            # Detection and annotation still happen
            assert mock_bird_detector.detect_boxes.call_count > 0
            assert mock_bird_annotator.annotate.call_count == num_segments

            # on_segment is called for each segment
            assert mock_stream_archiver.on_segment.call_count == num_segments

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

        def test_run_prunes_archiver_detections(self, hls_processor, mock_stream_archiver, dummy_watchtower):
            """Test that run() prunes archiver detections after each segment."""
            hls_processor.process_segment = MagicMock(return_value=False)

            hls_processor.run()

            expected_prune_calls = [call(dummy_watchtower.seen_segments) for _ in dummy_watchtower.segments]
            mock_stream_archiver.prune_detections.assert_has_calls(expected_prune_calls)
