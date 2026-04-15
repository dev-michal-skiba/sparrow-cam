import json

import pytest


def make_stream(archive_root, year, month, day, stream_name):
    """Create a stream directory in the archive structure."""
    path = archive_root / year / month / day / stream_name
    path.mkdir(parents=True, exist_ok=True)
    return path


def make_stream_with_birds(archive_root, year, month, day, stream_name, birds):
    """Create a stream directory with bird detection metadata."""
    stream_path = make_stream(archive_root, year, month, day, stream_name)
    meta = {"detections": {"segment1.ts": [{"class": bird} for bird in birds]}}
    meta_file = stream_path / "meta.json"
    with meta_file.open("w") as f:
        json.dump(meta, f)
    return stream_path


class TestDateValidation:
    def test_missing_from(self, client):
        c, _ = client
        resp = c.get("/?to=2025-01-31")
        assert resp.status_code == 400
        assert "from" in resp.get_json()["error"]

    def test_missing_to(self, client):
        c, _ = client
        resp = c.get("/?from=2025-01-01")
        assert resp.status_code == 400
        assert "to" in resp.get_json()["error"]

    def test_missing_both(self, client):
        c, _ = client
        resp = c.get("/")
        assert resp.status_code == 400

    @pytest.mark.parametrize("from_date", ["2025/01/01", "01-01-2025", "2025-1-1", "20250101", "2025-13-01"])
    def test_invalid_from_format(self, client, from_date):
        c, _ = client
        resp = c.get(f"/?from={from_date}&to=2025-01-31")
        assert resp.status_code == 400
        assert "from" in resp.get_json()["error"]

    @pytest.mark.parametrize("to_date", ["2025/01/31", "31-01-2025", "2025-1-31", "20250131", "2025-01-32"])
    def test_invalid_to_format(self, client, to_date):
        c, _ = client
        resp = c.get(f"/?from=2025-01-01&to={to_date}")
        assert resp.status_code == 400
        assert "to" in resp.get_json()["error"]

    def test_from_after_to(self, client):
        c, _ = client
        resp = c.get("/?from=2025-01-31&to=2025-01-01")
        assert resp.status_code == 400
        assert "error" in resp.get_json()

    def test_range_exactly_31_days(self, client):
        c, _ = client
        resp = c.get("/?from=2025-01-01&to=2025-01-31")
        assert resp.status_code == 200

    def test_range_exceeds_31_days(self, client):
        c, _ = client
        resp = c.get("/?from=2025-01-01&to=2025-02-01")
        assert resp.status_code == 400
        assert "31" in resp.get_json()["error"]

    def test_same_day_range(self, client):
        c, _ = client
        resp = c.get("/?from=2025-01-15&to=2025-01-15")
        assert resp.status_code == 200


