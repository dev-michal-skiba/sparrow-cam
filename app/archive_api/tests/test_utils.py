import json
from datetime import date

from archive_api.utils import get_stream_birds, parse_bird_filter, parse_date, stream_matches_filter


class TestParseDate:
    def test_valid_date(self):
        result, err = parse_date("2025-01-15", "from")
        assert err is None
        assert result == date(2025, 1, 15)

    def test_missing_value(self):
        result, err = parse_date(None, "from")
        assert result is None
        assert "from" in err["error"]

    def test_invalid_format(self):
        result, err = parse_date("15-01-2025", "from")
        assert result is None
        assert "from" in err["error"]

    def test_invalid_date_value(self):
        result, err = parse_date("2025-13-01", "from")
        assert result is None
        assert err is not None


class TestGetStreamBirds:
    def test_returns_empty_when_no_meta(self, tmp_path):
        assert get_stream_birds(tmp_path) == []

    def test_returns_empty_when_meta_has_no_detections(self, tmp_path):
        meta_path = tmp_path / "meta.json"
        meta_path.write_text(json.dumps({}))
        assert get_stream_birds(tmp_path) == []

    def test_returns_sorted_unique_birds(self, tmp_path):
        meta_path = tmp_path / "meta.json"
        meta_path.write_text(
            json.dumps(
                {
                    "detections": {
                        "seg1.ts": [{"class": "sparrow"}, {"class": "cardinal"}],
                        "seg2.ts": [{"class": "sparrow"}],
                    }
                }
            )
        )
        assert get_stream_birds(tmp_path) == ["cardinal", "sparrow"]

    def test_handles_corrupt_meta(self, tmp_path):
        meta_path = tmp_path / "meta.json"
        meta_path.write_text("not json")
        assert get_stream_birds(tmp_path) == []


class TestParseBirdFilter:
    def test_none_returns_empty(self):
        assert parse_bird_filter(None) == []

    def test_empty_string_returns_empty(self):
        assert parse_bird_filter("") == []

    def test_single_bird(self):
        assert parse_bird_filter("sparrow") == ["sparrow"]

    def test_multiple_birds(self):
        assert parse_bird_filter("sparrow,cardinal") == ["sparrow", "cardinal"]

    def test_strips_whitespace(self):
        assert parse_bird_filter(" sparrow , cardinal ") == ["sparrow", "cardinal"]


class TestStreamMatchesFilter:
    def test_empty_filter_always_matches(self, tmp_path):
        assert stream_matches_filter(tmp_path, []) is True

    def test_matches_when_bird_present(self, tmp_path):
        meta_path = tmp_path / "meta.json"
        meta_path.write_text(json.dumps({"detections": {"seg.ts": [{"class": "sparrow"}]}}))
        assert stream_matches_filter(tmp_path, ["sparrow"]) is True

    def test_no_match_when_bird_absent(self, tmp_path):
        meta_path = tmp_path / "meta.json"
        meta_path.write_text(json.dumps({"detections": {"seg.ts": [{"class": "sparrow"}]}}))
        assert stream_matches_filter(tmp_path, ["cardinal"]) is False
