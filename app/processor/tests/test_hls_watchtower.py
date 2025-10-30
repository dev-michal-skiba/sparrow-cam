import os
import pytest
from unittest.mock import patch, mock_open
from processor.hls_watchtower import HLSWatchtower


def assert_iterator_exhausted(iterator):
    """Assert that the iterator/generator has been exhausted and raises StopIteration."""
    with pytest.raises(RuntimeError) as e:
        next(iterator)
    assert str(e.value) == "generator raised StopIteration"


class TestHLSWatchtower:
    """Test suite for HLSWatchtower class."""

    def test_init(self):
        """Test HLSWatchtower initialization."""
        watchtower = HLSWatchtower()
        assert watchtower.seen_segments == set()
        assert watchtower.retry_delay == HLSWatchtower.INITIAL_RETRY_DELAY

    def test_read_playlist_file_not_exists(self):
        """Test read_playlist when playlist file doesn't exist."""
        watchtower = HLSWatchtower()

        with (
            patch('os.path.exists', return_value=False),
            patch('time.sleep') as mock_sleep
        ):
            result = watchtower.read_playlist('/fake/path/playlist.m3u8')

        assert result is None
        mock_sleep.assert_called_once_with(HLSWatchtower.INITIAL_RETRY_DELAY)
        assert watchtower.retry_delay == HLSWatchtower.INITIAL_RETRY_DELAY * 1.5

    def test_read_playlist_retry_delay_caps_at_max(self):
        """Test that retry delay caps at MAX_RETRY_DELAY."""
        watchtower = HLSWatchtower()
        watchtower.retry_delay = HLSWatchtower.MAX_RETRY_DELAY - 0.1

        with (
            patch('os.path.exists', return_value=False),
            patch('time.sleep')
        ):
            watchtower.read_playlist('/fake/path/playlist.m3u8')

        assert watchtower.retry_delay == HLSWatchtower.MAX_RETRY_DELAY

    def test_read_playlist_no_segments(self):
        """Test read_playlist when playlist exists but has no segments."""
        watchtower = HLSWatchtower()
        playlist_content = (
            '#EXTM3U\n'
            '#EXT-X-VERSION:3\n'
        )

        with (
            patch('os.path.exists', return_value=True),
            patch('builtins.open', mock_open(read_data=playlist_content)),
            patch('time.sleep') as mock_sleep
        ):
            result = watchtower.read_playlist('/fake/path/playlist.m3u8')

        assert result is None
        mock_sleep.assert_called_once_with(HLSWatchtower.POLL_INTERVAL)

    def test_read_playlist_with_segments(self):
        """Test read_playlist successfully extracts segments."""
        watchtower = HLSWatchtower()
        watchtower.retry_delay = HLSWatchtower.INITIAL_RETRY_DELAY + 1.0
        playlist_content = (
            '#EXTM3U\n'
            '#EXT-X-VERSION:3\n'
            '#EXT-X-TARGETDURATION:2\n'
            '#EXTINF:2.0,\n'
            'segment_001.ts\n'
            '#EXTINF:2.0,\n'
            'segment_002.ts\n'
            '#EXTINF:2.0,\n'
            'segment_003.ts\n'
        )

        with (
            patch('os.path.exists', return_value=True),
            patch('builtins.open', mock_open(read_data=playlist_content))
        ):
            result = watchtower.read_playlist('/fake/path/playlist.m3u8')

        assert result == ['segment_001.ts', 'segment_002.ts', 'segment_003.ts']
        assert watchtower.retry_delay == HLSWatchtower.INITIAL_RETRY_DELAY

    def test_read_playlist_segment_naming_patterns(self):
        """Test that read_playlist correctly matches various segment naming patterns."""
        watchtower = HLSWatchtower()
        playlist_content = (
            '#EXTM3U\n'
            'segment-001.ts\n'
            'segment_002.ts\n'
            'abc123def.ts\n'
            'test-segment_123.ts\n'
        )

        with (
            patch('os.path.exists', return_value=True),
            patch('builtins.open', mock_open(read_data=playlist_content))
        ):
            result = watchtower.read_playlist('/fake/path/playlist.m3u8')

        assert result == ['segment-001.ts', 'segment_002.ts', 'abc123def.ts', 'test-segment_123.ts']

    def test_read_playlist_ignores_invalid_segments(self):
        """Test that read_playlist ignores segments with invalid naming."""
        watchtower = HLSWatchtower()
        playlist_content = (
            '#EXTM3U\n'
            'valid_segment.ts\n'
            'Invalid_Segment.ts\n'
            'segment with spaces.ts\n'
        )

        with (
            patch('os.path.exists', return_value=True),
            patch('builtins.open', mock_open(read_data=playlist_content))
        ):
            result = watchtower.read_playlist('/fake/path/playlist.m3u8')

        assert result == ['valid_segment.ts']

    def test_segments_iterator_yields_new_segments(self):
        """Test that segments_iterator yields only new segments."""
        watchtower = HLSWatchtower()

        with (
            patch.object(watchtower, 'read_playlist') as mock_read_playlist,
            patch('os.path.exists', return_value=True),
            patch('time.sleep')
        ):
            mock_read_playlist.side_effect = [
                ['segment_001.ts', 'segment_002.ts'],
                ['segment_001.ts', 'segment_002.ts', 'segment_003.ts'],
                None,
            ]

            iterator = watchtower.segments_iterator

            segment1 = next(iterator)
            assert segment1 == os.path.join(HLSWatchtower.INPUT_HLS_DIR, 'segment_001.ts')
            segment2 = next(iterator)
            assert segment2 == os.path.join(HLSWatchtower.INPUT_HLS_DIR, 'segment_002.ts')
            segment3 = next(iterator)
            assert segment3 == os.path.join(HLSWatchtower.INPUT_HLS_DIR, 'segment_003.ts')
            assert_iterator_exhausted(iterator)
            assert watchtower.seen_segments == {'segment_001.ts', 'segment_002.ts', 'segment_003.ts'}

    def test_segments_iterator_skips_missing_files(self):
        """Test that segments_iterator skips segments whose files don't exist."""
        watchtower = HLSWatchtower()

        def mock_exists(path):
            return 'segment_001.ts' in path

        with (
            patch.object(watchtower, 'read_playlist') as mock_read_playlist,
            patch('os.path.exists', side_effect=mock_exists),
            patch('time.sleep')
        ):
            mock_read_playlist.side_effect = [
                ['segment_001.ts', 'segment_002.ts'],
                None,
            ]

            iterator = watchtower.segments_iterator

            segment = next(iterator)
            assert segment == os.path.join(HLSWatchtower.INPUT_HLS_DIR, 'segment_001.ts')
            assert_iterator_exhausted(iterator)
            assert 'segment_002.ts' in watchtower.seen_segments

    def test_segments_iterator_cleans_up_old_segments(self):
        """Test that segments_iterator removes old segments from tracking."""
        watchtower = HLSWatchtower()

        with (
            patch.object(watchtower, 'read_playlist') as mock_read_playlist,
            patch('os.path.exists', return_value=True),
            patch('time.sleep')
        ):
            mock_read_playlist.side_effect = [
                ['segment_001.ts', 'segment_002.ts', 'segment_003.ts'],
                ['segment_002.ts', 'segment_003.ts', 'segment_004.ts'],
                None
            ]

            iterator = watchtower.segments_iterator

            # Consume first playlist
            next(iterator)
            next(iterator)
            next(iterator)
            # At this point, seen_segments should have all three
            assert watchtower.seen_segments == {'segment_001.ts', 'segment_002.ts', 'segment_003.ts'}
            # Consume second playlist
            next(iterator)
            assert_iterator_exhausted(iterator)
            assert watchtower.seen_segments == {'segment_002.ts', 'segment_003.ts', 'segment_004.ts'}

    def test_segments_iterator_handles_none_from_read_playlist(self):
        """Test that segments_iterator continues when read_playlist returns None."""
        watchtower = HLSWatchtower()

        with (
            patch.object(watchtower, 'read_playlist') as mock_read_playlist,
            patch('os.path.exists', return_value=True),
            patch('time.sleep')
        ):
            mock_read_playlist.side_effect = [
                None,
                None,
                ['segment_001.ts'],
                None
            ]

            iterator = watchtower.segments_iterator

            segment = next(iterator)
            assert segment == os.path.join(HLSWatchtower.INPUT_HLS_DIR, 'segment_001.ts')
            assert mock_read_playlist.call_count == 3
            assert_iterator_exhausted(iterator)

    def test_segments_iterator_sleeps_between_iterations(self):
        """Test that segments_iterator sleeps with POLL_INTERVAL between checks."""
        watchtower = HLSWatchtower()

        with (
            patch.object(watchtower, 'read_playlist') as mock_read_playlist,
            patch('os.path.exists', return_value=True),
            patch('time.sleep') as mock_sleep
        ):
            mock_read_playlist.side_effect = [
                ['segment_001.ts'],
                ['segment_001.ts', 'segment_002.ts'],
                None
            ]

            iterator = watchtower.segments_iterator

            # Get first segment
            next(iterator)
            # Get second segment
            next(iterator)
            assert_iterator_exhausted(iterator)
            assert mock_sleep.call_count >= 2
            mock_sleep.assert_called_with(HLSWatchtower.POLL_INTERVAL)