class TestArchiveListing:
    def test_empty_archive(self, client):
        c, _ = client
        resp = c.get("/?from=2025-01-01&to=2025-01-31")
        assert resp.status_code == 200
        assert resp.get_json() == {}

    def test_single_stream(self, client):
        c, archive_root = client
        make_stream(archive_root, "2025", "01", "15", "auto_2025-01-15T120000Z_abc")

        resp = c.get("/?from=2025-01-01&to=2025-01-31")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data == {"2025": {"01": {"15": {"auto_2025-01-15T120000Z_abc": {"birds": []}}}}}

    def test_multiple_streams_same_day(self, client):
        c, archive_root = client
        make_stream(archive_root, "2025", "01", "15", "auto_2025-01-15T100000Z_aaa")
        make_stream(archive_root, "2025", "01", "15", "auto_2025-01-15T110000Z_bbb")

        resp = c.get("/?from=2025-01-15&to=2025-01-15")
        assert resp.status_code == 200
        data = resp.get_json()
        assert set(data["2025"]["01"]["15"].keys()) == {
            "auto_2025-01-15T100000Z_aaa",
            "auto_2025-01-15T110000Z_bbb",
        }
        for stream_meta in data["2025"]["01"]["15"].values():
            assert stream_meta == {"birds": []}

    def test_streams_across_months(self, client):
        c, archive_root = client
        make_stream(archive_root, "2025", "12", "31", "auto_2025-12-31T120000Z_abc")
        make_stream(archive_root, "2026", "01", "01", "auto_2026-01-01T120000Z_def")

        resp = c.get("/?from=2025-12-31&to=2026-01-01")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "2025" in data
        assert "12" in data["2025"]
        assert "31" in data["2025"]["12"]
        assert "2026" in data
        assert "01" in data["2026"]
        assert "01" in data["2026"]["01"]

    def test_streams_outside_range_excluded(self, client):
        c, archive_root = client
        make_stream(archive_root, "2025", "01", "01", "stream_before")
        make_stream(archive_root, "2025", "01", "15", "stream_in_range")
        make_stream(archive_root, "2025", "01", "31", "stream_after")

        resp = c.get("/?from=2025-01-10&to=2025-01-20")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "stream_before" not in str(data)
        assert "stream_after" not in str(data)
        assert "stream_in_range" in str(data)

    def test_gte_from_date(self, client):
        c, archive_root = client
        make_stream(archive_root, "2025", "01", "10", "stream_on_from")

        resp = c.get("/?from=2025-01-10&to=2025-01-20")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "10" in data["2025"]["01"]

    def test_lte_to_date(self, client):
        c, archive_root = client
        make_stream(archive_root, "2025", "01", "20", "stream_on_to")

        resp = c.get("/?from=2025-01-10&to=2025-01-20")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "20" in data["2025"]["01"]

    def test_stream_metadata_is_empty(self, client):
        c, archive_root = client
        make_stream(archive_root, "2025", "01", "15", "auto_stream")

        resp = c.get("/?from=2025-01-15&to=2025-01-15")
        assert resp.status_code == 200
        assert resp.get_json()["2025"]["01"]["15"]["auto_stream"] == {"birds": []}

    def test_stream_with_birds_metadata(self, client):
        c, archive_root = client
        make_stream_with_birds(archive_root, "2025", "01", "15", "stream_with_birds", ["sparrow", "cardinal"])

        resp = c.get("/?from=2025-01-15&to=2025-01-15")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["2025"]["01"]["15"]["stream_with_birds"] == {"birds": ["cardinal", "sparrow"]}

    def test_bird_filter_single_match(self, client):
        c, archive_root = client
        make_stream_with_birds(archive_root, "2025", "01", "15", "stream_with_sparrow", ["sparrow"])
        make_stream_with_birds(archive_root, "2025", "01", "15", "stream_with_cardinal", ["cardinal"])

        resp = c.get("/?from=2025-01-15&to=2025-01-15&birds=sparrow")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "stream_with_sparrow" in data["2025"]["01"]["15"]
        assert "stream_with_cardinal" not in data["2025"]["01"]["15"]

    def test_bird_filter_multiple_birds(self, client):
        c, archive_root = client
        make_stream_with_birds(archive_root, "2025", "01", "15", "stream_sparrow_cardinal", ["sparrow", "cardinal"])
        make_stream_with_birds(archive_root, "2025", "01", "15", "stream_only_jay", ["jay"])

        resp = c.get("/?from=2025-01-15&to=2025-01-15&birds=sparrow,cardinal")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "stream_sparrow_cardinal" in data["2025"]["01"]["15"]
        assert "stream_only_jay" not in data["2025"]["01"]["15"]

    def test_bird_filter_no_matches(self, client):
        c, archive_root = client
        make_stream_with_birds(archive_root, "2025", "01", "15", "stream_with_sparrow", ["sparrow"])

        resp = c.get("/?from=2025-01-15&to=2025-01-15&birds=cardinal")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data == {}

    def test_bird_filter_empty_parameter(self, client):
        c, archive_root = client
        make_stream_with_birds(archive_root, "2025", "01", "15", "stream_with_birds", ["sparrow"])

        resp = c.get("/?from=2025-01-15&to=2025-01-15&birds=")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "stream_with_birds" in data["2025"]["01"]["15"]


