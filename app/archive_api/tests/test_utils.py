import json
from datetime import date

from archive_api.utils import (
    get_stream_birds,
    get_stream_manual_annotations,
    parse_annotations_filter,
    parse_bird_filter,
    parse_bool_filter,
    parse_date,
    stream_matches_annotations_filter,
    stream_matches_filter,
)


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

    def test_returns_birds_from_manual_annotations(self, tmp_path):
        meta_path = tmp_path / "meta.json"
        meta_path.write_text(
            json.dumps(
                {
                    "manual_annotations": {
                        "seg1.ts": [{"bird_class": "sparrow"}, {"bird_class": "cardinal"}],
                        "seg2.ts": [{"bird_class": "sparrow"}],
                    }
                }
            )
        )
        assert get_stream_birds(tmp_path) == ["cardinal", "sparrow"]

    def test_prefers_manual_annotations_over_detections(self, tmp_path):
        meta_path = tmp_path / "meta.json"
        meta_path.write_text(
            json.dumps(
                {
                    "manual_annotations": {
                        "seg1.ts": [{"bird_class": "cardinal"}],
                    },
                    "detections": {
                        "seg1.ts": [{"class": "sparrow"}],
                        "seg2.ts": [{"class": "jay"}],
                    },
                }
            )
        )
        assert get_stream_birds(tmp_path) == ["cardinal"]

    def test_ignores_detections_when_manual_annotations_present(self, tmp_path):
        meta_path = tmp_path / "meta.json"
        meta_path.write_text(
            json.dumps(
                {
                    "manual_annotations": {},
                    "detections": {
                        "seg1.ts": [{"class": "sparrow"}],
                    },
                }
            )
        )
        assert get_stream_birds(tmp_path) == []

    def test_handles_manual_annotations_with_missing_bird_class(self, tmp_path):
        meta_path = tmp_path / "meta.json"
        meta_path.write_text(
            json.dumps(
                {
                    "manual_annotations": {
                        "seg1.ts": [{"other_field": "value"}, {"bird_class": "sparrow"}],
                    }
                }
            )
        )
        assert get_stream_birds(tmp_path) == ["sparrow"]


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


class TestParseBoolFilter:
    def test_none_returns_false(self):
        assert parse_bool_filter(None) is False

    def test_true_string_returns_true(self):
        assert parse_bool_filter("true") is True

    def test_1_string_returns_true(self):
        assert parse_bool_filter("1") is True

    def test_false_string_returns_false(self):
        assert parse_bool_filter("false") is False

    def test_0_string_returns_false(self):
        assert parse_bool_filter("0") is False

    def test_empty_string_returns_false(self):
        assert parse_bool_filter("") is False

    def test_arbitrary_string_returns_false(self):
        assert parse_bool_filter("yes") is False


class TestParseAnnotationsFilter:
    def test_both_none_returns_defaults(self):
        exclude_fp, exclude_ann, err = parse_annotations_filter(None, None)
        assert exclude_fp is False
        assert exclude_ann is False
        assert err is None

    def test_exclude_false_positives_true(self):
        exclude_fp, exclude_ann, err = parse_annotations_filter("true", None)
        assert exclude_fp is True
        assert exclude_ann is False
        assert err is None

    def test_exclude_annotated_true(self):
        exclude_fp, exclude_ann, err = parse_annotations_filter(None, "true")
        assert exclude_fp is False
        assert exclude_ann is True
        assert err is None

    def test_both_set_returns_error(self):
        exclude_fp, exclude_ann, err = parse_annotations_filter("true", "true")
        assert exclude_fp is False
        assert exclude_ann is False
        assert err is not None
        assert "exclude_false_positives and exclude_annotated cannot both be set" in err["error"]

    def test_exclude_false_positives_with_1(self):
        exclude_fp, exclude_ann, err = parse_annotations_filter("1", None)
        assert exclude_fp is True
        assert exclude_ann is False
        assert err is None

    def test_exclude_annotated_with_1(self):
        exclude_fp, exclude_ann, err = parse_annotations_filter(None, "1")
        assert exclude_fp is False
        assert exclude_ann is True
        assert err is None

    def test_both_set_with_1_returns_error(self):
        exclude_fp, exclude_ann, err = parse_annotations_filter("1", "1")
        assert exclude_fp is False
        assert exclude_ann is False
        assert err is not None


