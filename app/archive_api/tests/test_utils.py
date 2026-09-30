from datetime import date

from archive_api.utils import (
    parse_annotations_filter,
    parse_bird_filter,
    parse_bool_filter,
    parse_date,
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
