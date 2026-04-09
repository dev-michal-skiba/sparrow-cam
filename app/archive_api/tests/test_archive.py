import pytest


def make_stream(archive_root, year, month, day, stream_name):
    """Create a stream directory in the archive structure."""
    path = archive_root / year / month / day / stream_name
    path.mkdir(parents=True, exist_ok=True)
    return path


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
        assert data == {"2025": {"01": {"15": {"auto_2025-01-15T120000Z_abc": {}}}}}

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
            assert stream_meta == {}

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
        assert resp.get_json()["2025"]["01"]["15"]["auto_stream"] == {}