class TestGetStreamManualAnnotations:
    def test_returns_none_when_no_meta(self, tmp_path):
        assert get_stream_manual_annotations(tmp_path) is None

    def test_returns_none_when_no_manual_annotations_key(self, tmp_path):
        meta_path = tmp_path / "meta.json"
        meta_path.write_text(json.dumps({"detections": {}}))
        assert get_stream_manual_annotations(tmp_path) is None

    def test_returns_manual_annotations_dict(self, tmp_path):
        meta_path = tmp_path / "meta.json"
        annotations = {"seg1.ts": "false positive"}
        meta_path.write_text(json.dumps({"detections": {}, "manual_annotations": annotations}))
        assert get_stream_manual_annotations(tmp_path) == annotations

    def test_returns_empty_dict_when_annotations_empty(self, tmp_path):
        meta_path = tmp_path / "meta.json"
        meta_path.write_text(json.dumps({"detections": {}, "manual_annotations": {}}))
        assert get_stream_manual_annotations(tmp_path) == {}

    def test_handles_corrupt_meta(self, tmp_path):
        meta_path = tmp_path / "meta.json"
        meta_path.write_text("not json")
        assert get_stream_manual_annotations(tmp_path) is None

    def test_handles_missing_file(self, tmp_path):
        assert get_stream_manual_annotations(tmp_path) is None


class TestStreamMatchesAnnotationsFilter:
    def test_no_flags_returns_true_for_no_annotations(self, tmp_path):
        assert (
            stream_matches_annotations_filter(tmp_path, exclude_false_positives=False, exclude_annotated=False) is True
        )

    def test_no_flags_returns_true_with_non_empty_annotations(self, tmp_path):
        meta_path = tmp_path / "meta.json"
        meta_path.write_text(json.dumps({"manual_annotations": {"seg.ts": "false positive"}}))
        assert (
            stream_matches_annotations_filter(tmp_path, exclude_false_positives=False, exclude_annotated=False) is True
        )

    def test_no_flags_returns_true_with_empty_annotations(self, tmp_path):
        meta_path = tmp_path / "meta.json"
        meta_path.write_text(json.dumps({"manual_annotations": {}}))
        assert (
            stream_matches_annotations_filter(tmp_path, exclude_false_positives=False, exclude_annotated=False) is True
        )

    def test_exclude_annotated_true_excludes_streams_with_annotations(self, tmp_path):
        meta_path = tmp_path / "meta.json"
        meta_path.write_text(json.dumps({"manual_annotations": {"seg.ts": "false positive"}}))
        assert (
            stream_matches_annotations_filter(tmp_path, exclude_false_positives=False, exclude_annotated=True) is False
        )

    def test_exclude_annotated_true_excludes_streams_with_empty_annotations(self, tmp_path):
        meta_path = tmp_path / "meta.json"
        meta_path.write_text(json.dumps({"manual_annotations": {}}))
        assert (
            stream_matches_annotations_filter(tmp_path, exclude_false_positives=False, exclude_annotated=True) is False
        )

    def test_exclude_annotated_true_includes_streams_without_annotations(self, tmp_path):
        assert (
            stream_matches_annotations_filter(tmp_path, exclude_false_positives=False, exclude_annotated=True) is True
        )

    def test_exclude_false_positives_true_includes_no_annotations(self, tmp_path):
        assert (
            stream_matches_annotations_filter(tmp_path, exclude_false_positives=True, exclude_annotated=False) is True
        )

    def test_exclude_false_positives_true_includes_non_empty_annotations(self, tmp_path):
        meta_path = tmp_path / "meta.json"
        meta_path.write_text(json.dumps({"manual_annotations": {"seg.ts": "false positive"}}))
        assert (
            stream_matches_annotations_filter(tmp_path, exclude_false_positives=True, exclude_annotated=False) is True
        )

    def test_exclude_false_positives_true_excludes_empty_annotations(self, tmp_path):
        meta_path = tmp_path / "meta.json"
        meta_path.write_text(json.dumps({"manual_annotations": {}}))
        assert (
            stream_matches_annotations_filter(tmp_path, exclude_false_positives=True, exclude_annotated=False) is False
        )
