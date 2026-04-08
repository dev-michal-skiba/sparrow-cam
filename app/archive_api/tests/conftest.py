import pytest

from archive_api.app import app as flask_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Flask test client with archive path pointing to a temp directory."""
    monkeypatch.setattr("archive_api.app.ARCHIVE_PATH", tmp_path)
    flask_app.config["TESTING"] = True
    with flask_app.test_client() as client:
        yield client, tmp_path