class TestAdjacentEndpoint:
    def test_missing_year(self, client):
        c, _ = client
        resp = c.get("/adjacent?month=01&day=15&stream=test")
        assert resp.status_code == 400
        assert "Missing required parameters" in resp.get_json()["error"]

    def test_missing_month(self, client):
        c, _ = client
        resp = c.get("/adjacent?year=2025&day=15&stream=test")
        assert resp.status_code == 400
        assert "Missing required parameters" in resp.get_json()["error"]

    def test_missing_day(self, client):
        c, _ = client
        resp = c.get("/adjacent?year=2025&month=01&stream=test")
        assert resp.status_code == 400
        assert "Missing required parameters" in resp.get_json()["error"]

    def test_missing_stream(self, client):
        c, _ = client
        resp = c.get("/adjacent?year=2025&month=01&day=15")
        assert resp.status_code == 400
        assert "Missing required parameters" in resp.get_json()["error"]

    def test_missing_all_parameters(self, client):
        c, _ = client
        resp = c.get("/adjacent")
        assert resp.status_code == 400
        assert "Missing required parameters" in resp.get_json()["error"]

    @pytest.mark.parametrize(
        "year,month,day",
        [
            ("25", "01", "15"),  # year not 4 digits
            ("2025", "1", "15"),  # month not 2 digits
            ("2025", "01", "5"),  # day not 2 digits
            ("2025", "13", "01"),  # month out of range
            ("2025", "01", "32"),  # day out of range
            ("2025", "02", "30"),  # day invalid for month
        ],
    )
    def test_invalid_date(self, client, year, month, day):
        c, _ = client
        resp = c.get(f"/adjacent?year={year}&month={month}&day={day}&stream=test")
        assert resp.status_code == 400
        assert "error" in resp.get_json()

    def test_recording_not_found(self, client):
        c, _ = client
        resp = c.get("/adjacent?year=2025&month=01&day=15&stream=nonexistent")
        assert resp.status_code == 404
        assert "Recording not found" in resp.get_json()["error"]

    def test_recording_not_found_empty_archive(self, client):
        c, archive_root = client
        make_stream(archive_root, "2025", "01", "15", "stream_a")

        resp = c.get("/adjacent?year=2025&month=01&day=15&stream=wrong_stream")
        assert resp.status_code == 404

    def test_single_recording_no_adjacent(self, client):
        c, archive_root = client
        make_stream(archive_root, "2025", "01", "15", "stream_a")

        resp = c.get("/adjacent?year=2025&month=01&day=15&stream=stream_a")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["previous"] is None
        assert data["next"] is None

    def test_first_recording_has_next(self, client):
        c, archive_root = client
        make_stream(archive_root, "2025", "01", "15", "stream_a")
        make_stream(archive_root, "2025", "01", "15", "stream_b")

        resp = c.get("/adjacent?year=2025&month=01&day=15&stream=stream_a")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["previous"] is None
        assert data["next"] == {
            "year": "2025",
            "month": "01",
            "day": "15",
            "stream": "stream_b",
        }

    def test_last_recording_has_previous(self, client):
        c, archive_root = client
        make_stream(archive_root, "2025", "01", "15", "stream_a")
        make_stream(archive_root, "2025", "01", "15", "stream_b")

        resp = c.get("/adjacent?year=2025&month=01&day=15&stream=stream_b")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["previous"] == {
            "year": "2025",
            "month": "01",
            "day": "15",
            "stream": "stream_a",
        }
        assert data["next"] is None

    def test_middle_recording_has_both(self, client):
        c, archive_root = client
        make_stream(archive_root, "2025", "01", "15", "stream_a")
        make_stream(archive_root, "2025", "01", "15", "stream_b")
        make_stream(archive_root, "2025", "01", "15", "stream_c")

        resp = c.get("/adjacent?year=2025&month=01&day=15&stream=stream_b")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["previous"] == {
            "year": "2025",
            "month": "01",
            "day": "15",
            "stream": "stream_a",
        }
        assert data["next"] == {
            "year": "2025",
            "month": "01",
            "day": "15",
            "stream": "stream_c",
        }

    def test_streams_across_days(self, client):
        c, archive_root = client
        make_stream(archive_root, "2025", "01", "14", "stream_a")
        make_stream(archive_root, "2025", "01", "15", "stream_b")
        make_stream(archive_root, "2025", "01", "16", "stream_c")

        # Request middle stream from day 15
        resp = c.get("/adjacent?year=2025&month=01&day=15&stream=stream_b")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["previous"] == {
            "year": "2025",
            "month": "01",
            "day": "14",
            "stream": "stream_a",
        }
        assert data["next"] == {
            "year": "2025",
            "month": "01",
            "day": "16",
            "stream": "stream_c",
        }

    def test_streams_across_months(self, client):
        c, archive_root = client
        make_stream(archive_root, "2025", "01", "31", "stream_a")
        make_stream(archive_root, "2025", "02", "01", "stream_b")
        make_stream(archive_root, "2025", "02", "02", "stream_c")

        # Request first stream of February
        resp = c.get("/adjacent?year=2025&month=02&day=01&stream=stream_b")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["previous"] == {
            "year": "2025",
            "month": "01",
            "day": "31",
            "stream": "stream_a",
        }
        assert data["next"] == {
            "year": "2025",
            "month": "02",
            "day": "02",
            "stream": "stream_c",
        }

    def test_streams_across_years(self, client):
        c, archive_root = client
        make_stream(archive_root, "2024", "12", "31", "stream_a")
        make_stream(archive_root, "2025", "01", "01", "stream_b")
        make_stream(archive_root, "2025", "01", "02", "stream_c")

        # Request first stream of 2025
        resp = c.get("/adjacent?year=2025&month=01&day=01&stream=stream_b")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["previous"] == {
            "year": "2024",
            "month": "12",
            "day": "31",
            "stream": "stream_a",
        }
        assert data["next"] == {
            "year": "2025",
            "month": "01",
            "day": "02",
            "stream": "stream_c",
        }

    def test_alphabetical_sorting_within_day(self, client):
        c, archive_root = client
        # Create in non-alphabetical order
        make_stream(archive_root, "2025", "01", "15", "zebra")
        make_stream(archive_root, "2025", "01", "15", "apple")
        make_stream(archive_root, "2025", "01", "15", "banana")

        resp = c.get("/adjacent?year=2025&month=01&day=15&stream=banana")
        assert resp.status_code == 200
        data = resp.get_json()
        # banana should be between apple and zebra when sorted
        assert data["previous"] == {
            "year": "2025",
            "month": "01",
            "day": "15",
            "stream": "apple",
        }
        assert data["next"] == {
            "year": "2025",
            "month": "01",
            "day": "15",
            "stream": "zebra",
        }

    def test_adjacent_with_bird_filter(self, client):
        c, archive_root = client
        make_stream_with_birds(archive_root, "2025", "01", "15", "stream_sparrow", ["sparrow"])
        make_stream_with_birds(archive_root, "2025", "01", "15", "stream_cardinal", ["cardinal"])
        make_stream_with_birds(archive_root, "2025", "01", "15", "stream_jay", ["jay"])

        resp = c.get("/adjacent?year=2025&month=01&day=15&stream=stream_cardinal&birds=cardinal")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["previous"] is None
        assert data["next"] is None

    def test_adjacent_with_bird_filter_multiple_birds(self, client):
        c, archive_root = client
        make_stream_with_birds(archive_root, "2025", "01", "14", "stream1", ["jay"])
        make_stream_with_birds(archive_root, "2025", "01", "15", "stream2", ["sparrow"])
        make_stream_with_birds(archive_root, "2025", "01", "16", "stream3", ["cardinal"])

        resp = c.get("/adjacent?year=2025&month=01&day=15&stream=stream2&birds=sparrow,jay")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["previous"] == {
            "year": "2025",
            "month": "01",
            "day": "14",
            "stream": "stream1",
        }
        assert data["next"] is None

    def test_adjacent_with_bird_filter_not_found(self, client):
        c, archive_root = client
        make_stream_with_birds(archive_root, "2025", "01", "15", "stream_sparrow", ["sparrow"])

        resp = c.get("/adjacent?year=2025&month=01&day=15&stream=stream_sparrow&birds=cardinal")
        assert resp.status_code == 404
        assert "Recording not found" in resp.get_json()["error"]
