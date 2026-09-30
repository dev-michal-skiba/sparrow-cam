import sqlite3

import pytest

from archive_api.app import app as flask_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Flask test client with archive path and database pointing to a temp directory."""
    # Set up archive path
    monkeypatch.setattr("archive_api.utils.ARCHIVE_PATH", tmp_path)

    # Set up temporary database
    db_path = tmp_path / "index.db"
    monkeypatch.setattr("archive_api.index_db.INDEX_DB_PATH", db_path)

    # Create the recordings table
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE recordings (
            date TEXT NOT NULL,
            stream TEXT NOT NULL,
            detections TEXT,
            manual_annotations TEXT,
            birds TEXT,
            PRIMARY KEY (date, stream)
        )
        """)
    conn.commit()
    conn.close()

    flask_app.config["TESTING"] = True
    with flask_app.test_client() as client:
        yield client, tmp_path
